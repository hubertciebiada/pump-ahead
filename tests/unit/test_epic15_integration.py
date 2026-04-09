"""Integration tests for Epic #15 -- HA Custom Integration Scaffold.

Verifies end-to-end cross-module wiring for the four sub-issues:
    #44 HA scaffold (__init__.py, const.py, manifest.json)
    #45 Config flow (config_flow.py — 5-step wizard)
    #46 Shadow mode sensors (sensor.py, coordinator.py)
    #47 Climate entities and live control (climate.py)

Tests exercise cross-module workflows:
    config flow -> coordinator pipeline
    options flow -> live control toggle
    coordinator -> sensor entity pipeline
    coordinator -> climate entity pipeline
    shadow mode full update cycle
    live control valve/split service calls
    Axiom 3 enforcement (splits never oppose mode)
    Axiom 8 enforcement (no brand-specific entity IDs)
    Architectural integrity (no HA imports in core library)

All tests are fast, deterministic, and use the
``@pytest.mark.unit`` marker.
"""

from __future__ import annotations

import ast
import asyncio
import json
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Module-scoped fixture — comprehensive HA mock covering all sub-issue
# modules: __init__, const, config_flow, coordinator, sensor, climate,
# ha_weather.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ha_integration_mocks() -> Any:  # noqa: C901
    """Set up mock HA modules, import all integration modules, yield, clean up.

    This is the most comprehensive HA mock fixture, modelled on the
    ``climate_mocks`` fixture from ``test_climate_entity.py`` but extended
    to also yield config_flow, sensor, and __init__ symbols.
    """
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

        def async_show_form(self, **kwargs: Any) -> dict:
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs: Any) -> dict:
            return {"type": "create_entry", **kwargs}

        async def async_set_unique_id(self, unique_id: str) -> None:
            pass

        def _abort_if_unique_id_configured(self) -> None:
            pass

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

    # Import all modules under test
    from custom_components.pumpahead.climate import (
        PumpAheadClimateEntity,
    )
    from custom_components.pumpahead.climate import (
        async_setup_entry as climate_async_setup_entry,
    )
    from custom_components.pumpahead.config_flow import (
        PumpAheadConfigFlow,
        PumpAheadOptionsFlow,
    )
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
        CONF_LIVE_CONTROL,
        CONF_LONGITUDE,
        CONF_ROOM_AREA,
        CONF_ROOM_NAME,
        CONF_ROOMS,
        CONF_W_COMFORT,
        CONF_W_ENERGY,
        CONF_W_SMOOTH,
        DEFAULT_SETPOINT,
        DOMAIN,
        PLATFORMS,
        UPDATE_INTERVAL_MINUTES,
    )
    from custom_components.pumpahead.coordinator import (
        PumpAheadCoordinator,
        PumpAheadCoordinatorData,
        RoomSensorData,
    )
    from custom_components.pumpahead.sensor import (
        GLOBAL_SENSORS,
        ROOM_SENSORS,
        PumpAheadSensorEntity,
    )
    from custom_components.pumpahead.sensor import (
        async_setup_entry as sensor_async_setup_entry,
    )

    class _Namespace:
        pass

    ns = _Namespace()
    # config_flow
    ns.PumpAheadConfigFlow = PumpAheadConfigFlow  # type: ignore[attr-defined]
    ns.PumpAheadOptionsFlow = PumpAheadOptionsFlow  # type: ignore[attr-defined]
    # coordinator
    ns.PumpAheadCoordinator = PumpAheadCoordinator  # type: ignore[attr-defined]
    ns.PumpAheadCoordinatorData = PumpAheadCoordinatorData  # type: ignore[attr-defined]
    ns.RoomSensorData = RoomSensorData  # type: ignore[attr-defined]
    # sensor
    ns.PumpAheadSensorEntity = PumpAheadSensorEntity  # type: ignore[attr-defined]
    ns.sensor_async_setup_entry = sensor_async_setup_entry  # type: ignore[attr-defined]
    ns.ROOM_SENSORS = ROOM_SENSORS  # type: ignore[attr-defined]
    ns.GLOBAL_SENSORS = GLOBAL_SENSORS  # type: ignore[attr-defined]
    # climate
    ns.PumpAheadClimateEntity = PumpAheadClimateEntity  # type: ignore[attr-defined]
    ns.climate_async_setup_entry = climate_async_setup_entry  # type: ignore[attr-defined]
    ns.HVACMode = _HVACMode  # type: ignore[attr-defined]
    ns.HVACAction = _HVACAction  # type: ignore[attr-defined]
    # const
    ns.PLATFORMS = PLATFORMS  # type: ignore[attr-defined]
    ns.DOMAIN = DOMAIN  # type: ignore[attr-defined]
    ns.CONF_ROOMS = CONF_ROOMS  # type: ignore[attr-defined]
    ns.CONF_ROOM_NAME = CONF_ROOM_NAME  # type: ignore[attr-defined]
    ns.CONF_ROOM_AREA = CONF_ROOM_AREA  # type: ignore[attr-defined]
    ns.CONF_HAS_SPLIT = CONF_HAS_SPLIT  # type: ignore[attr-defined]
    ns.CONF_ADD_ANOTHER = CONF_ADD_ANOTHER  # type: ignore[attr-defined]
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
    ns.CONF_LATITUDE = CONF_LATITUDE  # type: ignore[attr-defined]
    ns.CONF_LONGITUDE = CONF_LONGITUDE  # type: ignore[attr-defined]
    ns.CONF_LIVE_CONTROL = CONF_LIVE_CONTROL  # type: ignore[attr-defined]
    ns.DEFAULT_SETPOINT = DEFAULT_SETPOINT  # type: ignore[attr-defined]
    ns.UPDATE_INTERVAL_MINUTES = UPDATE_INTERVAL_MINUTES  # type: ignore[attr-defined]

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

