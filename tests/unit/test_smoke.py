"""Smoke tests to verify the project scaffold is correctly set up."""

import sys

import pytest


@pytest.mark.unit
def test_import_pumpahead() -> None:
    """Verify that the pumpahead package is importable and exposes __version__."""
    import pumpahead

    assert hasattr(pumpahead, "__version__")
    assert pumpahead.__version__ == "0.1.0"


@pytest.mark.unit
def test_core_does_not_import_homeassistant() -> None:
    """Verify that importing pumpahead does not pull in homeassistant modules.

    Records sys.modules state before import so that mock HA modules injected by
    other test modules (e.g. test_ha_scaffold.py) do not cause false failures.
    """
    ha_before = {name for name in sys.modules if name.startswith("homeassistant")}

    import pumpahead  # noqa: F401

    ha_after = {name for name in sys.modules if name.startswith("homeassistant")}
    new_ha = sorted(ha_after - ha_before)
    assert new_ha == [], f"pumpahead import added homeassistant modules: {new_ha}"
