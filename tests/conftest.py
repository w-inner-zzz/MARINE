from functools import lru_cache

import pytest

from sim.runner import run_scenario


@lru_cache(maxsize=None)
def _run(key):
    return run_scenario(key)


@pytest.fixture
def run():
    """run(key) -> simulated Run, computed once per test session."""
    return _run
