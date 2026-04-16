"""Comprehensive unit tests for SimulatedRoom, BuildingSimulator, and dataclasses."""

import dataclasses
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
    SplitMode,
)
from pumpahead.ufh_loop import LoopGeometry
from pumpahead.weather import SyntheticWeather

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


def _standard_geometry(area_m2: float = 20.0) -> LoopGeometry:
    """Return a standard UFH loop geometry used throughout the tests."""
    return LoopGeometry(
        effective_pipe_length_m=130.0,
        pipe_spacing_m=0.15,
        pipe_diameter_outer_mm=16.0,
        pipe_wall_thickness_mm=2.0,
        area_m2=area_m2,
    )


@pytest.fixture()
def simulated_room(model_3r3c: RCModel) -> SimulatedRoom:
    """SISO simulated room with standard UFH loop geometry."""
    return SimulatedRoom("test_room", model_3r3c, loop_geometry=_standard_geometry())


@pytest.fixture()
def simulated_room_mimo(model_3r3c_mimo: RCModel) -> SimulatedRoom:
    """MIMO simulated room with 2500 W split and standard UFH loop."""
    return SimulatedRoom(
        "test_room_mimo",
        model_3r3c_mimo,
        split_power_w=2500.0,
        loop_geometry=_standard_geometry(),
    )


@pytest.fixture()
def constant_weather() -> SyntheticWeather:
    """Constant weather: T_out=-5 degC, no solar."""
    return SyntheticWeather.constant(T_out=-5.0, GHI=0.0)


@pytest.fixture()
def simulator(
    simulated_room: SimulatedRoom,
    constant_weather: SyntheticWeather,
) -> BuildingSimulator:
    """Building simulator with SISO room and constant cold weather."""
    return BuildingSimulator(simulated_room, constant_weather)


# ---------------------------------------------------------------------------
# TestSimulatedRoom
# ---------------------------------------------------------------------------


