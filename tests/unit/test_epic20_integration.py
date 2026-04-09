"""Integration tests for Epic #20 -- Hardware Abstraction & Entity Mapping.

Verifies end-to-end cross-module wiring for the three sub-issues:
    #63 EntityValidator (custom_components/pumpahead/entity_validator.py)
    #64 HP mode mapping (pumpahead/hp_mode_mapping.py)
    #65 COP calculator  (pumpahead/cop_calculator.py)

Tests exercise cross-module workflows:
    EntityValidator -> config flow -> HPModeMapper pipeline
    HPModeMapper -> coordinator -> COPCalculator alignment
    EntityValidator unit validation -> COPCalculator assumptions
    combined end-to-end scenarios (multi-brand HP, pipeline, fallback)
    acceptance criteria explicit verification
    architectural integrity (dependency DAG, no homeassistant imports)

All tests are fast, deterministic, and use the
``@pytest.mark.unit`` marker.
"""

from __future__ import annotations

import inspect
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from pumpahead.cop_calculator import (
    COP_MAX,
    COP_MIN,
    COPCalculator,
    COPMode,
)
from pumpahead.hp_mode_mapping import HPModeMapper, HPOperatingState
from pumpahead.simulator import HeatPumpMode

_REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Module-scoped fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def epic20_mocks() -> Any:  # noqa: C901
    """Set up mock HA modules, import EntityValidator + const, yield, clean up."""
    existing_ha_keys = {
        k for k in sys.modules if k.startswith(("homeassistant", "custom_components"))
    }

    # -- Mock homeassistant modules -------------------------------------------

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

    class _FakeConfigFlow:
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

    ha_config_entries.ConfigFlow = _FakeConfigFlow  # type: ignore[attr-defined]

    class _FakeOptionsFlow:
        config_entry: Any = None

    ha_config_entries.OptionsFlow = _FakeOptionsFlow  # type: ignore[attr-defined]

    ha_data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    ha_data_entry_flow.FlowResult = dict  # type: ignore[attr-defined]

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
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.hass = args[0] if args else kwargs.get("hass")

        def __class_getitem__(cls, _item: object) -> type:  # noqa: N804
            return cls

        async def async_config_entry_first_refresh(self) -> None:
            pass

    ha_helpers_update_coordinator.DataUpdateCoordinator = _FakeDataUpdateCoordinator  # type: ignore[attr-defined]

    # voluptuous mock.
    vol = types.ModuleType("voluptuous")
    vol.Schema = MagicMock(side_effect=lambda x: x)  # type: ignore[attr-defined]
    vol.Required = MagicMock(side_effect=lambda key, **kw: key)  # type: ignore[attr-defined]
    vol.Optional = MagicMock(side_effect=lambda key, **kw: key)  # type: ignore[attr-defined]

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

    # Import the HA-dependent modules under test.
    from custom_components.pumpahead.const import (
        CONF_ENTITY_HP_STATE,
        CONF_HP_MODE_MAPPING,
        ENTITY_STALE_MAX_SECONDS,
        HP_OPERATING_STATES,
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
    ns.EntityValidator = EntityValidator  # type: ignore[attr-defined]
    ns.ValidationResult = ValidationResult  # type: ignore[attr-defined]
    ns.VALID_TEMP_UNITS = VALID_TEMP_UNITS  # type: ignore[attr-defined]
    ns.VALID_PERCENT_UNITS = VALID_PERCENT_UNITS  # type: ignore[attr-defined]
    ns.VALID_POWER_UNITS = VALID_POWER_UNITS  # type: ignore[attr-defined]
    ns.HP_OPERATING_STATES = HP_OPERATING_STATES  # type: ignore[attr-defined]
    ns.CONF_HP_MODE_MAPPING = CONF_HP_MODE_MAPPING  # type: ignore[attr-defined]
    ns.CONF_ENTITY_HP_STATE = CONF_ENTITY_HP_STATE  # type: ignore[attr-defined]
    ns.ENTITY_STALE_MAX_SECONDS = ENTITY_STALE_MAX_SECONDS  # type: ignore[attr-defined]

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


def _make_validator(epic20_mocks: Any) -> tuple[Any, MagicMock]:
    """Create an EntityValidator with a mocked hass.

    Returns ``(validator, hass_mock)`` so the test can configure
    ``hass_mock.states.get``.
    """
    hass = MagicMock()
    validator = epic20_mocks.EntityValidator(hass)
    return validator, hass


def _make_state(
    state_value: str = "21.5",
    unit: str | None = "\u00b0C",
    device_class: str | None = "temperature",
) -> MagicMock:
    """Create a mock entity state with configurable attributes."""
    state = MagicMock()
    state.state = state_value
    attrs: dict[str, str] = {}
    if unit is not None:
        attrs["unit_of_measurement"] = unit
    if device_class is not None:
        attrs["device_class"] = device_class
    state.attributes = attrs
    return state


def _extract_import_lines(mod: object) -> list[str]:
    """Extract import/from-import lines from a module's source code.

    Filters out docstrings and comments so that mentions of module
    names in documentation do not cause false positives.
    """
    source = inspect.getsource(mod)  # type: ignore[arg-type]
    lines: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return lines


# ---------------------------------------------------------------------------
# Multi-brand HP mapping configs
# ---------------------------------------------------------------------------

_HEISHAMON_CONFIG: dict[str, str] = {
    "Heat": "heating",
    "Cool": "cooling",
    "DHW": "dhw",
    "Idle": "idle",
    "Defrost": "defrost",
}

_DAIKIN_CONFIG: dict[str, str] = {
    "heating": "heating",
    "cooling": "cooling",
    "hot_water": "dhw",
    "standby": "idle",
    "defrosting": "defrost",
}

_NIBE_CONFIG: dict[str, str] = {
    "HEATING": "heating",
    "COOLING": "cooling",
    "HOT WATER": "dhw",
    "IDLE": "idle",
    "DEFROST": "defrost",
}

_EBUS_CONFIG: dict[str, str] = {
    "ch": "heating",
    "dhw": "dhw",
    "off": "idle",
}


# ---------------------------------------------------------------------------
# TestEntityValidatorToHPModeMapperPipeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEntityValidatorToHPModeMapperPipeline:
    """Cross-module: EntityValidator validates HP state entity -> HPModeMapper maps states."""

    def test_validated_hp_state_entity_produces_valid_mapper(
        self, epic20_mocks: Any
    ) -> None:
        """Validator accepts HP state sensor; mapper uses config to map states."""
        validator, hass = _make_validator(epic20_mocks)
        hass.states.get.return_value = _make_state(
            state_value="Heat", unit=None, device_class=None
        )

        # Validator approves the entity.
        result = validator.validate_entity("sensor.hp_state")
        assert result.valid is True

        # Mapper constructed from config maps the raw state.
        mapper = HPModeMapper.from_config(_HEISHAMON_CONFIG)
        state = mapper.map("Heat")
        assert state == HPOperatingState.HEATING

    def test_hp_operating_states_const_matches_enum_values(
        self, epic20_mocks: Any
    ) -> None:
        """HP_OPERATING_STATES in const.py must match HPOperatingState enum values exactly."""
        enum_values = sorted(s.value for s in HPOperatingState)
        const_values = sorted(epic20_mocks.HP_OPERATING_STATES)
        assert enum_values == const_values

    def test_config_mapping_dict_roundtrips_through_mapper(
        self, epic20_mocks: Any
    ) -> None:
        """A mapping dict from config flow roundtrips through HPModeMapper.from_config."""
        # Simulate config flow output.
        config_mapping = {
            "Heat": "heating",
            "Cool": "cooling",
            "DHW": "dhw",
            "Idle": "idle",
            "Defrost": "defrost",
        }
        mapper = HPModeMapper.from_config(config_mapping)

        # All config keys map correctly (case-insensitive).
        for raw_key, expected_value in config_mapping.items():
            mapped = mapper.map(raw_key)
            assert mapped.value == expected_value

    def test_entity_validator_allows_sensor_domain_for_hp_state(
        self, epic20_mocks: Any
    ) -> None:
        """EntityValidator must accept sensor.* entities for HP state mapping."""
        validator, hass = _make_validator(epic20_mocks)
        hass.states.get.return_value = _make_state(
            state_value="heating", unit=None, device_class=None
        )
        result = validator.validate_entity("sensor.heishamon_operating_state")
        assert result.valid is True


# ---------------------------------------------------------------------------
# TestHPModeMapperToCOPCalculatorAlignment
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHPModeMapperToCOPCalculatorAlignment:
    """Cross-module: HPModeMapper output determines COP calculation applicability."""

    def test_heating_mode_enables_cop_calculation(self) -> None:
        """HPOperatingState.HEATING maps to HeatPumpMode.HEATING; COP is computed."""
        mapper = HPModeMapper.from_config({"Heat": "heating"})
        op_state = mapper.map("Heat")
        hp_mode = HPModeMapper.to_heat_pump_mode(op_state)

        assert hp_mode == HeatPumpMode.HEATING

        # COP calculation proceeds in heating mode.
        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=3.5)
        cop = calc.get_cop(t_outdoor=-5.0)
        assert COP_MIN <= cop <= COP_MAX

    def test_cooling_mode_enables_cop_calculation(self) -> None:
        """HPOperatingState.COOLING maps to HeatPumpMode.COOLING; COP is computed."""
        mapper = HPModeMapper.from_config({"Cool": "cooling"})
        op_state = mapper.map("Cool")
        hp_mode = HPModeMapper.to_heat_pump_mode(op_state)

        assert hp_mode == HeatPumpMode.COOLING

        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=4.0)
        cop = calc.get_cop(t_outdoor=30.0)
        assert COP_MIN <= cop <= COP_MAX

    def test_non_thermal_modes_map_to_off_cop_not_applicable(self) -> None:
        """DHW, IDLE, DEFROST all map to HeatPumpMode.OFF."""
        mapper = HPModeMapper.from_config(
            {"DHW": "dhw", "Idle": "idle", "Defrost": "defrost"}
        )
        for raw_state in ("DHW", "Idle", "Defrost"):
            op_state = mapper.map(raw_state)
            hp_mode = HPModeMapper.to_heat_pump_mode(op_state)
            assert hp_mode == HeatPumpMode.OFF, (
                f"{raw_state} should map to OFF, got {hp_mode}"
            )

    def test_cop_auto_learned_with_hp_mode_filtered_samples(self) -> None:
        """COP samples should only be added when HP is in a thermal mode."""
        mapper = HPModeMapper.from_config({"Heat": "heating", "Idle": "idle"})
        calc = COPCalculator(mode=COPMode.AUTO_LEARNED, min_samples_hours=2)

        # Only add samples when HP is actively heating.
        for raw_state, t_outdoor, p_elec, q_thermal in [
            ("Heat", -5.0, 2000.0, 7000.0),
            ("Idle", 5.0, 100.0, 350.0),  # idle -- should not add
            ("Heat", 0.0, 1800.0, 5400.0),
        ]:
            op_state = mapper.map(raw_state)
            hp_mode = HPModeMapper.to_heat_pump_mode(op_state)
            if hp_mode in (HeatPumpMode.HEATING, HeatPumpMode.COOLING):
                calc.add_sample(t_outdoor, 35.0, p_elec, q_thermal)

        assert calc.n_samples == 2


