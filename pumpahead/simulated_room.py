"""Simulated room wrapping an RC thermal model with actuator state.

Provides the ``SimulatedRoom`` class which combines an ``RCModel`` with
physical actuator state (valve position, split power) and converts
percentage-based valve commands into Watts for the underlying model.

This module is the bridge between controller-level abstractions (valve
positions, split on/off) and the mathematical model (Q_floor in Watts,
Q_conv in Watts).

Units:
    Temperatures: degC
    Powers: W
    Valve position: 0-100 %
    Time step: inherited from the RCModel (default 60 s)
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from pumpahead.model import RCModel
from pumpahead.weather import WeatherPoint


class SimulatedRoom:
    """A simulated room wrapping an RCModel with actuator state.

    SimulatedRoom owns the thermal state vector and translates actuator
    commands (valve position as 0-100 %, split power in Watts) into the
    control input vector expected by the underlying ``RCModel``.

    Typical usage::

        model = RCModel(params, ModelOrder.THREE, dt=60.0)
        room = SimulatedRoom("living_room", model, ufh_max_power_w=5000.0)
        room.apply_actions(valve_position=50.0)
        room.step(weather_point, q_sol_w=0.0)
        print(room.T_air)
    """

    def __init__(
        self,
        name: str,
        model: RCModel,
        ufh_max_power_w: float = 5000.0,
        split_power_w: float = 0.0,
        q_int_w: float = 0.0,
    ) -> None:
        """Initialize the simulated room.

        Args:
            name: Human-readable room name (e.g. "living_room").
            model: The RC thermal model for this room.
            ufh_max_power_w: Maximum UFH heat output at 100 % valve [W].
            split_power_w: Maximum split/AC power [W].  Zero if no split.
            q_int_w: Constant internal heat gains [W] (occupancy, appliances).
        """
        self._name = name
        self._model = model
        self._ufh_max_power_w = ufh_max_power_w
        self._split_power_w = split_power_w
        self._q_int_w = q_int_w

        # Thermal state: all nodes at 20 degC
        self._x: NDArray[np.float64] = model.reset()

        # Actuator state
        self._valve_position: float = 0.0
        self._split_power_request_w: float = 0.0

    # -- Properties ----------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the room name."""
        return self._name

    @property
    def state(self) -> NDArray[np.float64]:
        """Return a copy of the current thermal state vector."""
        return self._x.copy()

    @property
    def T_air(self) -> float:
        """Return the current air temperature [degC]."""
        return float(self._x[0])

    @property
    def T_slab(self) -> float:
        """Return the current slab temperature [degC]."""
        return float(self._x[1])

    @property
    def valve_position(self) -> float:
        """Return the current valve position [0-100 %]."""
        return self._valve_position

    @property
    def has_split(self) -> bool:
        """Return whether the room has a split/AC unit."""
        return self._model.params.has_split

    @property
    def ufh_max_power_w(self) -> float:
        """Return the maximum UFH heat output at 100 % valve [W]."""
        return self._ufh_max_power_w

    # -- State manipulation --------------------------------------------------

    def set_initial_state(self, x: NDArray[np.float64]) -> None:
        """Set the thermal state vector to custom initial values.

        Args:
            x: State vector, shape (n_states,).
        """
        self._x = np.array(x, dtype=np.float64)

    def apply_actions(
        self,
        valve_position: float,
        split_power_w: float = 0.0,
    ) -> None:
        """Apply actuator commands.

        Valve position is clamped to [0.0, 100.0].  If the room has no
        split unit, split power is silently forced to zero.

        Args:
            valve_position: Desired valve position [0-100 %].
            split_power_w: Desired split power [W].  Positive for heating,
                negative for cooling.
        """
        self._valve_position = max(0.0, min(100.0, valve_position))
        self._split_power_request_w = split_power_w
        if not self.has_split:
            self._split_power_request_w = 0.0

    # -- Physics step --------------------------------------------------------

    def step(self, weather: WeatherPoint, q_sol_w: float = 0.0) -> None:
        """Propagate the thermal state by one time step.

        Converts actuator state to control inputs and delegates to
        :meth:`step_with_power`.

        Args:
            weather: Weather conditions at the current time step.
            q_sol_w: Solar heat gain reaching the room [W].
        """
        q_floor = self._valve_position / 100.0 * self._ufh_max_power_w
        self.step_with_power(weather, q_floor_w=q_floor, q_sol_w=q_sol_w)

    def step_with_power(
        self,
        weather: WeatherPoint,
        q_floor_w: float,
        q_sol_w: float = 0.0,
    ) -> None:
        """Propagate the thermal state with a pre-computed floor power.

        This method is used by multi-room simulation where the HP power
        distribution logic computes ``q_floor_w`` externally instead of
        deriving it from ``valve_position * ufh_max_power_w``.

        The split power (``q_conv``) is still read from the internal
        actuator state set by :meth:`apply_actions`.

        Args:
            weather: Weather conditions at the current time step.
            q_floor_w: Floor heating power [W] (pre-computed).
            q_sol_w: Solar heat gain reaching the room [W].
        """
        # Split control input
        q_conv = max(
            -self._split_power_w,
            min(self._split_power_w, self._split_power_request_w),
        )

        u = (
            np.array([q_conv, q_floor_w])
            if self.has_split
            else np.array([q_floor_w])
        )

        # Disturbance vector
        n_dist = self._model.n_disturbances
        if n_dist == 3:
            # 3R3C: d = [T_out, Q_sol, Q_int]
            d = np.array([weather.T_out, q_sol_w, self._q_int_w])
        else:
            # 2R2C: d = [T_out, Q_sol]
            d = np.array([weather.T_out, q_sol_w])

        self._x = self._model.step(self._x, u, d)
