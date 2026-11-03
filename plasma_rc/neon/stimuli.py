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
