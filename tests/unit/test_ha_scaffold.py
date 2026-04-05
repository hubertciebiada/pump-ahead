"""Tests for the PumpAhead Home Assistant integration scaffold."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Mock homeassistant modules before importing custom_components.pumpahead
# ---------------------------------------------------------------------------

_ha_const = types.ModuleType("homeassistant.const")


class _Platform:
    """Minimal stand-in for homeassistant.const.Platform."""

    SENSOR = "sensor"
    CLIMATE = "climate"


_ha_const.Platform = _Platform  # type: ignore[attr-defined]

_ha_core = types.ModuleType("homeassistant.core")
_ha_core.HomeAssistant = MagicMock  # type: ignore[attr-defined]

_ha_config_entries = types.ModuleType("homeassistant.config_entries")


class _FakeConfigEntry:
    """Minimal stand-in for homeassistant.config_entries.ConfigEntry."""

    def __class_getitem__(cls, _item: object) -> type:  # noqa: N804
        return cls


_ha_config_entries.ConfigEntry = _FakeConfigEntry  # type: ignore[attr-defined]

_ha = types.ModuleType("homeassistant")

sys.modules.setdefault("homeassistant", _ha)
sys.modules.setdefault("homeassistant.const", _ha_const)
sys.modules.setdefault("homeassistant.core", _ha_core)
sys.modules.setdefault("homeassistant.config_entries", _ha_config_entries)

# Ensure the custom_components package is importable
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Now safe to import the integration modules
from custom_components.pumpahead import (  # noqa: E402
    PumpAheadData,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.pumpahead.const import (  # noqa: E402
    CONF_ENTITY_TEMP_FLOOR,
    CONF_ENTITY_TEMP_OUTDOOR,
    CONF_ENTITY_TEMP_ROOM,
    CONF_ENTITY_VALVE,
    CONF_ROOM_NAME,
    DOMAIN,
    PLATFORMS,
)

MANIFEST_PATH = _repo_root / "custom_components" / "pumpahead" / "manifest.json"


# ---------------------------------------------------------------------------
# const.py tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_const_domain_value() -> None:
    """DOMAIN must be 'pumpahead'."""
    assert DOMAIN == "pumpahead"


@pytest.mark.unit
def test_const_platforms_is_list() -> None:
    """PLATFORMS must be a list and currently empty."""
    assert isinstance(PLATFORMS, list)
    assert len(PLATFORMS) == 0


@pytest.mark.unit
def test_const_conf_keys_defined() -> None:
    """All CONF_* constants must be non-empty strings."""
    for key in (
        CONF_ROOM_NAME,
        CONF_ENTITY_TEMP_ROOM,
        CONF_ENTITY_TEMP_FLOOR,
        CONF_ENTITY_VALVE,
        CONF_ENTITY_TEMP_OUTDOOR,
    ):
        assert isinstance(key, str)
        assert len(key) > 0


# ---------------------------------------------------------------------------
# manifest.json tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_manifest_json_valid() -> None:
    """manifest.json must be parseable and contain correct metadata."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["domain"] == "pumpahead"
    assert manifest["version"] == "0.1.0"
    assert manifest["iot_class"] == "local_polling"
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "hub"


@pytest.mark.unit
def test_manifest_json_has_required_keys() -> None:
    """manifest.json must contain all HA-required keys."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    required_keys = {"domain", "name", "version", "documentation", "codeowners", "iot_class"}
    assert required_keys.issubset(manifest.keys())


# ---------------------------------------------------------------------------
# async_setup_entry / async_unload_entry tests
# ---------------------------------------------------------------------------


def _make_hass_and_entry() -> tuple[MagicMock, MagicMock]:
    """Create mock HomeAssistant and ConfigEntry objects."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=None)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.runtime_data = None

    return hass, entry


@pytest.mark.unit
def test_async_setup_entry() -> None:
    """async_setup_entry must return True and store PumpAheadData."""
    hass, entry = _make_hass_and_entry()

    result = asyncio.run(async_setup_entry(hass, entry))

    assert result is True
    assert isinstance(entry.runtime_data, PumpAheadData)
    assert entry.runtime_data.initialized is True
    hass.config_entries.async_forward_entry_setups.assert_awaited_once()


@pytest.mark.unit
def test_async_unload_entry() -> None:
    """async_unload_entry must return True when unload succeeds."""
    hass, entry = _make_hass_and_entry()
    entry.runtime_data = PumpAheadData()

    result = asyncio.run(async_unload_entry(hass, entry))

    assert result is True
    hass.config_entries.async_unload_platforms.assert_awaited_once()


@pytest.mark.unit
def test_async_unload_entry_failure() -> None:
    """async_unload_entry must return False when unload fails."""
    hass, entry = _make_hass_and_entry()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    entry.runtime_data = PumpAheadData()

    result = asyncio.run(async_unload_entry(hass, entry))

    assert result is False
