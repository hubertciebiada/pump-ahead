"""Integration tests for Epic #5 — Scenario parametrization verification gate.

Verifies end-to-end wiring between the three sub-issue modules:
    #32 Configuration dataclasses (config.py)
    #33 Building profiles (building_profiles.py)
    #34 Scenario library (scenarios.py)

Each test verifies that scenarios and building profiles can construct
a ``BuildingSimulator``, run steps without error, and produce finite
temperature outputs.  This is the integration verification gate proving
all three modules work together correctly.

All tests are fast (<1s total), deterministic, and use the
``@pytest.mark.unit`` marker.
"""

from __future__ import annotations

import math

import pytest

from pumpahead.building_profiles import BUILDING_PROFILES, hubert_real
from pumpahead.config import RoomConfig, SimScenario
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.scenarios import (
    PARAMETRIC_SWEEPS,
    SCENARIO_LIBRARY,
    cold_snap,
    cwu_heavy,
    insulation_sweep,
    screed_sweep,
    solar_overshoot,
    steady_state,
)
from pumpahead.sensor_noise import SensorNoise
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.simulator import Actions, BuildingSimulator
from pumpahead.weather import WeatherPoint

# ---------------------------------------------------------------------------
# Helper — construct a BuildingSimulator from a SimScenario
# ---------------------------------------------------------------------------


def _build_simulator_from_scenario(scenario: SimScenario) -> BuildingSimulator:
    """Bridge SimScenario -> BuildingSimulator for integration testing.

    Iterates over scenario.building.rooms, creates an RCModel and
    SimulatedRoom for each, then constructs a BuildingSimulator with
    the scenario's weather, HP capacity, CWU schedule, and sensor noise.

    Args:
        scenario: Fully configured simulation scenario.

    Returns:
        A ready-to-run ``BuildingSimulator``.
    """
    rooms: list[SimulatedRoom] = []
    for room_cfg in scenario.building.rooms:
        model = RCModel(room_cfg.params, ModelOrder.THREE, dt=scenario.dt_seconds)
        sim_room = SimulatedRoom(
            room_cfg.name,
            model,
            ufh_max_power_w=room_cfg.ufh_max_power_w,
            split_power_w=room_cfg.split_power_w,
            q_int_w=room_cfg.q_int_w,
        )
        rooms.append(sim_room)

    noise: SensorNoise | None = None
    if scenario.sensor_noise_std > 0:
        noise = SensorNoise(std=scenario.sensor_noise_std, seed=42)

    return BuildingSimulator(
        rooms,
        scenario.weather,
        hp_max_power_w=scenario.building.hp_max_power_w,
        cwu_schedule=list(scenario.cwu_schedule),
        sensor_noise=noise,
    )


# ---------------------------------------------------------------------------
# TestScenarioToSimulatorWiring
# ---------------------------------------------------------------------------


