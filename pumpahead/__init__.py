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
    CSVConfig,
    CSVParseError,
    CSVWeather,
    OpenMeteoHistorical,
    ProfileKind,
    SyntheticWeather,
    WeatherAPIError,
    WeatherDataError,
    WeatherPoint,
    WeatherRangeError,
    WeatherSource,
)

__version__ = "0.1.0"

__all__ = [
    "CSVConfig",
    "CSVParseError",
    "CSVWeather",
    "ChannelProfile",
    "EphemerisCalculator",
    "KalmanEstimator",
    "ModelOrder",
    "OpenMeteoHistorical",
    "Orientation",
    "ProfileKind",
    "RCModel",
    "RCParams",
    "SolarGainModel",
    "SyntheticWeather",
    "WeatherAPIError",
    "WeatherDataError",
    "WeatherPoint",
    "WeatherRangeError",
    "WeatherSource",
    "WindowConfig",
    "__version__",
]
