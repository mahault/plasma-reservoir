"""Seeded held steps shared with the firmware; no audio dependencies."""
import numpy as np

# Held-step input for IPC and replica runs. The UNO generates the same sequence on its own
# clock (firmware/ne2_uno), so the host only needs the seed to know u(k) exactly (D-28).
# xorshift32 with shifts (13, 17, 5): G. Marsaglia, "Xorshift RNGs", J. Stat. Softw. 8(14), 2003.


def xorshift32_levels(seed: int, n: int) -> np.ndarray:
    """n PWM-DAC levels (0..255): the top byte of successive xorshift32 states."""
    if not 0 < seed < 2**32:
        raise ValueError("seed must be in 1 .. 2**32 - 1")
    x = seed
    out = np.empty(n, dtype=np.uint8)
    for i in range(n):
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        out[i] = x >> 24
    return out


def levels_to_u(levels: np.ndarray) -> np.ndarray:
    """Map DAC levels 0..255 onto u in [-1, 1] (Dambre et al. 2012 use u ~ U[-1, 1])."""
    return (levels.astype(np.float64) - 127.5) / 127.5


def replica_levels(prefix_seed: int, n_prefix: int, common_seed: int, n_common: int) -> np.ndarray:
    """A replica: its own random prefix (different initial state), then the shared drive."""
    prefix = xorshift32_levels(prefix_seed, n_prefix) if n_prefix else np.empty(0, np.uint8)
    return np.concatenate([prefix, xorshift32_levels(common_seed, n_common)])