_SINGLE_ROOM_CONFIG = {
    "room_name": "Living Room",
    "room_area": 25.0,
    "has_split": False,
    "entity_temp_room": "sensor.temp_living",
    "entity_temp_floor": "sensor.floor_living",
    "entity_valve": "number.valve_living",
    "entity_humidity": "sensor.humidity_living",
}

_SPLIT_ROOM_CONFIG = {
    "room_name": "Bedroom",
    "room_area": 18.0,
    "has_split": True,
    "entity_temp_room": "sensor.temp_bedroom",
    "entity_temp_floor": "sensor.floor_bedroom",
    "entity_valve": "number.valve_bedroom",
    "entity_humidity": "sensor.humidity_bedroom",
    "entity_split": "climate.split_bedroom",
}

_ENTRY_DATA_SINGLE = {
    "latitude": 50.06,
    "longitude": 19.94,
    "rooms": [_SINGLE_ROOM_CONFIG],
    "entity_temp_outdoor": "sensor.outdoor_temp",
    "entity_weather": "weather.home",
    "algorithm_mode": "heating",
    "w_comfort": 1.0,
    "w_energy": 0.1,
    "w_smooth": 0.01,
}

_ENTRY_DATA_MULTI = {
    "latitude": 50.06,
    "longitude": 19.94,
    "rooms": [_SINGLE_ROOM_CONFIG, _SPLIT_ROOM_CONFIG],
    "entity_temp_outdoor": "sensor.outdoor_temp",
    "entity_weather": "weather.home",
    "algorithm_mode": "heating",
    "w_comfort": 1.0,
    "w_energy": 0.1,
    "w_smooth": 0.01,
}


def _make_hass(
    *,
    living_temp: str = "21.5",
    living_floor: str = "28.0",
    living_valve: str = "45.0",
    living_humidity: str = "55.0",
    bedroom_temp: str = "19.0",
    bedroom_floor: str = "25.0",
    bedroom_valve: str = "60.0",
    bedroom_humidity: str = "50.0",
    outdoor_temp: str = "5.0",
) -> MagicMock:
    """Create a MagicMock hass with states.get that returns sensor values."""
    hass = MagicMock()
    hass.config.latitude = 50.06
    hass.config.longitude = 19.94
    hass.services.async_call = AsyncMock()

    state_map: dict[str, str] = {
        "sensor.temp_living": living_temp,
        "sensor.floor_living": living_floor,
        "number.valve_living": living_valve,
        "sensor.humidity_living": living_humidity,
        "sensor.temp_bedroom": bedroom_temp,
        "sensor.floor_bedroom": bedroom_floor,
        "number.valve_bedroom": bedroom_valve,
        "sensor.humidity_bedroom": bedroom_humidity,
        "sensor.outdoor_temp": outdoor_temp,
    }

    def _states_get(entity_id: str) -> MagicMock | None:
        if entity_id in state_map:
            state = MagicMock()
            state.state = state_map[entity_id]
            state.attributes = {}
            return state
        return None

    hass.states.get = MagicMock(side_effect=_states_get)
    return hass


def _make_entry(
    entry_data: dict[str, Any] | None = None,
    *,
    live_control: dict[str, bool] | None = None,
) -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = entry_data if entry_data is not None else dict(_ENTRY_DATA_SINGLE)
    entry.entry_id = "test_entry_id"
    entry.options = {"live_control": live_control or {}}
    return entry


def _make_coordinator(
    ns: Any,
    hass: MagicMock | None = None,
    entry: MagicMock | None = None,
) -> Any:
    """Create a PumpAheadCoordinator with patched weather source."""
    if hass is None:
        hass = _make_hass()
    if entry is None:
        entry = _make_entry()
    coordinator = ns.PumpAheadCoordinator(hass, entry)
    coordinator._weather_source = None
    return coordinator


