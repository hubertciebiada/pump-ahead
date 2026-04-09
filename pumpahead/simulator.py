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

from pumpahead.config import CWUCycle
from pumpahead.sensor_noise import SensorNoise
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.weather import WeatherSource

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
    """

    T_room: float
    T_slab: float
    T_outdoor: float
    valve_pos: float
    hp_mode: HeatPumpMode
    is_cwu_active: bool = False


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

        room = SimulatedRoom("living", model, ufh_max_power_w=5000.0)
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

        self._weather = weather
        self._hp_mode = hp_mode
        self._split_power_w = split_power_w
        self._hp_max_power_w = (
            hp_max_power_w if hp_max_power_w is not None else math.inf
        )
        self._cwu_schedule: list[CWUCycle] = cwu_schedule or []
        self._sensor_noise = sensor_noise
        self._time_minutes: int = 0
        self._dt_minutes: int = 1

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
        )
        return self._apply_noise(clean)

    def step(self, actions: Actions) -> Measurements:
        """Apply actions to the first room, propagate, and return measurements.

        This is the original single-room API, fully backward compatible.

        The method follows the ZOH convention:
        1. Check CWU schedule -- override valve_position to 0 if active.
        2. Convert ``actions`` to actuator commands.
        3. Apply actuator commands to the room.
        4. Query weather at the current time.
        5. Propagate the RC model by one step.
        6. Advance the simulation clock.
        7. Return updated measurements (with optional sensor noise).

        Args:
            actions: Controller commands for this time step.

        Returns:
            A ``Measurements`` snapshot after the step.
        """
        first = self._rooms[0]

        # CWU interrupt: force valve closed when HP is in DHW mode
        effective_valve = actions.valve_position
        if self._check_cwu_active():
            effective_valve = 0.0

        # Convert split mode to power
        if actions.split_mode == SplitMode.OFF:
            split_power = 0.0
        elif actions.split_mode == SplitMode.HEATING:
            split_power = self._split_power_w
        else:
            # COOLING: negative power
            split_power = -self._split_power_w

        # Apply actions to room actuators
        first.apply_actions(
            valve_position=effective_valve,
            split_power_w=split_power,
        )

        # Get weather at current time
        wp = self._weather.get(float(self._time_minutes))

        # Propagate physics
        first.step(wp, q_sol_w=0.0)

        # Advance clock
        self._time_minutes += self._dt_minutes

        return self.get_measurements()

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

    def _distribute_hp_power(
        self,
        actions: dict[str, Actions],
    ) -> dict[str, float]:
        """Compute per-room floor power respecting HP capacity.

        In HEATING mode:
        1. For each room compute demand = (valve / 100) * ufh_max_power_w.
        2. If total demand <= hp_max_power_w, each room gets its full demand.
        3. Otherwise, scale down proportionally.

        In COOLING mode:
        1. For each room compute demand = (valve / 100) * ufh_cooling_max_power_w.
        2. Scale proportionally if total demand exceeds HP capacity.
        3. Return negative values (cold water in the slab).

        Returns:
            Dictionary of allocated floor power [W] keyed by room name.
            Positive in heating mode, negative in cooling mode.
        """
        is_cooling = self._hp_mode == HeatPumpMode.COOLING

        demands: dict[str, float] = {}
        for r in self._rooms:
            valve = actions[r.name].valve_position
            # Use the clamped value that apply_actions would compute
            clamped = max(0.0, min(100.0, valve))
            if is_cooling:
                demands[r.name] = clamped / 100.0 * r.ufh_cooling_max_power_w
            else:
                demands[r.name] = clamped / 100.0 * r.ufh_max_power_w

        total_demand = sum(demands.values())

        if total_demand == 0.0:
            result = {name: 0.0 for name in demands}
        elif total_demand <= self._hp_max_power_w:
            result = demands
        else:
            scale = self._hp_max_power_w / total_demand
            result = {name: d * scale for name, d in demands.items()}

        # In cooling mode, power is negative (cold water)
        if is_cooling:
            return {name: -d for name, d in result.items()}
        return result
