"""State readout shared by simulation and hardware (READ-01, READ-02).

One definition of "the state of a step": the mean of each recorded signal in M equal sub-windows of the step
(a linear operation of the readout, disclosed). Adapters: `sim_states` (a simulate() Trace) and
`plasma_rc.hw.recording.segment_states` (ADC captures). Point samples are not used: they alias the µs
relaxation cycle (docs/study_2026-11-04.md §1.4).
READ-02 strike timing is a separate feature set: first-strike latency per step, right-censored at the step
length, with a struck flag.
"""
import numpy as np

FINE = 16   # simulation samples averaged per sub-window (resolution checked in tests/test_states.py)


def window_means(t, y, edges, m):
    """(n_segments, m) means of samples y taken at times t, per sub-window of every segment
    [edges[i], edges[i+1]); NaN where a sub-window holds no sample."""
    t, y, edges = np.asarray(t, float), np.asarray(y, float), np.asarray(edges, float)
    n = len(edges) - 1
    seg = np.searchsorted(edges, t, side="right") - 1
    ok = (seg >= 0) & (seg < n)
    seg, t, y = seg[ok], t[ok], y[ok]
    sub = np.minimum(np.floor((t - edges[seg]) * m / (edges[seg + 1] - edges[seg])).astype(int), m - 1)
    idx = seg * m + sub
    total = np.bincount(idx, weights=y, minlength=n * m)
    count = np.bincount(idx, minlength=n * m)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (total / count).reshape(n, m)


def sim_states(trace, m):
    """Simulation adapter: [v sub-windows, v_S sub-windows] per step from a run sampled at m·FINE points/step."""
    t = trace.t.ravel()
    return np.column_stack([window_means(t, trace.v.ravel(), trace.edges, m),
                            window_means(t, trace.v_s.ravel(), trace.edges, m)])


def strike_latency(flash_times, edges):
    """(n_steps, 2): [first-strike latency after step onset, struck flag]; no strike -> step length, flag 0."""
    edges, flashes = np.asarray(edges, float), np.sort(np.asarray(flash_times, float))
    width = np.diff(edges)
    first = np.searchsorted(flashes, edges[:-1], side="left")
    t_first = np.where(first < len(flashes), flashes[np.minimum(first, len(flashes) - 1)] if len(flashes)
                       else np.inf, np.inf)
    struck = t_first < edges[1:]
    return np.column_stack([np.where(struck, t_first - edges[:-1], width), struck.astype(float)])
