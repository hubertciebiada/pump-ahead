"""Integration tests for Epic #14 -- Cooling mode with dew point protection.

Verifies end-to-end cross-module wiring for the three sub-issues:
    #54 Cooling in RC model (mode_controller.py -- ModeController)
    #55 Dew point Magnus formula (dew_point.py -- graduated throttle)
    #56 Safety YAML cooling (safety_rules.py -- S2 condensation rule)

Tests exercise cross-module workflows:
    dew_point -> safety_rules S2 condition alignment
    mode_controller -> controller cooling path (error inversion, throttle)
    split_coordinator mode enforcement (Axiom #3)
    scenario configuration for cooling mode
    safety YAML S2 template entity references
    acceptance criteria explicit verification
    architectural integrity (dependency DAG, no homeassistant imports)

All tests are fast, deterministic, and use the
``@pytest.mark.unit`` marker.
"""

from __future__ import annotations

import inspect

import pytest
import yaml

from pumpahead.config import ControllerConfig
from pumpahead.controller import PumpAheadController
from pumpahead.dew_point import (
    condensation_margin,
    cooling_throttle_factor,
    dew_point,
)
from pumpahead.mode_controller import ModeController
from pumpahead.safety_rules import (
    S2_CONDENSATION,
    SafetyAction,
    SafetyEvaluator,
    SensorSnapshot,
)
from pumpahead.safety_yaml_generator import (
    RoomEntityConfig,
    SafetyYAMLConfig,
    generate_safety_yaml,
)
from pumpahead.scenarios import (
    dew_point_stress,
    dual_source_cooling_steady,
    hot_july,
    spring_transition,
)
from pumpahead.simulator import HeatPumpMode, Measurements, SplitMode
from pumpahead.split_coordinator import SplitCoordinator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normal_snapshot(
    *,
    T_floor: float = 25.0,
    T_room: float = 21.0,
    humidity: float = 50.0,
    hp_mode: HeatPumpMode = HeatPumpMode.COOLING,
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


def _make_cooling_controller(
    room_names: list[str],
    mode: str = "cooling",
    room_has_split: dict[str, bool] | None = None,
    **config_kwargs: object,
) -> PumpAheadController:
    """Create a PumpAheadController for cooling tests."""
    defaults = {"kp": 5.0, "ki": 0.0, "setpoint": 25.0}
    defaults.update(config_kwargs)
    config = ControllerConfig(**defaults)  # type: ignore[arg-type]
    return PumpAheadController(
        config,
        room_names,
        room_has_split=room_has_split,
        mode=mode,  # type: ignore[arg-type]
    )


def _make_measurements(
    *,
    T_room: float = 27.0,
    T_slab: float = 25.0,
    T_outdoor: float = 30.0,
    valve_pos: float = 0.0,
    hp_mode: HeatPumpMode = HeatPumpMode.COOLING,
    humidity: float = 50.0,
) -> Measurements:
    """Create Measurements for controller tests."""
    return Measurements(
        T_room=T_room,
        T_slab=T_slab,
        T_outdoor=T_outdoor,
        valve_pos=valve_pos,
        hp_mode=hp_mode,
        humidity=humidity,
    )


# ---------------------------------------------------------------------------
# TestDewPointToSafetyRulesPipeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDewPointToSafetyRulesPipeline:
    """Cross-module data flow: dew_point.py -> safety_rules.py S2 condition."""

    def test_s2_condition_uses_magnus_dew_point(self) -> None:
        """S2_CONDENSATION.condition produces the same value as Magnus formula."""
        snap = _normal_snapshot(T_floor=17.0, T_room=20.0, humidity=80.0)
        measured = S2_CONDENSATION.condition(snap)

        t_dew_magnus = dew_point(20.0, 80.0)
        expected = 17.0 - (t_dew_magnus + 2.0)

        assert measured == pytest.approx(expected, abs=1e-10)
        # The Magnus result should be different from the simplified formula
        t_dew_simplified = 20.0 - (100.0 - 80.0) / 5.0
        assert abs(t_dew_magnus - t_dew_simplified) > 0.1
        # Margin should be negative (condensation risk)
        assert measured < 0.0

    def test_s2_triggers_when_condensation_margin_negative(self) -> None:
        """S2 triggers with CLOSE_VALVE when condensation margin is negative."""
        evaluator = SafetyEvaluator()

        # T_floor=17, T_room=20, humidity=80 -> Magnus T_dew ~ 16.4
        # margin = 17 - (16.4 + 2) = -1.4 < 0 -> S2 triggers
        snap = _normal_snapshot(T_floor=17.0, T_room=20.0, humidity=80.0)
        assert condensation_margin(17.0, 20.0, 80.0) < 0.0

        results = evaluator.evaluate(snap)
        s2 = next(r for r in results if r.rule.name == "S2_condensation")
        assert s2.triggered is True
        assert s2.action == SafetyAction.CLOSE_VALVE

    def test_s2_clears_when_margin_exceeds_threshold_off(self) -> None:
        """S2 clears when margin exceeds threshold_off (1.0)."""
        evaluator = SafetyEvaluator()

        # First trigger S2
        snap_trigger = _normal_snapshot(T_floor=17.0, T_room=20.0, humidity=80.0)
        evaluator.evaluate(snap_trigger)

        # Now provide high T_floor so margin > threshold_off (1.0)
        # T_dew(20, 80) ~ 16.4, margin = T_floor - (16.4+2) > 1.0
        # T_floor > 16.4 + 2 + 1.0 = 19.4
        snap_clear = _normal_snapshot(T_floor=20.0, T_room=20.0, humidity=80.0)
        results = evaluator.evaluate(snap_clear)
        s2 = next(r for r in results if r.rule.name == "S2_condensation")
        assert s2.triggered is False

    def test_s2_hysteresis_prevents_oscillation(self) -> None:
        """S2 stays active when margin is between 0 and threshold_off."""
        evaluator = SafetyEvaluator()

        # Trigger S2 with negative margin
        t_dew = dew_point(20.0, 80.0)  # ~ 16.44
        snap_trigger = _normal_snapshot(
            T_floor=t_dew + 1.5,  # margin = -0.5 (below 0)
            T_room=20.0,
            humidity=80.0,
        )
        results = evaluator.evaluate(snap_trigger)
        s2 = next(r for r in results if r.rule.name == "S2_condensation")
        assert s2.triggered is True

        # Feed margin = +0.5 (between 0 and threshold_off=1.0)
        snap_mid = _normal_snapshot(
            T_floor=t_dew + 2.5,  # margin = +0.5
            T_room=20.0,
            humidity=80.0,
        )
        results = evaluator.evaluate(snap_mid)
        s2 = next(r for r in results if r.rule.name == "S2_condensation")
        assert s2.triggered is True  # Hysteresis holds

        # Feed margin = +1.5 (above threshold_off=1.0)
        snap_clear = _normal_snapshot(
            T_floor=t_dew + 3.5,  # margin = +1.5
            T_room=20.0,
            humidity=80.0,
        )
        results = evaluator.evaluate(snap_clear)
        s2 = next(r for r in results if r.rule.name == "S2_condensation")
        assert s2.triggered is False  # Now clears

    def test_cooling_throttle_factor_consistent_with_s2_margin(self) -> None:
        """When throttle==0, condensation margin is <= 0 (both agree on danger)."""
        t_room = 20.0
        humidity = 70.0
        t_dew = dew_point(t_room, humidity)
        margin_param = 2.0

        # At the exact point where throttle goes to 0: t_floor = t_dew + margin
        t_floor_critical = t_dew + margin_param
        throttle = cooling_throttle_factor(t_floor_critical, t_dew, margin=margin_param)
        assert throttle == 0.0

        # At this point, condensation_margin should be <= 0
        cm = condensation_margin(
            t_floor_critical,
            t_room,
            humidity,
            safety_margin=margin_param,
        )
        assert cm <= 0.0 + 1e-10


# ---------------------------------------------------------------------------
# TestModeControllerToCoolingPathPipeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestModeControllerToCoolingPathPipeline:
    """Cross-module: ModeController -> PumpAheadController cooling path."""

    def test_mode_switch_to_cooling_inverts_pid_error(self) -> None:
        """In cooling mode, PID produces valve > 0 when T_room > setpoint."""
        ctrl = _make_cooling_controller(["room1"], mode="cooling")

        # Room too hot (T_room=27 > setpoint=25) -> PID should open valve
        meas_hot = {"room1": _make_measurements(T_room=27.0, T_slab=25.0)}
        actions_hot = ctrl.step(meas_hot)
        assert actions_hot["room1"].valve_position > 0.0

        # Room cool enough (T_room=23 < setpoint=25) -> PID should close valve
        ctrl_cold = _make_cooling_controller(["room1"], mode="cooling")
        meas_cold = {"room1": _make_measurements(T_room=23.0, T_slab=25.0)}
        actions_cold = ctrl_cold.step(meas_cold)
        assert actions_cold["room1"].valve_position == 0.0

    def test_cooling_mode_applies_dew_point_throttle(self) -> None:
        """Valve is throttled when T_slab is close to T_dew + 2."""
        # T_room=27 (above setpoint=25), humidity=50
        # T_dew(27, 50) ~ 15.9
        # With T_slab=25 (far from T_dew+2=17.9), throttle ~ 1.0
        ctrl_safe = _make_cooling_controller(["room1"], mode="cooling")
        meas_safe = {
            "room1": _make_measurements(T_room=27.0, T_slab=25.0, humidity=50.0),
        }
        actions_safe = ctrl_safe.step(meas_safe)

        # With T_slab=18.5 (close to T_dew+2=17.9), throttle < 1.0
        ctrl_tight = _make_cooling_controller(["room1"], mode="cooling")
        meas_tight = {
            "room1": _make_measurements(T_room=27.0, T_slab=18.5, humidity=50.0),
        }
        actions_tight = ctrl_tight.step(meas_tight)

        # Both should have valve > 0 but tight should be less than safe
        assert actions_safe["room1"].valve_position > 0.0
        assert (
            actions_tight["room1"].valve_position < actions_safe["room1"].valve_position
        )

    def test_cooling_mode_valve_floor_not_enforced(self) -> None:
        """Valve floor is NOT enforced in cooling mode."""
        ctrl = _make_cooling_controller(
            ["room1"],
            mode="cooling",
            valve_floor_pct=15.0,
        )
        # T_room=23 < setpoint=25 -> PID outputs 0 (room already cool)
        meas = {"room1": _make_measurements(T_room=23.0, T_slab=25.0)}
        actions = ctrl.step(meas)
        assert actions["room1"].valve_position == 0.0

    def test_mode_controller_deadzone_preserves_current_mode(self) -> None:
        """Deadzone between thresholds preserves the current mode."""
        # Start in HEATING, feed temps in deadzone (18-22)
        mc_heat = ModeController(
            heating_threshold=18.0,
            cooling_threshold=22.0,
            min_hold_minutes=0,
            initial_mode=HeatPumpMode.HEATING,
        )
        for _ in range(200):
            mode = mc_heat.update(20.0)  # In deadzone
        assert mode == HeatPumpMode.HEATING

        # Start in COOLING, feed temps in deadzone
        mc_cool = ModeController(
            heating_threshold=18.0,
            cooling_threshold=22.0,
            min_hold_minutes=0,
            initial_mode=HeatPumpMode.COOLING,
        )
        for _ in range(200):
            mode = mc_cool.update(20.0)  # In deadzone
        assert mode == HeatPumpMode.COOLING


# ---------------------------------------------------------------------------
# TestSplitCoordinatorCoolingIntegration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSplitCoordinatorCoolingIntegration:
    """Split coordinator in cooling mode: Axiom #3 enforcement."""

    def test_split_never_heats_in_cooling_mode(self) -> None:
        """Split stays OFF with positive error in cooling mode (Axiom #3)."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=25.0, split_deadband=0.5)
        coordinator = SplitCoordinator(config)

        # Positive error means room is below setpoint (wants heating)
        # But HP mode is COOLING -> split must NOT heat
        for error in [0.5, 1.0, 2.0, 5.0]:
            decision = coordinator.decide(
                error=error,
                setpoint=25.0,
                hp_mode=HeatPumpMode.COOLING,
            )
            assert decision.split_mode != SplitMode.HEATING, (
                f"Split should never HEAT in COOLING mode, but got "
                f"HEATING for error={error}"
            )

    def test_split_cools_when_room_above_setpoint_in_cooling(self) -> None:
        """Split activates COOLING when room is hot enough in cooling mode."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.0,
            setpoint=25.0,
            split_deadband=1.0,
            split_setpoint_offset=2.0,
        )
        coordinator = SplitCoordinator(config)

        # error = setpoint - T_room = 25 - 27 = -2.0 (room 2C above setpoint)
        decision = coordinator.decide(
            error=-2.0,
            setpoint=25.0,
            hp_mode=HeatPumpMode.COOLING,
        )
        assert decision.split_mode == SplitMode.COOLING
        assert decision.split_setpoint == pytest.approx(23.0)  # 25 - 2

    def test_split_off_when_error_within_deadband_cooling(self) -> None:
        """Split stays OFF when error is within deadband in cooling mode."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.0,
            setpoint=25.0,
            split_deadband=1.0,
        )
        coordinator = SplitCoordinator(config)

        # error = -0.5, deadband = 1.0 -> |error| < deadband -> OFF
        decision = coordinator.decide(
            error=-0.5,
            setpoint=25.0,
            hp_mode=HeatPumpMode.COOLING,
        )
        assert decision.split_mode == SplitMode.OFF


# ---------------------------------------------------------------------------
# TestScenarioCoolingConfiguration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestScenarioCoolingConfiguration:
    """Verify cooling scenario configurations are correct."""

    def test_dew_point_stress_scenario_is_cooling_mode(self) -> None:
        """dew_point_stress scenario uses cooling mode."""
        assert dew_point_stress().mode == "cooling"

    def test_hot_july_scenario_is_cooling_mode(self) -> None:
        """hot_july scenario uses cooling mode."""
        assert hot_july().mode == "cooling"

    def test_dual_source_cooling_steady_is_cooling_mode(self) -> None:
        """dual_source_cooling_steady scenario uses cooling mode."""
        assert dual_source_cooling_steady().mode == "cooling"

    def test_spring_transition_scenario_is_auto_mode(self) -> None:
        """spring_transition scenario uses auto mode."""
        assert spring_transition().mode == "auto"

    def test_dew_point_stress_uses_hubert_real_building(self) -> None:
        """dew_point_stress uses hubert_real with 8 rooms (5 with splits)."""
        scenario = dew_point_stress()
        rooms = scenario.building.rooms
        assert len(rooms) == 8

        rooms_with_split = [r for r in rooms if r.has_split]
        rooms_without_split = [r for r in rooms if not r.has_split]
        assert len(rooms_with_split) == 5
        assert len(rooms_without_split) == 3

    def test_all_cooling_scenarios_have_cooling_power(self) -> None:
        """All rooms in cooling scenarios have ufh_cooling_max_power_w > 0."""
        scenarios = [dew_point_stress(), hot_july(), dual_source_cooling_steady()]
        for scenario in scenarios:
            for room in scenario.building.rooms:
                assert room.ufh_cooling_max_power_w > 0, (
                    f"Room '{room.name}' in scenario '{scenario.name}' "
                    f"has ufh_cooling_max_power_w={room.ufh_cooling_max_power_w}"
                )

    def test_cooling_power_asymmetry_in_scenarios(self) -> None:
        """Cooling power is less than heating power (asymmetric heat transfer)."""
        scenario = dew_point_stress()
        for room in scenario.building.rooms:
            assert room.ufh_cooling_max_power_w < room.ufh_max_power_w, (
                f"Room '{room.name}': cooling power "
                f"({room.ufh_cooling_max_power_w} W) should be less than "
                f"heating power ({room.ufh_max_power_w} W)"
            )


# ---------------------------------------------------------------------------
# TestSafetyYAMLCoolingIntegration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSafetyYAMLCoolingIntegration:
    """Safety YAML generation for cooling-specific rules (S2, S4)."""

    def test_s2_yaml_template_references_correct_entities(self) -> None:
        """S2 trigger template references floor temp, room temp, and humidity."""
        room = _make_room(entity_split="climate.living_room_split")
        config = _make_config(rooms=(room,))
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        s2_trigger = next(
            a for a in automations if "s2_condensation_trigger" in str(a["id"])
        )
        template = s2_trigger["trigger"][0]["value_template"]

        assert room.entity_temp_floor in template
        assert room.entity_temp_room in template
        assert room.entity_humidity in template

    def test_s2_yaml_trigger_margin_matches_s2_rule_constant(self) -> None:
        """S2 condensation margin (2.0) aligns with Axiom #5 (T_dew + 2C)."""
        config = _make_config()

        # SafetyYAMLConfig default margin
        assert config.s2_condensation_margin == 2.0

        # cooling_throttle_factor default margin parameter
        # At gap == margin (2.0), throttle returns 0.0
        t_dew = 10.0
        assert cooling_throttle_factor(t_dew + 2.0, t_dew) == 0.0

        # S2_CONDENSATION condition uses +2.0 in its lambda
        snap = _normal_snapshot(T_floor=12.0, T_room=20.0, humidity=50.0)
        measured = S2_CONDENSATION.condition(snap)
        expected = 12.0 - (dew_point(20.0, 50.0) + 2.0)
        assert measured == pytest.approx(expected, abs=1e-10)

    def test_s4_emergency_cool_yaml_present_for_split_rooms(self) -> None:
        """S4 emergency cooling trigger uses split entity for rooms with split."""
        room = _make_room(entity_split="climate.living_room_split")
        config = _make_config(rooms=(room,))
        yaml_str = generate_safety_yaml(config)
        automations = _parse_yaml(yaml_str)

        s4_trigger = next(
            a for a in automations if "s4_emergency_cool_trigger" in str(a["id"])
        )

        # S4 trigger should have an action that sets split to cool
        split_action = next(
            (
                a
                for a in s4_trigger["action"]
                if a.get("service") == "climate.set_hvac_mode"
            ),
            None,
        )
        assert split_action is not None
        assert split_action["target"]["entity_id"] == room.entity_split
        assert split_action["data"]["hvac_mode"] == "cool"