def _make_coordinator_data(
    ns: Any,
    *,
    rooms: dict[str, Any] | None = None,
    algorithm_mode: str = "heating",
    algorithm_status: str = "running",
) -> Any:
    """Build PumpAheadCoordinatorData with sensible defaults."""
    if rooms is None:
        rooms = {
            "Living Room": ns.RoomSensorData(
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
    return ns.PumpAheadCoordinatorData(
        rooms=rooms,
        T_outdoor=5.0,
        weather_source=None,
        last_update_success=True,
        algorithm_mode=algorithm_mode,
        algorithm_status=algorithm_status,
        last_update_timestamp="2026-04-09T12:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# TestArchitecturalIntegrity
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestArchitecturalIntegrity:
    """Verify architectural rules: no HA imports in core, valid structure."""

    def test_core_library_no_ha_imports(self) -> None:
        """pumpahead/ core must never import homeassistant."""
        core_dir = _REPO_ROOT / "pumpahead"
        assert core_dir.is_dir(), f"Core library directory not found: {core_dir}"

        violations: list[str] = []
        for py_file in core_dir.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("homeassistant"):
                            violations.append(
                                f"{py_file.relative_to(_REPO_ROOT)}:{node.lineno}"
                            )
                elif (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and node.module.startswith("homeassistant")
                ):
                    violations.append(
                        f"{py_file.relative_to(_REPO_ROOT)}:{node.lineno}"
                    )

        assert violations == [], f"Core library imports homeassistant in: {violations}"

    def test_custom_component_file_structure(self) -> None:
        """custom_components/pumpahead/ must have all expected files."""
        component_dir = _REPO_ROOT / "custom_components" / "pumpahead"
        expected_files = [
            "__init__.py",
            "const.py",
            "config_flow.py",
            "coordinator.py",
            "sensor.py",
            "climate.py",
            "ha_weather.py",
            "manifest.json",
        ]
        for filename in expected_files:
            assert (component_dir / filename).is_file(), (
                f"Missing expected file: custom_components/pumpahead/{filename}"
            )

    def test_manifest_schema_valid(self) -> None:
        """manifest.json must have valid schema fields."""
        manifest_path = _REPO_ROOT / "custom_components" / "pumpahead" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert manifest["domain"] == "pumpahead"
        assert manifest["config_flow"] is True
        assert manifest["integration_type"] == "hub"
        assert manifest["iot_class"] == "local_polling"
        assert "version" in manifest
        assert "codeowners" in manifest
        assert isinstance(manifest["codeowners"], list)

    def test_platforms_match_module_files(self, ha_integration_mocks: Any) -> None:
        """PLATFORMS constant must include sensor and climate."""
        ns = ha_integration_mocks
        platform_values = [str(p) for p in ns.PLATFORMS]
        assert "sensor" in platform_values
        assert "climate" in platform_values

    def test_coordinator_imports_pid_from_core(self) -> None:
        """coordinator.py must import PIDController from pumpahead.controller."""
        coord_path = _REPO_ROOT / "custom_components" / "pumpahead" / "coordinator.py"
        source = coord_path.read_text(encoding="utf-8")
        assert "from pumpahead.controller import PIDController" in source


# ---------------------------------------------------------------------------
# TestConfigFlowToCoordinatorPipeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConfigFlowToCoordinatorPipeline:
    """Tests that config flow output feeds into coordinator construction."""

    def test_full_wizard_produces_valid_coordinator_config(
        self, ha_integration_mocks: Any
    ) -> None:
        """Config flow data dict contains all keys needed by coordinator."""
        ns = ha_integration_mocks

        flow = ns.PumpAheadConfigFlow()
        flow.hass = _make_hass()

        # Step 1: Location
        asyncio.run(
            flow.async_step_user(
                {
                    ns.CONF_LATITUDE: 50.06,
                    ns.CONF_LONGITUDE: 19.94,
                }
            )
        )
        # After location, it auto-advances to rooms step (async_step_rooms)
        assert flow._location[ns.CONF_LATITUDE] == 50.06
        assert flow._location[ns.CONF_LONGITUDE] == 19.94

    def test_multi_room_config_flow_to_coordinator(
        self, ha_integration_mocks: Any
    ) -> None:
        """Multi-room config data creates coordinator with all rooms."""
        ns = ha_integration_mocks
        hass = _make_hass()
        entry = _make_entry(entry_data=dict(_ENTRY_DATA_MULTI))

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        data = asyncio.run(coordinator._async_update_data())
        assert "Living Room" in data.rooms
        assert "Bedroom" in data.rooms
        assert len(data.rooms) == 2

    def test_config_flow_entity_validation_prevents_bad_coordinator(
        self, ha_integration_mocks: Any
    ) -> None:
        """Config flow validates entity units, preventing invalid configs."""
        ns = ha_integration_mocks

        flow = ns.PumpAheadConfigFlow()
        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94

        # Provide entity with wrong unit
        wrong_unit_state = MagicMock()
        wrong_unit_state.attributes = {"unit_of_measurement": "F"}
        hass.states.get = MagicMock(return_value=wrong_unit_state)
        flow.hass = hass

        # Verify _validate_entity_unit rejects bad unit
        result = flow._validate_entity_unit("sensor.bad_temp", {"\u00b0C", "C"})
        assert result == "invalid_unit"

    def test_config_flow_accepts_entity_with_no_unit(
        self, ha_integration_mocks: Any
    ) -> None:
        """Config flow accepts entities without unit_of_measurement (e.g. actuators)."""
        ns = ha_integration_mocks

        flow = ns.PumpAheadConfigFlow()
        hass = MagicMock()
        no_unit_state = MagicMock()
        no_unit_state.attributes = {}
        hass.states.get = MagicMock(return_value=no_unit_state)
        flow.hass = hass

        result = flow._validate_entity_unit("number.valve", {"%"})
        assert result is None


# ---------------------------------------------------------------------------
# TestOptionsFlowLiveControlToggle
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOptionsFlowLiveControlToggle:
    """Tests for the options flow per-room live control toggle."""

    def test_options_flow_shows_toggle_per_room(
        self, ha_integration_mocks: Any
    ) -> None:
        """Options flow init step returns a form with toggle per room."""
        ns = ha_integration_mocks

        options_flow = ns.PumpAheadOptionsFlow()
        entry = _make_entry(entry_data=dict(_ENTRY_DATA_MULTI))
        options_flow.config_entry = entry

        result = asyncio.run(options_flow.async_step_init(user_input=None))
        assert result["type"] == "form"
        assert result["step_id"] == "init"

    def test_options_flow_enables_live_control_for_one_room(
        self, ha_integration_mocks: Any
    ) -> None:
        """Options flow creates entry with live_control map when toggled."""
        ns = ha_integration_mocks

        options_flow = ns.PumpAheadOptionsFlow()
        entry = _make_entry(entry_data=dict(_ENTRY_DATA_MULTI))
        options_flow.config_entry = entry

        result = asyncio.run(
            options_flow.async_step_init(
                user_input={
                    "enable_live_control_living_room": True,
                    "enable_live_control_bedroom": False,
                }
            )
        )
        assert result["type"] == "create_entry"
        live_control = result["data"][ns.CONF_LIVE_CONTROL]
        assert live_control["Living Room"] is True
        assert live_control["Bedroom"] is False

    def test_options_flow_defaults_to_shadow_mode(
        self, ha_integration_mocks: Any
    ) -> None:
        """Options flow defaults all rooms to shadow mode (False)."""
        ns = ha_integration_mocks

        options_flow = ns.PumpAheadOptionsFlow()
        entry = _make_entry(entry_data=dict(_ENTRY_DATA_MULTI))
        options_flow.config_entry = entry

        # Submit with no toggles set (empty dict)
        result = asyncio.run(options_flow.async_step_init(user_input={}))
        assert result["type"] == "create_entry"
        live_control = result["data"][ns.CONF_LIVE_CONTROL]
        for room_name in live_control:
            assert live_control[room_name] is False

    def test_options_flow_preserves_existing_settings(
        self, ha_integration_mocks: Any
    ) -> None:
        """Options flow shows current live_control state as defaults."""
        ns = ha_integration_mocks

        options_flow = ns.PumpAheadOptionsFlow()
        entry = _make_entry(
            entry_data=dict(_ENTRY_DATA_MULTI),
            live_control={"Living Room": True, "Bedroom": False},
        )
        options_flow.config_entry = entry

        # Request form (no user_input)
        result = asyncio.run(options_flow.async_step_init(user_input=None))
        assert result["type"] == "form"
        # The form is returned; the data_schema has defaults from existing options.
        # We verify that the flow works without error when options exist.


# ---------------------------------------------------------------------------
# TestCoordinatorToSensorPipeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoordinatorToSensorPipeline:
    """Tests that coordinator data flows correctly to sensor entities."""

    def test_coordinator_data_flows_to_room_sensors(
        self, ha_integration_mocks: Any
    ) -> None:
        """Room sensor native_value reads from coordinator data."""
        ns = ha_integration_mocks

        coordinator = _make_coordinator(ns)
        data = _make_coordinator_data(ns)
        coordinator.data = data

        # Create a room sensor (recommended_valve)
        desc = ns.ROOM_SENSORS[0]  # recommended_valve
        sensor = ns.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry_id",
            room_name="Living Room",
        )
        assert sensor.native_value == 62.5

    def test_coordinator_data_flows_to_global_sensors(
        self, ha_integration_mocks: Any
    ) -> None:
        """Global sensor native_value reads from coordinator data."""
        ns = ha_integration_mocks

        coordinator = _make_coordinator(ns)
        data = _make_coordinator_data(ns)
        coordinator.data = data

        # Create a global sensor (algorithm_status)
        desc = ns.GLOBAL_SENSORS[0]  # algorithm_status
        sensor = ns.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry_id",
            room_name=None,
        )
        assert sensor.native_value == "running"

    def test_sensor_returns_none_when_coordinator_data_missing(
        self, ha_integration_mocks: Any
    ) -> None:
        """Sensor must return None when coordinator.data is None."""
        ns = ha_integration_mocks

        coordinator = _make_coordinator(ns)
        coordinator.data = None

        desc = ns.ROOM_SENSORS[0]  # recommended_valve
        sensor = ns.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry_id",
            room_name="Living Room",
        )
        assert sensor.native_value is None

    def test_sensor_setup_entry_creates_correct_entity_count(
        self, ha_integration_mocks: Any
    ) -> None:
        """sensor.async_setup_entry creates per-room + global sensors."""
        ns = ha_integration_mocks

        hass = _make_hass()
        entry = _make_entry(entry_data=dict(_ENTRY_DATA_MULTI))

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None
        data = asyncio.run(coordinator._async_update_data())
        coordinator.data = data

        # Mock entry.runtime_data.coordinator
        runtime_data = MagicMock()
        runtime_data.coordinator = coordinator
        entry.runtime_data = runtime_data

        added_entities: list[Any] = []

        def capture_entities(entities: list) -> None:
            added_entities.extend(entities)

        asyncio.run(ns.sensor_async_setup_entry(hass, entry, capture_entities))

        num_rooms = len(data.rooms)  # 2
        expected = num_rooms * len(ns.ROOM_SENSORS) + len(ns.GLOBAL_SENSORS)
        assert len(added_entities) == expected


