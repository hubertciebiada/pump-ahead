"""Unit tests for SplitCoordinator and SplitDecision.

Tests cover deadband logic, mode enforcement (Axiom #3), anti-takeover
(Axiom #2), runtime tracking, setpoint computation, and reset behaviour.
"""

from __future__ import annotations

import pytest

from pumpahead.config import ControllerConfig
from pumpahead.simulator import HeatPumpMode, SplitMode
from pumpahead.split_coordinator import (
    SafetyViolationError,
    SplitCoordinator,
    SplitDecision,
)

# ---------------------------------------------------------------------------
# SplitDecision tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSplitDecision:
    """SplitDecision frozen dataclass tests."""

    def test_creation_with_defaults(self) -> None:
        """SplitDecision can be created with only split_mode."""
        decision = SplitDecision(split_mode=SplitMode.OFF)
        assert decision.split_mode == SplitMode.OFF
        assert decision.split_setpoint == 0.0
        assert decision.valve_floor_boost == 0.0
        assert decision.anti_takeover_active is False

    def test_creation_with_all_fields(self) -> None:
        """SplitDecision can be created with all fields specified."""
        decision = SplitDecision(
            split_mode=SplitMode.HEATING,
            split_setpoint=23.0,
            valve_floor_boost=50.0,
            anti_takeover_active=True,
        )
        assert decision.split_mode == SplitMode.HEATING
        assert decision.split_setpoint == 23.0
        assert decision.valve_floor_boost == 50.0
        assert decision.anti_takeover_active is True

    def test_frozen(self) -> None:
        """SplitDecision is immutable."""
        decision = SplitDecision(split_mode=SplitMode.OFF)
        with pytest.raises(AttributeError):
            decision.split_mode = SplitMode.HEATING  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SplitCoordinator init tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSplitCoordinatorInit:
    """SplitCoordinator constructor tests."""

    def test_valid_creation(self) -> None:
        """SplitCoordinator can be created with default config."""
        config = ControllerConfig()
        coordinator = SplitCoordinator(config)
        assert coordinator.window_size == 60
        assert coordinator.split_runtime_minutes == 0

    def test_custom_window_size(self) -> None:
        """SplitCoordinator accepts custom window_size."""
        config = ControllerConfig()
        coordinator = SplitCoordinator(config, window_size=30)
        assert coordinator.window_size == 30

    def test_invalid_window_size_raises(self) -> None:
        """Window size < 1 raises ValueError."""
        config = ControllerConfig()
        with pytest.raises(ValueError, match="window_size"):
            SplitCoordinator(config, window_size=0)


