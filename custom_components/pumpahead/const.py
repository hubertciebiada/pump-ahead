"""Constants for the PumpAhead integration."""

from homeassistant.const import Platform

DOMAIN: str = "pumpahead"

# Platforms will be added as their modules are implemented:
# Platform.SENSOR (shadow mode diagnostics)
# Platform.CLIMATE (ClimateEntity per room)
PLATFORMS: list[Platform] = []

# Configuration keys for config flow (issue #45)
CONF_ROOM_NAME: str = "room_name"
CONF_ENTITY_TEMP_ROOM: str = "entity_temp_room"
CONF_ENTITY_TEMP_FLOOR: str = "entity_temp_floor"
CONF_ENTITY_VALVE: str = "entity_valve"
CONF_ENTITY_TEMP_OUTDOOR: str = "entity_temp_outdoor"
CONF_ENTITY_WEATHER: str = "entity_weather"
