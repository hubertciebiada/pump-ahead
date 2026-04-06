"""Per-timestep simulation recording with slicing and querying.

Provides ``SimRecord`` (frozen dataclass for a single timestep) and
``SimulationLog`` (list-backed container with room filtering, time-range
queries, and optional pandas DataFrame export).

Units follow the simulation convention:
    Temperatures: degC
    Powers: W
    Valve position: 0-100 %
    Time: minutes
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    import pandas as pd

from pumpahead.simulator import Actions, HeatPumpMode, Measurements, SplitMode
from pumpahead.weather import WeatherPoint

# ---------------------------------------------------------------------------
# SimRecord — immutable snapshot of one simulation timestep
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimRecord:
    """Immutable record of simulation state at a single timestep.

    Wraps the simulator-controller interface dataclasses (``Measurements``,
    ``Actions``) and weather conditions (``WeatherPoint``) together with the
    simulation time and room identifier.

    Convenience properties provide flat access to the most-used fields,
    avoiding verbose chains like ``record.measurements.T_room``.

    Attributes:
        t: Simulation time [minutes].
        measurements: Room and system state snapshot.
        actions: Controller commands for this step.
        weather: Weather conditions at this step.
        room_name: Room identifier (default ``""``).
    """

    t: int
    measurements: Measurements
    actions: Actions
    weather: WeatherPoint
    room_name: str = ""

    # -- Measurement properties -----------------------------------------------

    @property
    def T_room(self) -> float:
        """Air temperature [degC]."""
        return self.measurements.T_room

    @property
    def T_slab(self) -> float:
        """Slab temperature [degC]."""
        return self.measurements.T_slab

    @property
    def T_floor(self) -> float:
        """Floor temperature [degC] (alias for ``T_slab``)."""
        return self.measurements.T_slab

    @property
    def T_outdoor(self) -> float:
        """Outdoor temperature [degC] from measurements."""
        return self.measurements.T_outdoor

    @property
    def valve_pos(self) -> float:
        """Current valve position [0-100 %] from measurements."""
        return self.measurements.valve_pos

    @property
    def hp_mode(self) -> HeatPumpMode:
        """Current heat pump operating mode."""
        return self.measurements.hp_mode

    # -- Action properties ----------------------------------------------------

    @property
    def valve_position(self) -> float:
        """Desired valve position [0-100 %] from actions."""
        return self.actions.valve_position

    @property
    def split_mode(self) -> SplitMode:
        """Split/AC operating mode from actions."""
        return self.actions.split_mode

    @property
    def split_setpoint(self) -> float:
        """Split target temperature [degC] from actions."""
        return self.actions.split_setpoint

    # -- Weather properties ---------------------------------------------------

    @property
    def T_out(self) -> float:
        """Outdoor temperature [degC] from weather."""
        return self.weather.T_out

    @property
    def GHI(self) -> float:
        """Global Horizontal Irradiance [W/m^2]."""
        return self.weather.GHI

    @property
    def wind_speed(self) -> float:
        """Wind speed [m/s]."""
        return self.weather.wind_speed

    @property
    def humidity(self) -> float:
        """Relative humidity [%] (0-100)."""
        return self.weather.humidity


# ---------------------------------------------------------------------------
# SimulationLog — list-backed container with querying
# ---------------------------------------------------------------------------


class SimulationLog:
    """Ordered collection of ``SimRecord`` instances with filtering and export.

    Supports append, indexed access, slicing (returns a new ``SimulationLog``),
    iteration, room-name filtering, time-range filtering, and optional pandas
    DataFrame conversion.

    Typical usage::

        log = SimulationLog()
        for t in range(1440):
            meas = sim.step(actions)
            wp = weather.get(float(t))
            log.append_from_step(t, meas, actions, wp, room_name="salon")

        salon = log.get_room("salon").time_range(0, 720)
        df = salon.to_dataframe()
    """

    def __init__(self, records: list[SimRecord] | None = None) -> None:
        """Initialize with an optional list of pre-existing records.

        The provided list is copied to avoid external aliasing.

        Args:
            records: Initial records.  ``None`` creates an empty log.
        """
        self._records: list[SimRecord] = list(records) if records is not None else []

    # -- Mutation -------------------------------------------------------------

    def append(self, record: SimRecord) -> None:
        """Append a single ``SimRecord`` to the log.

        Args:
            record: The record to add.
        """
        self._records.append(record)

    def append_from_step(
        self,
        t: int,
        measurements: Measurements,
        actions: Actions,
        weather: WeatherPoint,
        room_name: str = "",
    ) -> None:
        """Construct a ``SimRecord`` from step components and append it.

        This is a convenience wrapper that avoids constructing a ``SimRecord``
        at the call site.

        Args:
            t: Simulation time [minutes].
            measurements: Room/system state snapshot.
            actions: Controller commands for this step.
            weather: Weather conditions at this step.
            room_name: Room identifier (default ``""``).
        """
        self._records.append(
            SimRecord(
                t=t,
                measurements=measurements,
                actions=actions,
                weather=weather,
                room_name=room_name,
            )
        )

    # -- Sized / Iterable / Container -----------------------------------------

    def __len__(self) -> int:
        """Return the number of records in the log."""
        return len(self._records)

    def __iter__(self) -> Iterator[SimRecord]:
        """Iterate over records in chronological order."""
        return iter(self._records)

    @overload
    def __getitem__(self, index: int) -> SimRecord: ...

    @overload
    def __getitem__(self, index: slice) -> SimulationLog: ...

    def __getitem__(self, index: int | slice) -> SimRecord | SimulationLog:
        """Return a single record or a sliced ``SimulationLog``.

        Args:
            index: Integer index or slice.

        Returns:
            ``SimRecord`` for an integer index, ``SimulationLog`` for a slice.

        Raises:
            IndexError: If the integer index is out of range.
        """
        if isinstance(index, slice):
            return SimulationLog(self._records[index])
        return self._records[index]

    # -- Query methods --------------------------------------------------------

    def get_room(self, name: str) -> SimulationLog:
        """Return a new log containing only records for *name*.

        Args:
            name: Room identifier to match.

        Returns:
            A ``SimulationLog`` with the filtered records.
        """
        return SimulationLog([r for r in self._records if r.room_name == name])

    def time_range(self, start: int, end: int) -> SimulationLog:
        """Return a new log containing records where ``start <= t <= end``.

        Args:
            start: Inclusive lower bound on simulation time [minutes].
            end: Inclusive upper bound on simulation time [minutes].

        Returns:
            A ``SimulationLog`` with the filtered records.
        """
        return SimulationLog(
            [r for r in self._records if start <= r.t <= end]
        )

    # -- Export ---------------------------------------------------------------

    def to_dataframe(self) -> pd.DataFrame:
        """Convert the log to a pandas ``DataFrame`` with flattened columns.

        Columns: ``t``, ``T_room``, ``T_slab``, ``T_outdoor``, ``valve_pos``,
        ``hp_mode``, ``valve_position``, ``split_mode``, ``split_setpoint``,
        ``T_out``, ``GHI``, ``wind_speed``, ``humidity``, ``room_name``.

        Enum fields (``hp_mode``, ``split_mode``) are stored as their string
        ``.value`` representation.

        Returns:
            A ``pandas.DataFrame`` with one row per record.

        Raises:
            ImportError: If pandas is not installed.
        """
        try:
            import pandas as pd
        except ImportError:
            msg = (
                "pandas is required for to_dataframe(). "
                "Install with: pip install pumpahead[viz]"
            )
            raise ImportError(msg) from None

        rows = [
            {
                "t": r.t,
                "T_room": r.T_room,
                "T_slab": r.T_slab,
                "T_outdoor": r.T_outdoor,
                "valve_pos": r.valve_pos,
                "hp_mode": r.hp_mode.value,
                "valve_position": r.valve_position,
                "split_mode": r.split_mode.value,
                "split_setpoint": r.split_setpoint,
                "T_out": r.T_out,
                "GHI": r.GHI,
                "wind_speed": r.wind_speed,
                "humidity": r.humidity,
                "room_name": r.room_name,
            }
            for r in self._records
        ]
        return pd.DataFrame.from_records(rows)