# ---------------------------------------------------------------------------
# TestEntityValidatorUnitsToCOPCalculatorAlignment
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEntityValidatorUnitsToCOPCalculatorAlignment:
    """Cross-module: EntityValidator unit sets align with COPCalculator expectations."""

    def test_power_unit_watts_accepted_by_validator_and_used_by_cop(
        self, epic20_mocks: Any
    ) -> None:
        """EntityValidator accepts W; COPCalculator expects power in Watts."""
        validator, hass = _make_validator(epic20_mocks)
        hass.states.get.return_value = _make_state(unit="W", device_class="power")
        result = validator.validate_unit(
            "sensor.hp_power", epic20_mocks.VALID_POWER_UNITS
        )
        assert result.valid is True

        # COPCalculator uses W directly.
        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=3.5)
        assert calc.add_sample(t_outdoor=0.0, t_supply=35.0, p_electric=2000.0, q_thermal=7000.0)

    def test_temperature_unit_celsius_accepted_by_validator_and_used_by_cop(
        self, epic20_mocks: Any
    ) -> None:
        """EntityValidator accepts degC; COPCalculator expects temperatures in Celsius."""
        validator, hass = _make_validator(epic20_mocks)
        hass.states.get.return_value = _make_state(unit="\u00b0C", device_class="temperature")
        result = validator.validate_unit(
            "sensor.outdoor_temp", epic20_mocks.VALID_TEMP_UNITS
        )
        assert result.valid is True

        # COPCalculator uses Celsius directly.
        calc = COPCalculator(mode=COPMode.CONSTANT)
        cop = calc.get_cop(t_outdoor=5.0)
        assert COP_MIN <= cop <= COP_MAX

    def test_all_valid_temp_units_are_celsius_variants(
        self, epic20_mocks: Any
    ) -> None:
        """VALID_TEMP_UNITS must contain only Celsius-equivalent strings."""
        valid_celsius = {"\u00b0C", "C"}
        assert epic20_mocks.VALID_TEMP_UNITS == valid_celsius

    def test_all_valid_power_units_are_watts(self, epic20_mocks: Any) -> None:
        """VALID_POWER_UNITS must contain only 'W'."""
        assert epic20_mocks.VALID_POWER_UNITS == {"W"}


