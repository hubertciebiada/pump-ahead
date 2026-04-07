"""Integration tests for Epic #4 (BuildingSimulator full pipeline).

Exercises the complete simulator pipeline end-to-end: multi-room simulation
with CWU interrupts, sensor noise, HP capacity sharing, and SimulationLog
recording -- all wired together.

These tests verify that the fixes for two architectural-drift bugs work
correctly:
1. ``get_all_measurements()`` now applies sensor noise in multi-room mode.
2. ``step_all()`` now respects CWU interrupts in multi-room mode.

They also verify that CWU interrupts do NOT affect split operation (only
Q_floor is zeroed).
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from pumpahead.config import CWUCycle
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.sensor_noise import SensorNoise
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.simulation_log import SimulationLog
from pumpahead.simulator import (
    Actions,
    BuildingSimulator,
    Measurements,
    SplitMode,
)
from pumpahead.weather import SyntheticWeather

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_room(
    name: str,
    params: RCParams,
    ufh_max_power_w: float = 5000.0,
    split_power_w: float = 0.0,
) -> SimulatedRoom:
    """Create a SimulatedRoom with a 3R3C model at dt=60s."""
    model = RCModel(params, ModelOrder.THREE, dt=60.0)
    return SimulatedRoom(
        name, model, ufh_max_power_w=ufh_max_power_w, split_power_w=split_power_w
    )


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
def params_mimo() -> RCParams:
    """Standard 3R3C parameters (MIMO, UFH + split)."""
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


@pytest.fixture()
def constant_weather() -> SyntheticWeather:
    """Constant weather: T_out=-5 degC, no solar."""
    return SyntheticWeather.constant(T_out=-5.0, GHI=0.0)


# ---------------------------------------------------------------------------
# TestFullPipelineIntegration
# ---------------------------------------------------------------------------


class TestFullPipelineIntegration:
    """End-to-end integration tests for the BuildingSimulator pipeline."""

    @pytest.mark.unit
    def test_full_pipeline_8_rooms_with_logging(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """8 rooms, 1440 steps with CWU, noise, HP capacity, SimulationLog.

        Verifies that all features work together: CWU interrupts, sensor
        noise, HP capacity sharing, and SimulationLog recording. Asserts
        log record count, per-room filtering, finite temps, and that
        heated rooms are warmer than unheated ones.
        """
        rooms = _make_rooms(8, params, ufh_max_power_w=3000.0)
        noise = SensorNoise(std=0.1, seed=42)
        cwu_cycle = CWUCycle(start_minute=0, duration_minutes=30, interval_minutes=480)
        sim = BuildingSimulator(
            rooms,
            constant_weather,
            hp_max_power_w=12_000.0,
            cwu_schedule=[cwu_cycle],
            sensor_noise=noise,
        )

        log = SimulationLog()
        n_steps = 1440  # 24 hours

        for t in range(n_steps):
            # Different valves for different rooms
            actions = {
                f"room_{i}": Actions(valve_position=i * 100.0 / 7.0)
                for i in range(8)
            }
            results = sim.step_all(actions)

            wp = constant_weather.get(float(t))
            for name, meas in results.items():
                log.append_from_step(
                    t=t + 1,
                    measurements=meas,
                    actions=actions[name],
                    weather=wp,
                    room_name=name,
                )

        # Log records: 8 rooms * 1440 steps = 11520
        assert len(log) == 8 * n_steps

        # Per-room filtering: each room has exactly 1440 records
        for i in range(8):
            room_log = log.get_room(f"room_{i}")
            assert len(room_log) == n_steps

        # All temperatures must be finite (no NaN/inf)
        for record in log:
            assert np.isfinite(record.T_room), (
                f"T_room is not finite at t={record.t}, room={record.room_name}"
            )
            assert np.isfinite(record.T_slab), (
                f"T_slab is not finite at t={record.t}, room={record.room_name}"
            )

        # Valve-temperature correlation: room_0 (valve=0%) should be
        # colder than room_7 (valve=100%) after 24 hours
        # Use underlying physics state (not noisy measurement) to check trend
        assert sim.rooms["room_0"].T_air < sim.rooms["room_7"].T_air

    @pytest.mark.unit
    def test_weekly_simulation_all_features(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """4 rooms, 10080 steps (7 days) with CWU+noise+HP, <2s.

        Verifies performance, log integrity, and finite temperatures
        across a full-week simulation with all features enabled.
        """
        rooms = _make_rooms(4, params, ufh_max_power_w=4000.0)
        noise = SensorNoise(std=0.05, seed=99)
        cwu_cycle = CWUCycle(start_minute=0, duration_minutes=20, interval_minutes=360)
        sim = BuildingSimulator(
            rooms,
            constant_weather,
            hp_max_power_w=10_000.0,
            cwu_schedule=[cwu_cycle],
            sensor_noise=noise,
        )

        log = SimulationLog()
        n_steps = 10_080  # 7 days

        start = time.perf_counter()
        for t in range(n_steps):
            actions = {r.name: Actions(valve_position=50.0) for r in rooms}
            results = sim.step_all(actions)

            wp = constant_weather.get(float(t))
            for name, meas in results.items():
                log.append_from_step(
                    t=t + 1,
                    measurements=meas,
                    actions=actions[name],
                    weather=wp,
                    room_name=name,
                )
        elapsed = time.perf_counter() - start

        # Performance: must complete in < 2 seconds
        assert elapsed < 2.0, (
            f"Weekly 4-room simulation took {elapsed:.2f}s (limit: 2.0s)"
        )

        # Log integrity
        assert len(log) == 4 * n_steps

        for i in range(4):
            room_log = log.get_room(f"room_{i}")
            assert len(room_log) == n_steps

        # All temperatures must be finite
        for record in log:
            assert np.isfinite(record.T_room)
            assert np.isfinite(record.T_slab)


# ---------------------------------------------------------------------------
# TestCWUInterruptMultiRoom
# ---------------------------------------------------------------------------


class TestCWUInterruptMultiRoom:
    """Tests for CWU interrupt behavior in multi-room step_all()."""

    @pytest.mark.unit
    def test_cwu_interrupt_in_multi_room(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """CWU regression: T_slab matches zero-valve reference in multi-room.

        During a CWU cycle, step_all() must force valve_position=0 for
        all rooms.  The resulting T_slab should match a reference
        simulation run with valve=0 and no CWU schedule.
        """
        # CWU simulator: valve=100 but CWU active for 30 steps
        rooms_cwu = _make_rooms(2, params, ufh_max_power_w=5000.0)
        cwu_cycle = CWUCycle(start_minute=0, duration_minutes=30, interval_minutes=0)
        sim_cwu = BuildingSimulator(
            rooms_cwu,
            constant_weather,
            hp_max_power_w=10_000.0,
            cwu_schedule=[cwu_cycle],
        )

        # Reference simulator: valve=0, no CWU
        rooms_ref = _make_rooms(2, params, ufh_max_power_w=5000.0)
        sim_ref = BuildingSimulator(
            rooms_ref,
            constant_weather,
            hp_max_power_w=10_000.0,
        )

        for _ in range(30):
            sim_cwu.step_all({
                "room_0": Actions(valve_position=100.0),
                "room_1": Actions(valve_position=100.0),
            })
            sim_ref.step_all({
                "room_0": Actions(valve_position=0.0),
                "room_1": Actions(valve_position=0.0),
            })

        # T_slab must match the zero-valve reference exactly
        for name in ("room_0", "room_1"):
            assert sim_cwu.rooms[name].T_slab == pytest.approx(
                sim_ref.rooms[name].T_slab, abs=1e-10
            )
            assert sim_cwu.rooms[name].T_air == pytest.approx(
                sim_ref.rooms[name].T_air, abs=1e-10
            )

    @pytest.mark.unit
    def test_cwu_with_sensor_noise_multi_room(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """CWU + noise simultaneously: floor power zero during CWU, noise throughout.

        Verifies that both CWU interrupts and sensor noise work together
        in multi-room mode without interfering.
        """
        rooms = _make_rooms(2, params, ufh_max_power_w=5000.0)
        noise = SensorNoise(std=0.5, seed=42)
        # CWU active for first 10 steps, then off
        cwu_cycle = CWUCycle(start_minute=0, duration_minutes=10, interval_minutes=0)
        sim = BuildingSimulator(
            rooms,
            constant_weather,
            hp_max_power_w=10_000.0,
            cwu_schedule=[cwu_cycle],
            sensor_noise=noise,
        )

        # Reference for CWU period: valve=0, same noise seed
        rooms_ref = _make_rooms(2, params, ufh_max_power_w=5000.0)
        sim_ref = BuildingSimulator(
            rooms_ref,
            constant_weather,
            hp_max_power_w=10_000.0,
        )

        # CWU phase: 10 steps with valve=100 (overridden to 0)
        for _ in range(10):
            sim.step_all({
                "room_0": Actions(valve_position=100.0),
                "room_1": Actions(valve_position=100.0),
            })
            sim_ref.step_all({
                "room_0": Actions(valve_position=0.0),
                "room_1": Actions(valve_position=0.0),
            })

        # Physics state should match zero-valve reference
        for name in ("room_0", "room_1"):
            assert sim.rooms[name].T_slab == pytest.approx(
                sim_ref.rooms[name].T_slab, abs=1e-10
            )

        # After CWU: valve=100 should now heat the slab
        t_slab_after_cwu = rooms[0].T_slab
        for _ in range(100):
            sim.step_all({
                "room_0": Actions(valve_position=100.0),
                "room_1": Actions(valve_position=100.0),
            })

        # Slab should warm up now that CWU is over
        assert rooms[0].T_slab > t_slab_after_cwu

        # Noise is applied throughout (checked indirectly via non-equal
        # noisy measurement vs physics state -- but we test noise directly
        # in test_sensor_noise_in_multi_room)

    @pytest.mark.unit
    def test_hp_capacity_sharing_with_cwu(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """CWU active results in all HP allocations being 0W.

        When CWU is active, all valve positions are forced to 0, so
        _distribute_hp_power receives all-zero demands and returns
        all-zero allocations.
        """
        rooms = _make_rooms(3, params, ufh_max_power_w=5000.0)
        cwu_cycle = CWUCycle(start_minute=0, duration_minutes=100, interval_minutes=0)
        sim = BuildingSimulator(
            rooms,
            constant_weather,
            hp_max_power_w=6000.0,
            cwu_schedule=[cwu_cycle],
        )

        # CWU is active: all valves should be zeroed internally
        # We can verify by checking that all rooms cool identically
        # to a zero-valve reference
        rooms_ref = _make_rooms(3, params, ufh_max_power_w=5000.0)
        sim_ref = BuildingSimulator(
            rooms_ref,
            constant_weather,
            hp_max_power_w=6000.0,
        )

        for _ in range(50):
            sim.step_all({
                "room_0": Actions(valve_position=100.0),
                "room_1": Actions(valve_position=50.0),
                "room_2": Actions(valve_position=75.0),
            })
            sim_ref.step_all({
                "room_0": Actions(valve_position=0.0),
                "room_1": Actions(valve_position=0.0),
                "room_2": Actions(valve_position=0.0),
            })

        # All rooms should have identical state
        for name in ("room_0", "room_1", "room_2"):
            assert sim.rooms[name].T_slab == pytest.approx(
                sim_ref.rooms[name].T_slab, abs=1e-10
            )
            assert sim.rooms[name].T_air == pytest.approx(
                sim_ref.rooms[name].T_air, abs=1e-10
            )

    @pytest.mark.unit
    def test_cwu_does_not_affect_split_in_multi_room(
        self,
        params_mimo: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """CWU zeroes only valve_position; split operation is preserved.

        This is critical for Axiom #1: splits continue operating during
        CWU to provide comfort, even though floor heating is interrupted.
        """
        # CWU sim: valve=100 (overridden to 0), split=HEATING
        rooms_cwu = [
            _make_room(
                "room_0", params_mimo,
                ufh_max_power_w=5000.0, split_power_w=2500.0,
            ),
            _make_room(
                "room_1", params_mimo,
                ufh_max_power_w=5000.0, split_power_w=2500.0,
            ),
        ]
        cwu_cycle = CWUCycle(start_minute=0, duration_minutes=50, interval_minutes=0)
        sim_cwu = BuildingSimulator(
            rooms_cwu,
            constant_weather,
            hp_max_power_w=10_000.0,
            cwu_schedule=[cwu_cycle],
        )

        # Reference: valve=0, split=HEATING, no CWU
        rooms_ref = [
            _make_room(
                "room_0", params_mimo,
                ufh_max_power_w=5000.0, split_power_w=2500.0,
            ),
            _make_room(
                "room_1", params_mimo,
                ufh_max_power_w=5000.0, split_power_w=2500.0,
            ),
        ]
        sim_ref = BuildingSimulator(
            rooms_ref,
            constant_weather,
            hp_max_power_w=10_000.0,
        )

        for _ in range(50):
            sim_cwu.step_all({
                "room_0": Actions(
                    valve_position=100.0,
                    split_mode=SplitMode.HEATING,
                    split_setpoint=22.0,
                ),
                "room_1": Actions(
                    valve_position=100.0,
                    split_mode=SplitMode.HEATING,
                    split_setpoint=22.0,
                ),
            })
            sim_ref.step_all({
                "room_0": Actions(
                    valve_position=0.0,
                    split_mode=SplitMode.HEATING,
                    split_setpoint=22.0,
                ),
                "room_1": Actions(
                    valve_position=0.0,
                    split_mode=SplitMode.HEATING,
                    split_setpoint=22.0,
                ),
            })

        # Both should match exactly: splits active, floor zeroed in both
        for name in ("room_0", "room_1"):
            assert sim_cwu.rooms[name].T_air == pytest.approx(
                sim_ref.rooms[name].T_air, abs=1e-10
            )
            assert sim_cwu.rooms[name].T_slab == pytest.approx(
                sim_ref.rooms[name].T_slab, abs=1e-10
            )


# ---------------------------------------------------------------------------
# TestSensorNoiseMultiRoom
# ---------------------------------------------------------------------------


class TestSensorNoiseMultiRoom:
    """Tests for sensor noise in multi-room get_all_measurements()."""

    @pytest.mark.unit
    def test_sensor_noise_in_multi_room(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Noise regression: noisy T_room differs from true T_air, physics unaffected.

        After the fix, get_all_measurements() (called by step_all)
        applies sensor noise to T_room and T_slab.  The underlying
        physics state must remain unaffected by noise.
        """
        rooms = _make_rooms(2, params, ufh_max_power_w=5000.0)
        noise = SensorNoise(std=0.5, seed=42)
        sim = BuildingSimulator(
            rooms,
            constant_weather,
            hp_max_power_w=10_000.0,
            sensor_noise=noise,
        )

        # Run 50 steps and collect noisy measurements + true physics state
        noisy_t_rooms: list[float] = []
        true_t_airs: list[float] = []

        for _ in range(50):
            results = sim.step_all({
                "room_0": Actions(valve_position=50.0),
                "room_1": Actions(valve_position=50.0),
            })
            noisy_t_rooms.append(results["room_0"].T_room)
            true_t_airs.append(sim.rooms["room_0"].T_air)

        # Noisy measurements should differ from true physics state
        diffs = [
            abs(n - t)
            for n, t in zip(noisy_t_rooms, true_t_airs, strict=True)
        ]
        max_diff = max(diffs)
        assert max_diff > 0.01, (
            f"Expected noise to create differences, but max diff was {max_diff}"
        )

        # Physics state should be internally consistent (not corrupted by noise)
        # Both rooms started identically and got identical valve positions,
        # so they should have identical physics state
        assert sim.rooms["room_0"].T_air == pytest.approx(
            sim.rooms["room_1"].T_air, abs=1e-10
        )
        assert sim.rooms["room_0"].T_slab == pytest.approx(
            sim.rooms["room_1"].T_slab, abs=1e-10
        )

    @pytest.mark.unit
    def test_sensor_noise_deterministic_multi_room(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Same seed produces identical noisy T_room across two runs.

        This is critical for test reproducibility: the sensor noise must
        be deterministic given the same seed.
        """
        def run_sim(seed: int) -> list[float]:
            rooms = _make_rooms(2, params, ufh_max_power_w=5000.0)
            noise = SensorNoise(std=0.5, seed=seed)
            sim = BuildingSimulator(
                rooms,
                constant_weather,
                hp_max_power_w=10_000.0,
                sensor_noise=noise,
            )
            t_rooms: list[float] = []
            for _ in range(30):
                results = sim.step_all({
                    "room_0": Actions(valve_position=50.0),
                    "room_1": Actions(valve_position=50.0),
                })
                t_rooms.append(results["room_0"].T_room)
            return t_rooms

        run_a = run_sim(seed=123)
        run_b = run_sim(seed=123)
        run_c = run_sim(seed=456)

        # Same seed -> identical results
        np.testing.assert_array_equal(run_a, run_b)

        # Different seed -> different results
        assert run_a != run_c


# ---------------------------------------------------------------------------
# TestSimulationLogRecords
# ---------------------------------------------------------------------------


class TestSimulationLogRecords:
    """Tests for SimulationLog recording matching step_all() returns."""

    @pytest.mark.unit
    def test_simulation_log_records_match_measurements(
        self,
        params: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Log entries match step_all() return values exactly.

        Each step_all() returns a dict of Measurements.  When appended
        to the log, the record's convenience properties must match the
        original measurement values.
        """
        rooms = _make_rooms(2, params, ufh_max_power_w=5000.0)
        noise = SensorNoise(std=0.1, seed=42)
        sim = BuildingSimulator(
            rooms,
            constant_weather,
            hp_max_power_w=10_000.0,
            sensor_noise=noise,
        )

        log = SimulationLog()

        # Collect both step results and log records
        step_results: list[dict[str, Measurements]] = []
        actions_dict = {
            "room_0": Actions(valve_position=75.0),
            "room_1": Actions(valve_position=25.0),
        }

        for t in range(20):
            results = sim.step_all(actions_dict)
            step_results.append(results)
            wp = constant_weather.get(float(t))
            for name, meas in results.items():
                log.append_from_step(
                    t=t + 1,
                    measurements=meas,
                    actions=actions_dict[name],
                    weather=wp,
                    room_name=name,
                )

        # Verify each log record matches its corresponding step result
        for t in range(20):
            for room_idx, name in enumerate(("room_0", "room_1")):
                record_idx = t * 2 + room_idx
                record = log[record_idx]
                original_meas = step_results[t][name]

                assert record.T_room == original_meas.T_room
                assert record.T_slab == original_meas.T_slab
                assert record.T_outdoor == original_meas.T_outdoor
                assert record.valve_pos == original_meas.valve_pos
                assert record.hp_mode == original_meas.hp_mode
                assert record.room_name == name
                assert record.t == t + 1
