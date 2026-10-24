"""Lat/lon frame, Baltic chart, red/green paths, explanations and playbooks."""

import math

import pytest
from global_land_mask import globe

from marine_guard import ACTIONS, GuardConfig, State
from marine_guard.geometry import LocalFrame
from sim.analysis import first_danger, path_errors
from sim.bathymetry import parse_ascii_grid
from sim.baltic import baltic_chart
from sim.runner import run_scenario
from ui.explanations import CHECK_EXPLANATIONS, explain

GULF_OF_FINLAND = (59.75, 24.30)
HELSINKI_CENTRE = (60.1699, 24.9384)


@pytest.mark.parametrize("x, y", [(0, 0), (66_000, 4_300), (-25_000, 40_000), (12_345, -9_876)])
def test_local_frame_round_trip_within_1_m(x, y):
    frame = LocalFrame(59.75, 24.30)
    back_x, back_y = frame.to_xy(*frame.to_latlon(x, y))
    assert math.hypot(back_x - x, back_y - y) < 1.0


def test_local_frame_scale():
    frame = LocalFrame(60.0, 25.0)
    lat, lon = frame.to_latlon(0.0, 111_195.0)  # about one degree of latitude north
    assert lat == pytest.approx(61.0, abs=1e-3)
    lat, lon = frame.to_latlon(55_597.0, 0.0)  # one degree of longitude at 60 N is ~55.6 km
    assert lon == pytest.approx(26.0, abs=1e-3)


def test_results_and_rows_carry_lat_lon(run):
    for row in run("crude_spoof").rows[::50]:
        res = row.result
        assert res.lat_deg is not None and res.lon_deg is not None
        assert (res.lat_deg, res.lon_deg) == row.guard_latlon
        assert row.true_latlon[0] == pytest.approx(59.75, abs=0.1)
        assert (row.gnss_latlon is None) == (row.gnss_position is None)
        assert "lat_deg" in res.to_dict()


def test_land_mask_known_points():
    assert not globe.is_land(*GULF_OF_FINLAND)
    assert globe.is_land(*HELSINKI_CENTRE)
    cfg = GuardConfig()
    chart = baltic_chart(cfg.origin_lat_deg, cfg.origin_lon_deg)
    assert chart.is_water(0.0, 0.0)  # the voyage start, mid gulf
    assert chart.is_land_latlon(*HELSINKI_CENTRE)
    x, y = chart.frame.to_xy(*HELSINKI_CENTRE)
    assert not chart.is_water(x, y)
    assert chart.depth_at(0.0, 0.0) > 15.0
    assert chart.coast_y_at(0.0, 0.0) > 10_000.0  # Finnish coast lies well to the north


def test_ascii_grid_parser_turns_elevation_into_depth():
    text = ("ncols 2\nnrows 2\nxllcorner 24.0\nyllcorner 59.0\ncellsize 0.5\n"
            "NODATA_value -99999\n-10 5\n-40 -99999\n")
    grid = parse_ascii_grid(text, "test")
    assert grid.depth[0, 0] == 40.0  # bottom row of the file is the southern edge
    assert grid.depth[1, 0] == 10.0
    assert grid.depth[1, 1] == 0.0  # land
    assert grid.depth[0, 1] == 0.0  # no data


def test_red_and_green_paths_in_crude_spoof(run):
    errors = path_errors(run("crude_spoof"))
    assert errors.green_worst_m < 100.0
    assert errors.red_worst_m > 1000.0


def test_red_and_green_paths_in_smart_spoof(run):
    errors = path_errors(run("smart_spoof"))
    assert errors.green_worst_m < 100.0
    assert errors.red_worst_m > errors.green_worst_m


def test_baltic_voyage_crude_spoof_shows_grounding_risk():
    voyage = run_scenario("crude_spoof", voyage=True)
    assert len(voyage.rows) == 10_800
    errors = path_errors(voyage)
    assert errors.green_worst_m < 100.0
    assert errors.red_worst_m > 1000.0
    danger = first_danger(voyage)
    assert danger is not None and danger.what == "on land"
    end_lat, end_lon = voyage.rows[-1].true_latlon
    assert end_lon > 25.3  # about 66 km east of the start


def test_every_check_has_an_explanation(run):
    for check in run("jamming").rows[200].result.checks + run("normal").rows[100].result.checks:
        assert check.name in CHECK_EXPLANATIONS
        texts = explain(check)
        assert all(texts[k] for k in ("measured", "means", "if_fails"))
        assert "{" not in texts["measured"]


def test_actions_have_steps_for_every_state():
    for state in State:
        action = ACTIONS[state]
        assert action.steps, state
        assert action.why_it_matters, state
        assert action.rules, state
    for state in (State.JAMMING, State.SPOOFING):
        text = " ".join(ACTIONS[state].steps)
        for phrase in ("radar", "Head-Up", "VTS", "Traficom", "evidence", "AIS"):
            assert phrase in text, (state, phrase)
        assert any("Rule 5" in r for r in ACTIONS[state].rules)
        assert any("SOLAS" in r for r in ACTIONS[state].rules)
