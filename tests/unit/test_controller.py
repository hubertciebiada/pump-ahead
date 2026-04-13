"""Unit tests for PIDController and PumpAheadController.

Tests cover core PID behaviour (proportional, integral, derivative),
anti-windup via back-calculation, output clamping, reset, and the
multi-room orchestrator with valve floor minimum enforcement.
"""

from __future__ import annotations

import pytest

from pumpahead.config import ControllerConfig, CWUCycle
from pumpahead.controller import PIDController, PumpAheadController
from pumpahead.cwu_coordinator import CWU_HEAVY
from pumpahead.simulator import Actions, HeatPumpMode, Measurements, SplitMode

# ---------------------------------------------------------------------------
# PIDController unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPIDProportional:
    """Proportional-only PID behaviour."""

    def test_proportional_positive_error(self) -> None:
        """Positive error produces proportional output clamped to [0, 100]."""
        pid = PIDController(kp=5.0, ki=0.0, kd=0.0)
        output = pid.compute(2.0)
        assert output == pytest.approx(10.0)

    def test_proportional_large_error_clamps_to_max(self) -> None:
        """Large positive error clamps output to 100 %."""
        pid = PIDController(kp=5.0, ki=0.0, kd=0.0)
        output = pid.compute(30.0)
        assert output == pytest.approx(100.0)

    def test_proportional_negative_error_clamps_to_min(self) -> None:
        """Negative error (room above setpoint) clamps output to 0 %."""
        pid = PIDController(kp=5.0, ki=0.0, kd=0.0)
        output = pid.compute(-2.0)
        assert output == pytest.approx(0.0)

    def test_proportional_zero_error(self) -> None:
        """Zero error produces zero output."""
        pid = PIDController(kp=5.0, ki=0.0, kd=0.0)
        output = pid.compute(0.0)
        assert output == pytest.approx(0.0)


@pytest.mark.unit
class TestPIDIntegral:
    """Integral accumulation behaviour."""

    def test_integral_accumulation_positive_error(self) -> None:
        """Integral accumulates over multiple steps with positive error."""
        pid = PIDController(kp=0.0, ki=0.01, kd=0.0, dt=60.0)
        # Step 1: I = 0.01 * 1.0 * 60 = 0.6
        out1 = pid.compute(1.0)
        assert out1 == pytest.approx(0.6)
        assert pid.integral == pytest.approx(0.6)

        # Step 2: I = 0.6 + 0.01 * 1.0 * 60 = 1.2
        out2 = pid.compute(1.0)
        assert out2 == pytest.approx(1.2)
        assert pid.integral == pytest.approx(1.2)

    def test_integral_with_negative_error_decreases(self) -> None:
        """Integral decreases when error becomes negative."""
        pid = PIDController(kp=0.0, ki=0.01, kd=0.0, dt=60.0)
        pid.compute(2.0)  # I = 1.2
        pid.compute(-1.0)  # I = 1.2 + 0.01*(-1.0)*60 = 0.6
        assert pid.integral == pytest.approx(0.6)

    def test_integral_only_zero_gain(self) -> None:
        """Zero integral gain means integral stays at 0."""
        pid = PIDController(kp=0.0, ki=0.0, kd=0.0)
        pid.compute(5.0)
        assert pid.integral == pytest.approx(0.0)


@pytest.mark.unit
class TestPIDDerivative:
    """Derivative term behaviour."""

    def test_derivative_first_call_is_zero(self) -> None:
        """On the first call, derivative term is zero (no previous error)."""
        pid = PIDController(kp=0.0, ki=0.0, kd=1.0, dt=60.0)
        output = pid.compute(5.0)
        # D = 0 on first call, P = 0, I = 0 -> output = 0
        assert output == pytest.approx(0.0)

    def test_derivative_detects_error_change(self) -> None:
        """Derivative responds to change in error between steps."""
        pid = PIDController(kp=0.0, ki=0.0, kd=60.0, dt=60.0)
        pid.compute(1.0)  # First call: D = 0
        # Second call: D = 60.0 * (2.0 - 1.0) / 60.0 = 1.0
        output = pid.compute(2.0)
        assert output == pytest.approx(1.0)

    def test_derivative_decreasing_error(self) -> None:
        """Negative derivative when error is decreasing."""
        pid = PIDController(kp=0.0, ki=0.0, kd=60.0, dt=60.0)
        pid.compute(5.0)
        # D = 60.0 * (3.0 - 5.0) / 60.0 = -2.0 -> clamped to 0
        output = pid.compute(3.0)
        assert output == pytest.approx(0.0)


