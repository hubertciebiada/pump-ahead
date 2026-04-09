"""Tests for PumpAhead climate entities and live control.

Uses the same module-scoped mocking pattern as ``test_shadow_sensors.py``
to inject mock ``homeassistant`` modules into ``sys.modules``, import
the climate module, run tests, and clean up.
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Module-scoped fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def climate_mocks() -> Any:  # noqa: C901
    """Set up mock HA modules, import climate module, yield, clean up."""
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

    class _EntityCategory:
        DIAGNOSTIC = "diagnostic"
        CONFIG = "config"

    ha_const.EntityCategory = _EntityCategory  # type: ignore[attr-defined]

    class _UnitOfTemperature:
        CELSIUS = "\u00b0C"

    ha_const.UnitOfTemperature = _UnitOfTemperature  # type: ignore[attr-defined]

    ha_core = types.ModuleType("homeassistant.core")
    ha_core.HomeAssistant = MagicMock  # type: ignore[attr-defined]

    ha_config_entries = types.ModuleType("homeassistant.config_entries")

    class _FakeConfigEntry:
        def __class_getitem__(cls, _item: object) -> type:  # noqa: N804
            return cls

    ha_config_entries.ConfigEntry = _FakeConfigEntry  # type: ignore[attr-defined]

    class _FakeConfigFlow:
        DOMAIN: str = ""
        VERSION: int = 1
        hass: Any = None

        def __init_subclass__(cls, domain: str = "", **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)
            cls.DOMAIN = domain

        @staticmethod
        def async_get_options_flow(config_entry: Any) -> Any:
            return None

    ha_config_entries.ConfigFlow = _FakeConfigFlow  # type: ignore[attr-defined]

    class _FakeOptionsFlow:
        config_entry: Any = None

        def async_show_form(self, **kwargs: Any) -> dict:
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs: Any) -> dict:
            return {"type": "create_entry", **kwargs}

    ha_config_entries.OptionsFlow = _FakeOptionsFlow  # type: ignore[attr-defined]

    ha_data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    ha_data_entry_flow.FlowResult = dict  # type: ignore[attr-defined]

    # helpers modules
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

    # helpers.entity_platform mock
    ha_helpers_entity_platform = types.ModuleType(
        "homeassistant.helpers.entity_platform"
    )
    ha_helpers_entity_platform.AddEntitiesCallback = MagicMock  # type: ignore[attr-defined]

    # helpers.update_coordinator mock
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
            self.data: Any = None

        def __class_getitem__(cls, _item: object) -> type:  # noqa: N804
            return cls

        async def async_config_entry_first_refresh(self) -> None:
            pass

    ha_helpers_update_coordinator.DataUpdateCoordinator = _FakeDataUpdateCoordinator  # type: ignore[attr-defined]

    class _FakeCoordinatorEntity:
        """Minimal stand-in for CoordinatorEntity."""

        def __init__(self, coordinator: Any) -> None:
            self.coordinator = coordinator

        def __class_getitem__(cls, _item: object) -> type:  # noqa: N804
            return cls

    ha_helpers_update_coordinator.CoordinatorEntity = _FakeCoordinatorEntity  # type: ignore[attr-defined]

    # components.sensor mock
    ha_components = types.ModuleType("homeassistant.components")
    ha_components_sensor = types.ModuleType("homeassistant.components.sensor")

    class _SensorDeviceClass:
        TEMPERATURE = "temperature"
        TIMESTAMP = "timestamp"

    class _FakeSensorEntity:
        entity_description: Any = None
        _attr_has_entity_name: bool = False
        _attr_unique_id: str = ""
        _attr_name: str = ""

        @property
        def native_value(self) -> Any:
            return None

    from dataclasses import dataclass as _dataclass

    @_dataclass(frozen=True)
    class _SensorEntityDescription:
        key: str = ""
        translation_key: str | None = None
        native_unit_of_measurement: str | None = None
        device_class: str | None = None
        entity_category: str | None = None
        suggested_display_precision: int | None = None

    ha_components_sensor.SensorDeviceClass = _SensorDeviceClass  # type: ignore[attr-defined]
    ha_components_sensor.SensorEntity = _FakeSensorEntity  # type: ignore[attr-defined]
    ha_components_sensor.SensorEntityDescription = _SensorEntityDescription  # type: ignore[attr-defined]

    # components.climate mock
    ha_components_climate = types.ModuleType("homeassistant.components.climate")

    class _FakeClimateEntity:
        _attr_has_entity_name: bool = False
        _attr_temperature_unit: str = ""
        _attr_target_temperature_step: float = 0.5
        _attr_min_temp: float = 5.0
        _attr_max_temp: float = 35.0
        _attr_unique_id: str = ""
        _attr_name: str = ""
        _attr_target_temperature: float = 21.0
        _enable_turn_on_off_backwards_compatibility: bool = False

        def async_write_ha_state(self) -> None:
            pass

    class _ClimateEntityFeature:
        TARGET_TEMPERATURE = 1
        TURN_OFF = 64
        TURN_ON = 128

        def __or__(self, other: Any) -> int:
            return int(self) | int(other)

        def __ror__(self, other: Any) -> int:
            return int(other) | int(self)

    class _HVACMode:
        HEAT = "heat"
        COOL = "cool"
        AUTO = "auto"
        OFF = "off"

    class _HVACAction:
        HEATING = "heating"
        COOLING = "cooling"
        IDLE = "idle"
        OFF = "off"

    ha_components_climate.ClimateEntity = _FakeClimateEntity  # type: ignore[attr-defined]
    ha_components_climate.ClimateEntityFeature = _ClimateEntityFeature  # type: ignore[attr-defined]
    ha_components_climate.HVACMode = _HVACMode  # type: ignore[attr-defined]
    ha_components_climate.HVACAction = _HVACAction  # type: ignore[attr-defined]

    # Inject all modules
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.const"] = ha_const
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.config_entries"] = ha_config_entries
    sys.modules["homeassistant.data_entry_flow"] = ha_data_entry_flow
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.selector"] = ha_helpers_selector
    sys.modules["homeassistant.helpers.entity_platform"] = ha_helpers_entity_platform
    sys.modules["homeassistant.helpers.update_coordinator"] = (
        ha_helpers_update_coordinator
    )
    sys.modules["homeassistant.components"] = ha_components
    sys.modules["homeassistant.components.sensor"] = ha_components_sensor
    sys.modules["homeassistant.components.climate"] = ha_components_climate

    # voluptuous mock
    vol = types.ModuleType("voluptuous")
    vol.Schema = MagicMock(side_effect=lambda x: x)  # type: ignore[attr-defined]
    vol.Required = MagicMock(side_effect=lambda key, **kw: key)  # type: ignore[attr-defined]
    vol.Optional = MagicMock(side_effect=lambda key, **kw: key)  # type: ignore[attr-defined]
    sys.modules["voluptuous"] = vol

    repo_root_str = str(_REPO_ROOT)
    path_added = repo_root_str not in sys.path
    if path_added:
        sys.path.insert(0, repo_root_str)

    # Import modules under test
    from custom_components.pumpahead.climate import (
        PumpAheadClimateEntity,
        async_setup_entry,
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
    ns.PumpAheadClimateEntity = PumpAheadClimateEntity  # type: ignore[attr-defined]
    ns.async_setup_entry = async_setup_entry  # type: ignore[attr-defined]
    ns.HVACMode = _HVACMode  # type: ignore[attr-defined]
    ns.HVACAction = _HVACAction  # type: ignore[attr-defined]

    yield ns

    # Teardown
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


def _make_coordinator_data(
    climate_mocks: Any,
    *,
    rooms: dict[str, Any] | None = None,
    algorithm_mode: str = "heating",
    algorithm_status: str = "running",
) -> Any:
    """Build a PumpAheadCoordinatorData with sensible defaults."""
    if rooms is None:
        rooms = {
            "Living Room": climate_mocks.RoomSensorData(
                room_name="Living Room",
                T_room=21.5,
                T_floor=28.0,
                valve_pos=45.0,
                humidity=55.0,
                recommended_valve=62.5,
                predicted_temp=21.5,
                live_control_enabled=False,
            ),
        }
    return climate_mocks.PumpAheadCoordinatorData(
        rooms=rooms,
        T_outdoor=5.0,
        weather_source=None,
        last_update_success=True,
        algorithm_mode=algorithm_mode,
        algorithm_status=algorithm_status,
        last_update_timestamp="2026-04-09T12:00:00+00:00",
    )


def _make_coordinator_with_data(
    climate_mocks: Any,
    data: Any | None = None,
    *,
    live_control_map: dict[str, bool] | None = None,
) -> Any:
    """Create a mock coordinator with populated data."""
    hass = MagicMock()
    hass.config.latitude = 50.06
    hass.config.longitude = 19.94

    entry = MagicMock()
    entry.data = {
        "latitude": 50.06,
        "longitude": 19.94,
        "rooms": [
            {
                "room_name": "Living Room",
                "entity_temp_room": "sensor.temp_living",
                "entity_temp_floor": "sensor.floor_living",
                "entity_valve": "number.valve_living",
                "entity_humidity": "sensor.humidity_living",
                "has_split": False,
            },
        ],
        "entity_temp_outdoor": "sensor.outdoor_temp",
        "entity_weather": "",
        "algorithm_mode": "heating",
    }
    entry.entry_id = "test_entry_id"
    entry.options = {"live_control": live_control_map or {}}

    coordinator = climate_mocks.PumpAheadCoordinator(hass, entry)
    if data is None:
        data = _make_coordinator_data(climate_mocks)
    coordinator.data = data
    return coordinator


# ---------------------------------------------------------------------------
# TestClimateEntityCreation
# ---------------------------------------------------------------------------


class TestClimateEntityCreation:
    """Tests for PumpAheadClimateEntity construction."""

    @pytest.mark.unit
    def test_unique_id_format(self, climate_mocks: Any) -> None:
        """Climate entity must have unique_id with entry_id, room slug, 'climate'."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        assert entity._attr_unique_id == "test_entry_living_room_climate"

    @pytest.mark.unit
    def test_entity_name_includes_room(self, climate_mocks: Any) -> None:
        """Climate entity name must include the room name."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Bedroom",
            has_split=True,
        )
        assert "Bedroom" in entity._attr_name
        assert "Climate" in entity._attr_name

    @pytest.mark.unit
    def test_temperature_unit_celsius(self, climate_mocks: Any) -> None:
        """Climate entity must use Celsius."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        assert entity._attr_temperature_unit == "\u00b0C"

    @pytest.mark.unit
    def test_default_target_temperature(self, climate_mocks: Any) -> None:
        """Climate entity must default to DEFAULT_SETPOINT."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        assert entity.target_temperature == 21.0


# ---------------------------------------------------------------------------
# TestClimateEntityState
# ---------------------------------------------------------------------------


class TestClimateEntityState:
    """Tests for climate entity state properties."""

    @pytest.mark.unit
    def test_hvac_modes_list(self, climate_mocks: Any) -> None:
        """Climate entity must support HEAT, COOL, AUTO, OFF."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        modes = entity.hvac_modes
        assert "heat" in modes
        assert "cool" in modes
        assert "auto" in modes
        assert "off" in modes

    @pytest.mark.unit
    def test_hvac_mode_from_algorithm_mode_heating(
        self, climate_mocks: Any
    ) -> None:
        """HVAC mode must be HEAT when algorithm_mode is 'heating'."""
        data = _make_coordinator_data(climate_mocks, algorithm_mode="heating")
        coordinator = _make_coordinator_with_data(climate_mocks, data=data)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        assert entity.hvac_mode == climate_mocks.HVACMode.HEAT

    @pytest.mark.unit
    def test_hvac_mode_from_algorithm_mode_cooling(
        self, climate_mocks: Any
    ) -> None:
        """HVAC mode must be COOL when algorithm_mode is 'cooling'."""
        data = _make_coordinator_data(climate_mocks, algorithm_mode="cooling")
        coordinator = _make_coordinator_with_data(climate_mocks, data=data)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        assert entity.hvac_mode == climate_mocks.HVACMode.COOL

    @pytest.mark.unit
    def test_hvac_mode_from_algorithm_mode_auto(self, climate_mocks: Any) -> None:
        """HVAC mode must be AUTO when algorithm_mode is 'auto'."""
        data = _make_coordinator_data(climate_mocks, algorithm_mode="auto")
        coordinator = _make_coordinator_with_data(climate_mocks, data=data)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        assert entity.hvac_mode == climate_mocks.HVACMode.AUTO

    @pytest.mark.unit
    def test_hvac_mode_off_when_no_data(self, climate_mocks: Any) -> None:
        """HVAC mode must be OFF when coordinator data is None."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        coordinator.data = None
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        assert entity.hvac_mode == climate_mocks.HVACMode.OFF

    @pytest.mark.unit
    def test_hvac_mode_user_override(self, climate_mocks: Any) -> None:
        """User-set HVAC mode must override algorithm_mode."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        # Default is derived from algorithm_mode ("heating" -> HEAT).
        assert entity.hvac_mode == climate_mocks.HVACMode.HEAT

        # User sets OFF.
        asyncio.run(entity.async_set_hvac_mode(climate_mocks.HVACMode.OFF))
        assert entity.hvac_mode == climate_mocks.HVACMode.OFF

    @pytest.mark.unit
    def test_current_temperature_from_coordinator(
        self, climate_mocks: Any
    ) -> None:
        """current_temperature must return T_room from coordinator data."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        assert entity.current_temperature == 21.5

    @pytest.mark.unit
    def test_current_temperature_none_when_no_data(
        self, climate_mocks: Any
    ) -> None:
        """current_temperature must return None when coordinator data is None."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        coordinator.data = None
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        assert entity.current_temperature is None

    @pytest.mark.unit
    def test_current_temperature_none_for_unknown_room(
        self, climate_mocks: Any
    ) -> None:
        """current_temperature must return None for a room not in data."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Nonexistent Room",
            has_split=False,
        )
        assert entity.current_temperature is None

    @pytest.mark.unit
    def test_hvac_action_heating(self, climate_mocks: Any) -> None:
        """HVAC action must be HEATING when valve is active in heating mode."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        assert entity.hvac_action == climate_mocks.HVACAction.HEATING

    @pytest.mark.unit
    def test_hvac_action_idle_when_valve_zero(self, climate_mocks: Any) -> None:
        """HVAC action must be IDLE when recommended_valve is 0."""
        rooms = {
            "Living Room": climate_mocks.RoomSensorData(
                room_name="Living Room",
                T_room=22.0,
                T_floor=28.0,
                valve_pos=0.0,
                humidity=55.0,
                recommended_valve=0.0,
                predicted_temp=22.0,
            ),
        }
        data = _make_coordinator_data(climate_mocks, rooms=rooms)
        coordinator = _make_coordinator_with_data(climate_mocks, data=data)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        assert entity.hvac_action == climate_mocks.HVACAction.IDLE

    @pytest.mark.unit
    def test_hvac_action_off_when_mode_off(self, climate_mocks: Any) -> None:
        """HVAC action must be OFF when HVAC mode is OFF."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        asyncio.run(entity.async_set_hvac_mode(climate_mocks.HVACMode.OFF))
        assert entity.hvac_action == climate_mocks.HVACAction.OFF


# ---------------------------------------------------------------------------
# TestClimateEntityExtraAttributes
# ---------------------------------------------------------------------------


class TestClimateEntityExtraAttributes:
    """Tests for extra_state_attributes."""

    @pytest.mark.unit
    def test_has_room_name(self, climate_mocks: Any) -> None:
        """Extra attributes must include room_name."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        attrs = entity.extra_state_attributes
        assert attrs["room_name"] == "Living Room"

    @pytest.mark.unit
    def test_has_split_flag(self, climate_mocks: Any) -> None:
        """Extra attributes must include has_split flag."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=True,
        )
        attrs = entity.extra_state_attributes
        assert attrs["has_split"] is True

    @pytest.mark.unit
    def test_includes_live_control_enabled(self, climate_mocks: Any) -> None:
        """Extra attributes must include live_control_enabled."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        attrs = entity.extra_state_attributes
        assert "live_control_enabled" in attrs
        assert attrs["live_control_enabled"] is False

    @pytest.mark.unit
    def test_includes_recommended_valve(self, climate_mocks: Any) -> None:
        """Extra attributes must include recommended_valve."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        attrs = entity.extra_state_attributes
        assert attrs["recommended_valve"] == 62.5

    @pytest.mark.unit
    def test_split_attributes_when_has_split(self, climate_mocks: Any) -> None:
        """Extra attributes must include split fields when has_split=True."""
        rooms = {
            "Living Room": climate_mocks.RoomSensorData(
                room_name="Living Room",
                T_room=21.5,
                T_floor=28.0,
                valve_pos=45.0,
                humidity=55.0,
                recommended_valve=62.5,
                predicted_temp=21.5,
                split_recommended_mode="heating",
                split_recommended_setpoint=21.0,
            ),
        }
        data = _make_coordinator_data(climate_mocks, rooms=rooms)
        coordinator = _make_coordinator_with_data(climate_mocks, data=data)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=True,
        )
        attrs = entity.extra_state_attributes
        assert attrs["split_recommended_mode"] == "heating"
        assert attrs["split_recommended_setpoint"] == 21.0

    @pytest.mark.unit
    def test_no_split_attributes_when_no_split(self, climate_mocks: Any) -> None:
        """Extra attributes must NOT include split fields when has_split=False."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        attrs = entity.extra_state_attributes
        assert "split_recommended_mode" not in attrs
        assert "split_recommended_setpoint" not in attrs

    @pytest.mark.unit
    def test_extra_attrs_when_no_data(self, climate_mocks: Any) -> None:
        """Extra attributes must still have room_name when coordinator data is None."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        coordinator.data = None
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        attrs = entity.extra_state_attributes
        assert attrs["room_name"] == "Living Room"
        assert "live_control_enabled" not in attrs


# ---------------------------------------------------------------------------
# TestAsyncSetupEntry
# ---------------------------------------------------------------------------


class TestAsyncSetupEntry:
    """Tests for the async_setup_entry platform function."""

    @pytest.mark.unit
    def test_creates_one_entity_per_room(self, climate_mocks: Any) -> None:
        """async_setup_entry must create one climate entity per room."""
        coordinator = _make_coordinator_with_data(climate_mocks)

        entry = MagicMock()
        entry.entry_id = "test_entry"
        entry.data = {
            "rooms": [
                {"room_name": "Living Room", "has_split": False},
            ],
        }
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = coordinator

        entities: list[Any] = []

        def capture_entities(ents: list[Any]) -> None:
            entities.extend(ents)

        hass = MagicMock()
        asyncio.run(climate_mocks.async_setup_entry(hass, entry, capture_entities))
        assert len(entities) == 1
        assert entities[0]._room_name == "Living Room"

    @pytest.mark.unit
    def test_creates_entities_for_multiple_rooms(
        self, climate_mocks: Any
    ) -> None:
        """async_setup_entry must create climate entities for all rooms."""
        rooms = {
            "Living Room": climate_mocks.RoomSensorData(
                room_name="Living Room",
                T_room=21.5,
                T_floor=28.0,
                valve_pos=45.0,
                humidity=55.0,
            ),
            "Bedroom": climate_mocks.RoomSensorData(
                room_name="Bedroom",
                T_room=20.0,
                T_floor=25.0,
                valve_pos=30.0,
                humidity=50.0,
            ),
        }
        data = _make_coordinator_data(climate_mocks, rooms=rooms)
        coordinator = _make_coordinator_with_data(climate_mocks, data=data)

        entry = MagicMock()
        entry.entry_id = "test_entry"
        entry.data = {
            "rooms": [
                {"room_name": "Living Room", "has_split": False},
                {"room_name": "Bedroom", "has_split": True},
            ],
        }
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = coordinator

        entities: list[Any] = []

        def capture_entities(ents: list[Any]) -> None:
            entities.extend(ents)

        hass = MagicMock()
        asyncio.run(climate_mocks.async_setup_entry(hass, entry, capture_entities))
        assert len(entities) == 2

    @pytest.mark.unit
    def test_no_entities_when_no_rooms(self, climate_mocks: Any) -> None:
        """async_setup_entry must create no entities when no rooms configured."""
        coordinator = _make_coordinator_with_data(climate_mocks)

        entry = MagicMock()
        entry.entry_id = "test_entry"
        entry.data = {"rooms": []}
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = coordinator

        entities: list[Any] = []

        def capture_entities(ents: list[Any]) -> None:
            entities.extend(ents)

        hass = MagicMock()
        asyncio.run(climate_mocks.async_setup_entry(hass, entry, capture_entities))
        assert len(entities) == 0


# ---------------------------------------------------------------------------
# TestAsyncSetTemperature
# ---------------------------------------------------------------------------


class TestAsyncSetTemperature:
    """Tests for async_set_temperature."""

    @pytest.mark.unit
    def test_set_target_temperature(self, climate_mocks: Any) -> None:
        """Setting temperature must update target_temperature."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        asyncio.run(entity.async_set_temperature(temperature=23.5))
        assert entity.target_temperature == 23.5

    @pytest.mark.unit
    def test_set_temperature_no_op_when_none(self, climate_mocks: Any) -> None:
        """Setting temperature with no 'temperature' key must not change it."""
        coordinator = _make_coordinator_with_data(climate_mocks)
        entity = climate_mocks.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry",
            room_name="Living Room",
            has_split=False,
        )
        asyncio.run(entity.async_set_temperature())
        assert entity.target_temperature == 21.0  # unchanged default


