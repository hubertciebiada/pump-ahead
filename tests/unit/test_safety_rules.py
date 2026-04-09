"""Unit tests for safety rules S1-S5.

Tests cover SafetyAction enum members, SensorSnapshot validation,
SafetyRule construction and hysteresis validation, default rule
constants, and the stateful SafetyEvaluator with hysteresis tracking
and oscillation prevention.
"""

from __future__ import annotations

import pytest

from pumpahead.safety_rules import (
    DEFAULT_SAFETY_RULES,
    S1_FLOOR_OVERHEAT,
    S2_CONDENSATION,
    S3_EMERGENCY_HEAT,
    S4_EMERGENCY_COOL,
    S5_WATCHDOG,
    SafetyAction,
    SafetyEvaluator,
    SafetyRule,
    SafetyRuleResult,
    SensorSnapshot,
)
from pumpahead.simulator import HeatPumpMode

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


# ---------------------------------------------------------------------------
# SafetyAction tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSafetyAction:
    """SafetyAction enum tests."""

    def test_action_members_exist(self) -> None:
        """All four enum members exist."""
        assert SafetyAction.CLOSE_VALVE.value == "close_valve"
        assert SafetyAction.EMERGENCY_HEAT.value == "emergency_heat"
        assert SafetyAction.EMERGENCY_COOL.value == "emergency_cool"
        assert SafetyAction.FALLBACK_HP_CURVE.value == "fallback_hp_curve"

    def test_member_count(self) -> None:
        """Exactly four members."""
        assert len(SafetyAction) == 4


# ---------------------------------------------------------------------------
# SensorSnapshot tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSensorSnapshot:
    """SensorSnapshot frozen dataclass tests."""

    def test_creation_with_valid_data(self) -> None:
        """SensorSnapshot can be created with valid data."""
        snap = _normal_snapshot()
        assert snap.T_floor == 25.0
        assert snap.T_room == 21.0
        assert snap.humidity == 50.0
        assert snap.hp_mode == HeatPumpMode.HEATING
        assert snap.last_update_age_minutes == 1.0

    def test_frozen(self) -> None:
        """SensorSnapshot is immutable."""
        snap = _normal_snapshot()
        with pytest.raises(AttributeError):
            snap.T_floor = 30.0  # type: ignore[misc]

    def test_invalid_humidity_too_high(self) -> None:
        """Humidity > 100 raises ValueError."""
        with pytest.raises(ValueError, match="humidity"):
            _normal_snapshot(humidity=101.0)

    def test_invalid_humidity_negative(self) -> None:
        """Humidity < 0 raises ValueError."""
        with pytest.raises(ValueError, match="humidity"):
            _normal_snapshot(humidity=-1.0)

    def test_invalid_last_update_negative(self) -> None:
        """Negative last_update_age_minutes raises ValueError."""
        with pytest.raises(ValueError, match="last_update_age_minutes"):
            _normal_snapshot(last_update_age_minutes=-0.1)

    def test_boundary_humidity_zero(self) -> None:
        """Humidity of exactly 0 is valid."""
        snap = _normal_snapshot(humidity=0.0)
        assert snap.humidity == 0.0

    def test_boundary_humidity_hundred(self) -> None:
        """Humidity of exactly 100 is valid."""
        snap = _normal_snapshot(humidity=100.0)
        assert snap.humidity == 100.0

    def test_last_update_age_zero(self) -> None:
        """last_update_age_minutes of 0 is valid."""
        snap = _normal_snapshot(last_update_age_minutes=0.0)
        assert snap.last_update_age_minutes == 0.0


