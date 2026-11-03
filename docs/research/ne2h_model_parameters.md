# NE-2H (C2A) parameters for simulation

Date: 2026-11-03. Scope: device-specific values in the CML-IT C2A datasheet and their applicability to the repository's electrical switch model. This is a product datasheet review, not peer-reviewed evidence or a measurement of our bulb.

## What the datasheet establishes

The CML-IT *Neon Indicator Lamps* datasheet identifies C2A as NE-2H, a wire-terminal, high-brightness lamp (p. 2, high-brightness table). Values below apply only if the physical bulb is this CML-IT variant.

| Quantity | Datasheet value | Conditions and meaning |
|---|---:|---|
| Design current | 1.9 mA | C2A row; a product design rating, not a measured holding current or current-voltage curve. |
| Maximum initial breakdown | 95 VAC; 135 VDC | C2A row, footnote 2: maximum initial breakdown voltage in light. These are maxima, not typical values, distributions, or a prescribed switch threshold. |
| Minimum DC circuit voltage for high-brightness lamps | 150 V | Footnote 2; this is circuit voltage, not lamp voltage, strike voltage, or maintaining voltage. |
| Suggested series resistor in the high-brightness table | 30 kΩ, 1/4 W at 100–125 V circuit range; 100 kΩ, 1/3 W at 220–250 V circuit range | p. 3. These recommendations are circuit-specific and are not values for every driver or experimental topology. |

The datasheet includes other footnotes for other lamp rows, including a 1.5 mA minimum-stable-current statement and a 100 VAC maximum-breakdown-in-total-darkness statement. Do not transfer those values to C2A: the C2A entry's cited maximum initial breakdown is explicitly **in light**. Do not combine unrelated rows or footnotes.

**Cited:** CML Innovative Technologies (CML-IT), *Neon Indicator Lamps*, pp. 2–3, C2A / NE-2H high-brightness rows and footnotes. [Manufacturer datasheet (PDF hosted by RS Components)](https://assets.rs-online.com/v1698855769/Datasheets/33c338a3395bf8a48766cf8b62fb2d18.pdf). Values were checked in the source PDF, including the C2A row and footnote associations.

## Model parameters that remain unknown

The datasheet does not give a typical strike voltage, strike-voltage distribution, extinction or holding voltage/current, maintaining voltage, conducting-branch I–V slope, ignition delay, internal discharge dynamics, or quantitative optical transfer function. It also does not specify bulb/wiring/probe capacitance for our setup. These cannot be inferred from the maximum initial breakdown and design current.

| Simulation quantity | Evidence-based status | What is needed |
|---|---|---|
| `strike_v` | Unknown for an individual bulb; 135 VDC is only the catalog maximum initial breakdown in light. | Repeated ignition measurements under recorded illumination and drive conditions. |
| `extinction_v`, `intercept_v`, `on_resistance_ohm` | Unknown; neither a maintaining point nor the conducting I–V branch is supplied. | Measured lamp voltage and current over the relevant conducting range, including extinction/re-ignition cycles. |
| `parasitic_capacitance_f` | Unknown for the assembled circuit; not a C2A device rating. | Measure or bound lamp, wiring, probe and fixture loading separately where feasible. |
| Ignition/recovery dynamics and optical response | Not represented by the present instantaneous switch; no C2A-specific dynamic or optical transfer parameters are specified here. | Time-resolved, calibrated voltage/current/light measurements and an appropriate dynamic model. |

**Derived:** the C2A datasheet constrains a product's maximum initial striking condition and provides a design-current rating; it does not determine the parameters of a hysteretic switch or a continuous-discharge model. In particular, assigning 135 V as a nominal strike threshold or 1.9 mA as an extinction/holding current would change the meaning of the published values.

## Calibration implication

The repository's grid fitter ranks explicit candidate values for the switch thresholds, conducting-branch parameters and parasitic capacitance against a synchronized measured electrical trace; it does not invent default NE-2H ranges. Supply measured `time_s`, `drive_v`, and `voltage_v`, plus independently measured and synchronized `current_a` if available. A current inferred from the ballast voltage drop must account for capacitive current. Reserve a separate trace for validation. See [the calibration instructions](../../plasma_rc/neon/README.md).

**Important limit:** the sweep can select a candidate that best fits the supplied trace under the current model and score. It cannot establish physical accuracy without measured reference traces, and it cannot recover behavior omitted from the instantaneous switch model, such as stochastic ignition delay, internal glow dynamics or optical transfer. A low fitting error is calibration evidence for that trace/model/metric, not proof of a faithful plasma simulation. No physical C2A/NE-2H calibration trace was supplied for this task; the searched CSV/NPZ inputs were archived stimulus files and test fixtures.