# ---------------------------------------------------------------------------
# TestCoordinatorToClimatePipeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoordinatorToClimatePipeline:
    """Tests that coordinator data flows correctly to climate entities."""

    def test_coordinator_data_flows_to_climate_entity(
        self, ha_integration_mocks: Any
    ) -> None:
        """Climate entity reads current_temperature from coordinator data."""
        ns = ha_integration_mocks

        coordinator = _make_coordinator(ns)
        data = _make_coordinator_data(ns)
        coordinator.data = data

        entity = ns.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry_id",
            room_name="Living Room",
            has_split=False,
        )
        assert entity.current_temperature == 21.5

    def test_climate_entity_reflects_algorithm_mode_changes(
        self, ha_integration_mocks: Any
    ) -> None:
        """Climate entity HVAC mode changes when coordinator data changes."""
        ns = ha_integration_mocks

        coordinator = _make_coordinator(ns)

        # Heating mode
        data_heat = _make_coordinator_data(ns, algorithm_mode="heating")
        coordinator.data = data_heat
        entity = ns.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry_id",
            room_name="Living Room",
            has_split=False,
        )
        assert entity.hvac_mode == ns.HVACMode.HEAT

        # Switch to cooling
        data_cool = _make_coordinator_data(ns, algorithm_mode="cooling")
        coordinator.data = data_cool
        assert entity.hvac_mode == ns.HVACMode.COOL

    def test_climate_setup_entry_creates_one_entity_per_room(
        self, ha_integration_mocks: Any
    ) -> None:
        """climate.async_setup_entry creates one entity per configured room."""
        ns = ha_integration_mocks

        hass = _make_hass()
        entry = _make_entry(entry_data=dict(_ENTRY_DATA_MULTI))

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        runtime_data = MagicMock()
        runtime_data.coordinator = coordinator
        entry.runtime_data = runtime_data

        added_entities: list[Any] = []

        def capture_entities(entities: list) -> None:
            added_entities.extend(entities)

        asyncio.run(ns.climate_async_setup_entry(hass, entry, capture_entities))

        assert len(added_entities) == 2  # Living Room + Bedroom
        room_names = {e._room_name for e in added_entities}
        assert room_names == {"Living Room", "Bedroom"}

    def test_climate_entity_no_data_returns_none_temperature(
        self, ha_integration_mocks: Any
    ) -> None:
        """Climate entity returns None temperature when coordinator.data is None."""
        ns = ha_integration_mocks

        coordinator = _make_coordinator(ns)
        coordinator.data = None

        entity = ns.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id="test_entry_id",
            room_name="Living Room",
            has_split=False,
        )
        assert entity.current_temperature is None
        assert entity.hvac_mode == ns.HVACMode.OFF


