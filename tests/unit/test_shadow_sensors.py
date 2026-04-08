"""Tests for PumpAhead shadow mode diagnostic sensors.

Uses the same module-scoped mocking pattern as ``test_coordinator.py``
and ``test_ha_scaffold.py`` to inject mock ``homeassistant`` modules
into ``sys.modules``, import the sensor module, run tests, and clean up.
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
def sensor_mocks() -> Any:  # noqa: C901
    """Set up mock HA modules, import sensor module, yield, clean up."""
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
        CELSIUS = "°C"

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

    ha_config_entries.ConfigFlow = _FakeConfigFlow  # type: ignore[attr-defined]

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
        """Minimal stand-in for SensorEntity."""

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
    from custom_components.pumpahead.coordinator import (
        PumpAheadCoordinator,
        PumpAheadCoordinatorData,
        RoomSensorData,
    )
    from custom_components.pumpahead.sensor import (
        GLOBAL_SENSORS,
        ROOM_SENSORS,
        PumpAheadSensorEntity,
        PumpAheadSensorEntityDescription,
        async_setup_entry,
    )

    class _Namespace:
        pass

    ns = _Namespace()
    ns.PumpAheadCoordinator = PumpAheadCoordinator  # type: ignore[attr-defined]
    ns.PumpAheadCoordinatorData = PumpAheadCoordinatorData  # type: ignore[attr-defined]
    ns.RoomSensorData = RoomSensorData  # type: ignore[attr-defined]
    ns.PumpAheadSensorEntity = PumpAheadSensorEntity  # type: ignore[attr-defined]
    ns.PumpAheadSensorEntityDescription = PumpAheadSensorEntityDescription  # type: ignore[attr-defined]
    ns.ROOM_SENSORS = ROOM_SENSORS  # type: ignore[attr-defined]
    ns.GLOBAL_SENSORS = GLOBAL_SENSORS  # type: ignore[attr-defined]
    ns.async_setup_entry = async_setup_entry  # type: ignore[attr-defined]

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
    sensor_mocks: Any,
    *,
    rooms: dict[str, Any] | None = None,
    algorithm_status: str = "running",
    last_update_timestamp: str | None = "2026-04-09T12:00:00+00:00",
) -> Any:
    """Build a PumpAheadCoordinatorData with sensible defaults."""
    if rooms is None:
        rooms = {
            "Living Room": sensor_mocks.RoomSensorData(
                room_name="Living Room",
                T_room=21.5,
                T_floor=28.0,
                valve_pos=45.0,
                humidity=55.0,
                recommended_valve=62.5,
                predicted_temp=21.5,
            ),
        }
    return sensor_mocks.PumpAheadCoordinatorData(
        rooms=rooms,
        T_outdoor=5.0,
        weather_source=None,
        last_update_success=True,
        algorithm_mode="heating",
        algorithm_status=algorithm_status,
        last_update_timestamp=last_update_timestamp,
    )


def _make_coordinator_with_data(
    sensor_mocks: Any,
    data: Any | None = None,
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
            },
        ],
        "entity_temp_outdoor": "sensor.outdoor_temp",
        "entity_weather": "",
        "algorithm_mode": "heating",
    }
    entry.entry_id = "test_entry_id"

    coordinator = sensor_mocks.PumpAheadCoordinator(hass, entry)
    if data is None:
        data = _make_coordinator_data(sensor_mocks)
    coordinator.data = data
    return coordinator


# ---------------------------------------------------------------------------
# TestSensorDescriptions
# ---------------------------------------------------------------------------


class TestSensorDescriptions:
    """Tests for sensor description tuples."""

    @pytest.mark.unit
    def test_room_sensors_count(self, sensor_mocks: Any) -> None:
        """There must be exactly 2 per-room sensor descriptions."""
        assert len(sensor_mocks.ROOM_SENSORS) == 2

    @pytest.mark.unit
    def test_global_sensors_count(self, sensor_mocks: Any) -> None:
        """There must be exactly 2 global sensor descriptions."""
        assert len(sensor_mocks.GLOBAL_SENSORS) == 2

    @pytest.mark.unit
    def test_room_sensor_keys(self, sensor_mocks: Any) -> None:
        """Per-room sensors must have correct keys."""
        keys = {desc.key for desc in sensor_mocks.ROOM_SENSORS}
        assert keys == {"recommended_valve", "predicted_temp"}

    @pytest.mark.unit
    def test_global_sensor_keys(self, sensor_mocks: Any) -> None:
        """Global sensors must have correct keys."""
        keys = {desc.key for desc in sensor_mocks.GLOBAL_SENSORS}
        assert keys == {"algorithm_status", "last_update"}

    @pytest.mark.unit
    def test_room_sensors_are_diagnostic(self, sensor_mocks: Any) -> None:
        """All per-room sensors must have entity_category DIAGNOSTIC."""
        for desc in sensor_mocks.ROOM_SENSORS:
            assert desc.entity_category == "diagnostic"

    @pytest.mark.unit
    def test_global_sensors_are_diagnostic(self, sensor_mocks: Any) -> None:
        """All global sensors must have entity_category DIAGNOSTIC."""
        for desc in sensor_mocks.GLOBAL_SENSORS:
            assert desc.entity_category == "diagnostic"

    @pytest.mark.unit
    def test_recommended_valve_unit(self, sensor_mocks: Any) -> None:
        """recommended_valve must have unit '%'."""
        desc = next(
            d for d in sensor_mocks.ROOM_SENSORS if d.key == "recommended_valve"
        )
        assert desc.native_unit_of_measurement == "%"

    @pytest.mark.unit
    def test_predicted_temp_device_class(self, sensor_mocks: Any) -> None:
        """predicted_temp must have device_class TEMPERATURE."""
        desc = next(
            d for d in sensor_mocks.ROOM_SENSORS if d.key == "predicted_temp"
        )
        assert desc.device_class == "temperature"

    @pytest.mark.unit
    def test_last_update_device_class(self, sensor_mocks: Any) -> None:
        """last_update must have device_class TIMESTAMP."""
        desc = next(
            d for d in sensor_mocks.GLOBAL_SENSORS if d.key == "last_update"
        )
        assert desc.device_class == "timestamp"


# ---------------------------------------------------------------------------
# TestSensorEntityCreation
# ---------------------------------------------------------------------------


class TestSensorEntityCreation:
    """Tests for PumpAheadSensorEntity construction."""

    @pytest.mark.unit
    def test_per_room_entity_unique_id(self, sensor_mocks: Any) -> None:
        """Per-room entity must have unique_id with entry_id, room slug, key."""
        coordinator = _make_coordinator_with_data(sensor_mocks)
        desc = sensor_mocks.ROOM_SENSORS[0]  # recommended_valve
        entity = sensor_mocks.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            room_name="Living Room",
        )
        assert entity._attr_unique_id == "test_entry_living_room_recommended_valve"

    @pytest.mark.unit
    def test_global_entity_unique_id(self, sensor_mocks: Any) -> None:
        """Global entity must have unique_id with entry_id and key."""
        coordinator = _make_coordinator_with_data(sensor_mocks)
        desc = sensor_mocks.GLOBAL_SENSORS[0]  # algorithm_status
        entity = sensor_mocks.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            room_name=None,
        )
        assert entity._attr_unique_id == "test_entry_algorithm_status"

    @pytest.mark.unit
    def test_per_room_entity_name(self, sensor_mocks: Any) -> None:
        """Per-room entity must include room name in its name."""
        coordinator = _make_coordinator_with_data(sensor_mocks)
        desc = sensor_mocks.ROOM_SENSORS[0]  # recommended_valve
        entity = sensor_mocks.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            room_name="Living Room",
        )
        assert "Living Room" in entity._attr_name
        assert "recommended" in entity._attr_name

    @pytest.mark.unit
    def test_global_entity_name(self, sensor_mocks: Any) -> None:
        """Global entity must include PumpAhead in its name."""
        coordinator = _make_coordinator_with_data(sensor_mocks)
        desc = sensor_mocks.GLOBAL_SENSORS[0]  # algorithm_status
        entity = sensor_mocks.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            room_name=None,
        )
        assert "PumpAhead" in entity._attr_name


# ---------------------------------------------------------------------------
# TestSensorValues
# ---------------------------------------------------------------------------


class TestSensorValues:
    """Tests for sensor native_value extraction."""

    @pytest.mark.unit
    def test_recommended_valve_value(self, sensor_mocks: Any) -> None:
        """recommended_valve must return the value from coordinator data."""
        coordinator = _make_coordinator_with_data(sensor_mocks)
        desc = next(
            d for d in sensor_mocks.ROOM_SENSORS if d.key == "recommended_valve"
        )
        entity = sensor_mocks.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            room_name="Living Room",
        )
        assert entity.native_value == 62.5

    @pytest.mark.unit
    def test_predicted_temp_value(self, sensor_mocks: Any) -> None:
        """predicted_temp must return the value from coordinator data."""
        coordinator = _make_coordinator_with_data(sensor_mocks)
        desc = next(
            d for d in sensor_mocks.ROOM_SENSORS if d.key == "predicted_temp"
        )
        entity = sensor_mocks.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            room_name="Living Room",
        )
        assert entity.native_value == 21.5

    @pytest.mark.unit
    def test_algorithm_status_value(self, sensor_mocks: Any) -> None:
        """algorithm_status must return the status string."""
        coordinator = _make_coordinator_with_data(sensor_mocks)
        desc = next(
            d for d in sensor_mocks.GLOBAL_SENSORS if d.key == "algorithm_status"
        )
        entity = sensor_mocks.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            room_name=None,
        )
        assert entity.native_value == "running"

    @pytest.mark.unit
    def test_last_update_value(self, sensor_mocks: Any) -> None:
        """last_update must return the ISO timestamp."""
        coordinator = _make_coordinator_with_data(sensor_mocks)
        desc = next(
            d for d in sensor_mocks.GLOBAL_SENSORS if d.key == "last_update"
        )
        entity = sensor_mocks.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            room_name=None,
        )
        assert entity.native_value == "2026-04-09T12:00:00+00:00"

    @pytest.mark.unit
    def test_native_value_none_when_coordinator_data_is_none(
        self, sensor_mocks: Any
    ) -> None:
        """native_value must return None when coordinator.data is None."""
        coordinator = _make_coordinator_with_data(sensor_mocks)
        coordinator.data = None
        desc = sensor_mocks.ROOM_SENSORS[0]
        entity = sensor_mocks.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            room_name="Living Room",
        )
        assert entity.native_value is None

    @pytest.mark.unit
    def test_native_value_none_for_unknown_room(self, sensor_mocks: Any) -> None:
        """native_value must return None for a room not in coordinator data."""
        coordinator = _make_coordinator_with_data(sensor_mocks)
        desc = sensor_mocks.ROOM_SENSORS[0]  # recommended_valve
        entity = sensor_mocks.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            room_name="Nonexistent Room",
        )
        assert entity.native_value is None

    @pytest.mark.unit
    def test_algorithm_status_error(self, sensor_mocks: Any) -> None:
        """algorithm_status must reflect 'error' status."""
        data = _make_coordinator_data(sensor_mocks, algorithm_status="error")
        coordinator = _make_coordinator_with_data(sensor_mocks, data=data)
        desc = next(
            d for d in sensor_mocks.GLOBAL_SENSORS if d.key == "algorithm_status"
        )
        entity = sensor_mocks.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            room_name=None,
        )
        assert entity.native_value == "error"

    @pytest.mark.unit
    def test_algorithm_status_stale(self, sensor_mocks: Any) -> None:
        """algorithm_status must reflect 'stale' status."""
        data = _make_coordinator_data(sensor_mocks, algorithm_status="stale")
        coordinator = _make_coordinator_with_data(sensor_mocks, data=data)
        desc = next(
            d for d in sensor_mocks.GLOBAL_SENSORS if d.key == "algorithm_status"
        )
        entity = sensor_mocks.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            room_name=None,
        )
        assert entity.native_value == "stale"


# ---------------------------------------------------------------------------
# TestAsyncSetupEntry
# ---------------------------------------------------------------------------


class TestAsyncSetupEntry:
    """Tests for the async_setup_entry platform function."""

    @pytest.mark.unit
    def test_creates_per_room_and_global_entities(self, sensor_mocks: Any) -> None:
        """async_setup_entry must create per-room + global entities."""
        coordinator = _make_coordinator_with_data(sensor_mocks)

        entry = MagicMock()
        entry.entry_id = "test_entry"
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = coordinator

        entities: list[Any] = []

        def capture_entities(ents: list[Any]) -> None:
            entities.extend(ents)

        hass = MagicMock()
        asyncio.run(
            sensor_mocks.async_setup_entry(hass, entry, capture_entities)
        )

        # 1 room * 2 room sensors + 2 global sensors = 4
        assert len(entities) == 4

    @pytest.mark.unit
    def test_creates_entities_for_multiple_rooms(self, sensor_mocks: Any) -> None:
        """async_setup_entry must create sensors for all rooms."""
        rooms = {
            "Living Room": sensor_mocks.RoomSensorData(
                room_name="Living Room",
                T_room=21.5,
                T_floor=28.0,
                valve_pos=45.0,
                humidity=55.0,
                recommended_valve=62.5,
                predicted_temp=21.5,
            ),
            "Bedroom": sensor_mocks.RoomSensorData(
                room_name="Bedroom",
                T_room=20.0,
                T_floor=25.0,
                valve_pos=30.0,
                humidity=50.0,
                recommended_valve=75.0,
                predicted_temp=20.0,
            ),
        }
        data = _make_coordinator_data(sensor_mocks, rooms=rooms)
        coordinator = _make_coordinator_with_data(sensor_mocks, data=data)

        entry = MagicMock()
        entry.entry_id = "test_entry"
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = coordinator

        entities: list[Any] = []

        def capture_entities(ents: list[Any]) -> None:
            entities.extend(ents)

        hass = MagicMock()
        asyncio.run(
            sensor_mocks.async_setup_entry(hass, entry, capture_entities)
        )

        # 2 rooms * 2 room sensors + 2 global sensors = 6
        assert len(entities) == 6

    @pytest.mark.unit
    def test_creates_only_global_when_no_rooms(self, sensor_mocks: Any) -> None:
        """async_setup_entry must create only global sensors when no rooms."""
        data = _make_coordinator_data(sensor_mocks, rooms={})
        coordinator = _make_coordinator_with_data(sensor_mocks, data=data)

        entry = MagicMock()
        entry.entry_id = "test_entry"
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = coordinator

        entities: list[Any] = []

        def capture_entities(ents: list[Any]) -> None:
            entities.extend(ents)

        hass = MagicMock()
        asyncio.run(
            sensor_mocks.async_setup_entry(hass, entry, capture_entities)
        )

        # Only 2 global sensors
        assert len(entities) == 2


# ---------------------------------------------------------------------------
# TestShadowModeReadOnly
# ---------------------------------------------------------------------------


class TestShadowModeReadOnly:
    """Tests that shadow mode is strictly read-only."""

    @pytest.mark.unit
    def test_no_service_calls_in_sensor_module(self, sensor_mocks: Any) -> None:
        """sensor.py must not contain hass.services.async_call."""
        sensor_path = _REPO_ROOT / "custom_components" / "pumpahead" / "sensor.py"
        source = sensor_path.read_text(encoding="utf-8")
        assert "async_call" not in source
        assert "services.call" not in source

    @pytest.mark.unit
    def test_no_service_calls_in_coordinator_pid(self, sensor_mocks: Any) -> None:
        """Shadow PID in coordinator must not call any HA services."""
        coord_path = _REPO_ROOT / "custom_components" / "pumpahead" / "coordinator.py"
        source = coord_path.read_text(encoding="utf-8")
        # The only async_call should be in the weather update, not PID.
        # Check that _run_shadow_pid method doesn't contain service calls.
        pid_section_start = source.find("def _run_shadow_pid")
        pid_section_end = source.find("def _read_float_state")
        assert pid_section_start > 0
        assert pid_section_end > pid_section_start
        pid_section = source[pid_section_start:pid_section_end]
        assert "async_call" not in pid_section
        assert "services" not in pid_section


# ---------------------------------------------------------------------------
# TestCoordinatorPIDIntegration
# ---------------------------------------------------------------------------


class TestCoordinatorPIDIntegration:
    """Tests for PID computation in the coordinator."""

    @pytest.mark.unit
    def test_pid_controllers_created(self, sensor_mocks: Any) -> None:
        """Coordinator must create a PID controller per room."""
        coordinator = _make_coordinator_with_data(sensor_mocks)
        assert "Living Room" in coordinator._pid_controllers
        assert len(coordinator._pid_controllers) == 1

    @pytest.mark.unit
    def test_update_populates_recommended_valve(self, sensor_mocks: Any) -> None:
        """After _async_update_data, rooms must have recommended_valve."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94

        def _states_get(entity_id: str) -> MagicMock:
            state = MagicMock()
            if "temp_living" in entity_id:
                state.state = "20.0"
            elif "floor_living" in entity_id:
                state.state = "27.0"
            elif "valve_living" in entity_id:
                state.state = "40.0"
            elif "humidity_living" in entity_id:
                state.state = "50.0"
            elif "outdoor_temp" in entity_id:
                state.state = "5.0"
            else:
                state.state = "unknown"
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
                    "entity_temp_floor": "sensor.floor_living",
                    "entity_valve": "number.valve_living",
                    "entity_humidity": "sensor.humidity_living",
                },
            ],
            "entity_temp_outdoor": "sensor.outdoor_temp",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"

        coordinator = sensor_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())

        room = data.rooms["Living Room"]
        # T_room=20.0, setpoint=21.0, error=1.0 -> PID output > 0
        assert room.recommended_valve is not None
        assert room.recommended_valve > 0.0
        assert room.recommended_valve <= 100.0

    @pytest.mark.unit
    def test_update_populates_predicted_temp(self, sensor_mocks: Any) -> None:
        """After _async_update_data, rooms must have predicted_temp."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94

        def _states_get(entity_id: str) -> MagicMock:
            state = MagicMock()
            if "temp_living" in entity_id:
                state.state = "21.5"
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
                },
            ],
            "entity_temp_outdoor": "sensor.outdoor_temp",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"

        coordinator = sensor_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())

        room = data.rooms["Living Room"]
        # Predicted temp echoes current T_room.
        assert room.predicted_temp == 21.5

    @pytest.mark.unit
    def test_status_running_when_all_rooms_have_data(
        self, sensor_mocks: Any
    ) -> None:
        """algorithm_status must be 'running' when all rooms have T_room."""
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
                },
            ],
            "entity_temp_outdoor": "sensor.outdoor_temp",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"

        coordinator = sensor_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        assert data.algorithm_status == "running"

    @pytest.mark.unit
    def test_status_stale_when_all_rooms_have_none_temp(
        self, sensor_mocks: Any
    ) -> None:
        """algorithm_status must be 'stale' when all rooms have None T_room."""
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

        coordinator = sensor_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        assert data.algorithm_status == "stale"

    @pytest.mark.unit
    def test_status_stale_when_some_rooms_have_none_temp(
        self, sensor_mocks: Any
    ) -> None:
        """algorithm_status must be 'stale' when some rooms lack T_room."""
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94

        def _states_get(entity_id: str) -> MagicMock:
            state = MagicMock()
            if "temp_living" in entity_id:
                state.state = "21.0"
            else:
                return None  # type: ignore[return-value]
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
                },
                {
                    "room_name": "Bedroom",
                    "entity_temp_room": "sensor.temp_bedroom",
                },
            ],
            "entity_temp_outdoor": "",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"

        coordinator = sensor_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        assert data.algorithm_status == "stale"

    @pytest.mark.unit
    def test_has_last_update_timestamp(self, sensor_mocks: Any) -> None:
        """Coordinator data must contain a last_update_timestamp."""
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
                },
            ],
            "entity_temp_outdoor": "sensor.outdoor_temp",
            "entity_weather": "",
            "algorithm_mode": "heating",
        }
        entry.entry_id = "test_entry_id"

        coordinator = sensor_mocks.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        assert data.last_update_timestamp is not None
        assert "T" in data.last_update_timestamp  # ISO 8601 format