# ---------------------------------------------------------------------------
# SplitCoordinator.decide() — deadband and activation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSplitCoordinatorDecide:
    """Deadband, mode matching, and activation tests."""

    def test_off_when_error_within_deadband(self) -> None:
        """Split stays OFF when error is within deadband."""
        config = ControllerConfig(split_deadband=0.5)
        coordinator = SplitCoordinator(config)
        decision = coordinator.decide(
            error=0.3, setpoint=21.0, hp_mode=HeatPumpMode.HEATING
        )
        assert decision.split_mode == SplitMode.OFF

    def test_off_when_error_exactly_equals_deadband(self) -> None:
        """Split stays OFF when error exactly equals deadband (strict >)."""
        config = ControllerConfig(split_deadband=0.5)
        coordinator = SplitCoordinator(config)
        decision = coordinator.decide(
            error=0.5, setpoint=21.0, hp_mode=HeatPumpMode.HEATING
        )
        assert decision.split_mode == SplitMode.OFF

    def test_heating_when_error_exceeds_deadband(self) -> None:
        """Split activates HEATING when positive error exceeds deadband."""
        config = ControllerConfig(split_deadband=0.5)
        coordinator = SplitCoordinator(config)
        decision = coordinator.decide(
            error=0.8, setpoint=21.0, hp_mode=HeatPumpMode.HEATING
        )
        assert decision.split_mode == SplitMode.HEATING

    def test_cooling_when_negative_error_exceeds_deadband(self) -> None:
        """Split activates COOLING when negative error exceeds deadband."""
        config = ControllerConfig(split_deadband=0.5)
        coordinator = SplitCoordinator(config)
        decision = coordinator.decide(
            error=-0.8, setpoint=25.0, hp_mode=HeatPumpMode.COOLING
        )
        assert decision.split_mode == SplitMode.COOLING

    def test_no_opposing_action_heating_mode(self) -> None:
        """Split does NOT cool in heating mode even with negative error."""
        config = ControllerConfig(split_deadband=0.5)
        coordinator = SplitCoordinator(config)
        # Negative error in heating mode = overshoot, split must stay OFF
        decision = coordinator.decide(
            error=-1.0, setpoint=21.0, hp_mode=HeatPumpMode.HEATING
        )
        assert decision.split_mode == SplitMode.OFF

    def test_no_opposing_action_cooling_mode(self) -> None:
        """Split does NOT heat in cooling mode even with positive error."""
        config = ControllerConfig(split_deadband=0.5)
        coordinator = SplitCoordinator(config)
        # Positive error in cooling mode = undershoot, split must stay OFF
        decision = coordinator.decide(
            error=1.0, setpoint=25.0, hp_mode=HeatPumpMode.COOLING
        )
        assert decision.split_mode == SplitMode.OFF

    def test_hp_off_always_returns_split_off(self) -> None:
        """HP mode OFF always produces split OFF regardless of error."""
        config = ControllerConfig(split_deadband=0.5)
        coordinator = SplitCoordinator(config)
        for error in [2.0, -2.0, 0.0, 10.0]:
            decision = coordinator.decide(
                error=error, setpoint=21.0, hp_mode=HeatPumpMode.OFF
            )
            assert decision.split_mode == SplitMode.OFF

    def test_split_setpoint_heating(self) -> None:
        """Split setpoint in heating = setpoint + offset."""
        config = ControllerConfig(split_deadband=0.5, split_setpoint_offset=2.0)
        coordinator = SplitCoordinator(config)
        decision = coordinator.decide(
            error=1.0, setpoint=21.0, hp_mode=HeatPumpMode.HEATING
        )
        assert decision.split_setpoint == pytest.approx(23.0)

    def test_split_setpoint_cooling(self) -> None:
        """Split setpoint in cooling = setpoint - offset."""
        config = ControllerConfig(split_deadband=0.5, split_setpoint_offset=2.0)
        coordinator = SplitCoordinator(config)
        decision = coordinator.decide(
            error=-1.0, setpoint=25.0, hp_mode=HeatPumpMode.COOLING
        )
        assert decision.split_setpoint == pytest.approx(23.0)

    def test_split_setpoint_zero_when_off(self) -> None:
        """Split setpoint is 0.0 when split is OFF."""
        config = ControllerConfig(split_deadband=0.5)
        coordinator = SplitCoordinator(config)
        decision = coordinator.decide(
            error=0.1, setpoint=21.0, hp_mode=HeatPumpMode.HEATING
        )
        assert decision.split_mode == SplitMode.OFF
        assert decision.split_setpoint == 0.0