class TestScenarioToSimulatorWiring:
    """Verify every scenario can construct and run a BuildingSimulator."""

    @pytest.mark.unit
    @pytest.mark.parametrize("scenario_name", list(SCENARIO_LIBRARY.keys()))
    def test_every_library_scenario_constructs_simulator(
        self, scenario_name: str
    ) -> None:
        """SCENARIO_LIBRARY[name]() -> BuildingSimulator construction succeeds."""
        factory = SCENARIO_LIBRARY[scenario_name]
        scenario = factory()
        sim = _build_simulator_from_scenario(scenario)

        assert isinstance(sim, BuildingSimulator)
        assert len(sim.rooms) == len(scenario.building.rooms)

    @pytest.mark.unit
    @pytest.mark.parametrize("scenario_name", list(SCENARIO_LIBRARY.keys()))
    def test_every_library_scenario_runs_10_steps(self, scenario_name: str) -> None:
        """Every scenario runs 10 steps producing finite T_room and T_slab."""
        factory = SCENARIO_LIBRARY[scenario_name]
        scenario = factory()
        sim = _build_simulator_from_scenario(scenario)

        for _ in range(10):
            actions = {
                r.name: Actions(valve_position=50.0) for r in scenario.building.rooms
            }
            results = sim.step_all(actions)

            for name, meas in results.items():
                assert math.isfinite(meas.T_room), (
                    f"{scenario_name}/{name}: T_room={meas.T_room} is not finite"
                )
                assert math.isfinite(meas.T_slab), (
                    f"{scenario_name}/{name}: T_slab={meas.T_slab} is not finite"
                )

    @pytest.mark.unit
    @pytest.mark.parametrize("sweep_name", list(PARAMETRIC_SWEEPS.keys()))
    def test_every_sweep_scenario_constructs_and_runs(self, sweep_name: str) -> None:
        """Every sweep scenario constructs a simulator and runs 10 steps."""
        generator = PARAMETRIC_SWEEPS[sweep_name]
        scenarios = generator()
        assert len(scenarios) >= 2, (
            f"Sweep {sweep_name} should produce multiple scenarios"
        )

        for scenario in scenarios:
            sim = _build_simulator_from_scenario(scenario)
            assert isinstance(sim, BuildingSimulator)

            for _ in range(10):
                actions = {
                    r.name: Actions(valve_position=50.0)
                    for r in scenario.building.rooms
                }
                results = sim.step_all(actions)
                for name, meas in results.items():
                    assert math.isfinite(meas.T_room), (
                        f"{scenario.name}/{name}: T_room not finite"
                    )
                    assert math.isfinite(meas.T_slab), (
                        f"{scenario.name}/{name}: T_slab not finite"
                    )

    @pytest.mark.unit
    def test_cold_snap_multi_room_wiring(self) -> None:
        """cold_snap (hubert_real, 8 rooms) wires correctly to simulator."""
        scenario = cold_snap()
        sim = _build_simulator_from_scenario(scenario)

        # Verify 8 rooms
        assert len(sim.rooms) == 8

        # Verify room names match
        expected_names = {r.name for r in scenario.building.rooms}
        actual_names = set(sim.rooms.keys())
        assert actual_names == expected_names

        # Run 50 steps — all temps must be finite
        for _ in range(50):
            actions = {
                r.name: Actions(valve_position=50.0) for r in scenario.building.rooms
            }
            results = sim.step_all(actions)
            for name, meas in results.items():
                assert math.isfinite(meas.T_room), (
                    f"cold_snap/{name}: T_room not finite"
                )
                assert math.isfinite(meas.T_slab), (
                    f"cold_snap/{name}: T_slab not finite"
                )

    @pytest.mark.unit
    def test_cwu_heavy_schedule_propagates(self) -> None:
        """cwu_heavy CWU schedule propagates correctly into simulator.

        CWU cycle: start=0, duration=45, interval=180.
        At t=0 CWU should be active. At t=44 still active.
        At t=45 CWU should be inactive. At t=180 it should repeat.
        """
        scenario = cwu_heavy()
        sim = _build_simulator_from_scenario(scenario)

        # At t=0 CWU is active
        assert sim.is_cwu_active, "CWU should be active at t=0"

        # Run 44 steps (t goes from 0 to 44)
        for _ in range(44):
            actions = {
                r.name: Actions(valve_position=50.0) for r in scenario.building.rooms
            }
            sim.step_all(actions)

        # At t=44 CWU is still active (duration=45, so active at t=0..44)
        assert sim.is_cwu_active, "CWU should still be active at t=44"

        # One more step: t=45, CWU ends
        actions = {
            r.name: Actions(valve_position=50.0) for r in scenario.building.rooms
        }
        sim.step_all(actions)
        # Now time_minutes=45, which is >= duration, so CWU should be off
        assert not sim.is_cwu_active, f"CWU should be inactive at t={sim.time_minutes}"

        # Run until t=180 to verify repeat cycle
        steps_remaining = 180 - sim.time_minutes
        for _ in range(steps_remaining):
            actions = {
                r.name: Actions(valve_position=50.0) for r in scenario.building.rooms
            }
            sim.step_all(actions)

        # At t=180, CWU repeats (180 % 180 == 0 < 45)
        assert sim.is_cwu_active, f"CWU should repeat at t={sim.time_minutes}"


# ---------------------------------------------------------------------------
# TestSplitConsistencyAcrossModules
# ---------------------------------------------------------------------------