@pytest.mark.unit
class TestPIDAntiWindup:
    """Back-calculation anti-windup behaviour."""

    def test_anti_windup_limits_integral_during_saturation(self) -> None:
        """Integral does not grow unboundedly when output is saturated."""
        pid = PIDController(kp=10.0, ki=0.01, kd=0.0, dt=60.0)
        # With error=20, kp=10 -> P=200, already saturated at 100
        for _ in range(100):
            pid.compute(20.0)
        # Integral should be clamped, not growing without bound
        # Without anti-windup, integral would be 0.01 * 20 * 60 * 100 = 1200
        assert pid.integral < 100.0

    def test_anti_windup_recovery_no_large_overshoot(self) -> None:
        """After saturation, switching to negative error recovers quickly.

        Without anti-windup the integral would be huge, causing overshoot.
        With anti-windup the output should drop to 0 within a few steps.
        """
        pid = PIDController(kp=5.0, ki=0.01, kd=0.0, dt=60.0)
        # Saturate for 100 steps
        for _ in range(100):
            pid.compute(30.0)
        # Now error goes negative (room above setpoint)
        output = pid.compute(-1.0)
        # Output should be close to 0 (not stuck at 100 due to windup)
        assert output < 10.0

    def test_anti_windup_integral_bounded_at_saturation(self) -> None:
        """Integral is bounded when output saturates at max."""
        pid = PIDController(kp=0.0, ki=0.1, kd=0.0, dt=60.0)
        # I per step = 0.1 * 5.0 * 60 = 30
        # But output_max = 100, so integral should not exceed 100
        for _ in range(10):
            pid.compute(5.0)
        assert pid.integral <= 100.0 + 1e-9

    def test_anti_windup_integral_bounded_at_min(self) -> None:
        """Integral is bounded when output saturates at min."""
        pid = PIDController(kp=0.0, ki=0.1, kd=0.0, dt=60.0)
        for _ in range(10):
            pid.compute(-5.0)
        # Integral should not go below 0 (output_min=0)
        assert pid.integral >= -1e-9


@pytest.mark.unit
class TestPIDOutputClamping:
    """Output clamping to [output_min, output_max]."""

    def test_output_never_exceeds_max(self) -> None:
        """Output is always <= output_max regardless of input."""
        pid = PIDController(kp=100.0, ki=0.0, kd=0.0, output_max=100.0)
        assert pid.compute(500.0) == pytest.approx(100.0)

    def test_output_never_below_min(self) -> None:
        """Output is always >= output_min regardless of input."""
        pid = PIDController(kp=100.0, ki=0.0, kd=0.0, output_min=0.0)
        assert pid.compute(-500.0) == pytest.approx(0.0)

    def test_custom_output_range(self) -> None:
        """Custom output_min/output_max are respected."""
        pid = PIDController(kp=1.0, ki=0.0, kd=0.0, output_min=10.0, output_max=90.0)
        assert pid.compute(50.0) == pytest.approx(50.0)  # within range
        assert pid.compute(100.0) == pytest.approx(90.0)  # clamped high
        assert pid.compute(-100.0) == pytest.approx(10.0)  # clamped low


@pytest.mark.unit
class TestPIDReset:
    """PID reset behaviour."""

    def test_reset_clears_integral(self) -> None:
        """Reset clears the integral accumulator."""
        pid = PIDController(kp=0.0, ki=0.01, kd=0.0)
        pid.compute(5.0)
        assert pid.integral != 0.0
        pid.reset()
        assert pid.integral == pytest.approx(0.0)

    def test_reset_clears_last_output(self) -> None:
        """Reset clears the last output value."""
        pid = PIDController(kp=5.0, ki=0.0, kd=0.0)
        pid.compute(5.0)
        assert pid.last_output > 0.0
        pid.reset()
        assert pid.last_output == pytest.approx(0.0)

    def test_reset_clears_derivative_state(self) -> None:
        """After reset, first compute has zero derivative contribution."""
        pid = PIDController(kp=0.0, ki=0.0, kd=60.0, dt=60.0)
        pid.compute(5.0)
        pid.compute(10.0)  # D = 60*(10-5)/60 = 5
        pid.reset()
        # After reset, first call should have D=0 (no previous error)
        output = pid.compute(10.0)
        assert output == pytest.approx(0.0)


@pytest.mark.unit
class TestPIDValidation:
    """Constructor validation."""

    def test_negative_kp_raises(self) -> None:
        """Negative kp raises ValueError."""
        with pytest.raises(ValueError, match="kp"):
            PIDController(kp=-1.0, ki=0.0, kd=0.0)

    def test_negative_ki_raises(self) -> None:
        """Negative ki raises ValueError."""
        with pytest.raises(ValueError, match="ki"):
            PIDController(kp=0.0, ki=-1.0, kd=0.0)

    def test_negative_kd_raises(self) -> None:
        """Negative kd raises ValueError."""
        with pytest.raises(ValueError, match="kd"):
            PIDController(kp=0.0, ki=0.0, kd=-1.0)

    def test_zero_dt_raises(self) -> None:
        """Zero dt raises ValueError."""
        with pytest.raises(ValueError, match="dt"):
            PIDController(kp=1.0, ki=0.0, kd=0.0, dt=0.0)

    def test_inverted_output_range_raises(self) -> None:
        """output_max < output_min raises ValueError."""
        with pytest.raises(ValueError, match="output_max"):
            PIDController(kp=1.0, ki=0.0, kd=0.0, output_min=100.0, output_max=0.0)


