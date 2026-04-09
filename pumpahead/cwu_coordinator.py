"""CWU (domestic hot water) coordination with underfloor heating.

During a CWU cycle the heat pump is dedicated to DHW production and
floor heating loops receive no power (Q_floor=0).  The ``CWUCoordinator``
prevents false-alarm split activations (anti-panic) and pre-charges
the slab before predicted CWU interruptions.

Anti-panic logic:
    When CWU is active and ``T_room > setpoint - margin``, split
    activation is blocked.  The room temperature drop during a typical
    45-min CWU cycle is < 0.5 degC thanks to slab thermal mass, so
    activating a split would be unnecessary and wasteful.  Safety
    fallback: when ``T_room <= setpoint - margin``, the split is
    unblocked even during CWU.

Pre-charge logic:
    When a CWU cycle is predicted to start within a configurable
    lookahead window, the coordinator returns an additive valve floor
    boost.  This raises T_slab slightly before the interruption,
    reducing the room temperature drop during CWU.

The coordinator is instantiated once per ``PumpAheadController`` (not
per room) because CWU is a system-level event affecting all rooms
simultaneously.

Units:
    Temperatures: degC
    Time: minutes (simulation convention)
    Valve boost: 0-100 %
"""

from __future__ import annotations

from pumpahead.config import ControllerConfig, CWUCycle

# ---------------------------------------------------------------------------
# Predefined CWU schedule constants
# ---------------------------------------------------------------------------

CWU_STANDARD: tuple[CWUCycle, ...] = (
    CWUCycle(start_minute=0, duration_minutes=30, interval_minutes=480),
)
"""Standard DHW schedule: 30-min cycle every 8 hours."""

CWU_HEAVY: tuple[CWUCycle, ...] = (
    CWUCycle(start_minute=0, duration_minutes=45, interval_minutes=180),
)
"""Heavy DHW schedule: 45-min cycle every 3 hours (large family)."""

CWU_WORST_CASE: tuple[CWUCycle, ...] = (
    CWUCycle(start_minute=0, duration_minutes=45, interval_minutes=120),
)
"""Worst-case DHW schedule: 45-min cycle every 2 hours (stress test)."""


# ---------------------------------------------------------------------------
# CWUCoordinator
# ---------------------------------------------------------------------------


class CWUCoordinator:
    """System-level CWU coordinator with anti-panic and pre-charge logic.

    Tracks the CWU schedule and provides two decision methods:

    * :meth:`should_block_split` — returns ``True`` when a split should
      be blocked during an active CWU cycle (anti-panic).
    * :meth:`get_pre_charge_boost` — returns an additive valve floor
      boost when a CWU cycle is predicted to start soon.

    The coordinator does not manage per-room state.  It operates on
    system-level CWU timing and per-room temperature inputs.

    Typical usage::

        cwu = CWUCoordinator(config, cwu_schedule=CWU_HEAVY)

        for t in range(1440):
            is_cwu = sim.is_cwu_active
            boost = cwu.get_pre_charge_boost(t, is_cwu)
            for room in rooms:
                block = cwu.should_block_split(T_room, setpoint, is_cwu)

    Args:
        config: Controller configuration with CWU tuning parameters.
        cwu_schedule: Tuple of CWU cycle definitions.  Empty tuple
            makes the coordinator a no-op.
    """

    def __init__(
        self,
        config: ControllerConfig,
        cwu_schedule: tuple[CWUCycle, ...] = (),
    ) -> None:
        self._config = config
        self._cwu_schedule = cwu_schedule

    # -- Public interface -----------------------------------------------------

    def should_block_split(
        self,
        T_room: float,
        setpoint: float,
        is_cwu_active: bool,
    ) -> bool:
        """Decide whether to block split activation during CWU.

        Anti-panic logic: during a CWU cycle, split activation is
        blocked when the room temperature is still comfortably close
        to setpoint.  This prevents unnecessary split activations
        caused by the temporary Q_floor=0 during DHW production.

        Safety fallback: when ``T_room <= setpoint - margin``, the
        split is unblocked even during CWU to protect comfort.

        Args:
            T_room: Current room air temperature [degC].
            setpoint: Room setpoint temperature [degC].
            is_cwu_active: Whether a CWU cycle is currently active.

        Returns:
            ``True`` if the split should be blocked (anti-panic),
            ``False`` if the split should be allowed.
        """
        if not is_cwu_active:
            return False
        if not self._cwu_schedule:
            return False

        margin = self._config.cwu_anti_panic_margin
        # Block split when room is still warm enough
        # Unblock (return False) when T_room has dropped below safety threshold
        return T_room > setpoint - margin

    def get_pre_charge_boost(
        self,
        current_time_minutes: int,
        is_cwu_active: bool,
    ) -> float:
        """Compute pre-charge valve floor boost before a CWU cycle.

        When a CWU cycle is predicted to start within the lookahead
        window and CWU is not currently active, returns an additive
        valve floor boost to pre-charge the slab.

        Args:
            current_time_minutes: Current simulation time [minutes].
            is_cwu_active: Whether a CWU cycle is currently active.

        Returns:
            Valve floor boost [%].  Zero when no pre-charge is needed.
        """
        if not self._cwu_schedule:
            return 0.0
        if is_cwu_active:
            return 0.0

        lookahead = self._config.cwu_pre_charge_lookahead_minutes
        if lookahead == 0:
            return 0.0

        # Check if any CWU cycle will start within the lookahead window
        for future_t in range(
            current_time_minutes + 1,
            current_time_minutes + lookahead + 1,
        ):
            if self._is_cwu_active_at(future_t):
                return self._config.cwu_pre_charge_valve_boost_pct

        return 0.0

    def reset(self) -> None:
        """Reset coordinator state.

        No-op for now — the coordinator is stateless beyond its
        configuration.  Provided for API consistency with
        ``SplitCoordinator.reset()``.
        """

    # -- Private helpers ------------------------------------------------------

    def _is_cwu_active_at(self, t: int) -> bool:
        """Check if any CWU cycle is active at time *t*.

        Args:
            t: Simulation time [minutes].

        Returns:
            ``True`` if any CWU cycle is active at time *t*.
        """
        for cycle in self._cwu_schedule:
            if t < cycle.start_minute:
                continue
            elapsed = t - cycle.start_minute
            if cycle.interval_minutes == 0:
                if elapsed < cycle.duration_minutes:
                    return True
            else:
                if elapsed % cycle.interval_minutes < cycle.duration_minutes:
                    return True
        return False
