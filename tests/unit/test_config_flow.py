"""Tests for the PumpAhead config flow.

Uses the same module-scoped mocking pattern as ``test_ha_scaffold.py``
and ``test_ha_weather.py`` to inject mock ``homeassistant`` modules into
``sys.modules``, import the config flow, run tests, and clean up.
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Module-scoped fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cf_mocks() -> Any:  # noqa: C901
    """Set up mock HA modules, import config_flow and const, yield, clean up."""
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

    # ConfigFlow base class mock.
    class _FakeConfigFlow:
        """Minimal stand-in for homeassistant.config_entries.ConfigFlow."""

        DOMAIN: str = ""
        VERSION: int = 1
        hass: Any = None

        def __init_subclass__(cls, domain: str = "", **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)
            cls.DOMAIN = domain

        def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
            return {"type": "create_entry", **kwargs}

        async def async_set_unique_id(self, unique_id: str) -> None:
            self._unique_id = unique_id  # type: ignore[attr-defined]

        def _abort_if_unique_id_configured(self) -> None:
            pass

    ha_config_entries.ConfigFlow = _FakeConfigFlow  # type: ignore[attr-defined]

    class _FakeOptionsFlow:
        """Minimal stand-in for homeassistant.config_entries.OptionsFlow."""

        config_entry: Any = None

        def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
            return {"type": "create_entry", **kwargs}

    ha_config_entries.OptionsFlow = _FakeOptionsFlow  # type: ignore[attr-defined]

    # data_entry_flow mock.
    ha_data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    ha_data_entry_flow.FlowResult = dict  # type: ignore[attr-defined]

    # helpers.selector mock — we need selector classes that accept config args.
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

    # voluptuous mock.
    vol = types.ModuleType("voluptuous")

    class _VolSchema:
        """Minimal stand-in for voluptuous.Schema."""

        def __init__(self, schema: Any) -> None:
            self._schema = schema

    class _VolRequired:
        """Minimal stand-in for voluptuous.Required."""

        def __init__(self, key: str, **kwargs: Any) -> None:
            self.key = key
            self.default = kwargs.get("default")

        def __hash__(self) -> int:
            return hash(self.key)

        def __eq__(self, other: object) -> bool:
            if isinstance(other, _VolRequired):
                return self.key == other.key
            return self.key == other

    class _VolOptional:
        """Minimal stand-in for voluptuous.Optional."""

        def __init__(self, key: str, **kwargs: Any) -> None:
            self.key = key
            self.default = kwargs.get("default")

        def __hash__(self) -> int:
            return hash(self.key)

        def __eq__(self, other: object) -> bool:
            if isinstance(other, _VolOptional):
                return self.key == other.key
            return self.key == other

    vol.Schema = _VolSchema  # type: ignore[attr-defined]
    vol.Required = _VolRequired  # type: ignore[attr-defined]
    vol.Optional = _VolOptional  # type: ignore[attr-defined]

    # Inject into sys.modules.
    sys.modules["voluptuous"] = vol
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

    repo_root_str = str(_REPO_ROOT)
    path_added = repo_root_str not in sys.path
    if path_added:
        sys.path.insert(0, repo_root_str)

    # Import the modules under test.
    from custom_components.pumpahead.config_flow import PumpAheadConfigFlow
    from custom_components.pumpahead.const import (
        CONF_ADD_ANOTHER,
        CONF_ALGORITHM_MODE,
        CONF_ENTITY_HUMIDITY,
        CONF_ENTITY_SPLIT,
        CONF_ENTITY_TEMP_FLOOR,
        CONF_ENTITY_TEMP_OUTDOOR,
        CONF_ENTITY_TEMP_ROOM,
        CONF_ENTITY_VALVE,
        CONF_ENTITY_WEATHER,
        CONF_HAS_SPLIT,
        CONF_LATITUDE,
        CONF_LONGITUDE,
        CONF_ROOM_AREA,
        CONF_ROOM_NAME,
        CONF_ROOMS,
        CONF_W_COMFORT,
        CONF_W_ENERGY,
        CONF_W_SMOOTH,
        VALID_PERCENT_UNITS,
        VALID_POWER_UNITS,
        VALID_TEMP_UNITS,
    )
    from custom_components.pumpahead.entity_validator import (
        EntityValidator,
        ValidationResult,
    )

    class _Namespace:
        pass

    ns = _Namespace()
    ns.PumpAheadConfigFlow = PumpAheadConfigFlow  # type: ignore[attr-defined]
    ns.CONF_LATITUDE = CONF_LATITUDE  # type: ignore[attr-defined]
    ns.CONF_LONGITUDE = CONF_LONGITUDE  # type: ignore[attr-defined]
    ns.CONF_ROOM_NAME = CONF_ROOM_NAME  # type: ignore[attr-defined]
    ns.CONF_ROOM_AREA = CONF_ROOM_AREA  # type: ignore[attr-defined]
    ns.CONF_HAS_SPLIT = CONF_HAS_SPLIT  # type: ignore[attr-defined]
    ns.CONF_ADD_ANOTHER = CONF_ADD_ANOTHER  # type: ignore[attr-defined]
    ns.CONF_ROOMS = CONF_ROOMS  # type: ignore[attr-defined]
    ns.CONF_ENTITY_TEMP_ROOM = CONF_ENTITY_TEMP_ROOM  # type: ignore[attr-defined]
    ns.CONF_ENTITY_TEMP_FLOOR = CONF_ENTITY_TEMP_FLOOR  # type: ignore[attr-defined]
    ns.CONF_ENTITY_VALVE = CONF_ENTITY_VALVE  # type: ignore[attr-defined]
    ns.CONF_ENTITY_HUMIDITY = CONF_ENTITY_HUMIDITY  # type: ignore[attr-defined]
    ns.CONF_ENTITY_SPLIT = CONF_ENTITY_SPLIT  # type: ignore[attr-defined]
    ns.CONF_ENTITY_TEMP_OUTDOOR = CONF_ENTITY_TEMP_OUTDOOR  # type: ignore[attr-defined]
    ns.CONF_ENTITY_WEATHER = CONF_ENTITY_WEATHER  # type: ignore[attr-defined]
    ns.CONF_ALGORITHM_MODE = CONF_ALGORITHM_MODE  # type: ignore[attr-defined]
    ns.CONF_W_COMFORT = CONF_W_COMFORT  # type: ignore[attr-defined]
    ns.CONF_W_ENERGY = CONF_W_ENERGY  # type: ignore[attr-defined]
    ns.CONF_W_SMOOTH = CONF_W_SMOOTH  # type: ignore[attr-defined]
    ns.VALID_TEMP_UNITS = VALID_TEMP_UNITS  # type: ignore[attr-defined]
    ns.VALID_PERCENT_UNITS = VALID_PERCENT_UNITS  # type: ignore[attr-defined]
    ns.VALID_POWER_UNITS = VALID_POWER_UNITS  # type: ignore[attr-defined]
    ns.EntityValidator = EntityValidator  # type: ignore[attr-defined]
    ns.ValidationResult = ValidationResult  # type: ignore[attr-defined]

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


def _make_flow(cf_mocks: Any) -> Any:
    """Create a PumpAheadConfigFlow with a mocked hass attached."""
    flow = cf_mocks.PumpAheadConfigFlow()
    hass = MagicMock()
    hass.config.latitude = 50.06
    hass.config.longitude = 19.94

    # Default entity state mock: returns valid temperature entity.
    def _states_get(entity_id: str) -> MagicMock:
        state = MagicMock()
        state.state = "21.5"
        if "temp" in entity_id or "outdoor" in entity_id:
            state.attributes = {"unit_of_measurement": "\u00b0C"}
        elif "valve" in entity_id or "humidity" in entity_id:
            state.attributes = {"unit_of_measurement": "%"}
        elif "weather" in entity_id:
            state.attributes = {}
        else:
            state.attributes = {}
        return state

    hass.states.get = MagicMock(side_effect=_states_get)
    flow.hass = hass
    return flow


def _run(coro: Any) -> Any:
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# TestStepUser (Step 1: Location)
# ---------------------------------------------------------------------------


class TestStepUser:
    """Tests for the location step."""

    @pytest.mark.unit
    def test_show_form_with_defaults(self, cf_mocks: Any) -> None:
        """First call (user_input=None) must show form with HA defaults."""
        flow = _make_flow(cf_mocks)
        result = _run(flow.async_step_user(None))
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    @pytest.mark.unit
    def test_valid_location_proceeds_to_rooms(self, cf_mocks: Any) -> None:
        """Valid lat/lon must proceed to the rooms step."""
        flow = _make_flow(cf_mocks)
        result = _run(
            flow.async_step_user(
                {cf_mocks.CONF_LATITUDE: 50.0, cf_mocks.CONF_LONGITUDE: 20.0}
            )
        )
        # Should show the rooms form.
        assert result["type"] == "form"
        assert result["step_id"] == "rooms"

    @pytest.mark.unit
    def test_invalid_latitude_shows_error(self, cf_mocks: Any) -> None:
        """Latitude outside [-90, 90] must show error."""
        flow = _make_flow(cf_mocks)
        result = _run(
            flow.async_step_user(
                {cf_mocks.CONF_LATITUDE: 100.0, cf_mocks.CONF_LONGITUDE: 20.0}
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert "invalid_latitude" in result["errors"].values()

    @pytest.mark.unit
    def test_invalid_longitude_shows_error(self, cf_mocks: Any) -> None:
        """Longitude outside [-180, 180] must show error."""
        flow = _make_flow(cf_mocks)
        result = _run(
            flow.async_step_user(
                {cf_mocks.CONF_LATITUDE: 50.0, cf_mocks.CONF_LONGITUDE: 200.0}
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert "invalid_longitude" in result["errors"].values()


# ---------------------------------------------------------------------------
# TestStepRooms (Step 2: Room definition)
# ---------------------------------------------------------------------------


class TestStepRooms:
    """Tests for the room definition step."""

    @pytest.mark.unit
    def test_add_single_room_proceeds(self, cf_mocks: Any) -> None:
        """Single room without add_another must proceed to entities."""
        flow = _make_flow(cf_mocks)
        # Set location first.
        _run(
            flow.async_step_user(
                {cf_mocks.CONF_LATITUDE: 50.0, cf_mocks.CONF_LONGITUDE: 20.0}
            )
        )
        result = _run(
            flow.async_step_rooms(
                {
                    cf_mocks.CONF_ROOM_NAME: "Living Room",
                    cf_mocks.CONF_ROOM_AREA: 25.0,
                    cf_mocks.CONF_HAS_SPLIT: False,
                    cf_mocks.CONF_ADD_ANOTHER: False,
                }
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "entities"

    @pytest.mark.unit
    def test_add_multiple_rooms_loop(self, cf_mocks: Any) -> None:
        """add_another=True must loop back to rooms step."""
        flow = _make_flow(cf_mocks)
        _run(
            flow.async_step_user(
                {cf_mocks.CONF_LATITUDE: 50.0, cf_mocks.CONF_LONGITUDE: 20.0}
            )
        )
        # First room with add_another=True.
        result = _run(
            flow.async_step_rooms(
                {
                    cf_mocks.CONF_ROOM_NAME: "Living Room",
                    cf_mocks.CONF_ROOM_AREA: 25.0,
                    cf_mocks.CONF_HAS_SPLIT: False,
                    cf_mocks.CONF_ADD_ANOTHER: True,
                }
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "rooms"

        # Second room without add_another.
        result = _run(
            flow.async_step_rooms(
                {
                    cf_mocks.CONF_ROOM_NAME: "Bedroom",
                    cf_mocks.CONF_ROOM_AREA: 15.0,
                    cf_mocks.CONF_HAS_SPLIT: False,
                    cf_mocks.CONF_ADD_ANOTHER: False,
                }
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "entities"

    @pytest.mark.unit
    def test_empty_name_error(self, cf_mocks: Any) -> None:
        """Empty room name must show error."""
        flow = _make_flow(cf_mocks)
        _run(
            flow.async_step_user(
                {cf_mocks.CONF_LATITUDE: 50.0, cf_mocks.CONF_LONGITUDE: 20.0}
            )
        )
        result = _run(
            flow.async_step_rooms(
                {
                    cf_mocks.CONF_ROOM_NAME: "",
                    cf_mocks.CONF_ROOM_AREA: 20.0,
                    cf_mocks.CONF_HAS_SPLIT: False,
                    cf_mocks.CONF_ADD_ANOTHER: False,
                }
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "rooms"
        assert "empty_room_name" in result["errors"].values()

    @pytest.mark.unit
    def test_duplicate_name_error(self, cf_mocks: Any) -> None:
        """Duplicate room name must show error."""
        flow = _make_flow(cf_mocks)
        _run(
            flow.async_step_user(
                {cf_mocks.CONF_LATITUDE: 50.0, cf_mocks.CONF_LONGITUDE: 20.0}
            )
        )
        # Add first room.
        _run(
            flow.async_step_rooms(
                {
                    cf_mocks.CONF_ROOM_NAME: "Living Room",
                    cf_mocks.CONF_ROOM_AREA: 25.0,
                    cf_mocks.CONF_HAS_SPLIT: False,
                    cf_mocks.CONF_ADD_ANOTHER: True,
                }
            )
        )
        # Try duplicate name.
        result = _run(
            flow.async_step_rooms(
                {
                    cf_mocks.CONF_ROOM_NAME: "Living Room",
                    cf_mocks.CONF_ROOM_AREA: 20.0,
                    cf_mocks.CONF_HAS_SPLIT: False,
                    cf_mocks.CONF_ADD_ANOTHER: False,
                }
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "rooms"
        assert "duplicate_room_name" in result["errors"].values()

    @pytest.mark.unit
    def test_invalid_area_error(self, cf_mocks: Any) -> None:
        """Area <= 0 must show error."""
        flow = _make_flow(cf_mocks)
        _run(
            flow.async_step_user(
                {cf_mocks.CONF_LATITUDE: 50.0, cf_mocks.CONF_LONGITUDE: 20.0}
            )
        )
        result = _run(
            flow.async_step_rooms(
                {
                    cf_mocks.CONF_ROOM_NAME: "Living Room",
                    cf_mocks.CONF_ROOM_AREA: 0,
                    cf_mocks.CONF_HAS_SPLIT: False,
                    cf_mocks.CONF_ADD_ANOTHER: False,
                }
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "rooms"
        assert "invalid_area" in result["errors"].values()


# ---------------------------------------------------------------------------
# TestStepEntities (Step 3: Entity mapping)
# ---------------------------------------------------------------------------


class TestStepEntities:
    """Tests for the entity mapping step."""

    def _setup_to_entities(self, cf_mocks: Any) -> Any:
        """Create a flow and advance to the entities step with one room."""
        flow = _make_flow(cf_mocks)
        _run(
            flow.async_step_user(
                {cf_mocks.CONF_LATITUDE: 50.0, cf_mocks.CONF_LONGITUDE: 20.0}
            )
        )
        _run(
            flow.async_step_rooms(
                {
                    cf_mocks.CONF_ROOM_NAME: "Living Room",
                    cf_mocks.CONF_ROOM_AREA: 25.0,
                    cf_mocks.CONF_HAS_SPLIT: False,
                    cf_mocks.CONF_ADD_ANOTHER: False,
                }
            )
        )
        return flow

    @pytest.mark.unit
    def test_valid_entities_proceed(self, cf_mocks: Any) -> None:
        """Valid entities must proceed to algorithm step."""
        flow = self._setup_to_entities(cf_mocks)
        result = _run(
            flow.async_step_entities(
                {
                    cf_mocks.CONF_ENTITY_TEMP_ROOM: "sensor.temp_living",
                    cf_mocks.CONF_ENTITY_VALVE: "number.valve_living",
                    cf_mocks.CONF_ENTITY_TEMP_OUTDOOR: "sensor.outdoor_temp",
                }
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "algorithm"

    @pytest.mark.unit
    def test_entity_not_found_error(self, cf_mocks: Any) -> None:
        """Non-existent entity must show entity_not_found error."""
        flow = self._setup_to_entities(cf_mocks)
        # Make states.get return None for the room temp entity.
        original_side_effect = flow.hass.states.get.side_effect

        def _states_get_missing(entity_id: str) -> MagicMock | None:
            if entity_id == "sensor.nonexistent":
                return None
            return original_side_effect(entity_id)

        flow.hass.states.get = MagicMock(side_effect=_states_get_missing)

        result = _run(
            flow.async_step_entities(
                {
                    cf_mocks.CONF_ENTITY_TEMP_ROOM: "sensor.nonexistent",
                    cf_mocks.CONF_ENTITY_VALVE: "number.valve_living",
                    cf_mocks.CONF_ENTITY_TEMP_OUTDOOR: "sensor.outdoor_temp",
                }
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "entities"
        assert "entity_not_found" in result["errors"].values()

    @pytest.mark.unit
    def test_wrong_unit_error(self, cf_mocks: Any) -> None:
        """Entity with wrong unit must show invalid_unit error."""
        flow = self._setup_to_entities(cf_mocks)
        original_side_effect = flow.hass.states.get.side_effect

        def _states_get_wrong_unit(entity_id: str) -> MagicMock:
            if entity_id == "sensor.temp_fahrenheit":
                state = MagicMock()
                state.state = "70.0"
                state.attributes = {"unit_of_measurement": "\u00b0F"}
                return state
            return original_side_effect(entity_id)

        flow.hass.states.get = MagicMock(side_effect=_states_get_wrong_unit)

        result = _run(
            flow.async_step_entities(
                {
                    cf_mocks.CONF_ENTITY_TEMP_ROOM: "sensor.temp_fahrenheit",
                    cf_mocks.CONF_ENTITY_VALVE: "number.valve_living",
                    cf_mocks.CONF_ENTITY_TEMP_OUTDOOR: "sensor.outdoor_temp",
                }
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "entities"
        assert "invalid_unit" in result["errors"].values()

    @pytest.mark.unit
    def test_optional_entities_skipped(self, cf_mocks: Any) -> None:
        """Optional entities can be omitted without error."""
        flow = self._setup_to_entities(cf_mocks)
        result = _run(
            flow.async_step_entities(
                {
                    cf_mocks.CONF_ENTITY_TEMP_ROOM: "sensor.temp_living",
                    cf_mocks.CONF_ENTITY_VALVE: "number.valve_living",
                    cf_mocks.CONF_ENTITY_TEMP_OUTDOOR: "sensor.outdoor_temp",
                    # No floor temp, no humidity, no weather -- all optional.
                }
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "algorithm"


# ---------------------------------------------------------------------------
# TestStepAlgorithm (Step 4: Algorithm parameters)
# ---------------------------------------------------------------------------


class TestStepAlgorithm:
    """Tests for the algorithm parameters step."""

    def _setup_to_algorithm(self, cf_mocks: Any) -> Any:
        """Create a flow and advance to the algorithm step."""
        flow = _make_flow(cf_mocks)
        _run(
            flow.async_step_user(
                {cf_mocks.CONF_LATITUDE: 50.0, cf_mocks.CONF_LONGITUDE: 20.0}
            )
        )
        _run(
            flow.async_step_rooms(
                {
                    cf_mocks.CONF_ROOM_NAME: "Living Room",
                    cf_mocks.CONF_ROOM_AREA: 25.0,
                    cf_mocks.CONF_HAS_SPLIT: False,
                    cf_mocks.CONF_ADD_ANOTHER: False,
                }
            )
        )
        _run(
            flow.async_step_entities(
                {
                    cf_mocks.CONF_ENTITY_TEMP_ROOM: "sensor.temp_living",
                    cf_mocks.CONF_ENTITY_VALVE: "number.valve_living",
                    cf_mocks.CONF_ENTITY_TEMP_OUTDOOR: "sensor.outdoor_temp",
                }
            )
        )
        return flow

    @pytest.mark.unit
    def test_valid_params_proceed(self, cf_mocks: Any) -> None:
        """Valid algorithm params must proceed to confirm step."""
        flow = self._setup_to_algorithm(cf_mocks)
        result = _run(
            flow.async_step_algorithm(
                {
                    cf_mocks.CONF_ALGORITHM_MODE: "heating",
                    cf_mocks.CONF_W_COMFORT: 1.0,
                    cf_mocks.CONF_W_ENERGY: 0.1,
                    cf_mocks.CONF_W_SMOOTH: 0.01,
                }
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

    @pytest.mark.unit
    def test_negative_weight_error(self, cf_mocks: Any) -> None:
        """Negative weight must show invalid_weight error."""
        flow = self._setup_to_algorithm(cf_mocks)
        result = _run(
            flow.async_step_algorithm(
                {
                    cf_mocks.CONF_ALGORITHM_MODE: "heating",
                    cf_mocks.CONF_W_COMFORT: -1.0,
                    cf_mocks.CONF_W_ENERGY: 0.1,
                    cf_mocks.CONF_W_SMOOTH: 0.01,
                }
            )
        )
        assert result["type"] == "form"
        assert result["step_id"] == "algorithm"
        assert "invalid_weight" in result["errors"].values()


# ---------------------------------------------------------------------------
# TestStepConfirm (Step 5: Confirmation)
# ---------------------------------------------------------------------------


class TestStepConfirm:
    """Tests for the confirmation step."""

    def _setup_to_confirm(self, cf_mocks: Any) -> Any:
        """Create a flow and advance to the confirm step."""
        flow = _make_flow(cf_mocks)
        _run(
            flow.async_step_user(
                {cf_mocks.CONF_LATITUDE: 50.0, cf_mocks.CONF_LONGITUDE: 20.0}
            )
        )
        _run(
            flow.async_step_rooms(
                {
                    cf_mocks.CONF_ROOM_NAME: "Living Room",
                    cf_mocks.CONF_ROOM_AREA: 25.0,
                    cf_mocks.CONF_HAS_SPLIT: False,
                    cf_mocks.CONF_ADD_ANOTHER: False,
                }
            )
        )
        _run(
            flow.async_step_entities(
                {
                    cf_mocks.CONF_ENTITY_TEMP_ROOM: "sensor.temp_living",
                    cf_mocks.CONF_ENTITY_VALVE: "number.valve_living",
                    cf_mocks.CONF_ENTITY_TEMP_OUTDOOR: "sensor.outdoor_temp",
                }
            )
        )
        _run(
            flow.async_step_algorithm(
                {
                    cf_mocks.CONF_ALGORITHM_MODE: "heating",
                    cf_mocks.CONF_W_COMFORT: 1.0,
                    cf_mocks.CONF_W_ENERGY: 0.1,
                    cf_mocks.CONF_W_SMOOTH: 0.01,
                }
            )
        )
        return flow

    @pytest.mark.unit
    def test_confirm_shows_summary(self, cf_mocks: Any) -> None:
        """Confirm step with no input must show summary form."""
        flow = self._setup_to_confirm(cf_mocks)
        result = _run(flow.async_step_confirm(None))
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"
        assert "num_rooms" in result["description_placeholders"]
        assert result["description_placeholders"]["num_rooms"] == "1"

    @pytest.mark.unit
    def test_creates_entry_with_correct_data(self, cf_mocks: Any) -> None:
        """Confirming must create an entry with all accumulated data."""
        flow = self._setup_to_confirm(cf_mocks)
        result = _run(flow.async_step_confirm({}))
        assert result["type"] == "create_entry"
        assert result["title"] == "PumpAhead"
        data = result["data"]
        assert data[cf_mocks.CONF_LATITUDE] == 50.0
        assert data[cf_mocks.CONF_LONGITUDE] == 20.0
        assert cf_mocks.CONF_ROOMS in data
        assert len(data[cf_mocks.CONF_ROOMS]) == 1
        assert data[cf_mocks.CONF_ROOMS][0][cf_mocks.CONF_ROOM_NAME] == "Living Room"
        assert data[cf_mocks.CONF_ALGORITHM_MODE] == "heating"
        assert data[cf_mocks.CONF_W_COMFORT] == 1.0


# ---------------------------------------------------------------------------
# TestEntityValidation
# ---------------------------------------------------------------------------


class TestEntityValidation:
    """Tests for entity validation via EntityValidator in the config flow."""

    @pytest.mark.unit
    def test_validate_celsius_entity(self, cf_mocks: Any) -> None:
        """Entity with unit degC must pass validation."""
        hass = MagicMock()
        state = MagicMock()
        state.state = "21.5"
        state.attributes = {"unit_of_measurement": "\u00b0C"}
        hass.states.get.return_value = state
        validator = cf_mocks.EntityValidator(hass)
        result = validator.validate_unit("sensor.temp_room", cf_mocks.VALID_TEMP_UNITS)
        assert result.valid is True

    @pytest.mark.unit
    def test_validate_percent_entity(self, cf_mocks: Any) -> None:
        """Entity with unit % must pass validation."""
        hass = MagicMock()
        state = MagicMock()
        state.state = "55.0"
        state.attributes = {"unit_of_measurement": "%"}
        hass.states.get.return_value = state
        validator = cf_mocks.EntityValidator(hass)
        result = validator.validate_unit(
            "sensor.humidity_room", cf_mocks.VALID_PERCENT_UNITS
        )
        assert result.valid is True

    @pytest.mark.unit
    def test_validate_missing_entity_returns_error(self, cf_mocks: Any) -> None:
        """Non-existent entity must return entity_not_found."""
        hass = MagicMock()
        hass.states.get.return_value = None
        validator = cf_mocks.EntityValidator(hass)
        result = validator.validate_unit(
            "sensor.nonexistent", cf_mocks.VALID_TEMP_UNITS
        )
        assert result.valid is False
        assert result.error_key == "entity_not_found"

    @pytest.mark.unit
    def test_validate_empty_entity_id_returns_valid(self, cf_mocks: Any) -> None:
        """Empty entity ID must return valid (skip validation)."""
        hass = MagicMock()
        validator = cf_mocks.EntityValidator(hass)
        result = validator.validate_unit("", cf_mocks.VALID_TEMP_UNITS)
        assert result.valid is True

    @pytest.mark.unit
    def test_validate_entity_no_unit_attribute_accepted(self, cf_mocks: Any) -> None:
        """Entity without unit_of_measurement attribute must be accepted."""
        hass = MagicMock()
        state = MagicMock()
        state.attributes = {}
        hass.states.get.return_value = state
        validator = cf_mocks.EntityValidator(hass)
        result = validator.validate_unit(
            "number.valve_living", cf_mocks.VALID_PERCENT_UNITS
        )
        assert result.valid is True

    @pytest.mark.unit
    def test_validate_wrong_unit_returns_error(self, cf_mocks: Any) -> None:
        """Entity with wrong unit must return invalid_unit."""
        hass = MagicMock()
        state = MagicMock()
        state.attributes = {"unit_of_measurement": "\u00b0F"}
        hass.states.get.return_value = state
        validator = cf_mocks.EntityValidator(hass)
        result = validator.validate_unit(
            "sensor.temp_fahrenheit", cf_mocks.VALID_TEMP_UNITS
        )
        assert result.valid is False
        assert result.error_key == "invalid_unit"
