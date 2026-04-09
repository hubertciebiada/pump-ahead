"""Tests for the PumpAhead DataUpdateCoordinator.

Uses the same module-scoped mocking pattern as ``test_ha_scaffold.py``
and ``test_ha_weather.py`` to inject mock ``homeassistant`` modules into
``sys.modules``, import the coordinator, run tests, and clean up.
"""

from __future__ import annotations

import asyncio
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Module-scoped fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def coord_mocks() -> Any:  # noqa: C901
    """Set up mock HA modules, import coordinator, yield, clean up."""
    existing_ha_keys = {
        k for k in sys.modules if k.startswith(("homeassistant", "custom_components"))
    }

    # -- Mock homeassistant modules -----------------------------------------

    ha = types.ModuleType("homeassistant")

    ha_const = types.ModuleType("homeassistant.const")

    class _Platform:
        SENSOR = "sensor"
        CLIMATE = "climate"

    ha_const.Platform = _Platform  # type: ignore[attr-defined]

    ha_core = types.ModuleType("homeassistant.core")
    ha_core.HomeAssistant = MagicMock  # type: ignore[attr-defined]

    ha_config_entries = types.ModuleType("homeassistant.config_entries")

    class _FakeConfigEntry:
        def __class_getitem__(cls, _item: object) -> type:  # noqa: N804
            return cls

    ha_config_entries.ConfigEntry = _FakeConfigEntry  # type: ignore[attr-defined]

    # ConfigFlow base class mock (needed for config_flow import chain).
    class _FakeConfigFlow:
        DOMAIN: str = ""
        VERSION: int = 1
        hass: Any = None

        def __init_subclass__(cls, domain: str = "", **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)
            cls.DOMAIN = domain

    ha_config_entries.ConfigFlow = _FakeConfigFlow  # type: ignore[attr-defined]

    class _FakeOptionsFlow:
        config_entry: Any = None

    ha_config_entries.OptionsFlow = _FakeOptionsFlow  # type: ignore[attr-defined]

    # data_entry_flow mock.
    ha_data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    ha_data_entry_flow.FlowResult = dict  # type: ignore[attr-defined]

    # helpers.selector mock.
    ha_helpers = types.ModuleType("homeassistant.helpers")
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

    # helpers.update_coordinator mock.
    ha_helpers_update_coordinator = types.ModuleType(
        "homeassistant.helpers.update_coordinator"
    )

    class _FakeDataUpdateCoordinator:
        """Minimal stand-in for DataUpdateCoordinator."""

        def __init__(self, hass: Any, logger: Any, **kwargs: Any) -> None:
            self.hass = hass
            self.logger = logger
            self.name = kwargs.get("name", "")
            self.config_entry = kwargs.get("config_entry")
            self.update_interval = kwargs.get("update_interval")

        def __class_getitem__(cls, _item: object) -> type:  # noqa: N804
            return cls

        async def async_config_entry_first_refresh(self) -> None:
            pass

    ha_helpers_update_coordinator.DataUpdateCoordinator = _FakeDataUpdateCoordinator  # type: ignore[attr-defined]

    # Inject into sys.modules.
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.const"] = ha_const
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.config_entries"] = ha_config_entries
    sys.modules["homeassistant.data_entry_flow"] = ha_data_entry_flow
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.selector"] = ha_helpers_selector
    sys.modules["homeassistant.helpers.update_coordinator"] = (
        ha_helpers_update_coordinator
    )

    # voluptuous mock (needed by config_flow).
    vol = types.ModuleType("voluptuous")
    vol.Schema = MagicMock(side_effect=lambda x: x)  # type: ignore[attr-defined]
    vol.Required = MagicMock(side_effect=lambda key, **kw: key)  # type: ignore[attr-defined]
    vol.Optional = MagicMock(side_effect=lambda key, **kw: key)  # type: ignore[attr-defined]
    sys.modules["voluptuous"] = vol

    repo_root_str = str(_REPO_ROOT)
    path_added = repo_root_str not in sys.path
    if path_added:
        sys.path.insert(0, repo_root_str)

    # Import the modules under test.
    from custom_components.pumpahead.const import (
        CONF_ALGORITHM_MODE,
        CONF_ENTITY_HUMIDITY,
        CONF_ENTITY_TEMP_FLOOR,
        CONF_ENTITY_TEMP_OUTDOOR,
        CONF_ENTITY_TEMP_ROOM,
        CONF_ENTITY_VALVE,
        CONF_ENTITY_WEATHER,
        CONF_LATITUDE,
        CONF_LONGITUDE,
        CONF_ROOM_NAME,
        CONF_ROOMS,
        UPDATE_INTERVAL_MINUTES,
    )
    from custom_components.pumpahead.coordinator import (
        PumpAheadCoordinator,
        PumpAheadCoordinatorData,
        RoomSensorData,
    )

    class _Namespace:
        pass

    ns = _Namespace()
    ns.PumpAheadCoordinator = PumpAheadCoordinator  # type: ignore[attr-defined]
    ns.PumpAheadCoordinatorData = PumpAheadCoordinatorData  # type: ignore[attr-defined]
    ns.RoomSensorData = RoomSensorData  # type: ignore[attr-defined]
    ns.CONF_ROOMS = CONF_ROOMS  # type: ignore[attr-defined]
    ns.CONF_ROOM_NAME = CONF_ROOM_NAME  # type: ignore[attr-defined]
    ns.CONF_ENTITY_TEMP_ROOM = CONF_ENTITY_TEMP_ROOM  # type: ignore[attr-defined]
    ns.CONF_ENTITY_TEMP_FLOOR = CONF_ENTITY_TEMP_FLOOR  # type: ignore[attr-defined]
    ns.CONF_ENTITY_VALVE = CONF_ENTITY_VALVE  # type: ignore[attr-defined]
    ns.CONF_ENTITY_HUMIDITY = CONF_ENTITY_HUMIDITY  # type: ignore[attr-defined]
    ns.CONF_ENTITY_TEMP_OUTDOOR = CONF_ENTITY_TEMP_OUTDOOR  # type: ignore[attr-defined]
    ns.CONF_ENTITY_WEATHER = CONF_ENTITY_WEATHER  # type: ignore[attr-defined]
    ns.CONF_LATITUDE = CONF_LATITUDE  # type: ignore[attr-defined]
    ns.CONF_LONGITUDE = CONF_LONGITUDE  # type: ignore[attr-defined]
    ns.CONF_ALGORITHM_MODE = CONF_ALGORITHM_MODE  # type: ignore[attr-defined]
    ns.UPDATE_INTERVAL_MINUTES = UPDATE_INTERVAL_MINUTES  # type: ignore[attr-defined]

    yield ns

    # Teardown.
    keys_to_remove = [
        k
        for k in sys.modules
        if k.startswith(("homeassistant", "custom_components", "voluptuous"))
        and k not in existing_ha_keys
    ]
    for k in keys_to_remove:
        del sys.modules[k]

    if path_added and repo_root_str in sys.path:
        sys.path.remove(repo_root_str)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ROOM_CONFIG = {
    "room_name": "Living Room",
    "entity_temp_room": "sensor.temp_living",
    "entity_temp_floor": "sensor.floor_living",
    "entity_valve": "number.valve_living",
    "entity_humidity": "sensor.humidity_living",
}

