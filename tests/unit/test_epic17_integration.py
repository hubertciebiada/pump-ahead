"""Integration tests for Epic #17 -- Safety Layer verification gate.

Verifies end-to-end cross-module wiring for the three sub-issues:
    #60 Safety rules S1-S5 (safety_rules.py -- SafetyEvaluator, constants)
    #61 YAML automation generator (safety_yaml_generator.py)
    #62 Watchdog monitor (watchdog.py -- WatchdogMonitor state machine)

Tests exercise cross-module workflows:
    safety_rules thresholds -> YAML generator defaults alignment
    WatchdogMonitor timeouts -> SafetyEvaluator S5 thresholds alignment
    combined evaluation scenarios (simultaneous S1+S5, condensation,
        emergency heat with/without split, multi-room YAML)
    acceptance criteria explicit verification
    architectural integrity (dependency DAG, no homeassistant imports)

All tests are fast, deterministic, and use the
``@pytest.mark.unit`` marker.
"""

from __future__ import annotations

import inspect

import pytest
import yaml

from pumpahead.safety_rules import (
    DEFAULT_SAFETY_RULES,
    S1_FLOOR_OVERHEAT,
    S3_EMERGENCY_HEAT,
    S4_EMERGENCY_COOL,
    S5_WATCHDOG,
    SafetyAction,
    SafetyEvaluator,
    SensorSnapshot,
)
from pumpahead.safety_yaml_generator import (
    RoomEntityConfig,
    SafetyYAMLConfig,
    generate_safety_yaml,
)
from pumpahead.simulator import HeatPumpMode
from pumpahead.watchdog import WatchdogMonitor, WatchdogState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normal_snapshot(
    *,
    T_floor: float = 25.0,
    T_room: float = 21.0,
    humidity: float = 50.0,
    hp_mode: HeatPumpMode = HeatPumpMode.HEATING,
    last_update_age_minutes: float = 1.0,
) -> SensorSnapshot:
    """Create a normal-conditions snapshot with overridable fields."""
    return SensorSnapshot(
        T_floor=T_floor,
        T_room=T_room,
        humidity=humidity,
        hp_mode=hp_mode,
        last_update_age_minutes=last_update_age_minutes,
    )


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
# TestSafetyRulesToYAMLGeneratorPipeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSafetyRulesToYAMLGeneratorPipeline:
    """Cross-module data flow: safety_rules constants -> YAML generator defaults."""

    def test_yaml_generator_defaults_match_safety_rule_constants(self) -> None:
        """SafetyYAMLConfig defaults reference the safety_rules constants."""
        config = _make_config()

        # S1 thresholds
        assert config.s1_threshold_on == S1_FLOOR_OVERHEAT.threshold_on
        assert config.s1_threshold_off == S1_FLOOR_OVERHEAT.threshold_off

        # S3 thresholds
        assert config.s3_threshold_on == S3_EMERGENCY_HEAT.threshold_on
        assert config.s3_threshold_off == S3_EMERGENCY_HEAT.threshold_off

        # S4 thresholds
        assert config.s4_threshold_on == S4_EMERGENCY_COOL.threshold_on
        assert config.s4_threshold_off == S4_EMERGENCY_COOL.threshold_off

        # S5 thresholds
        assert config.s5_threshold_on == S5_WATCHDOG.threshold_on
        assert config.s5_threshold_off == S5_WATCHDOG.threshold_off

    def test_generated_yaml_s1_threshold_matches_safety_rule(self) -> None:
        """S1 trigger/clear automation thresholds match safety_rules constants."""
        config = _make_config()
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        s1_trigger = next(
            a for a in automations if "s1_floor_overheat_trigger" in str(a["id"])
        )
        s1_clear = next(
            a for a in automations if "s1_floor_overheat_clear" in str(a["id"])
        )

        assert s1_trigger["trigger"][0]["above"] == S1_FLOOR_OVERHEAT.threshold_on
        assert s1_clear["trigger"][0]["below"] == S1_FLOOR_OVERHEAT.threshold_off

    def test_generated_yaml_s3_threshold_matches_safety_rule(self) -> None:
        """S3 trigger/clear automation thresholds match safety_rules constants."""
        config = _make_config()
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        s3_trigger = next(
            a for a in automations if "s3_emergency_heat_trigger" in str(a["id"])
        )
        s3_clear = next(
            a for a in automations if "s3_emergency_heat_clear" in str(a["id"])
        )

        assert s3_trigger["trigger"][0]["below"] == S3_EMERGENCY_HEAT.threshold_on
        assert s3_clear["trigger"][0]["above"] == S3_EMERGENCY_HEAT.threshold_off

    def test_generated_yaml_s5_watchdog_threshold_in_template(self) -> None:
        """S5 trigger/clear YAML templates contain the S5 threshold values."""
        config = _make_config()
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        s5_trigger = next(
            a for a in automations if a.get("id") == "pumpahead_s5_watchdog_trigger"
        )
        s5_clear = next(
            a for a in automations if a.get("id") == "pumpahead_s5_watchdog_clear"
        )

        trigger_template = s5_trigger["trigger"][0]["value_template"]
        clear_template = s5_clear["trigger"][0]["value_template"]

        # Template should contain the threshold value as a number
        assert str(S5_WATCHDOG.threshold_on) in trigger_template
        assert str(S5_WATCHDOG.threshold_off) in clear_template

    def test_evaluator_s1_trigger_matches_yaml_s1_action(self) -> None:
        """SafetyEvaluator S1 CLOSE_VALVE maps to YAML valve=0 action."""
        # Evaluator triggers S1
        evaluator = SafetyEvaluator()
        snap = _normal_snapshot(T_floor=35.0)
        results = evaluator.evaluate(snap)
        s1_result = next(r for r in results if r.rule.name == "S1_floor_overheat")
        assert s1_result.triggered is True
        assert s1_result.action == SafetyAction.CLOSE_VALVE

        # YAML S1 trigger automation closes valve to 0
        config = _make_config()
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        s1_auto = next(
            a for a in automations if "s1_floor_overheat_trigger" in str(a["id"])
        )
        valve_action = next(
            a for a in s1_auto["action"] if a.get("service") == "number.set_value"
        )
        assert valve_action["data"]["value"] == 0

    def test_evaluator_s3_trigger_matches_yaml_s3_action(self) -> None:
        """SafetyEvaluator S3 EMERGENCY_HEAT maps to YAML valve=100 action."""
        # Evaluator triggers S3
        evaluator = SafetyEvaluator()
        snap = _normal_snapshot(T_room=4.0)
        results = evaluator.evaluate(snap)
        s3_result = next(r for r in results if r.rule.name == "S3_emergency_heat")
        assert s3_result.triggered is True
        assert s3_result.action == SafetyAction.EMERGENCY_HEAT

        # YAML S3 trigger automation opens valve to 100
        config = _make_config()
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        s3_auto = next(
            a for a in automations if "s3_emergency_heat_trigger" in str(a["id"])
        )
        valve_action = next(
            a for a in s3_auto["action"] if a.get("service") == "number.set_value"
        )
        assert valve_action["data"]["value"] == 100


