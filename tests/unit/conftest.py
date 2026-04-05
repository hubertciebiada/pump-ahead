"""Fixtures specific to PumpAhead unit tests."""

import numpy as np
import pytest

from pumpahead.model import ModelOrder, RCModel, RCParams


@pytest.fixture()
def rng() -> np.random.Generator:
    """Seeded random generator for deterministic unit tests."""
    return np.random.default_rng(42)


@pytest.fixture()
def short_dt_model(params_3r3c: RCParams) -> RCModel:
    """3R3C model with short dt=10s for fast unit test convergence."""
    return RCModel(params_3r3c, ModelOrder.THREE, dt=10.0)


@pytest.fixture()
def zero_input_siso() -> np.ndarray:
    """Zero control input for SISO (UFH-only) model."""
    return np.array([0.0])


@pytest.fixture()
def zero_input_mimo() -> np.ndarray:
    """Zero control input for MIMO (UFH+split) model."""
    return np.array([0.0, 0.0])
