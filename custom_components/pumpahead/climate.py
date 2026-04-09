"""Climate entities for the PumpAhead integration.

Provides a ``PumpAheadClimateEntity`` per configured room.  Each entity
exposes standard HA climate controls (HVAC mode, target temperature)
and reads its state from the coordinator's ``PumpAheadCoordinatorData``.

When live control is enabled for a room (via options flow toggle), the
coordinator issues service calls to the mapped valve and split entities.
The climate entity itself is a presentation layer -- it does NOT issue
service calls directly.  This keeps the architecture clean: the
coordinator is the single point of control output.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HAS_SPLIT, CONF_ROOM_NAME, CONF_ROOMS, DEFAULT_SETPOINT
from .coordinator import PumpAheadCoordinator

_LOGGER = logging.getLogger(__name__)

# Temperature bounds for the climate entity (degC).
_MIN_TEMP: float = 5.0
_MAX_TEMP: float = 35.0
_TEMP_STEP: float = 0.5

# Map algorithm_mode to HVACMode.
_MODE_TO_HVAC: dict[str, HVACMode] = {
    "heating": HVACMode.HEAT,
    "cooling": HVACMode.COOL,
    "auto": HVACMode.AUTO,
}


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PumpAhead climate entities from a config entry."""
    coordinator: PumpAheadCoordinator = entry.runtime_data.coordinator  # type: ignore[attr-defined]

    entities: list[PumpAheadClimateEntity] = []

    room_configs: list[dict[str, Any]] = entry.data.get(CONF_ROOMS, [])  # type: ignore[assignment]
    for room_cfg in room_configs:
        room_name: str = room_cfg[CONF_ROOM_NAME]
        has_split: bool = room_cfg.get(CONF_HAS_SPLIT, False)
        entities.append(
            PumpAheadClimateEntity(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                room_name=room_name,
                has_split=has_split,
            )
        )

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Climate entity
# ---------------------------------------------------------------------------


class PumpAheadClimateEntity(CoordinatorEntity[PumpAheadCoordinator], ClimateEntity):
    """Climate entity for a single PumpAhead-controlled room.

    Reads its state from the coordinator's ``PumpAheadCoordinatorData``.
    Supports HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, and
    HVACMode.OFF.  Target temperature is stored per-entity and
    propagated to the coordinator.
    """

    _attr_has_entity_name: bool = True
    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step: float = _TEMP_STEP
    _attr_min_temp: float = _MIN_TEMP
    _attr_max_temp: float = _MAX_TEMP
    _enable_turn_on_off_backwards_compatibility: bool = False

    def __init__(
        self,
        coordinator: PumpAheadCoordinator,
        entry_id: str,
        room_name: str,
        has_split: bool,
    ) -> None:
        """Initialize a PumpAhead climate entity.

        Args:
            coordinator: The PumpAhead data coordinator.
            entry_id: Config entry ID for unique_id generation.
            room_name: Room name this entity controls.
            has_split: Whether the room has a split/AC unit.
        """
        super().__init__(coordinator)
        self._room_name = room_name
        self._has_split = has_split
        self._attr_target_temperature: float = DEFAULT_SETPOINT
        self._user_hvac_mode: HVACMode | None = None

        safe_room = room_name.lower().replace(" ", "_")
        self._attr_unique_id = f"{entry_id}_{safe_room}_climate"
        self._attr_name = f"{room_name} Climate"

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the supported features for this entity."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        return [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode.

        If the user has explicitly set a mode, use that.  Otherwise
        derive from the coordinator's algorithm_mode.
        """
        if self._user_hvac_mode is not None:
            return self._user_hvac_mode

        if self.coordinator.data is None:
            return HVACMode.OFF

        algorithm_mode = self.coordinator.data.algorithm_mode
        return _MODE_TO_HVAC.get(algorithm_mode, HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action (heating/cooling/idle/off)."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF

        if self.coordinator.data is None:
            return HVACAction.IDLE

        room_data = self.coordinator.data.rooms.get(self._room_name)
        if room_data is None:
            return HVACAction.IDLE

        # Determine action based on recommended valve output.
        if room_data.recommended_valve is not None and room_data.recommended_valve > 0:
            if self.hvac_mode in (HVACMode.HEAT, HVACMode.AUTO):
                return HVACAction.HEATING
            if self.hvac_mode == HVACMode.COOL:
                return HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature."""
        if self.coordinator.data is None:
            return None
        room_data = self.coordinator.data.rooms.get(self._room_name)
        if room_data is None:
            return None
        return room_data.T_room

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return self._attr_target_temperature

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes for diagnostics."""
        attrs: dict[str, Any] = {
            "room_name": self._room_name,
            "has_split": self._has_split,
        }

        if self.coordinator.data is None:
            return attrs

        room_data = self.coordinator.data.rooms.get(self._room_name)
        if room_data is None:
            return attrs

        attrs["live_control_enabled"] = room_data.live_control_enabled
        attrs["recommended_valve"] = room_data.recommended_valve
        attrs["predicted_temp"] = room_data.predicted_temp
        if self._has_split:
            attrs["split_recommended_mode"] = room_data.split_recommended_mode
            attrs["split_recommended_setpoint"] = (
                room_data.split_recommended_setpoint
            )

        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature.

        Args:
            **kwargs: Must include ``temperature`` key with the target
                value in degrees Celsius.
        """
        temperature: float | None = kwargs.get("temperature")
        if temperature is not None:
            self._attr_target_temperature = temperature
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode.

        Setting OFF disables control output for this room.  Other modes
        override the coordinator's algorithm_mode for display purposes.

        Args:
            hvac_mode: The desired HVAC mode.
        """
        self._user_hvac_mode = hvac_mode
        self.async_write_ha_state()