# ---------------------------------------------------------------------------
# TestCombinedEpic20Scenarios
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCombinedEpic20Scenarios:
    """End-to-end scenarios combining EntityValidator, HPModeMapper, COPCalculator."""

    def test_full_pipeline_validate_entity_map_state_compute_cop(
        self, epic20_mocks: Any
    ) -> None:
        """Full pipeline: validate entity -> map HP state -> compute COP."""
        # 1. EntityValidator validates the HP state sensor.
        validator, hass = _make_validator(epic20_mocks)
        hass.states.get.return_value = _make_state(
            state_value="Heat", unit=None, device_class=None
        )
        val_result = validator.validate_entity("sensor.hp_state")
        assert val_result.valid is True

        # 2. HPModeMapper maps the raw state.
        mapper = HPModeMapper.from_config(_HEISHAMON_CONFIG)
        op_state = mapper.map("Heat")
        assert op_state == HPOperatingState.HEATING

        hp_mode = HPModeMapper.to_heat_pump_mode(op_state)
        assert hp_mode == HeatPumpMode.HEATING

        # 3. COPCalculator provides COP for heating conditions.
        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=3.5)
        cop = calc.get_cop(t_outdoor=-5.0)
        assert cop == 3.5

    def test_heishamon_scenario_all_modules(self, epic20_mocks: Any) -> None:
        """HeishaMon brand: validate temp+power entities, map states, compute COP."""
        validator, hass = _make_validator(epic20_mocks)

        # Validate temperature entity.
        hass.states.get.return_value = _make_state(
            state_value="35.0", unit="\u00b0C", device_class="temperature"
        )
        assert validator.validate_unit(
            "sensor.heishamon_t_supply", epic20_mocks.VALID_TEMP_UNITS
        ).valid is True

        # Validate power entity.
        hass.states.get.return_value = _make_state(
            state_value="2000", unit="W", device_class="power"
        )
        assert validator.validate_unit(
            "sensor.heishamon_power", epic20_mocks.VALID_POWER_UNITS
        ).valid is True

        # Map HP state.
        mapper = HPModeMapper.from_config(_HEISHAMON_CONFIG)
        assert mapper.map("Heat") == HPOperatingState.HEATING
        assert mapper.map("DHW") == HPOperatingState.DHW

        # COP calculation with validated data.
        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=3.5)
        cop = calc.get_cop(t_outdoor=-5.0)
        assert cop == 3.5

    def test_fallback_cop_when_mapper_returns_idle(
        self, epic20_mocks: Any
    ) -> None:
        """Unknown raw state -> IDLE -> HeatPumpMode.OFF -> COP uses fallback."""
        mapper = HPModeMapper.from_config(_HEISHAMON_CONFIG)

        # Unknown state falls back to IDLE.
        op_state = mapper.map("SomeUnknownState")
        assert op_state == HPOperatingState.IDLE

        hp_mode = HPModeMapper.to_heat_pump_mode(op_state)
        assert hp_mode == HeatPumpMode.OFF

        # In a real coordinator, COP would not be computed for OFF mode.
        # But the fallback constant COP remains available.
        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=3.5)
        cop = calc.get_cop(t_outdoor=5.0)
        assert cop == 3.5

    def test_multi_brand_mapping_cop_consistency(self, epic20_mocks: Any) -> None:
        """All four brand configs produce consistent COP for their heating state."""
        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=3.5)

        brand_configs = {
            "HeishaMon": (_HEISHAMON_CONFIG, "Heat"),
            "Daikin": (_DAIKIN_CONFIG, "heating"),
            "Nibe": (_NIBE_CONFIG, "HEATING"),
            "eBUS": (_EBUS_CONFIG, "ch"),
        }

        for brand_name, (config, heating_raw) in brand_configs.items():
            mapper = HPModeMapper.from_config(config)
            op_state = mapper.map(heating_raw)
            hp_mode = HPModeMapper.to_heat_pump_mode(op_state)

            assert hp_mode == HeatPumpMode.HEATING, (
                f"{brand_name}: expected HEATING, got {hp_mode}"
            )

            cop = calc.get_cop(t_outdoor=0.0)
            assert COP_MIN <= cop <= COP_MAX, (
                f"{brand_name}: COP {cop} outside valid range"
            )


