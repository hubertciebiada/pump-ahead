"""Shared pytest fixtures for PumpAhead tests."""

import numpy as np
import pytest

from pumpahead.estimator import KalmanEstimator
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.solar import (
    EphemerisCalculator,
    Orientation,
    SolarGainModel,
    WindowConfig,
)


@pytest.fixture()
def params_3r3c() -> RCParams:
    """Standard 3R3C parameters for a 20 m^2 room (SISO, UFH only)."""
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
def params_3r3c_mimo() -> RCParams:
    """Standard 3R3C parameters for a 20 m^2 room (MIMO, UFH + split)."""
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
def params_2r2c() -> RCParams:
    """Standard 2R2C parameters for a 20 m^2 room (SISO, UFH only)."""
    return RCParams(
        C_air=60_000,
        C_slab=3_250_000,
        R_sf=0.01,
        R_env=0.03,
        f_conv=0.6,
        f_rad=0.4,
        T_ground=10.0,
        has_split=False,
    )


@pytest.fixture()
def params_2r2c_mimo() -> RCParams:
    """Standard 2R2C parameters (MIMO, UFH + split)."""
    return RCParams(
        C_air=60_000,
        C_slab=3_250_000,
        R_sf=0.01,
        R_env=0.03,
        f_conv=0.6,
        f_rad=0.4,
        T_ground=10.0,
        has_split=True,
    )


@pytest.fixture()
def model_3r3c(params_3r3c: RCParams) -> RCModel:
    """3R3C SISO model with default dt=60s."""
    return RCModel(params_3r3c, ModelOrder.THREE, dt=60.0)


@pytest.fixture()
def model_3r3c_mimo(params_3r3c_mimo: RCParams) -> RCModel:
    """3R3C MIMO model with default dt=60s."""
    return RCModel(params_3r3c_mimo, ModelOrder.THREE, dt=60.0)


@pytest.fixture()
def model_2r2c(params_2r2c: RCParams) -> RCModel:
    """2R2C SISO model with default dt=60s."""
    return RCModel(params_2r2c, ModelOrder.TWO, dt=60.0)


@pytest.fixture()
def model_2r2c_mimo(params_2r2c_mimo: RCParams) -> RCModel:
    """2R2C MIMO model with default dt=60s."""
    return RCModel(params_2r2c_mimo, ModelOrder.TWO, dt=60.0)


# ---------------------------------------------------------------------------
# Solar fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def south_window() -> WindowConfig:
    """South-facing window: 3 m^2, g=0.6 (typical double glazing)."""
    return WindowConfig(Orientation.SOUTH, area_m2=3.0, g_value=0.6)


@pytest.fixture()
def solar_model() -> SolarGainModel:
    """Stateless solar gain calculator."""
    return SolarGainModel()


@pytest.fixture()
def ephemeris_lubcza() -> EphemerisCalculator:
    """EphemerisCalculator for Lubcza, Poland (Hubert's location)."""
    return EphemerisCalculator(latitude=50.69, longitude=17.38)


# ---------------------------------------------------------------------------
# KalmanEstimator fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def kalman_3r3c(model_3r3c: RCModel) -> KalmanEstimator:
    """3R3C Kalman estimator with T_room only."""
    return KalmanEstimator(model_3r3c, has_floor_sensor=False)


@pytest.fixture()
def kalman_3r3c_dual(model_3r3c: RCModel) -> KalmanEstimator:
    """3R3C Kalman estimator with T_room + T_floor_surface."""
    return KalmanEstimator(model_3r3c, has_floor_sensor=True)


@pytest.fixture()
def kalman_2r2c(model_2r2c: RCModel) -> KalmanEstimator:
    """2R2C Kalman estimator with T_room only."""
    return KalmanEstimator(model_2r2c, has_floor_sensor=False)


@pytest.fixture()
def kalman_2r2c_dual(model_2r2c: RCModel) -> KalmanEstimator:
    """2R2C Kalman estimator with T_room + T_floor_surface."""
    return KalmanEstimator(model_2r2c, has_floor_sensor=True)


# ---------------------------------------------------------------------------
# Weather / disturbance fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def constant_disturbance() -> np.ndarray:
    """Constant disturbance vector: T_out=5C, no solar, no internal gains."""
    return np.array([5.0, 0.0, 0.0])


@pytest.fixture()
def winter_disturbance() -> np.ndarray:
    """Winter night disturbance: T_out=-10C, no solar, no internal gains."""
    return np.array([-10.0, 0.0, 0.0])


@pytest.fixture()
def summer_disturbance() -> np.ndarray:
    """Summer noon disturbance: T_out=30C, Q_sol=400W, Q_int=100W."""
    return np.array([30.0, 400.0, 100.0])


@pytest.fixture()
def outdoor_temperature_24h() -> np.ndarray:
    """24h sinusoidal outdoor temperature profile at 1-min resolution.

    Mean=5C, amplitude=10C (range: -5C to 15C).
    """
    return np.sin(2.0 * np.pi * np.arange(1440) / 1440) * 10.0 + 5.0


@pytest.fixture()
def disturbance_sequence_24h(outdoor_temperature_24h: np.ndarray) -> np.ndarray:
    """24h disturbance sequence [T_out, Q_sol, Q_int] at 1-min resolution.

    Column 0: outdoor temperature from *outdoor_temperature_24h*.
    Column 1: Q_sol — half-sine peaking at 500 W during daylight (minutes 360–1080).
    Column 2: Q_int — constant 50 W internal gains.
    """
    n = 1440
    q_sol = np.zeros(n)
    daylight_start, daylight_end = 360, 1080
    daylight_len = daylight_end - daylight_start
    daylight_idx = np.arange(daylight_start, daylight_end)
    q_sol[daylight_idx] = 500.0 * np.sin(
        np.pi * (daylight_idx - daylight_start) / daylight_len
    )

    q_int = np.full(n, 50.0)

    return np.column_stack([outdoor_temperature_24h, q_sol, q_int])


# ---------------------------------------------------------------------------
# Identifier fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def identifier_2r2c_synth_data(
    params_2r2c: RCParams,
    model_2r2c: RCModel,
) -> tuple[RCParams, np.ndarray, np.ndarray, np.ndarray]:
    """Synthetic 2R2C identification data: cyclic heating, 2 days at dt=60s.

    Returns (true_params, u_sequence, d_sequence, T_room_measured).

    Starts from thermal equilibrium at T_out=5C (T_air = T_slab = 5C),
    then alternates Q_floor between 1500 W and 0 in 4-hour blocks.
    Constant T_out and no Q_sol keep the landscape smooth while the
    cycling excitation ensures both fast (C_air) and slow (C_slab) modes
    are identifiable.
    """
    n_steps = 2880  # 2 days
    u_seq = np.zeros((n_steps, 1))
    for i in range(n_steps):
        block = (i // 240) % 2  # 4-hour blocks (240 min)
        # First block is OFF so x0 matches cost function exactly
        u_seq[i, 0] = 0.0 if block == 0 else 1500.0

    d_seq = np.zeros((n_steps, 2))
    d_seq[:, 0] = 5.0  # constant T_out = 5 C

    # Start from equilibrium: T_air = T_slab = T_out = 5 C
    x0 = np.array([5.0, 5.0])
    traj = model_2r2c.predict(x0, u_seq, d_seq)
    T_room = traj[1:, 0]  # T_air at each step (skip x0)

    return params_2r2c, u_seq, d_seq, T_room
