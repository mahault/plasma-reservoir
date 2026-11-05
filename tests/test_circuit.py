"""Load-line algebra against hand-derived values (research doc §4.2–4.5).

Round illustrative numbers chosen for hand calculation, not NE-2H values:
R_B' = R_B + Z_o = 100 kΩ, R_d = 100 kΩ  ->  V_th = V_D/2, R_th = 50 kΩ;
R_th + R_S + r_on = 55 kΩ.
"""
import copy

import pytest

from plasma_rc.circuit import Config

RAW = {
    "circuit": {
        "R_B": {"value": 90e3, "unit": "ohm", "source": "assumed"},
        "Z_o": {"value": 10e3, "unit": "ohm", "source": "assumed"},
        "R_d": {"value": 100e3, "unit": "ohm", "source": "assumed"},
        "R_S": {"value": 1e3, "unit": "ohm", "source": "assumed"},
        "C_s": {"value": 10e-12, "unit": "F", "source": "assumed"},
        "V_bias": {"value": 100.0, "unit": "V", "source": "assumed"},
        "G": {"value": 100.0, "unit": "V", "source": "assumed"},
        "V_D_max": {"value": 200.0, "unit": "V", "source": "assumed"},
    },
    "lamp": {
        "V_b": {"value": 80.0, "unit": "V", "source": "assumed"},
        "V_m": {"value": 50.0, "unit": "V", "source": "assumed"},
        "r_on": {"value": 4e3, "unit": "ohm", "source": "assumed"},
        "I_x": {"value": 0.5e-3, "unit": "A", "source": "assumed"},
        "I_design": {"value": 1.9e-3, "unit": "A", "source": "datasheet"},
    },
}


def cfg(**lamp):
    raw = copy.deepcopy(RAW)
    for k, v in lamp.items():
        raw["lamp"][k]["value"] = v
    return Config(raw)


def test_thevenin_includes_driver_impedance_and_divider():
    v_th, r_th = cfg().thevenin(160.0)
    assert v_th == pytest.approx(80.0)
    assert r_th == pytest.approx(50e3)


def test_operating_current_and_extinction_voltage():
    c = cfg()
    assert c.operating_current(200.0) == pytest.approx(50 / 55e3)   # (100 - 50) V / 55 kΩ
    assert c.extinction_voltage() == pytest.approx(50 + 5e3 * 0.5e-3)  # node: V_m + (r_on + R_S)·I_x


def test_regimes():
    assert cfg().regime(120.0) == "R0"            # V_th 60 < 80; i_op 0.18 mA < 0.5 mA
    assert cfg(I_x=0.7e-3).regime(170.0) == "R1"  # V_th 85 >= 80; i_op 0.636 mA < 0.7 mA
    assert cfg().regime(200.0) == "R2"            # V_th 100 >= 80; i_op 0.909 mA >= 0.5 mA
    assert cfg().regime(150.0) == "R0"            # V_th 75 < 80; i_op 0.455 mA < 0.5 mA
    assert cfg(I_x=0.3e-3).regime(150.0) == "latch"  # V_th 75 < 80 but 0.455 mA >= 0.3 mA


def test_drive_mapping_and_range():
    c = cfg()
    assert c.drive(0.0) == 100.0 and c.drive(1.0) == 200.0
    assert c.regimes_over_range(0.9, 1.0) == {"R2"}
    # Latch band: holds when V_D/2 - 50 >= 0.5 mA·55 kΩ (V_D >= 155 V) yet cannot strike (V_D < 160 V)
    assert c.regimes_over_range(0.0, 1.0) == {"R0", "latch", "R2", "boundary"}
    assert c.regimes_over_range(0.55, 0.59) == {"latch", "boundary"}


def test_safety_bounds():
    s = cfg().safety()
    assert s["source_current_max_a"] == pytest.approx(200 / 100e3)
    assert s["continuous_bound_ok"] is False      # 101 kΩ < 200 V / 1.9 mA = 105.3 kΩ
    assert s["strike_peak_current_a"] == pytest.approx((200 - 50) / 5e3)
    assert s["strike_energy_j"] == pytest.approx(10e-12 * 200**2 / 2)
    assert s["ballast_short_power_w"] == pytest.approx(200**2 * 90e3 / 100e3**2)


def test_unknown_values_refuse_to_compute():
    raw = copy.deepcopy(RAW)
    raw["lamp"]["V_b"] = {"value": None, "unit": "V", "source": "unknown"}
    with pytest.raises(ValueError, match="V_b"):
        Config(raw).regime(150.0)
    s = Config(raw).safety()   # before E1: source bounds known, strike bounds not
    assert s["strike_peak_current_a"] == pytest.approx(150 / 5e3)
    assert s["continuous_bound_ok"] is False
    assert s["source_current_max_a"] == pytest.approx(200 / 100e3)


def test_rejects_untagged_or_inconsistent_values():
    raw = copy.deepcopy(RAW)
    raw["lamp"]["V_b"]["source"] = "guess"
    with pytest.raises(ValueError, match="source"):
        Config(raw)
    raw["lamp"]["V_b"] = {"value": None, "unit": "V", "source": "assumed"}
    with pytest.raises(ValueError, match="unknown"):
        Config(raw)


def test_exact_breakdown_equilibrium_is_boundary():
    assert cfg().regime(160.0) == "boundary"


def test_with_values_makes_a_tagged_variant():
    c = Config(copy.deepcopy(RAW))
    v = c.with_values(C_s=1e-9, V_b=90.0)
    assert v.get("circuit", "C_s") == 1e-9 and v.raw["lamp"]["V_b"]["source"] == "override"
    assert c.get("circuit", "C_s") == 10e-12              # original untouched
    with pytest.raises(KeyError):
        c.with_values(nonexistent=1.0)
