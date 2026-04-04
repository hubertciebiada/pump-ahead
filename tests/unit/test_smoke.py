"""Smoke tests to verify the project scaffold is correctly set up."""

import sys

import pytest


@pytest.mark.unit
def test_import_pumpahead() -> None:
    """Verify that the pumpahead package is importable and exposes __version__."""
    import pumpahead

    assert hasattr(pumpahead, "__version__")
    assert pumpahead.__version__ == "0.0.0"


@pytest.mark.unit
def test_core_does_not_import_homeassistant() -> None:
    """Verify that importing pumpahead does not pull in homeassistant modules."""
    import pumpahead  # noqa: F401

    ha_modules = [name for name in sys.modules if name.startswith("homeassistant")]
    assert ha_modules == [], f"Unexpected homeassistant modules loaded: {ha_modules}"