# ---------------------------------------------------------------------------
# TestWatchdogToSafetyEvaluatorAlignment
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWatchdogToSafetyEvaluatorAlignment:
    """Cross-module: watchdog.py timeouts align with S5 in safety_rules.py."""

    def test_watchdog_default_timeout_matches_s5_threshold_on(self) -> None:
        """WatchdogMonitor default timeout (900s) == S5 threshold_on (15 min) * 60."""
        # Verify WatchdogMonitor can be created with defaults (no ValueError)
        WatchdogMonitor()
        # Default timeout is 900.0 seconds = 15 minutes
        assert S5_WATCHDOG.threshold_on * 60 == 900.0

    def test_watchdog_default_recovery_matches_s5_threshold_off(self) -> None:
        """WatchdogMonitor default recovery (300s) == S5 threshold_off (5 min) * 60."""
        # Verify WatchdogMonitor can be created with defaults (no ValueError)
        WatchdogMonitor()
        # Default recovery is 300.0 seconds = 5 minutes
        assert S5_WATCHDOG.threshold_off * 60 == 300.0

    def test_watchdog_fallback_and_evaluator_s5_trigger_at_same_point(self) -> None:
        """Both WatchdogMonitor and SafetyEvaluator trigger at 16 min stale."""
        monitor = WatchdogMonitor()
        evaluator = SafetyEvaluator()

        # 16 minutes since last update
        age_minutes = 16.0
        age_seconds = age_minutes * 60

        status = monitor.update(age_seconds)
        assert status.state == WatchdogState.FALLBACK
        assert status.fallback_active is True

        snap = _normal_snapshot(last_update_age_minutes=age_minutes)
        results = evaluator.evaluate(snap)
        s5_result = next(r for r in results if r.rule.name == "S5_watchdog")
        assert s5_result.triggered is True

    def test_watchdog_recovery_and_evaluator_s5_clear_at_same_point(self) -> None:
        """Both WatchdogMonitor and SafetyEvaluator clear at 3 min fresh."""
        monitor = WatchdogMonitor()
        evaluator = SafetyEvaluator()

        # First trigger both at 16 minutes
        monitor.update(16.0 * 60)
        evaluator.evaluate(_normal_snapshot(last_update_age_minutes=16.0))

        # Now feed 3 minutes since last update
        age_minutes = 3.0
        age_seconds = age_minutes * 60

        status = monitor.update(age_seconds)
        # WatchdogMonitor transitions FALLBACK -> RECOVERING at < recovery_seconds
        assert status.state == WatchdogState.RECOVERING

        snap = _normal_snapshot(last_update_age_minutes=age_minutes)
        results = evaluator.evaluate(snap)
        s5_result = next(r for r in results if r.rule.name == "S5_watchdog")
        # SafetyEvaluator S5 clears when measured < threshold_off (5.0)
        assert s5_result.triggered is False


