"""Tests for the PumpAhead Home Assistant integration scaffold."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = _REPO_ROOT / "custom_components" / "pumpahead" / "manifest.json"


@pytest.fixture(scope="module")
def ha_mocks() -> Any:  # noqa: C901
    """Set up mock homeassistant modules, import custom_components.pumpahead, yield
    the imported symbols, and clean up sys.modules afterward.

    This prevents homeassistant mock modules from leaking into other test modules.
    """
    # Record which homeassistant/custom_components keys already exist
    existing_ha_keys = {
        k for k in sys.modules if k.startswith(("homeassistant", "custom_components"))
    }

    # Create mock HA modules
    ha_const = types.ModuleType("homeassistant.const")

    class _Platform:
        """Minimal stand-in for homeassistant.const.Platform."""

        SENSOR = "sensor"
        CLIMATE = "climate"

    ha_const.Platform = _Platform  # type: ignore[attr-defined]

    ha_core = types.ModuleType("homeassistant.core")
    ha_core.HomeAssistant = MagicMock  # type: ignore[attr-defined]

    ha_config_entries = types.ModuleType("homeassistant.config_entries")

    class _FakeConfigEntry:
        """Minimal stand-in for homeassistant.config_entries.ConfigEntry."""

        def __class_getitem__(cls, _item: object) -> type:  # noqa: N804
            return cls

    ha_config_entries.ConfigEntry = _FakeConfigEntry  # type: ignore[attr-defined]

    ha = types.ModuleType("homeassistant")

    # helpers.update_coordinator mock (needed by coordinator.py import chain)
    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_helpers_update_coordinator = types.ModuleType(
        "homeassistant.helpers.update_coordinator"
    )

    class _FakeDataUpdateCoordinator:
        """Minimal stand-in for DataUpdateCoordinator."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.hass = args[0] if args else kwargs.get("hass")

        def __class_getitem__(cls, _item: object) -> type:  # noqa: N804
            return cls

        async def async_config_entry_first_refresh(self) -> None:
            pass

    ha_helpers_update_coordinator.DataUpdateCoordinator = _FakeDataUpdateCoordinator  # type: ignore[attr-defined]

    # helpers.selector mock (needed by config_flow.py import chain)
    ha_helpers_selector = types.ModuleType("homeassistant.helpers.selector")

    class _SelectorConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class _Selector:
        def __init__(self, config: Any = None) -> None:
            self.config = config

    ha_helpers_selector.EntitySelector = _Selector  # type: ignore[attr-defined]
    ha_helpers_selector.EntitySelectorConfig = _SelectorConfig  # type: ignore[attr-defined]
    ha_helpers_selector.NumberSelector = _Selector  # type: ignore[attr-defined]
    ha_helpers_selector.NumberSelectorConfig = _SelectorConfig  # type: ignore[attr-defined]
    ha_helpers_selector.NumberSelectorMode = types.SimpleNamespace(BOX="box")  # type: ignore[attr-defined]
    ha_helpers_selector.SelectSelector = _Selector  # type: ignore[attr-defined]
    ha_helpers_selector.SelectSelectorConfig = _SelectorConfig  # type: ignore[attr-defined]
    ha_helpers_selector.BooleanSelector = _Selector  # type: ignore[attr-defined]
    ha_helpers_selector.TextSelector = _Selector  # type: ignore[attr-defined]

    # ConfigFlow base class mock (needed by config_flow.py)
    class _FakeConfigFlow:
        DOMAIN: str = ""
        VERSION: int = 1
        hass: Any = None

        def __init_subclass__(cls, domain: str = "", **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)
            cls.DOMAIN = domain

    ha_config_entries.ConfigFlow = _FakeConfigFlow  # type: ignore[attr-defined]

    # data_entry_flow mock (needed by config_flow.py)
    ha_data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    ha_data_entry_flow.FlowResult = dict  # type: ignore[attr-defined]

    # Inject mock modules into sys.modules
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.const"] = ha_const
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.config_entries"] = ha_config_entries
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.update_coordinator"] = (
        ha_helpers_update_coordinator
    )
    sys.modules["homeassistant.helpers.selector"] = ha_helpers_selector
    sys.modules["homeassistant.data_entry_flow"] = ha_data_entry_flow

    # Ensure the custom_components package is importable
    repo_root_str = str(_REPO_ROOT)
    path_added = repo_root_str not in sys.path
    if path_added:
        sys.path.insert(0, repo_root_str)

    # Import the integration modules
    from custom_components.pumpahead import (
        PumpAheadData,
        async_setup_entry,
        async_unload_entry,
    )
    from custom_components.pumpahead.const import (
        CONF_ENTITY_TEMP_FLOOR,
        CONF_ENTITY_TEMP_OUTDOOR,
        CONF_ENTITY_TEMP_ROOM,
        CONF_ENTITY_VALVE,
        CONF_ROOM_NAME,
        DOMAIN,
        PLATFORMS,
    )

    # Yield all symbols as a namespace object
    class _Namespace:
        pass

    ns = _Namespace()
    ns.PumpAheadData = PumpAheadData  # type: ignore[attr-defined]
    ns.async_setup_entry = async_setup_entry  # type: ignore[attr-defined]
    ns.async_unload_entry = async_unload_entry  # type: ignore[attr-defined]
    ns.DOMAIN = DOMAIN  # type: ignore[attr-defined]
    ns.PLATFORMS = PLATFORMS  # type: ignore[attr-defined]
    ns.CONF_ROOM_NAME = CONF_ROOM_NAME  # type: ignore[attr-defined]
    ns.CONF_ENTITY_TEMP_ROOM = CONF_ENTITY_TEMP_ROOM  # type: ignore[attr-defined]
    ns.CONF_ENTITY_TEMP_FLOOR = CONF_ENTITY_TEMP_FLOOR  # type: ignore[attr-defined]
    ns.CONF_ENTITY_VALVE = CONF_ENTITY_VALVE  # type: ignore[attr-defined]
    ns.CONF_ENTITY_TEMP_OUTDOOR = CONF_ENTITY_TEMP_OUTDOOR  # type: ignore[attr-defined]

    yield ns

    # Teardown: remove all homeassistant/custom_components modules we added
    keys_to_remove = [
        k
        for k in sys.modules
        if k.startswith(("homeassistant", "custom_components"))
        and k not in existing_ha_keys
    ]
    for k in keys_to_remove:
        del sys.modules[k]

    # Remove the sys.path entry if we added it
    if path_added and repo_root_str in sys.path:
        sys.path.remove(repo_root_str)


