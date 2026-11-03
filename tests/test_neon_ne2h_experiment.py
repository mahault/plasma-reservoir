import json
import os
import shutil
from pathlib import Path

import pytest

from plasma_rc.neon.ne2h_study import candidate_grid, run_ne2h_study
from plasma_rc.neon.ne2h_report import FIGURE_DESCRIPTIONS


def test_candidate_grid_is_explicit_and_ne2h_limit_is_not_a_nominal_value():
    candidates = candidate_grid()
    assert len(candidates) == 32
    assert {item["strike_v"] for item in candidates} == {120.0, 135.0}
    assert all(item["parameter_status"] == "exploratory assumption" for item in candidates)


def test_small_study_saves_report_metrics_and_figures(tmp_path):
    if not shutil.which("ngspice"):
        pytest.skip("ngspice required")
    output = tmp_path / "study"
    result = run_ne2h_study(
        output,
        seeds=(3,),
        n_steps=80,
        candidates=candidate_grid()[:1],
        max_step_s=20e-6,
        n_shuffles=2,
    )
    assert result["selection"]["criterion"] == "mean validation NARMA-10 NMSE"
    assert result["selection"]["test_used_for_selection"] is False
    stability = result["diagnostics"]["conditional_lyapunov"]
    assert stability["status"].startswith("estimated")
    assert stability["interpretation"].startswith("not a physical")
    assert stability["relative_difference"] < 0.05
    assert (output / "report.md").is_file()
    source_review = Path(
        os.path.relpath(
            Path("docs/research/ne2h_model_parameters.md").resolve(), output.resolve()
        )
    ).as_posix()
    report = (output / "report.md").read_text()
    for filename, description in FIGURE_DESCRIPTIONS.items():
        assert f"(figures/{filename})" in report
        assert description in report
    assert f"[the source review]({source_review})" in report
    assert (output / source_review).resolve() == Path(
        "docs/research/ne2h_model_parameters.md"
    ).resolve()
    assert (output / "best" / "seed-3" / "trace.txt").is_file()
    assert (output / "figures" / "narma_prediction.png").is_file()
    assert (output / "figures" / "ipc.png").is_file()
    saved = json.loads((output / "summary.json").read_text())
    assert saved["best"]["parameters"]["strike_v"] == 120
