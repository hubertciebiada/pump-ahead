"""PumpAhead — Predictive heating/cooling controller with RC thermal models."""

from pumpahead.config import CWUCycle
from pumpahead.estimator import KalmanEstimator
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.sensor_noise import SensorNoise
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.simulator import (
    Actions,
    BuildingSimulator,
    HeatPumpMode,
    Measurements,
    SplitMode,
)
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
    "Actions",
    "BuildingSimulator",
    "CWUCycle",
    "CSVConfig",
    "CSVParseError",
    "CSVWeather",
    "ChannelProfile",
    "EphemerisCalculator",
    "HeatPumpMode",
    "KalmanEstimator",
    "Measurements",
    "ModelOrder",
    "OpenMeteoHistorical",
    "Orientation",
    "ProfileKind",
    "RCModel",
    "RCParams",
    "SensorNoise",
    "SimulatedRoom",
    "SolarGainModel",
    "SplitMode",
    "SyntheticWeather",
    "WeatherAPIError",
    "WeatherDataError",
    "WeatherPoint",
    "WeatherRangeError",
    "WeatherSource",
    "WindowConfig",
    "__version__",
]
