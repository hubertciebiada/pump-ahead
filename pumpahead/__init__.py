"""PumpAhead — Predictive heating/cooling controller with RC thermal models."""

from pumpahead.building_profiles import (
    BUILDING_PROFILES,
    HUBERT_ROOMS,
    heavy_construction,
    hubert_real,
    leaky_old_house,
    thin_screed,
    well_insulated,
)
from pumpahead.config import (
    BuildingParams,
    ControllerConfig,
    CWUCycle,
    RoomConfig,
    SimScenario,
)
from pumpahead.metrics import SimMetrics
from pumpahead.estimator import KalmanEstimator
from pumpahead.model import ModelOrder, RCModel, RCParams
from pumpahead.scenarios import (
    PARAMETRIC_SWEEPS,
    SCENARIO_LIBRARY,
    cold_snap,
    cwu_heavy,
    extreme_cold,
    full_year_2025,
    hot_july,
    insulation_sweep,
    rapid_warming,
    screed_sweep,
    solar_overshoot,
    steady_state,
)
from pumpahead.sensor_noise import SensorNoise
from pumpahead.simulated_room import SimulatedRoom
from pumpahead.simulation_log import SimRecord, SimulationLog
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
    "BUILDING_PROFILES",
    "BuildingParams",
    "BuildingSimulator",
    "ControllerConfig",
    "CWUCycle",
    "CSVConfig",
    "CSVParseError",
    "CSVWeather",
    "ChannelProfile",
    "EphemerisCalculator",
    "HUBERT_ROOMS",
    "HeatPumpMode",
    "KalmanEstimator",
    "Measurements",
    "ModelOrder",
    "OpenMeteoHistorical",
    "Orientation",
    "PARAMETRIC_SWEEPS",
    "ProfileKind",
    "RCModel",
    "RCParams",
    "RoomConfig",
    "SCENARIO_LIBRARY",
    "SensorNoise",
    "SimMetrics",
    "SimRecord",
    "SimScenario",
    "SimulatedRoom",
    "SimulationLog",
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
    "cold_snap",
    "cwu_heavy",
    "extreme_cold",
    "full_year_2025",
    "heavy_construction",
    "hot_july",
    "hubert_real",
    "insulation_sweep",
    "leaky_old_house",
    "rapid_warming",
    "screed_sweep",
    "solar_overshoot",
    "steady_state",
    "thin_screed",
    "well_insulated",
]
