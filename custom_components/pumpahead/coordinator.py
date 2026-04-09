"""DataUpdateCoordinator for the PumpAhead integration.

Polls HA entity states every 5 minutes, runs shadow-mode PID
computation, and provides typed data to entity platforms via
``coordinator.data``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from pumpahead.controller import PIDController

from .const import (
    CONF_ALGORITHM_MODE,
    CONF_ENTITY_HUMIDITY,
    CONF_ENTITY_SPLIT,
    CONF_ENTITY_TEMP_FLOOR,
    CONF_ENTITY_TEMP_OUTDOOR,
    CONF_ENTITY_TEMP_ROOM,
    CONF_ENTITY_VALVE,
    CONF_ENTITY_WEATHER,
    CONF_HAS_SPLIT,
    CONF_LATITUDE,
    CONF_LIVE_CONTROL,
    CONF_LONGITUDE,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    DEFAULT_KD,
    DEFAULT_KI,
    DEFAULT_KP,
    DEFAULT_SETPOINT,
    DOMAIN,
    ENTITY_STALE_MAX_SECONDS,
    UPDATE_INTERVAL_MINUTES,
)
from .ha_weather import HAWeatherSource

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RoomSensorData:
    """Sensor readings and shadow-mode recommendations for a single room."""

    room_name: str
    T_room: float | None  # degC
    T_floor: float | None  # degC (optional sensor)
    valve_pos: float | None  # 0-100 %
    humidity: float | None  # % (optional)
    recommended_valve: float | None = None  # 0-100 % (shadow mode)
    predicted_temp: float | None = None  # degC (shadow mode)
    live_control_enabled: bool = False  # per-room live control toggle
    setpoint: float = DEFAULT_SETPOINT  # target temperature (degC)
    split_recommended_mode: str | None = None  # "heating" / "cooling" / "off" / None
    split_recommended_setpoint: float | None = None  # degC for split target


@dataclass
class PumpAheadCoordinatorData:
    """All data collected by the coordinator in one update cycle."""

    rooms: dict[str, RoomSensorData]  # keyed by room name
    T_outdoor: float | None  # degC
    weather_source: HAWeatherSource | None
    last_update_success: bool
    algorithm_mode: str  # "heating" / "cooling" / "auto"
    algorithm_status: str = "running"  # "running" / "error" / "stale"
    last_update_timestamp: str | None = None  # ISO 8601 timestamp


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
            self._weather_source = HAWeatherSource(self._weather_entity, lat, lon)

        # Per-room live control settings from options flow.
        self._live_control_map: dict[str, bool] = entry.options.get(
            CONF_LIVE_CONTROL, {}
        )

        # Fallback cache: entity_id -> (last_value, timestamp).
        self._entity_cache: dict[str, tuple[float, datetime]] = {}

        # Shadow-mode PID controllers (one per room).
        self._pid_controllers: dict[str, PIDController] = {}
        for room_cfg in self._room_configs:
            room_name: str = room_cfg[CONF_ROOM_NAME]
            self._pid_controllers[room_name] = PIDController(
                kp=DEFAULT_KP,
                ki=DEFAULT_KI,
                kd=DEFAULT_KD,
                dt=UPDATE_INTERVAL_MINUTES * 60.0,
            )

    # -- Update -------------------------------------------------------------

    async def _async_update_data(self) -> PumpAheadCoordinatorData:
        """Fetch data from HA entities and run shadow-mode PID."""
        rooms: dict[str, RoomSensorData] = {}
        for room_cfg in self._room_configs:
            room_name: str = room_cfg[CONF_ROOM_NAME]
            is_live = self._live_control_map.get(room_name, False)
            rooms[room_name] = RoomSensorData(
                room_name=room_name,
                T_room=self._read_float_state(room_cfg.get(CONF_ENTITY_TEMP_ROOM)),
                T_floor=self._read_float_state(room_cfg.get(CONF_ENTITY_TEMP_FLOOR)),
                valve_pos=self._read_float_state(room_cfg.get(CONF_ENTITY_VALVE)),
                humidity=self._read_float_state(room_cfg.get(CONF_ENTITY_HUMIDITY)),
                live_control_enabled=is_live,
            )

        T_outdoor = self._read_float_state(self._outdoor_entity)

        if self._weather_source is not None:
            try:
                await self._weather_source.async_update(self.hass)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Weather update failed")

        # Shadow-mode PID computation.
        algorithm_status = self._run_shadow_pid(rooms)
        now_iso = datetime.now(UTC).isoformat()

        # Populate split recommendations for rooms with splits.
        self._compute_split_recommendations(rooms)

        # Live control: apply valve and split outputs for enabled rooms.
        for room_cfg in self._room_configs:
            room_name = room_cfg[CONF_ROOM_NAME]
            room_data = rooms.get(room_name)
            if room_data is None or not room_data.live_control_enabled:
                continue
            await self._apply_valve_control(room_cfg, room_data)
            if room_cfg.get(CONF_HAS_SPLIT, False) and room_cfg.get(CONF_ENTITY_SPLIT):
                await self._apply_split_control(room_cfg, room_data)

        return PumpAheadCoordinatorData(
            rooms=rooms,
            T_outdoor=T_outdoor,
            weather_source=self._weather_source,
            last_update_success=True,
            algorithm_mode=self._algorithm_mode,
            algorithm_status=algorithm_status,
            last_update_timestamp=now_iso,
        )

    # -- Shadow-mode PID -----------------------------------------------------

    def _run_shadow_pid(self, rooms: dict[str, RoomSensorData]) -> str:
        """Run PID computation for all rooms and populate recommendations.

        Returns the algorithm status: ``"running"``, ``"error"``, or
        ``"stale"``.
        """
        # Check if all rooms have None T_room — stale.
        all_stale = all(room.T_room is None for room in rooms.values())
        if rooms and all_stale:
            return "stale"

        has_any_stale = any(room.T_room is None for room in rooms.values())
        try:
            for room_name, room_data in rooms.items():
                if room_data.T_room is None:
                    # Cannot compute for this room — leave recommendations None.
                    continue
                pid = self._pid_controllers.get(room_name)
                if pid is None:
                    continue
                error = DEFAULT_SETPOINT - room_data.T_room
                room_data.recommended_valve = pid.compute(error)
                # Predicted temp: echo current value (MPC not yet available).
                room_data.predicted_temp = room_data.T_room
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Shadow-mode PID computation failed")
            return "error"

        return "stale" if has_any_stale else "running"

    # -- Split recommendations ------------------------------------------------

    def _compute_split_recommendations(self, rooms: dict[str, RoomSensorData]) -> None:
        """Populate split recommendation fields for rooms with splits.

        Determines whether the split should assist based on the PID error
        and the current algorithm mode.  Axiom 3: splits never oppose the
        mode (no cooling in heating mode, no heating in cooling mode).
        """
        for room_cfg in self._room_configs:
            room_name = room_cfg[CONF_ROOM_NAME]
            room_data = rooms.get(room_name)
            if room_data is None:
                continue
            if not room_cfg.get(CONF_HAS_SPLIT, False):
                continue
            if room_data.T_room is None:
                continue

            error = room_data.setpoint - room_data.T_room

            if self._algorithm_mode == "heating" and error > 0.5:
                room_data.split_recommended_mode = "heating"
                room_data.split_recommended_setpoint = room_data.setpoint
            elif self._algorithm_mode == "cooling" and error < -0.5:
                room_data.split_recommended_mode = "cooling"
                room_data.split_recommended_setpoint = room_data.setpoint
            elif self._algorithm_mode == "auto":
                if error > 0.5:
                    room_data.split_recommended_mode = "heating"
                    room_data.split_recommended_setpoint = room_data.setpoint
                elif error < -0.5:
                    room_data.split_recommended_mode = "cooling"
                    room_data.split_recommended_setpoint = room_data.setpoint
                else:
                    room_data.split_recommended_mode = "off"
                    room_data.split_recommended_setpoint = None
            else:
                room_data.split_recommended_mode = "off"
                room_data.split_recommended_setpoint = None

    # -- Live control output ---------------------------------------------------

    async def _apply_valve_control(
        self, room_cfg: dict, room_data: RoomSensorData
    ) -> None:
        """Issue ``number.set_value`` for the room's valve entity.

        Skipped when the room has no temperature data or no recommended
        valve value.  Service call uses ``blocking=False`` to avoid
        blocking the event loop.
        """
        valve_entity = room_cfg.get(CONF_ENTITY_VALVE)
        if not valve_entity or room_data.recommended_valve is None:
            return

        try:
            await self.hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": valve_entity, "value": room_data.recommended_valve},
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Failed to set valve %s for room %s",
                valve_entity,
                room_data.room_name,
            )

    async def _apply_split_control(
        self, room_cfg: dict, room_data: RoomSensorData
    ) -> None:
        """Issue set_hvac_mode and set_temperature for the split.

        Only called when the recommended state differs from the current
        state to avoid unnecessary service calls.  Axiom 3: splits never
        oppose the current mode.
        """
        split_entity = room_cfg.get(CONF_ENTITY_SPLIT)
        if not split_entity or room_data.split_recommended_mode is None:
            return

        # Map internal mode names to HA HVAC modes.
        mode_map = {"heating": "heat", "cooling": "cool", "off": "off"}
        ha_mode = mode_map.get(room_data.split_recommended_mode, "off")

        try:
            await self.hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {"entity_id": split_entity, "hvac_mode": ha_mode},
                blocking=False,
            )
            if ha_mode != "off" and room_data.split_recommended_setpoint is not None:
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {
                        "entity_id": split_entity,
                        "temperature": room_data.split_recommended_setpoint,
                    },
                    blocking=False,
                )
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Failed to control split %s for room %s",
                split_entity,
                room_data.room_name,
            )

    # -- Helpers ------------------------------------------------------------

    def _read_float_state(self, entity_id: str | None) -> float | None:
        """Read a numeric entity state, returning ``None`` on failure.

        On a successful read the value is cached.  When the entity is
        unavailable or unknown the cached value is returned if it is
        less than :data:`ENTITY_STALE_MAX_SECONDS` old.
        """
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            cached = self._entity_cache.get(entity_id)
            if cached is not None:
                value, ts = cached
                age = (datetime.now(UTC) - ts).total_seconds()
                if age <= ENTITY_STALE_MAX_SECONDS:
                    _LOGGER.debug(
                        "Entity %s unavailable; using cached value %.2f (age %.0fs)",
                        entity_id,
                        value,
                        age,
                    )
                    return value
            _LOGGER.warning(
                "Entity %s is unavailable and no recent cached value exists",
                entity_id,
            )
            return None
        try:
            value = float(state.state)
        except (ValueError, TypeError):
            return None
        self._entity_cache[entity_id] = (value, datetime.now(UTC))
        return value
