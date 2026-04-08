"""MPC disturbance vector assembly for the prediction horizon.

Builds the disturbance matrix ``d[k]`` for the MPC state equation:

    x[k+1] = A*x[k] + B*u[k] + E*d[k]

The disturbance vector at each MPC step combines three sources:

1. ``T_out`` -- outdoor temperature from a :class:`WeatherSource`.
2. ``Q_sol`` -- solar gain through room windows via :class:`GTIModel`.
3. ``Q_int`` -- internal gains from an :class:`InternalGainProfile`.

For 3R3C models ``d[k] = [T_out, Q_sol, Q_int]`` (3 disturbances).
For 2R2C models ``d[k] = [T_out, Q_sol]`` (2 disturbances, Q_int omitted).

The output is a plain numpy array of shape ``(horizon_steps, n_disturbances)``
suitable for use as a ``cvxpy.Parameter`` in the MPC optimizer.  The cvxpy
import is deferred to keep this module importable without the solver installed.

Units:
    T_out: degC
    Q_sol: W
    Q_int: W
    time steps: seconds (dt_seconds), minutes (sim time)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
from numpy.typing import NDArray

from pumpahead.model import RCModel
from pumpahead.solar import EphemerisCalculator, WindowConfig
from pumpahead.solar_gti import GTIModel
from pumpahead.weather import WeatherSource

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

MPC_DT_SECONDS: int = 900
"""Default MPC time step in seconds (15 minutes)."""

MPC_HORIZON_STEPS: int = 96
"""Default MPC horizon length in steps (96 * 15 min = 24 h)."""


# ---------------------------------------------------------------------------
# InternalGainProfile -- configurable day/night, weekday/weekend Q_int
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InternalGainProfile:
    """Configurable internal heat gain profile (day/night, weekday/weekend).

    Internal gains model occupancy-related heat sources: people, appliances,
    lighting, cooking.  The profile switches between four values depending on
    time of day and day of week.

    Attributes:
        weekday_day_w: Internal gain during weekday daytime [W].
        weekday_night_w: Internal gain during weekday nighttime [W].
        weekend_day_w: Internal gain during weekend daytime [W].
        weekend_night_w: Internal gain during weekend nighttime [W].
        day_start_hour: Hour when daytime begins (inclusive), [0, 23].
        day_end_hour: Hour when daytime ends (exclusive), [1, 23].
            Must be strictly greater than ``day_start_hour``.
    """

    weekday_day_w: float
    weekday_night_w: float
    weekend_day_w: float
    weekend_night_w: float
    day_start_hour: int = 7
    day_end_hour: int = 22

    def __post_init__(self) -> None:
        """Validate profile parameters.

        Raises:
            ValueError: If any wattage is negative, hours are out of range,
                or ``day_start_hour >= day_end_hour``.
        """
        for field_name in (
            "weekday_day_w",
            "weekday_night_w",
            "weekend_day_w",
            "weekend_night_w",
        ):
            value = getattr(self, field_name)
            if value < 0:
                msg = f"{field_name} must be >= 0, got {value}"
                raise ValueError(msg)

        if not (0 <= self.day_start_hour <= 23):
            msg = f"day_start_hour must be in [0, 23], got {self.day_start_hour}"
            raise ValueError(msg)
        if not (0 <= self.day_end_hour <= 23):
            msg = f"day_end_hour must be in [0, 23], got {self.day_end_hour}"
            raise ValueError(msg)
        if self.day_start_hour >= self.day_end_hour:
            msg = (
                f"day_start_hour ({self.day_start_hour}) must be < "
                f"day_end_hour ({self.day_end_hour})"
            )
            raise ValueError(msg)

    def evaluate(self, dt: datetime) -> float:
        """Return Q_int [W] for the given datetime.

        Uses ``dt.weekday()`` (0=Monday ... 6=Sunday) to determine
        weekday/weekend, and ``dt.hour`` for day/night boundary.

        Args:
            dt: Absolute datetime (timezone-aware recommended).

        Returns:
            Internal gain in Watts.
        """
        is_weekend = dt.weekday() >= 5  # Saturday=5, Sunday=6
        is_day = self.day_start_hour <= dt.hour < self.day_end_hour

        if is_weekend:
            return self.weekend_day_w if is_day else self.weekend_night_w
        return self.weekday_day_w if is_day else self.weekday_night_w

    @classmethod
    def constant(cls, q_int_w: float) -> InternalGainProfile:
        """Create a profile with constant Q_int regardless of time.

        Args:
            q_int_w: Constant internal gain [W].

        Returns:
            An ``InternalGainProfile`` that always returns *q_int_w*.
        """
        return cls(
            weekday_day_w=q_int_w,
            weekday_night_w=q_int_w,
            weekend_day_w=q_int_w,
            weekend_night_w=q_int_w,
        )


# ---------------------------------------------------------------------------
# DisturbanceBuilder -- assembles d[k] over the MPC horizon
# ---------------------------------------------------------------------------


class DisturbanceBuilder:
    """Assembles the MPC disturbance matrix over the prediction horizon.

    For each MPC step *k* the builder:

    1. Queries the :class:`WeatherSource` for ``T_out`` and ``GHI``.
    2. Computes sun position via :class:`EphemerisCalculator`.
    3. Computes ``Q_sol`` via :class:`GTIModel` for the room's windows.
    4. Evaluates ``Q_int`` from the :class:`InternalGainProfile`.

    The result is a numpy array of shape ``(horizon_steps, n_disturbances)``
    ready for use in the MPC optimizer.

    Attributes:
        weather: Weather data source.
        gti_model: GTI solar gain model.
        ephemeris: Sun position calculator.
        windows: Room window configurations.
        gain_profile: Internal gain schedule.
        dt_seconds: MPC time step [s].
        horizon_steps: Number of MPC steps.
    """

    def __init__(
        self,
        weather: WeatherSource,
        gti_model: GTIModel,
        ephemeris: EphemerisCalculator,
        windows: Sequence[WindowConfig],
        gain_profile: InternalGainProfile,
        dt_seconds: int = MPC_DT_SECONDS,
        horizon_steps: int = MPC_HORIZON_STEPS,
    ) -> None:
        """Initialise the disturbance builder.

        Args:
            weather: Source for T_out and GHI at simulation time.
            gti_model: Model for computing Q_sol from GHI and sun position.
            ephemeris: Calculator for sun elevation and azimuth.
            windows: Tuple/list of window configurations for the room.
            gain_profile: Internal gain schedule (day/night, weekday/weekend).
            dt_seconds: MPC time step in seconds.  Default 900 (15 min).
            horizon_steps: Number of MPC prediction steps.  Default 96 (24 h).

        Raises:
            ValueError: If ``dt_seconds <= 0`` or ``horizon_steps <= 0``.
        """
        if dt_seconds <= 0:
            msg = f"dt_seconds must be positive, got {dt_seconds}"
            raise ValueError(msg)
        if horizon_steps <= 0:
            msg = f"horizon_steps must be positive, got {horizon_steps}"
            raise ValueError(msg)

        self.weather = weather
        self.gti_model = gti_model
        self.ephemeris = ephemeris
        self.windows = tuple(windows)
        self.gain_profile = gain_profile
        self.dt_seconds = dt_seconds
        self.horizon_steps = horizon_steps

    def build(
        self,
        start_time: datetime,
        sim_t0_minutes: float = 0.0,
        n_disturbances: int = 3,
    ) -> NDArray[np.float64]:
        """Build the disturbance matrix for the full MPC horizon.

        Args:
            start_time: Absolute datetime for the first MPC step.
                Timezone-aware (UTC) recommended for correct sun position.
            sim_t0_minutes: Simulation time (in minutes) corresponding to
                ``start_time``.  Used to query the :class:`WeatherSource`.
            n_disturbances: Number of disturbance columns.  3 for 3R3C
                ``[T_out, Q_sol, Q_int]``, 2 for 2R2C ``[T_out, Q_sol]``.

        Returns:
            Disturbance matrix of shape ``(horizon_steps, n_disturbances)``.

        Raises:
            ValueError: If ``n_disturbances`` is not 2 or 3.
        """
        if n_disturbances not in (2, 3):
            msg = f"n_disturbances must be 2 or 3, got {n_disturbances}"
            raise ValueError(msg)

        d = np.zeros((self.horizon_steps, n_disturbances), dtype=np.float64)

        for k in range(self.horizon_steps):
            t_minutes_k = sim_t0_minutes + k * self.dt_seconds / 60.0
            dt_k = start_time + timedelta(seconds=k * self.dt_seconds)

            # 1. Weather: T_out and GHI
            wp = self.weather.get(t_minutes_k)
            d[k, 0] = wp.T_out

            # 2. Solar gain: Q_sol via GTI model
            elevation, azimuth = self.ephemeris.sun_position(dt_k)
            day_of_year = dt_k.timetuple().tm_yday
            q_sol = self.gti_model.compute(
                wp.GHI, elevation, azimuth, self.windows, day_of_year
            )
            d[k, 1] = q_sol

            # 3. Internal gains (3R3C only)
            if n_disturbances == 3:
                d[k, 2] = self.gain_profile.evaluate(dt_k)

        return d

    def build_for_model(
        self,
        start_time: datetime,
        model: RCModel,
        sim_t0_minutes: float = 0.0,
    ) -> NDArray[np.float64]:
        """Build the disturbance matrix sized for a specific RC model.

        Convenience wrapper around :meth:`build` that reads
        ``model.n_disturbances`` to determine the number of columns.

        Args:
            start_time: Absolute datetime for the first MPC step.
            model: RC model whose ``n_disturbances`` determines shape.
            sim_t0_minutes: Simulation time (in minutes) for the first step.

        Returns:
            Disturbance matrix of shape
            ``(horizon_steps, model.n_disturbances)``.
        """
        return self.build(start_time, sim_t0_minutes, model.n_disturbances)

    def as_parameter(
        self,
        d: NDArray[np.float64],
    ) -> object:
        """Wrap a disturbance matrix in a ``cvxpy.Parameter``.

        The cvxpy import is deferred so this module can be imported
        without the QP solver installed.

        Args:
            d: Disturbance matrix of shape ``(horizon_steps, n_disturbances)``.

        Returns:
            A ``cvxpy.Parameter`` initialised with the values of *d*.
        """
        import cvxpy as cp

        param: object = cp.Parameter(shape=d.shape, value=d)
        return param
