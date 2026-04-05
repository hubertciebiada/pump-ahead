"""PumpAhead — Predictive heating/cooling controller with RC thermal models."""

from pumpahead.estimator import KalmanEstimator
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.solar import (
    EphemerisCalculator,
    Orientation,
    SolarGainModel,
    WindowConfig,
)
from pumpahead.weather import (
    ChannelProfile,
    ProfileKind,
    SyntheticWeather,
    WeatherPoint,
    WeatherSource,
)

__version__ = "0.1.0"

__all__ = [
    "ChannelProfile",
    "EphemerisCalculator",
    "KalmanEstimator",
    "ModelOrder",
    "Orientation",
    "ProfileKind",
    "RCModel",
    "RCParams",
    "SolarGainModel",
    "SyntheticWeather",
    "WeatherPoint",
    "WeatherSource",
    "WindowConfig",
    "__version__",
]
