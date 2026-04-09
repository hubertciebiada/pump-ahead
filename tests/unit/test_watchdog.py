"""Unit tests for the watchdog monitor.

Tests cover WatchdogState enum members, WatchdogStatus frozen
dataclass, and WatchdogMonitor state machine transitions including
hysteresis, notification deduplication, and oscillation prevention.
"""

from __future__ import annotations

import pytest

from pumpahead.watchdog import WatchdogMonitor, WatchdogState, WatchdogStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_monitor(
    *,
    timeout_seconds: float = 900.0,
    recovery_seconds: float = 300.0,
) -> WatchdogMonitor:
    """Create a WatchdogMonitor with configurable thresholds."""
    return WatchdogMonitor(
        timeout_seconds=timeout_seconds,
        recovery_seconds=recovery_seconds,
    )


# ---------------------------------------------------------------------------
# WatchdogState tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWatchdogState:
    """WatchdogState enum tests."""

    def test_enum_members_exist(self) -> None:
        """All three enum members exist with correct string values."""
        assert WatchdogState.OK.value == "ok"
        assert WatchdogState.FALLBACK.value == "fallback"
        assert WatchdogState.RECOVERING.value == "recovering"

    def test_member_count(self) -> None:
        """Exactly three members."""
        assert len(WatchdogState) == 3


# ---------------------------------------------------------------------------
# WatchdogStatus tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWatchdogStatus:
    """WatchdogStatus frozen dataclass tests."""

    def test_creation(self) -> None:
        """Frozen dataclass can be created with all fields."""
        status = WatchdogStatus(
            state=WatchdogState.OK,
            seconds_since_heartbeat=60.0,
            should_notify=False,
            fallback_active=False,
        )
        assert status.state == WatchdogState.OK
        assert status.seconds_since_heartbeat == 60.0
        assert status.should_notify is False
        assert status.fallback_active is False

    def test_immutability(self) -> None:
        """WatchdogStatus is frozen (immutable)."""
        status = WatchdogStatus(
            state=WatchdogState.OK,
            seconds_since_heartbeat=0.0,
            should_notify=False,
            fallback_active=False,
        )
        with pytest.raises(AttributeError):
            status.state = WatchdogState.FALLBACK  # type: ignore[misc]


