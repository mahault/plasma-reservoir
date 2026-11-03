# Decisions and development history

| Decision | Status | Reason |
| --- | --- | --- |
| One neon bulb with a ballast and controlled voltage drive | Agreed | Study near-breakdown and continuously lit conditions. |
| Separate simulation and hardware pipelines; preserve master | Agreed | Independent, focused workflows unified on this branch. |
| Separately driven LED control | Agreed | Test ordinary optical transduction without a neon breakdown label. |
| Record synchronized light, bulb voltage and drive; preserve raw captures | Agreed | Features and timing can be checked against the input. |
| NARMA-10, individual and combined readouts, controls, held-out tests | Agreed | A score alone does not establish reservoir contribution. |
| Report correlations and truncated IPC with controls | Agreed | Compare features and nonlinear memory without test leakage. |
| Bulb, light and LED models are hypotheses | Agreed | Real device parameters remain unmeasured. |
| Physical Lyapunov estimation is not established | Agreed | Repeated trials include independent noise. |

Previous audio, Bayesian readout and Circuit A studies are historical and accessible in Git history and the original workspace archive. They are not results for this circuit.
