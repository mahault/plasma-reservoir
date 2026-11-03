"""Causal feature extraction and benchmark analysis."""

import numpy as np
from sklearn.linear_model import Ridge

from plasma_rc.neon.narma import narma10_target
from plasma_rc.neon.metrics import nmse


def narma_predict(states, u, train, test, alpha):
    """Return test target and next-step predictions with training-only normalization."""
    states, u = np.asarray(states), np.asarray(u)
    if states.ndim != 2 or len(states) != len(u) or not (0 <= train[0] < train[1] <= test[0] < test[1] < len(u)):
        raise ValueError("incompatible state, input, or chronological splits")
    target = narma10_target(u)[1:]
    states = states[:-1]
    tr, te = slice(*train), slice(*test)
    mean, scale = states[tr].mean(axis=0), states[tr].std(axis=0)
    scale = np.where(scale == 0, 1, scale)
    model = Ridge(alpha=alpha).fit((states[tr] - mean) / scale, target[tr])
    return target[te], model.predict((states[te] - mean) / scale)


def strike_delay(trace, start_s, end_s, threshold_a=1e-6):
    """First off-to-on current event after the pulse, or None if none occurs."""
    if not (np.isfinite(start_s) and np.isfinite(end_s) and start_s < end_s and
            np.isfinite(threshold_a) and threshold_a > 0):
        raise ValueError("invalid pulse interval or threshold")
    on = trace.current_a > threshold_a
    events = trace.time_s[1:][on[1:] & ~on[:-1]]
    eligible = events[(events > start_s) & (events <= end_s)]
    return float(eligible[0] - start_s) if len(eligible) else None


def feature_correlations(features):
    """Pearson correlations; constant channels are undefined rather than zero."""
    x = np.asarray(features, dtype=float)
    if x.ndim != 2 or len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("features must be a finite matrix with at least two rows")
    centered = x - x.mean(axis=0)
    scale = np.linalg.norm(centered, axis=0)
    out = [[None] * x.shape[1] for _ in range(x.shape[1])]
    for i in range(x.shape[1]):
        for j in range(x.shape[1]):
            if scale[i] > 0 and scale[j] > 0:
                out[i][j] = float(centered[:, i] @ centered[:, j] / (scale[i] * scale[j]))
    return out


def optical_features(trace, edges_s, samples=16, threshold_a=1e-6):
    """Current-based brightness, ignition-event rate and brightness variation per step.

    Brightness assumes light is proportional to positive current. Frequency is
    the count of off-to-on threshold crossings divided by the step duration;
    variation is the standard deviation of brightness samples, not a spectrum.
    """
    if not np.isfinite(threshold_a) or threshold_a <= 0:
        raise ValueError("event threshold must be finite and positive")
    edges = np.asarray(edges_s, dtype=float)
    values = step_samples(trace, edges, samples)
    brightness = np.maximum(values[:, samples:], 0.0)
    on = trace.current_a > threshold_a
    event_times = trace.time_s[1:][on[1:] & ~on[:-1]]
    event_times = event_times[(event_times >= edges[0]) & (event_times < edges[-1])]
    counts = np.histogram(event_times, bins=edges)[0]
    return np.column_stack((brightness.mean(axis=1), counts / np.diff(edges), brightness.std(axis=1)))


def characterize_ipc(states, u, train, test, max_delay, seed, n_shuffles=20):
    """Truncated degree-2 held-out capacity with a conservative shuffled maximum cutoff."""
    if n_shuffles < 1:
        raise ValueError("at least one shuffled null is required")
    actual = delayed_capacities(states, u, train, test, max_delay)
    rng = np.random.default_rng(seed)
    thresholds = {"degree_1": 0.0, "degree_2": 0.0}
    for _ in range(n_shuffles):
        null = delayed_capacities(states, rng.permutation(u), train, test, max_delay)
        thresholds["degree_1"] = max(thresholds["degree_1"], *null["degree_1"])
        quadratic = list(null["degree_2"]) + list(null["degree_2_cross"].values())
        thresholds["degree_2"] = max(thresholds["degree_2"], *quadratic)
    linear = sum(x for x in actual["degree_1"] if x > thresholds["degree_1"])
    quadratic = list(actual["degree_2"]) + list(actual["degree_2_cross"].values())
    nonlinear = sum(x for x in quadratic if x > thresholds["degree_2"])
    return {"linear_capacity": float(linear), "nonlinear_degree_2": float(nonlinear),
            "truncated_total": float(linear + nonlinear), "null_max": thresholds,
            "n_shuffles": n_shuffles, "null_seed": seed, "targets": actual}


