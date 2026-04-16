"""Building simulation engine with single- and multi-room support.

Provides the core simulation loop: ``BuildingSimulator`` manages time
progression and orchestrates one or more ``SimulatedRoom`` physics steps,
while ``Measurements`` and ``Actions`` dataclasses define the
simulator-controller interface.

In multi-room mode the heat pump has finite power (``hp_max_power_w``).
When total room demand exceeds capacity, power is distributed
proportionally to each room's demand.

The simulation loop follows a zero-order hold (ZOH) convention: actions
are applied at the beginning of the time step, held constant for the
step duration (dt=60 s), and the RC model propagates the state.

Units:
    Temperatures: degC
    Powers: W
    Valve position: 0-100 %
    Time: minutes (simulation convention)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Literal

from pumpahead.config import CWUCycle
from pumpahead.sensor_noise import SensorNoise
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.ufh_loop import loop_power
from pumpahead.weather import WeatherSource
from pumpahead.weather_comp import CoolingCompCurve, WeatherCompCurve

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class HeatPumpMode(Enum):
    """Operating mode of the heat pump."""

    HEATING = "heating"
    COOLING = "cooling"
    OFF = "off"


class SplitMode(Enum):
    """Operating mode of a split/AC unit."""

    OFF = "off"
    HEATING = "heating"
    COOLING = "cooling"


# ---------------------------------------------------------------------------
# Fallback supply temperatures — used only when no weather-compensation
# curve is supplied.  The chosen values sit inside the default clamp range
# of ``WeatherCompCurve`` (>=20 C) and ``CoolingCompCurve`` (>=7 C) so
# they stay representative of a real HP operating point.
# ---------------------------------------------------------------------------

_FALLBACK_T_SUPPLY_HEATING_C: float = 35.0
"""Fallback supply temperature used when no WeatherCompCurve is provided."""

_FALLBACK_T_SUPPLY_COOLING_C: float = 18.0
"""Fallback supply temperature used when no CoolingCompCurve is provided."""


# ---------------------------------------------------------------------------
# Dataclasses — simulator-controller interface
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Measurements:
    """Immutable snapshot of room and system state.

    Attributes:
        T_room: Air temperature [degC].
        T_slab: Slab temperature [degC].
        T_outdoor: Outdoor temperature [degC].
        valve_pos: Current valve position [0-100 %].
        hp_mode: Current heat pump operating mode.
        is_cwu_active: Whether a CWU (DHW) cycle is currently active.
        humidity: Relative humidity [%] (0-100).  Defaults to 50.0
            when no humidity sensor is available.
    """

    T_room: float
    T_slab: float
    T_outdoor: float
    valve_pos: float
    hp_mode: HeatPumpMode
    is_cwu_active: bool = False
    humidity: float = 50.0


@dataclass(frozen=True)
class Actions:
    """Controller commands for one simulation step.

    Attributes:
        valve_position: Desired UFH valve position [0-100 %].
        split_mode: Split/AC operating mode.
        split_setpoint: Split target temperature [degC].
            Only used when ``split_mode`` is not ``OFF``.
    """

    valve_position: float
    split_mode: SplitMode = SplitMode.OFF
    split_setpoint: float = 0.0


# ---------------------------------------------------------------------------
# BuildingSimulator
# ---------------------------------------------------------------------------


class BuildingSimulator:
    """Core simulation engine for single- and multi-room thermal simulation.

    Manages the simulation loop: receives ``Actions`` from a controller,
    applies them to one or more ``SimulatedRoom`` instances, queries
    weather, propagates the RC models, and returns ``Measurements``.

    For single-room usage the API is fully backward compatible: pass a
    single ``SimulatedRoom`` and use :meth:`step`.

    For multi-room usage pass a list of rooms and optionally an
    ``hp_max_power_w`` limit.  Use :meth:`step_all` to advance all
    rooms simultaneously with HP capacity sharing.

    Typical single-room usage::

        geom = LoopGeometry(
            effective_pipe_length_m=130.0,
            pipe_spacing_m=0.15,
            pipe_diameter_outer_mm=16.0,
            pipe_wall_thickness_mm=2.0,
            area_m2=20.0,
        )
        room = SimulatedRoom("living", model, loop_geometry=geom)
        weather = SyntheticWeather.constant(T_out=-5.0, GHI=0.0)
        sim = BuildingSimulator(room, weather)

        for _ in range(1440):
            meas = sim.step(Actions(valve_position=50.0))
            print(meas.T_room)

    Typical multi-room usage::

        rooms = [SimulatedRoom(f"room_{i}", model) for i in range(8)]
        sim = BuildingSimulator(rooms, weather, hp_max_power_w=6000.0)
        actions = {r.name: Actions(valve_position=50.0) for r in rooms}
        results = sim.step_all(actions)
    """

    def __init__(
        self,
        room: SimulatedRoom | list[SimulatedRoom],
        weather: WeatherSource,
        hp_mode: HeatPumpMode = HeatPumpMode.HEATING,
        split_power_w: float = 2500.0,
        hp_max_power_w: float | None = None,
        cwu_schedule: list[CWUCycle] | None = None,
        sensor_noise: SensorNoise | None = None,
        *,
        weather_comp: WeatherCompCurve | None = None,
        cooling_comp: CoolingCompCurve | None = None,
    ) -> None:
        """Initialize the simulator.

        Args:
            room: A single ``SimulatedRoom`` or a list of rooms.
            weather: Weather data source.
            hp_mode: Heat pump operating mode.
            split_power_w: Maximum split/AC power [W].
            hp_max_power_w: Heat pump total capacity [W].  ``None`` means
                unlimited (no scaling).
            cwu_schedule: Optional list of CWU (DHW) interrupt cycles.
                During an active CWU cycle, Q_floor is forced to 0.
            sensor_noise: Optional sensor noise source.  When provided,
                Gaussian noise is added to T_room and T_slab in returned
                ``Measurements``.  Does not affect physical state.
            weather_comp: Optional heating weather-compensation curve.
                When provided, ``T_supply`` used by the physical UFH
                model is derived from ``weather_comp.t_supply(T_out)``
                during heating steps.  ``None`` (default) falls back to
                ``_FALLBACK_T_SUPPLY_HEATING_C``.
            cooling_comp: Optional cooling weather-compensation curve.
                Used only when ``hp_mode == HeatPumpMode.COOLING``.
                ``None`` (default) falls back to
                ``_FALLBACK_T_SUPPLY_COOLING_C``.

        Raises:
            ValueError: If the room list is empty or contains duplicate
                room names.
        """
        if isinstance(room, list):
            if len(room) == 0:
                msg = "room list must not be empty"
                raise ValueError(msg)
            names = [r.name for r in room]
            if len(names) != len(set(names)):
                msg = f"room names must be unique, got duplicates in {names}"
                raise ValueError(msg)
            self._rooms: list[SimulatedRoom] = room
        else:
            self._rooms = [room]

        # Issue #144: every room must carry pipe geometry so the
        # physical UFH model (``pumpahead.ufh_loop.loop_power``) can be
        # evaluated.  Fail fast instead of silently dropping power.
        for r in self._rooms:
            if r.loop_geometry is None:
                msg = (
                    f"SimulatedRoom '{r.name}' must have loop_geometry set "
                    f"(issue #144 removed the proportional-power fallback)"
                )
                raise ValueError(msg)

        self._weather = weather
        self._hp_mode = hp_mode
        self._split_power_w = split_power_w
        self._hp_max_power_w = (
            hp_max_power_w if hp_max_power_w is not None else math.inf
        )
        self._cwu_schedule: list[CWUCycle] = cwu_schedule or []
        self._sensor_noise = sensor_noise
        self._weather_comp = weather_comp
        self._cooling_comp = cooling_comp
        self._time_minutes: int = 0
        self._dt_minutes: int = 1

        # Diagnostics populated by ``_distribute_hp_power``.
        self._last_t_supply_c: float | None = None
        self._last_q_floor_w: dict[str, float] = {}

    # -- Properties ----------------------------------------------------------

    @property
    def time_minutes(self) -> int:
        """Return the current simulation time in minutes."""
        return self._time_minutes

    @property
    def room(self) -> SimulatedRoom:
        """Return the first (or only) simulated room for backward compat."""
        return self._rooms[0]

    @property
    def rooms(self) -> dict[str, SimulatedRoom]:
        """Return all rooms as a name-keyed dictionary (read-only)."""
        return {r.name: r for r in self._rooms}

    @property
    def hp_mode(self) -> HeatPumpMode:
        """Return the current heat pump operating mode."""
        return self._hp_mode

    @property
    def is_cwu_active(self) -> bool:
        """Return whether a CWU cycle is active at the current time."""
        return self._check_cwu_active()

    @property
    def last_step_info(self) -> dict[str, object]:
        """Return diagnostics from the most recent ``_distribute_hp_power`` call.

        The returned dictionary contains three keys:

        * ``t_supply_c`` — supply temperature [degC] used in the last
          distribution step, or ``None`` before any step and when the
          heat pump was in ``HeatPumpMode.OFF``.
        * ``q_floor_w`` — per-room allocated floor power [W].  Positive
          in heating, negative in cooling.  Empty dictionary before any
          distribution has been performed.
        * ``hp_mode`` — the current :class:`HeatPumpMode`.

        The ``q_floor_w`` dictionary is a defensive copy — mutating it
        does not affect subsequent diagnostics.

        Returns:
            Dictionary with diagnostic state from the last step.
        """
        return {
            "t_supply_c": self._last_t_supply_c,
            "q_floor_w": dict(self._last_q_floor_w),
            "hp_mode": self._hp_mode,
        }

    def set_hp_mode(self, mode: HeatPumpMode) -> None:
        """Update the heat pump operating mode.

        Used by the controller to switch between HEATING and COOLING
        during auto-mode simulation.

        Args:
            mode: The new heat pump operating mode.
        """
        self._hp_mode = mode

    # -- Private helpers -----------------------------------------------------

    def _check_cwu_active(self) -> bool:
        """Check if any CWU cycle is active at the current simulation time.

        For each cycle in the schedule, the cycle is active when:
        - The current time is at or after the cycle's start_minute, AND
        - For repeating cycles (interval > 0): the time within the current
          period is less than the duration.
        - For single-shot cycles (interval == 0): the elapsed time since
          start is less than the duration.

        Returns:
            True if any CWU cycle is currently active.
        """
        t = self._time_minutes
        for cycle in self._cwu_schedule:
            if t < cycle.start_minute:
                continue
            elapsed = t - cycle.start_minute
            if cycle.interval_minutes == 0:
                # Single-shot: active only during first occurrence
                if elapsed < cycle.duration_minutes:
                    return True
            else:
                # Repeating: check position within period
                if elapsed % cycle.interval_minutes < cycle.duration_minutes:
                    return True
        return False

    def _apply_noise(self, measurements: Measurements) -> Measurements:
        """Apply sensor noise to temperature fields if noise is configured.

        Only T_room and T_slab are corrupted.  T_outdoor, valve_pos,
        and hp_mode are returned unchanged.

        Args:
            measurements: Clean measurements from the physical simulation.

        Returns:
            A new ``Measurements`` instance with noisy temperatures,
            or the original instance if no noise source is configured.
        """
        if self._sensor_noise is None:
            return measurements
        return Measurements(
            T_room=self._sensor_noise.corrupt(measurements.T_room),
            T_slab=self._sensor_noise.corrupt(measurements.T_slab),
            T_outdoor=measurements.T_outdoor,
            valve_pos=measurements.valve_pos,
            hp_mode=measurements.hp_mode,
            is_cwu_active=measurements.is_cwu_active,
            humidity=measurements.humidity,
        )

    # -- Public interface — single room (backward compatible) ----------------

    def get_measurements(self) -> Measurements:
        """Return current measurements for the first room.

        If a ``SensorNoise`` source is configured, Gaussian noise is
        applied to T_room and T_slab.  The physical state is unaffected.

        Returns:
            A ``Measurements`` snapshot of the current state.
        """
        wp = self._weather.get(float(self._time_minutes))
        first = self._rooms[0]
        cwu_active = self._check_cwu_active()
        clean = Measurements(
            T_room=first.T_air,
            T_slab=first.T_slab,
            T_outdoor=wp.T_out,
            valve_pos=first.valve_position,
            hp_mode=self._hp_mode,
            is_cwu_active=cwu_active,
            humidity=wp.humidity,
        )
        return self._apply_noise(clean)

    def step(self, actions: Actions) -> Measurements:
        """Apply actions to the first room, propagate, and return measurements.

        This is the original single-room API, fully backward compatible
        from the caller's perspective.  Internally it delegates to
        :meth:`step_all` so the single-room and multi-room paths share
        the exact same physical distributor (``_distribute_hp_power`` →
        ``loop_power``).  Issue #144 eliminated the old proportional
        ``valve * rated-power`` shim that the legacy single-room
        ``step()`` used to take.

        Args:
            actions: Controller commands for this time step.

        Returns:
            A ``Measurements`` snapshot after the step for the first
            (or only) room.
        """
        first = self._rooms[0]
        all_meas = self.step_all({first.name: actions})
        return all_meas[first.name]

    # -- Public interface — multi-room ---------------------------------------

    def get_all_measurements(self) -> dict[str, Measurements]:
        """Return current measurements for every room.

        If a ``SensorNoise`` source is configured, Gaussian noise is
        applied to T_room and T_slab for each room.  The physical state
        is unaffected.

        Returns:
            Dictionary keyed by room name with ``Measurements`` values.
        """
        wp = self._weather.get(float(self._time_minutes))
        cwu_active = self._check_cwu_active()
        result: dict[str, Measurements] = {}
        for r in self._rooms:
            clean = Measurements(
                T_room=r.T_air,
                T_slab=r.T_slab,
                T_outdoor=wp.T_out,
                valve_pos=r.valve_position,
                hp_mode=self._hp_mode,
                is_cwu_active=cwu_active,
                humidity=wp.humidity,
            )
            result[r.name] = self._apply_noise(clean)
        return result

    def step_all(
        self,
        actions: dict[str, Actions],
    ) -> dict[str, Measurements]:
        """Apply per-room actions, distribute HP power, and propagate all rooms.

        Args:
            actions: Dictionary of ``Actions`` keyed by room name.  Must
                contain exactly one entry per room managed by this simulator.

        Returns:
            Dictionary of ``Measurements`` keyed by room name after the step.

        Raises:
            ValueError: If action keys do not match room names exactly.
        """
        room_names = {r.name for r in self._rooms}
        action_names = set(actions.keys())
        if action_names != room_names:
            missing = room_names - action_names
            extra = action_names - room_names
            parts: list[str] = []
            if missing:
                parts.append(f"missing rooms: {sorted(missing)}")
            if extra:
                parts.append(f"unknown rooms: {sorted(extra)}")
            msg = f"Action keys do not match room names: {', '.join(parts)}"
            raise ValueError(msg)

        # CWU interrupt: force valve closed when HP is in DHW mode.
        # Only valve_position is zeroed; split_mode/split_setpoint are
        # preserved so that splits continue operating (Axiom #1/#2).
        cwu_active = self._check_cwu_active()
        effective_actions = actions
        if cwu_active:
            effective_actions = {
                name: replace(a, valve_position=0.0) for name, a in actions.items()
            }

        # Apply actuator commands to each room
        for r in self._rooms:
            a = effective_actions[r.name]
            if a.split_mode == SplitMode.OFF:
                split_power = 0.0
            elif a.split_mode == SplitMode.HEATING:
                split_power = self._split_power_w
            else:
                split_power = -self._split_power_w
            r.apply_actions(
                valve_position=a.valve_position,
                split_power_w=split_power,
            )

        # Distribute HP power (uses effective_actions with zeroed valves
        # during CWU, so all floor allocations will be 0 W)
        allocated = self._distribute_hp_power(effective_actions)

        # Get weather at current time
        wp = self._weather.get(float(self._time_minutes))

        # Propagate physics for each room with allocated power
        for r in self._rooms:
            r.step_with_power(wp, q_floor_w=allocated[r.name], q_sol_w=0.0)

        # Advance clock
        self._time_minutes += self._dt_minutes

        return self.get_all_measurements()

    # -- Private helpers -----------------------------------------------------

    def _compute_t_supply(self, t_out: float) -> float:
        """Compute supply temperature for the current HP mode.

        Uses the weather-compensation curve when available, otherwise
        falls back to the module-level constant for the current mode.

        Args:
            t_out: Current outdoor temperature [degC].

        Returns:
            Supply temperature [degC].  Returns ``0.0`` when the HP is
            OFF — callers should not use the value in that case.
        """
        if self._hp_mode == HeatPumpMode.HEATING:
            if self._weather_comp is not None:
                return self._weather_comp.t_supply(t_out)
            return _FALLBACK_T_SUPPLY_HEATING_C
        if self._hp_mode == HeatPumpMode.COOLING:
            if self._cooling_comp is not None:
                return self._cooling_comp.t_supply(t_out)
            return _FALLBACK_T_SUPPLY_COOLING_C
        # HP OFF — callers short-circuit and should not use this value.
        return 0.0

    def _distribute_hp_power(
        self,
        actions: dict[str, Actions],
    ) -> dict[str, float]:
        """Compute per-room floor power respecting HP capacity.

        Algorithm:

        1. When the HP is OFF, every room receives zero floor power and
           diagnostics are reset.
        2. Otherwise, the supply temperature ``T_supply`` is derived
           once (per call) from the appropriate weather-compensation
           curve — ``WeatherCompCurve`` in heating or
           ``CoolingCompCurve`` in cooling — falling back to
           ``_FALLBACK_T_SUPPLY_HEATING_C`` / ``_FALLBACK_T_SUPPLY_COOLING_C``
           when no curve is configured.
        3. For each room the *physical* UFH model is used:
           ``Q_max = loop_power(T_supply, T_slab, geometry, mode)``.
           This already carries the mode-correct sign (positive in
           heating, negative in cooling) and returns ``0.0`` when the
           gradient is wrong (Axiom #3).  Every room is required to
           carry pipe geometry — ``BuildingSimulator.__init__`` raises
           ``ValueError`` if any room has ``loop_geometry is None``.

           Per-room demand is ``valve_fraction * Q_max``.
        4. The absolute total demand is compared against
           ``hp_max_power_w``.  When the HP cannot cover it all, every
           room's allocation is scaled uniformly by ``hp_max_power_w /
           total_abs`` — signs (heating vs cooling) are preserved.
        5. Diagnostics are stored in ``self._last_t_supply_c`` and
           ``self._last_q_floor_w`` so :attr:`last_step_info` exposes
           them for inspection.

        Returns:
            Dictionary of allocated floor power [W] keyed by room name.
            Positive in heating mode, negative in cooling mode, zero
            when the HP is OFF or the valve is closed.
        """
        # HP OFF — short-circuit before computing T_supply.
        if self._hp_mode == HeatPumpMode.OFF:
            result = {r.name: 0.0 for r in self._rooms}
            self._last_t_supply_c = None
            self._last_q_floor_w = dict(result)
            return result

        t_out = self._weather.get(float(self._time_minutes)).T_out
        t_supply = self._compute_t_supply(t_out)
        self._last_t_supply_c = t_supply

        mode_str: Literal["heating", "cooling"] = (
            "cooling" if self._hp_mode == HeatPumpMode.COOLING else "heating"
        )

        # Per-room demand (signed: positive heating, negative cooling).
        # ``BuildingSimulator.__init__`` already guarantees every room
        # carries loop geometry, so ``r.loop_geometry`` is never ``None``.
        demands: dict[str, float] = {}
        for r in self._rooms:
            valve_frac = max(0.0, min(100.0, actions[r.name].valve_position)) / 100.0
            geometry = r.loop_geometry
            assert geometry is not None  # enforced in __init__
            q_max = loop_power(t_supply, r.T_slab, geometry, mode_str)
            demands[r.name] = valve_frac * q_max

        total_abs = sum(abs(d) for d in demands.values())

        if total_abs == 0.0:
            result = {name: 0.0 for name in demands}
        elif total_abs <= self._hp_max_power_w:
            result = dict(demands)
        else:
            scale = self._hp_max_power_w / total_abs
            result = {name: d * scale for name, d in demands.items()}

        self._last_q_floor_w = dict(result)
        return result
