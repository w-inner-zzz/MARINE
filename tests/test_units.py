"""Unit tests of the building blocks."""

import math

from marine_guard import (GnssEpoch, GnssGuard, GuardConfig, SatInfo,
                          ShipSensors, State)
from marine_guard.backup import DepthSample, fuse, match_depth_profile
from marine_guard.geometry import hdop, invert_4x4
from sim.chart import SyntheticChart


def test_invert_4x4_matches_identity():
    m = [[4, 1, 0, 2], [1, 3, 1, 0], [0, 1, 5, 1], [2, 0, 1, 6]]
    inv = invert_4x4(m)
    for i in range(4):
        for j in range(4):
            value = sum(m[i][k] * inv[k][j] for k in range(4))
            assert math.isclose(value, 1.0 if i == j else 0.0, abs_tol=1e-9)


def test_invert_4x4_singular_returns_none():
    assert invert_4x4([[1, 2, 3, 4]] * 4) is None


def _sat(i, az, el):
    return SatInfo(i, az, el, 45.0, True)


def test_hdop_good_and_poor_geometry():
    spread = [_sat(i, az, el) for i, (az, el) in
              enumerate([(0, 30), (90, 30), (180, 30), (270, 30), (0, 85), (45, 60)])]
    assert hdop(spread) < 2.0
    bunched = [_sat(i, 100 + i, 20 + 10 * i) for i in range(6)]
    poor = hdop(bunched)
    assert poor is None or poor > 5.0
    assert hdop(spread[:3]) is None


def test_fuse_equal_weights():
    est, sigma = fuse(0.0, 10.0, 10.0, 10.0)
    assert math.isclose(est, 5.0)
    assert math.isclose(sigma, 10.0 / math.sqrt(2))


def test_depth_profile_finds_known_offset():
    chart, cfg = SyntheticChart(), GuardConfig()
    true_offset = 40.0  # the dead-reckoning track sits 40 m west of the truth
    samples = [DepthSample(500 + 6 * k, 0.0, chart.depth_at(500 + 6 * k + true_offset, 0.0))
               for k in range(cfg.depth_window_s)]
    assert match_depth_profile(samples, chart, sigma_x=30.0, cfg=cfg) == true_offset


def _healthy_epoch(t, position):
    sats = tuple(SatInfo(i, 36.0 * i, 15 + 7 * i, 38 + 1.3 * i, True) for i in range(10))
    return GnssEpoch(t, sats, 20.0, position, 0.01)


def test_guard_trusts_healthy_signal_and_flags_jamming():
    guard = GnssGuard(chart=SyntheticChart())
    sensors = ShipSensors(90.0, 5.0, None, None)
    for t in range(5):
        result = guard.update(_healthy_epoch(t, (5.0 * t, 0.0)), sensors)
        assert result.state == State.TRUSTED
    jammed = GnssEpoch(5, (), 40.0, None, None)
    result = guard.update(jammed, sensors)
    assert result.state == State.JAMMING
    assert result.action.autopilot_mode.startswith("Heading hold")
    assert result.to_dict()["state"] == "JAMMING"
    assert "40.0 dB" in result.reason