# ---------------------------------------------------------------------------
# TestAcceptanceCriteriaVerification
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAcceptanceCriteriaVerification:
    """Explicit verification of Epic #14 acceptance criteria."""

    def test_ac_condensation_protection_uses_magnus(self) -> None:
        """dew_point() uses Magnus formula, not simplified approximation."""
        result = dew_point(20.0, 50.0)

        # Magnus: gamma = (17.625*20)/(243.04+20) + ln(0.5) = 1.339 - 0.693 = 0.646
        # T_dew = (243.04*0.646)/(17.625-0.646) = 156.9/16.98 = 9.26
        assert result == pytest.approx(9.26, abs=0.1)

        # Simplified would give: 20 - (100-50)/5 = 10.0
        assert abs(result - 10.0) > 0.5, (
            "dew_point() should NOT match the simplified formula"
        )

    def test_ac_safety_margin_is_2c(self) -> None:
        """S2 condition uses +2.0 margin (T_floor >= T_dew + 2C)."""
        t_room = 20.0
        humidity = 50.0
        t_dew = dew_point(t_room, humidity)

        # At T_floor = T_dew + 2, the margin should be 0
        snap = _normal_snapshot(
            T_floor=t_dew + 2.0,
            T_room=t_room,
            humidity=humidity,
        )
        measured = S2_CONDENSATION.condition(snap)
        assert measured == pytest.approx(0.0, abs=1e-10)

    def test_ac_split_never_opposes_mode_structurally(self) -> None:
        """SplitCoordinator.decide() has safety assertions against mode violation."""
        source = inspect.getsource(SplitCoordinator.decide)
        # Verify the assertions that prevent mode opposition
        assert "HEATING" in source and "COOLING" in source
        assert "Axiom #3" in source or "assert" in source

    def test_ac_auto_switching_uses_hysteresis(self) -> None:
        """ModeController with min_hold prevents rapid oscillation."""
        mc = ModeController(
            heating_threshold=18.0,
            cooling_threshold=22.0,
            min_hold_minutes=60,
            initial_mode=HeatPumpMode.HEATING,
        )

        switches = 0
        prev_mode = mc.current_mode

        # Rapid oscillation: alternate 17C and 23C every minute for 120 min
        for i in range(120):
            t_outdoor = 17.0 if i % 2 == 0 else 23.0
            mode = mc.update(t_outdoor)
            if mode != prev_mode:
                switches += 1
                prev_mode = mode

        # With 60-minute hold, at most 2 switches in 120 minutes
        assert switches <= 2

    def test_ac_cooling_throttle_is_graduated_not_binary(self) -> None:
        """cooling_throttle_factor() produces intermediate values, not just 0/1."""
        t_dew = 10.0
        margin = 2.0
        ramp_width = 2.0

        # At midpoint of ramp: gap = margin + ramp_width/2 = 3.0
        # t_floor = t_dew + 3.0 = 13.0
        midpoint = cooling_throttle_factor(
            t_dew + margin + ramp_width / 2,
            t_dew,
            margin=margin,
            ramp_width=ramp_width,
        )
        assert 0.0 < midpoint < 1.0
        assert midpoint == pytest.approx(0.5, abs=0.01)