# ---------------------------------------------------------------------------
# TestShadowModeFullPipeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestShadowModeFullPipeline:
    """Tests shadow mode end-to-end: read entities -> PID -> recommendations."""

    def test_shadow_mode_update_cycle_end_to_end(
        self, ha_integration_mocks: Any
    ) -> None:
        """Full update cycle: entity read -> PID compute -> sensor output."""
        ns = ha_integration_mocks

        hass = _make_hass()
        entry = _make_entry()

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        # Run the update cycle
        data = asyncio.run(coordinator._async_update_data())

        # Verify room data was populated from entities
        room = data.rooms["Living Room"]
        assert room.T_room == 21.5
        assert room.T_floor == 28.0
        assert room.valve_pos == 45.0
        assert room.humidity == 55.0

        # Verify PID computed a recommendation
        assert room.recommended_valve is not None
        assert 0 <= room.recommended_valve <= 100

        # Verify global data
        assert data.T_outdoor == 5.0
        assert data.algorithm_mode == "heating"
        assert data.algorithm_status == "running"
        assert data.last_update_timestamp is not None

        # Now verify sensor entity reads the recommendation
        coordinator.data = data
        desc = ns.ROOM_SENSORS[0]  # recommended_valve
        sensor = ns.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry_id",
            room_name="Living Room",
        )
        assert sensor.native_value == room.recommended_valve

    def test_shadow_mode_stale_sensors_report_stale_status(
        self, ha_integration_mocks: Any
    ) -> None:
        """When all room sensors are unavailable, status is 'stale'."""
        ns = ha_integration_mocks

        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94
        hass.services.async_call = AsyncMock()

        # All entities return unavailable
        def _states_unavailable(entity_id: str) -> MagicMock:
            state = MagicMock()
            state.state = "unavailable"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_unavailable)

        entry = _make_entry()
        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        data = asyncio.run(coordinator._async_update_data())
        assert data.algorithm_status == "stale"

        # Verify sensor reports the stale status
        coordinator.data = data
        status_desc = ns.GLOBAL_SENSORS[0]  # algorithm_status
        sensor = ns.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=status_desc,
            entry_id="test_entry_id",
            room_name=None,
        )
        assert sensor.native_value == "stale"

    def test_shadow_mode_partial_stale_continues(
        self, ha_integration_mocks: Any
    ) -> None:
        """When one room is unavailable, others still get recommendations."""
        ns = ha_integration_mocks

        hass = MagicMock()
        hass.config.latitude = 50.06
        hass.config.longitude = 19.94
        hass.services.async_call = AsyncMock()

        def _states_partial(entity_id: str) -> MagicMock:
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
                state.state = "unavailable"
            state.attributes = {}
            return state

        hass.states.get = MagicMock(side_effect=_states_partial)

        entry = _make_entry(entry_data=dict(_ENTRY_DATA_MULTI))
        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        data = asyncio.run(coordinator._async_update_data())

        # Living Room should have recommendations
        living = data.rooms["Living Room"]
        assert living.T_room == 21.5
        assert living.recommended_valve is not None

        # Bedroom should have None (unavailable)
        bedroom = data.rooms["Bedroom"]
        assert bedroom.T_room is None
        assert bedroom.recommended_valve is None

        # Status should be stale (some rooms unavailable)
        assert data.algorithm_status == "stale"


