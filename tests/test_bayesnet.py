"""Tests for the Bayesian network readout."""
import numpy as np
import pytest

from plasma_rc.readout.bayesnet import BayesNetReadout, NodeSpec


@pytest.fixture
def simple_dag():
    """A -> C, B -> C (two roots, one leaf)."""
    return [
        NodeSpec("A", parents=[]),
        NodeSpec("B", parents=[]),
        NodeSpec("C", parents=["A", "B"], is_target=True),
    ]


@pytest.fixture
def synthetic_data():
    rng = np.random.RandomState(0)
    N, D = 200, 10
    states = rng.randn(N, D)
    w_a = rng.randn(D)
    w_b = rng.randn(D)
    a = states @ w_a
    b = states @ w_b
    c = 0.5 * a + 0.5 * b + rng.randn(N) * 0.1
    return states, {"A": a, "B": b, "C": c}


class TestDAGConstruction:
    def test_valid_dag(self, simple_dag):
        bn = BayesNetReadout(simple_dag)
        assert bn.order == ["A", "B", "C"] or bn.order == ["B", "A", "C"]

    def test_cycle_raises(self):
        nodes = [
            NodeSpec("X", parents=["Y"]),
            NodeSpec("Y", parents=["X"]),
        ]
        with pytest.raises(ValueError, match="cycle"):
            BayesNetReadout(nodes)

    def test_missing_parent_raises(self):
        nodes = [NodeSpec("A", parents=["Z"])]
        with pytest.raises(ValueError, match="not in the node specs"):
            BayesNetReadout(nodes)


class TestFitPredict:
    def test_fit_returns_log_ml(self, simple_dag, synthetic_data):
        states, targets = synthetic_data
        bn = BayesNetReadout(simple_dag)
        lml = bn.fit(states, targets)
        assert isinstance(lml, float)

    def test_predict_shapes(self, simple_dag, synthetic_data):
        states, targets = synthetic_data
        bn = BayesNetReadout(simple_dag)
        bn.fit(states, targets)
        result = bn.predict(states)
        for name in ["A", "B", "C"]:
            assert result[name].mean.shape == (states.shape[0],)
            assert result[name].std.shape == (states.shape[0],)

    def test_predict_before_fit_raises(self, simple_dag, synthetic_data):
        states, _ = synthetic_data
        bn = BayesNetReadout(simple_dag)
        with pytest.raises(RuntimeError):
            bn.predict(states)

    def test_missing_targets_raises(self, simple_dag, synthetic_data):
        states, targets = synthetic_data
        del targets["B"]
        bn = BayesNetReadout(simple_dag)
        with pytest.raises(ValueError, match="Missing target"):
            bn.fit(states, targets)

    def test_dag_beats_noise(self, simple_dag, synthetic_data):
        """DAG readout should achieve low NMSE on structured data."""
        states, targets = synthetic_data
        bn = BayesNetReadout(simple_dag)
        bn.fit(states[:150], {k: v[:150] for k, v in targets.items()})
        result = bn.predict(states[150:])
        y_true = targets["C"][150:]
        y_pred = result["C"].mean
        mse = np.mean((y_true - y_pred) ** 2)
        var = np.var(y_true)
        nmse = mse / var
        assert nmse < 0.1, f"NMSE too high: {nmse:.4f}"


class TestModelComparison:
    def test_returns_log_bf(self, simple_dag, synthetic_data):
        states, targets = synthetic_data
        bn = BayesNetReadout(simple_dag)
        bn.fit(states, targets)
        comp = bn.model_comparison(states, targets)
        assert "C" in comp
        assert isinstance(comp["C"], float)


class TestTemporal:
    def test_temporal_mode(self):
        nodes = [
            NodeSpec("X", parents=[]),
            NodeSpec("Y", parents=["X"], is_target=True),
        ]
        rng = np.random.RandomState(1)
        N, D = 100, 5
        states = rng.randn(N, D)
        x = states @ rng.randn(D)
        y = np.zeros(N)
        for t in range(1, N):
            y[t] = 0.5 * x[t] + 0.3 * y[t - 1] + rng.randn() * 0.05

        bn = BayesNetReadout(nodes, temporal=True)
        bn.fit(states, {"X": x, "Y": y})
        result = bn.predict(states)
        assert result["Y"].mean.shape == (N,)