# ---------------------------------------------------------------------------
# SafetyRule tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSafetyRule:
    """SafetyRule frozen dataclass tests."""

    def test_creation_with_all_fields(self) -> None:
        """SafetyRule can be created with all fields specified."""
        rule = SafetyRule(
            name="test_rule",
            description="Test description",
            priority=1,
            threshold_on=34.0,
            threshold_off=33.0,
            action=SafetyAction.CLOSE_VALVE,
            condition=lambda s: s.T_floor,
            trigger_above=True,
        )
        assert rule.name == "test_rule"
        assert rule.priority == 1
        assert rule.threshold_on == 34.0
        assert rule.threshold_off == 33.0
        assert rule.action == SafetyAction.CLOSE_VALVE
        assert rule.trigger_above is True

    def test_frozen(self) -> None:
        """SafetyRule is immutable."""
        rule = S1_FLOOR_OVERHEAT
        with pytest.raises(AttributeError):
            rule.priority = 5  # type: ignore[misc]

    def test_empty_name_raises(self) -> None:
        """Empty rule name raises ValueError."""
        with pytest.raises(ValueError, match="name must be non-empty"):
            SafetyRule(
                name="",
                description="Bad rule",
                priority=1,
                threshold_on=34.0,
                threshold_off=33.0,
                action=SafetyAction.CLOSE_VALVE,
                condition=lambda s: s.T_floor,
                trigger_above=True,
            )

    def test_invalid_priority_zero_raises(self) -> None:
        """Priority 0 raises ValueError."""
        with pytest.raises(ValueError, match="priority"):
            SafetyRule(
                name="bad_priority",
                description="Bad priority",
                priority=0,
                threshold_on=34.0,
                threshold_off=33.0,
                action=SafetyAction.CLOSE_VALVE,
                condition=lambda s: s.T_floor,
                trigger_above=True,
            )

    def test_hysteresis_validation_trigger_above(self) -> None:
        """trigger_above rule: threshold_off > threshold_on raises."""
        with pytest.raises(ValueError, match="threshold_off"):
            SafetyRule(
                name="bad_hysteresis",
                description="Bad hysteresis",
                priority=1,
                threshold_on=34.0,
                threshold_off=35.0,  # off > on for trigger_above -> invalid
                action=SafetyAction.CLOSE_VALVE,
                condition=lambda s: s.T_floor,
                trigger_above=True,
            )

    def test_hysteresis_validation_trigger_below(self) -> None:
        """trigger_below rule: threshold_off < threshold_on raises."""
        with pytest.raises(ValueError, match="threshold_off"):
            SafetyRule(
                name="bad_hysteresis_below",
                description="Bad hysteresis below",
                priority=1,
                threshold_on=5.0,
                threshold_off=4.0,  # off < on for trigger_below -> invalid
                action=SafetyAction.EMERGENCY_HEAT,
                condition=lambda s: s.T_room,
                trigger_above=False,
            )

    def test_hysteresis_equal_thresholds_trigger_above(self) -> None:
        """trigger_above rule: equal thresholds are valid (no hysteresis)."""
        rule = SafetyRule(
            name="no_hysteresis",
            description="Equal thresholds",
            priority=1,
            threshold_on=34.0,
            threshold_off=34.0,
            action=SafetyAction.CLOSE_VALVE,
            condition=lambda s: s.T_floor,
            trigger_above=True,
        )
        assert rule.threshold_on == rule.threshold_off

    def test_hysteresis_equal_thresholds_trigger_below(self) -> None:
        """trigger_below rule: equal thresholds are valid (no hysteresis)."""
        rule = SafetyRule(
            name="no_hysteresis_below",
            description="Equal thresholds below",
            priority=1,
            threshold_on=5.0,
            threshold_off=5.0,
            action=SafetyAction.EMERGENCY_HEAT,
            condition=lambda s: s.T_room,
            trigger_above=False,
        )
        assert rule.threshold_on == rule.threshold_off