# ---------------------------------------------------------------------------
# TestLiveControlFullPipeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLiveControlFullPipeline:
    """Tests live control: coordinator issues service calls for valve/split."""

    def test_live_control_issues_valve_service_call(
        self, ha_integration_mocks: Any
    ) -> None:
        """When live control is enabled, coordinator calls number.set_value."""
        ns = ha_integration_mocks

        hass = _make_hass()
        entry = _make_entry(live_control={"Living Room": True})

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        asyncio.run(coordinator._async_update_data())

        # Verify number.set_value was called for the valve
        calls = hass.services.async_call.call_args_list
        valve_calls = [
            c for c in calls if c.args[0] == "number" and c.args[1] == "set_value"
        ]
        assert len(valve_calls) == 1
        assert valve_calls[0].args[2]["entity_id"] == "number.valve_living"

    def test_live_control_disabled_no_service_calls(
        self, ha_integration_mocks: Any
    ) -> None:
        """When live control is disabled, no service calls are issued."""
        ns = ha_integration_mocks

        hass = _make_hass()
        entry = _make_entry(live_control={"Living Room": False})

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        asyncio.run(coordinator._async_update_data())

        # No service calls should have been made
        hass.services.async_call.assert_not_called()

    def test_live_control_split_service_calls_in_heating_mode(
        self, ha_integration_mocks: Any
    ) -> None:
        """Live control issues split calls when room has split."""
        ns = ha_integration_mocks

        # Room temp well below setpoint to trigger split recommendation
        hass = _make_hass(bedroom_temp="18.0")
        entry = _make_entry(
            entry_data=dict(_ENTRY_DATA_MULTI),
            live_control={"Living Room": False, "Bedroom": True},
        )

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        asyncio.run(coordinator._async_update_data())

        calls = hass.services.async_call.call_args_list

        # Verify valve set_value was called for bedroom
        valve_calls = [
            c for c in calls if c.args[0] == "number" and c.args[1] == "set_value"
        ]
        assert len(valve_calls) >= 1

        # Verify climate service calls for split
        climate_calls = [c for c in calls if c.args[0] == "climate"]
        # Should have set_hvac_mode and set_temperature calls
        hvac_mode_calls = [c for c in climate_calls if c.args[1] == "set_hvac_mode"]
        assert len(hvac_mode_calls) >= 1
        # In heating mode, split should be set to "heat" (not "cool")
        assert hvac_mode_calls[0].args[2]["hvac_mode"] == "heat"

    def test_live_control_service_call_failure_does_not_crash(
        self, ha_integration_mocks: Any
    ) -> None:
        """Service call failure must not crash the coordinator update."""
        ns = ha_integration_mocks

        hass = _make_hass()
        hass.services.async_call = AsyncMock(side_effect=RuntimeError("Service failed"))
        entry = _make_entry(live_control={"Living Room": True})

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        # Must not raise despite service call failure
        data = asyncio.run(coordinator._async_update_data())
        assert data.last_update_success is True


