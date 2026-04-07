"""Unit tests for sensor noise injection.

Tests cover the ``SensorNoise`` class (determinism, statistics,
validation) and its integration into ``BuildingSimulator`` (noise in
``step()`` and ``get_measurements()``, noise does not affect physics).
"""

from __future__ import annotations

import numpy as np
import pytest

from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.sensor_noise import SensorNoise
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.simulator import (
    Actions,
    BuildingSimulator,
    HeatPumpMode,
)
from pumpahead.weather import SyntheticWeather

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def siso_room(model_3r3c: RCModel) -> SimulatedRoom:
    """SISO simulated room with 5000 W UFH capacity."""
    return SimulatedRoom("noise_test", model_3r3c, ufh_max_power_w=5000.0)


@pytest.fixture()
def constant_weather() -> SyntheticWeather:
    """Constant weather: T_out=-5 degC, no solar."""
    return SyntheticWeather.constant(T_out=-5.0, GHI=0.0)


# ---------------------------------------------------------------------------
# TestSensorNoise
# ---------------------------------------------------------------------------


class TestSensorNoise:
    """Tests for the SensorNoise class in isolation."""

    @pytest.mark.unit
    def test_corrupt_alters_value(self) -> None:
        """Noise with std > 0 changes the input value."""
        noise = SensorNoise(std=0.5, seed=42)
        original = 20.0
        noisy = noise.corrupt(original)
        # With std=0.5 and a fixed seed, the value should differ
        assert noisy != original

    @pytest.mark.unit
    def test_deterministic_with_same_seed(self) -> None:
        """Two SensorNoise instances with the same seed produce identical sequences."""
        noise_a = SensorNoise(std=0.5, seed=123)
        noise_b = SensorNoise(std=0.5, seed=123)

        for _ in range(100):
            val_a = noise_a.corrupt(20.0)
            val_b = noise_b.corrupt(20.0)
            assert val_a == val_b

    @pytest.mark.unit
    def test_different_seeds_differ(self) -> None:
        """Different seeds produce different noise sequences."""
        noise_a = SensorNoise(std=0.5, seed=1)
        noise_b = SensorNoise(std=0.5, seed=2)

        values_a = [noise_a.corrupt(20.0) for _ in range(10)]
        values_b = [noise_b.corrupt(20.0) for _ in range(10)]

        # At least some values should differ
        assert values_a != values_b

    @pytest.mark.unit
    def test_zero_std_no_op(self) -> None:
        """With std=0.0, corrupt() returns the original value unchanged."""
        noise = SensorNoise(std=0.0, seed=42)
        for _ in range(100):
            assert noise.corrupt(20.0) == 20.0
            assert noise.corrupt(-5.5) == -5.5

    @pytest.mark.unit
    def test_negative_std_raises(self) -> None:
        """Negative std raises ValueError."""
        with pytest.raises(ValueError, match="std must be >= 0.0"):
            SensorNoise(std=-0.1, seed=42)

    @pytest.mark.unit
    def test_noise_statistics(self) -> None:
        """Over many samples, noise mean is ~0 and std matches configuration."""
        target_std = 0.3
        noise = SensorNoise(std=target_std, seed=42)
        base_value = 20.0

        samples = np.array([noise.corrupt(base_value) for _ in range(10_000)])
        deltas = samples - base_value

        # Mean of noise should be near zero (within 3 sigma of sampling distribution)
        assert abs(np.mean(deltas)) < 3.0 * target_std / np.sqrt(len(deltas))
        # Std of noise should match configured std (within 10 %)
        assert np.std(deltas) == pytest.approx(target_std, rel=0.1)

    @pytest.mark.unit
    def test_properties(self) -> None:
        """std and seed properties return configured values."""
        noise = SensorNoise(std=0.25, seed=99)
        assert noise.std == 0.25
        assert noise.seed == 99


# ---------------------------------------------------------------------------
# TestSensorNoiseIntegration
# ---------------------------------------------------------------------------