# ---------------------------------------------------------------------------
# WatchdogMonitor tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWatchdogMonitor:
    """WatchdogMonitor state machine tests."""

    def test_initial_state_is_ok(self) -> None:
        """New monitor starts in OK state."""
        monitor = _make_monitor()
        assert monitor.state == WatchdogState.OK

    def test_stays_ok_when_heartbeat_recent(self) -> None:
        """Update with recent heartbeat stays in OK state."""
        monitor = _make_monitor()
        status = monitor.update(60.0)
        assert status.state == WatchdogState.OK
        assert status.should_notify is False
        assert status.fallback_active is False

    def test_transitions_to_fallback_on_timeout(self) -> None:
        """Update with age > timeout transitions to FALLBACK."""
        monitor = _make_monitor()
        status = monitor.update(901.0)
        assert status.state == WatchdogState.FALLBACK
        assert status.should_notify is True
        assert status.fallback_active is True

    def test_does_not_trigger_at_exactly_threshold(self) -> None:
        """Update with age == timeout stays OK (strict >)."""
        monitor = _make_monitor()
        status = monitor.update(900.0)
        assert status.state == WatchdogState.OK
        assert status.should_notify is False

    def test_fallback_stays_active_between_thresholds(self) -> None:
        """After triggering, age between recovery and timeout stays FALLBACK."""
        monitor = _make_monitor()
        monitor.update(901.0)  # trigger FALLBACK
        status = monitor.update(600.0)  # between 300 and 900
        assert status.state == WatchdogState.FALLBACK
        assert status.should_notify is False
        assert status.fallback_active is True

    def test_transitions_to_recovering_when_heartbeat_resumes(self) -> None:
        """After FALLBACK, fresh heartbeat transitions to RECOVERING."""
        monitor = _make_monitor()
        monitor.update(901.0)  # trigger FALLBACK
        status = monitor.update(0.0)  # heartbeat resumed
        assert status.state == WatchdogState.RECOVERING
        assert status.should_notify is True
        assert status.fallback_active is True

    def test_recovering_transitions_to_ok(self) -> None:
        """After RECOVERING, next good heartbeat transitions to OK."""
        monitor = _make_monitor()
        monitor.update(901.0)  # FALLBACK
        monitor.update(0.0)  # RECOVERING
        status = monitor.update(0.0)  # should go OK
        assert status.state == WatchdogState.OK
        assert status.should_notify is True
        assert status.fallback_active is False

    def test_should_notify_true_on_state_transition(self) -> None:
        """should_notify is True when state changes, False when stable."""
        monitor = _make_monitor()
        # OK -> OK: no notification
        status = monitor.update(60.0)
        assert status.should_notify is False

        # OK -> FALLBACK: notification
        status = monitor.update(901.0)
        assert status.should_notify is True

        # FALLBACK -> FALLBACK: no notification
        status = monitor.update(901.0)
        assert status.should_notify is False

        # FALLBACK -> RECOVERING: notification
        status = monitor.update(0.0)
        assert status.should_notify is True

        # RECOVERING -> OK: notification
        status = monitor.update(0.0)
        assert status.should_notify is True

        # OK -> OK: no notification
        status = monitor.update(0.0)
        assert status.should_notify is False

    def test_fallback_active_flag(self) -> None:
        """fallback_active is True in FALLBACK and RECOVERING, False in OK."""
        monitor = _make_monitor()

        # OK
        status = monitor.update(0.0)
        assert status.fallback_active is False

        # FALLBACK
        status = monitor.update(901.0)
        assert status.fallback_active is True

        # RECOVERING
        status = monitor.update(0.0)
        assert status.fallback_active is True

        # OK again
        status = monitor.update(0.0)
        assert status.fallback_active is False

    def test_custom_timeout_and_recovery(self) -> None:
        """Constructor accepts custom thresholds."""
        monitor = _make_monitor(timeout_seconds=60.0, recovery_seconds=10.0)

        # Below custom timeout: stays OK
        status = monitor.update(59.0)
        assert status.state == WatchdogState.OK

        # Above custom timeout: triggers FALLBACK
        status = monitor.update(61.0)
        assert status.state == WatchdogState.FALLBACK

        # Below custom recovery: transitions to RECOVERING
        status = monitor.update(5.0)
        assert status.state == WatchdogState.RECOVERING

    def test_reset_returns_to_ok(self) -> None:
        """reset() clears state to OK regardless of current state."""
        monitor = _make_monitor()
        monitor.update(901.0)  # FALLBACK
        assert monitor.state == WatchdogState.FALLBACK

        monitor.reset()
        assert monitor.state == WatchdogState.OK

    def test_oscillation_prevention(self) -> None:
        """Rapid alternation between good and bad heartbeats does not
        cause rapid state changes due to hysteresis."""
        monitor = _make_monitor()

        # OK -> FALLBACK
        monitor.update(901.0)
        assert monitor.state == WatchdogState.FALLBACK

        # Age drops to 600s (between 300 and 900): stays FALLBACK
        status = monitor.update(600.0)
        assert status.state == WatchdogState.FALLBACK

        # Age spikes back above timeout: stays FALLBACK (no extra transition)
        status = monitor.update(950.0)
        assert status.state == WatchdogState.FALLBACK
        assert status.should_notify is False

        # Age finally drops below recovery: transitions to RECOVERING
        status = monitor.update(100.0)
        assert status.state == WatchdogState.RECOVERING

    def test_recovering_back_to_fallback_on_timeout(self) -> None:
        """Heartbeat going stale again during RECOVERING reverts to FALLBACK."""
        monitor = _make_monitor()
        monitor.update(901.0)  # FALLBACK
        monitor.update(0.0)  # RECOVERING

        # Heartbeat goes stale again
        status = monitor.update(901.0)
        assert status.state == WatchdogState.FALLBACK
        assert status.should_notify is True

    def test_negative_heartbeat_age_raises(self) -> None:
        """Negative heartbeat age raises ValueError."""
        monitor = _make_monitor()
        with pytest.raises(ValueError, match="seconds_since_heartbeat must be >= 0"):
            monitor.update(-1.0)

    def test_invalid_timeout_seconds_raises(self) -> None:
        """Zero or negative timeout raises ValueError."""
        with pytest.raises(ValueError, match="timeout_seconds must be > 0"):
            WatchdogMonitor(timeout_seconds=0.0)

    def test_invalid_recovery_seconds_raises(self) -> None:
        """Zero or negative recovery raises ValueError."""
        with pytest.raises(ValueError, match="recovery_seconds must be > 0"):
            WatchdogMonitor(timeout_seconds=900.0, recovery_seconds=0.0)

    def test_recovery_gte_timeout_raises(self) -> None:
        """Recovery >= timeout raises ValueError (no hysteresis band)."""
        with pytest.raises(ValueError, match="recovery_seconds.*must be"):
            WatchdogMonitor(timeout_seconds=60.0, recovery_seconds=60.0)
