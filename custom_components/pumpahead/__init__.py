"""PumpAhead Home Assistant custom integration."""

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS

_LOGGER = logging.getLogger(__name__)


@dataclass
class PumpAheadData:
    """Runtime data for the PumpAhead integration.

    Placeholder for future coordinator and other runtime objects (issue #45).
    """

    initialized: bool = True


type PumpAheadConfigEntry = ConfigEntry[PumpAheadData]


async def async_setup_entry(hass: HomeAssistant, entry: PumpAheadConfigEntry) -> bool:
    """Set up PumpAhead from a config entry."""
    _LOGGER.debug("Setting up PumpAhead entry: %s", entry.entry_id)

    entry.runtime_data = PumpAheadData()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PumpAheadConfigEntry) -> bool:
    """Unload a PumpAhead config entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    _LOGGER.debug("Unloaded PumpAhead entry: %s (ok=%s)", entry.entry_id, unload_ok)

    return unload_ok