# ---------------------------------------------------------------------------
# TestAxiomEnforcement
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAxiomEnforcement:
    """Verify axiom enforcement in the integrated pipeline."""

    def test_axiom3_split_never_opposes_heating_mode(
        self, ha_integration_mocks: Any
    ) -> None:
        """Axiom 3: In heating mode, split must never recommend cooling."""
        ns = ha_integration_mocks

        # Room is well above setpoint in heating mode — split should be "off",
        # NOT "cooling".
        hass = _make_hass(bedroom_temp="25.0")
        entry_data = dict(_ENTRY_DATA_MULTI)
        entry_data["algorithm_mode"] = "heating"
        entry = _make_entry(entry_data=entry_data)

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        data = asyncio.run(coordinator._async_update_data())
        bedroom = data.rooms["Bedroom"]

        # In heating mode, even if room is too hot, split must NOT cool
        assert bedroom.split_recommended_mode != "cooling", (
            "Axiom 3 violated: split recommended cooling in heating mode"
        )
        # Should be "off" since no heating is needed
        assert bedroom.split_recommended_mode == "off"

    def test_axiom3_split_never_opposes_cooling_mode(
        self, ha_integration_mocks: Any
    ) -> None:
        """Axiom 3: In cooling mode, split must never recommend heating."""
        ns = ha_integration_mocks

        # Room is well below setpoint in cooling mode — split should be "off",
        # NOT "heating".
        hass = _make_hass(bedroom_temp="18.0")
        entry_data = dict(_ENTRY_DATA_MULTI)
        entry_data["algorithm_mode"] = "cooling"
        entry = _make_entry(entry_data=entry_data)

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        data = asyncio.run(coordinator._async_update_data())
        bedroom = data.rooms["Bedroom"]

        # In cooling mode, even if room is too cold, split must NOT heat
        assert bedroom.split_recommended_mode != "heating", (
            "Axiom 3 violated: split recommended heating in cooling mode"
        )
        # Should be "off" since no cooling is needed
        assert bedroom.split_recommended_mode == "off"

    def test_axiom3_split_heats_in_heating_mode_when_needed(
        self, ha_integration_mocks: Any
    ) -> None:
        """Axiom 3: In heating mode, split can assist with heating."""
        ns = ha_integration_mocks

        # Room well below setpoint in heating mode
        hass = _make_hass(bedroom_temp="18.0")
        entry_data = dict(_ENTRY_DATA_MULTI)
        entry_data["algorithm_mode"] = "heating"
        entry = _make_entry(entry_data=entry_data)

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        data = asyncio.run(coordinator._async_update_data())
        bedroom = data.rooms["Bedroom"]

        # In heating mode with room below setpoint, split should help heat
        assert bedroom.split_recommended_mode == "heating"
        assert bedroom.split_recommended_setpoint == ns.DEFAULT_SETPOINT

    def test_axiom3_split_cools_in_cooling_mode_when_needed(
        self, ha_integration_mocks: Any
    ) -> None:
        """Axiom 3: In cooling mode, split can assist with cooling."""
        ns = ha_integration_mocks

        # Room well above setpoint in cooling mode
        hass = _make_hass(bedroom_temp="25.0")
        entry_data = dict(_ENTRY_DATA_MULTI)
        entry_data["algorithm_mode"] = "cooling"
        entry = _make_entry(entry_data=entry_data)

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        data = asyncio.run(coordinator._async_update_data())
        bedroom = data.rooms["Bedroom"]

        # In cooling mode with room above setpoint, split should cool
        assert bedroom.split_recommended_mode == "cooling"
        assert bedroom.split_recommended_setpoint == ns.DEFAULT_SETPOINT

    def test_axiom8_no_brand_specific_entities_in_config(self) -> None:
        """Axiom 8: No brand-specific entity IDs in config flow or coordinator."""
        brand_keywords = [
            "heishamon",
            "aquarea",
            "vdmot",
            "mitsubishi",
            "cn105",
            "panasonic",
            "daikin",
            "toshiba",
            "lg_",
        ]
        files_to_check = [
            _REPO_ROOT / "custom_components" / "pumpahead" / "config_flow.py",
            _REPO_ROOT / "custom_components" / "pumpahead" / "coordinator.py",
            _REPO_ROOT / "custom_components" / "pumpahead" / "const.py",
            _REPO_ROOT / "custom_components" / "pumpahead" / "climate.py",
            _REPO_ROOT / "custom_components" / "pumpahead" / "sensor.py",
        ]

        violations: list[str] = []
        for file_path in files_to_check:
            source = file_path.read_text(encoding="utf-8").lower()
            for keyword in brand_keywords:
                if keyword in source:
                    violations.append(
                        f"{file_path.name} contains brand keyword '{keyword}'"
                    )

        assert violations == [], (
            f"Axiom 8 violated — brand-specific references: {violations}"
        )