_ENTRY_DATA = {
    "latitude": 50.06,
    "longitude": 19.94,
    "rooms": [_ROOM_CONFIG],
    "entity_temp_outdoor": "sensor.outdoor_temp",
    "entity_weather": "weather.home",
    "algorithm_mode": "heating",
}


def _make_hass_and_entry(
    coord_mocks: Any, entry_data: dict[str, Any] | None = None
) -> tuple[MagicMock, MagicMock]:
    """Create mock hass and config entry objects."""
    hass = MagicMock()
    hass.config.latitude = 50.06
    hass.config.longitude = 19.94

    def _states_get(entity_id: str) -> MagicMock:
        state = MagicMock()
        if "temp_living" in entity_id:
            state.state = "21.5"
        elif "floor_living" in entity_id:
            state.state = "28.0"
        elif "valve_living" in entity_id:
            state.state = "45.0"
        elif "humidity_living" in entity_id:
            state.state = "55.0"
        elif "outdoor_temp" in entity_id:
            state.state = "5.0"
        else:
            state.state = "unknown"
        state.attributes = {}
        return state

    hass.states.get = MagicMock(side_effect=_states_get)

    entry = MagicMock()
    entry.data = entry_data if entry_data is not None else dict(_ENTRY_DATA)
    entry.entry_id = "test_entry_id"

    return hass, entry


# ---------------------------------------------------------------------------
# TestCoordinatorInit
# ---------------------------------------------------------------------------


