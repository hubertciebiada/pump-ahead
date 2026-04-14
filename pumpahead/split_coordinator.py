"""Split/AC coordination with underfloor heating (UFH).

Provides ``SplitDecision`` (frozen dataclass) and ``SplitCoordinator``
(per-room stateful coordinator) that determine when a split unit should
activate, at what setpoint, and whether anti-takeover valve boosting
is needed.

Design principles:
    * UFH is always the primary heat source (Axiom #1).
    * Split never opposes the heat pump mode (Axiom #3).
    * Split runtime > threshold triggers valve floor boost to force
      UFH takeover (Axiom #2 — zero priority inversion).
    * Rule-based entry/exit via deadband + error direction.  MPC-based
      activation deferred to MPC integration milestone.

The coordinator is instantiated per room by ``PumpAheadController``.
Rooms without a split unit receive no coordinator instance and always
get ``SplitMode.OFF``.

Units:
    Temperatures: degC
    Time: minutes (sliding window entries)
    Valve boost: 0-100 %
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from pumpahead.config import ControllerConfig
from pumpahead.simulator import HeatPumpMode, SplitMode


class SafetyViolationError(RuntimeError):
    """Raised when a hard safety axiom would be violated.

    Inherits from :class:`RuntimeError` so existing catch-alls still trap
    it, but the dedicated type lets safety logic be distinguished from
    generic runtime errors. Used by :class:`SplitCoordinator` to enforce
    Axiom #3 (split never opposes HP mode).

    Unlike ``assert`` statements, raising this error survives running
    Python with the ``-O`` (optimize) flag, so the safety check cannot be
    silently stripped from production deployments.
    """


@dataclass(frozen=True)
class SplitDecision:
    """Immutable result of a split coordination decision.

    Returned by :meth:`SplitCoordinator.decide` to communicate what
    the split unit should do and whether anti-takeover is active.

    Attributes:
        split_mode: Operating mode for the split unit.
        split_setpoint: Target temperature for the split [degC].
            Only meaningful when ``split_mode`` is not ``OFF``.
        valve_floor_boost: Additional valve floor percentage from
            anti-takeover [%].  Zero when anti-takeover is not active.
        anti_takeover_active: Whether anti-takeover is currently
            triggered due to excessive split runtime.
    """

    split_mode: SplitMode
    split_setpoint: float = 0.0
    valve_floor_boost: float = 0.0
    anti_takeover_active: bool = False


class SplitCoordinator:
    """Per-room split/AC coordinator with anti-takeover protection.

    Tracks split runtime over a sliding window and decides whether the
    split should be ON or OFF based on the temperature error, heat pump
    mode, and deadband configuration.

    Anti-takeover (Axiom #2): when split runtime in the sliding window
    exceeds ``config.anti_takeover_threshold_minutes``, the decision
    includes a ``valve_floor_boost`` to force UFH to increase its
    contribution.

    Typical usage::

        coordinator = SplitCoordinator(config)
        decision = coordinator.decide(error=1.5, setpoint=21.0,
                                      hp_mode=HeatPumpMode.HEATING)
        # Apply decision.split_mode and decision.valve_floor_boost

    Args:
        config: Controller configuration with split parameters.
        window_size: Size of the sliding window [minutes] for runtime
            tracking.  Defaults to 60 (1 hour).
    """

    def __init__(
        self,
        config: ControllerConfig,
        window_size: int = 60,
    ) -> None:
        if window_size < 1:
            msg = f"window_size must be >= 1, got {window_size}"
            raise ValueError(msg)

        self._config = config
        self._window_size = window_size
        self._runtime_window: deque[bool] = deque(maxlen=window_size)

    # -- Properties -----------------------------------------------------------

    @property
    def split_runtime_minutes(self) -> int:
        """Number of minutes the split was ON in the current window."""
        return sum(self._runtime_window)

    @property
    def anti_takeover_active(self) -> bool:
        """Whether anti-takeover is currently triggered."""
        return (
            self.split_runtime_minutes >= self._config.anti_takeover_threshold_minutes
        )

    @property
    def window_size(self) -> int:
        """Size of the sliding window [minutes]."""
        return self._window_size

    # -- Public interface -----------------------------------------------------

    def decide(
        self,
        error: float,
        setpoint: float,
        hp_mode: HeatPumpMode,
        room_name: str | None = None,
    ) -> SplitDecision:
        """Decide split action based on error, setpoint, and HP mode.

        Decision logic:
        1. If ``hp_mode`` is OFF, split is OFF.
        2. Anti-takeover check (Axiom #2): if split runtime exceeds
           threshold, split is forced OFF and valve boost is applied.
           This forces UFH to become the primary source again.
        3. If ``|error| > split_deadband`` and error direction matches
           the HP mode, split activates in the matching mode.
        4. Mode enforcement (Axiom #3): split never opposes HP mode.

        The method records one entry (True/False) in the sliding window
        on every call.

        Args:
            error: Temperature error ``setpoint - T_room`` [degC].
                Positive means room is below setpoint.
            setpoint: Room setpoint temperature [degC].
            hp_mode: Current heat pump operating mode.
            room_name: Optional room identifier used for diagnostic
                messages when an Axiom #3 safety violation is detected.
                When ``None`` the diagnostic message uses
                ``'<unknown>'``.

        Returns:
            A frozen ``SplitDecision`` with the recommended action.

        Raises:
            SafetyViolationError: If the chosen split mode would
                oppose the heat pump mode (Axiom #3 violation). This
                check is enforced via an explicit ``raise`` rather
                than ``assert`` so it survives ``python -O``.
        """
        cfg = self._config

        # HP OFF -> split OFF
        if hp_mode == HeatPumpMode.OFF:
            self._runtime_window.append(False)
            return SplitDecision(split_mode=SplitMode.OFF)

        # Anti-takeover: if runtime exceeds threshold, force split OFF
        # and boost valve floor to make UFH the primary source (Axiom #2)
        if self.anti_takeover_active:
            self._runtime_window.append(False)
            return SplitDecision(
                split_mode=SplitMode.OFF,
                valve_floor_boost=cfg.anti_takeover_valve_boost_pct,
                anti_takeover_active=True,
            )

        # Determine whether split should activate
        should_activate = False
        split_mode = SplitMode.OFF
        split_setpoint = 0.0

        if abs(error) > cfg.split_deadband:
            if hp_mode == HeatPumpMode.HEATING and error > 0:
                # Room is below setpoint in heating mode -> split heats
                should_activate = True
                split_mode = SplitMode.HEATING
                split_setpoint = setpoint + cfg.split_setpoint_offset
            elif hp_mode == HeatPumpMode.COOLING and error < 0:
                # Room is above setpoint in cooling mode -> split cools
                should_activate = True
                split_mode = SplitMode.COOLING
                split_setpoint = setpoint - cfg.split_setpoint_offset

        # Record runtime
        self._runtime_window.append(should_activate)

        if not should_activate:
            return SplitDecision(split_mode=SplitMode.OFF)

        # Axiom #3: split mode must never oppose HP mode. Enforced via
        # an explicit raise so the check is NOT stripped under python -O.
        self._check_axiom3(hp_mode, split_mode, room_name)

        return SplitDecision(
            split_mode=split_mode,
            split_setpoint=split_setpoint,
        )

    def reset(self) -> None:
        """Clear the runtime sliding window."""
        self._runtime_window.clear()

    # -- Internal helpers -----------------------------------------------------

    def _check_axiom3(
        self,
        hp_mode: HeatPumpMode,
        split_mode: SplitMode,
        room_name: str | None,
    ) -> None:
        """Enforce Axiom #3 (split never opposes HP mode).

        Args:
            hp_mode: Current heat pump operating mode.
            split_mode: Proposed split unit operating mode.
            room_name: Optional room identifier used to make the
                diagnostic message actionable. ``None`` is rendered
                as ``'<unknown>'``.

        Raises:
            SafetyViolationError: If the split mode would oppose the
                heat pump mode. Always raises explicitly (never via
                ``assert``) so the check survives ``python -O``.
        """
        room_label = room_name if room_name is not None else "<unknown>"
        if hp_mode == HeatPumpMode.HEATING and split_mode == SplitMode.COOLING:
            msg = (
                f"Axiom #3 violation in room {room_label!r}: split would COOL "
                f"while heat pump is in HEATING mode "
                f"(hp_mode={hp_mode.name}, split_mode={split_mode.name})"
            )
            raise SafetyViolationError(msg)
        if hp_mode == HeatPumpMode.COOLING and split_mode == SplitMode.HEATING:
            msg = (
                f"Axiom #3 violation in room {room_label!r}: split would HEAT "
                f"while heat pump is in COOLING mode "
                f"(hp_mode={hp_mode.name}, split_mode={split_mode.name})"
            )
            raise SafetyViolationError(msg)