# ---------------------------------------------------------------------------
# const.py tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_const_domain_value(ha_mocks: Any) -> None:
    """DOMAIN must be 'pumpahead'."""
    assert ha_mocks.DOMAIN == "pumpahead"


@pytest.mark.unit
def test_const_platforms_is_list(ha_mocks: Any) -> None:
    """PLATFORMS must be a list and currently empty."""
    assert isinstance(ha_mocks.PLATFORMS, list)
    assert len(ha_mocks.PLATFORMS) == 0


@pytest.mark.unit
def test_const_conf_keys_defined(ha_mocks: Any) -> None:
    """All CONF_* constants must be non-empty strings."""
    for key in (
        ha_mocks.CONF_ROOM_NAME,
        ha_mocks.CONF_ENTITY_TEMP_ROOM,
        ha_mocks.CONF_ENTITY_TEMP_FLOOR,
        ha_mocks.CONF_ENTITY_VALVE,
        ha_mocks.CONF_ENTITY_TEMP_OUTDOOR,
    ):
        assert isinstance(key, str)
        assert len(key) > 0


# ---------------------------------------------------------------------------
# manifest.json tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_manifest_json_valid(ha_mocks: Any) -> None:
    """manifest.json must be parseable and contain correct metadata."""
    _ = ha_mocks  # fixture ensures HA mocks are active
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["domain"] == "pumpahead"
    assert manifest["version"] == "0.1.0"
    assert manifest["iot_class"] == "local_polling"
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "hub"


@pytest.mark.unit
def test_manifest_json_has_required_keys(ha_mocks: Any) -> None:
    """manifest.json must contain all HA-required keys."""
    _ = ha_mocks  # fixture ensures HA mocks are active
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    required_keys = {
        "domain",
        "name",
        "version",
        "documentation",
        "codeowners",
        "iot_class",
    }
    assert required_keys.issubset(manifest.keys())


# ---------------------------------------------------------------------------
# async_setup_entry / async_unload_entry tests
# ---------------------------------------------------------------------------


def _make_hass_and_entry() -> tuple[MagicMock, MagicMock]:
    """Create mock HomeAssistant and ConfigEntry objects."""
    hass = MagicMock()
    hass.config.latitude = 50.06
    hass.config.longitude = 19.94
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=None)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.runtime_data = None
    # Minimal valid config data for coordinator construction.
    entry.data = {
        "latitude": 50.06,
        "longitude": 19.94,
        "rooms": [
            {
                "room_name": "Test Room",
                "entity_temp_room": "sensor.temp_test",
                "entity_valve": "number.valve_test",
            }
        ],
        "entity_temp_outdoor": "sensor.outdoor_temp",
        "entity_weather": "",
        "algorithm_mode": "heating",
    }

    return hass, entry


@pytest.mark.unit
def test_async_setup_entry(ha_mocks: Any) -> None:
    """async_setup_entry must return True and store PumpAheadData with coordinator."""
    hass, entry = _make_hass_and_entry()

    result = asyncio.run(ha_mocks.async_setup_entry(hass, entry))

    assert result is True
    assert isinstance(entry.runtime_data, ha_mocks.PumpAheadData)
    assert entry.runtime_data.coordinator is not None
    hass.config_entries.async_forward_entry_setups.assert_awaited_once()


@pytest.mark.unit
def test_async_unload_entry(ha_mocks: Any) -> None:
    """async_unload_entry must return True when unload succeeds."""
    hass, entry = _make_hass_and_entry()
    entry.runtime_data = ha_mocks.PumpAheadData(coordinator=MagicMock())

    result = asyncio.run(ha_mocks.async_unload_entry(hass, entry))

    assert result is True
    hass.config_entries.async_unload_platforms.assert_awaited_once()


@pytest.mark.unit
def test_async_unload_entry_failure(ha_mocks: Any) -> None:
    """async_unload_entry must return False when unload fails."""
    hass, entry = _make_hass_and_entry()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    entry.runtime_data = ha_mocks.PumpAheadData(coordinator=MagicMock())

    result = asyncio.run(ha_mocks.async_unload_entry(hass, entry))

    assert result is False
