"""Fixtures specific to PumpAhead simulation tests."""

import numpy as np
import pytest

from pumpahead.model import ModelOrder, RCModel, RCParams


@pytest.fixture()
def sim_rng() -> np.random.Generator:
    """Seeded random generator for deterministic simulation tests.

    Uses a different seed than unit tests to catch seed-dependent bugs.
    """
    return np.random.default_rng(12345)


@pytest.fixture()
def sim_model_3r3c(params_3r3c: RCParams) -> RCModel:
    """3R3C model with dt=60s (1-min steps) for simulation tests."""
    return RCModel(params_3r3c, ModelOrder.THREE, dt=60.0)


@pytest.fixture()
def sim_steps_24h() -> int:
    """Number of simulation steps for a 24-hour simulation at dt=60s."""
    return 1440


@pytest.fixture()
def sim_steps_7d() -> int:
    """Number of simulation steps for a 7-day simulation at dt=60s."""
    return 10080