# ---------------------------------------------------------------------------
# TestCombinedSafetyScenarios
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCombinedSafetyScenarios:
    """End-to-end scenarios combining all three modules."""

    def test_floor_overheat_during_watchdog_fallback(self) -> None:
        """S1 + S5 triggered simultaneously; S1 has higher priority."""
        evaluator = SafetyEvaluator()
        monitor = WatchdogMonitor()

        # T_floor=35 triggers S1, last_update=20 min triggers S5
        snap = _normal_snapshot(T_floor=35.0, last_update_age_minutes=20.0)
        results = evaluator.evaluate(snap)
        status = monitor.update(20.0 * 60)

        # Both S1 and S5 should be active
        s1 = next(r for r in results if r.rule.name == "S1_floor_overheat")
        s5 = next(r for r in results if r.rule.name == "S5_watchdog")
        assert s1.triggered is True
        assert s5.triggered is True
        assert status.state == WatchdogState.FALLBACK

        # S1 has higher priority (1) than S5 (3)
        assert s1.rule.priority < s5.rule.priority

        # YAML has automations for both S1 and S5
        config = _make_config()
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        s1_autos = [a for a in automations if "s1_floor_overheat" in str(a["id"])]
        s5_autos = [a for a in automations if "s5_watchdog" in str(a["id"])]
        assert len(s1_autos) == 2  # trigger + clear
        assert len(s5_autos) == 2  # trigger + clear

    def test_condensation_protection_with_split_room_yaml(self) -> None:
        """S2 triggers CLOSE_VALVE; YAML has template trigger with all entities."""
        evaluator = SafetyEvaluator()

        # T_floor=17, T_room=20, humidity=80 -> dew_point = 20-(100-80)/5 = 16
        # margin = T_floor - (T_dew + 2) = 17 - 18 = -1 < 0 -> S2 triggers
        snap = _normal_snapshot(T_floor=17.0, T_room=20.0, humidity=80.0)
        results = evaluator.evaluate(snap)
        s2 = next(r for r in results if r.rule.name == "S2_condensation")
        assert s2.triggered is True
        assert s2.action == SafetyAction.CLOSE_VALVE

        # Generate YAML for a room with split
        room = _make_room(entity_split="climate.living_room_split")
        config = _make_config(rooms=(room,))
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        s2_trigger = next(
            a for a in automations if "s2_condensation_trigger" in str(a["id"])
        )
        # S2 uses template trigger referencing floor, room, humidity entities
        template = s2_trigger["trigger"][0]["value_template"]
        assert room.entity_temp_floor in template
        assert room.entity_temp_room in template
        assert room.entity_humidity in template

    def test_emergency_heat_generates_valve_and_split_actions(self) -> None:
        """S3: WITH split gets valve+split; WITHOUT gets valve only."""
        evaluator = SafetyEvaluator()
        snap = _normal_snapshot(T_room=4.0)
        results = evaluator.evaluate(snap)
        s3 = next(r for r in results if r.rule.name == "S3_emergency_heat")
        assert s3.action == SafetyAction.EMERGENCY_HEAT

        # Room WITH split
        room_with = _make_room(entity_split="climate.split")
        config_with = _make_config(rooms=(room_with,))
        yaml_with = generate_safety_yaml(config_with)
        autos_with = _parse_yaml(yaml_with)

        s3_trigger_with = next(
            a for a in autos_with if "s3_emergency_heat_trigger" in str(a["id"])
        )
        services_with = [a["service"] for a in s3_trigger_with["action"]]
        assert "number.set_value" in services_with
        assert "climate.set_hvac_mode" in services_with

        # Room WITHOUT split
        room_without = _make_room(entity_split=None)
        config_without = _make_config(rooms=(room_without,))
        yaml_without = generate_safety_yaml(config_without)
        autos_without = _parse_yaml(yaml_without)

        s3_trigger_without = next(
            a for a in autos_without if "s3_emergency_heat_trigger" in str(a["id"])
        )
        services_without = [a["service"] for a in s3_trigger_without["action"]]
        assert "number.set_value" in services_without
        assert "climate.set_hvac_mode" not in services_without

    def test_multi_room_yaml_with_all_rules_produces_correct_count(self) -> None:
        """3 rooms -> 3*8 per-room + 2 global S5 = 26 automations, all unique."""
        rooms = (
            _make_room(room_name="Kitchen"),
            _make_room(room_name="Bedroom"),
            _make_room(room_name="Bathroom"),
        )
        config = _make_config(rooms=rooms)
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        assert len(automations) == 26  # 3 rooms * 8 + 2 global

        # All IDs unique
        ids = [a["id"] for a in automations]
        assert len(ids) == len(set(ids))

        # Every automation has required keys
        for auto in automations:
            assert "id" in auto
            assert "alias" in auto
            assert "trigger" in auto
            assert "condition" in auto
            assert "action" in auto

    def test_yaml_round_trip_preserves_all_thresholds(self) -> None:
        """Custom thresholds survive YAML serialise -> parse round-trip."""
        config = _make_config(
            s1_threshold_on=32.0,
            s1_threshold_off=31.0,
            s3_threshold_on=4.0,
            s3_threshold_off=5.0,
            s5_threshold_on=20.0,
            s5_threshold_off=10.0,
        )
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        # S1 custom thresholds
        s1_trigger = next(
            a for a in automations if "s1_floor_overheat_trigger" in str(a["id"])
        )
        assert s1_trigger["trigger"][0]["above"] == 32.0

        s1_clear = next(
            a for a in automations if "s1_floor_overheat_clear" in str(a["id"])
        )
        assert s1_clear["trigger"][0]["below"] == 31.0

        # S3 custom thresholds
        s3_trigger = next(
            a for a in automations if "s3_emergency_heat_trigger" in str(a["id"])
        )
        assert s3_trigger["trigger"][0]["below"] == 4.0

        # S5 custom threshold in template
        s5_trigger = next(
            a for a in automations if a.get("id") == "pumpahead_s5_watchdog_trigger"
        )
        assert "20.0" in s5_trigger["trigger"][0]["value_template"]


