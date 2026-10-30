"""The preserved CSV loader contract, without unpublished recording fixtures."""
import numpy as np
import pytest
from plasma_rc.reservoir.physical import PlasmaDataLoader, LivePlasmaReservoir


def test_loader_preserves_raw_observables(tmp_path):
    (tmp_path/'trial.csv').write_text('Timestamp_Seconds,Brightness,Frequency_Hz,Settle_Micros\n0,10,20,30\n1,11,21,31\n')
    loader = PlasmaDataLoader(tmp_path)
    assert loader.list_trials()[0]['name'] == 'trial'
    t,x = loader.load_trial('trial.csv')
    np.testing.assert_array_equal(t,[0,1])
    np.testing.assert_array_equal(x,[[10,20,30],[11,21,31]])


def test_live_stub_does_not_claim_hardware_support():
    with pytest.raises(NotImplementedError):
        LivePlasmaReservoir().step(0.)
