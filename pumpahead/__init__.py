"""PumpAhead — Predictive heating/cooling controller with RC thermal models."""

from pumpahead.estimator import KalmanEstimator
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.solar import (
    EphemerisCalculator,
    Orientation,
    SolarGainModel,
    WindowConfig,
)

__version__ = "0.1.0"

__all__ = [
    "EphemerisCalculator",
    "KalmanEstimator",
    "ModelOrder",
    "Orientation",
    "RCModel",
    "RCParams",
    "SolarGainModel",
    "WindowConfig",
    "__version__",
]
