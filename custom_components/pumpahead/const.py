"""Constants for the PumpAhead integration."""

from homeassistant.const import Platform

DOMAIN: str = "pumpahead"

# Platforms will be added as their modules are implemented:
# Platform.SENSOR (shadow mode diagnostics)
# Platform.CLIMATE (ClimateEntity per room)
PLATFORMS: list[Platform] = []

# ---------------------------------------------------------------------------
# Configuration keys for config flow (issue #45)
# ---------------------------------------------------------------------------

# Step 1: Location
CONF_LATITUDE: str = "latitude"
CONF_LONGITUDE: str = "longitude"

# Step 2: Rooms
CONF_ROOMS: str = "rooms"
CONF_ROOM_NAME: str = "room_name"
CONF_ROOM_AREA: str = "room_area"
CONF_HAS_SPLIT: str = "has_split"
CONF_ADD_ANOTHER: str = "add_another"

# Step 3: Entity mapping (per-room)
CONF_ENTITY_TEMP_ROOM: str = "entity_temp_room"
CONF_ENTITY_TEMP_FLOOR: str = "entity_temp_floor"
CONF_ENTITY_VALVE: str = "entity_valve"
CONF_ENTITY_HUMIDITY: str = "entity_humidity"
CONF_ENTITY_SPLIT: str = "entity_split"

# Step 3: Entity mapping (global)
CONF_ENTITY_TEMP_OUTDOOR: str = "entity_temp_outdoor"
CONF_ENTITY_WEATHER: str = "entity_weather"

# Step 4: Algorithm parameters
CONF_ALGORITHM_MODE: str = "algorithm_mode"
CONF_W_COMFORT: str = "w_comfort"
CONF_W_ENERGY: str = "w_energy"
CONF_W_SMOOTH: str = "w_smooth"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_W_COMFORT: float = 1.0
DEFAULT_W_ENERGY: float = 0.1
DEFAULT_W_SMOOTH: float = 0.01

# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

UPDATE_INTERVAL_MINUTES: int = 5

# ---------------------------------------------------------------------------
# Unit validation sets (Axiom 8: hardware-agnostic, unit validation only)
# ---------------------------------------------------------------------------

VALID_TEMP_UNITS: set[str] = {"\u00b0C", "C"}
VALID_PERCENT_UNITS: set[str] = {"%"}
VALID_POWER_UNITS: set[str] = {"W"}