class TestSplitConsistencyAcrossModules:
    """Verify split/MIMO consistency from RoomConfig -> RCModel -> SimulatedRoom."""

    @pytest.mark.unit
    def test_hubert_real_split_rooms_produce_mimo_models(self) -> None:
        """Rooms with has_split=True produce 2-input MIMO RCModels."""
        building = hubert_real()
        for room_cfg in building.rooms:
            model = RCModel(room_cfg.params, ModelOrder.THREE, dt=60.0)
            if room_cfg.has_split:
                assert model.n_inputs == 2, (
                    f"{room_cfg.name}: has_split=True but n_inputs={model.n_inputs}"
                )
            else:
                assert model.n_inputs == 1, (
                    f"{room_cfg.name}: has_split=False but n_inputs={model.n_inputs}"
                )

    @pytest.mark.unit
    def test_split_power_flows_to_simulated_room(self) -> None:
        """SimulatedRoom.has_split reflects the RoomConfig.has_split flag."""
        building = hubert_real()
        for room_cfg in building.rooms:
            model = RCModel(room_cfg.params, ModelOrder.THREE, dt=60.0)
            sim_room = SimulatedRoom(
                room_cfg.name,
                model,
                ufh_max_power_w=room_cfg.ufh_max_power_w,
                split_power_w=room_cfg.split_power_w,
                q_int_w=room_cfg.q_int_w,
            )
            if room_cfg.has_split:
                assert sim_room.has_split, (
                    f"{room_cfg.name}: expected has_split=True in SimulatedRoom"
                )
            else:
                assert not sim_room.has_split, (
                    f"{room_cfg.name}: expected has_split=False in SimulatedRoom"
                )

    @pytest.mark.unit
    def test_sweep_hubert_salon_has_no_split(self) -> None:
        """Parametric sweep hubert_salon variants have no split (SISO)."""
        for sweep_fn in (insulation_sweep, screed_sweep):
            scenarios = sweep_fn()
            salon_scenarios = [s for s in scenarios if "hubert_salon" in s.name]
            assert len(salon_scenarios) == 1, (
                f"Expected 1 hubert_salon scenario, got {len(salon_scenarios)}"
            )
            scenario = salon_scenarios[0]
            assert len(scenario.building.rooms) == 1
            room_cfg = scenario.building.rooms[0]
            assert not room_cfg.has_split, (
                f"{scenario.name}: hubert_salon should have has_split=False"
            )
            model = RCModel(room_cfg.params, ModelOrder.THREE, dt=60.0)
            assert model.n_inputs == 1, (
                f"{scenario.name}: hubert_salon RCModel should be SISO (n_inputs=1)"
            )


# ---------------------------------------------------------------------------
# TestBuildingParamsSimulatorCompatibility
# ---------------------------------------------------------------------------


class TestBuildingParamsSimulatorCompatibility:
    """Verify BuildingParams produce valid RC models and simulators."""

    @pytest.mark.unit
    @pytest.mark.parametrize("profile_name", list(BUILDING_PROFILES.keys()))
    def test_all_profiles_produce_valid_rc_models(self, profile_name: str) -> None:
        """Every building profile produces valid 3R3C RCModels (n_states=3)."""
        factory = BUILDING_PROFILES[profile_name]
        building = factory()
        for room_cfg in building.rooms:
            model = RCModel(room_cfg.params, ModelOrder.THREE, dt=60.0)
            assert model.n_states == 3, (
                f"{profile_name}/{room_cfg.name}: expected 3 states"
            )

    @pytest.mark.unit
    def test_building_hp_power_constrains_simulator(self) -> None:
        """cold_snap simulator with hp_max_power_w=9000 runs without error."""
        scenario = cold_snap()
        assert scenario.building.hp_max_power_w == 9000.0
        sim = _build_simulator_from_scenario(scenario)

        # Run 10 steps with all 8 rooms at valve=100%
        for _ in range(10):
            actions = {
                r.name: Actions(valve_position=100.0) for r in scenario.building.rooms
            }
            results = sim.step_all(actions)
            for _name, meas in results.items():
                assert math.isfinite(meas.T_room)
                assert math.isfinite(meas.T_slab)

    @pytest.mark.unit
    def test_window_configs_present_in_scenario_rooms(self) -> None:
        """solar_overshoot (hubert_real) rooms have correct window configurations."""
        scenario = solar_overshoot()
        rooms_by_name = {r.name: r for r in scenario.building.rooms}

        # salon has 2 windows (south + west)
        salon = rooms_by_name["salon"]
        assert len(salon.windows) == 2, (
            f"salon should have 2 windows, got {len(salon.windows)}"
        )

        # garderoba has no windows
        garderoba = rooms_by_name["garderoba"]
        assert len(garderoba.windows) == 0, (
            f"garderoba should have 0 windows, got {len(garderoba.windows)}"
        )

        # lazienka has 1 window (north, small)
        lazienka = rooms_by_name["lazienka"]
        assert len(lazienka.windows) == 1, (
            f"lazienka should have 1 window, got {len(lazienka.windows)}"
        )


# ---------------------------------------------------------------------------
# TestScenarioDeterminism
# ---------------------------------------------------------------------------


class TestScenarioDeterminism:
    """Verify simulator output is deterministic for the same scenario."""

    @pytest.mark.unit
    def test_simulator_output_deterministic_for_scenario(self) -> None:
        """Two simulators from steady_state() produce identical output."""
        scenario = steady_state()
        sim_a = _build_simulator_from_scenario(scenario)
        sim_b = _build_simulator_from_scenario(scenario)

        for step in range(50):
            actions = {
                r.name: Actions(valve_position=50.0) for r in scenario.building.rooms
            }
            results_a = sim_a.step_all(actions)
            results_b = sim_b.step_all(actions)

            for name in results_a:
                assert results_a[name].T_room == results_b[name].T_room, (
                    f"Step {step}, {name}: T_room diverged"
                )
                assert results_a[name].T_slab == results_b[name].T_slab, (
                    f"Step {step}, {name}: T_slab diverged"
                )

    @pytest.mark.unit
    def test_sweep_scenario_output_deterministic(self) -> None:
        """Two simulators from insulation_sweep()[0] produce identical output."""
        scenarios = insulation_sweep()
        scenario = scenarios[0]

        sim_a = _build_simulator_from_scenario(scenario)
        sim_b = _build_simulator_from_scenario(scenario)

        for step in range(20):
            actions = {
                r.name: Actions(valve_position=50.0) for r in scenario.building.rooms
            }
            results_a = sim_a.step_all(actions)
            results_b = sim_b.step_all(actions)

            for name in results_a:
                assert results_a[name].T_room == results_b[name].T_room, (
                    f"Step {step}, {name}: T_room diverged"
                )
                assert results_a[name].T_slab == results_b[name].T_slab, (
                    f"Step {step}, {name}: T_slab diverged"
                )


