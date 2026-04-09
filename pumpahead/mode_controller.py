"""Automatic heat/cool mode switching with hysteresis.

Provides the ``ModeController`` class that determines whether the heat
pump should operate in HEATING or COOLING mode based on outdoor
temperature.  The controller uses a hysteresis band and a minimum hold
time to prevent rapid oscillation during transition seasons.

Design principles:
    * Hysteresis prevents chatter: outdoor temperature must cross the
      threshold AND the mode must have been held for ``min_hold_minutes``
      before a switch is allowed.
    * Default band: HEATING below 18 degC, COOLING above 22 degC.
      Between 18-22 degC the current mode is maintained (deadzone).
    * Stateful: tracks minutes spent in the current mode.
    * ``reset()`` clears internal state (like ``SplitCoordinator``).

Units:
    Temperatures: degC
    Time: minutes (simulation convention)
"""

from __future__ import annotations

from pumpahead.simulator import HeatPumpMode


class ModeController:
    """Auto-switching controller for HEATING/COOLING mode selection.

    Uses outdoor temperature thresholds with hysteresis and a minimum
    hold time to prevent rapid mode oscillation.

    Typical usage::

        mc = ModeController(
            heating_threshold=18.0,
            cooling_threshold=22.0,
            min_hold_minutes=60,
        )
        for t_outdoor in outdoor_temps:
            mode = mc.update(t_outdoor)

    Args:
        heating_threshold: Switch to HEATING when T_outdoor drops
            below this value [degC].
        cooling_threshold: Switch to COOLING when T_outdoor rises
            above this value [degC].  Must be > *heating_threshold*.
        min_hold_minutes: Minimum time to hold the current mode before
            allowing a switch [min].  Must be >= 0.
        initial_mode: Starting mode.  Defaults to HEATING.

    Raises:
        ValueError: If thresholds or hold time are invalid.
    """

    def __init__(
        self,
        heating_threshold: float = 18.0,
        cooling_threshold: float = 22.0,
        min_hold_minutes: int = 60,
        initial_mode: HeatPumpMode = HeatPumpMode.HEATING,
    ) -> None:
        if heating_threshold >= cooling_threshold:
            msg = (
                f"heating_threshold ({heating_threshold}) must be < "
                f"cooling_threshold ({cooling_threshold})"
            )
            raise ValueError(msg)
        if min_hold_minutes < 0:
            msg = f"min_hold_minutes must be >= 0, got {min_hold_minutes}"
            raise ValueError(msg)
        if initial_mode == HeatPumpMode.OFF:
            msg = "initial_mode must be HEATING or COOLING, not OFF"
            raise ValueError(msg)

        self._heating_threshold = heating_threshold
        self._cooling_threshold = cooling_threshold
        self._min_hold_minutes = min_hold_minutes
        self._current_mode = initial_mode
        self._minutes_in_current_mode: int = 0

    # -- Properties -----------------------------------------------------------

    @property
    def current_mode(self) -> HeatPumpMode:
        """Return the current operating mode."""
        return self._current_mode

    @property
    def minutes_in_current_mode(self) -> int:
        """Return how many minutes the current mode has been held."""
        return self._minutes_in_current_mode

    @property
    def heating_threshold(self) -> float:
        """Return the heating threshold temperature [degC]."""
        return self._heating_threshold

    @property
    def cooling_threshold(self) -> float:
        """Return the cooling threshold temperature [degC]."""
        return self._cooling_threshold

    @property
    def min_hold_minutes(self) -> int:
        """Return the minimum hold time before mode switch [min]."""
        return self._min_hold_minutes

    # -- Public interface -----------------------------------------------------

    def update(self, t_outdoor: float) -> HeatPumpMode:
        """Update mode based on current outdoor temperature.

        Called once per simulation step (1 minute).  The mode switches
        only when:
        1. T_outdoor crosses the appropriate threshold, AND
        2. The current mode has been held for at least
           ``min_hold_minutes``.

        Between the two thresholds (deadzone) the mode is maintained
        regardless of hold time.

        Args:
            t_outdoor: Current outdoor temperature [degC].

        Returns:
            The (possibly updated) heat pump operating mode.
        """
        self._minutes_in_current_mode += 1

        can_switch = self._minutes_in_current_mode >= self._min_hold_minutes

        if can_switch:
            if (
                self._current_mode == HeatPumpMode.HEATING
                and t_outdoor > self._cooling_threshold
            ):
                self._current_mode = HeatPumpMode.COOLING
                self._minutes_in_current_mode = 0
            elif (
                self._current_mode == HeatPumpMode.COOLING
                and t_outdoor < self._heating_threshold
            ):
                self._current_mode = HeatPumpMode.HEATING
                self._minutes_in_current_mode = 0

        return self._current_mode

    def reset(self) -> None:
        """Reset internal state to initial values."""
        self._minutes_in_current_mode = 0