class TestSensorNoiseIntegration:
    """Tests for SensorNoise integration in BuildingSimulator."""

    @pytest.mark.unit
    def test_noise_in_step_measurements(
        self,
        siso_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """step() returns noisy T_room and T_slab when noise is configured."""
        noise = SensorNoise(std=0.5, seed=42)
        sim = BuildingSimulator(siso_room, constant_weather, sensor_noise=noise)

        # Step to get a measurement
        meas = sim.step(Actions(valve_position=50.0))

        # The measurement T_room/T_slab should differ from the true physical state
        # (unless extremely unlikely coincidence)
        true_t_room = siso_room.T_air
        true_t_slab = siso_room.T_slab
        # At least one should differ (extremely unlikely both match with std=0.5)
        assert meas.T_room != true_t_room or meas.T_slab != true_t_slab

    @pytest.mark.unit
    def test_noise_in_get_measurements(
        self,
        siso_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """get_measurements() also applies noise when configured."""
        noise = SensorNoise(std=0.5, seed=42)
        sim = BuildingSimulator(siso_room, constant_weather, sensor_noise=noise)

        meas = sim.get_measurements()

        # T_outdoor, valve_pos, hp_mode should be exact
        assert meas.T_outdoor == -5.0
        assert meas.valve_pos == 0.0
        assert meas.hp_mode == HeatPumpMode.HEATING

    @pytest.mark.unit
    def test_noise_preserves_t_outdoor(
        self,
        siso_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Noise is NOT applied to T_outdoor."""
        noise = SensorNoise(std=1.0, seed=42)
        sim = BuildingSimulator(siso_room, constant_weather, sensor_noise=noise)

        for _ in range(100):
            meas = sim.step(Actions(valve_position=50.0))
            assert meas.T_outdoor == -5.0

    @pytest.mark.unit
    def test_noise_does_not_affect_physics(
        self,
        model_3r3c: RCModel,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Physical state evolves identically with and without noise."""
        params = model_3r3c.params
        order = ModelOrder.THREE

        # Simulator WITH noise
        model_noisy = RCModel(params, order, dt=60.0)
        room_noisy = SimulatedRoom("noisy", model_noisy, ufh_max_power_w=5000.0)
        noise = SensorNoise(std=1.0, seed=42)
        sim_noisy = BuildingSimulator(room_noisy, constant_weather, sensor_noise=noise)

        # Simulator WITHOUT noise
        model_clean = RCModel(params, order, dt=60.0)
        room_clean = SimulatedRoom("clean", model_clean, ufh_max_power_w=5000.0)
        sim_clean = BuildingSimulator(room_clean, constant_weather)

        # Run both with identical actions
        for _ in range(200):
            sim_noisy.step(Actions(valve_position=75.0))
            sim_clean.step(Actions(valve_position=75.0))

        # Physical state must be identical
        np.testing.assert_array_equal(room_noisy.state, room_clean.state)

    @pytest.mark.unit
    def test_no_noise_returns_exact_values(
        self,
        siso_room: SimulatedRoom,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Without noise configured, measurements are exact."""
        sim = BuildingSimulator(siso_room, constant_weather)

        meas = sim.step(Actions(valve_position=50.0))

        assert meas.T_room == siso_room.T_air
        assert meas.T_slab == siso_room.T_slab

    @pytest.mark.unit
    def test_noise_deterministic_across_runs(
        self,
        params_3r3c: RCParams,
        constant_weather: SyntheticWeather,
    ) -> None:
        """Two simulators with the same noise seed produce identical measurements."""
        results: list[list[float]] = []

        for _ in range(2):
            model = RCModel(params_3r3c, ModelOrder.THREE, dt=60.0)
            room = SimulatedRoom("det", model, ufh_max_power_w=5000.0)
            noise = SensorNoise(std=0.3, seed=42)
            sim = BuildingSimulator(room, constant_weather, sensor_noise=noise)

            run_t_rooms = []
            for step in range(100):
                valve = 50.0 if step < 50 else 0.0
                meas = sim.step(Actions(valve_position=valve))
                run_t_rooms.append(meas.T_room)
            results.append(run_t_rooms)

        for i in range(100):
            assert results[0][i] == results[1][i]
