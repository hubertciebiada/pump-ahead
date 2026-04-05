"""Smoke test for the simulation test suite.

This file ensures that ``pytest tests/simulation/ -m simulation`` collects at
least one test and returns exit code 0 instead of exit code 5 (no tests
collected).  It will be replaced by real scenario tests as later milestones
land.
"""

import pytest


@pytest.mark.simulation
def test_simulation_placeholder() -> None:
    """Placeholder: simulation test infrastructure is wired correctly."""
    assert True
