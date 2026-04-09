"""Tests for the PumpAhead EntityValidator.

Uses the same module-scoped mocking pattern as ``test_config_flow.py``
to inject mock ``homeassistant`` modules into ``sys.modules``, import
the entity validator, run tests, and clean up.
"""

from __future__ import annotations

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
def ev_mocks() -> Any:  # noqa: C901
    """Set up mock HA modules, import EntityValidator, yield, clean up."""
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

    # Import the modules under test.
    from custom_components.pumpahead.const import (
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


def _make_validator(ev_mocks: Any) -> tuple[Any, MagicMock]:
    """Create an EntityValidator with a mocked hass.

    Returns ``(validator, hass_mock)`` so the test can configure
    ``hass_mock.states.get``.
    """
    hass = MagicMock()
    validator = ev_mocks.EntityValidator(hass)
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


# ---------------------------------------------------------------------------
# TestValidateUnit
# ---------------------------------------------------------------------------


class TestValidateUnit:
    """Tests for EntityValidator.validate_unit."""

    @pytest.mark.unit
    def test_valid_celsius_unit(self, ev_mocks: Any) -> None:
        """Entity with degC unit must pass validation."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(unit="\u00b0C")
        result = validator.validate_unit("sensor.temp", ev_mocks.VALID_TEMP_UNITS)
        assert result.valid is True

    @pytest.mark.unit
    def test_valid_ascii_c_unit(self, ev_mocks: Any) -> None:
        """Entity with ASCII 'C' unit must pass validation."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(unit="C")
        result = validator.validate_unit("sensor.temp", ev_mocks.VALID_TEMP_UNITS)
        assert result.valid is True

    @pytest.mark.unit
    def test_invalid_unit_fahrenheit(self, ev_mocks: Any) -> None:
        """Entity with degF unit must fail validation."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(unit="\u00b0F")
        result = validator.validate_unit("sensor.temp", ev_mocks.VALID_TEMP_UNITS)
        assert result.valid is False
        assert result.error_key == "invalid_unit"
        assert "sensor.temp" in (result.error_details or "")

    @pytest.mark.unit
    def test_entity_not_found(self, ev_mocks: Any) -> None:
        """Missing entity must return entity_not_found."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = None
        result = validator.validate_unit("sensor.missing", ev_mocks.VALID_TEMP_UNITS)
        assert result.valid is False
        assert result.error_key == "entity_not_found"

    @pytest.mark.unit
    def test_entity_with_no_unit_accepted(self, ev_mocks: Any) -> None:
        """Entity without unit_of_measurement must be accepted."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(unit=None)
        result = validator.validate_unit("number.valve", ev_mocks.VALID_PERCENT_UNITS)
        assert result.valid is True

    @pytest.mark.unit
    def test_empty_entity_id_returns_valid(self, ev_mocks: Any) -> None:
        """Empty entity_id must return valid (skip validation)."""
        validator, _hass = _make_validator(ev_mocks)
        result = validator.validate_unit("", ev_mocks.VALID_TEMP_UNITS)
        assert result.valid is True

    @pytest.mark.unit
    def test_valid_percent_unit(self, ev_mocks: Any) -> None:
        """Entity with % unit must pass validation."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(unit="%")
        result = validator.validate_unit(
            "sensor.humidity", ev_mocks.VALID_PERCENT_UNITS
        )
        assert result.valid is True

    @pytest.mark.unit
    def test_valid_power_unit(self, ev_mocks: Any) -> None:
        """Entity with W unit must pass validation."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(unit="W")
        result = validator.validate_unit("sensor.power", ev_mocks.VALID_POWER_UNITS)
        assert result.valid is True


# ---------------------------------------------------------------------------
# TestValidateDeviceClass
# ---------------------------------------------------------------------------


class TestValidateDeviceClass:
    """Tests for EntityValidator.validate_device_class."""

    @pytest.mark.unit
    def test_matching_device_class(self, ev_mocks: Any) -> None:
        """Entity with matching device_class must pass."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(device_class="temperature")
        result = validator.validate_device_class("sensor.temp", "temperature")
        assert result.valid is True

    @pytest.mark.unit
    def test_mismatching_device_class(self, ev_mocks: Any) -> None:
        """Entity with wrong device_class must fail."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(device_class="humidity")
        result = validator.validate_device_class("sensor.temp", "temperature")
        assert result.valid is False
        assert result.error_key == "invalid_device_class"
        assert "humidity" in (result.error_details or "")
        assert "temperature" in (result.error_details or "")

    @pytest.mark.unit
    def test_no_device_class_accepted(self, ev_mocks: Any) -> None:
        """Entity without device_class attribute must be accepted."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(device_class=None)
        result = validator.validate_device_class("number.valve", "temperature")
        assert result.valid is True

    @pytest.mark.unit
    def test_entity_not_found(self, ev_mocks: Any) -> None:
        """Missing entity must return entity_not_found."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = None
        result = validator.validate_device_class("sensor.missing", "temperature")
        assert result.valid is False
        assert result.error_key == "entity_not_found"

    @pytest.mark.unit
    def test_empty_entity_id_returns_valid(self, ev_mocks: Any) -> None:
        """Empty entity_id must return valid."""
        validator, _hass = _make_validator(ev_mocks)
        result = validator.validate_device_class("", "temperature")
        assert result.valid is True


# ---------------------------------------------------------------------------
# TestValidateAvailability
# ---------------------------------------------------------------------------


class TestValidateAvailability:
    """Tests for EntityValidator.validate_availability."""

    @pytest.mark.unit
    def test_available_entity(self, ev_mocks: Any) -> None:
        """Available entity must pass."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(state_value="21.5")
        result = validator.validate_availability("sensor.temp")
        assert result.valid is True

    @pytest.mark.unit
    def test_unavailable_entity(self, ev_mocks: Any) -> None:
        """Unavailable entity must fail with entity_unavailable."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(state_value="unavailable")
        result = validator.validate_availability("sensor.temp")
        assert result.valid is False
        assert result.error_key == "entity_unavailable"

    @pytest.mark.unit
    def test_unknown_entity_state(self, ev_mocks: Any) -> None:
        """Unknown entity state must fail with entity_unavailable."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(state_value="unknown")
        result = validator.validate_availability("sensor.temp")
        assert result.valid is False
        assert result.error_key == "entity_unavailable"

    @pytest.mark.unit
    def test_missing_entity(self, ev_mocks: Any) -> None:
        """Missing entity must return entity_not_found."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = None
        result = validator.validate_availability("sensor.missing")
        assert result.valid is False
        assert result.error_key == "entity_not_found"

    @pytest.mark.unit
    def test_empty_entity_id_returns_valid(self, ev_mocks: Any) -> None:
        """Empty entity_id must return valid."""
        validator, _hass = _make_validator(ev_mocks)
        result = validator.validate_availability("")
        assert result.valid is True


# ---------------------------------------------------------------------------
# TestValidateEntity (composite)
# ---------------------------------------------------------------------------


class TestValidateEntity:
    """Tests for EntityValidator.validate_entity (composite check)."""

    @pytest.mark.unit
    def test_full_valid_entity(self, ev_mocks: Any) -> None:
        """Entity passing all checks must return valid."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(
            state_value="21.5", unit="\u00b0C", device_class="temperature"
        )
        result = validator.validate_entity(
            "sensor.temp",
            valid_units=ev_mocks.VALID_TEMP_UNITS,
            expected_device_class="temperature",
        )
        assert result.valid is True

    @pytest.mark.unit
    def test_entity_not_found(self, ev_mocks: Any) -> None:
        """Non-existent entity must fail with entity_not_found."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = None
        result = validator.validate_entity(
            "sensor.missing", valid_units=ev_mocks.VALID_TEMP_UNITS
        )
        assert result.valid is False
        assert result.error_key == "entity_not_found"

    @pytest.mark.unit
    def test_unavailable_entity_still_validates_units(self, ev_mocks: Any) -> None:
        """Unavailable entity logs warning but still checks unit/device_class."""
        validator, hass = _make_validator(ev_mocks)
        state = _make_state(
            state_value="unavailable", unit="\u00b0C", device_class="temperature"
        )
        hass.states.get.return_value = state
        result = validator.validate_entity(
            "sensor.temp",
            valid_units=ev_mocks.VALID_TEMP_UNITS,
            expected_device_class="temperature",
        )
        # Unit and device_class are correct, so this should be valid
        # despite the availability warning.
        assert result.valid is True

    @pytest.mark.unit
    def test_bad_device_class_blocks(self, ev_mocks: Any) -> None:
        """Wrong device_class must block validation."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(
            device_class="humidity", unit="\u00b0C"
        )
        result = validator.validate_entity(
            "sensor.temp",
            valid_units=ev_mocks.VALID_TEMP_UNITS,
            expected_device_class="temperature",
        )
        assert result.valid is False
        assert result.error_key == "invalid_device_class"

    @pytest.mark.unit
    def test_bad_unit_blocks(self, ev_mocks: Any) -> None:
        """Wrong unit must block validation."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(
            unit="\u00b0F", device_class="temperature"
        )
        result = validator.validate_entity(
            "sensor.temp",
            valid_units=ev_mocks.VALID_TEMP_UNITS,
            expected_device_class="temperature",
        )
        assert result.valid is False
        assert result.error_key == "invalid_unit"

    @pytest.mark.unit
    def test_empty_entity_id_returns_valid(self, ev_mocks: Any) -> None:
        """Empty entity_id must return valid."""
        validator, _hass = _make_validator(ev_mocks)
        result = validator.validate_entity("", valid_units=ev_mocks.VALID_TEMP_UNITS)
        assert result.valid is True

    @pytest.mark.unit
    def test_existence_only_check(self, ev_mocks: Any) -> None:
        """Entity check without unit or device_class must only check existence."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(unit=None, device_class=None)
        result = validator.validate_entity("number.valve")
        assert result.valid is True

    @pytest.mark.unit
    def test_no_unit_no_device_class_attributes_accepted(self, ev_mocks: Any) -> None:
        """Entity with no attributes must pass when no checks requested."""
        validator, hass = _make_validator(ev_mocks)
        state = MagicMock()
        state.state = "45.0"
        state.attributes = {}
        hass.states.get.return_value = state
        result = validator.validate_entity("number.valve")
        assert result.valid is True

    @pytest.mark.unit
    def test_device_class_check_skipped_when_none(self, ev_mocks: Any) -> None:
        """Device class check must be skipped when expected_device_class is None."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(
            device_class="humidity", unit="\u00b0C"
        )
        # No expected_device_class -> should not fail on device_class mismatch.
        result = validator.validate_entity(
            "sensor.temp", valid_units=ev_mocks.VALID_TEMP_UNITS
        )
        assert result.valid is True

    @pytest.mark.unit
    def test_unit_check_skipped_when_none(self, ev_mocks: Any) -> None:
        """Unit check must be skipped when valid_units is None."""
        validator, hass = _make_validator(ev_mocks)
        hass.states.get.return_value = _make_state(unit="\u00b0F")
        # No valid_units -> should not fail on unit mismatch.
        result = validator.validate_entity("sensor.temp")
        assert result.valid is True