# ---------------------------------------------------------------------------
# TestAcceptanceCriteriaVerification
# ---------------------------------------------------------------------------


class TestAcceptanceCriteriaVerification:
    """Re-verify all Epic #5 acceptance criteria."""

    @pytest.mark.unit
    def test_hubert_real_has_8_rooms_with_realistic_params(self) -> None:
        """hubert_real() has 8 rooms, 13 UFH loops, 5 splits, correct location."""
        building = hubert_real()
        assert len(building.rooms) == 8

        total_loops = sum(r.ufh_loops for r in building.rooms)
        assert total_loops == 13

        split_rooms = [r for r in building.rooms if r.has_split]
        assert len(split_rooms) == 5

        assert building.latitude == pytest.approx(50.69)
        assert building.longitude == pytest.approx(17.38)

    @pytest.mark.unit
    def test_at_least_10_total_scenarios(self) -> None:
        """SCENARIO_LIBRARY + PARAMETRIC_SWEEPS produce >= 10 total scenarios."""
        library_count = len(SCENARIO_LIBRARY)
        sweep_count = sum(len(gen()) for gen in PARAMETRIC_SWEEPS.values())
        total = library_count + sweep_count
        assert total >= 10, (
            f"Expected >= 10 scenarios, got {total} "
            f"(library={library_count}, sweeps={sweep_count})"
        )

    @pytest.mark.unit
    def test_validation_raises_on_invalid_room_config(self) -> None:
        """RoomConfig with has_split=True and split_power_w=0 raises ValueError."""
        with pytest.raises(ValueError, match="split_power_w must be > 0"):
            RoomConfig(
                name="bad_room",
                area_m2=20.0,
                params=RCParams(
                    C_air=60_000,
                    C_slab=3_250_000,
                    C_wall=1_500_000,
                    R_sf=0.01,
                    R_wi=0.02,
                    R_wo=0.03,
                    R_ve=0.03,
                    R_ins=0.01,
                    has_split=True,
                ),
                has_split=True,
                split_power_w=0.0,
            )

    @pytest.mark.unit
    @pytest.mark.parametrize("scenario_name", list(SCENARIO_LIBRARY.keys()))
    def test_all_scenarios_deterministic_full_check(self, scenario_name: str) -> None:
        """Every scenario in SCENARIO_LIBRARY is deterministic over 10 steps."""
        factory = SCENARIO_LIBRARY[scenario_name]
        scenario_a = factory()
        scenario_b = factory()
        sim_a = _build_simulator_from_scenario(scenario_a)
        sim_b = _build_simulator_from_scenario(scenario_b)

        for step in range(10):
            actions_a = {
                r.name: Actions(valve_position=50.0) for r in scenario_a.building.rooms
            }
            actions_b = {
                r.name: Actions(valve_position=50.0) for r in scenario_b.building.rooms
            }
            results_a = sim_a.step_all(actions_a)
            results_b = sim_b.step_all(actions_b)

            for name in results_a:
                assert results_a[name].T_room == results_b[name].T_room, (
                    f"{scenario_name} step {step} {name}: T_room diverged"
                )
                assert results_a[name].T_slab == results_b[name].T_slab, (
                    f"{scenario_name} step {step} {name}: T_slab diverged"
                )

    @pytest.mark.unit
    @pytest.mark.parametrize("scenario_name", list(SCENARIO_LIBRARY.keys()))
    def test_weather_compatible_with_building_simulator(
        self, scenario_name: str
    ) -> None:
        """Every scenario's weather.get(0.0) returns a valid WeatherPoint."""
        factory = SCENARIO_LIBRARY[scenario_name]
        scenario = factory()
        wp = scenario.weather.get(0.0)

        assert isinstance(wp, WeatherPoint)
        assert math.isfinite(wp.T_out)
        assert math.isfinite(wp.GHI)
        assert math.isfinite(wp.wind_speed)
        assert math.isfinite(wp.humidity)
