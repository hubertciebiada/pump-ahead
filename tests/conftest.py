"""Shared pytest fixtures for PumpAhead tests."""

import pytest

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
