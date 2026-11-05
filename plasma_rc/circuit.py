"""One parameter file for the minimal circuit, shared by simulation and hardware (CIRC-01, CIRC-03).

Circuit: V_D = V_bias + G·x -> Z_o -> R_B -> node N2 (C_s, divider R_d) -> lamp -> R_S -> return.
Equations: docs/research/claude_minimal_circuit_improvement_2026-11-04.md §4.2–4.5 (Derived).
Every value carries a source tag; unknown values are refused, never defaulted.
"""
import json
import math
from pathlib import Path

SOURCES = {"measured", "datasheet", "assumed", "override", "unknown"}  # override: a deliberate variant


class Config:
    def __init__(self, raw):
        if isinstance(raw, (str, Path)):
            raw = json.loads(Path(raw).read_text())
        for section, params in raw.items():
            for name, p in params.items():
                if p.get("source") not in SOURCES:
                    raise ValueError(f"{section}.{name}: source must be one of {sorted(SOURCES)}")
                if (p["value"] is None) != (p["source"] == "unknown"):
                    raise ValueError(f"{section}.{name}: value is null exactly when source is unknown")
                if p["value"] is not None and not math.isfinite(p["value"]):
                    raise ValueError(f"{section}.{name}: value must be finite")
        self.raw = raw

    def get(self, section, name):
        p = self.raw.get(section, {}).get(name)
        if p is None or p["value"] is None:
            raise ValueError(f"{section}.{name} is unknown; measure it or tag an assumption")
        return float(p["value"])

    def with_values(self, **changes):
        """New Config with the named values replaced and tagged 'override'; unknown names raise."""
        raw = json.loads(json.dumps(self.raw))
        for name, value in changes.items():
            hits = [s for s in raw.values() if name in s]
            if len(hits) != 1:
                raise KeyError(f"{name}: not exactly one parameter of that name")
            hits[0][name] = {**hits[0][name], "value": value, "source": "override"}
        return Config(raw)

    def _c(self, name):
        return self.get("circuit", name)

    def _l(self, name):
        return self.get("lamp", name)

    def drive(self, x):
        """Commanded drive V_D [V] for normalized DAC output x in [0, 1]."""
        return self._c("V_bias") + self._c("G") * x

    def thevenin(self, v_d):
        """(V_th [V], R_th [Ω]) seen by lamp + R_S; R_B' = R_B + Z_o in parallel with R_d."""
        rb, rd = self._c("R_B") + self._c("Z_o"), self._c("R_d")
        return v_d * rd / (rb + rd), rb * rd / (rb + rd)

    def operating_current(self, v_d):
        """Lit steady current on the linear fit v_L = V_m + r_on·i_L."""
        v_th, r_th = self.thevenin(v_d)
        return (v_th - self._l("V_m")) / (r_th + self._c("R_S") + self._l("r_on"))

    def extinction_voltage(self):
        """Node (N2) voltage at the sustaining limit I_x: V_x = V_m + (r_on + R_S)·I_x."""
        return self._l("V_m") + (self._l("r_on") + self._c("R_S")) * self._l("I_x")

    def regime(self, v_d):
        """R0 dark, R1 flashing, R2 lit, or latch (bistable), from the load line (§4.3)."""
        if self.thevenin(v_d)[0] == self._l("V_b") or self.operating_current(v_d) == self._l("I_x"):
            return "boundary"
        strikes = self.thevenin(v_d)[0] > self._l("V_b")
        holds = self.operating_current(v_d) >= self._l("I_x")
        return {(False, False): "R0", (True, False): "R1", (True, True): "R2", (False, True): "latch"}[
            (strikes, holds)]

    def regimes_over_range(self, x_lo, x_hi, n=201):
        return {self.regime(self.drive(x_lo + (x_hi - x_lo) * i / (n - 1))) for i in range(n)}

    def safety(self):
        """Derived bounds (§4.5). Not ratings: compare with the chosen parts' datasheets.
        A bound whose inputs are still unknown is None (strike bounds need the E1 lamp measurements)."""
        def bound(f):
            try:
                return f()
            except ValueError:
                return None
        rb = lambda: self._c("R_B") + self._c("Z_o")  # noqa: E731
        return {
            "source_current_max_a": bound(lambda: self._c("V_D_max") / rb()),
            "continuous_bound_ok": bound(lambda: rb() + self._c("R_S") >= self._c("V_D_max") / self._l("I_design")),
            # Conditional bounds: passive positive-resistance model, initial node and drive <= V_D_max.
            # These are not measured pulse ratings; total pulse energy can include source energy.
            "strike_peak_current_a": bound(lambda: max(0.0, self._c("V_D_max") - self._l("V_m"))
                                           / (self._l("r_on") + self._c("R_S"))),
            "strike_energy_j": bound(lambda: self._c("C_s") * self._c("V_D_max")**2 / 2),
            "ballast_short_power_w": bound(lambda: self._c("V_D_max")**2 * self._c("R_B") / rb()**2),
        }