@pytest.mark.unit
class TestPIDZeroGains:
    """Edge case: all gains zero."""

    def test_zero_gains_output_zero(self) -> None:
        """All-zero gains always produce zero output."""
        pid = PIDController(kp=0.0, ki=0.0, kd=0.0)
        for e in [1.0, -1.0, 10.0, 0.0]:
            assert pid.compute(e) == pytest.approx(0.0)


@pytest.mark.unit
class TestPIDNegativeError:
    """PID response to negative error (room above setpoint)."""

    def test_negative_error_all_terms(self) -> None:
        """Negative error drives all terms negative, clamped to 0."""
        pid = PIDController(kp=5.0, ki=0.01, kd=0.0, dt=60.0)
        output = pid.compute(-5.0)
        assert output == pytest.approx(0.0)

    def test_transition_positive_to_negative(self) -> None:
        """Output transitions smoothly from positive to negative error."""
        pid = PIDController(kp=5.0, ki=0.0, kd=0.0)
        assert pid.compute(2.0) == pytest.approx(10.0)
        assert pid.compute(-2.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# PumpAheadController unit tests
# ---------------------------------------------------------------------------


def _make_measurements(
    t_room: float = 20.0,
    t_slab: float = 22.0,
    t_outdoor: float = 0.0,
    valve_pos: float = 50.0,
    hp_mode: HeatPumpMode = HeatPumpMode.HEATING,
    is_cwu_active: bool = False,
) -> Measurements:
    """Create a Measurements instance for testing."""
    return Measurements(
        T_room=t_room,
        T_slab=t_slab,
        T_outdoor=t_outdoor,
        valve_pos=valve_pos,
        hp_mode=hp_mode,
        is_cwu_active=is_cwu_active,
    )


@pytest.mark.unit
class TestPumpAheadControllerSingleRoom:
    """Single-room PumpAheadController tests."""

    def test_single_room_step_returns_actions(self) -> None:
        """step() returns an Actions dict with the correct room name."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        ctrl = PumpAheadController(config, ["salon"])
        meas = {"salon": _make_measurements(t_room=20.0)}
        actions = ctrl.step(meas)
        assert "salon" in actions
        assert isinstance(actions["salon"], Actions)

    def test_single_room_positive_error_positive_valve(self) -> None:
        """Room below setpoint produces positive valve output."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        ctrl = PumpAheadController(config, ["salon"])
        meas = {"salon": _make_measurements(t_room=19.0)}
        actions = ctrl.step(meas)
        # error = 21 - 19 = 2, P = 5*2 = 10
        assert actions["salon"].valve_position == pytest.approx(10.0)

    def test_single_room_splits_off(self) -> None:
        """PumpAheadController always sets split to OFF."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        ctrl = PumpAheadController(config, ["salon"])
        meas = {"salon": _make_measurements(t_room=19.0)}
        actions = ctrl.step(meas)
        assert actions["salon"].split_mode == SplitMode.OFF


@pytest.mark.unit
class TestPumpAheadControllerMultiRoom:
    """Multi-room PumpAheadController tests."""

    def test_multi_room_independent_outputs(self) -> None:
        """Each room computes its own independent valve position."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        rooms = ["salon", "bedroom", "kitchen"]
        ctrl = PumpAheadController(config, rooms)

        meas = {
            "salon": _make_measurements(t_room=20.0),  # error=1, valve=5
            "bedroom": _make_measurements(t_room=19.0),  # error=2, valve=10
            "kitchen": _make_measurements(t_room=21.0),  # error=0, valve=0
        }
        actions = ctrl.step(meas)

        # valve_floor_pct=10 applies when room < setpoint+deadband
        # salon: 20.0 < 21.5 -> valve_floor applies -> max(5.0, 10.0) = 10.0
        assert actions["salon"].valve_position == pytest.approx(10.0)
        # bedroom: 19.0 < 21.5 -> valve_floor applies -> max(10.0, 10.0) = 10.0
        assert actions["bedroom"].valve_position == pytest.approx(10.0)
        # kitchen: error=0 -> PID=0, but 21.0 < 21.5 -> floor applies -> 10.0
        assert actions["kitchen"].valve_position == pytest.approx(10.0)

    def test_eight_rooms_parallel(self) -> None:
        """8 rooms running in parallel with independent PID state."""
        config = ControllerConfig(kp=5.0, ki=0.01, setpoint=21.0)
        rooms = [f"room_{i}" for i in range(8)]
        ctrl = PumpAheadController(config, rooms)

        # Each room at a different temperature
        temps = [18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0]
        meas = {f"room_{i}": _make_measurements(t_room=temps[i]) for i in range(8)}
        actions = ctrl.step(meas)

        assert len(actions) == 8
        for name in rooms:
            assert name in actions
            assert isinstance(actions[name], Actions)

        # Verify rooms with higher temperature have lower valve output
        # (after accounting for valve floor)
        # room_0 (18C) should have higher valve than room_7 (25C)
        assert actions["room_0"].valve_position >= actions["room_7"].valve_position

    def test_multi_room_no_interference(self) -> None:
        """Running multi-room does not interfere between rooms.

        Verify that a room at setpoint maintains its own integral
        independently of a room with large error.
        """
        config = ControllerConfig(kp=0.0, ki=0.01, setpoint=21.0)
        ctrl = PumpAheadController(config, ["stable", "cold"])

        for _ in range(10):
            meas = {
                "stable": _make_measurements(t_room=21.0),
                "cold": _make_measurements(t_room=15.0),
            }
            ctrl.step(meas)

        diag = ctrl.get_diagnostics()
        # stable room: error=0 every step -> integral=0
        assert diag["stable"]["integral"] == pytest.approx(0.0)
        # cold room: error=6 every step -> integral grows
        assert diag["cold"]["integral"] > 0.0


@pytest.mark.unit
class TestPumpAheadValveFloor:
    """Valve floor minimum enforcement tests."""

    def test_valve_floor_applied_below_setpoint(self) -> None:
        """Valve floor is applied when room is below setpoint + deadband."""
        config = ControllerConfig(
            kp=0.0,
            ki=0.0,
            setpoint=21.0,
            deadband=0.5,
            valve_floor_pct=15.0,
        )
        ctrl = PumpAheadController(config, ["room"])
        # PID output is 0 (all gains zero), but room is below 21.5
        meas = {"room": _make_measurements(t_room=20.0)}
        actions = ctrl.step(meas)
        assert actions["room"].valve_position == pytest.approx(15.0)

    def test_valve_floor_not_applied_above_setpoint_plus_deadband(self) -> None:
        """Valve floor is NOT applied when room is above setpoint + deadband."""
        config = ControllerConfig(
            kp=0.0,
            ki=0.0,
            setpoint=21.0,
            deadband=0.5,
            valve_floor_pct=15.0,
        )
        ctrl = PumpAheadController(config, ["room"])
        # Room at 22.0 > 21.5 (setpoint + deadband)
        meas = {"room": _make_measurements(t_room=22.0)}
        actions = ctrl.step(meas)
        assert actions["room"].valve_position == pytest.approx(0.0)

    def test_valve_floor_not_applied_hp_off(self) -> None:
        """Valve floor is NOT applied when HP mode is OFF."""
        config = ControllerConfig(
            kp=0.0,
            ki=0.0,
            setpoint=21.0,
            valve_floor_pct=15.0,
        )
        ctrl = PumpAheadController(config, ["room"])
        meas = {"room": _make_measurements(t_room=20.0, hp_mode=HeatPumpMode.OFF)}
        actions = ctrl.step(meas)
        assert actions["room"].valve_position == pytest.approx(0.0)

    def test_valve_floor_not_applied_hp_cooling(self) -> None:
        """Valve floor is NOT applied when HP mode is COOLING."""
        config = ControllerConfig(
            kp=0.0,
            ki=0.0,
            setpoint=21.0,
            valve_floor_pct=15.0,
        )
        ctrl = PumpAheadController(config, ["room"])
        meas = {"room": _make_measurements(t_room=20.0, hp_mode=HeatPumpMode.COOLING)}
        actions = ctrl.step(meas)
        assert actions["room"].valve_position == pytest.approx(0.0)

    def test_valve_floor_does_not_reduce_pid_output(self) -> None:
        """When PID output > valve_floor, the PID output is used."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.0,
            setpoint=21.0,
            valve_floor_pct=10.0,
        )
        ctrl = PumpAheadController(config, ["room"])
        # error=5 -> PID=25, which is > valve_floor=10
        meas = {"room": _make_measurements(t_room=16.0)}
        actions = ctrl.step(meas)
        assert actions["room"].valve_position == pytest.approx(25.0)


@pytest.mark.unit
class TestPumpAheadRoomOverrides:
    """Room-specific configuration overrides."""

    def test_room_override_changes_setpoint(self) -> None:
        """Room override uses a different setpoint."""
        base = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        bedroom_config = ControllerConfig(kp=5.0, ki=0.0, setpoint=19.0)
        ctrl = PumpAheadController(
            base,
            ["salon", "bedroom"],
            room_overrides={"bedroom": bedroom_config},
        )
        meas = {
            "salon": _make_measurements(t_room=20.0),
            "bedroom": _make_measurements(t_room=20.0),
        }
        actions = ctrl.step(meas)

        # salon: error = 21-20 = 1, valve = max(5.0, valve_floor=10.0) = 10.0
        assert actions["salon"].valve_position == pytest.approx(10.0)
        # bedroom: error = 19-20 = -1, valve = 0
        # bedroom: 20.0 < 19.0 + 0.5 = 19.5? No, 20.0 > 19.5 -> no floor
        assert actions["bedroom"].valve_position == pytest.approx(0.0)

    def test_room_override_different_gains(self) -> None:
        """Room override uses different PID gains."""
        base = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        kitchen_config = ControllerConfig(kp=10.0, ki=0.0, setpoint=21.0)
        ctrl = PumpAheadController(
            base,
            ["salon", "kitchen"],
            room_overrides={"kitchen": kitchen_config},
        )
        meas = {
            "salon": _make_measurements(t_room=19.0),
            "kitchen": _make_measurements(t_room=19.0),
        }
        actions = ctrl.step(meas)

        # salon: error=2, valve=max(10.0, 10.0)=10.0
        assert actions["salon"].valve_position == pytest.approx(10.0)
        # kitchen: error=2, kp=10 -> valve=max(20.0, 10.0)=20.0
        assert actions["kitchen"].valve_position == pytest.approx(20.0)


@pytest.mark.unit
class TestPumpAheadReset:
    """PumpAheadController reset behaviour."""

    def test_reset_clears_all_pid_state(self) -> None:
        """Reset clears integral and last_output for all rooms."""
        config = ControllerConfig(kp=5.0, ki=0.01, setpoint=21.0)
        ctrl = PumpAheadController(config, ["room_a", "room_b"])

        meas = {
            "room_a": _make_measurements(t_room=18.0),
            "room_b": _make_measurements(t_room=19.0),
        }
        for _ in range(10):
            ctrl.step(meas)

        diag_before = ctrl.get_diagnostics()
        assert diag_before["room_a"]["integral"] != 0.0

        ctrl.reset()

        diag_after = ctrl.get_diagnostics()
        for name in ["room_a", "room_b"]:
            assert diag_after[name]["integral"] == pytest.approx(0.0)
            assert diag_after[name]["last_output"] == pytest.approx(0.0)


@pytest.mark.unit
class TestPumpAheadControllerValidation:
    """Constructor validation tests."""

    def test_empty_room_names_raises(self) -> None:
        """Empty room_names raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            PumpAheadController(ControllerConfig(), [])

    def test_duplicate_room_names_raises(self) -> None:
        """Duplicate room names raises ValueError."""
        with pytest.raises(ValueError, match="unique"):
            PumpAheadController(ControllerConfig(), ["a", "a"])

    def test_unknown_room_override_raises(self) -> None:
        """Room override for unknown room raises ValueError."""
        with pytest.raises(ValueError, match="unknown room"):
            PumpAheadController(
                ControllerConfig(),
                ["a"],
                room_overrides={"b": ControllerConfig()},
            )

    def test_mismatched_measurements_raises(self) -> None:
        """step() with wrong measurement keys raises ValueError."""
        ctrl = PumpAheadController(ControllerConfig(), ["a", "b"])
        meas = {"a": _make_measurements(), "c": _make_measurements()}
        with pytest.raises(ValueError, match="Measurement keys"):
            ctrl.step(meas)


@pytest.mark.unit
class TestPumpAheadDiagnostics:
    """get_diagnostics() tests."""

    def test_diagnostics_returns_all_rooms(self) -> None:
        """Diagnostics contain entries for all rooms."""
        config = ControllerConfig(kp=5.0, ki=0.01, setpoint=21.0)
        ctrl = PumpAheadController(config, ["a", "b"])
        diag = ctrl.get_diagnostics()
        assert set(diag.keys()) == {"a", "b"}

    def test_diagnostics_fields_present(self) -> None:
        """Each room diagnostic has the expected fields."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.01,
            setpoint=21.0,
            valve_floor_pct=10.0,
        )
        ctrl = PumpAheadController(config, ["room"])
        diag = ctrl.get_diagnostics()["room"]
        assert "integral" in diag
        assert "last_output" in diag
        assert "setpoint" in diag
        assert "valve_floor_pct" in diag
        assert diag["setpoint"] == pytest.approx(21.0)
        assert diag["valve_floor_pct"] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# PumpAheadController split coordination tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPumpAheadControllerSplitCoordination:
    """Tests for split coordination integration in PumpAheadController."""

    def test_split_off_for_rooms_without_split(self) -> None:
        """Rooms with room_has_split=False always get SplitMode.OFF."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        ctrl = PumpAheadController(config, ["room_a"], room_has_split={"room_a": False})
        meas = {"room_a": _make_measurements(t_room=19.0)}
        actions = ctrl.step(meas)
        assert actions["room_a"].split_mode == SplitMode.OFF

    def test_split_activates_when_error_exceeds_deadband(self) -> None:
        """Split activates HEATING when error > deadband in heating mode."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0, split_deadband=0.5)
        ctrl = PumpAheadController(config, ["room_a"], room_has_split={"room_a": True})
        # error = 21.0 - 19.0 = 2.0 > 0.5 (deadband)
        meas = {"room_a": _make_measurements(t_room=19.0)}
        actions = ctrl.step(meas)
        assert actions["room_a"].split_mode == SplitMode.HEATING

    def test_split_off_within_deadband(self) -> None:
        """Split stays OFF when error is within deadband."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0, split_deadband=0.5)
        ctrl = PumpAheadController(config, ["room_a"], room_has_split={"room_a": True})
        # error = 21.0 - 20.7 = 0.3 < 0.5 (deadband)
        meas = {"room_a": _make_measurements(t_room=20.7)}
        actions = ctrl.step(meas)
        assert actions["room_a"].split_mode == SplitMode.OFF

    def test_backward_compat_no_room_has_split_param(self) -> None:
        """Without room_has_split, all rooms get SplitMode.OFF."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        ctrl = PumpAheadController(config, ["room_a", "room_b"])
        meas = {
            "room_a": _make_measurements(t_room=19.0),
            "room_b": _make_measurements(t_room=18.0),
        }
        actions = ctrl.step(meas)
        assert actions["room_a"].split_mode == SplitMode.OFF
        assert actions["room_b"].split_mode == SplitMode.OFF

    def test_mixed_rooms_split_and_no_split(self) -> None:
        """Mixed rooms: one with split, one without."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0, split_deadband=0.5)
        ctrl = PumpAheadController(
            config,
            ["with_split", "without_split"],
            room_has_split={"with_split": True, "without_split": False},
        )
        meas = {
            "with_split": _make_measurements(t_room=19.0),
            "without_split": _make_measurements(t_room=19.0),
        }
        actions = ctrl.step(meas)
        assert actions["with_split"].split_mode == SplitMode.HEATING
        assert actions["without_split"].split_mode == SplitMode.OFF

    def test_anti_takeover_boosts_valve(self) -> None:
        """Anti-takeover boosts valve above normal valve_floor."""
        config = ControllerConfig(
            kp=0.0,
            ki=0.0,
            setpoint=21.0,
            valve_floor_pct=10.0,
            split_deadband=0.5,
            anti_takeover_threshold_minutes=30,
            anti_takeover_valve_boost_pct=50.0,
        )
        ctrl = PumpAheadController(config, ["room_a"], room_has_split={"room_a": True})

        # Run 31 steps with large error to trigger anti-takeover
        for _ in range(31):
            meas = {"room_a": _make_measurements(t_room=19.0)}
            actions = ctrl.step(meas)

        # After anti-takeover, valve should be boosted to
        # valve_floor_pct + anti_takeover_valve_boost_pct = 60.0
        assert actions["room_a"].valve_position == pytest.approx(60.0)
        # Anti-takeover forces split OFF to make UFH primary
        assert actions["room_a"].split_mode == SplitMode.OFF

    def test_diagnostics_include_split_info(self) -> None:
        """Diagnostics include split fields for rooms with coordinators."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        ctrl = PumpAheadController(
            config,
            ["with_split", "without_split"],
            room_has_split={"with_split": True, "without_split": False},
        )
        diag = ctrl.get_diagnostics()

        # Room with split has extra diagnostic fields
        assert "split_runtime_minutes" in diag["with_split"]
        assert "anti_takeover_active" in diag["with_split"]

        # Room without split does not
        assert "split_runtime_minutes" not in diag["without_split"]
        assert "anti_takeover_active" not in diag["without_split"]

    def test_reset_clears_split_coordinators(self) -> None:
        """Reset clears split coordinator state."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0, split_deadband=0.5)
        ctrl = PumpAheadController(config, ["room_a"], room_has_split={"room_a": True})

        # Run a few steps
        for _ in range(5):
            meas = {"room_a": _make_measurements(t_room=19.0)}
            ctrl.step(meas)

        diag_before = ctrl.get_diagnostics()
        assert diag_before["room_a"]["split_runtime_minutes"] > 0

        ctrl.reset()

        diag_after = ctrl.get_diagnostics()
        assert diag_after["room_a"]["split_runtime_minutes"] == 0.0


# ---------------------------------------------------------------------------
# PumpAheadController CWU coordination tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPumpAheadControllerCWU:
    """Tests for CWU coordination integration in PumpAheadController."""

    def test_split_blocked_during_cwu_when_warm(self) -> None:
        """Split is blocked during CWU when T_room > setpoint - margin."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.0,
            setpoint=21.0,
            split_deadband=0.5,
            cwu_anti_panic_margin=1.0,
        )
        ctrl = PumpAheadController(
            config,
            ["room_a"],
            room_has_split={"room_a": True},
            cwu_schedule=CWU_HEAVY,
        )
        # T_room=20.5, setpoint=21.0, margin=1.0 => threshold=20.0
        # 20.5 > 20.0 => split blocked
        # error=0.5 <= deadband=0.5 => split would be OFF anyway, but
        # let's use a larger error to ensure the block is active
        meas = {"room_a": _make_measurements(t_room=19.5, is_cwu_active=True)}
        actions = ctrl.step(meas)
        # T_room=19.5 > 20.0? No. So split should NOT be blocked.
        # Let's test with T_room=20.5 where split would activate
        meas = {"room_a": _make_measurements(t_room=20.2, is_cwu_active=True)}
        actions = ctrl.step(meas)
        # error = 21.0 - 20.2 = 0.8 > 0.5 deadband => split would
        # normally activate, but CWU anti-panic blocks it
        assert actions["room_a"].split_mode == SplitMode.OFF

    def test_split_unblocked_during_cwu_safety_fallback(self) -> None:
        """Split is unblocked during CWU when T_room drops below safety threshold."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.0,
            setpoint=21.0,
            split_deadband=0.5,
            cwu_anti_panic_margin=1.0,
        )
        ctrl = PumpAheadController(
            config,
            ["room_a"],
            room_has_split={"room_a": True},
            cwu_schedule=CWU_HEAVY,
        )
        # T_room=19.5, threshold=20.0 => 19.5 <= 20.0 => unblocked
        # error = 21.0 - 19.5 = 1.5 > 0.5 deadband => split activates
        meas = {"room_a": _make_measurements(t_room=19.5, is_cwu_active=True)}
        actions = ctrl.step(meas)
        assert actions["room_a"].split_mode == SplitMode.HEATING

    def test_split_normal_when_cwu_inactive(self) -> None:
        """Split operates normally when CWU is not active."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.0,
            setpoint=21.0,
            split_deadband=0.5,
        )
        ctrl = PumpAheadController(
            config,
            ["room_a"],
            room_has_split={"room_a": True},
            cwu_schedule=CWU_HEAVY,
        )
        # CWU not active, error > deadband => split activates normally
        meas = {"room_a": _make_measurements(t_room=20.0, is_cwu_active=False)}
        actions = ctrl.step(meas)
        assert actions["room_a"].split_mode == SplitMode.HEATING

    def test_pre_charge_boosts_valve(self) -> None:
        """Pre-charge boosts valve floor before CWU cycle."""
        config = ControllerConfig(
            kp=0.0,
            ki=0.0,
            setpoint=21.0,
            valve_floor_pct=10.0,
            cwu_pre_charge_lookahead_minutes=30,
            cwu_pre_charge_valve_boost_pct=15.0,
        )
        # CWU starts at t=60 (single-shot, 45 min)
        schedule = (CWUCycle(start_minute=60, duration_minutes=45, interval_minutes=0),)
        ctrl = PumpAheadController(
            config,
            ["room_a"],
            cwu_schedule=schedule,
        )
        # Step to t=35 (25 min before CWU) => within 30 min lookahead
        for _ in range(35):
            meas = {"room_a": _make_measurements(t_room=20.0, is_cwu_active=False)}
            ctrl.step(meas)

        # At step 35, pre-charge should boost valve
        meas = {"room_a": _make_measurements(t_room=20.0, is_cwu_active=False)}
        actions = ctrl.step(meas)
        # Valve should be boosted: valve_floor + pre_charge = 10 + 15 = 25
        assert actions["room_a"].valve_position == pytest.approx(25.0)

    def test_backward_compatibility_no_cwu(self) -> None:
        """Without cwu_schedule, controller behaves exactly as before."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        ctrl = PumpAheadController(config, ["room_a"])
        meas = {"room_a": _make_measurements(t_room=20.0)}
        actions = ctrl.step(meas)
        assert isinstance(actions["room_a"], Actions)
        # Valve should match PID output + valve floor
        assert actions["room_a"].valve_position == pytest.approx(10.0)

    def test_cwu_diagnostics_present(self) -> None:
        """Diagnostics include CWU fields when coordinator exists."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        ctrl = PumpAheadController(
            config,
            ["room_a"],
            cwu_schedule=CWU_HEAVY,
        )
        # Run one step to populate diagnostics
        meas = {"room_a": _make_measurements(t_room=20.0, is_cwu_active=False)}
        ctrl.step(meas)

        diag = ctrl.get_diagnostics()
        assert "cwu_pre_charge_active" in diag["room_a"]
        assert "cwu_split_blocked" in diag["room_a"]

    def test_cwu_diagnostics_absent_without_cwu(self) -> None:
        """Diagnostics do not include CWU fields without coordinator."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        ctrl = PumpAheadController(config, ["room_a"])
        meas = {"room_a": _make_measurements(t_room=20.0)}
        ctrl.step(meas)
        diag = ctrl.get_diagnostics()
        assert "cwu_pre_charge_active" not in diag["room_a"]
        assert "cwu_split_blocked" not in diag["room_a"]

    def test_reset_clears_step_count(self) -> None:
        """Reset clears step count for pre-charge timing."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        ctrl = PumpAheadController(
            config,
            ["room_a"],
            cwu_schedule=CWU_HEAVY,
        )
        # Run 10 steps
        for _ in range(10):
            meas = {"room_a": _make_measurements(t_room=20.0)}
            ctrl.step(meas)

        ctrl.reset()
        # After reset, step count should be 0 (checked via pre-charge
        # which uses step count as time proxy)
        assert ctrl._step_count == 0

    def test_split_runtime_window_not_contaminated_during_cwu(self) -> None:
        """Split runtime window is not contaminated when split is blocked."""
        config = ControllerConfig(
            kp=5.0,
            ki=0.0,
            setpoint=21.0,
            split_deadband=0.5,
            cwu_anti_panic_margin=1.0,
        )
        ctrl = PumpAheadController(
            config,
            ["room_a"],
            room_has_split={"room_a": True},
            cwu_schedule=CWU_HEAVY,
        )
        # Run 30 steps with CWU active, T_room warm enough to block split
        for _ in range(30):
            meas = {"room_a": _make_measurements(t_room=20.5, is_cwu_active=True)}
            ctrl.step(meas)

        # Split runtime should be 0 because split was always blocked
        diag = ctrl.get_diagnostics()
        assert diag["room_a"]["split_runtime_minutes"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# PumpAheadController heating-only auxiliary (heater) tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPumpAheadControllerHeaterAuxiliary:
    """Tests for the ``room_auxiliary_type='heater'`` short-circuit."""

    def test_heater_passive_in_cooling_mode(self) -> None:
        """Heater room is SplitMode.OFF in cooling, split room cools normally."""
        config = ControllerConfig(
            kp=5.0, ki=0.0, setpoint=24.0, split_deadband=0.5
        )
        ctrl = PumpAheadController(
            config,
            ["heater_room", "split_room"],
            room_has_split={"heater_room": True, "split_room": True},
            room_auxiliary_type={
                "heater_room": "heater",
                "split_room": "split",
            },
        )
        # Both rooms are hot (T_room > setpoint) in cooling mode.
        # Cooling error = T_room - setpoint = 26 - 24 = 2 > 0.5 deadband.
        meas = {
            "heater_room": _make_measurements(
                t_room=26.0, hp_mode=HeatPumpMode.COOLING
            ),
            "split_room": _make_measurements(
                t_room=26.0, hp_mode=HeatPumpMode.COOLING
            ),
        }
        actions = ctrl.step(meas)
        # Heater room is passive — no split action.
        assert actions["heater_room"].split_mode == SplitMode.OFF
        assert actions["heater_room"].split_setpoint == 0.0
        # Split room activates cooling normally.
        assert actions["split_room"].split_mode == SplitMode.COOLING

    def test_heater_activates_in_heating_mode(self) -> None:
        """Heater room activates normally in heating mode (no short-circuit)."""
        config = ControllerConfig(
            kp=5.0, ki=0.0, setpoint=24.0, split_deadband=0.5
        )
        ctrl = PumpAheadController(
            config,
            ["heater_room"],
            room_has_split={"heater_room": True},
            room_auxiliary_type={"heater_room": "heater"},
        )
        # Heating mode, error = 24 - 22 = 2 > 0.5 deadband => heater activates.
        meas = {
            "heater_room": _make_measurements(
                t_room=22.0, hp_mode=HeatPumpMode.HEATING
            ),
        }
        actions = ctrl.step(meas)
        assert actions["heater_room"].split_mode == SplitMode.HEATING

    def test_heater_runtime_window_not_contaminated_in_cooling(self) -> None:
        """Cooling-mode short-circuit does not accumulate split runtime."""
        config = ControllerConfig(
            kp=5.0, ki=0.0, setpoint=24.0, split_deadband=0.5
        )
        ctrl = PumpAheadController(
            config,
            ["heater_room"],
            room_has_split={"heater_room": True},
            room_auxiliary_type={"heater_room": "heater"},
        )
        for _ in range(30):
            meas = {
                "heater_room": _make_measurements(
                    t_room=26.0, hp_mode=HeatPumpMode.COOLING
                ),
            }
            ctrl.step(meas)
        diag = ctrl.get_diagnostics()
        assert diag["heater_room"]["split_runtime_minutes"] == pytest.approx(0.0)

    def test_unknown_room_in_auxiliary_type_raises(self) -> None:
        """room_auxiliary_type with unknown room name raises ValueError."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        with pytest.raises(ValueError, match="unknown room names"):
            PumpAheadController(
                config,
                ["room_a"],
                room_auxiliary_type={"ghost": "heater"},
            )

    def test_invalid_auxiliary_type_value_raises(self) -> None:
        """Unsupported value in room_auxiliary_type raises ValueError."""
        config = ControllerConfig(kp=5.0, ki=0.0, setpoint=21.0)
        with pytest.raises(ValueError, match="must be 'split' or 'heater'"):
            PumpAheadController(
                config,
                ["room_a"],
                room_auxiliary_type={"room_a": "turbo"},
            )