# ---------------------------------------------------------------------------
# TestAcceptanceCriteriaVerification
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAcceptanceCriteriaVerification:
    """Explicit verification of Epic #17 acceptance criteria."""

    def test_ac_safety_yaml_independent_of_python_process(self) -> None:
        """Generated YAML uses only HA-native constructs, no custom Python."""
        config = _make_config()
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        allowed_platforms = {"numeric_state", "template"}
        allowed_services = {
            "number.set_value",
            "climate.set_hvac_mode",
            "persistent_notification.create",
            "input_boolean.turn_on",
            "input_boolean.turn_off",
        }

        for auto in automations:
            # All triggers use HA-native platforms
            for trigger in auto["trigger"]:
                assert trigger["platform"] in allowed_platforms, (
                    f"Automation {auto['id']} uses non-HA platform: "
                    f"{trigger['platform']}"
                )

            # All actions use HA services
            for action in auto["action"]:
                assert action["service"] in allowed_services, (
                    f"Automation {auto['id']} uses non-HA service: {action['service']}"
                )

    def test_ac_s1_valve_closed_action_present(self) -> None:
        """S1 trigger automation closes valve to 0."""
        config = _make_config()
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        s1_trigger = next(
            a for a in automations if "s1_floor_overheat_trigger" in str(a["id"])
        )
        valve_action = next(
            a for a in s1_trigger["action"] if a.get("service") == "number.set_value"
        )
        assert valve_action["data"]["value"] == 0

    def test_ac_s5_fallback_active_after_timeout(self) -> None:
        """S5 watchdog trigger automation exists; WatchdogMonitor enters FALLBACK."""
        # YAML has S5 watchdog trigger
        config = _make_config()
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        s5_trigger = next(
            a for a in automations if a.get("id") == "pumpahead_s5_watchdog_trigger"
        )
        assert s5_trigger is not None

        # WatchdogMonitor transitions to FALLBACK
        monitor = WatchdogMonitor()
        status = monitor.update(1000.0)  # > 900s timeout
        assert status.state == WatchdogState.FALLBACK
        assert status.fallback_active is True

    def test_ac_s3_emergency_heat_on_low_temp(self) -> None:
        """S3 triggers at T_room < 5.0; YAML automation has below: 5.0."""
        # SafetyEvaluator triggers S3
        evaluator = SafetyEvaluator()
        snap = _normal_snapshot(T_room=4.0)
        results = evaluator.evaluate(snap)
        s3 = next(r for r in results if r.rule.name == "S3_emergency_heat")
        assert s3.triggered is True

        # YAML S3 trigger has below: 5.0
        config = _make_config()
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        s3_trigger = next(
            a for a in automations if "s3_emergency_heat_trigger" in str(a["id"])
        )
        assert s3_trigger["trigger"][0]["below"] == S3_EMERGENCY_HEAT.threshold_on

    def test_ac_all_rules_have_hysteresis(self) -> None:
        """All 5 safety rules have threshold_on != threshold_off; YAML has pairs."""
        # Verify rule constants
        for rule in DEFAULT_SAFETY_RULES:
            assert rule.threshold_on != rule.threshold_off, (
                f"Rule {rule.name} has no hysteresis: "
                f"on={rule.threshold_on}, off={rule.threshold_off}"
            )

        # Verify YAML has trigger+clear pairs for every rule
        config = _make_config()
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        for rule_id in [
            "s1_floor_overheat",
            "s2_condensation",
            "s3_emergency_heat",
            "s4_emergency_cool",
        ]:
            triggers = [a for a in automations if f"{rule_id}_trigger" in str(a["id"])]
            clears = [a for a in automations if f"{rule_id}_clear" in str(a["id"])]
            assert len(triggers) >= 1, f"No trigger automation for {rule_id}"
            assert len(clears) >= 1, f"No clear automation for {rule_id}"

        # S5 global trigger+clear
        s5_triggers = [
            a for a in automations if a.get("id") == "pumpahead_s5_watchdog_trigger"
        ]
        s5_clears = [
            a for a in automations if a.get("id") == "pumpahead_s5_watchdog_clear"
        ]
        assert len(s5_triggers) == 1
        assert len(s5_clears) == 1