class TestCoordinatorInit:
    """Tests for PumpAheadCoordinator construction."""

    @pytest.mark.unit
    def test_creates_with_valid_config(self, coord_mocks: Any) -> None:
        """Constructor succeeds with valid config entry data."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        assert coordinator is not None

    @pytest.mark.unit
    def test_update_interval_is_5_minutes(self, coord_mocks: Any) -> None:
        """Update interval must be 5 minutes."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        assert coordinator.update_interval == timedelta(minutes=5)

    @pytest.mark.unit
    def test_creates_weather_source_when_entity_configured(
        self, coord_mocks: Any
    ) -> None:
        """Weather source must be created when weather entity is configured."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        assert coordinator._weather_source is not None

    @pytest.mark.unit
    def test_no_weather_source_when_entity_missing(self, coord_mocks: Any) -> None:
        """Weather source must be None when no weather entity configured."""
        data = dict(_ENTRY_DATA)
        data["entity_weather"] = ""
        hass, entry = _make_hass_and_entry(coord_mocks, entry_data=data)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        assert coordinator._weather_source is None


# ---------------------------------------------------------------------------
# TestCoordinatorUpdate
# ---------------------------------------------------------------------------


class TestCoordinatorUpdate:
    """Tests for the coordinator's _async_update_data method."""

    @pytest.mark.unit
    def test_reads_room_sensors(self, coord_mocks: Any) -> None:
        """Update must read room temperature, floor, valve, humidity."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        # Patch weather source to avoid real async call.
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        room = data.rooms["Living Room"]
        assert room.T_room == 21.5
        assert room.T_floor == 28.0
        assert room.valve_pos == 45.0
        assert room.humidity == 55.0

    @pytest.mark.unit
    def test_reads_outdoor_temperature(self, coord_mocks: Any) -> None:
        """Update must read outdoor temperature."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        assert data.T_outdoor == 5.0

    @pytest.mark.unit
    def test_handles_unavailable_entity(self, coord_mocks: Any) -> None:
        """Unavailable entity state must return None."""
        hass, entry = _make_hass_and_entry(coord_mocks)

        def _states_get_unavailable(entity_id: str) -> MagicMock:
            state = MagicMock()
            state.state = "unavailable"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_get_unavailable)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        room = data.rooms["Living Room"]
        assert room.T_room is None

    @pytest.mark.unit
    def test_handles_unknown_entity(self, coord_mocks: Any) -> None:
        """Unknown entity state must return None."""
        hass, entry = _make_hass_and_entry(coord_mocks)

        def _states_get_unknown(entity_id: str) -> MagicMock:
            state = MagicMock()
            state.state = "unknown"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_get_unknown)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        room = data.rooms["Living Room"]
        assert room.T_room is None

    @pytest.mark.unit
    def test_handles_missing_entity(self, coord_mocks: Any) -> None:
        """Entity that returns None from states.get must return None."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        hass.states.get = MagicMock(return_value=None)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        room = data.rooms["Living Room"]
        assert room.T_room is None
        assert room.T_floor is None
        assert room.valve_pos is None

    @pytest.mark.unit
    def test_handles_non_numeric_state(self, coord_mocks: Any) -> None:
        """Non-numeric entity state must return None."""
        hass, entry = _make_hass_and_entry(coord_mocks)

        def _states_get_nonnumeric(entity_id: str) -> MagicMock:
            state = MagicMock()
            state.state = "not_a_number"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_get_nonnumeric)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        room = data.rooms["Living Room"]
        assert room.T_room is None

    @pytest.mark.unit
    def test_weather_update_called(self, coord_mocks: Any) -> None:
        """Weather source async_update must be called during update."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        # Replace weather source with a mock.
        mock_ws = MagicMock()
        mock_ws.async_update = AsyncMock()
        coordinator._weather_source = mock_ws
        asyncio.run(coordinator._async_update_data())
        mock_ws.async_update.assert_awaited_once_with(hass)

    @pytest.mark.unit
    def test_weather_update_failure_does_not_crash(self, coord_mocks: Any) -> None:
        """Weather update failure must not crash the coordinator."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        mock_ws = MagicMock()
        mock_ws.async_update = AsyncMock(side_effect=RuntimeError("fail"))
        coordinator._weather_source = mock_ws
        # Must not raise.
        data = asyncio.run(coordinator._async_update_data())
        assert data.last_update_success is True


# ---------------------------------------------------------------------------
# TestCoordinatorDataStructure
# ---------------------------------------------------------------------------


class TestCoordinatorDataStructure:
    """Tests for the coordinator's returned data structure."""

    @pytest.mark.unit
    def test_data_contains_all_rooms(self, coord_mocks: Any) -> None:
        """Coordinator data must contain all configured rooms."""
        data = dict(_ENTRY_DATA)
        data["rooms"] = [
            {
                "room_name": "Living Room",
                "entity_temp_room": "sensor.temp_living",
                "entity_valve": "number.valve_living",
            },
            {
                "room_name": "Bedroom",
                "entity_temp_room": "sensor.temp_living",
                "entity_valve": "number.valve_living",
            },
        ]
        hass, entry = _make_hass_and_entry(coord_mocks, entry_data=data)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        result = asyncio.run(coordinator._async_update_data())
        assert "Living Room" in result.rooms
        assert "Bedroom" in result.rooms
        assert len(result.rooms) == 2

    @pytest.mark.unit
    def test_data_has_correct_algorithm_mode(self, coord_mocks: Any) -> None:
        """Coordinator data must reflect the configured algorithm mode."""
        data = dict(_ENTRY_DATA)
        data["algorithm_mode"] = "cooling"
        hass, entry = _make_hass_and_entry(coord_mocks, entry_data=data)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        result = asyncio.run(coordinator._async_update_data())
        assert result.algorithm_mode == "cooling"