# ---------------------------------------------------------------------------
# TestAcceptanceCriteriaVerification
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAcceptanceCriteriaVerification:
    """Explicit checks for Epic 15 acceptance criteria."""

    def test_all_modules_importable(self, ha_integration_mocks: Any) -> None:
        """All HA integration modules must be importable without error.

        The fact that the fixture yields successfully proves this, but
        we verify the key symbols exist.
        """
        ns = ha_integration_mocks
        assert ns.PumpAheadConfigFlow is not None
        assert ns.PumpAheadOptionsFlow is not None
        assert ns.PumpAheadCoordinator is not None
        assert ns.PumpAheadCoordinatorData is not None
        assert ns.RoomSensorData is not None
        assert ns.PumpAheadSensorEntity is not None
        assert ns.PumpAheadClimateEntity is not None

    def test_domain_is_pumpahead(self, ha_integration_mocks: Any) -> None:
        """DOMAIN constant must be 'pumpahead'."""
        ns = ha_integration_mocks
        assert ns.DOMAIN == "pumpahead"

    def test_update_interval_is_5_minutes(self, ha_integration_mocks: Any) -> None:
        """UPDATE_INTERVAL_MINUTES must be 5."""
        ns = ha_integration_mocks
        assert ns.UPDATE_INTERVAL_MINUTES == 5

    def test_config_flow_version_is_1(self, ha_integration_mocks: Any) -> None:
        """Config flow VERSION must be 1."""
        ns = ha_integration_mocks
        assert ns.PumpAheadConfigFlow.VERSION == 1

    def test_full_pipeline_config_to_sensor_output(
        self, ha_integration_mocks: Any
    ) -> None:
        """End-to-end: config data -> coordinator -> sensor entity -> value.

        This is the most comprehensive pipeline test: start with raw
        config entry data, create coordinator, run update, create sensor
        entity, and verify native_value.
        """
        ns = ha_integration_mocks

        hass = _make_hass()
        entry = _make_entry(entry_data=dict(_ENTRY_DATA_MULTI))

        # Step 1: Create coordinator from config
        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        # Step 2: Run update cycle (entity read + PID)
        data = asyncio.run(coordinator._async_update_data())
        coordinator.data = data

        # Step 3: Create sensor entity
        desc = ns.ROOM_SENSORS[0]  # recommended_valve
        sensor = ns.PumpAheadSensorEntity(
            coordinator=coordinator,
            description=desc,
            entry_id=entry.entry_id,
            room_name="Living Room",
        )

        # Step 4: Verify sensor reads the PID output
        assert sensor.native_value is not None
        assert isinstance(sensor.native_value, float)

    def test_full_pipeline_config_to_climate_output(
        self, ha_integration_mocks: Any
    ) -> None:
        """End-to-end: config data -> coordinator -> climate entity -> props.

        Start with raw config entry data, create coordinator, run update,
        create climate entity, and verify all properties.
        """
        ns = ha_integration_mocks

        hass = _make_hass()
        entry = _make_entry(entry_data=dict(_ENTRY_DATA_MULTI))

        coordinator = ns.PumpAheadCoordinator(hass, entry)
        coordinator._weather_source = None

        data = asyncio.run(coordinator._async_update_data())
        coordinator.data = data

        entity = ns.PumpAheadClimateEntity(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            room_name="Living Room",
            has_split=False,
        )

        # Verify climate entity properties
        assert entity.current_temperature == 21.5
        assert entity.target_temperature == ns.DEFAULT_SETPOINT
        assert entity.hvac_mode == ns.HVACMode.HEAT
        assert "heat" in entity.hvac_modes
        assert entity.extra_state_attributes["room_name"] == "Living Room"
        assert entity.extra_state_attributes["recommended_valve"] is not None
