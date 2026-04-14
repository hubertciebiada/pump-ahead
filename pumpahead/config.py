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

from dataclasses import dataclass, field
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
        ufh_cooling_max_power_w: Maximum UFH cooling power [W]
            (must be >= 0).  Typically ~60 % of heating power due to
            asymmetric floor heat transfer.  Defaults to 0.0 (no floor
            cooling capability).
        ufh_loops: Number of UFH loops (must be >= 1).
        q_int_w: Internal heat gains [W] (must be >= 0).
        auxiliary_type: Type of the auxiliary heat source.  ``"split"``
            (default) models a reversible split/AC unit that can heat
            or cool depending on the HP mode.  ``"heater"`` models a
            heating-only source (e.g. an electric resistive heater) and
            is only active in heating mode — the controller forces
            ``SplitMode.OFF`` in cooling mode regardless of error.
            ``"heater"`` requires ``has_split=True`` (to reuse the
            ``SplitCoordinator`` pipeline) and
            ``ufh_cooling_max_power_w == 0.0`` (heater rooms must not
            cool via the floor either).
    """

    name: str
    area_m2: float
    params: RCParams
    windows: tuple[WindowConfig, ...] = ()
    has_split: bool = False
    split_power_w: float = 0.0
    ufh_max_power_w: float = 5000.0
    ufh_cooling_max_power_w: float = 0.0
    ufh_loops: int = 1
    q_int_w: float = 0.0
    auxiliary_type: Literal["split", "heater"] = "split"

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
        if self.ufh_cooling_max_power_w < 0:
            msg = (
                f"ufh_cooling_max_power_w must be >= 0, "
                f"got {self.ufh_cooling_max_power_w}"
            )
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
        allowed_aux = ("split", "heater")
        if self.auxiliary_type not in allowed_aux:
            msg = (
                f"auxiliary_type must be one of {allowed_aux}, "
                f"got '{self.auxiliary_type}'"
            )
            raise ValueError(msg)
        if self.auxiliary_type == "heater":
            if not self.has_split:
                msg = (
                    "auxiliary_type='heater' requires has_split=True "
                    "(heater rooms reuse the split coordinator pipeline)"
                )
                raise ValueError(msg)
            if self.ufh_cooling_max_power_w != 0.0:
                msg = (
                    f"auxiliary_type='heater' requires "
                    f"ufh_cooling_max_power_w=0.0, "
                    f"got {self.ufh_cooling_max_power_w}"
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
        split_deadband: Half-width of deadband where split does not
            activate [degC] (must be >= 0).
        split_setpoint_offset: Split aims at ``setpoint + offset`` in
            heating or ``setpoint - offset`` in cooling [degC]
            (must be >= 0).
        anti_takeover_threshold_minutes: Maximum split runtime per
            60-minute window before anti-takeover activates [min]
            (must be in [1, 60]).
        anti_takeover_valve_boost_pct: Valve floor boost applied during
            anti-takeover [%] (must be in (0, 100]).
        cwu_anti_panic_margin: Temperature margin below setpoint for
            anti-panic split blocking during CWU [degC] (must be > 0).
        cwu_pre_charge_lookahead_minutes: How many minutes before a
            predicted CWU cycle to start pre-charging the slab
            (must be in [0, 120]).
        cwu_pre_charge_valve_boost_pct: Additional valve floor percentage
            during pre-charge [%] (must be in [0, 50]).
        mode_switch_heating_threshold: Outdoor temperature below which
            the system switches to HEATING mode [degC].
        mode_switch_cooling_threshold: Outdoor temperature above which
            the system switches to COOLING mode [degC].  Must be >
            ``mode_switch_heating_threshold``.
        mode_switch_min_hold_minutes: Minimum time to hold the current
            mode before allowing a switch [min] (must be >= 0).
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
    split_deadband: float = 0.5
    split_setpoint_offset: float = 2.0
    anti_takeover_threshold_minutes: int = 30
    anti_takeover_valve_boost_pct: float = 50.0
    cwu_anti_panic_margin: float = 1.0
    cwu_pre_charge_lookahead_minutes: int = 30
    cwu_pre_charge_valve_boost_pct: float = 15.0
    mode_switch_heating_threshold: float = 18.0
    mode_switch_cooling_threshold: float = 22.0
    mode_switch_min_hold_minutes: int = 60

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
        if self.split_deadband < 0:
            msg = f"split_deadband must be >= 0, got {self.split_deadband}"
            raise ValueError(msg)
        if self.split_setpoint_offset < 0:
            msg = (
                f"split_setpoint_offset must be >= 0, got {self.split_setpoint_offset}"
            )
            raise ValueError(msg)
        if (
            self.anti_takeover_threshold_minutes < 1
            or self.anti_takeover_threshold_minutes > 60
        ):
            msg = (
                f"anti_takeover_threshold_minutes must be in [1, 60], "
                f"got {self.anti_takeover_threshold_minutes}"
            )
            raise ValueError(msg)
        if (
            self.anti_takeover_valve_boost_pct <= 0
            or self.anti_takeover_valve_boost_pct > 100
        ):
            msg = (
                f"anti_takeover_valve_boost_pct must be in (0, 100], "
                f"got {self.anti_takeover_valve_boost_pct}"
            )
            raise ValueError(msg)
        if self.cwu_anti_panic_margin <= 0:
            msg = f"cwu_anti_panic_margin must be > 0, got {self.cwu_anti_panic_margin}"
            raise ValueError(msg)
        if (
            self.cwu_pre_charge_lookahead_minutes < 0
            or self.cwu_pre_charge_lookahead_minutes > 120
        ):
            msg = (
                f"cwu_pre_charge_lookahead_minutes must be in [0, 120], "
                f"got {self.cwu_pre_charge_lookahead_minutes}"
            )
            raise ValueError(msg)
        if (
            self.cwu_pre_charge_valve_boost_pct < 0
            or self.cwu_pre_charge_valve_boost_pct > 50
        ):
            msg = (
                f"cwu_pre_charge_valve_boost_pct must be in [0, 50], "
                f"got {self.cwu_pre_charge_valve_boost_pct}"
            )
            raise ValueError(msg)
        if self.mode_switch_heating_threshold >= self.mode_switch_cooling_threshold:
            msg = (
                f"mode_switch_heating_threshold ({self.mode_switch_heating_threshold}) "
                f"must be < mode_switch_cooling_threshold "
                f"({self.mode_switch_cooling_threshold})"
            )
            raise ValueError(msg)
        if self.mode_switch_min_hold_minutes < 0:
            msg = (
                f"mode_switch_min_hold_minutes must be >= 0, "
                f"got {self.mode_switch_min_hold_minutes}"
            )
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
        room_overrides: Optional per-room ``ControllerConfig`` overrides.
            Keys must match room names in ``building.rooms``.  Rooms not
            listed use the scenario-level ``controller`` configuration.
            Empty dict by default.
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
    room_overrides: dict[str, ControllerConfig] = field(default_factory=dict)

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
        if self.room_overrides:
            known = {r.name for r in self.building.rooms}
            unknown = set(self.room_overrides.keys()) - known
            if unknown:
                msg = f"room_overrides contains unknown room names: {sorted(unknown)}"
                raise ValueError(msg)
            for room_name, override in self.room_overrides.items():
                if not isinstance(override, ControllerConfig):
                    msg = (
                        f"room_overrides[{room_name!r}] must be a "
                        f"ControllerConfig, got "
                        f"{type(override).__name__}"
                    )
                    raise ValueError(msg)