def conditional_contraction(a, b, start_s, end_s):
    """Finite-time voltage divergence slope for an identical-drive, continuously lit segment.

    This is not a general hybrid or stochastic Lyapunov estimator.
    """
    if not (max(a.time_s[0], b.time_s[0]) <= start_s < end_s <= min(a.time_s[-1], b.time_s[-1])):
        raise ValueError("interval lies outside traces")
    times = np.linspace(start_s, end_s, 200)
    if not np.allclose(np.interp(times, a.time_s, a.drive_v), np.interp(times, b.time_s, b.drive_v), rtol=0, atol=1e-9):
        raise ValueError("drives differ during the measurement interval")
    if np.any(np.interp(times, a.time_s, a.current_a) <= 1e-6) or np.any(np.interp(times, b.time_s, b.current_a) <= 1e-6):
        raise ValueError("both traces must remain conducting")
    distance = np.abs(np.interp(times, a.time_s, a.voltage_v) - np.interp(times, b.time_s, b.voltage_v))
    if np.any(distance <= 1e-10):
        raise ValueError("perturbation is below the numerical floor")
    return float(np.polyfit(times - start_s, np.log(distance), 1)[0])


def delayed_capacities(states, u, train, test, max_delay):
    """Held-out scores for individual linear and quadratic Legendre delay targets.

    The input must be i.i.d. uniform on [0, 0.5]; includes degree-2 cross-delay products.
    Negative values are retained rather than silently inflating the sum.
    """
    u, states = np.asarray(u), np.asarray(states)
    if (states.ndim != 2 or len(states) != len(u) or max_delay < 1 or
            not (max_delay - 1 <= train[0] < train[1] <= test[0] < test[1] <= len(u))):
        raise ValueError("invalid states or splits")
    if np.any((u < 0) | (u > 0.5)):
        raise ValueError("input must be in [0, 0.5]")
    tr, te = slice(*train), slice(*test)
    mean, scale = states[tr].mean(axis=0), states[tr].std(axis=0)
    scale = np.where(scale == 0, 1, scale)
    z = (states - mean) / scale
    delays = input_delays(4 * u - 1, max_delay)
    targets = {"degree_1": delays, "degree_2": (3 * delays**2 - 1) / 2}
    result = {}
    for name, target in targets.items():
        scores = []
        for col in target.T:
            model = Ridge(alpha=0.01).fit(z[tr], col[tr])
            scores.append(1 - nmse(col[te], model.predict(z[te])))
        result[name] = scores
    result["degree_2_cross"] = {}
    for i in range(max_delay):
        for j in range(i + 1, max_delay):
            col = delays[:, i] * delays[:, j]
            model = Ridge(alpha=0.01).fit(z[tr], col[tr])
            result["degree_2_cross"][f"{i},{j}"] = 1 - nmse(col[te], model.predict(z[te]))
    return result


def input_delays(u, taps):
    u = np.asarray(u, dtype=float)
    if u.ndim != 1 or taps < 1 or taps > len(u):
        raise ValueError("invalid input or tap count")
    return np.column_stack([np.concatenate((np.zeros(delay), u[:len(u) - delay])) for delay in range(taps)])


def held_drive(u, bias_v, gain_v, step_s, start_s, rise_s):
    """Create finite-edge held levels after a bias-only warm-up ramp."""
    u = np.asarray(u, dtype=float)
    if u.ndim != 1 or not len(u) or not np.all(np.isfinite(u)):
        raise ValueError("input must be a finite nonempty vector")
    if not 0 < rise_s < step_s or not start_s > rise_s:
        raise ValueError("invalid input or warm-up timing")
    edges = start_s + np.arange(len(u) + 1) * step_s
    points = [(0.0, 0.0), (rise_s, bias_v), (start_s, bias_v)]
    previous = bias_v
    for edge, value in zip(edges[:-1], bias_v + gain_v * u):
        if edge != start_s:
            points.append((float(edge), float(previous)))
        points.append((float(edge + rise_s), float(value)))
        previous = value
    points.append((float(edges[-1]), float(previous)))
    return points, edges


def step_samples(trace, edges_s, windows):
    """Sample voltage and current at subwindow midpoints, ordered by channel."""
    edges = np.asarray(edges_s, dtype=float)
    if windows < 1 or len(edges) < 2 or np.any(np.diff(edges) <= 0):
        raise ValueError("step edges must increase and windows must be positive")
    tolerance = 16 * np.finfo(float).eps * max(1.0, abs(trace.time_s[-1]))
    if edges[0] < trace.time_s[0] - tolerance or edges[-1] > trace.time_s[-1] + tolerance:
        raise ValueError("step edges extend outside trace")
    times = edges[:-1, None] + np.diff(edges)[:, None] * ((np.arange(windows) + 0.5) / windows)
    right = np.searchsorted(trace.time_s, times, side="left")
    right = np.clip(right, 0, len(trace.time_s) - 1)
    exact = np.abs(trace.time_s[right] - times) <= tolerance
    left = np.where(exact, right, np.maximum(right - 1, 0))
    if np.any(trace.time_s[left] < edges[:-1, None] - tolerance) or np.any(
        trace.time_s[right] > edges[1:, None] + tolerance
    ):
        raise ValueError("sample interpolation bracket crosses a step boundary")
    voltage = np.interp(times, trace.time_s, trace.voltage_v)
    current = np.interp(times, trace.time_s, trace.current_a)
    return np.column_stack((voltage, current))


def narma_score(states, u, train, test, alpha):
    """Train on x[k] to predict y[k+1]; normalize features using training only."""
    target, prediction = narma_predict(states, u, train, test, alpha)
    return nmse(target, prediction)
