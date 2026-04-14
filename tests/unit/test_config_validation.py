"""Tests for configuration dataclass validation.

Validates RoomConfig, BuildingParams, ControllerConfig, and SimScenario
from ``pumpahead.config``.  All dataclasses are ``frozen=True`` with
``__post_init__`` validation raising ``ValueError`` for invalid data.
"""

import pytest

from pumpahead.config import (
    BuildingParams,
    ControllerConfig,
    CWUCycle,
    RoomConfig,
    SimScenario,
)
from pumpahead.model import RCParams
from pumpahead.solar import Orientation, WindowConfig
from pumpahead.weather import SyntheticWeather

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _siso_params() -> RCParams:
    """Standard 3R3C SISO (UFH-only) parameters."""
    return RCParams(
        C_air=60_000,
        C_slab=3_250_000,
        C_wall=1_500_000,
        R_sf=0.01,
        R_wi=0.02,
        R_wo=0.03,
        R_ve=0.03,
        R_ins=0.01,
        f_conv=0.6,
        f_rad=0.4,
        T_ground=10.0,
        has_split=False,
    )


def _mimo_params() -> RCParams:
    """Standard 3R3C MIMO (UFH + split) parameters."""
    return RCParams(
        C_air=60_000,
        C_slab=3_250_000,
        C_wall=1_500_000,
        R_sf=0.01,
        R_wi=0.02,
        R_wo=0.03,
        R_ve=0.03,
        R_ins=0.01,
        f_conv=0.6,
        f_rad=0.4,
        T_ground=10.0,
        has_split=True,
    )


def _make_room(
    name: str = "living_room",
    area_m2: float = 25.0,
    params: RCParams | None = None,
    **kwargs: object,
) -> RoomConfig:
    """Create a valid RoomConfig with sensible defaults."""
    if params is None:
        params = _siso_params()
    return RoomConfig(name=name, area_m2=area_m2, params=params, **kwargs)  # type: ignore[arg-type]


def _make_building(
    rooms: tuple[RoomConfig, ...] | None = None,
    hp_max_power_w: float = 12_000.0,
    latitude: float = 50.06,
    longitude: float = 19.94,
) -> BuildingParams:
    """Create a valid BuildingParams with sensible defaults."""
    if rooms is None:
        rooms = (_make_room(),)
    return BuildingParams(
        rooms=rooms,
        hp_max_power_w=hp_max_power_w,
        latitude=latitude,
        longitude=longitude,
    )


# ===========================================================================
# TestRoomConfig
# ===========================================================================