# ---------------------------------------------------------------------------
# TestAcceptanceCriteriaVerification
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAcceptanceCriteriaVerification:
    """Explicit verification of Epic #20 acceptance criteria."""

    def test_ac_entity_mapping_validates_required_entities(
        self, epic20_mocks: Any
    ) -> None:
        """AC: Entity mapping validates required entities with correct units."""
        validator, hass = _make_validator(epic20_mocks)

        # Temperature entity with degC.
        hass.states.get.return_value = _make_state(
            state_value="21.0", unit="\u00b0C", device_class="temperature"
        )
        result = validator.validate_entity(
            "sensor.room_temp",
            valid_units=epic20_mocks.VALID_TEMP_UNITS,
            expected_device_class="temperature",
        )
        assert result.valid is True

        # Humidity entity with %.
        hass.states.get.return_value = _make_state(
            state_value="55", unit="%", device_class="humidity"
        )
        result = validator.validate_entity(
            "sensor.room_humidity",
            valid_units=epic20_mocks.VALID_PERCENT_UNITS,
            expected_device_class="humidity",
        )
        assert result.valid is True

        # Power entity with W.
        hass.states.get.return_value = _make_state(
            state_value="2000", unit="W", device_class="power"
        )
        result = validator.validate_entity(
            "sensor.hp_power",
            valid_units=epic20_mocks.VALID_POWER_UNITS,
            expected_device_class="power",
        )
        assert result.valid is True

    def test_ac_unit_validation_rejects_wrong_units(
        self, epic20_mocks: Any
    ) -> None:
        """AC: Unit validation rejects entities with incorrect units."""
        validator, hass = _make_validator(epic20_mocks)

        # Fahrenheit rejected.
        hass.states.get.return_value = _make_state(unit="\u00b0F")
        result = validator.validate_unit(
            "sensor.temp_f", epic20_mocks.VALID_TEMP_UNITS
        )
        assert result.valid is False
        assert result.error_key == "invalid_unit"

        # kW rejected for power (only W accepted).
        hass.states.get.return_value = _make_state(unit="kW")
        result = validator.validate_unit(
            "sensor.power_kw", epic20_mocks.VALID_POWER_UNITS
        )
        assert result.valid is False
        assert result.error_key == "invalid_unit"

    def test_ac_hp_state_mapping_user_defined(self, epic20_mocks: Any) -> None:
        """AC: HP state mapping is user-defined, not hardcoded."""
        # User defines a custom mapping.
        custom_config = {
            "Betrieb": "heating",
            "Kuehlung": "cooling",
            "Warmwasser": "dhw",
            "Aus": "idle",
        }
        mapper = HPModeMapper.from_config(custom_config)

        # German state names map correctly.
        assert mapper.map("Betrieb") == HPOperatingState.HEATING
        assert mapper.map("Kuehlung") == HPOperatingState.COOLING
        assert mapper.map("Warmwasser") == HPOperatingState.DHW
        assert mapper.map("Aus") == HPOperatingState.IDLE

    def test_ac_system_works_with_any_hp_integration(
        self, epic20_mocks: Any
    ) -> None:
        """AC: Multi-brand compatibility -- HeishaMon, Daikin, Nibe, eBUS all work."""
        all_configs = [
            ("HeishaMon", _HEISHAMON_CONFIG),
            ("Daikin", _DAIKIN_CONFIG),
            ("Nibe", _NIBE_CONFIG),
            ("eBUS", _EBUS_CONFIG),
        ]

        for brand_name, config in all_configs:
            mapper = HPModeMapper.from_config(config)

            # Every config must have a heating state that maps to HEATING.
            heating_states = [
                raw
                for raw, target in config.items()
                if target == "heating"
            ]
            assert len(heating_states) >= 1, (
                f"{brand_name}: no heating state in config"
            )

            for raw_state in heating_states:
                op_state = mapper.map(raw_state)
                assert op_state == HPOperatingState.HEATING, (
                    f"{brand_name}: '{raw_state}' did not map to HEATING"
                )
                hp_mode = HPModeMapper.to_heat_pump_mode(op_state)
                assert hp_mode == HeatPumpMode.HEATING

    def test_ac_fallback_on_unavailable_entity(self, epic20_mocks: Any) -> None:
        """AC: Fallback behaviour when entity is unavailable."""
        validator, hass = _make_validator(epic20_mocks)
        hass.states.get.return_value = _make_state(state_value="unavailable")
        result = validator.validate_availability("sensor.hp_state")
        assert result.valid is False
        assert result.error_key == "entity_unavailable"

        # Mapper still falls back gracefully for unknown states.
        mapper = HPModeMapper.from_config(_HEISHAMON_CONFIG)
        op_state = mapper.map("unavailable")
        assert op_state == HPOperatingState.IDLE  # default fallback

        # COP calculator returns fallback constant.
        calc = COPCalculator(mode=COPMode.CONSTANT, default_cop=3.5)
        cop = calc.get_cop(t_outdoor=5.0)
        assert cop == 3.5

    def test_entity_stale_max_seconds_is_300(self, epic20_mocks: Any) -> None:
        """ENTITY_STALE_MAX_SECONDS must be 300 (5 minutes)."""
        assert epic20_mocks.ENTITY_STALE_MAX_SECONDS == 300


