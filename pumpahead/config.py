"""Configuration dataclasses for simulation parameters.

Provides frozen dataclasses for room, building, controller, and scenario
configuration.  All are immutable (``frozen=True``) with ``__post_init__``
validation that raises ``ValueError`` for invalid data.

Hierarchy:
    CWUCycle          — CWU (domestic hot water) interrupt schedule
    RoomConfig        — single room: RC params, windows, UFH/split config
    BuildingParams    — building: rooms, heat pump, location
    ControllerConfig  — PID + MPC tuning knobs
    SimScenario       — full simulation scenario (building + weather + control)

Units:
    All time fields: minutes (simulation convention).
    All powers: Watts.
    All temperatures: Celsius.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pumpahead.model import RCParams
from pumpahead.solar import WindowConfig

if TYPE_CHECKING:
    from pumpahead.weather import WeatherSource


@dataclass(frozen=True)
class CWUCycle:
    """Defines a repeating CWU (domestic hot water) interrupt schedule.

    During a CWU cycle the heat pump is dedicated to DHW production and
    floor heating loops receive no power (Q_floor=0).

    Attributes:
        start_minute: Simulation minute when the first cycle begins.
        duration_minutes: How long each cycle lasts [min].
        interval_minutes: Repetition period [min].  Set to 0 for a
            single (non-repeating) occurrence.
    """

    start_minute: int
    duration_minutes: int
    interval_minutes: int

    def __post_init__(self) -> None:
        """Validate CWU cycle parameters."""
        if self.start_minute < 0:
            raise ValueError(f"start_minute must be >= 0, got {self.start_minute}")
        if self.duration_minutes <= 0:
            raise ValueError(
                f"duration_minutes must be > 0, got {self.duration_minutes}"
            )
        if self.interval_minutes < 0:
            raise ValueError(
                f"interval_minutes must be >= 0, got {self.interval_minutes}"
            )
        if self.interval_minutes > 0 and self.interval_minutes <= self.duration_minutes:
            raise ValueError(
                f"interval_minutes ({self.interval_minutes}) must be > "
                f"duration_minutes ({self.duration_minutes}) when repeating"
            )


# ---------------------------------------------------------------------------
# RoomConfig — single room configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoomConfig:
    """Configuration for a single room in the building.

    Attributes:
        name: Human-readable room identifier (must be non-empty).
        area_m2: Floor area [m^2] (must be > 0).
        params: RC thermal parameters for this room.
        windows: Window configurations for solar gain calculation.
        has_split: Whether this room has a split/AC unit.
        split_power_w: Maximum split power [W] (> 0 when has_split=True,
            must be 0.0 when has_split=False).
        ufh_max_power_w: Maximum UFH power [W] (must be > 0).
        ufh_loops: Number of UFH loops (must be >= 1).
        q_int_w: Internal heat gains [W] (must be >= 0).
    """

    name: str
    area_m2: float
    params: RCParams
    windows: tuple[WindowConfig, ...] = ()
    has_split: bool = False
    split_power_w: float = 0.0
    ufh_max_power_w: float = 5000.0
    ufh_loops: int = 1
    q_int_w: float = 0.0

    def __post_init__(self) -> None:
        """Validate room configuration.

        Raises:
            ValueError: If any parameter is out of range or inconsistent.
        """
        if not self.name or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if self.area_m2 <= 0:
            msg = f"area_m2 must be > 0, got {self.area_m2}"
            raise ValueError(msg)
        if self.has_split and self.split_power_w <= 0:
            msg = (
                f"split_power_w must be > 0 when has_split=True, "
                f"got {self.split_power_w}"
            )
            raise ValueError(msg)
        if not self.has_split and self.split_power_w != 0.0:
            msg = (
                f"split_power_w must be 0.0 when has_split=False, "
                f"got {self.split_power_w}"
            )
            raise ValueError(msg)
        if self.ufh_max_power_w <= 0:
            msg = f"ufh_max_power_w must be > 0, got {self.ufh_max_power_w}"
            raise ValueError(msg)
        if self.ufh_loops < 1:
            msg = f"ufh_loops must be >= 1, got {self.ufh_loops}"
            raise ValueError(msg)
        if self.q_int_w < 0:
            msg = f"q_int_w must be >= 0, got {self.q_int_w}"
            raise ValueError(msg)
        if self.has_split != self.params.has_split:
            msg = (
                f"RoomConfig.has_split ({self.has_split}) must match "
                f"RCParams.has_split ({self.params.has_split})"
            )
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# BuildingParams — building-level configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildingParams:
    """Configuration for a building containing one or more rooms.

    Attributes:
        rooms: Tuple of room configurations (must contain >= 1 room).
        hp_max_power_w: Heat pump maximum power [W] (must be > 0).
        latitude: Geographic latitude [-90, 90] degrees.
        longitude: Geographic longitude [-180, 180] degrees.
    """

    rooms: tuple[RoomConfig, ...]
    hp_max_power_w: float
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        """Validate building parameters.

        Raises:
            ValueError: If any parameter is out of range or rooms are invalid.
        """
        if len(self.rooms) == 0:
            raise ValueError("rooms must contain at least 1 room")
        if self.hp_max_power_w <= 0:
            msg = f"hp_max_power_w must be > 0, got {self.hp_max_power_w}"
            raise ValueError(msg)
        if self.latitude < -90 or self.latitude > 90:
            msg = f"latitude must be in [-90, 90], got {self.latitude}"
            raise ValueError(msg)
        if self.longitude < -180 or self.longitude > 180:
            msg = f"longitude must be in [-180, 180], got {self.longitude}"
            raise ValueError(msg)
        names = [r.name for r in self.rooms]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            msg = f"room names must be unique, duplicates: {sorted(set(duplicates))}"
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# ControllerConfig — PID + MPC tuning parameters
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ControllerConfig:
    """Tuning parameters for the PID controller and MPC optimizer.

    Attributes:
        kp: Proportional gain (must be >= 0).
        ki: Integral gain (must be >= 0).
        kd: Derivative gain (must be >= 0).
        setpoint: Target room temperature [degC] (must be in [5, 35]).
        deadband: Deadband around setpoint [K] (must be >= 0).
        valve_floor_pct: Minimum valve position when heating [%] (in [0, 100]).
        w_comfort: MPC comfort weight (must be >= 0).
        w_energy: MPC energy weight (must be >= 0).
        w_smooth: MPC control smoothness weight (must be >= 0).
    """

    kp: float = 5.0
    ki: float = 0.01
    kd: float = 0.0
    setpoint: float = 21.0
    deadband: float = 0.5
    valve_floor_pct: float = 10.0
    w_comfort: float = 1.0
    w_energy: float = 0.1
    w_smooth: float = 0.01

    def __post_init__(self) -> None:
        """Validate controller parameters.

        Raises:
            ValueError: If any parameter is out of range.
        """
        if self.kp < 0:
            msg = f"kp must be >= 0, got {self.kp}"
            raise ValueError(msg)
        if self.ki < 0:
            msg = f"ki must be >= 0, got {self.ki}"
            raise ValueError(msg)
        if self.kd < 0:
            msg = f"kd must be >= 0, got {self.kd}"
            raise ValueError(msg)
        if self.setpoint < 5 or self.setpoint > 35:
            msg = f"setpoint must be in [5, 35], got {self.setpoint}"
            raise ValueError(msg)
        if self.deadband < 0:
            msg = f"deadband must be >= 0, got {self.deadband}"
            raise ValueError(msg)
        if self.valve_floor_pct < 0 or self.valve_floor_pct > 100:
            msg = f"valve_floor_pct must be in [0, 100], got {self.valve_floor_pct}"
            raise ValueError(msg)
        if self.w_comfort < 0:
            msg = f"w_comfort must be >= 0, got {self.w_comfort}"
            raise ValueError(msg)
        if self.w_energy < 0:
            msg = f"w_energy must be >= 0, got {self.w_energy}"
            raise ValueError(msg)
        if self.w_smooth < 0:
            msg = f"w_smooth must be >= 0, got {self.w_smooth}"
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# SimScenario — full simulation scenario
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimScenario:
    """Full simulation scenario composing building, weather, and controller.

    Attributes:
        name: Human-readable scenario identifier (must be non-empty).
        building: Building configuration with rooms and heat pump.
        weather: Weather data source (any ``WeatherSource`` implementation).
        controller: Controller tuning parameters.
        duration_minutes: Total simulation duration [min] (must be > 0).
        mode: Operating mode — ``"heating"``, ``"cooling"``, or ``"auto"``.
        dt_seconds: Simulation time step [s] (must be > 0).
        cwu_schedule: CWU interrupt schedule entries.
        sensor_noise_std: Sensor noise standard deviation [K] (must be >= 0).
        description: Human-readable description for reporting (default "").
    """

    name: str
    building: BuildingParams
    weather: WeatherSource
    controller: ControllerConfig
    duration_minutes: int
    mode: Literal["heating", "cooling", "auto"] = "heating"
    dt_seconds: float = 60.0
    cwu_schedule: tuple[CWUCycle, ...] = ()
    sensor_noise_std: float = 0.0
    description: str = ""

    def __post_init__(self) -> None:
        """Validate scenario parameters.

        Raises:
            ValueError: If any parameter is out of range.
        """
        if not self.name or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if not isinstance(self.description, str):
            msg = f"description must be a string, got {type(self.description).__name__}"
            raise ValueError(msg)
        if self.duration_minutes <= 0:
            msg = f"duration_minutes must be > 0, got {self.duration_minutes}"
            raise ValueError(msg)
        if self.dt_seconds <= 0:
            msg = f"dt_seconds must be > 0, got {self.dt_seconds}"
            raise ValueError(msg)
        if self.sensor_noise_std < 0:
            msg = f"sensor_noise_std must be >= 0, got {self.sensor_noise_std}"
            raise ValueError(msg)
        allowed_modes = ("heating", "cooling", "auto")
        if self.mode not in allowed_modes:
            msg = f"mode must be one of {allowed_modes}, got '{self.mode}'"
            raise ValueError(msg)