# ---------------------------------------------------------------------------
# Anti-takeover tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAntiTakeover:
    """Anti-takeover detection and valve boost tests."""

    def test_anti_takeover_triggers_after_threshold(self) -> None:
        """Anti-takeover triggers when runtime exceeds threshold.

        When anti-takeover activates, the split is forced OFF and
        the valve floor boost is applied.
        """
        config = ControllerConfig(
            split_deadband=0.5,
            anti_takeover_threshold_minutes=30,
            anti_takeover_valve_boost_pct=50.0,
        )
        coordinator = SplitCoordinator(config, window_size=60)

        # Activate split for 30 minutes to hit the threshold
        for _ in range(30):
            decision = coordinator.decide(
                error=2.0, setpoint=21.0, hp_mode=HeatPumpMode.HEATING
            )

        # The 30th decision still has split ON (threshold checked before)
        assert decision.split_mode == SplitMode.HEATING

        # The 31st call: anti-takeover is now active (runtime=30 >= 30),
        # so split is forced OFF with valve boost
        decision = coordinator.decide(
            error=2.0, setpoint=21.0, hp_mode=HeatPumpMode.HEATING
        )
        assert decision.anti_takeover_active is True
        assert decision.split_mode == SplitMode.OFF
        assert decision.valve_floor_boost == pytest.approx(50.0)

    def test_anti_takeover_not_active_below_threshold(self) -> None:
        """Anti-takeover does not trigger below the threshold."""
        config = ControllerConfig(
            split_deadband=0.5,
            anti_takeover_threshold_minutes=30,
        )
        coordinator = SplitCoordinator(config, window_size=60)

        # Activate split for 29 minutes
        for _ in range(29):
            coordinator.decide(error=2.0, setpoint=21.0, hp_mode=HeatPumpMode.HEATING)

        assert coordinator.anti_takeover_active is False

    def test_anti_takeover_clears_after_window_expires(self) -> None:
        """Anti-takeover deactivates when old ON entries leave the window.

        After anti-takeover triggers, continued calls with large error
        will record False (split forced OFF), eventually draining the
        ON entries from the sliding window.
        """
        config = ControllerConfig(
            split_deadband=0.5,
            anti_takeover_threshold_minutes=30,
        )
        coordinator = SplitCoordinator(config, window_size=60)

        # Activate split for 30 minutes to hit threshold
        for _ in range(30):
            coordinator.decide(error=2.0, setpoint=21.0, hp_mode=HeatPumpMode.HEATING)
        assert coordinator.anti_takeover_active is True

        # Anti-takeover is active, so all subsequent calls record False.
        # After 31 calls with anti-takeover forcing OFF:
        # Window has 30 ON + 31 OFF = 61 entries -> maxlen=60 means
        # 1 ON entry fell off, leaving 29 ON + 31 OFF. Runtime = 29 < 30.
        for _ in range(31):
            coordinator.decide(error=2.0, setpoint=21.0, hp_mode=HeatPumpMode.HEATING)

        assert coordinator.anti_takeover_active is False

    def test_runtime_tracking_accuracy(self) -> None:
        """Split runtime minutes counts correctly for mixed sequences."""
        config = ControllerConfig(split_deadband=0.5)
        coordinator = SplitCoordinator(config, window_size=60)

        # 10 ON entries
        for _ in range(10):
            coordinator.decide(error=2.0, setpoint=21.0, hp_mode=HeatPumpMode.HEATING)
        assert coordinator.split_runtime_minutes == 10

        # 5 OFF entries
        for _ in range(5):
            coordinator.decide(error=0.1, setpoint=21.0, hp_mode=HeatPumpMode.HEATING)
        assert coordinator.split_runtime_minutes == 10  # still 10 ON in window

        # 10 more ON entries
        for _ in range(10):
            coordinator.decide(error=2.0, setpoint=21.0, hp_mode=HeatPumpMode.HEATING)
        assert coordinator.split_runtime_minutes == 20  # 20 ON total

    def test_anti_takeover_boost_on_off_decision(self) -> None:
        """Anti-takeover valve boost is included even in OFF decisions."""
        config = ControllerConfig(
            split_deadband=0.5,
            anti_takeover_threshold_minutes=30,
            anti_takeover_valve_boost_pct=50.0,
        )
        coordinator = SplitCoordinator(config, window_size=60)

        # Fill 30 ON entries to trigger anti-takeover
        for _ in range(30):
            coordinator.decide(error=2.0, setpoint=21.0, hp_mode=HeatPumpMode.HEATING)

        # Now make a decision where error is within deadband (OFF)
        decision = coordinator.decide(
            error=0.1, setpoint=21.0, hp_mode=HeatPumpMode.HEATING
        )
        assert decision.split_mode == SplitMode.OFF
        assert decision.anti_takeover_active is True
        assert decision.valve_floor_boost == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Reset tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSplitCoordinatorReset:
    """SplitCoordinator.reset() tests."""

    def test_reset_clears_deque(self) -> None:
        """Reset clears the runtime window."""
        config = ControllerConfig(split_deadband=0.5)
        coordinator = SplitCoordinator(config, window_size=60)

        for _ in range(20):
            coordinator.decide(error=2.0, setpoint=21.0, hp_mode=HeatPumpMode.HEATING)
        assert coordinator.split_runtime_minutes == 20

        coordinator.reset()
        assert coordinator.split_runtime_minutes == 0
        assert coordinator.anti_takeover_active is False