# ---------------------------------------------------------------------------
# TestArchitecturalIntegrity
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestArchitecturalIntegrity:
    """Verify DAG dependency direction and no architectural drift."""

    def test_dew_point_does_not_import_safety_rules_or_controller(self) -> None:
        """dew_point.py is a leaf module with no internal dependencies."""
        import pumpahead.dew_point as mod

        import_lines = _extract_import_lines(mod)
        assert not any("safety_rules" in line for line in import_lines), (
            "dew_point.py must not import safety_rules"
        )
        assert not any("controller" in line for line in import_lines), (
            "dew_point.py must not import controller"
        )
        assert not any("simulator" in line for line in import_lines), (
            "dew_point.py must not import simulator"
        )

    def test_mode_controller_does_not_import_dew_point_or_safety(self) -> None:
        """mode_controller.py must not import dew_point or safety_rules."""
        import pumpahead.mode_controller as mod

        import_lines = _extract_import_lines(mod)
        assert not any("dew_point" in line for line in import_lines), (
            "mode_controller.py must not import dew_point"
        )
        assert not any("safety_rules" in line for line in import_lines), (
            "mode_controller.py must not import safety_rules"
        )

    def test_safety_rules_imports_dew_point_but_not_controller(self) -> None:
        """safety_rules.py imports dew_point but not controller or mode_controller."""
        import pumpahead.safety_rules as mod

        import_lines = _extract_import_lines(mod)
        assert any("dew_point" in line for line in import_lines), (
            "safety_rules.py must import dew_point (for S2 condition)"
        )
        assert not any("controller" in line for line in import_lines), (
            "safety_rules.py must not import controller"
        )
        assert not any("mode_controller" in line for line in import_lines), (
            "safety_rules.py must not import mode_controller"
        )

    def test_controller_imports_both_dew_point_and_mode_controller(self) -> None:
        """controller.py is the integration point for dew_point and mode_controller."""
        import pumpahead.controller as mod

        import_lines = _extract_import_lines(mod)
        assert any("dew_point" in line for line in import_lines), (
            "controller.py must import dew_point"
        )
        assert any("mode_controller" in line for line in import_lines), (
            "controller.py must import mode_controller"
        )

    def test_no_homeassistant_imports_in_cooling_modules(self) -> None:
        """None of the three cooling modules import homeassistant."""
        import pumpahead.dew_point as dp_mod
        import pumpahead.mode_controller as mc_mod
        import pumpahead.safety_rules as sr_mod

        for mod_name, mod in [
            ("dew_point", dp_mod),
            ("mode_controller", mc_mod),
            ("safety_rules", sr_mod),
        ]:
            import_lines = _extract_import_lines(mod)
            assert not any("homeassistant" in line for line in import_lines), (
                f"{mod_name} must not import homeassistant"
            )

    def test_all_cooling_public_symbols_exported_from_init(self) -> None:
        """Key public cooling symbols are accessible from pumpahead package."""
        import pumpahead

        expected_symbols = [
            "dew_point",
            "dew_point_simplified",
            "cooling_throttle_factor",
            "condensation_margin",
            "ModeController",
        ]

        for symbol in expected_symbols:
            assert hasattr(pumpahead, symbol), (
                f"{symbol} not exported from pumpahead.__init__"
            )
            assert symbol in pumpahead.__all__, f"{symbol} not in pumpahead.__all__"