# ---------------------------------------------------------------------------
# TestLiveControlGuard
# ---------------------------------------------------------------------------


class TestLiveControlGuard:
    """Tests that live control is guarded by the toggle."""

    @pytest.mark.unit
    def test_live_control_disabled_by_default(self, climate_mocks: Any) -> None:
        """Rooms must default to shadow mode (live_control_enabled=False)."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94
        hass.states.get = MagicMock(return_value=None)

        entry = MagicMock()
        entry.data = {
            "latitude": 50.06,
            "longitude": 19.94,
            "rooms": [
                {
                    "room_name": "Living Room",
                    "entity_temp_room": "sensor.temp_living",
                },
            ],
            "entity_temp_outdoor": "",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"
        entry.options = {}

        coordinator = climate_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        room = data.rooms["Living Room"]
        assert room.live_control_enabled is False

    @pytest.mark.unit
    def test_live_control_enabled_from_options(self, climate_mocks: Any) -> None:
        """Rooms with live_control=True in options have live_control_enabled."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94

        def _states_get(entity_id: str) -> MagicMock:
            state = MagicMock()
            state.state = "21.0"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_get)

        entry = MagicMock()
        entry.data = {
            "latitude": 50.06,
            "longitude": 19.94,
            "rooms": [
                {
                    "room_name": "Living Room",
                    "entity_temp_room": "sensor.temp_living",
                    "entity_valve": "number.valve_living",
                },
            ],
            "entity_temp_outdoor": "",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"
        entry.options = {"live_control": {"Living Room": True}}

        coordinator = climate_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        room = data.rooms["Living Room"]
        assert room.live_control_enabled is True

    @pytest.mark.unit
    def test_valve_service_called_when_live(self, climate_mocks: Any) -> None:
        """Coordinator must call number.set_value when live control is enabled."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94
        hass.services.async_call = AsyncMock()

        def _states_get(entity_id: str) -> MagicMock:
            state = MagicMock()
            if "temp_living" in entity_id:
                state.state = "20.0"  # below setpoint -> PID gives > 0
            else:
                state.state = "5.0"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_get)

        entry = MagicMock()
        entry.data = {
            "latitude": 50.06,
            "longitude": 19.94,
            "rooms": [
                {
                    "room_name": "Living Room",
                    "entity_temp_room": "sensor.temp_living",
                    "entity_valve": "number.valve_living",
                    "has_split": False,
                },
            ],
            "entity_temp_outdoor": "sensor.outdoor_temp",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"
        entry.options = {"live_control": {"Living Room": True}}

        coordinator = climate_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        asyncio.run(coordinator._async_update_data())

        # Verify number.set_value was called.
        calls = hass.services.async_call.call_args_list
        valve_calls = [
            c for c in calls if c[0][0] == "number" and c[0][1] == "set_value"
        ]
        assert len(valve_calls) == 1
        assert valve_calls[0][0][2]["entity_id"] == "number.valve_living"
        assert valve_calls[0][0][2]["value"] > 0

    @pytest.mark.unit
    def test_no_valve_service_when_shadow(self, climate_mocks: Any) -> None:
        """Coordinator must NOT call number.set_value when live control is disabled."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94
        hass.services.async_call = AsyncMock()

        def _states_get(entity_id: str) -> MagicMock:
            state = MagicMock()
            state.state = "20.0"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_get)

        entry = MagicMock()
        entry.data = {
            "latitude": 50.06,
            "longitude": 19.94,
            "rooms": [
                {
                    "room_name": "Living Room",
                    "entity_temp_room": "sensor.temp_living",
                    "entity_valve": "number.valve_living",
                    "has_split": False,
                },
            ],
            "entity_temp_outdoor": "sensor.outdoor_temp",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"
        entry.options = {}  # No live control

        coordinator = climate_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        asyncio.run(coordinator._async_update_data())

        # Verify no number.set_value calls.
        hass.services.async_call.assert_not_called()

    @pytest.mark.unit
    def test_split_service_called_when_live_with_split(
        self, climate_mocks: Any
    ) -> None:
        """Coordinator must call climate.set_hvac_mode when live control + split."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94
        hass.services.async_call = AsyncMock()

        def _states_get(entity_id: str) -> MagicMock:
            state = MagicMock()
            if "temp_living" in entity_id:
                state.state = "19.0"  # below setpoint by >0.5 -> split activates
            else:
                state.state = "5.0"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_get)

        entry = MagicMock()
        entry.data = {
            "latitude": 50.06,
            "longitude": 19.94,
            "rooms": [
                {
                    "room_name": "Living Room",
                    "entity_temp_room": "sensor.temp_living",
                    "entity_valve": "number.valve_living",
                    "has_split": True,
                    "entity_split": "climate.split_living",
                },
            ],
            "entity_temp_outdoor": "sensor.outdoor_temp",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"
        entry.options = {"live_control": {"Living Room": True}}

        coordinator = climate_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        asyncio.run(coordinator._async_update_data())

        calls = hass.services.async_call.call_args_list
        hvac_calls = [
            c
            for c in calls
            if c[0][0] == "climate" and c[0][1] == "set_hvac_mode"
        ]
        assert len(hvac_calls) == 1
        assert hvac_calls[0][0][2]["entity_id"] == "climate.split_living"
        assert hvac_calls[0][0][2]["hvac_mode"] == "heat"

    @pytest.mark.unit
    def test_no_valve_service_when_temp_unavailable(
        self, climate_mocks: Any
    ) -> None:
        """Coordinator must skip live control when room T_room is None."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94
        hass.services.async_call = AsyncMock()

        # All entities return None (unavailable).
        hass.states.get = MagicMock(return_value=None)

        entry = MagicMock()
        entry.data = {
            "latitude": 50.06,
            "longitude": 19.94,
            "rooms": [
                {
                    "room_name": "Living Room",
                    "entity_temp_room": "sensor.temp_living",
                    "entity_valve": "number.valve_living",
                    "has_split": False,
                },
            ],
            "entity_temp_outdoor": "",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"
        entry.options = {"live_control": {"Living Room": True}}

        coordinator = climate_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        asyncio.run(coordinator._async_update_data())

        # No service calls because T_room is None -> recommended_valve is None.
        hass.services.async_call.assert_not_called()


# ---------------------------------------------------------------------------
# TestSplitRecommendations
# ---------------------------------------------------------------------------


class TestSplitRecommendations:
    """Tests for split recommendation computation."""

    @pytest.mark.unit
    def test_split_heating_when_error_positive(self, climate_mocks: Any) -> None:
        """Split must recommend 'heating' when error > 0.5 in heating mode."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94

        def _states_get(entity_id: str) -> MagicMock:
            state = MagicMock()
            if "temp_living" in entity_id:
                state.state = "19.0"  # error = 21.0 - 19.0 = 2.0
            else:
                state.state = "5.0"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_get)

        entry = MagicMock()
        entry.data = {
            "latitude": 50.06,
            "longitude": 19.94,
            "rooms": [
                {
                    "room_name": "Living Room",
                    "entity_temp_room": "sensor.temp_living",
                    "has_split": True,
                },
            ],
            "entity_temp_outdoor": "sensor.outdoor_temp",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"
        entry.options = {}

        coordinator = climate_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        room = data.rooms["Living Room"]
        assert room.split_recommended_mode == "heating"
        assert room.split_recommended_setpoint == 21.0

    @pytest.mark.unit
    def test_split_off_when_error_small(self, climate_mocks: Any) -> None:
        """Split must recommend 'off' when error < 0.5 in heating mode."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94

        def _states_get(entity_id: str) -> MagicMock:
            state = MagicMock()
            if "temp_living" in entity_id:
                state.state = "20.8"  # error = 21.0 - 20.8 = 0.2 < 0.5
            else:
                state.state = "5.0"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_get)

        entry = MagicMock()
        entry.data = {
            "latitude": 50.06,
            "longitude": 19.94,
            "rooms": [
                {
                    "room_name": "Living Room",
                    "entity_temp_room": "sensor.temp_living",
                    "has_split": True,
                },
            ],
            "entity_temp_outdoor": "sensor.outdoor_temp",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"
        entry.options = {}

        coordinator = climate_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        room = data.rooms["Living Room"]
        assert room.split_recommended_mode == "off"
        assert room.split_recommended_setpoint is None

    @pytest.mark.unit
    def test_split_no_recommendation_without_split(
        self, climate_mocks: Any
    ) -> None:
        """Room without split must have None split recommendations."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94

        def _states_get(entity_id: str) -> MagicMock:
            state = MagicMock()
            state.state = "19.0"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_get)

        entry = MagicMock()
        entry.data = {
            "latitude": 50.06,
            "longitude": 19.94,
            "rooms": [
                {
                    "room_name": "Living Room",
                    "entity_temp_room": "sensor.temp_living",
                    "has_split": False,
                },
            ],
            "entity_temp_outdoor": "sensor.outdoor_temp",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"
        entry.options = {}

        coordinator = climate_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        room = data.rooms["Living Room"]
        assert room.split_recommended_mode is None
        assert room.split_recommended_setpoint is None

    @pytest.mark.unit
    def test_split_cooling_in_cooling_mode(self, climate_mocks: Any) -> None:
        """Split must recommend 'cooling' when error < -0.5 in cooling mode."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94

        def _states_get(entity_id: str) -> MagicMock:
            state = MagicMock()
            if "temp_living" in entity_id:
                state.state = "23.0"  # error = 21.0 - 23.0 = -2.0
            else:
                state.state = "30.0"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_get)

        entry = MagicMock()
        entry.data = {
            "latitude": 50.06,
            "longitude": 19.94,
            "rooms": [
                {
                    "room_name": "Living Room",
                    "entity_temp_room": "sensor.temp_living",
                    "has_split": True,
                },
            ],
            "entity_temp_outdoor": "sensor.outdoor_temp",
            "entity_weather": "",
            "algorithm_mode": "cooling",
        }
        entry.entry_id = "test_entry_id"
        entry.options = {}

        coordinator = climate_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        room = data.rooms["Living Room"]
        assert room.split_recommended_mode == "cooling"
        assert room.split_recommended_setpoint == 21.0

    @pytest.mark.unit
    def test_axiom3_no_cooling_in_heating_mode(
        self, climate_mocks: Any
    ) -> None:
        """Axiom 3: no 'cooling' recommendation in 'heating' mode."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94

        def _states_get(entity_id: str) -> MagicMock:
            state = MagicMock()
            if "temp_living" in entity_id:
                state.state = "23.0"  # error = 21.0 - 23.0 = -2.0 (overshooting)
            else:
                state.state = "5.0"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_get)

        entry = MagicMock()
        entry.data = {
            "latitude": 50.06,
            "longitude": 19.94,
            "rooms": [
                {
                    "room_name": "Living Room",
                    "entity_temp_room": "sensor.temp_living",
                    "has_split": True,
                },
            ],
            "entity_temp_outdoor": "sensor.outdoor_temp",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"
        entry.options = {}

        coordinator = climate_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        room = data.rooms["Living Room"]
        # Axiom 3: In heating mode with negative error, split should be off
        assert room.split_recommended_mode == "off"
        assert room.split_recommended_setpoint is None