# ---------------------------------------------------------------------------
# TestArchitecturalIntegrity
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestArchitecturalIntegrity:
    """Verify DAG dependency direction and no architectural drift."""

    def test_entity_validator_lives_in_custom_components(self) -> None:
        """entity_validator.py must reside in custom_components/pumpahead/."""
        path = _REPO_ROOT / "custom_components" / "pumpahead" / "entity_validator.py"
        assert path.exists(), f"entity_validator.py not found at {path}"

    def test_hp_mode_mapping_lives_in_core_library(self) -> None:
        """hp_mode_mapping.py must reside in pumpahead/ (core library)."""
        path = _REPO_ROOT / "pumpahead" / "hp_mode_mapping.py"
        assert path.exists(), f"hp_mode_mapping.py not found at {path}"

    def test_cop_calculator_lives_in_core_library(self) -> None:
        """cop_calculator.py must reside in pumpahead/ (core library)."""
        path = _REPO_ROOT / "pumpahead" / "cop_calculator.py"
        assert path.exists(), f"cop_calculator.py not found at {path}"

    def test_cop_calculator_does_not_import_hp_mode_mapping(self) -> None:
        """cop_calculator.py must not import hp_mode_mapping."""
        import pumpahead.cop_calculator as mod

        import_lines = _extract_import_lines(mod)
        assert not any("hp_mode_mapping" in line for line in import_lines), (
            "cop_calculator.py must not import hp_mode_mapping"
        )

    def test_hp_mode_mapping_does_not_import_cop_calculator(self) -> None:
        """hp_mode_mapping.py must not import cop_calculator."""
        import pumpahead.hp_mode_mapping as mod

        import_lines = _extract_import_lines(mod)
        assert not any("cop_calculator" in line for line in import_lines), (
            "hp_mode_mapping.py must not import cop_calculator"
        )

    def test_hp_mode_mapping_does_not_import_entity_validator(self) -> None:
        """hp_mode_mapping.py must not import entity_validator."""
        import pumpahead.hp_mode_mapping as mod

        import_lines = _extract_import_lines(mod)
        assert not any("entity_validator" in line for line in import_lines), (
            "hp_mode_mapping.py must not import entity_validator"
        )

    def test_no_homeassistant_imports_in_core_modules(self) -> None:
        """Neither hp_mode_mapping nor cop_calculator imports homeassistant."""
        import pumpahead.cop_calculator as cop_mod
        import pumpahead.hp_mode_mapping as hp_mod

        for mod_name, mod in [
            ("hp_mode_mapping", hp_mod),
            ("cop_calculator", cop_mod),
        ]:
            import_lines = _extract_import_lines(mod)
            assert not any("homeassistant" in line for line in import_lines), (
                f"{mod_name} must not import homeassistant"
            )

    def test_all_epic20_symbols_exported_from_pumpahead_init(self) -> None:
        """All public symbols from epic 20 modules are in pumpahead.__all__."""
        import pumpahead

        expected_symbols = [
            # From hp_mode_mapping.py
            "HPModeMapper",
            "HPOperatingState",
            # From cop_calculator.py
            "COPCalculator",
            "COPMode",
            "COPSample",
            "COP_MIN",
            "COP_MAX",
            "DEFAULT_COP",
            "DEFAULT_T_SUPPLY",
            "MIN_SAMPLES_HOURS",
        ]

        for symbol in expected_symbols:
            assert hasattr(pumpahead, symbol), (
                f"{symbol} not exported from pumpahead.__init__"
            )
            assert symbol in pumpahead.__all__, (
                f"{symbol} not in pumpahead.__all__"
            )

    def test_entity_validator_not_in_core_init(self) -> None:
        """EntityValidator must NOT be exported from pumpahead.__init__."""
        import pumpahead

        assert not hasattr(pumpahead, "EntityValidator"), (
            "EntityValidator must not be in pumpahead (architectural boundary)"
        )
        assert "EntityValidator" not in pumpahead.__all__