# ---------------------------------------------------------------------------
# Default rule constant tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDefaultRules:
    """Tests for the five default safety rule constants."""

    def test_default_rules_count(self) -> None:
        """DEFAULT_SAFETY_RULES contains exactly 5 rules."""
        assert len(DEFAULT_SAFETY_RULES) == 5

    def test_s1_thresholds(self) -> None:
        """S1: on at 34C, off at 33C, trigger above."""
        assert S1_FLOOR_OVERHEAT.threshold_on == 34.0
        assert S1_FLOOR_OVERHEAT.threshold_off == 33.0
        assert S1_FLOOR_OVERHEAT.trigger_above is True
        assert S1_FLOOR_OVERHEAT.action == SafetyAction.CLOSE_VALVE
        assert S1_FLOOR_OVERHEAT.priority == 1

    def test_s2_thresholds(self) -> None:
        """S2: on at margin < 0, off at margin > 1, trigger below."""
        assert S2_CONDENSATION.threshold_on == 0.0
        assert S2_CONDENSATION.threshold_off == 1.0
        assert S2_CONDENSATION.trigger_above is False
        assert S2_CONDENSATION.action == SafetyAction.CLOSE_VALVE
        assert S2_CONDENSATION.priority == 1

    def test_s3_thresholds(self) -> None:
        """S3: on at T_room < 5C, off at T_room > 6C, trigger below."""
        assert S3_EMERGENCY_HEAT.threshold_on == 5.0
        assert S3_EMERGENCY_HEAT.threshold_off == 6.0
        assert S3_EMERGENCY_HEAT.trigger_above is False
        assert S3_EMERGENCY_HEAT.action == SafetyAction.EMERGENCY_HEAT
        assert S3_EMERGENCY_HEAT.priority == 2

    def test_s4_thresholds(self) -> None:
        """S4: on at T_room > 35C, off at T_room < 34C, trigger above."""
        assert S4_EMERGENCY_COOL.threshold_on == 35.0
        assert S4_EMERGENCY_COOL.threshold_off == 34.0
        assert S4_EMERGENCY_COOL.trigger_above is True
        assert S4_EMERGENCY_COOL.action == SafetyAction.EMERGENCY_COOL
        assert S4_EMERGENCY_COOL.priority == 2

    def test_s5_thresholds(self) -> None:
        """S5: on at age > 15 min, off at age < 5 min, trigger above."""
        assert S5_WATCHDOG.threshold_on == 15.0
        assert S5_WATCHDOG.threshold_off == 5.0
        assert S5_WATCHDOG.trigger_above is True
        assert S5_WATCHDOG.action == SafetyAction.FALLBACK_HP_CURVE
        assert S5_WATCHDOG.priority == 3

    def test_priorities_ordered(self) -> None:
        """Rules in DEFAULT_SAFETY_RULES are sorted by priority."""
        priorities = [r.priority for r in DEFAULT_SAFETY_RULES]
        assert priorities == sorted(priorities)

    def test_all_rules_have_unique_names(self) -> None:
        """Each rule has a unique name."""
        names = [r.name for r in DEFAULT_SAFETY_RULES]
        assert len(names) == len(set(names))

    def test_s2_condition_computes_condensation_margin(self) -> None:
        """S2 condition extracts T_floor - (T_dew + 2)."""
        # T_room=20, humidity=50 => T_dew = 20 - (100-50)/5 = 10
        # margin = T_floor - (10 + 2) = T_floor - 12
        snap = _normal_snapshot(T_floor=11.0, T_room=20.0, humidity=50.0)
        margin = S2_CONDENSATION.condition(snap)
        assert margin == pytest.approx(-1.0)

    def test_s2_condition_safe_margin(self) -> None:
        """S2 margin is positive when floor is well above dew point."""
        # T_room=20, humidity=50 => T_dew=10, margin = 25 - 12 = 13
        snap = _normal_snapshot(T_floor=25.0, T_room=20.0, humidity=50.0)
        margin = S2_CONDENSATION.condition(snap)
        assert margin == pytest.approx(13.0)