class TestRoomConfig:
    """Tests for RoomConfig validation."""

    def test_valid_siso_construction(self) -> None:
        """Valid SISO room is created without error."""
        room = _make_room()
        assert room.name == "living_room"
        assert room.area_m2 == 25.0
        assert room.has_split is False
        assert room.split_power_w == 0.0
        assert room.ufh_max_power_w == 5000.0
        assert room.ufh_loops == 1
        assert room.q_int_w == 0.0
        assert room.windows == ()

    def test_valid_mimo_construction(self) -> None:
        """Valid MIMO room with split is created without error."""
        room = _make_room(
            params=_mimo_params(),
            has_split=True,
            split_power_w=3500.0,
        )
        assert room.has_split is True
        assert room.split_power_w == 3500.0

    def test_frozen(self) -> None:
        """RoomConfig is immutable."""
        room = _make_room()
        with pytest.raises(AttributeError):
            room.name = "new_name"  # type: ignore[misc]

    def test_empty_name_raises(self) -> None:
        """Empty name string raises ValueError."""
        with pytest.raises(ValueError, match="non-empty string"):
            _make_room(name="")

    def test_whitespace_name_raises(self) -> None:
        """Whitespace-only name raises ValueError."""
        with pytest.raises(ValueError, match="non-empty string"):
            _make_room(name="   ")

    def test_area_zero_raises(self) -> None:
        """Zero area raises ValueError."""
        with pytest.raises(ValueError, match="area_m2 must be > 0"):
            _make_room(area_m2=0.0)

    def test_area_negative_raises(self) -> None:
        """Negative area raises ValueError."""
        with pytest.raises(ValueError, match="area_m2 must be > 0"):
            _make_room(area_m2=-10.0)

    def test_has_split_true_zero_power_raises(self) -> None:
        """has_split=True with zero split_power_w raises ValueError."""
        with pytest.raises(ValueError, match="split_power_w must be > 0"):
            _make_room(
                params=_mimo_params(),
                has_split=True,
                split_power_w=0.0,
            )

    def test_has_split_true_negative_power_raises(self) -> None:
        """has_split=True with negative split_power_w raises ValueError."""
        with pytest.raises(ValueError, match="split_power_w must be > 0"):
            _make_room(
                params=_mimo_params(),
                has_split=True,
                split_power_w=-100.0,
            )

    def test_has_split_false_nonzero_power_raises(self) -> None:
        """has_split=False with non-zero split_power_w raises ValueError."""
        with pytest.raises(ValueError, match="split_power_w must be 0.0"):
            _make_room(
                params=_siso_params(),
                has_split=False,
                split_power_w=1000.0,
            )

    def test_ufh_max_power_zero_raises(self) -> None:
        """Zero UFH power raises ValueError."""
        with pytest.raises(ValueError, match="ufh_max_power_w must be > 0"):
            _make_room(ufh_max_power_w=0.0)

    def test_ufh_max_power_negative_raises(self) -> None:
        """Negative UFH power raises ValueError."""
        with pytest.raises(ValueError, match="ufh_max_power_w must be > 0"):
            _make_room(ufh_max_power_w=-500.0)

    def test_ufh_loops_zero_raises(self) -> None:
        """Zero UFH loops raises ValueError."""
        with pytest.raises(ValueError, match="ufh_loops must be >= 1"):
            _make_room(ufh_loops=0)

    def test_ufh_loops_negative_raises(self) -> None:
        """Negative UFH loops raises ValueError."""
        with pytest.raises(ValueError, match="ufh_loops must be >= 1"):
            _make_room(ufh_loops=-1)

    def test_q_int_negative_raises(self) -> None:
        """Negative internal gains raises ValueError."""
        with pytest.raises(ValueError, match="q_int_w must be >= 0"):
            _make_room(q_int_w=-10.0)

    def test_q_int_zero_valid(self) -> None:
        """Zero internal gains is valid."""
        room = _make_room(q_int_w=0.0)
        assert room.q_int_w == 0.0

    def test_windows_tuple(self) -> None:
        """Windows are stored as a tuple."""
        south = WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)
        east = WindowConfig(Orientation.EAST, area_m2=2.0, g_value=0.5)
        room = _make_room(windows=(south, east))
        assert len(room.windows) == 2
        assert room.windows[0].orientation == Orientation.SOUTH

    def test_empty_windows_valid(self) -> None:
        """Empty windows tuple is valid (interior room)."""
        room = _make_room(windows=())
        assert room.windows == ()

    def test_params_has_split_mismatch_raises(self) -> None:
        """Mismatch between RoomConfig.has_split and RCParams.has_split raises."""
        with pytest.raises(ValueError, match="must match"):
            RoomConfig(
                name="bad_room",
                area_m2=20.0,
                params=_siso_params(),  # has_split=False
                has_split=True,
                split_power_w=2000.0,
            )

    def test_params_has_split_mismatch_reverse_raises(self) -> None:
        """Reverse mismatch (params MIMO, room SISO) also raises."""
        with pytest.raises(ValueError, match="must match"):
            RoomConfig(
                name="bad_room",
                area_m2=20.0,
                params=_mimo_params(),  # has_split=True
                has_split=False,
            )

    def test_custom_ufh_loops(self) -> None:
        """Custom ufh_loops value is accepted."""
        room = _make_room(ufh_loops=4)
        assert room.ufh_loops == 4

    def test_custom_q_int(self) -> None:
        """Custom q_int_w value is accepted."""
        room = _make_room(q_int_w=150.0)
        assert room.q_int_w == 150.0

    def test_auxiliary_type_default_is_split(self) -> None:
        """Default auxiliary_type is ``"split"``."""
        room = _make_room()
        assert room.auxiliary_type == "split"

    def test_auxiliary_type_heater_valid(self) -> None:
        """``"heater"`` is accepted when has_split=True and cooling=0.0."""
        room = RoomConfig(
            name="lazienka",
            area_m2=9.0,
            params=_mimo_params(),
            has_split=True,
            split_power_w=300.0,
            ufh_cooling_max_power_w=0.0,
            auxiliary_type="heater",
        )
        assert room.auxiliary_type == "heater"
        assert room.has_split is True
        assert room.ufh_cooling_max_power_w == 0.0

    def test_auxiliary_type_invalid_value_raises(self) -> None:
        """Unknown auxiliary_type string raises ValueError."""
        with pytest.raises(ValueError, match="auxiliary_type must be one of"):
            RoomConfig(
                name="bad_room",
                area_m2=20.0,
                params=_siso_params(),
                auxiliary_type="turbo",  # type: ignore[arg-type]
            )

    def test_auxiliary_type_heater_without_split_raises(self) -> None:
        """``"heater"`` without has_split=True raises ValueError."""
        with pytest.raises(ValueError, match="requires has_split=True"):
            RoomConfig(
                name="bad_room",
                area_m2=20.0,
                params=_siso_params(),
                has_split=False,
                auxiliary_type="heater",
            )

    def test_auxiliary_type_heater_with_cooling_raises(self) -> None:
        """``"heater"`` with nonzero cooling power raises ValueError."""
        with pytest.raises(ValueError, match="requires ufh_cooling_max_power_w=0.0"):
            RoomConfig(
                name="bad_room",
                area_m2=20.0,
                params=_mimo_params(),
                has_split=True,
                split_power_w=300.0,
                ufh_cooling_max_power_w=1000.0,
                auxiliary_type="heater",
            )


