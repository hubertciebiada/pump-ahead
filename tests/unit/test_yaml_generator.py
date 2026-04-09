"""Unit tests for safety YAML automation generator.

Tests cover dataclass validation, YAML validity (round-trip through
``yaml.safe_load``), correct automation count, entity_id
substitution, threshold values, template triggers, split/no-split
variations, unique automation IDs, and custom threshold overrides.
"""

from __future__ import annotations

import pytest
import yaml

from pumpahead.safety_rules import (
    S1_FLOOR_OVERHEAT,
    S3_EMERGENCY_HEAT,
    S4_EMERGENCY_COOL,
    S5_WATCHDOG,
)
from pumpahead.safety_yaml_generator import (
    RoomEntityConfig,
    SafetyYAMLConfig,
    generate_safety_yaml,
    generate_safety_yaml_for_room,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_room(
    *,
    room_name: str = "Living Room",
    entity_split: str | None = "climate.living_room_split",
) -> RoomEntityConfig:
    """Create a room entity config with sensible defaults."""
    return RoomEntityConfig(
        room_name=room_name,
        entity_temp_floor="sensor.living_room_floor_temp",
        entity_temp_room="sensor.living_room_temp",
        entity_humidity="sensor.living_room_humidity",
        entity_valve="number.living_room_valve",
        entity_split=entity_split,
    )


def _make_config(
    rooms: tuple[RoomEntityConfig, ...] | None = None,
    **kwargs: object,
) -> SafetyYAMLConfig:
    """Create a safety YAML config with defaults."""
    if rooms is None:
        rooms = (_make_room(),)
    return SafetyYAMLConfig(rooms=rooms, **kwargs)


def _parse_yaml(yaml_str: str) -> list[dict[str, object]]:
    """Parse a YAML string and return the list of automation dicts."""
    result = yaml.safe_load(yaml_str)
    assert isinstance(result, list)
    return result


# ---------------------------------------------------------------------------
# RoomEntityConfig validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRoomEntityConfig:
    """RoomEntityConfig frozen dataclass validation tests."""

    def test_valid_room(self) -> None:
        """Valid room config with split."""
        room = _make_room()
        assert room.room_name == "Living Room"
        assert room.entity_split == "climate.living_room_split"

    def test_valid_room_without_split(self) -> None:
        """Valid room config without split."""
        room = _make_room(entity_split=None)
        assert room.entity_split is None

    def test_empty_room_name_raises(self) -> None:
        """Empty room name raises ValueError."""
        with pytest.raises(ValueError, match="room_name must be non-empty"):
            RoomEntityConfig(
                room_name="",
                entity_temp_floor="sensor.floor",
                entity_temp_room="sensor.room",
                entity_humidity="sensor.humidity",
                entity_valve="number.valve",
            )

    def test_whitespace_room_name_raises(self) -> None:
        """Whitespace-only room name raises ValueError."""
        with pytest.raises(ValueError, match="room_name must be non-empty"):
            RoomEntityConfig(
                room_name="   ",
                entity_temp_floor="sensor.floor",
                entity_temp_room="sensor.room",
                entity_humidity="sensor.humidity",
                entity_valve="number.valve",
            )

    def test_empty_entity_temp_floor_raises(self) -> None:
        """Empty entity_temp_floor raises ValueError."""
        with pytest.raises(ValueError, match="entity_temp_floor must be non-empty"):
            RoomEntityConfig(
                room_name="Room",
                entity_temp_floor="",
                entity_temp_room="sensor.room",
                entity_humidity="sensor.humidity",
                entity_valve="number.valve",
            )

    def test_empty_entity_temp_room_raises(self) -> None:
        """Empty entity_temp_room raises ValueError."""
        with pytest.raises(ValueError, match="entity_temp_room must be non-empty"):
            RoomEntityConfig(
                room_name="Room",
                entity_temp_floor="sensor.floor",
                entity_temp_room="",
                entity_humidity="sensor.humidity",
                entity_valve="number.valve",
            )

    def test_empty_entity_humidity_raises(self) -> None:
        """Empty entity_humidity raises ValueError."""
        with pytest.raises(ValueError, match="entity_humidity must be non-empty"):
            RoomEntityConfig(
                room_name="Room",
                entity_temp_floor="sensor.floor",
                entity_temp_room="sensor.room",
                entity_humidity="",
                entity_valve="number.valve",
            )

    def test_empty_entity_valve_raises(self) -> None:
        """Empty entity_valve raises ValueError."""
        with pytest.raises(ValueError, match="entity_valve must be non-empty"):
            RoomEntityConfig(
                room_name="Room",
                entity_temp_floor="sensor.floor",
                entity_temp_room="sensor.room",
                entity_humidity="sensor.humidity",
                entity_valve="",
            )

    def test_frozen(self) -> None:
        """RoomEntityConfig is frozen (immutable)."""
        room = _make_room()
        with pytest.raises(AttributeError):
            room.room_name = "New Name"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SafetyYAMLConfig validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSafetyYAMLConfig:
    """SafetyYAMLConfig frozen dataclass validation tests."""

    def test_valid_config(self) -> None:
        """Valid config with default thresholds."""
        config = _make_config()
        assert len(config.rooms) == 1
        assert config.s1_threshold_on == S1_FLOOR_OVERHEAT.threshold_on

    def test_empty_rooms_raises(self) -> None:
        """Empty rooms tuple raises ValueError."""
        with pytest.raises(ValueError, match="rooms must be non-empty"):
            SafetyYAMLConfig(rooms=())

    def test_duplicate_room_names_raises(self) -> None:
        """Duplicate room names raise ValueError."""
        room = _make_room()
        room2 = RoomEntityConfig(
            room_name="Living Room",
            entity_temp_floor="sensor.other_floor",
            entity_temp_room="sensor.other_room",
            entity_humidity="sensor.other_humidity",
            entity_valve="number.other_valve",
        )
        with pytest.raises(ValueError, match="room names must be unique"):
            SafetyYAMLConfig(rooms=(room, room2))

    def test_s1_invalid_threshold_relationship_raises(self) -> None:
        """S1 threshold_off > threshold_on raises ValueError."""
        with pytest.raises(ValueError, match="S1"):
            _make_config(s1_threshold_on=34.0, s1_threshold_off=35.0)

    def test_s3_invalid_threshold_relationship_raises(self) -> None:
        """S3 threshold_off < threshold_on raises ValueError."""
        with pytest.raises(ValueError, match="S3"):
            _make_config(s3_threshold_on=5.0, s3_threshold_off=4.0)

    def test_s4_invalid_threshold_relationship_raises(self) -> None:
        """S4 threshold_off > threshold_on raises ValueError."""
        with pytest.raises(ValueError, match="S4"):
            _make_config(s4_threshold_on=35.0, s4_threshold_off=36.0)

    def test_s5_invalid_threshold_relationship_raises(self) -> None:
        """S5 threshold_off > threshold_on raises ValueError."""
        with pytest.raises(ValueError, match="S5"):
            _make_config(s5_threshold_on=15.0, s5_threshold_off=16.0)

    def test_frozen(self) -> None:
        """SafetyYAMLConfig is frozen (immutable)."""
        config = _make_config()
        with pytest.raises(AttributeError):
            config.s1_threshold_on = 99.0  # type: ignore[misc]

    def test_default_thresholds_match_safety_rules(self) -> None:
        """Default thresholds match safety_rules.py constants."""
        config = _make_config()
        assert config.s1_threshold_on == S1_FLOOR_OVERHEAT.threshold_on
        assert config.s1_threshold_off == S1_FLOOR_OVERHEAT.threshold_off
        assert config.s3_threshold_on == S3_EMERGENCY_HEAT.threshold_on
        assert config.s3_threshold_off == S3_EMERGENCY_HEAT.threshold_off
        assert config.s4_threshold_on == S4_EMERGENCY_COOL.threshold_on
        assert config.s4_threshold_off == S4_EMERGENCY_COOL.threshold_off
        assert config.s5_threshold_on == S5_WATCHDOG.threshold_on
        assert config.s5_threshold_off == S5_WATCHDOG.threshold_off


# ---------------------------------------------------------------------------
# YAML validity (round-trip)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestYAMLValidity:
    """Generated YAML is valid and round-trips through yaml.safe_load."""

    def test_single_room_yaml_is_valid(self) -> None:
        """Single room generates valid YAML."""
        config = _make_config()
        yaml_str = generate_safety_yaml(config)
        parsed = _parse_yaml(yaml_str)
        assert isinstance(parsed, list)
        assert all(isinstance(a, dict) for a in parsed)

    def test_multi_room_yaml_is_valid(self) -> None:
        """Multiple rooms generate valid YAML."""
        rooms = (
            _make_room(room_name="Living Room"),
            RoomEntityConfig(
                room_name="Bedroom",
                entity_temp_floor="sensor.bedroom_floor",
                entity_temp_room="sensor.bedroom_temp",
                entity_humidity="sensor.bedroom_humidity",
                entity_valve="number.bedroom_valve",
                entity_split="climate.bedroom_split",
            ),
        )
        config = _make_config(rooms=rooms)
        yaml_str = generate_safety_yaml(config)
        parsed = _parse_yaml(yaml_str)
        assert isinstance(parsed, list)

    def test_room_only_yaml_is_valid(self) -> None:
        """generate_safety_yaml_for_room produces valid YAML."""
        room = _make_room()
        config = _make_config()
        yaml_str = generate_safety_yaml_for_room(room, config)
        parsed = _parse_yaml(yaml_str)
        assert isinstance(parsed, list)

    def test_no_split_yaml_is_valid(self) -> None:
        """Room without split generates valid YAML."""
        room = _make_room(entity_split=None)
        config = _make_config(rooms=(room,))
        yaml_str = generate_safety_yaml(config)
        parsed = _parse_yaml(yaml_str)
        assert isinstance(parsed, list)


# ---------------------------------------------------------------------------
# Automation count
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAutomationCount:
    """Correct number of automations generated."""

    def test_single_room_count(self) -> None:
        """Single room: 8 per-room (S1-S4 x trigger+clear) + 2 S5 = 10."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        assert len(parsed) == 10

    def test_two_room_count(self) -> None:
        """Two rooms: 8 * 2 per-room + 2 S5 = 18."""
        rooms = (
            _make_room(room_name="Living Room"),
            RoomEntityConfig(
                room_name="Bedroom",
                entity_temp_floor="sensor.bedroom_floor",
                entity_temp_room="sensor.bedroom_temp",
                entity_humidity="sensor.bedroom_humidity",
                entity_valve="number.bedroom_valve",
            ),
        )
        config = _make_config(rooms=rooms)
        parsed = _parse_yaml(generate_safety_yaml(config))
        assert len(parsed) == 18

    def test_room_only_count(self) -> None:
        """generate_safety_yaml_for_room: 8 automations (no S5)."""
        room = _make_room()
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml_for_room(room, config))
        assert len(parsed) == 8

    def test_three_room_count(self) -> None:
        """Three rooms: 8 * 3 + 2 = 26."""
        rooms = (
            _make_room(room_name="Room A"),
            RoomEntityConfig(
                room_name="Room B",
                entity_temp_floor="sensor.b_floor",
                entity_temp_room="sensor.b_temp",
                entity_humidity="sensor.b_humidity",
                entity_valve="number.b_valve",
            ),
            RoomEntityConfig(
                room_name="Room C",
                entity_temp_floor="sensor.c_floor",
                entity_temp_room="sensor.c_temp",
                entity_humidity="sensor.c_humidity",
                entity_valve="number.c_valve",
            ),
        )
        config = _make_config(rooms=rooms)
        parsed = _parse_yaml(generate_safety_yaml(config))
        assert len(parsed) == 26


# ---------------------------------------------------------------------------
# Entity ID substitution
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEntitySubstitution:
    """Entity IDs from config appear in the generated YAML."""

    def test_s1_trigger_has_floor_entity(self) -> None:
        """S1 trigger references the floor temperature entity."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s1_trigger = parsed[0]
        trigger = s1_trigger["trigger"]
        assert isinstance(trigger, list)
        assert trigger[0]["entity_id"] == "sensor.living_room_floor_temp"

    def test_s1_action_has_valve_entity(self) -> None:
        """S1 trigger action references the valve entity."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s1_trigger = parsed[0]
        action = s1_trigger["action"]
        assert isinstance(action, list)
        assert action[0]["target"]["entity_id"] == "number.living_room_valve"

    def test_s2_template_has_all_entities(self) -> None:
        """S2 template trigger references floor, room, and humidity entities."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_trigger = parsed[2]  # After S1 trigger + S1 clear
        trigger = s2_trigger["trigger"]
        assert isinstance(trigger, list)
        template = trigger[0]["value_template"]
        assert "sensor.living_room_floor_temp" in template
        assert "sensor.living_room_temp" in template
        assert "sensor.living_room_humidity" in template

    def test_s3_has_split_entity_when_present(self) -> None:
        """S3 trigger includes split entity when room has a split."""
        room = _make_room(entity_split="climate.my_split")
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s3_trigger = parsed[4]  # After S1(2) + S2(2)
        action = s3_trigger["action"]
        assert isinstance(action, list)
        split_actions = [
            a
            for a in action
            if isinstance(a.get("service"), str)
            and a["service"] == "climate.set_hvac_mode"
        ]
        assert len(split_actions) == 1
        assert split_actions[0]["target"]["entity_id"] == "climate.my_split"

    def test_s3_no_split_entity_when_absent(self) -> None:
        """S3 trigger omits split actions when room has no split."""
        room = _make_room(entity_split=None)
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s3_trigger = parsed[4]  # After S1(2) + S2(2)
        action = s3_trigger["action"]
        assert isinstance(action, list)
        split_actions = [
            a
            for a in action
            if isinstance(a.get("service"), str)
            and a["service"] == "climate.set_hvac_mode"
        ]
        assert len(split_actions) == 0

    def test_s4_has_split_entity_when_present(self) -> None:
        """S4 trigger includes split entity when room has a split."""
        room = _make_room(entity_split="climate.my_split")
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s4_trigger = parsed[6]  # After S1(2) + S2(2) + S3(2)
        action = s4_trigger["action"]
        assert isinstance(action, list)
        split_actions = [
            a
            for a in action
            if isinstance(a.get("service"), str)
            and a["service"] == "climate.set_hvac_mode"
        ]
        assert len(split_actions) == 1
        assert split_actions[0]["data"]["hvac_mode"] == "cool"

    def test_s4_no_split_entity_when_absent(self) -> None:
        """S4 trigger has valve-close only when room has no split."""
        room = _make_room(entity_split=None)
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s4_trigger = parsed[6]  # After S1(2) + S2(2) + S3(2)
        action = s4_trigger["action"]
        assert isinstance(action, list)
        split_actions = [
            a
            for a in action
            if isinstance(a.get("service"), str)
            and a["service"] == "climate.set_hvac_mode"
        ]
        assert len(split_actions) == 0

    def test_s5_watchdog_has_last_update_entity(self) -> None:
        """S5 watchdog trigger references PumpAhead last update entity."""
        config = _make_config(
            entity_pumpahead_last_update="sensor.pa_last_update",
        )
        parsed = _parse_yaml(generate_safety_yaml(config))
        s5_trigger = parsed[-2]  # Second to last
        trigger = s5_trigger["trigger"]
        assert isinstance(trigger, list)
        template = trigger[0]["value_template"]
        assert "sensor.pa_last_update" in template


# ---------------------------------------------------------------------------
# Threshold values in triggers
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestThresholdValues:
    """Threshold values appear correctly in triggers."""

    def test_s1_default_thresholds(self) -> None:
        """S1 uses default 34C trigger, 33C clear."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s1_trigger = parsed[0]
        s1_clear = parsed[1]
        assert s1_trigger["trigger"][0]["above"] == 34.0
        assert s1_clear["trigger"][0]["below"] == 33.0

    def test_s1_custom_thresholds(self) -> None:
        """S1 with custom thresholds."""
        config = _make_config(s1_threshold_on=32.0, s1_threshold_off=31.0)
        parsed = _parse_yaml(generate_safety_yaml(config))
        s1_trigger = parsed[0]
        s1_clear = parsed[1]
        assert s1_trigger["trigger"][0]["above"] == 32.0
        assert s1_clear["trigger"][0]["below"] == 31.0

    def test_s3_default_thresholds(self) -> None:
        """S3 uses default 5C trigger, 6C clear."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s3_trigger = parsed[4]
        s3_clear = parsed[5]
        assert s3_trigger["trigger"][0]["below"] == 5.0
        assert s3_clear["trigger"][0]["above"] == 6.0

    def test_s4_default_thresholds(self) -> None:
        """S4 uses default 35C trigger, 34C clear."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s4_trigger = parsed[6]
        s4_clear = parsed[7]
        assert s4_trigger["trigger"][0]["above"] == 35.0
        assert s4_clear["trigger"][0]["below"] == 34.0

    def test_s5_default_thresholds_in_template(self) -> None:
        """S5 template contains the correct threshold values."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s5_trigger = parsed[-2]
        s5_clear = parsed[-1]
        trigger_template = s5_trigger["trigger"][0]["value_template"]
        clear_template = s5_clear["trigger"][0]["value_template"]
        assert "15.0" in trigger_template
        assert "5.0" in clear_template

    def test_s5_custom_thresholds_in_template(self) -> None:
        """S5 template with custom thresholds."""
        config = _make_config(s5_threshold_on=20.0, s5_threshold_off=3.0)
        parsed = _parse_yaml(generate_safety_yaml(config))
        s5_trigger = parsed[-2]
        s5_clear = parsed[-1]
        trigger_template = s5_trigger["trigger"][0]["value_template"]
        clear_template = s5_clear["trigger"][0]["value_template"]
        assert "20.0" in trigger_template
        assert "3.0" in clear_template


# ---------------------------------------------------------------------------
# S2 condensation template trigger
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestS2CondensationTemplate:
    """S2 condensation uses template trigger with dew point formula."""

    def test_s2_trigger_has_dew_point_formula(self) -> None:
        """S2 trigger template computes dew point using Magnus formula."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_trigger = parsed[2]
        template = s2_trigger["trigger"][0]["value_template"]
        # Magnus formula: t_dew = t_room - (100 - rh) / 5
        assert "(100 - rh) / 5" in template

    def test_s2_clear_has_dew_point_formula(self) -> None:
        """S2 clear template also computes dew point."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_clear = parsed[3]
        template = s2_clear["trigger"][0]["value_template"]
        assert "(100 - rh) / 5" in template

    def test_s2_trigger_uses_template_platform(self) -> None:
        """S2 uses template platform, not numeric_state."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_trigger = parsed[2]
        assert s2_trigger["trigger"][0]["platform"] == "template"

    def test_s2_condensation_margin_in_template(self) -> None:
        """S2 trigger includes the condensation margin."""
        config = _make_config(s2_condensation_margin=3.0)
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_trigger = parsed[2]
        template = s2_trigger["trigger"][0]["value_template"]
        assert "t_dew + 3.0" in template

    def test_s2_action_closes_valve(self) -> None:
        """S2 trigger action closes the valve."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_trigger = parsed[2]
        action = s2_trigger["action"]
        assert isinstance(action, list)
        valve_action = action[0]
        assert valve_action["service"] == "number.set_value"
        assert valve_action["data"]["value"] == 0


# ---------------------------------------------------------------------------
# S5 watchdog (global, not per-room)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestS5Watchdog:
    """S5 watchdog is global and uses template triggers."""

    def test_s5_is_global(self) -> None:
        """S5 automations do not contain room-specific IDs."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s5_trigger = parsed[-2]
        s5_clear = parsed[-1]
        assert "s5_watchdog_trigger" in s5_trigger["id"]
        assert "s5_watchdog_clear" in s5_clear["id"]
        # No room slug in S5 IDs
        assert "living_room" not in s5_trigger["id"]
        assert "living_room" not in s5_clear["id"]

    def test_s5_uses_template_platform(self) -> None:
        """S5 uses template platform."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s5_trigger = parsed[-2]
        assert s5_trigger["trigger"][0]["platform"] == "template"

    def test_s5_template_handles_unknown_state(self) -> None:
        """S5 template handles unknown/unavailable sensor states."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s5_trigger = parsed[-2]
        template = s5_trigger["trigger"][0]["value_template"]
        assert "unknown" in template
        assert "unavailable" in template

    def test_s5_count_independent_of_rooms(self) -> None:
        """S5 generates exactly 2 automations regardless of room count."""
        rooms_1 = (_make_room(room_name="Room A"),)
        rooms_3 = (
            _make_room(room_name="Room A"),
            RoomEntityConfig(
                room_name="Room B",
                entity_temp_floor="sensor.b_floor",
                entity_temp_room="sensor.b_temp",
                entity_humidity="sensor.b_humidity",
                entity_valve="number.b_valve",
            ),
            RoomEntityConfig(
                room_name="Room C",
                entity_temp_floor="sensor.c_floor",
                entity_temp_room="sensor.c_temp",
                entity_humidity="sensor.c_humidity",
                entity_valve="number.c_valve",
            ),
        )
        config_1 = _make_config(rooms=rooms_1)
        config_3 = _make_config(rooms=rooms_3)
        parsed_1 = _parse_yaml(generate_safety_yaml(config_1))
        parsed_3 = _parse_yaml(generate_safety_yaml(config_3))
        s5_count_1 = sum(1 for a in parsed_1 if "s5_watchdog" in a["id"])
        s5_count_3 = sum(1 for a in parsed_3 if "s5_watchdog" in a["id"])
        assert s5_count_1 == 2
        assert s5_count_3 == 2


# ---------------------------------------------------------------------------
# Unique and deterministic automation IDs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAutomationIDs:
    """Automation IDs are unique and deterministic."""

    def test_single_room_unique_ids(self) -> None:
        """Single room: all 10 automation IDs are unique."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        ids = [a["id"] for a in parsed]
        assert len(ids) == len(set(ids))

    def test_multi_room_unique_ids(self) -> None:
        """Multiple rooms: all automation IDs are unique."""
        rooms = (
            _make_room(room_name="Living Room"),
            RoomEntityConfig(
                room_name="Bedroom",
                entity_temp_floor="sensor.bedroom_floor",
                entity_temp_room="sensor.bedroom_temp",
                entity_humidity="sensor.bedroom_humidity",
                entity_valve="number.bedroom_valve",
            ),
        )
        config = _make_config(rooms=rooms)
        parsed = _parse_yaml(generate_safety_yaml(config))
        ids = [a["id"] for a in parsed]
        assert len(ids) == len(set(ids))

    def test_ids_are_deterministic(self) -> None:
        """Same config produces same IDs across calls."""
        config = _make_config()
        parsed_1 = _parse_yaml(generate_safety_yaml(config))
        parsed_2 = _parse_yaml(generate_safety_yaml(config))
        ids_1 = [a["id"] for a in parsed_1]
        ids_2 = [a["id"] for a in parsed_2]
        assert ids_1 == ids_2

    def test_id_contains_rule_name_and_room_slug(self) -> None:
        """Automation IDs contain rule identifier and room slug."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s1_trigger = parsed[0]
        assert "s1_floor_overheat" in s1_trigger["id"]
        assert "living_room" in s1_trigger["id"]

    def test_id_uses_pumpahead_prefix(self) -> None:
        """All automation IDs start with 'pumpahead_'."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        for auto in parsed:
            assert auto["id"].startswith("pumpahead_")


# ---------------------------------------------------------------------------
# Automation structure (HA-compatible)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAutomationStructure:
    """Each automation has the required HA fields."""

    def test_required_fields_present(self) -> None:
        """Each automation has id, alias, description, mode, trigger,
        condition, action."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        required = {
            "id",
            "alias",
            "description",
            "mode",
            "trigger",
            "condition",
            "action",
        }
        for auto in parsed:
            assert required.issubset(auto.keys()), (
                f"Missing keys in {auto['id']}: {required - set(auto.keys())}"
            )

    def test_mode_is_single(self) -> None:
        """All automations use single mode."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        for auto in parsed:
            assert auto["mode"] == "single"

    def test_trigger_is_list(self) -> None:
        """Trigger field is always a list."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        for auto in parsed:
            assert isinstance(auto["trigger"], list)

    def test_action_is_list(self) -> None:
        """Action field is always a list."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        for auto in parsed:
            assert isinstance(auto["action"], list)

    def test_condition_is_list(self) -> None:
        """Condition field is always a list."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        for auto in parsed:
            assert isinstance(auto["condition"], list)


# ---------------------------------------------------------------------------
# Custom threshold overrides
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCustomThresholds:
    """Custom threshold values propagate to generated automations."""

    def test_custom_s1_thresholds(self) -> None:
        """Custom S1 thresholds appear in trigger/clear."""
        config = _make_config(s1_threshold_on=30.0, s1_threshold_off=29.0)
        parsed = _parse_yaml(generate_safety_yaml(config))
        assert parsed[0]["trigger"][0]["above"] == 30.0
        assert parsed[1]["trigger"][0]["below"] == 29.0

    def test_custom_s3_thresholds(self) -> None:
        """Custom S3 thresholds appear in trigger/clear."""
        config = _make_config(s3_threshold_on=3.0, s3_threshold_off=4.0)
        parsed = _parse_yaml(generate_safety_yaml(config))
        assert parsed[4]["trigger"][0]["below"] == 3.0
        assert parsed[5]["trigger"][0]["above"] == 4.0

    def test_custom_s4_thresholds(self) -> None:
        """Custom S4 thresholds appear in trigger/clear."""
        config = _make_config(s4_threshold_on=40.0, s4_threshold_off=38.0)
        parsed = _parse_yaml(generate_safety_yaml(config))
        assert parsed[6]["trigger"][0]["above"] == 40.0
        assert parsed[7]["trigger"][0]["below"] == 38.0

    def test_custom_s2_margins(self) -> None:
        """Custom S2 condensation margin appears in template."""
        config = _make_config(
            s2_condensation_margin=4.0,
            s2_threshold_off_margin=2.0,
        )
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_trigger = parsed[2]
        s2_clear = parsed[3]
        trigger_tmpl = s2_trigger["trigger"][0]["value_template"]
        clear_tmpl = s2_clear["trigger"][0]["value_template"]
        assert "t_dew + 4.0" in trigger_tmpl
        assert "t_dew + 4.0 + 2.0" in clear_tmpl


# ---------------------------------------------------------------------------
# Polish characters / special room names
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSpecialRoomNames:
    """Room names with special characters are handled correctly."""

    def test_polish_characters_in_slug(self) -> None:
        """Polish diacritics are stripped for slug but kept in description."""
        room = RoomEntityConfig(
            room_name="Lazienka Gorna",
            entity_temp_floor="sensor.laz_floor",
            entity_temp_room="sensor.laz_temp",
            entity_humidity="sensor.laz_humidity",
            entity_valve="number.laz_valve",
        )
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        # Slug should be ascii
        assert "lazienka_gorna" in parsed[0]["id"]
        # Description keeps original name
        assert "Lazienka Gorna" in parsed[0]["description"]

    def test_room_name_with_spaces(self) -> None:
        """Room names with spaces become underscored slugs."""
        room = _make_room(room_name="My Big Room")
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        assert "my_big_room" in parsed[0]["id"]

    def test_yaml_special_chars_in_name(self) -> None:
        """Room names with YAML special characters produce valid YAML."""
        room = RoomEntityConfig(
            room_name="Room: A & B",
            entity_temp_floor="sensor.room_floor",
            entity_temp_room="sensor.room_temp",
            entity_humidity="sensor.room_humidity",
            entity_valve="number.room_valve",
        )
        config = _make_config(rooms=(room,))
        yaml_str = generate_safety_yaml(config)
        # Must not raise
        parsed = _parse_yaml(yaml_str)
        assert len(parsed) == 10
        # Original name preserved in alias/description
        assert "Room: A & B" in parsed[0]["alias"]


# ---------------------------------------------------------------------------
# S3/S4 split vs no-split variations
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSplitVariations:
    """S3 and S4 actions differ based on split presence."""

    def test_s3_with_split_sets_heat_mode(self) -> None:
        """S3 with split sets HVAC mode to 'heat'."""
        room = _make_room(entity_split="climate.split_ac")
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s3_trigger = parsed[4]
        hvac_actions = [
            a
            for a in s3_trigger["action"]
            if isinstance(a.get("service"), str)
            and a["service"] == "climate.set_hvac_mode"
        ]
        assert len(hvac_actions) == 1
        assert hvac_actions[0]["data"]["hvac_mode"] == "heat"

    def test_s3_without_split_valve_only(self) -> None:
        """S3 without split only sets valve to 100%."""
        room = _make_room(entity_split=None)
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s3_trigger = parsed[4]
        valve_actions = [
            a
            for a in s3_trigger["action"]
            if isinstance(a.get("service"), str) and a["service"] == "number.set_value"
        ]
        assert len(valve_actions) == 1
        assert valve_actions[0]["data"]["value"] == 100

    def test_s4_with_split_sets_cool_mode(self) -> None:
        """S4 with split sets HVAC mode to 'cool'."""
        room = _make_room(entity_split="climate.split_ac")
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s4_trigger = parsed[6]
        hvac_actions = [
            a
            for a in s4_trigger["action"]
            if isinstance(a.get("service"), str)
            and a["service"] == "climate.set_hvac_mode"
        ]
        assert len(hvac_actions) == 1
        assert hvac_actions[0]["data"]["hvac_mode"] == "cool"

    def test_s4_without_split_closes_valve(self) -> None:
        """S4 without split closes valve (stops heating)."""
        room = _make_room(entity_split=None)
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s4_trigger = parsed[6]
        valve_actions = [
            a
            for a in s4_trigger["action"]
            if isinstance(a.get("service"), str) and a["service"] == "number.set_value"
        ]
        assert len(valve_actions) == 1
        assert valve_actions[0]["data"]["value"] == 0


# ---------------------------------------------------------------------------
# Notifications present in all automations
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNotifications:
    """All automations include a persistent_notification."""

    def test_all_automations_have_notification(self) -> None:
        """Every automation includes at least one notification action."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        for auto in parsed:
            notification_actions = [
                a
                for a in auto["action"]
                if isinstance(a.get("service"), str)
                and a["service"] == "persistent_notification.create"
            ]
            assert len(notification_actions) >= 1, (
                f"Automation {auto['id']} has no notification action"
            )


# ---------------------------------------------------------------------------
# S5 watchdog fallback actions (issue #62)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestS5WatchdogFallback:
    """S5 watchdog trigger/clear include fallback flag and HP thermostat actions."""

    def test_s5_trigger_has_watchdog_flag_action(self) -> None:
        """S5 trigger includes input_boolean.turn_on for the watchdog flag."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s5_trigger = parsed[-2]
        flag_actions = [
            a
            for a in s5_trigger["action"]
            if isinstance(a.get("service"), str)
            and a["service"] == "input_boolean.turn_on"
        ]
        assert len(flag_actions) == 1
        assert (
            flag_actions[0]["target"]["entity_id"]
            == "input_boolean.pumpahead_watchdog_fallback"
        )

    def test_s5_clear_has_watchdog_flag_action(self) -> None:
        """S5 clear includes input_boolean.turn_off for the watchdog flag."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s5_clear = parsed[-1]
        flag_actions = [
            a
            for a in s5_clear["action"]
            if isinstance(a.get("service"), str)
            and a["service"] == "input_boolean.turn_off"
        ]
        assert len(flag_actions) == 1
        assert (
            flag_actions[0]["target"]["entity_id"]
            == "input_boolean.pumpahead_watchdog_fallback"
        )

    def test_s5_trigger_has_hp_thermostat_action_when_configured(self) -> None:
        """S5 trigger includes climate.set_hvac_mode when HP thermostat set."""
        config = _make_config(entity_hp_thermostat="climate.heat_pump")
        parsed = _parse_yaml(generate_safety_yaml(config))
        s5_trigger = parsed[-2]
        hvac_actions = [
            a
            for a in s5_trigger["action"]
            if isinstance(a.get("service"), str)
            and a["service"] == "climate.set_hvac_mode"
        ]
        assert len(hvac_actions) == 1
        assert hvac_actions[0]["target"]["entity_id"] == "climate.heat_pump"
        assert hvac_actions[0]["data"]["hvac_mode"] == "heat"

    def test_s5_trigger_no_hp_thermostat_action_when_not_configured(self) -> None:
        """S5 trigger omits climate actions when HP thermostat is None."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s5_trigger = parsed[-2]
        hvac_actions = [
            a
            for a in s5_trigger["action"]
            if isinstance(a.get("service"), str)
            and a["service"] == "climate.set_hvac_mode"
        ]
        assert len(hvac_actions) == 0

    def test_s5_custom_watchdog_flag_entity(self) -> None:
        """Custom watchdog flag entity appears in generated YAML."""
        config = _make_config(
            entity_watchdog_flag="input_boolean.custom_watchdog",
        )
        parsed = _parse_yaml(generate_safety_yaml(config))
        s5_trigger = parsed[-2]
        flag_actions = [
            a
            for a in s5_trigger["action"]
            if isinstance(a.get("service"), str)
            and a["service"] == "input_boolean.turn_on"
        ]
        assert len(flag_actions) == 1
        assert flag_actions[0]["target"]["entity_id"] == "input_boolean.custom_watchdog"

    def test_s5_clear_message_mentions_resuming(self) -> None:
        """S5 clear notification message mentions PumpAhead resuming."""
        config = _make_config()
        parsed = _parse_yaml(generate_safety_yaml(config))
        s5_clear = parsed[-1]
        notif_actions = [
            a
            for a in s5_clear["action"]
            if isinstance(a.get("service"), str)
            and a["service"] == "persistent_notification.create"
        ]
        assert len(notif_actions) == 1
        assert "resuming" in notif_actions[0]["data"]["message"].lower()


# ---------------------------------------------------------------------------
# S2 emergency split cool (issue #56)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestS2EmergencySplitCool:
    """S2 condensation trigger/clear include emergency split cool actions."""

    def test_s2_trigger_activates_split_cool_when_split_present(self) -> None:
        """S2 trigger sets split to cool mode when room has a split."""
        room = _make_room(entity_split="climate.living_room_split")
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_trigger = parsed[2]  # After S1 trigger + S1 clear
        action = s2_trigger["action"]
        assert isinstance(action, list)
        hvac_actions = [
            a
            for a in action
            if isinstance(a.get("service"), str)
            and a["service"] == "climate.set_hvac_mode"
        ]
        assert len(hvac_actions) == 1
        assert hvac_actions[0]["target"]["entity_id"] == "climate.living_room_split"
        assert hvac_actions[0]["data"]["hvac_mode"] == "cool"

    def test_s2_trigger_no_split_action_when_no_split(self) -> None:
        """S2 trigger omits split actions when room has no split."""
        room = _make_room(entity_split=None)
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_trigger = parsed[2]  # After S1 trigger + S1 clear
        action = s2_trigger["action"]
        assert isinstance(action, list)
        hvac_actions = [
            a
            for a in action
            if isinstance(a.get("service"), str)
            and a["service"] == "climate.set_hvac_mode"
        ]
        assert len(hvac_actions) == 0

    def test_s2_clear_turns_split_off_when_split_present(self) -> None:
        """S2 clear sets split to off mode when room has a split."""
        room = _make_room(entity_split="climate.living_room_split")
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_clear = parsed[3]  # After S1 trigger + S1 clear + S2 trigger
        action = s2_clear["action"]
        assert isinstance(action, list)
        hvac_actions = [
            a
            for a in action
            if isinstance(a.get("service"), str)
            and a["service"] == "climate.set_hvac_mode"
        ]
        assert len(hvac_actions) == 1
        assert hvac_actions[0]["target"]["entity_id"] == "climate.living_room_split"
        assert hvac_actions[0]["data"]["hvac_mode"] == "off"

    def test_s2_clear_no_split_action_when_no_split(self) -> None:
        """S2 clear omits split actions when room has no split."""
        room = _make_room(entity_split=None)
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_clear = parsed[3]  # After S1 trigger + S1 clear + S2 trigger
        action = s2_clear["action"]
        assert isinstance(action, list)
        hvac_actions = [
            a
            for a in action
            if isinstance(a.get("service"), str)
            and a["service"] == "climate.set_hvac_mode"
        ]
        assert len(hvac_actions) == 0

    def test_s2_trigger_notification_mentions_split_when_present(self) -> None:
        """S2 trigger notification mentions split set to cool when present."""
        room = _make_room(entity_split="climate.my_split")
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_trigger = parsed[2]
        notif_actions = [
            a
            for a in s2_trigger["action"]
            if isinstance(a.get("service"), str)
            and a["service"] == "persistent_notification.create"
        ]
        assert len(notif_actions) == 1
        assert "split set to cool" in notif_actions[0]["data"]["message"]

    def test_s2_trigger_notification_no_split_mention_when_absent(self) -> None:
        """S2 trigger notification does not mention split when absent."""
        room = _make_room(entity_split=None)
        config = _make_config(rooms=(room,))
        parsed = _parse_yaml(generate_safety_yaml(config))
        s2_trigger = parsed[2]
        notif_actions = [
            a
            for a in s2_trigger["action"]
            if isinstance(a.get("service"), str)
            and a["service"] == "persistent_notification.create"
        ]
        assert len(notif_actions) == 1
        assert "split" not in notif_actions[0]["data"]["message"].lower()
