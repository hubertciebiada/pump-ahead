"""Config flow for the PumpAhead integration.

Implements a 5-step wizard:
    1. Location (latitude, longitude)
    2. Rooms (name, area, has_split -- loops for multiple rooms)
    3. Entity mapping (per-room sensors + global entities)
    4. Algorithm parameters (mode, weights)
    5. Confirmation

Entity pickers use domain/device_class filtering.  Each selected entity
is validated for correct ``unit_of_measurement`` (Axiom 8: hardware-
agnostic, unit validation only -- degC, %, W).
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import (
    CONF_ADD_ANOTHER,
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
    CONF_ROOM_AREA,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    CONF_W_COMFORT,
    CONF_W_ENERGY,
    CONF_W_SMOOTH,
    DEFAULT_W_COMFORT,
    DEFAULT_W_ENERGY,
    DEFAULT_W_SMOOTH,
    DOMAIN,
    VALID_PERCENT_UNITS,
    VALID_TEMP_UNITS,
)
from .entity_validator import EntityValidator

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Algorithm mode options
# ---------------------------------------------------------------------------

ALGORITHM_MODES: list[str] = ["heating", "cooling", "auto"]


class PumpAheadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Multi-step config flow for PumpAhead."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigFlow,  # type: ignore[override]
    ) -> PumpAheadOptionsFlow:
        """Return the options flow handler."""
        return PumpAheadOptionsFlow()

    def __init__(self) -> None:
        """Initialise mutable flow state."""
        self._location: dict[str, Any] = {}
        self._rooms: list[dict[str, Any]] = []
        self._current_room: dict[str, Any] = {}
        self._algorithm: dict[str, Any] = {}
        self._entity_room_idx: int = 0
        self._global_entities: dict[str, Any] = {}

    # -- Step 1: Location ---------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Location (latitude, longitude)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            lat = user_input.get(CONF_LATITUDE, 0.0)
            lon = user_input.get(CONF_LONGITUDE, 0.0)

            if not -90 <= lat <= 90:
                errors["base"] = "invalid_latitude"
            if not -180 <= lon <= 180:
                errors["base"] = "invalid_longitude"

            if not errors:
                self._location = {
                    CONF_LATITUDE: lat,
                    CONF_LONGITUDE: lon,
                }
                return await self.async_step_rooms()

        default_lat = self.hass.config.latitude
        default_lon = self.hass.config.longitude

        schema = vol.Schema(
            {
                vol.Required(CONF_LATITUDE, default=default_lat): NumberSelector(
                    NumberSelectorConfig(
                        min=-90, max=90, step=0.001, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_LONGITUDE, default=default_lon): NumberSelector(
                    NumberSelectorConfig(
                        min=-180, max=180, step=0.001, mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    # -- Step 2: Rooms ------------------------------------------------------

    async def async_step_rooms(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Room definition (name, area, has_split)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = str(user_input.get(CONF_ROOM_NAME, "")).strip()
            area = user_input.get(CONF_ROOM_AREA, 20.0)
            has_split = user_input.get(CONF_HAS_SPLIT, False)
            add_another = user_input.get(CONF_ADD_ANOTHER, False)

            if not name:
                errors["base"] = "empty_room_name"
            elif any(r[CONF_ROOM_NAME] == name for r in self._rooms):
                errors["base"] = "duplicate_room_name"
            if area <= 0:
                errors["base"] = "invalid_area"

            if not errors:
                self._rooms.append(
                    {
                        CONF_ROOM_NAME: name,
                        CONF_ROOM_AREA: area,
                        CONF_HAS_SPLIT: has_split,
                    }
                )
                if add_another:
                    return await self.async_step_rooms()
                self._entity_room_idx = 0
                return await self.async_step_entities()

        schema = vol.Schema(
            {
                vol.Required(CONF_ROOM_NAME): TextSelector(),
                vol.Required(CONF_ROOM_AREA, default=20.0): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=500, step=0.1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_HAS_SPLIT, default=False): BooleanSelector(),
                vol.Required(CONF_ADD_ANOTHER, default=False): BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="rooms",
            data_schema=schema,
            errors=errors,
        )

    # -- Step 3: Entity mapping ---------------------------------------------

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Entity mapping for the current room."""
        errors: dict[str, str] = {}
        room = self._rooms[self._entity_room_idx]
        room_name = room[CONF_ROOM_NAME]

        if user_input is not None:
            validator = EntityValidator(self.hass)

            # Validate per-room temperature entity (required).
            result = validator.validate_entity(
                user_input.get(CONF_ENTITY_TEMP_ROOM, ""),
                valid_units=VALID_TEMP_UNITS,
                expected_device_class="temperature",
            )
            if not result.valid:
                errors["base"] = result.error_key  # type: ignore[assignment]
                if result.error_details:
                    _LOGGER.warning("%s", result.error_details)

            # Validate optional floor temperature entity.
            floor_entity = user_input.get(CONF_ENTITY_TEMP_FLOOR, "")
            if floor_entity and not errors:
                result = validator.validate_entity(
                    floor_entity,
                    valid_units=VALID_TEMP_UNITS,
                    expected_device_class="temperature",
                )
                if not result.valid:
                    errors["base"] = result.error_key  # type: ignore[assignment]
                    if result.error_details:
                        _LOGGER.warning("%s", result.error_details)

            # Validate optional humidity entity.
            humidity_entity = user_input.get(CONF_ENTITY_HUMIDITY, "")
            if humidity_entity and not errors:
                result = validator.validate_entity(
                    humidity_entity,
                    valid_units=VALID_PERCENT_UNITS,
                    expected_device_class="humidity",
                )
                if not result.valid:
                    errors["base"] = result.error_key  # type: ignore[assignment]
                    if result.error_details:
                        _LOGGER.warning("%s", result.error_details)

            # Validate valve entity (existence only, no unit/device_class).
            valve_entity = user_input.get(CONF_ENTITY_VALVE, "")
            if valve_entity and not errors:
                result = validator.validate_entity(valve_entity)
                if not result.valid and result.error_key != "entity_unavailable":
                    errors["base"] = result.error_key  # type: ignore[assignment]

            # Global entities (only validated for the first room).
            if self._entity_room_idx == 0 and not errors:
                outdoor_entity = user_input.get(CONF_ENTITY_TEMP_OUTDOOR, "")
                if outdoor_entity:
                    result = validator.validate_entity(
                        outdoor_entity,
                        valid_units=VALID_TEMP_UNITS,
                        expected_device_class="temperature",
                    )
                    if not result.valid:
                        errors["base"] = result.error_key  # type: ignore[assignment]
                        if result.error_details:
                            _LOGGER.warning("%s", result.error_details)

            if not errors:
                room[CONF_ENTITY_TEMP_ROOM] = user_input.get(CONF_ENTITY_TEMP_ROOM, "")
                room[CONF_ENTITY_TEMP_FLOOR] = user_input.get(
                    CONF_ENTITY_TEMP_FLOOR, ""
                )
                room[CONF_ENTITY_VALVE] = user_input.get(CONF_ENTITY_VALVE, "")
                room[CONF_ENTITY_HUMIDITY] = user_input.get(CONF_ENTITY_HUMIDITY, "")
                if room[CONF_HAS_SPLIT]:
                    room[CONF_ENTITY_SPLIT] = user_input.get(CONF_ENTITY_SPLIT, "")

                if self._entity_room_idx == 0:
                    self._global_entities = {
                        CONF_ENTITY_TEMP_OUTDOOR: user_input.get(
                            CONF_ENTITY_TEMP_OUTDOOR, ""
                        ),
                        CONF_ENTITY_WEATHER: user_input.get(CONF_ENTITY_WEATHER, ""),
                    }

                self._entity_room_idx += 1
                if self._entity_room_idx < len(self._rooms):
                    return await self.async_step_entities()
                return await self.async_step_algorithm()

        # Build the entity selection schema for this room.
        schema_dict: dict[Any, Any] = {
            vol.Required(CONF_ENTITY_TEMP_ROOM): EntitySelector(
                EntitySelectorConfig(
                    domain=["sensor"],
                    device_class=["temperature"],
                )
            ),
            vol.Optional(CONF_ENTITY_TEMP_FLOOR): EntitySelector(
                EntitySelectorConfig(
                    domain=["sensor"],
                    device_class=["temperature"],
                )
            ),
            vol.Required(CONF_ENTITY_VALVE): EntitySelector(
                EntitySelectorConfig(domain=["number"])
            ),
            vol.Optional(CONF_ENTITY_HUMIDITY): EntitySelector(
                EntitySelectorConfig(
                    domain=["sensor"],
                    device_class=["humidity"],
                )
            ),
        }

        if room[CONF_HAS_SPLIT]:
            schema_dict[vol.Optional(CONF_ENTITY_SPLIT)] = EntitySelector(
                EntitySelectorConfig(domain=["climate"])
            )

        # Global entities shown only for the first room.
        if self._entity_room_idx == 0:
            schema_dict[vol.Required(CONF_ENTITY_TEMP_OUTDOOR)] = EntitySelector(
                EntitySelectorConfig(
                    domain=["sensor"],
                    device_class=["temperature"],
                )
            )
            schema_dict[vol.Optional(CONF_ENTITY_WEATHER)] = EntitySelector(
                EntitySelectorConfig(domain=["weather"])
            )

        schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="entities",
            data_schema=schema,
            errors=errors,
            description_placeholders={"room_name": room_name},
        )

    # -- Step 4: Algorithm parameters ---------------------------------------

    async def async_step_algorithm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Algorithm parameters (mode, weights)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            w_comfort = user_input.get(CONF_W_COMFORT, DEFAULT_W_COMFORT)
            w_energy = user_input.get(CONF_W_ENERGY, DEFAULT_W_ENERGY)
            w_smooth = user_input.get(CONF_W_SMOOTH, DEFAULT_W_SMOOTH)

            if w_comfort < 0 or w_energy < 0 or w_smooth < 0:
                errors["base"] = "invalid_weight"

            if not errors:
                self._algorithm = {
                    CONF_ALGORITHM_MODE: user_input.get(CONF_ALGORITHM_MODE, "heating"),
                    CONF_W_COMFORT: w_comfort,
                    CONF_W_ENERGY: w_energy,
                    CONF_W_SMOOTH: w_smooth,
                }
                return await self.async_step_confirm()

        schema = vol.Schema(
            {
                vol.Required(CONF_ALGORITHM_MODE, default="heating"): SelectSelector(
                    SelectSelectorConfig(options=ALGORITHM_MODES)
                ),
                vol.Required(CONF_W_COMFORT, default=DEFAULT_W_COMFORT): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=100, step=0.01, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_W_ENERGY, default=DEFAULT_W_ENERGY): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=100, step=0.01, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_W_SMOOTH, default=DEFAULT_W_SMOOTH): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=100, step=0.001, mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="algorithm",
            data_schema=schema,
            errors=errors,
        )

    # -- Step 5: Confirmation -----------------------------------------------

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 5: Confirmation and save."""
        if user_input is not None:
            # Build the combined data dict.
            data: dict[str, Any] = {
                **self._location,
                CONF_ROOMS: self._rooms,
                **self._global_entities,
                **self._algorithm,
            }

            # Set unique_id to prevent duplicate entries for same location.
            unique_id = (
                f"{self._location[CONF_LATITUDE]}_{self._location[CONF_LONGITUDE]}"
            )
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title="PumpAhead", data=data)

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "num_rooms": str(len(self._rooms)),
                "algorithm_mode": self._algorithm.get(CONF_ALGORITHM_MODE, "heating"),
                "latitude": str(self._location.get(CONF_LATITUDE, "")),
                "longitude": str(self._location.get(CONF_LONGITUDE, "")),
            },
        )



# ---------------------------------------------------------------------------
# Options flow (per-room live control toggle)
# ---------------------------------------------------------------------------


class PumpAheadOptionsFlow(OptionsFlow):
    """Options flow for PumpAhead -- per-room live control toggle.

    Presents a boolean toggle per room (``enable_live_control_{room_slug}``).
    Defaults to ``False`` (shadow mode).  This is the shadow-to-live
    transition mechanism -- no reconfiguration needed, just toggle in
    options.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options flow init step."""
        rooms: list[dict[str, Any]] = self.config_entry.data.get(CONF_ROOMS, [])  # type: ignore[assignment]

        if user_input is not None:
            # Build live_control map: room_name -> bool.
            live_control: dict[str, bool] = {}
            for room_cfg in rooms:
                room_name: str = room_cfg[CONF_ROOM_NAME]
                safe_key = room_name.lower().replace(" ", "_")
                live_control[room_name] = user_input.get(
                    f"enable_live_control_{safe_key}", False
                )
            return self.async_create_entry(
                title="",
                data={CONF_LIVE_CONTROL: live_control},
            )

        # Build the schema with one boolean toggle per room.
        current_live: dict[str, bool] = self.config_entry.options.get(
            CONF_LIVE_CONTROL, {}
        )

        schema_dict: dict[Any, Any] = {}
        for room_cfg in rooms:
            room_name = room_cfg[CONF_ROOM_NAME]
            safe_key = room_name.lower().replace(" ", "_")
            key = f"enable_live_control_{safe_key}"
            default_val = current_live.get(room_name, False)
            schema_dict[vol.Optional(key, default=default_val)] = BooleanSelector()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
