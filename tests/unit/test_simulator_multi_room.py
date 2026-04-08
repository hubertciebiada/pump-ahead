"""Unit tests for multi-room BuildingSimulator with HP power distribution."""

import time

import numpy as np
import pytest

from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.simulator import (
    Actions,
    BuildingSimulator,
    HeatPumpMode,
    Measurements,
)
from pumpahead.weather import SyntheticWeather

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_room(
    name: str,
    params: RCParams,
    ufh_max_power_w: float = 5000.0,
) -> SimulatedRoom:
    """Create a SimulatedRoom with a 3R3C model at dt=60s."""
    model = RCModel(params, ModelOrder.THREE, dt=60.0)
    return SimulatedRoom(name, model, ufh_max_power_w=ufh_max_power_w)


def _make_rooms(
    n: int,
    params: RCParams,
    ufh_max_power_w: float = 5000.0,
) -> list[SimulatedRoom]:
    """Create *n* rooms with distinct names and identical RC parameters."""
    return [
        _make_room(f"room_{i}", params, ufh_max_power_w=ufh_max_power_w)
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def params() -> RCParams:
    """Standard 3R3C parameters (SISO)."""
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


@pytest.fixture()
def constant_weather() -> SyntheticWeather:
    """Constant weather: T_out=-5 degC, no solar."""
    return SyntheticWeather.constant(T_out=-5.0, GHI=0.0)


# ---------------------------------------------------------------------------
# TestHPPowerDistribution
# ---------------------------------------------------------------------------


class TestHPPowerDistribution:
    """Tests for the HP power distribution algorithm."""

    @pytest.mark.unit
    def test_equal_valves_equal_power(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Two rooms with equal valve and equal ufh_max get equal power."""
        rooms = _make_rooms(2, params, ufh_max_power_w=5000.0)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)

        actions = {
            "room_0": Actions(valve_position=50.0),
            "room_1": Actions(valve_position=50.0),
        }
        # Each room demands 50% * 5000 = 2500 W.  Total = 5000 <= 6000.
        allocated = sim._distribute_hp_power(actions)

        assert allocated["room_0"] == pytest.approx(2500.0)
        assert allocated["room_1"] == pytest.approx(2500.0)

    @pytest.mark.unit
    def test_unequal_valves_proportional_power(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """With constrained HP, rooms get power proportional to demand."""
        rooms = _make_rooms(2, params, ufh_max_power_w=5000.0)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=3000.0)

        actions = {
            "room_0": Actions(valve_position=100.0),  # demands 5000 W
            "room_1": Actions(valve_position=50.0),  # demands 2500 W
        }
        # Total demand = 7500, HP = 3000, scale = 3000/7500 = 0.4
        allocated = sim._distribute_hp_power(actions)

        assert allocated["room_0"] == pytest.approx(5000.0 * 0.4)
        assert allocated["room_1"] == pytest.approx(2500.0 * 0.4)

    @pytest.mark.unit
    def test_all_valves_zero_gives_zero_power(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """All valves at 0% results in zero power for all rooms."""
        rooms = _make_rooms(3, params)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)

        actions = {r.name: Actions(valve_position=0.0) for r in rooms}
        allocated = sim._distribute_hp_power(actions)

        for name in allocated:
            assert allocated[name] == 0.0

    @pytest.mark.unit
    def test_single_valve_open_gets_full_hp(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """One open valve with undersized HP gets the HP limit, not ufh_max."""
        rooms = _make_rooms(2, params, ufh_max_power_w=5000.0)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=3000.0)

        actions = {
            "room_0": Actions(valve_position=100.0),  # demands 5000 W
            "room_1": Actions(valve_position=0.0),  # demands 0 W
        }
        allocated = sim._distribute_hp_power(actions)

        assert allocated["room_0"] == pytest.approx(3000.0)
        assert allocated["room_1"] == 0.0

    @pytest.mark.unit
    def test_demand_within_capacity_no_scaling(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """When total demand is below HP capacity, each room gets full demand."""
        rooms = _make_rooms(2, params, ufh_max_power_w=2000.0)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)

        actions = {
            "room_0": Actions(valve_position=100.0),  # demands 2000 W
            "room_1": Actions(valve_position=50.0),  # demands 1000 W
        }
        allocated = sim._distribute_hp_power(actions)

        assert allocated["room_0"] == pytest.approx(2000.0)
        assert allocated["room_1"] == pytest.approx(1000.0)

    @pytest.mark.unit
    def test_energy_conservation(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Sum of allocated power equals HP capacity when demand exceeds it."""
        rooms = _make_rooms(4, params, ufh_max_power_w=5000.0)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)

        actions = {r.name: Actions(valve_position=100.0) for r in rooms}
        # Total demand = 4 * 5000 = 20000, HP = 6000
        allocated = sim._distribute_hp_power(actions)

        total_allocated = sum(allocated.values())
        assert total_allocated == pytest.approx(6000.0)

    @pytest.mark.unit
    def test_energy_conservation_under_capacity(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Sum of allocated power equals total demand when within capacity."""
        rooms = _make_rooms(2, params, ufh_max_power_w=1000.0)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)

        actions = {
            "room_0": Actions(valve_position=80.0),  # demands 800 W
            "room_1": Actions(valve_position=60.0),  # demands 600 W
        }
        allocated = sim._distribute_hp_power(actions)

        total_allocated = sum(allocated.values())
        assert total_allocated == pytest.approx(1400.0)

    @pytest.mark.unit
    def test_unlimited_hp_no_scaling(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """With hp_max_power_w=None (unlimited), each room gets full demand."""
        rooms = _make_rooms(4, params, ufh_max_power_w=5000.0)
        sim = BuildingSimulator(rooms, constant_weather)  # no hp_max_power_w

        actions = {r.name: Actions(valve_position=100.0) for r in rooms}
        allocated = sim._distribute_hp_power(actions)

        for name in allocated:
            assert allocated[name] == pytest.approx(5000.0)

    @pytest.mark.unit
    def test_rooms_with_different_ufh_max(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Rooms with different ufh_max_power_w get proportional shares."""
        room_a = _make_room("room_a", params, ufh_max_power_w=5000.0)
        room_b = _make_room("room_b", params, ufh_max_power_w=2000.0)
        sim = BuildingSimulator(
            [room_a, room_b], constant_weather, hp_max_power_w=3000.0
        )

        actions = {
            "room_a": Actions(valve_position=100.0),  # demands 5000 W
            "room_b": Actions(valve_position=100.0),  # demands 2000 W
        }
        # Total demand = 7000, scale = 3000/7000
        allocated = sim._distribute_hp_power(actions)

        scale = 3000.0 / 7000.0
        assert allocated["room_a"] == pytest.approx(5000.0 * scale)
        assert allocated["room_b"] == pytest.approx(2000.0 * scale)
        assert sum(allocated.values()) == pytest.approx(3000.0)


# ---------------------------------------------------------------------------
# TestBuildingSimulatorMultiRoom
# ---------------------------------------------------------------------------


class TestBuildingSimulatorMultiRoom:
    """Integration tests for multi-room BuildingSimulator."""

    @pytest.mark.unit
    def test_step_all_returns_dict(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """step_all() returns a dict keyed by room name with Measurements."""
        rooms = _make_rooms(3, params)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)
        actions = {r.name: Actions(valve_position=50.0) for r in rooms}

        result = sim.step_all(actions)

        assert isinstance(result, dict)
        assert set(result.keys()) == {"room_0", "room_1", "room_2"}
        for meas in result.values():
            assert isinstance(meas, Measurements)
            assert np.isfinite(meas.T_room)
            assert np.isfinite(meas.T_slab)

    @pytest.mark.unit
    def test_step_all_advances_time(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Each step_all() call increments time by 1 minute."""
        rooms = _make_rooms(2, params)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)
        actions = {r.name: Actions(valve_position=50.0) for r in rooms}

        assert sim.time_minutes == 0
        sim.step_all(actions)
        assert sim.time_minutes == 1
        for _ in range(9):
            sim.step_all(actions)
        assert sim.time_minutes == 10

    @pytest.mark.unit
    def test_mismatched_room_name_raises(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """step_all() raises ValueError for unknown room names."""
        rooms = _make_rooms(2, params)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)
        actions = {
            "room_0": Actions(valve_position=50.0),
            "bogus_room": Actions(valve_position=50.0),
        }

        with pytest.raises(ValueError, match="unknown rooms"):
            sim.step_all(actions)

    @pytest.mark.unit
    def test_missing_room_raises(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """step_all() raises ValueError when a room is missing from actions."""
        rooms = _make_rooms(2, params)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)
        actions = {"room_0": Actions(valve_position=50.0)}  # room_1 missing

        with pytest.raises(ValueError, match="missing rooms"):
            sim.step_all(actions)

    @pytest.mark.unit
    def test_eight_rooms_independent_temperatures(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """8 rooms with different valves produce different temperatures."""
        rooms = _make_rooms(8, params)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=40_000.0)

        # Give each room a different valve position (0% to 100%)
        actions = {
            f"room_{i}": Actions(valve_position=i * 100.0 / 7.0) for i in range(8)
        }

        for _ in range(200):
            sim.step_all(actions)

        temps = [sim.rooms[f"room_{i}"].T_air for i in range(8)]

        # Room with 0% valve should be coldest, 100% should be warmest
        assert temps[0] < temps[7]
        # Temperatures should be monotonically non-decreasing
        for i in range(7):
            assert temps[i] <= temps[i + 1] + 1e-9

    @pytest.mark.unit
    def test_closed_valve_zero_power(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """A room with valve=0% receives zero floor power and cools."""
        rooms = _make_rooms(2, params)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)

        initial_t_air = rooms[1].T_air
        actions = {
            "room_0": Actions(valve_position=100.0),
            "room_1": Actions(valve_position=0.0),
        }

        for _ in range(100):
            sim.step_all(actions)

        # Room 1 should cool (no heating, cold weather)
        assert rooms[1].T_air < initial_t_air
        # Room 0 should warm (getting heated)
        assert rooms[0].T_slab > 20.0

    @pytest.mark.unit
    def test_hp_power_conservation_in_step_all(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """After step_all, total distributed power = HP capacity (when exceeded)."""
        rooms = _make_rooms(4, params, ufh_max_power_w=5000.0)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)

        actions = {r.name: Actions(valve_position=100.0) for r in rooms}
        # Total demand = 20000 > 6000, so total allocated = 6000
        allocated = sim._distribute_hp_power(actions)

        assert sum(allocated.values()) == pytest.approx(6000.0)

    @pytest.mark.unit
    def test_backward_compat_single_room(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Single-room API (step) still works when using list constructor."""
        room = _make_room("single", params)
        sim = BuildingSimulator(room, constant_weather)

        meas = sim.step(Actions(valve_position=50.0))
        assert isinstance(meas, Measurements)
        assert sim.time_minutes == 1
        assert sim.room.name == "single"

    @pytest.mark.unit
    def test_rooms_property_returns_dict(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """The rooms property returns a dict keyed by room name."""
        rooms = _make_rooms(3, params)
        sim = BuildingSimulator(rooms, constant_weather)

        rooms_dict = sim.rooms
        assert isinstance(rooms_dict, dict)
        assert set(rooms_dict.keys()) == {"room_0", "room_1", "room_2"}

    @pytest.mark.unit
    def test_duplicate_room_names_raises(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Constructor raises ValueError for duplicate room names."""
        r1 = _make_room("dup", params)
        r2 = _make_room("dup", params)

        with pytest.raises(ValueError, match="duplicate"):
            BuildingSimulator([r1, r2], constant_weather)

    @pytest.mark.unit
    def test_empty_room_list_raises(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Constructor raises ValueError for empty room list."""
        with pytest.raises(ValueError, match="empty"):
            BuildingSimulator([], constant_weather)


# ---------------------------------------------------------------------------
# TestMultiRoomPerformance
# ---------------------------------------------------------------------------


class TestMultiRoomPerformance:
    """Performance tests for multi-room simulation."""

    @pytest.mark.unit
    def test_weekly_8_rooms_under_2_seconds(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """8-room weekly simulation (10080 steps) completes in < 5 seconds."""
        rooms = _make_rooms(8, params)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)
        actions = {r.name: Actions(valve_position=50.0) for r in rooms}

        start = time.perf_counter()
        for _ in range(10_080):
            sim.step_all(actions)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, (
            f"Weekly 8-room simulation took {elapsed:.2f}s (limit: 5.0s)"
        )


# ---------------------------------------------------------------------------
# TestMultiRoomMeasurements
# ---------------------------------------------------------------------------


class TestMultiRoomMeasurements:
    """Tests for get_all_measurements and per-room state."""

    @pytest.mark.unit
    def test_get_all_measurements_before_step(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """get_all_measurements() returns valid data before any step."""
        rooms = _make_rooms(3, params)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=6000.0)

        all_meas = sim.get_all_measurements()

        assert len(all_meas) == 3
        for _name, meas in all_meas.items():
            assert isinstance(meas, Measurements)
            assert meas.T_room == 20.0
            assert meas.T_slab == 20.0
            assert meas.T_outdoor == -5.0
            assert meas.valve_pos == 0.0
            assert meas.hp_mode == HeatPumpMode.HEATING

    @pytest.mark.unit
    def test_get_all_measurements_after_step_all(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """get_all_measurements() reflects state after step_all()."""
        rooms = _make_rooms(2, params)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=10_000.0)

        actions = {
            "room_0": Actions(valve_position=100.0),
            "room_1": Actions(valve_position=0.0),
        }
        sim.step_all(actions)

        all_meas = sim.get_all_measurements()

        # Room 0 was heated, room 1 was not
        # Both cooled due to cold weather, but room 0 got floor heat
        # so its T_slab should differ from room 1's
        assert all_meas["room_0"].T_slab != all_meas["room_1"].T_slab

    @pytest.mark.unit
    def test_per_room_valve_pos_in_measurements(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Measurements reflect the valve position set in actions."""
        rooms = _make_rooms(2, params)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=10_000.0)

        actions = {
            "room_0": Actions(valve_position=75.0),
            "room_1": Actions(valve_position=25.0),
        }
        result = sim.step_all(actions)

        assert result["room_0"].valve_pos == 75.0
        assert result["room_1"].valve_pos == 25.0

    @pytest.mark.unit
    def test_step_all_result_matches_get_all_measurements(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """step_all() return value matches get_all_measurements()."""
        rooms = _make_rooms(2, params)
        sim = BuildingSimulator(rooms, constant_weather, hp_max_power_w=10_000.0)

        actions = {r.name: Actions(valve_position=50.0) for r in rooms}
        step_result = sim.step_all(actions)
        get_result = sim.get_all_measurements()

        for name in step_result:
            assert step_result[name].T_room == get_result[name].T_room
            assert step_result[name].T_slab == get_result[name].T_slab
            assert step_result[name].valve_pos == get_result[name].valve_pos