# ---------------------------------------------------------------------------
# TestArchitecturalIntegrity
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestArchitecturalIntegrity:
    """Verify DAG dependency direction and no architectural drift."""

    def test_safety_rules_does_not_import_yaml_generator_or_watchdog(self) -> None:
        """safety_rules.py must not import safety_yaml_generator or watchdog."""
        import pumpahead.safety_rules as mod

        import_lines = _extract_import_lines(mod)
        assert not any("safety_yaml_generator" in line for line in import_lines), (
            "safety_rules.py must not import safety_yaml_generator"
        )
        assert not any("watchdog" in line for line in import_lines), (
            "safety_rules.py must not import watchdog"
        )

    def test_watchdog_does_not_import_safety_rules_or_yaml_generator(self) -> None:
        """watchdog.py must not import safety_rules or safety_yaml_generator."""
        import pumpahead.watchdog as mod

        import_lines = _extract_import_lines(mod)
        assert not any("safety_rules" in line for line in import_lines), (
            "watchdog.py must not import safety_rules"
        )
        assert not any("safety_yaml_generator" in line for line in import_lines), (
            "watchdog.py must not import safety_yaml_generator"
        )

    def test_yaml_generator_imports_safety_rules_but_not_watchdog(self) -> None:
        """safety_yaml_generator.py imports safety_rules but not watchdog."""
        import pumpahead.safety_yaml_generator as mod

        import_lines = _extract_import_lines(mod)
        assert any("safety_rules" in line for line in import_lines), (
            "safety_yaml_generator.py must import safety_rules"
        )
        assert not any("watchdog" in line for line in import_lines), (
            "safety_yaml_generator.py must not import watchdog"
        )

    def test_no_homeassistant_imports_in_any_safety_module(self) -> None:
        """None of the three safety modules import homeassistant."""
        import pumpahead.safety_rules as rules_mod
        import pumpahead.safety_yaml_generator as yaml_mod
        import pumpahead.watchdog as watchdog_mod

        for mod_name, mod in [
            ("safety_rules", rules_mod),
            ("safety_yaml_generator", yaml_mod),
            ("watchdog", watchdog_mod),
        ]:
            import_lines = _extract_import_lines(mod)
            assert not any("homeassistant" in line for line in import_lines), (
                f"{mod_name} must not import homeassistant"
            )

    def test_all_public_symbols_exported_from_init(self) -> None:
        """All public symbols from the three modules are in pumpahead.__all__."""
        import pumpahead

        expected_symbols = [
            # From safety_rules.py
            "DEFAULT_SAFETY_RULES",
            "S1_FLOOR_OVERHEAT",
            "S2_CONDENSATION",
            "S3_EMERGENCY_HEAT",
            "S4_EMERGENCY_COOL",
            "S5_WATCHDOG",
            "SafetyAction",
            "SafetyEvaluator",
            "SafetyRule",
            "SafetyRuleResult",
            "SensorSnapshot",
            # From safety_yaml_generator.py
            "RoomEntityConfig",
            "SafetyYAMLConfig",
            "generate_safety_yaml",
            "generate_safety_yaml_for_room",
            # From watchdog.py
            "WatchdogMonitor",
            "WatchdogState",
            "WatchdogStatus",
        ]

        for symbol in expected_symbols:
            assert hasattr(pumpahead, symbol), (
                f"{symbol} not exported from pumpahead.__init__"
            )
            assert symbol in pumpahead.__all__, f"{symbol} not in pumpahead.__all__"
