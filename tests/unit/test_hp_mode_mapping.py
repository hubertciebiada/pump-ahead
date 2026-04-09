"""Tests for the HP mode mapping module.

Tests the ``HPOperatingState`` enum, ``HPModeMapper`` class, and the
``from_config`` factory method.  No HA dependencies — pure core
library testing.
"""

from __future__ import annotations

import logging

import pytest

from pumpahead.hp_mode_mapping import HPModeMapper, HPOperatingState
from pumpahead.simulator import HeatPumpMode

# ---------------------------------------------------------------------------
# TestHPOperatingState
# ---------------------------------------------------------------------------


class TestHPOperatingState:
    """Verify enum members and their string values."""

    @pytest.mark.unit
    def test_enum_members_exist(self) -> None:
        """All expected enum members must be present."""
        assert HPOperatingState.HEATING is not None
        assert HPOperatingState.COOLING is not None
        assert HPOperatingState.DHW is not None
        assert HPOperatingState.IDLE is not None
        assert HPOperatingState.DEFROST is not None

    @pytest.mark.unit
    def test_enum_values(self) -> None:
        """Enum values must match expected strings."""
        assert HPOperatingState.HEATING.value == "heating"
        assert HPOperatingState.COOLING.value == "cooling"
        assert HPOperatingState.DHW.value == "dhw"
        assert HPOperatingState.IDLE.value == "idle"
        assert HPOperatingState.DEFROST.value == "defrost"

    @pytest.mark.unit
    def test_enum_has_five_members(self) -> None:
        """Exactly five members must exist."""
        assert len(HPOperatingState) == 5


# ---------------------------------------------------------------------------
# TestHPModeMapper
# ---------------------------------------------------------------------------


class TestHPModeMapper:
    """Tests for the HPModeMapper class."""

    @pytest.mark.unit
    def test_basic_mapping(self) -> None:
        """Exact-match lookup must return the correct state."""
        mapper = HPModeMapper(
            {
                "Heat": HPOperatingState.HEATING,
                "Cool": HPOperatingState.COOLING,
                "DHW": HPOperatingState.DHW,
            }
        )
        assert mapper.map("Heat") == HPOperatingState.HEATING
        assert mapper.map("Cool") == HPOperatingState.COOLING
        assert mapper.map("DHW") == HPOperatingState.DHW

    @pytest.mark.unit
    def test_case_insensitive(self) -> None:
        """Mapping must be case-insensitive."""
        mapper = HPModeMapper({"Heat": HPOperatingState.HEATING})
        assert mapper.map("heat") == HPOperatingState.HEATING
        assert mapper.map("HEAT") == HPOperatingState.HEATING
        assert mapper.map("Heat") == HPOperatingState.HEATING
        assert mapper.map("hEaT") == HPOperatingState.HEATING

    @pytest.mark.unit
    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace must be stripped."""
        mapper = HPModeMapper({"Heat": HPOperatingState.HEATING})
        assert mapper.map("  Heat  ") == HPOperatingState.HEATING
        assert mapper.map("\tHeat\n") == HPOperatingState.HEATING

    @pytest.mark.unit
    def test_unknown_state_returns_default_idle(self) -> None:
        """Unknown state must return IDLE by default."""
        mapper = HPModeMapper({"Heat": HPOperatingState.HEATING})
        assert mapper.map("SomeUnknownState") == HPOperatingState.IDLE

    @pytest.mark.unit
    def test_unknown_state_custom_default(self) -> None:
        """Unknown state must return the configured custom default."""
        mapper = HPModeMapper(
            {"Heat": HPOperatingState.HEATING},
            default=HPOperatingState.DEFROST,
        )
        assert mapper.map("Unknown") == HPOperatingState.DEFROST

    @pytest.mark.unit
    def test_unknown_state_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Unknown state must log a warning with the raw value."""
        mapper = HPModeMapper({"Heat": HPOperatingState.HEATING})
        with caplog.at_level(logging.WARNING, logger="pumpahead.hp_mode_mapping"):
            result = mapper.map("SomeUnknownState")
        assert result == HPOperatingState.IDLE
        assert "Unknown HP state 'SomeUnknownState'" in caplog.text
        assert "idle" in caplog.text

    @pytest.mark.unit
    def test_empty_mapping(self) -> None:
        """Empty mapping dict must map all states to IDLE."""
        mapper = HPModeMapper({})
        assert mapper.map("Heat") == HPOperatingState.IDLE
        assert mapper.map("Cool") == HPOperatingState.IDLE

    @pytest.mark.unit
    def test_heishamon_mapping(self) -> None:
        """Simulate HeishaMon integration states."""
        mapper = HPModeMapper(
            {
                "Heat": HPOperatingState.HEATING,
                "Cool": HPOperatingState.COOLING,
                "DHW": HPOperatingState.DHW,
                "Off": HPOperatingState.IDLE,
                "Defrost": HPOperatingState.DEFROST,
            }
        )
        assert mapper.map("Heat") == HPOperatingState.HEATING
        assert mapper.map("Cool") == HPOperatingState.COOLING
        assert mapper.map("DHW") == HPOperatingState.DHW
        assert mapper.map("Off") == HPOperatingState.IDLE
        assert mapper.map("Defrost") == HPOperatingState.DEFROST

    @pytest.mark.unit
    def test_daikin_mapping(self) -> None:
        """Simulate Daikin integration states (lowercase)."""
        mapper = HPModeMapper(
            {
                "heating": HPOperatingState.HEATING,
                "cooling": HPOperatingState.COOLING,
                "idle": HPOperatingState.IDLE,
            }
        )
        assert mapper.map("heating") == HPOperatingState.HEATING
        assert mapper.map("cooling") == HPOperatingState.COOLING
        assert mapper.map("idle") == HPOperatingState.IDLE

    @pytest.mark.unit
    def test_nibe_mapping(self) -> None:
        """Simulate Nibe integration states (numeric strings)."""
        mapper = HPModeMapper(
            {
                "30": HPOperatingState.HEATING,
                "40": HPOperatingState.COOLING,
                "50": HPOperatingState.DHW,
                "0": HPOperatingState.IDLE,
            }
        )
        assert mapper.map("30") == HPOperatingState.HEATING
        assert mapper.map("40") == HPOperatingState.COOLING
        assert mapper.map("50") == HPOperatingState.DHW
        assert mapper.map("0") == HPOperatingState.IDLE

    @pytest.mark.unit
    def test_ebus_mapping(self) -> None:
        """Simulate eBUS integration states with different format."""
        mapper = HPModeMapper(
            {
                "CH": HPOperatingState.HEATING,
                "DHW_ACTIVE": HPOperatingState.DHW,
                "STANDBY": HPOperatingState.IDLE,
            }
        )
        assert mapper.map("CH") == HPOperatingState.HEATING
        assert mapper.map("DHW_ACTIVE") == HPOperatingState.DHW
        assert mapper.map("STANDBY") == HPOperatingState.IDLE


