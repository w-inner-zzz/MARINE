"""The diagnosis flow chart (docs/) must match the guard's real checks."""

import importlib.util
import pathlib

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"


def load_flowchart():
    spec = importlib.util.spec_from_file_location("flowchart", DOCS / "flowchart.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_flow_chart_covers_every_check_in_order():
    flowchart = load_flowchart()
    checks = flowchart.checks_in_code_order()
    assert len(checks) == 10
    assert set(flowchart.QUESTIONS) == {name for name, _ in checks}
    svg = flowchart.build()
    positions = [svg.index(f"{i}. {name}") for i, (name, _) in enumerate(checks, 1)]
    assert positions == sorted(positions)


def test_committed_flow_chart_is_up_to_date():
    """Regenerate with `python docs/flowchart.py` after changing checks or thresholds."""
    flowchart = load_flowchart()
    assert (DOCS / "diagnosis_flowchart.svg").read_text(encoding="utf-8") == flowchart.build()
