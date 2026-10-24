"""The static website's data: export_web.py must describe every second faithfully."""

import base64
import gzip
import json

import pytest

import export_web
from marine_guard import GuardConfig, State
from teaching.explanations import CHECK_EXPLANATIONS


def unpack(text):
    return json.loads(gzip.decompress(base64.b64decode(text)))


def test_packed_round_trip():
    data = {"a": [1, 2.5, None], "b": "Gulf of Finland"}
    assert unpack(export_web.packed(data)) == data


@pytest.mark.parametrize("key", ["crude_spoof", "lost"])
def test_scenario_payload_matches_the_run(run, key):
    r = run(key)
    payload = unpack(export_web.packed(export_web.scenario_payload(r)))
    n = len(r.rows)
    for column in ("state", "lat", "lon", "unc", "glat", "agc", "nsat", "sats", "checks", "reason"):
        assert len(payload[column]) == n, column
    for t in (0, 200, n - 1):
        row = r.rows[t]
        assert export_web.STATES[payload["state"][t]] == row.result.state.value
        assert payload["lat"][t] == pytest.approx(row.guard_latlon[0], abs=1e-6)
        assert len(payload["checks"][t]) == len(row.result.checks)
        assert payload["reason"][t] == row.result.reason
    assert payload["path_errors"]["red_worst_m"] > 0 or key == "lost"


def test_content_has_every_state_and_check(run):
    content = export_web.content_payload(GuardConfig(), run("normal"))
    assert set(content["actions"]) == {s.value for s in State}
    assert set(content["palette"]["states"]) == {s.value for s in State}
    assert [c["name"] for c in content["checks"]] == list(CHECK_EXPLANATIONS)
    assert content["derivations"] and content["simple"] and content["briefing"]
    assert all(b["svg"].startswith("<svg") for d in content["derivations"]
               for b in d["blocks"] if b["type"] == "diagram")