# ---------------------------------------------------------------------------
# TestToHeatPumpMode
# ---------------------------------------------------------------------------


class TestToHeatPumpMode:
    """Tests for HPOperatingState -> HeatPumpMode conversion."""

    @pytest.mark.unit
    def test_heating_maps_to_heating(self) -> None:
        result = HPModeMapper.to_heat_pump_mode(HPOperatingState.HEATING)
        assert result == HeatPumpMode.HEATING

    @pytest.mark.unit
    def test_cooling_maps_to_cooling(self) -> None:
        result = HPModeMapper.to_heat_pump_mode(HPOperatingState.COOLING)
        assert result == HeatPumpMode.COOLING

    @pytest.mark.unit
    def test_dhw_maps_to_off(self) -> None:
        result = HPModeMapper.to_heat_pump_mode(HPOperatingState.DHW)
        assert result == HeatPumpMode.OFF

    @pytest.mark.unit
    def test_idle_maps_to_off(self) -> None:
        result = HPModeMapper.to_heat_pump_mode(HPOperatingState.IDLE)
        assert result == HeatPumpMode.OFF

    @pytest.mark.unit
    def test_defrost_maps_to_off(self) -> None:
        result = HPModeMapper.to_heat_pump_mode(HPOperatingState.DEFROST)
        assert result == HeatPumpMode.OFF


# ---------------------------------------------------------------------------
# TestFromConfig
# ---------------------------------------------------------------------------


class TestFromConfig:
    """Tests for the from_config factory method."""

    @pytest.mark.unit
    def test_from_config_valid(self) -> None:
        """Valid config dict must create a working mapper."""
        mapper = HPModeMapper.from_config({"Heat": "heating", "Cool": "cooling"})
        assert mapper.map("Heat") == HPOperatingState.HEATING
        assert mapper.map("Cool") == HPOperatingState.COOLING

    @pytest.mark.unit
    def test_from_config_all_states(self) -> None:
        """Config with all five states must work."""
        config = {
            "Heat": "heating",
            "Cool": "cooling",
            "DHW": "dhw",
            "Off": "idle",
            "Defrost": "defrost",
        }
        mapper = HPModeMapper.from_config(config)
        assert mapper.map("Heat") == HPOperatingState.HEATING
        assert mapper.map("Defrost") == HPOperatingState.DEFROST

    @pytest.mark.unit
    def test_from_config_invalid_value(self) -> None:
        """Invalid target value must raise ValueError."""
        with pytest.raises(
            ValueError, match="Invalid HP operating state 'nonexistent'"
        ):
            HPModeMapper.from_config({"Heat": "nonexistent"})

    @pytest.mark.unit
    def test_from_config_roundtrip(self) -> None:
        """Build mapper, serialize to config, reconstruct, verify same behaviour."""
        original_mapping = {
            "Heat": HPOperatingState.HEATING,
            "Cool": HPOperatingState.COOLING,
            "DHW": HPOperatingState.DHW,
        }
        original_mapper = HPModeMapper(original_mapping)

        # Serialize to config dict (string values).
        config = {k: v.value for k, v in original_mapping.items()}

        # Reconstruct.
        reconstructed = HPModeMapper.from_config(config)

        # Verify same behaviour.
        for raw_state in ("Heat", "Cool", "DHW"):
            assert original_mapper.map(raw_state) == reconstructed.map(raw_state)

    @pytest.mark.unit
    def test_from_config_empty(self) -> None:
        """Empty config dict must create a mapper that maps everything to IDLE."""
        mapper = HPModeMapper.from_config({})
        assert mapper.map("anything") == HPOperatingState.IDLE
