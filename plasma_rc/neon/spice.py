"""ngspice simulation of the minimal single-bulb circuit."""

import json
import math
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Trace:
    time_s: np.ndarray
    drive_v: np.ndarray
    voltage_v: np.ndarray
    current_a: np.ndarray


@dataclass(frozen=True)
class LED:
    saturation_current_a: float
    ideality: float
    max_drive_v: float

    def __post_init__(self):
        if not all(math.isfinite(x) and x > 0 for x in (self.saturation_current_a, self.ideality, self.max_drive_v)):
            raise ValueError("LED model parameters must be finite and positive")


@dataclass(frozen=True)
class NeonSwitch:
    strike_v: float
    extinction_v: float
    intercept_v: float
    on_resistance_ohm: float

    def __post_init__(self):
        if not all(math.isfinite(x) for x in (self.strike_v, self.extinction_v,
                                               self.intercept_v, self.on_resistance_ohm)):
            raise ValueError("lamp parameters must be finite")
        if not (self.strike_v > self.extinction_v > self.intercept_v >= 0 and self.on_resistance_ohm > 0):
            raise ValueError("invalid switch thresholds or on-branch parameters")


def run_transient(config, drive, duration_s, max_step_s, output_dir, *, bulb, control_resistance_ohm=None):
    """Run an illustrative switch model or a control, saving the netlist and raw trace."""
    points = [(float(t), float(v)) for t, v in drive]
    if len(points) < 2 or points[0][0] != 0 or any(
        not math.isfinite(t) or not math.isfinite(v) for t, v in points
    ) or any(b[0] <= a[0] for a, b in zip(points, points[1:])):
        raise ValueError("drive must contain finite, strictly increasing points starting at zero")
    if not math.isfinite(duration_s) or not math.isfinite(max_step_s) or duration_s <= 0 or max_step_s <= 0:
        raise ValueError("duration and maximum timestep must be finite and positive")
    if not isinstance(bulb, (NeonSwitch, LED)) and bulb not in {"open", "resistor"}:
        raise ValueError("unsupported bulb model")
    if isinstance(bulb, LED) and any(v < 0 or v > bulb.max_drive_v for _, v in points):
        raise ValueError("LED drive must remain within the explicitly configured voltage range")
    if bulb == "resistor" and (control_resistance_ohm is None or
                               not math.isfinite(control_resistance_ohm) or control_resistance_ohm <= 0):
        raise ValueError("resistor control requires a positive resistance")
    work = Path(output_dir).resolve()
    work.mkdir(parents=True, exist_ok=False)
    pwl = " ".join(f"{t:.17g} {v:.17g}" for t, v in points)
    if isinstance(bulb, NeonSwitch):
        vt = (bulb.strike_v + bulb.extinction_v) / 2
        vh = (bulb.strike_v - bulb.extinction_v) / 2
        load = (f"Sbulb load internal node 0 neon\n"
                f".model neon sw vt={vt:.17g} vh={vh:.17g} ron={bulb.on_resistance_ohm:.17g} roff=1e18\n"
                f"Vmaint internal 0 {bulb.intercept_v:.17g}")
        bulb_meta = {"model": "instantaneous_hysteretic_switch", **asdict(bulb)}
    elif isinstance(bulb, LED):
        load = (f"Dled load 0 ledmodel\n.model ledmodel D(is={bulb.saturation_current_a:.17g} "
                f"n={bulb.ideality:.17g})")
        bulb_meta = {"model": "diode_hypothesis", **asdict(bulb)}
    else:
        resistance = 1e18 if bulb == "open" else control_resistance_ohm
        load = f"Rload load 0 {resistance:.17g}"
        bulb_meta = bulb
    netlist = f'''* Minimal reservoir circuit
Vdrive source 0 PWL({pwl})
Rballast source node {config.ballast_ohm:.17g}
Cparasitic node 0 {config.parasitic_capacitance_f:.17g}
Vsense node load 0
{load}
.control
set wr_singlescale
set numdgt=15
tran {max_step_s:.17g} {duration_s:.17g} 0 {max_step_s:.17g}
wrdata trace.txt v(source) v(node) i(Vsense)
quit
.endc
.end
'''
    (work / "circuit.cir").write_text(netlist)
    (work / "config.json").write_text(json.dumps({"circuit": asdict(config), "drive": points,
        "duration_s": duration_s, "max_step_s": max_step_s, "bulb": bulb_meta,
        "control_resistance_ohm": control_resistance_ohm}, indent=2))
    result = subprocess.run(["ngspice", "-b", "circuit.cir"], cwd=work, capture_output=True, text=True)
    (work / "ngspice.log").write_text(result.stdout + result.stderr)
    result.check_returncode()
    values = np.loadtxt(work / "trace.txt", ndmin=2)
    return Trace(*values.T)