# ---------------------------------------------------------------------------
# SafetyEvaluator tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSafetyEvaluator:
    """SafetyEvaluator stateful evaluator tests."""

    def test_no_rules_triggered_normal_conditions(self) -> None:
        """Normal snapshot triggers no rules."""
        evaluator = SafetyEvaluator()
        results = evaluator.evaluate(_normal_snapshot())
        assert all(not r.triggered for r in results)
        assert len(results) == 5

    def test_s1_triggers_on_floor_overheat(self) -> None:
        """S1 triggers when T_floor > 34C."""
        evaluator = SafetyEvaluator()
        snap = _normal_snapshot(T_floor=34.5)
        results = evaluator.evaluate(snap)
        s1 = next(r for r in results if r.rule.name == "S1_floor_overheat")
        assert s1.triggered is True
        assert s1.action == SafetyAction.CLOSE_VALVE
        assert s1.measured_value == 34.5

    def test_s1_does_not_trigger_at_exactly_34(self) -> None:
        """S1 uses strict > comparison, so exactly 34.0 does NOT trigger."""
        evaluator = SafetyEvaluator()
        snap = _normal_snapshot(T_floor=34.0)
        results = evaluator.evaluate(snap)
        s1 = next(r for r in results if r.rule.name == "S1_floor_overheat")
        assert s1.triggered is False

    def test_s1_hysteresis_stays_active(self) -> None:
        """S1 stays active at T_floor=33.5 (between on=34 and off=33)."""
        evaluator = SafetyEvaluator()
        # Trigger S1
        evaluator.evaluate(_normal_snapshot(T_floor=34.5))
        # Drop to 33.5 -- still above threshold_off=33
        results = evaluator.evaluate(_normal_snapshot(T_floor=33.5))
        s1 = next(r for r in results if r.rule.name == "S1_floor_overheat")
        assert s1.triggered is True

    def test_s1_hysteresis_clears_below_off(self) -> None:
        """S1 clears when T_floor drops below threshold_off=33C."""
        evaluator = SafetyEvaluator()
        # Trigger
        evaluator.evaluate(_normal_snapshot(T_floor=34.5))
        # Clear
        results = evaluator.evaluate(_normal_snapshot(T_floor=32.5))
        s1 = next(r for r in results if r.rule.name == "S1_floor_overheat")
        assert s1.triggered is False
        assert s1.action is None

    def test_s2_triggers_on_condensation_risk(self) -> None:
        """S2 triggers when condensation margin < 0."""
        evaluator = SafetyEvaluator()
        # T_room=20, humidity=80 => T_dew = 20-(100-80)/5 = 16
        # margin = T_floor - (16+2) = 17 - 18 = -1
        snap = _normal_snapshot(T_floor=17.0, T_room=20.0, humidity=80.0)
        results = evaluator.evaluate(snap)
        s2 = next(r for r in results if r.rule.name == "S2_condensation")
        assert s2.triggered is True
        assert s2.action == SafetyAction.CLOSE_VALVE

    def test_s2_does_not_trigger_safe_margin(self) -> None:
        """S2 does not trigger when margin is comfortably above 0."""
        evaluator = SafetyEvaluator()
        snap = _normal_snapshot(T_floor=25.0, T_room=20.0, humidity=50.0)
        results = evaluator.evaluate(snap)
        s2 = next(r for r in results if r.rule.name == "S2_condensation")
        assert s2.triggered is False

    def test_s2_with_very_low_humidity(self) -> None:
        """S2 never triggers with very low humidity (large margin)."""
        evaluator = SafetyEvaluator()
        # humidity=5 => T_dew = 20-(100-5)/5 = 20-19 = 1
        # margin = 25 - (1+2) = 22
        snap = _normal_snapshot(T_floor=25.0, T_room=20.0, humidity=5.0)
        results = evaluator.evaluate(snap)
        s2 = next(r for r in results if r.rule.name == "S2_condensation")
        assert s2.triggered is False
        assert s2.measured_value == pytest.approx(22.0)

    def test_s2_with_100_percent_humidity(self) -> None:
        """S2 with 100% humidity: T_dew=T_room, margin = T_floor - (T_room+2)."""
        evaluator = SafetyEvaluator()
        # T_dew = 20, margin = 21 - (20+2) = -1 => triggers
        snap = _normal_snapshot(T_floor=21.0, T_room=20.0, humidity=100.0)
        results = evaluator.evaluate(snap)
        s2 = next(r for r in results if r.rule.name == "S2_condensation")
        assert s2.triggered is True

    def test_s3_triggers_emergency_heat(self) -> None:
        """S3 triggers when T_room < 5C."""
        evaluator = SafetyEvaluator()
        snap = _normal_snapshot(T_room=4.0)
        results = evaluator.evaluate(snap)
        s3 = next(r for r in results if r.rule.name == "S3_emergency_heat")
        assert s3.triggered is True
        assert s3.action == SafetyAction.EMERGENCY_HEAT

    def test_s3_hysteresis_stays_active_at_5_5(self) -> None:
        """S3 stays active at T_room=5.5 (between on=5 and off=6)."""
        evaluator = SafetyEvaluator()
        evaluator.evaluate(_normal_snapshot(T_room=4.0))
        results = evaluator.evaluate(_normal_snapshot(T_room=5.5))
        s3 = next(r for r in results if r.rule.name == "S3_emergency_heat")
        assert s3.triggered is True

    def test_s3_hysteresis_clears_at_6(self) -> None:
        """S3 clears when T_room rises above threshold_off=6C."""
        evaluator = SafetyEvaluator()
        evaluator.evaluate(_normal_snapshot(T_room=4.0))
        results = evaluator.evaluate(_normal_snapshot(T_room=6.5))
        s3 = next(r for r in results if r.rule.name == "S3_emergency_heat")
        assert s3.triggered is False

    def test_s4_triggers_emergency_cool(self) -> None:
        """S4 triggers when T_room > 35C."""
        evaluator = SafetyEvaluator()
        snap = _normal_snapshot(T_room=36.0)
        results = evaluator.evaluate(snap)
        s4 = next(r for r in results if r.rule.name == "S4_emergency_cool")
        assert s4.triggered is True
        assert s4.action == SafetyAction.EMERGENCY_COOL

    def test_s5_triggers_watchdog_timeout(self) -> None:
        """S5 triggers when last_update_age_minutes > 15."""
        evaluator = SafetyEvaluator()
        snap = _normal_snapshot(last_update_age_minutes=20.0)
        results = evaluator.evaluate(snap)
        s5 = next(r for r in results if r.rule.name == "S5_watchdog")
        assert s5.triggered is True
        assert s5.action == SafetyAction.FALLBACK_HP_CURVE

    def test_s5_does_not_trigger_at_exactly_15(self) -> None:
        """S5 uses strict > comparison, so exactly 15.0 does NOT trigger."""
        evaluator = SafetyEvaluator()
        snap = _normal_snapshot(last_update_age_minutes=15.0)
        results = evaluator.evaluate(snap)
        s5 = next(r for r in results if r.rule.name == "S5_watchdog")
        assert s5.triggered is False

    def test_s5_clears_after_update(self) -> None:
        """S5 clears when last_update_age_minutes drops below 5."""
        evaluator = SafetyEvaluator()
        evaluator.evaluate(_normal_snapshot(last_update_age_minutes=20.0))
        results = evaluator.evaluate(_normal_snapshot(last_update_age_minutes=3.0))
        s5 = next(r for r in results if r.rule.name == "S5_watchdog")
        assert s5.triggered is False

    def test_s5_hysteresis_stays_active_between_thresholds(self) -> None:
        """S5 stays active at age=10 (between on=15 and off=5)."""
        evaluator = SafetyEvaluator()
        evaluator.evaluate(_normal_snapshot(last_update_age_minutes=20.0))
        results = evaluator.evaluate(_normal_snapshot(last_update_age_minutes=10.0))
        s5 = next(r for r in results if r.rule.name == "S5_watchdog")
        assert s5.triggered is True

    def test_multiple_rules_can_trigger_simultaneously(self) -> None:
        """Multiple rules can be active at the same time."""
        evaluator = SafetyEvaluator()
        # S1 (T_floor=35 > 34) and S5 (age=20 > 15)
        snap = _normal_snapshot(T_floor=35.0, last_update_age_minutes=20.0)
        results = evaluator.evaluate(snap)
        triggered = [r for r in results if r.triggered]
        triggered_names = {r.rule.name for r in triggered}
        assert "S1_floor_overheat" in triggered_names
        assert "S5_watchdog" in triggered_names
        assert len(triggered) >= 2

    def test_results_sorted_by_priority(self) -> None:
        """Results are returned sorted by priority (lowest number first)."""
        evaluator = SafetyEvaluator()
        results = evaluator.evaluate(_normal_snapshot())
        priorities = [r.rule.priority for r in results]
        assert priorities == sorted(priorities)

    def test_get_active_rules_returns_only_triggered(self) -> None:
        """get_active_rules returns only rules currently active."""
        evaluator = SafetyEvaluator()
        evaluator.evaluate(_normal_snapshot(T_floor=35.0))
        active = evaluator.get_active_rules()
        assert len(active) == 1
        assert active[0].rule.name == "S1_floor_overheat"
        assert active[0].triggered is True

    def test_get_active_rules_empty_when_none_active(self) -> None:
        """get_active_rules returns empty list under normal conditions."""
        evaluator = SafetyEvaluator()
        evaluator.evaluate(_normal_snapshot())
        assert evaluator.get_active_rules() == []

    def test_reset_clears_all_active_states(self) -> None:
        """reset() deactivates all rules."""
        evaluator = SafetyEvaluator()
        evaluator.evaluate(_normal_snapshot(T_floor=35.0))
        assert len(evaluator.active_rule_names) > 0
        evaluator.reset()
        assert evaluator.active_rule_names == []

    def test_active_rule_names_property(self) -> None:
        """active_rule_names returns names of currently active rules."""
        evaluator = SafetyEvaluator()
        evaluator.evaluate(
            _normal_snapshot(T_floor=35.0, last_update_age_minutes=20.0)
        )
        names = evaluator.active_rule_names
        assert "S1_floor_overheat" in names
        assert "S5_watchdog" in names

    def test_custom_rules_override_defaults(self) -> None:
        """SafetyEvaluator accepts custom rules instead of defaults."""
        custom_s1 = SafetyRule(
            name="S1_custom",
            description="Custom floor overheat at 30C",
            priority=1,
            threshold_on=30.0,
            threshold_off=29.0,
            action=SafetyAction.CLOSE_VALVE,
            condition=lambda s: s.T_floor,
            trigger_above=True,
        )
        evaluator = SafetyEvaluator(rules=(custom_s1,))
        # Default 34C would not trigger, but custom 30C does
        results = evaluator.evaluate(_normal_snapshot(T_floor=31.0))
        assert len(results) == 1
        assert results[0].triggered is True
        assert results[0].rule.name == "S1_custom"

    def test_oscillation_prevention(self) -> None:
        """Hysteresis prevents oscillation around the threshold.

        Simulates T_floor oscillating around 34C. Without hysteresis the
        rule would toggle on/off every step. With the 1-degree band
        (on=34, off=33) the rule stays active once triggered until the
        temperature drops below 33.
        """
        evaluator = SafetyEvaluator()
        temperatures = [33.5, 34.1, 33.8, 33.5, 33.2, 32.9, 33.1]
        expected_active = [False, True, True, True, True, False, False]

        for temp, expected in zip(temperatures, expected_active, strict=True):
            results = evaluator.evaluate(_normal_snapshot(T_floor=temp))
            s1 = next(r for r in results if r.rule.name == "S1_floor_overheat")
            assert s1.triggered is expected, (
                f"T_floor={temp}: expected triggered={expected}, "
                f"got {s1.triggered}"
            )

    def test_evaluator_with_empty_rules(self) -> None:
        """SafetyEvaluator with no rules returns empty results."""
        evaluator = SafetyEvaluator(rules=())
        results = evaluator.evaluate(_normal_snapshot())
        assert results == []

    def test_result_action_none_when_not_triggered(self) -> None:
        """SafetyRuleResult.action is None when the rule is not triggered."""
        evaluator = SafetyEvaluator()
        results = evaluator.evaluate(_normal_snapshot())
        for result in results:
            assert result.triggered is False
            assert result.action is None

    def test_safety_rule_result_frozen(self) -> None:
        """SafetyRuleResult is immutable."""
        result = SafetyRuleResult(
            rule=S1_FLOOR_OVERHEAT,
            triggered=True,
            measured_value=35.0,
            action=SafetyAction.CLOSE_VALVE,
        )
        with pytest.raises(AttributeError):
            result.triggered = False  # type: ignore[misc]