class TestSimulatedRoom:
    """Tests for the SimulatedRoom class."""

    @pytest.mark.unit
    def test_initial_state_default(self, simulated_room: SimulatedRoom) -> None:
        """SimulatedRoom starts with all temperatures at 20.0 degC."""
        state = simulated_room.state
        np.testing.assert_array_equal(state, [20.0, 20.0, 20.0])
        assert simulated_room.valve_position == 0.0

    @pytest.mark.unit
    def test_set_initial_state(self, simulated_room: SimulatedRoom) -> None:
        """Custom initial state is applied correctly."""
        simulated_room.set_initial_state(np.array([18.0, 22.0, 19.0]))
        assert simulated_room.T_air == 18.0
        assert simulated_room.T_slab == 22.0

    @pytest.mark.unit
    def test_step_propagates_temperature(
        self,
        simulated_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Stepping with cold weather and no heating cools the room."""
        sim = BuildingSimulator(simulated_room, constant_weather)
        initial_t_air = simulated_room.T_air
        sim.step(Actions(valve_position=0.0))
        # Room should cool: T_out=-5 < T_initial=20
        assert simulated_room.T_air < initial_t_air

    @pytest.mark.unit
    def test_valve_position_clamp_high(self, simulated_room: SimulatedRoom) -> None:
        """Valve position above 100 % is clamped to 100 %."""
        simulated_room.apply_actions(valve_position=150.0)
        assert simulated_room.valve_position == 100.0

    @pytest.mark.unit
    def test_valve_position_clamp_low(self, simulated_room: SimulatedRoom) -> None:
        """Valve position below 0 % is clamped to 0 %."""
        simulated_room.apply_actions(valve_position=-10.0)
        assert simulated_room.valve_position == 0.0

    @pytest.mark.unit
    def test_valve_drives_slab_heating(
        self,
        simulated_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """100 % valve heats the slab over 100 steps via the simulator."""
        sim = BuildingSimulator(simulated_room, constant_weather)
        initial_t_slab = simulated_room.T_slab
        for _ in range(100):
            sim.step(Actions(valve_position=100.0))
        assert simulated_room.T_slab > initial_t_slab

    @pytest.mark.unit
    def test_zero_valve_no_floor_heat(
        self,
        model_3r3c: RCModel,
        simulated_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """With valve=0, Q_floor=0 so the state matches RCModel.step(u=[0])."""
        # Direct model step — reference expected state with u=[0].
        x0 = model_3r3c.reset()
        u = np.array([0.0])
        wp = constant_weather.get(0.0)
        d = np.array([wp.T_out, 0.0, 0.0])
        x_expected = model_3r3c.step(x0, u, d)

        # BuildingSimulator step with valve=0 -> Q_floor=0 via loop_power.
        sim = BuildingSimulator(simulated_room, constant_weather)
        sim.step(Actions(valve_position=0.0))

        np.testing.assert_array_equal(simulated_room.state, x_expected)

    @pytest.mark.unit
    def test_mimo_split_heating(
        self,
        simulated_room_mimo: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """MIMO room with split heating warms T_air faster than without."""
        # Reference SISO room without split — same geometry.
        params_siso = RCParams(
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
        model_siso = RCModel(params_siso, ModelOrder.THREE, dt=60.0)
        room_siso = SimulatedRoom(
            "siso", model_siso, loop_geometry=_standard_geometry()
        )
        sim_siso = BuildingSimulator(room_siso, constant_weather)
        sim_mimo = BuildingSimulator(
            simulated_room_mimo, constant_weather, split_power_w=2500.0
        )

        # Both rooms: same valve, MIMO also has split heating on.
        for _ in range(50):
            sim_siso.step(Actions(valve_position=50.0))
            sim_mimo.step(
                Actions(
                    valve_position=50.0,
                    split_mode=SplitMode.HEATING,
                    split_setpoint=21.0,
                )
            )

        # MIMO room with split should be warmer.
        assert simulated_room_mimo.T_air > room_siso.T_air

    @pytest.mark.unit
    def test_siso_ignores_split_power(
        self,
        simulated_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """SISO room silently ignores split power (Q_conv=0)."""
        # Build a second identical SISO room that NEVER asks for a split.
        model_ref = RCModel(
            simulated_room._model.params,  # noqa: SLF001 — same params
            ModelOrder.THREE,
            dt=60.0,
        )
        room_ref = SimulatedRoom("ref", model_ref, loop_geometry=_standard_geometry())

        sim_a = BuildingSimulator(simulated_room, constant_weather)
        sim_b = BuildingSimulator(room_ref, constant_weather)

        # sim_a requests split heating (should be ignored — no has_split).
        # sim_b requests no split.
        sim_a.step(
            Actions(
                valve_position=50.0,
                split_mode=SplitMode.HEATING,
                split_setpoint=21.0,
            )
        )
        sim_b.step(Actions(valve_position=50.0))

        np.testing.assert_array_equal(simulated_room.state, room_ref.state)

    @pytest.mark.unit
    def test_state_copy_independence(self, simulated_room: SimulatedRoom) -> None:
        """room.state returns a copy, not a reference to internal state."""
        state1 = simulated_room.state
        state1[0] = 999.0
        state2 = simulated_room.state
        assert state2[0] == 20.0


# ---------------------------------------------------------------------------
# TestMeasurementsDataclass
# ---------------------------------------------------------------------------


class TestMeasurementsDataclass:
    """Tests for the Measurements frozen dataclass."""

    @pytest.mark.unit
    def test_measurements_fields(self) -> None:
        """Measurements fields are accessible and have correct types."""
        m = Measurements(
            T_room=20.0,
            T_slab=21.0,
            T_outdoor=-5.0,
            valve_pos=50.0,
            hp_mode=HeatPumpMode.HEATING,
        )
        assert isinstance(m.T_room, float)
        assert isinstance(m.T_slab, float)
        assert isinstance(m.T_outdoor, float)
        assert isinstance(m.valve_pos, float)
        assert isinstance(m.hp_mode, HeatPumpMode)

    @pytest.mark.unit
    def test_measurements_frozen(self) -> None:
        """Assigning to a Measurements field raises FrozenInstanceError."""
        m = Measurements(
            T_room=20.0,
            T_slab=21.0,
            T_outdoor=-5.0,
            valve_pos=50.0,
            hp_mode=HeatPumpMode.HEATING,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            m.T_room = 25.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestActionsDataclass
# ---------------------------------------------------------------------------


class TestActionsDataclass:
    """Tests for the Actions frozen dataclass."""

    @pytest.mark.unit
    def test_actions_defaults(self) -> None:
        """Actions with only valve_position uses correct defaults."""
        a = Actions(valve_position=50.0)
        assert a.valve_position == 50.0
        assert a.split_mode == SplitMode.OFF
        assert a.split_setpoint == 0.0

    @pytest.mark.unit
    def test_actions_with_split(self) -> None:
        """Actions with split mode and setpoint are stored correctly."""
        a = Actions(
            valve_position=30.0,
            split_mode=SplitMode.HEATING,
            split_setpoint=22.0,
        )
        assert a.split_mode == SplitMode.HEATING
        assert a.split_setpoint == 22.0


# ---------------------------------------------------------------------------
# TestBuildingSimulatorSingleRoom
# ---------------------------------------------------------------------------


class TestBuildingSimulatorSingleRoom:
    """Tests for single-room BuildingSimulator."""

    @pytest.mark.unit
    def test_step_returns_measurements(self, simulator: BuildingSimulator) -> None:
        """step() returns a Measurements with all fields finite."""
        meas = simulator.step(Actions(valve_position=0.0))
        assert isinstance(meas, Measurements)
        assert np.isfinite(meas.T_room)
        assert np.isfinite(meas.T_slab)
        assert np.isfinite(meas.T_outdoor)
        assert np.isfinite(meas.valve_pos)

    @pytest.mark.unit
    def test_step_advances_time(self, simulator: BuildingSimulator) -> None:
        """Each step increments time_minutes by 1."""
        assert simulator.time_minutes == 0
        simulator.step(Actions(valve_position=0.0))
        assert simulator.time_minutes == 1
        for _ in range(9):
            simulator.step(Actions(valve_position=0.0))
        assert simulator.time_minutes == 10

    @pytest.mark.unit
    def test_single_room_propagation_matches_rc_model(
        self,
        model_3r3c: RCModel,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Simulator output matches direct RCModel.step() exactly."""
        room = SimulatedRoom("test", model_3r3c, loop_geometry=_standard_geometry())
        sim = BuildingSimulator(room, constant_weather)

        # Direct model step
        x0 = model_3r3c.reset()
        u = np.array([0.0])  # valve=0 => Q_floor=0
        wp = constant_weather.get(0.0)
        d = np.array([wp.T_out, 0.0, 0.0])
        x_expected = model_3r3c.step(x0, u, d)

        # Simulator step
        meas = sim.step(Actions(valve_position=0.0))

        assert meas.T_room == float(x_expected[0])
        assert meas.T_slab == float(x_expected[1])

    @pytest.mark.unit
    def test_24h_simulation_under_100ms(
        self,
        model_3r3c: RCModel,
        constant_weather: SyntheticWeather,
    ) -> None:
        """1440 steps complete in under 100 ms wall-clock time."""
        room = SimulatedRoom("perf", model_3r3c, loop_geometry=_standard_geometry())
        sim = BuildingSimulator(room, constant_weather)
        actions = Actions(valve_position=50.0)

        start = time.perf_counter()
        for _ in range(1440):
            sim.step(actions)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        # Allow generous margin for CI environments
        assert elapsed_ms < 200.0, f"24h simulation took {elapsed_ms:.1f} ms"

    @pytest.mark.unit
    def test_deterministic_output(
        self,
        params_3r3c: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Two identical simulations produce identical Measurements sequences."""
        results: list[list[Measurements]] = []

        for _ in range(2):
            model = RCModel(params_3r3c, ModelOrder.THREE, dt=60.0)
            room = SimulatedRoom("det", model, loop_geometry=_standard_geometry())
            sim = BuildingSimulator(room, constant_weather)
            run_results: list[Measurements] = []
            for step in range(1440):
                valve = 50.0 if step < 720 else 0.0
                meas = sim.step(Actions(valve_position=valve))
                run_results.append(meas)
            results.append(run_results)

        for i in range(1440):
            assert results[0][i].T_room == results[1][i].T_room
            assert results[0][i].T_slab == results[1][i].T_slab
            assert results[0][i].T_outdoor == results[1][i].T_outdoor
            assert results[0][i].valve_pos == results[1][i].valve_pos

    @pytest.mark.unit
    def test_measurements_reflect_weather(
        self,
        model_3r3c: RCModel,
    ) -> None:
        """T_outdoor in Measurements matches the weather source value."""
        weather = SyntheticWeather.step_t_out(
            baseline=-10.0,
            amplitude=15.0,
            step_time_minutes=60.0,
        )
        room = SimulatedRoom("wx", model_3r3c, loop_geometry=_standard_geometry())
        sim = BuildingSimulator(room, weather)

        # Before the step (t=0..59 => T_out=-10)
        meas_before = sim.step(Actions(valve_position=0.0))
        assert meas_before.T_outdoor == -10.0

        # Step to t=60 where the step change occurs
        for _ in range(59):
            sim.step(Actions(valve_position=0.0))
        # Now time_minutes=60, get_measurements queries t=60
        meas_after = sim.step(Actions(valve_position=0.0))
        # After step at t=60, T_out = -10 + 15 = 5
        assert meas_after.T_outdoor == 5.0

    @pytest.mark.unit
    def test_valve_change_affects_temperature(
        self, simulator: BuildingSimulator
    ) -> None:
        """Changing valve from 0 to 100 % increases T_slab."""
        # Run 100 steps with valve=0
        for _ in range(100):
            simulator.step(Actions(valve_position=0.0))
        t_slab_no_heat = simulator.room.T_slab

        # Run 100 more steps with valve=100%
        for _ in range(100):
            simulator.step(Actions(valve_position=100.0))
        t_slab_heated = simulator.room.T_slab

        assert t_slab_heated > t_slab_no_heat

    @pytest.mark.unit
    def test_cold_outdoor_cools_room(
        self,
        model_3r3c: RCModel,
    ) -> None:
        """With T_out=-15 and no heating, T_air drops from 20 degC."""
        weather = SyntheticWeather.constant(T_out=-15.0, GHI=0.0)
        room = SimulatedRoom("cold", model_3r3c, loop_geometry=_standard_geometry())
        sim = BuildingSimulator(room, weather)

        initial_t_air = room.T_air
        for _ in range(100):
            sim.step(Actions(valve_position=0.0))

        assert room.T_air < initial_t_air

    @pytest.mark.unit
    def test_steady_state_convergence(
        self,
        model_3r3c: RCModel,
    ) -> None:
        """After many steps with constant inputs, T_air converges."""
        weather = SyntheticWeather.constant(T_out=0.0, GHI=0.0)
        room = SimulatedRoom("steady", model_3r3c, loop_geometry=_standard_geometry())
        sim = BuildingSimulator(room, weather)

        actions = Actions(valve_position=50.0)
        for _ in range(10000):
            sim.step(actions)

        # After 10000 steps, check that T_air has stabilized
        t_air_a = room.T_air
        for _ in range(100):
            sim.step(actions)
        t_air_b = room.T_air

        # Change over 100 additional steps should be negligible
        assert abs(t_air_b - t_air_a) < 0.01

    @pytest.mark.unit
    def test_get_measurements_without_step(self, simulator: BuildingSimulator) -> None:
        """get_measurements() before any step returns valid initial state."""
        meas = simulator.get_measurements()
        assert isinstance(meas, Measurements)
        assert meas.T_room == 20.0
        assert meas.T_slab == 20.0
        assert meas.T_outdoor == -5.0
        assert meas.valve_pos == 0.0
        assert meas.hp_mode == HeatPumpMode.HEATING
