"""Shadow mode diagnostic sensors for the PumpAhead integration.

Publishes per-room sensors (recommended valve position, predicted
temperature) and global sensors (algorithm status, last update
timestamp) as HA diagnostic entities.  These sensors are strictly
read-only — shadow mode does not issue any service calls or control
any devices.

All sensors inherit from ``CoordinatorEntity`` and ``SensorEntity``,
reading their values from the coordinator's typed data.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PumpAheadCoordinator, PumpAheadCoordinatorData

# ---------------------------------------------------------------------------
# Sensor descriptions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class PumpAheadSensorEntityDescription(SensorEntityDescription):
    """Extended sensor description with a value extraction function."""

    value_fn: Callable[[PumpAheadCoordinatorData, str | None], Any]


# Per-room sensor descriptions.
ROOM_SENSORS: tuple[PumpAheadSensorEntityDescription, ...] = (
    PumpAheadSensorEntityDescription(
        key="recommended_valve",
        translation_key="recommended_valve",
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda data, room: (
            data.rooms[room].recommended_valve  # type: ignore[index]
            if room and room in data.rooms
            else None
        ),
    ),
    PumpAheadSensorEntityDescription(
        key="predicted_temp",
        translation_key="predicted_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda data, room: (
            data.rooms[room].predicted_temp  # type: ignore[index]
            if room and room in data.rooms
            else None
        ),
    ),
)

# Global sensor descriptions.
GLOBAL_SENSORS: tuple[PumpAheadSensorEntityDescription, ...] = (
    PumpAheadSensorEntityDescription(
        key="algorithm_status",
        translation_key="algorithm_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, _room: data.algorithm_status,
    ),
    PumpAheadSensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, _room: data.last_update_timestamp,
    ),
)


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PumpAhead sensor entities from a config entry."""
    coordinator: PumpAheadCoordinator = entry.runtime_data.coordinator  # type: ignore[attr-defined]

    entities: list[PumpAheadSensorEntity] = []

    # Per-room sensors.
    if coordinator.data is not None:
        for room_name in coordinator.data.rooms:
            for description in ROOM_SENSORS:
                entities.append(
                    PumpAheadSensorEntity(
                        coordinator=coordinator,
                        description=description,
                        entry_id=entry.entry_id,
                        room_name=room_name,
                    )
                )

    # Global sensors.
    for description in GLOBAL_SENSORS:
        entities.append(
            PumpAheadSensorEntity(
                coordinator=coordinator,
                description=description,
                entry_id=entry.entry_id,
                room_name=None,
            )
        )

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Sensor entity
# ---------------------------------------------------------------------------


class PumpAheadSensorEntity(CoordinatorEntity[PumpAheadCoordinator], SensorEntity):
    """Diagnostic sensor entity for PumpAhead shadow mode."""

    entity_description: PumpAheadSensorEntityDescription

    def __init__(
        self,
        coordinator: PumpAheadCoordinator,
        description: PumpAheadSensorEntityDescription,
        entry_id: str,
        room_name: str | None,
    ) -> None:
        """Initialize a PumpAhead sensor entity.

        Args:
            coordinator: The PumpAhead data coordinator.
            description: Sensor entity description with value_fn.
            entry_id: Config entry ID for unique_id generation.
            room_name: Room name for per-room sensors, None for global.
        """
        super().__init__(coordinator)
        self.entity_description = description
        self._room_name = room_name
        self._attr_has_entity_name = True

        if room_name is not None:
            # Per-room sensor: "pumpahead_{room}_{key}"
            safe_room = room_name.lower().replace(" ", "_")
            self._attr_unique_id = f"{entry_id}_{safe_room}_{description.key}"
            self._attr_name = f"{room_name} {description.key.replace('_', ' ')}"
        else:
            # Global sensor: "pumpahead_{key}"
            self._attr_unique_id = f"{entry_id}_{description.key}"
            self._attr_name = f"PumpAhead {description.key.replace('_', ' ')}"

    @property
    def native_value(self) -> Any:
        """Return the sensor value from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data, self._room_name)
