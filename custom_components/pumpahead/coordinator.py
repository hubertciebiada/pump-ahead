"""DataUpdateCoordinator for the PumpAhead integration.

Polls HA entity states every 5 minutes and provides typed data to
entity platforms via ``coordinator.data``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ALGORITHM_MODE,
    CONF_ENTITY_HUMIDITY,
    CONF_ENTITY_TEMP_FLOOR,
    CONF_ENTITY_TEMP_OUTDOOR,
    CONF_ENTITY_TEMP_ROOM,
    CONF_ENTITY_VALVE,
    CONF_ENTITY_WEATHER,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    DOMAIN,
    UPDATE_INTERVAL_MINUTES,
)
from .ha_weather import HAWeatherSource

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RoomSensorData:
    """Sensor readings for a single room."""

    room_name: str
    T_room: float | None  # degC
    T_floor: float | None  # degC (optional sensor)
    valve_pos: float | None  # 0-100 %
    humidity: float | None  # % (optional)


@dataclass
class PumpAheadCoordinatorData:
    """All data collected by the coordinator in one update cycle."""

    rooms: dict[str, RoomSensorData]  # keyed by room name
    T_outdoor: float | None  # degC
    weather_source: HAWeatherSource | None
    last_update_success: bool
    algorithm_mode: str  # "heating" / "cooling" / "auto"


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class PumpAheadCoordinator(DataUpdateCoordinator[PumpAheadCoordinatorData]):
    """Coordinator that polls HA entities every 5 minutes."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self._room_configs: list[dict] = entry.data.get(CONF_ROOMS, [])  # type: ignore[assignment]
        self._weather_entity: str = entry.data.get(CONF_ENTITY_WEATHER, "")  # type: ignore[assignment]
        self._outdoor_entity: str = entry.data.get(CONF_ENTITY_TEMP_OUTDOOR, "")  # type: ignore[assignment]
        self._weather_source: HAWeatherSource | None = None
        self._algorithm_mode: str = entry.data.get(CONF_ALGORITHM_MODE, "heating")  # type: ignore[assignment]

        lat: float = entry.data.get(CONF_LATITUDE, hass.config.latitude)  # type: ignore[assignment]
        lon: float = entry.data.get(CONF_LONGITUDE, hass.config.longitude)  # type: ignore[assignment]
        if self._weather_entity:
            self._weather_source = HAWeatherSource(
                self._weather_entity, lat, lon
            )

    # -- Update -------------------------------------------------------------

    async def _async_update_data(self) -> PumpAheadCoordinatorData:
        """Fetch data from HA entities."""
        rooms: dict[str, RoomSensorData] = {}
        for room_cfg in self._room_configs:
            room_name: str = room_cfg[CONF_ROOM_NAME]
            rooms[room_name] = RoomSensorData(
                room_name=room_name,
                T_room=self._read_float_state(room_cfg.get(CONF_ENTITY_TEMP_ROOM)),
                T_floor=self._read_float_state(room_cfg.get(CONF_ENTITY_TEMP_FLOOR)),
                valve_pos=self._read_float_state(room_cfg.get(CONF_ENTITY_VALVE)),
                humidity=self._read_float_state(room_cfg.get(CONF_ENTITY_HUMIDITY)),
            )

        T_outdoor = self._read_float_state(self._outdoor_entity)

        if self._weather_source is not None:
            try:
                await self._weather_source.async_update(self.hass)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Weather update failed")

        return PumpAheadCoordinatorData(
            rooms=rooms,
            T_outdoor=T_outdoor,
            weather_source=self._weather_source,
            last_update_success=True,
            algorithm_mode=self._algorithm_mode,
        )

    # -- Helpers ------------------------------------------------------------

    def _read_float_state(self, entity_id: str | None) -> float | None:
        """Read a numeric entity state, returning ``None`` on failure."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None