# ===========================================================================
# TestBuildingParams
# ===========================================================================


class TestBuildingParams:
    """Tests for BuildingParams validation."""

    def test_valid_construction(self) -> None:
        """Valid building is created without error."""
        building = _make_building()
        assert len(building.rooms) == 1
        assert building.hp_max_power_w == 12_000.0
        assert building.latitude == 50.06
        assert building.longitude == 19.94

    def test_frozen(self) -> None:
        """BuildingParams is immutable."""
        building = _make_building()
        with pytest.raises(AttributeError):
            building.latitude = 0.0  # type: ignore[misc]

    def test_empty_rooms_raises(self) -> None:
        """Empty rooms tuple raises ValueError."""
        with pytest.raises(ValueError, match="at least 1 room"):
            _make_building(rooms=())

    def test_hp_power_zero_raises(self) -> None:
        """Zero HP power raises ValueError."""
        with pytest.raises(ValueError, match="hp_max_power_w must be > 0"):
            _make_building(hp_max_power_w=0.0)

    def test_hp_power_negative_raises(self) -> None:
        """Negative HP power raises ValueError."""
        with pytest.raises(ValueError, match="hp_max_power_w must be > 0"):
            _make_building(hp_max_power_w=-5000.0)

    def test_latitude_below_range_raises(self) -> None:
        """Latitude < -90 raises ValueError."""
        with pytest.raises(ValueError, match="latitude must be in"):
            _make_building(latitude=-91.0)

    def test_latitude_above_range_raises(self) -> None:
        """Latitude > 90 raises ValueError."""
        with pytest.raises(ValueError, match="latitude must be in"):
            _make_building(latitude=91.0)

    def test_longitude_below_range_raises(self) -> None:
        """Longitude < -180 raises ValueError."""
        with pytest.raises(ValueError, match="longitude must be in"):
            _make_building(longitude=-181.0)

    def test_longitude_above_range_raises(self) -> None:
        """Longitude > 180 raises ValueError."""
        with pytest.raises(ValueError, match="longitude must be in"):
            _make_building(longitude=181.0)

    def test_latitude_boundary_valid(self) -> None:
        """Latitude at -90 and 90 boundaries is valid."""
        b1 = _make_building(latitude=-90.0)
        assert b1.latitude == -90.0
        b2 = _make_building(latitude=90.0)
        assert b2.latitude == 90.0

    def test_longitude_boundary_valid(self) -> None:
        """Longitude at -180 and 180 boundaries is valid."""
        b1 = _make_building(longitude=-180.0)
        assert b1.longitude == -180.0
        b2 = _make_building(longitude=180.0)
        assert b2.longitude == 180.0

    def test_duplicate_room_names_raises(self) -> None:
        """Duplicate room names raise ValueError."""
        r1 = _make_room(name="kitchen")
        r2 = _make_room(name="kitchen")
        with pytest.raises(ValueError, match="unique"):
            _make_building(rooms=(r1, r2))

    def test_multiple_rooms_unique_names(self) -> None:
        """Multiple rooms with unique names are valid."""
        r1 = _make_room(name="kitchen")
        r2 = _make_room(name="bedroom")
        r3 = _make_room(name="bathroom")
        building = _make_building(rooms=(r1, r2, r3))
        assert len(building.rooms) == 3

    def test_rooms_stored_as_tuple(self) -> None:
        """Rooms field is a tuple (not a list)."""
        building = _make_building()
        assert isinstance(building.rooms, tuple)