# ---------------------------------------------------------------------------
# TestFallbackCache
# ---------------------------------------------------------------------------


class TestFallbackCache:
    """Tests for the 5-minute fallback cache in _read_float_state."""

    @pytest.mark.unit
    def test_cached_value_returned_within_5_minutes(self, coord_mocks: Any) -> None:
        """Unavailable entity within cache TTL must return cached value."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)

        # First read succeeds — populates cache.
        good_state = MagicMock()
        good_state.state = "21.5"
        hass.states.get = MagicMock(return_value=good_state)
        val = coordinator._read_float_state("sensor.temp_living")
        assert val == 21.5

        # Second read — entity is now unavailable.
        unavail_state = MagicMock()
        unavail_state.state = "unavailable"
        hass.states.get = MagicMock(return_value=unavail_state)
        val = coordinator._read_float_state("sensor.temp_living")
        assert val == 21.5  # cached

    @pytest.mark.unit
    def test_cached_value_expires_after_5_minutes(self, coord_mocks: Any) -> None:
        """Unavailable entity beyond cache TTL must return None."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)

        # Populate cache with an old timestamp.
        old_ts = datetime.now(UTC) - timedelta(seconds=301)
        coordinator._entity_cache["sensor.temp_living"] = (21.5, old_ts)

        # Read when entity is unavailable — cache expired.
        unavail_state = MagicMock()
        unavail_state.state = "unavailable"
        hass.states.get = MagicMock(return_value=unavail_state)
        val = coordinator._read_float_state("sensor.temp_living")
        assert val is None

    @pytest.mark.unit
    def test_never_cached_entity_returns_none(self, coord_mocks: Any) -> None:
        """Entity that was never available must return None immediately."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)

        unavail_state = MagicMock()
        unavail_state.state = "unavailable"
        hass.states.get = MagicMock(return_value=unavail_state)
        val = coordinator._read_float_state("sensor.temp_living")
        assert val is None

    @pytest.mark.unit
    def test_cache_updated_on_successful_read(self, coord_mocks: Any) -> None:
        """Successful read must update the cache entry."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)

        good_state = MagicMock()
        good_state.state = "22.0"
        hass.states.get = MagicMock(return_value=good_state)
        coordinator._read_float_state("sensor.temp_living")

        assert "sensor.temp_living" in coordinator._entity_cache
        cached_val, cached_ts = coordinator._entity_cache["sensor.temp_living"]
        assert cached_val == 22.0
        assert (datetime.now(UTC) - cached_ts).total_seconds() < 2.0

    @pytest.mark.unit
    def test_unknown_state_uses_cache(self, coord_mocks: Any) -> None:
        """Entity with 'unknown' state must use cache if available."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)

        # First read succeeds.
        good_state = MagicMock()
        good_state.state = "23.0"
        hass.states.get = MagicMock(return_value=good_state)
        coordinator._read_float_state("sensor.temp_living")

        # Second read — entity is unknown.
        unknown_state = MagicMock()
        unknown_state.state = "unknown"
        hass.states.get = MagicMock(return_value=unknown_state)
        val = coordinator._read_float_state("sensor.temp_living")
        assert val == 23.0

    @pytest.mark.unit
    def test_none_entity_returns_none_no_cache(self, coord_mocks: Any) -> None:
        """None entity state (missing) must use cache if available."""
        hass, entry = _make_hass_and_entry(coord_mocks)
        coordinator = coord_mocks.PumpAheadCoordinator(hass, entry)

        # First read succeeds.
        good_state = MagicMock()
        good_state.state = "24.0"
        hass.states.get = MagicMock(return_value=good_state)
        coordinator._read_float_state("sensor.temp_living")

        # Second read — entity returns None.
        hass.states.get = MagicMock(return_value=None)
        val = coordinator._read_float_state("sensor.temp_living")
        assert val == 24.0  # cached
