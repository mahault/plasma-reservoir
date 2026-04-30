"""Bayesian network readout for reservoir computing.

Novel contribution: instead of a single linear readout from reservoir states
to a target, we structure the readout as a directed acyclic graph (DAG) of
Bayesian Ridge regressors.  Each node in the DAG reads from:

    1. The reservoir state vector  (shared nonlinear features)
    2. The outputs of its parent nodes  (structured conditional dependencies)

This lets us:
    - Encode domain knowledge about how observables relate
      (e.g. energy depends on intensity + frequency)
    - Get calibrated uncertainty at every node via Bayesian Ridge
    - Propagate uncertainty through the graph
    - Compare structured vs flat readout to quantify whether
      the DAG structure adds capacity beyond a single linear layer

For dynamic Bayesian networks (temporal tasks), we extend each node's
input to include its own previous-timestep output, giving the DAG
fading-memory structure that mirrors the reservoir's temporal dynamics.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import numpy as np
from sklearn.linear_model import BayesianRidge


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class NodeResult:
    """Per-node prediction output."""
    mean: np.ndarray        # (N,)
    std: np.ndarray         # (N,)
    weights: np.ndarray     # (D_input,)
    alpha: float            # learned precision of weights
    lambda_: float          # learned precision of noise


@dataclass
class BayesNetResult:
    """Full graph prediction output."""
    nodes: dict[str, NodeResult]
    log_marginal_likelihood: float  # sum across all nodes

    def __getitem__(self, node: str) -> NodeResult:
        return self.nodes[node]


@dataclass
class NodeSpec:
    """Specification for one node in the readout DAG."""
    name: str
    parents: list[str] = field(default_factory=list)
    is_target: bool = False     # mark leaf nodes used for final prediction
    prior_alpha: float = 1e-6   # BayesianRidge alpha_init
    prior_lambda: float = 1e-6  # BayesianRidge lambda_init


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------

class BayesNetReadout:
    """DAG-structured Bayesian readout from reservoir states.

    Parameters
    ----------
    nodes : list of NodeSpec defining the DAG structure
    temporal : if True, each node also conditions on its own t-1 output
               (dynamic Bayesian network mode for time-series tasks)
    """

    def __init__(self, nodes: list[NodeSpec], temporal: bool = False):
        self._specs = {n.name: n for n in nodes}
        self._temporal = temporal
        self._models: dict[str, BayesianRidge] = {}
        self._fit_predictions: dict[str, np.ndarray] = {}
        self._graph = self._build_graph()
        self._order = list(nx.topological_sort(self._graph))

    # -- public API ---------------------------------------------------------

    def fit(
        self,
        reservoir_states: np.ndarray,
        targets: dict[str, np.ndarray],
    ) -> float:
        """Train all nodes in topological order.

        Parameters
        ----------
        reservoir_states : (N, D) reservoir state matrix
        targets : {node_name: (N,)} ground truth for every node

        Returns
        -------
        total_log_ml : sum of log marginal likelihoods across nodes
        """
        self._validate_targets(targets)
        N = reservoir_states.shape[0]
        total_log_ml = 0.0

        for node_name in self._order:
            spec = self._specs[node_name]
            X = self._build_node_input(
                node_name, reservoir_states, self._fit_predictions,
                targets=targets, is_training=True,
            )
            y = targets[node_name]

            # trim first row if temporal (no t-1 available)
            if self._temporal:
                X, y = X[1:], y[1:]

            model = BayesianRidge(
                alpha_init=spec.prior_alpha,
                lambda_init=spec.prior_lambda,
                compute_score=True,
            )
            model.fit(X, y)
            self._models[node_name] = model

            # store predictions for downstream children
            pred = model.predict(X)
            if self._temporal:
                # pad first timestep with zero
                pred = np.concatenate([[0.0], pred])
            self._fit_predictions[node_name] = pred
            total_log_ml += model.scores_[-1]

        return total_log_ml

    def predict(self, reservoir_states: np.ndarray) -> BayesNetResult:
        """Forward pass through the DAG on new data.

        Returns BayesNetResult with per-node mean, std, weights.
        """
        if not self._models:
            raise RuntimeError("Call fit() first.")

        N = reservoir_states.shape[0]
        predictions: dict[str, np.ndarray] = {}
        node_results: dict[str, NodeResult] = {}
        total_log_ml = 0.0

        for node_name in self._order:
            model = self._models[node_name]
            X = self._build_node_input(
                node_name, reservoir_states, predictions,
                is_training=False,
            )
            if self._temporal:
                X = X[1:]

            mean, std = model.predict(X, return_std=True)

            if self._temporal:
                mean = np.concatenate([[0.0], mean])
                std = np.concatenate([[std.mean()], std])

            predictions[node_name] = mean
            node_results[node_name] = NodeResult(
                mean=mean,
                std=std,
                weights=model.coef_,
                alpha=model.alpha_,
                lambda_=model.lambda_,
            )
            if model.scores_ is not None and len(model.scores_) > 0:
                total_log_ml += model.scores_[-1]

        return BayesNetResult(nodes=node_results, log_marginal_likelihood=total_log_ml)

    def model_comparison(
        self,
        reservoir_states: np.ndarray,
        targets: dict[str, np.ndarray],
    ) -> dict[str, float]:
        """Compare structured DAG readout vs flat single-node readout.

        For each target node marked is_target=True, trains a flat
        BayesianRidge directly from reservoir states and compares
        log marginal likelihood against the DAG path.

        Returns
        -------
        comparison : {node_name: log_BF} where log_BF > 0 favours DAG
        """
        target_nodes = [n for n, s in self._specs.items() if s.is_target]
        if not target_nodes:
            target_nodes = [self._order[-1]]  # default to last node

        comparison = {}
        for node_name in target_nodes:
            # Flat baseline
            flat = BayesianRidge(compute_score=True)
            flat.fit(reservoir_states, targets[node_name])
            flat_lml = flat.scores_[-1]

            # DAG path: sum log-ML of this node + all ancestors
            dag_lml = 0.0
            ancestors = nx.ancestors(self._graph, node_name) | {node_name}
            for anc in ancestors:
                if anc in self._models:
                    scores = self._models[anc].scores_
                    if scores is not None and len(scores) > 0:
                        dag_lml += scores[-1]

            comparison[node_name] = dag_lml - flat_lml  # log Bayes factor

        return comparison

    @property
    def graph(self) -> nx.DiGraph:
        return self._graph

    @property
    def order(self) -> list[str]:
        return list(self._order)

    @property
    def target_nodes(self) -> list[str]:
        return [n for n, s in self._specs.items() if s.is_target]

    # -- internals ----------------------------------------------------------

    def _build_graph(self) -> nx.DiGraph:
        g = nx.DiGraph()
        for name, spec in self._specs.items():
            g.add_node(name)
            for parent in spec.parents:
                if parent not in self._specs:
                    raise ValueError(
                        f"Node '{name}' lists parent '{parent}' "
                        f"which is not in the node specs."
                    )
                g.add_edge(parent, name)
        if not nx.is_directed_acyclic_graph(g):
            raise ValueError("Node specs contain a cycle — must be a DAG.")
        return g

    def _build_node_input(
        self,
        node_name: str,
        reservoir_states: np.ndarray,
        predictions: dict[str, np.ndarray],
        targets: dict[str, np.ndarray] | None = None,
        is_training: bool = False,
    ) -> np.ndarray:
        """Concatenate reservoir states + parent outputs (+ temporal lag)."""
        parts = [reservoir_states]

        # parent outputs
        for parent in self._specs[node_name].parents:
            if is_training and targets is not None and parent in targets:
                # during training, use ground truth for parent values
                # to avoid error propagation during fitting
                p = targets[parent]
            elif parent in predictions:
                p = predictions[parent]
            else:
                raise RuntimeError(
                    f"Parent '{parent}' of node '{node_name}' has no predictions. "
                    f"Ensure topological order is respected."
                )
            parts.append(p.reshape(-1, 1))

        # temporal: own previous output
        if self._temporal:
            if node_name in predictions:
                lagged = np.concatenate([[0.0], predictions[node_name][:-1]])
            elif is_training and targets is not None:
                lagged = np.concatenate([[0.0], targets[node_name][:-1]])
            else:
                lagged = np.zeros(reservoir_states.shape[0])
            parts.append(lagged.reshape(-1, 1))

        return np.column_stack(parts)

    def _validate_targets(self, targets: dict[str, np.ndarray]) -> None:
        missing = set(self._specs.keys()) - set(targets.keys())
        if missing:
            raise ValueError(
                f"Missing target data for nodes: {missing}. "
                f"All nodes need ground truth during training."
            )