# ===========================================================================
# TestControllerConfig
# ===========================================================================


class TestControllerConfig:
    """Tests for ControllerConfig validation."""

    def test_defaults(self) -> None:
        """Default controller config has expected values."""
        cfg = ControllerConfig()
        assert cfg.kp == 5.0
        assert cfg.ki == 0.01
        assert cfg.kd == 0.0
        assert cfg.setpoint == 21.0
        assert cfg.deadband == 0.5
        assert cfg.valve_floor_pct == 10.0
        assert cfg.w_comfort == 1.0
        assert cfg.w_energy == 0.1
        assert cfg.w_smooth == 0.01

    def test_frozen(self) -> None:
        """ControllerConfig is immutable."""
        cfg = ControllerConfig()
        with pytest.raises(AttributeError):
            cfg.kp = 10.0  # type: ignore[misc]

    def test_negative_kp_raises(self) -> None:
        """Negative kp raises ValueError."""
        with pytest.raises(ValueError, match="kp must be >= 0"):
            ControllerConfig(kp=-1.0)

    def test_negative_ki_raises(self) -> None:
        """Negative ki raises ValueError."""
        with pytest.raises(ValueError, match="ki must be >= 0"):
            ControllerConfig(ki=-0.5)

    def test_negative_kd_raises(self) -> None:
        """Negative kd raises ValueError."""
        with pytest.raises(ValueError, match="kd must be >= 0"):
            ControllerConfig(kd=-0.1)

    def test_setpoint_below_range_raises(self) -> None:
        """Setpoint < 5 raises ValueError."""
        with pytest.raises(ValueError, match="setpoint must be in"):
            ControllerConfig(setpoint=4.0)

    def test_setpoint_above_range_raises(self) -> None:
        """Setpoint > 35 raises ValueError."""
        with pytest.raises(ValueError, match="setpoint must be in"):
            ControllerConfig(setpoint=36.0)

    def test_setpoint_boundary_valid(self) -> None:
        """Setpoint at boundaries 5 and 35 is valid."""
        c1 = ControllerConfig(setpoint=5.0)
        assert c1.setpoint == 5.0
        c2 = ControllerConfig(setpoint=35.0)
        assert c2.setpoint == 35.0

    def test_negative_deadband_raises(self) -> None:
        """Negative deadband raises ValueError."""
        with pytest.raises(ValueError, match="deadband must be >= 0"):
            ControllerConfig(deadband=-0.1)

    def test_zero_deadband_valid(self) -> None:
        """Zero deadband is valid."""
        cfg = ControllerConfig(deadband=0.0)
        assert cfg.deadband == 0.0

    def test_valve_floor_below_range_raises(self) -> None:
        """valve_floor_pct < 0 raises ValueError."""
        with pytest.raises(ValueError, match="valve_floor_pct must be in"):
            ControllerConfig(valve_floor_pct=-1.0)

    def test_valve_floor_above_range_raises(self) -> None:
        """valve_floor_pct > 100 raises ValueError."""
        with pytest.raises(ValueError, match="valve_floor_pct must be in"):
            ControllerConfig(valve_floor_pct=101.0)

    def test_valve_floor_boundary_valid(self) -> None:
        """valve_floor_pct at 0 and 100 is valid."""
        c1 = ControllerConfig(valve_floor_pct=0.0)
        assert c1.valve_floor_pct == 0.0
        c2 = ControllerConfig(valve_floor_pct=100.0)
        assert c2.valve_floor_pct == 100.0

    def test_negative_w_comfort_raises(self) -> None:
        """Negative w_comfort raises ValueError."""
        with pytest.raises(ValueError, match="w_comfort must be >= 0"):
            ControllerConfig(w_comfort=-0.1)

    def test_negative_w_energy_raises(self) -> None:
        """Negative w_energy raises ValueError."""
        with pytest.raises(ValueError, match="w_energy must be >= 0"):
            ControllerConfig(w_energy=-0.01)

    def test_negative_w_smooth_raises(self) -> None:
        """Negative w_smooth raises ValueError."""
        with pytest.raises(ValueError, match="w_smooth must be >= 0"):
            ControllerConfig(w_smooth=-0.001)

    def test_zero_gains_valid(self) -> None:
        """Zero PID gains are valid (pure feedforward)."""
        cfg = ControllerConfig(kp=0.0, ki=0.0, kd=0.0)
        assert cfg.kp == 0.0
        assert cfg.ki == 0.0
        assert cfg.kd == 0.0

    def test_zero_weights_valid(self) -> None:
        """Zero MPC weights are valid."""
        cfg = ControllerConfig(w_comfort=0.0, w_energy=0.0, w_smooth=0.0)
        assert cfg.w_comfort == 0.0