# ---------------------------------------------------------------------------
# Axiom #3 safety violation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSafetyViolation:
    """Axiom #3 safety enforcement via SafetyViolationError.

    These tests exercise the private ``_check_axiom3`` helper directly
    because the public ``decide()`` control flow currently makes the
    violation path unreachable. The whole point of the explicit raise
    is to fail loud if a future refactor introduces a regression, so
    we test the safety helper in isolation to guarantee it raises.
    """

    def test_safety_violation_error_is_runtime_error(self) -> None:
        """SafetyViolationError must inherit from RuntimeError.

        Acceptance criteria require the safety check to raise a
        RuntimeError (or subclass) so generic ``except RuntimeError``
        catches still trap it.
        """
        assert issubclass(SafetyViolationError, RuntimeError)

    def test_safety_violation_raised_when_split_cools_in_heating_mode(
        self,
    ) -> None:
        """Split COOLING while HP HEATING raises SafetyViolationError."""
        coordinator = SplitCoordinator(ControllerConfig())
        with pytest.raises(SafetyViolationError, match=r"bedroom.*COOL.*HEATING"):
            coordinator._check_axiom3(
                HeatPumpMode.HEATING, SplitMode.COOLING, "bedroom"
            )

    def test_safety_violation_raised_when_split_heats_in_cooling_mode(
        self,
    ) -> None:
        """Split HEATING while HP COOLING raises SafetyViolationError."""
        coordinator = SplitCoordinator(ControllerConfig())
        with pytest.raises(SafetyViolationError, match=r"bedroom.*HEAT.*COOLING"):
            coordinator._check_axiom3(
                HeatPumpMode.COOLING, SplitMode.HEATING, "bedroom"
            )

    def test_safety_violation_message_includes_room_name(self) -> None:
        """Diagnostic message includes the room name for actionability."""
        coordinator = SplitCoordinator(ControllerConfig())
        with pytest.raises(SafetyViolationError) as exc_info:
            coordinator._check_axiom3(
                HeatPumpMode.HEATING, SplitMode.COOLING, "living_room"
            )
        message = str(exc_info.value)
        assert "living_room" in message
        assert "HEATING" in message
        assert "COOLING" in message

    def test_safety_violation_message_uses_unknown_when_room_name_none(
        self,
    ) -> None:
        """When room_name is None, the diagnostic message uses '<unknown>'."""
        coordinator = SplitCoordinator(ControllerConfig())
        with pytest.raises(SafetyViolationError) as exc_info:
            coordinator._check_axiom3(HeatPumpMode.COOLING, SplitMode.HEATING, None)
        assert "<unknown>" in str(exc_info.value)

    @pytest.mark.parametrize(
        ("hp_mode", "split_mode"),
        [
            (HeatPumpMode.HEATING, SplitMode.HEATING),
            (HeatPumpMode.COOLING, SplitMode.COOLING),
            (HeatPumpMode.HEATING, SplitMode.OFF),
            (HeatPumpMode.COOLING, SplitMode.OFF),
            (HeatPumpMode.OFF, SplitMode.OFF),
        ],
    )
    def test_safety_violation_no_raise_for_valid_combinations(
        self,
        hp_mode: HeatPumpMode,
        split_mode: SplitMode,
    ) -> None:
        """Valid (non-opposing) mode combinations do not raise."""
        coordinator = SplitCoordinator(ControllerConfig())
        # Should return None without raising
        coordinator._check_axiom3(hp_mode, split_mode, "bedroom")

    def test_decide_accepts_room_name_kwarg(self) -> None:
        """decide() accepts the new optional room_name keyword argument.

        Backward compatibility: existing call sites without room_name
        still work, and the new keyword can be passed through.
        """
        config = ControllerConfig(split_deadband=0.5)
        coordinator = SplitCoordinator(config)
        decision = coordinator.decide(
            error=1.0,
            setpoint=21.0,
            hp_mode=HeatPumpMode.HEATING,
            room_name="bedroom",
        )
        assert decision.split_mode == SplitMode.HEATING
