"""Building simulation engine with single-room support.

Provides the core simulation loop: ``BuildingSimulator`` manages time
progression and orchestrates the ``SimulatedRoom`` physics step, while
``Measurements`` and ``Actions`` dataclasses define the simulator-controller
interface.

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

from dataclasses import dataclass
from enum import Enum

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
    """

    T_room: float
    T_slab: float
    T_outdoor: float
    valve_pos: float
    hp_mode: HeatPumpMode


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
    """Core simulation engine for single-room thermal simulation.

    Manages the simulation loop: receives ``Actions`` from a controller,
    applies them to the ``SimulatedRoom``, queries weather, propagates
    the RC model, and returns ``Measurements``.

    Typical usage::

        room = SimulatedRoom("living", model, ufh_max_power_w=5000.0)
        weather = SyntheticWeather.constant(T_out=-5.0, GHI=0.0)
        sim = BuildingSimulator(room, weather)

        for _ in range(1440):
            meas = sim.step(Actions(valve_position=50.0))
            print(meas.T_room)
    """

    def __init__(
        self,
        room: SimulatedRoom,
        weather: WeatherSource,
        hp_mode: HeatPumpMode = HeatPumpMode.HEATING,
        split_power_w: float = 2500.0,
    ) -> None:
        """Initialize the simulator.

        Args:
            room: The simulated room to manage.
            weather: Weather data source.
            hp_mode: Heat pump operating mode.
            split_power_w: Maximum split/AC power [W].
        """
        self._room = room
        self._weather = weather
        self._hp_mode = hp_mode
        self._split_power_w = split_power_w
        self._time_minutes: int = 0
        self._dt_minutes: int = 1

    # -- Properties ----------------------------------------------------------

    @property
    def time_minutes(self) -> int:
        """Return the current simulation time in minutes."""
        return self._time_minutes

    @property
    def room(self) -> SimulatedRoom:
        """Return the simulated room (read-only access)."""
        return self._room

    # -- Public interface ----------------------------------------------------

    def get_measurements(self) -> Measurements:
        """Return current measurements without advancing time.

        Returns:
            A ``Measurements`` snapshot of the current state.
        """
        wp = self._weather.get(float(self._time_minutes))
        return Measurements(
            T_room=self._room.T_air,
            T_slab=self._room.T_slab,
            T_outdoor=wp.T_out,
            valve_pos=self._room.valve_position,
            hp_mode=self._hp_mode,
        )

    def step(self, actions: Actions) -> Measurements:
        """Apply actions, propagate physics, and return new measurements.

        The method follows the ZOH convention:
        1. Convert ``actions`` to actuator commands.
        2. Apply actuator commands to the room.
        3. Query weather at the current time.
        4. Propagate the RC model by one step.
        5. Advance the simulation clock.
        6. Return updated measurements.

        Args:
            actions: Controller commands for this time step.

        Returns:
            A ``Measurements`` snapshot after the step.
        """
        # Convert split mode to power
        if actions.split_mode == SplitMode.OFF:
            split_power = 0.0
        elif actions.split_mode == SplitMode.HEATING:
            split_power = self._split_power_w
        else:
            # COOLING: negative power
            split_power = -self._split_power_w

        # Apply actions to room actuators
        self._room.apply_actions(
            valve_position=actions.valve_position,
            split_power_w=split_power,
        )

        # Get weather at current time
        wp = self._weather.get(float(self._time_minutes))

        # Propagate physics
        self._room.step(wp, q_sol_w=0.0)

        # Advance clock
        self._time_minutes += self._dt_minutes

        return self.get_measurements()
