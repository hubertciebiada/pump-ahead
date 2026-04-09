"""Watchdog monitor with heartbeat tracking and fallback state machine.

Tracks the age of the coordinator's heartbeat and manages transitions
between OK, FALLBACK, and RECOVERING states.  The watchdog triggers
fallback to the heat pump's native heating curve when PumpAhead has
not updated for longer than the configured timeout (default 15 min,
matching S5 in ``safety_rules.py``).

The state machine uses hysteresis to prevent oscillation:

    OK  -->  FALLBACK   : seconds_since_heartbeat > timeout_seconds
    FALLBACK --> RECOVERING : seconds_since_heartbeat < recovery_seconds
    RECOVERING --> OK       : next update with heartbeat still fresh

Design principles:
    * Safety is independent of the algorithm (Axiom #6).
    * Zero ``homeassistant`` dependency -- pure Python, testable standalone.
    * Hysteresis band prevents rapid state toggling.
    * Notifications fire only on state transitions (``should_notify``).
    * ``fallback_active`` is True in both FALLBACK and RECOVERING states
      so that the heat pump stays on its native curve until full recovery.

Units:
    Time: seconds (constructor thresholds and ``update`` argument).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class WatchdogState(Enum):
    """Watchdog state machine states.

    Members:
        OK: Algorithm is running normally; heartbeat is fresh.
        FALLBACK: Heartbeat timed out; HP deferred to native curve.
        RECOVERING: Heartbeat resumed but not yet confirmed stable.
    """

    OK = "ok"
    FALLBACK = "fallback"
    RECOVERING = "recovering"


# ---------------------------------------------------------------------------
# Status snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WatchdogStatus:
    """Immutable snapshot of the watchdog evaluation result.

    Attributes:
        state: Current watchdog state.
        seconds_since_heartbeat: Age of the last heartbeat [s].
        should_notify: ``True`` only when the state changed on this
            evaluation (prevents notification spam).
        fallback_active: ``True`` when the heat pump should remain on
            its native curve (FALLBACK or RECOVERING).
    """

    state: WatchdogState
    seconds_since_heartbeat: float
    should_notify: bool
    fallback_active: bool


# ---------------------------------------------------------------------------
# Stateful monitor
# ---------------------------------------------------------------------------


class WatchdogMonitor:
    """Stateful watchdog monitor with hysteresis.

    Tracks heartbeat freshness and manages state transitions between
    OK, FALLBACK, and RECOVERING.  Call :meth:`update` each coordinator
    cycle with the age of the last heartbeat.

    The monitor does **not** import ``homeassistant`` -- it is a pure
    Python state machine suitable for standalone unit testing.

    Args:
        timeout_seconds: Heartbeat age [s] that triggers FALLBACK.
            Default ``900.0`` (15 min, matching S5_WATCHDOG.threshold_on).
        recovery_seconds: Heartbeat age [s] below which FALLBACK
            transitions to RECOVERING.  Default ``300.0`` (5 min,
            matching S5_WATCHDOG.threshold_off).
    """

    def __init__(
        self,
        timeout_seconds: float = 900.0,
        recovery_seconds: float = 300.0,
    ) -> None:
        if timeout_seconds <= 0.0:
            msg = f"timeout_seconds must be > 0, got {timeout_seconds}"
            raise ValueError(msg)
        if recovery_seconds <= 0.0:
            msg = f"recovery_seconds must be > 0, got {recovery_seconds}"
            raise ValueError(msg)
        if recovery_seconds >= timeout_seconds:
            msg = (
                f"recovery_seconds ({recovery_seconds}) must be "
                f"< timeout_seconds ({timeout_seconds})"
            )
            raise ValueError(msg)

        self._timeout_seconds = timeout_seconds
        self._recovery_seconds = recovery_seconds
        self._state = WatchdogState.OK

    # -- Properties -----------------------------------------------------------

    @property
    def state(self) -> WatchdogState:
        """Current watchdog state."""
        return self._state

    # -- Public interface -----------------------------------------------------

    def update(self, seconds_since_heartbeat: float) -> WatchdogStatus:
        """Evaluate heartbeat age and transition state if needed.

        State transitions (with hysteresis):

        * **OK -> FALLBACK**: ``seconds_since_heartbeat > timeout_seconds``
          (strict greater-than; exactly at threshold stays OK).
        * **FALLBACK -> RECOVERING**: ``seconds_since_heartbeat < recovery_seconds``
          (heartbeat resumed).
        * **RECOVERING -> OK**: ``seconds_since_heartbeat < recovery_seconds``
          (confirmed stable on the next good cycle).

        Args:
            seconds_since_heartbeat: Age of the last successful
                coordinator update [s].  Must be >= 0.

        Returns:
            A :class:`WatchdogStatus` snapshot with the new state,
            whether a notification should be sent, and whether
            fallback is active.
        """
        if seconds_since_heartbeat < 0.0:
            msg = (
                "seconds_since_heartbeat must be >= 0, "
                f"got {seconds_since_heartbeat}"
            )
            raise ValueError(msg)

        previous_state = self._state

        if self._state == WatchdogState.OK:
            if seconds_since_heartbeat > self._timeout_seconds:
                self._state = WatchdogState.FALLBACK
        elif self._state == WatchdogState.FALLBACK:
            if seconds_since_heartbeat < self._recovery_seconds:
                self._state = WatchdogState.RECOVERING
        elif self._state == WatchdogState.RECOVERING:
            if seconds_since_heartbeat < self._recovery_seconds:
                self._state = WatchdogState.OK
            elif seconds_since_heartbeat > self._timeout_seconds:
                # Heartbeat went stale again during recovery.
                self._state = WatchdogState.FALLBACK

        changed = self._state != previous_state
        fallback_active = self._state in (
            WatchdogState.FALLBACK,
            WatchdogState.RECOVERING,
        )

        return WatchdogStatus(
            state=self._state,
            seconds_since_heartbeat=seconds_since_heartbeat,
            should_notify=changed,
            fallback_active=fallback_active,
        )

    def reset(self) -> None:
        """Reset the watchdog to the initial OK state."""
        self._state = WatchdogState.OK