# ===========================================================================
# TestSimScenario
# ===========================================================================


class TestSimScenario:
    """Tests for SimScenario validation."""

    def _make_scenario(self, **overrides: object) -> SimScenario:
        """Create a valid SimScenario with sensible defaults."""
        defaults: dict[str, object] = {
            "name": "test_scenario",
            "building": _make_building(),
            "weather": SyntheticWeather.constant(T_out=-5.0),
            "controller": ControllerConfig(),
            "duration_minutes": 1440,
        }
        defaults.update(overrides)
        return SimScenario(**defaults)  # type: ignore[arg-type]

    def test_valid_construction(self) -> None:
        """Valid scenario is created without error."""
        scenario = self._make_scenario()
        assert scenario.name == "test_scenario"
        assert scenario.duration_minutes == 1440
        assert scenario.mode == "heating"
        assert scenario.dt_seconds == 60.0
        assert scenario.cwu_schedule == ()
        assert scenario.sensor_noise_std == 0.0

    def test_frozen(self) -> None:
        """SimScenario is immutable."""
        scenario = self._make_scenario()
        with pytest.raises(AttributeError):
            scenario.name = "other"  # type: ignore[misc]

    def test_empty_name_raises(self) -> None:
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="non-empty string"):
            self._make_scenario(name="")

    def test_whitespace_name_raises(self) -> None:
        """Whitespace-only name raises ValueError."""
        with pytest.raises(ValueError, match="non-empty string"):
            self._make_scenario(name="  \t  ")

    def test_duration_zero_raises(self) -> None:
        """Zero duration raises ValueError."""
        with pytest.raises(ValueError, match="duration_minutes must be > 0"):
            self._make_scenario(duration_minutes=0)

    def test_duration_negative_raises(self) -> None:
        """Negative duration raises ValueError."""
        with pytest.raises(ValueError, match="duration_minutes must be > 0"):
            self._make_scenario(duration_minutes=-60)

    def test_dt_zero_raises(self) -> None:
        """Zero dt_seconds raises ValueError."""
        with pytest.raises(ValueError, match="dt_seconds must be > 0"):
            self._make_scenario(dt_seconds=0.0)

    def test_dt_negative_raises(self) -> None:
        """Negative dt_seconds raises ValueError."""
        with pytest.raises(ValueError, match="dt_seconds must be > 0"):
            self._make_scenario(dt_seconds=-10.0)

    def test_noise_negative_raises(self) -> None:
        """Negative sensor_noise_std raises ValueError."""
        with pytest.raises(ValueError, match="sensor_noise_std must be >= 0"):
            self._make_scenario(sensor_noise_std=-0.1)

    def test_noise_zero_valid(self) -> None:
        """Zero sensor noise is valid."""
        scenario = self._make_scenario(sensor_noise_std=0.0)
        assert scenario.sensor_noise_std == 0.0

    def test_mode_heating_valid(self) -> None:
        """Mode 'heating' is valid."""
        scenario = self._make_scenario(mode="heating")
        assert scenario.mode == "heating"

    def test_mode_cooling_valid(self) -> None:
        """Mode 'cooling' is valid."""
        scenario = self._make_scenario(mode="cooling")
        assert scenario.mode == "cooling"

    def test_mode_auto_valid(self) -> None:
        """Mode 'auto' is valid."""
        scenario = self._make_scenario(mode="auto")
        assert scenario.mode == "auto"

    def test_cwu_schedule_tuple(self) -> None:
        """CWU schedule is stored as a tuple."""
        c1 = CWUCycle(start_minute=0, duration_minutes=30, interval_minutes=120)
        c2 = CWUCycle(start_minute=60, duration_minutes=20, interval_minutes=0)
        scenario = self._make_scenario(cwu_schedule=(c1, c2))
        assert len(scenario.cwu_schedule) == 2
        assert isinstance(scenario.cwu_schedule, tuple)

    def test_defaults(self) -> None:
        """Default optional values are correct."""
        scenario = self._make_scenario()
        assert scenario.mode == "heating"
        assert scenario.dt_seconds == 60.0
        assert scenario.cwu_schedule == ()
        assert scenario.sensor_noise_std == 0.0

    def test_custom_dt(self) -> None:
        """Custom dt_seconds is accepted."""
        scenario = self._make_scenario(dt_seconds=30.0)
        assert scenario.dt_seconds == 30.0

    def test_invalid_mode_raises(self) -> None:
        """Invalid mode string raises ValueError."""
        with pytest.raises(ValueError, match="mode must be one of"):
            self._make_scenario(mode="turbo")  # type: ignore[arg-type]

    def test_custom_noise(self) -> None:
        """Custom sensor_noise_std is accepted."""
        scenario = self._make_scenario(sensor_noise_std=0.5)
        assert scenario.sensor_noise_std == 0.5

    def test_room_overrides_default_empty(self) -> None:
        """Default room_overrides is an empty dict."""
        scenario = self._make_scenario()
        assert scenario.room_overrides == {}

    def test_room_overrides_valid(self) -> None:
        """Valid room_overrides referencing an existing room is accepted."""
        override = ControllerConfig(setpoint=24.0)
        scenario = self._make_scenario(room_overrides={"living_room": override})
        assert scenario.room_overrides["living_room"].setpoint == 24.0

    def test_room_overrides_unknown_room_raises(self) -> None:
        """Unknown room name in room_overrides raises ValueError."""
        override = ControllerConfig(setpoint=24.0)
        with pytest.raises(
            ValueError, match="room_overrides contains unknown room names"
        ):
            self._make_scenario(room_overrides={"ghost_room": override})
