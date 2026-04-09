"""PumpAhead Home Assistant custom integration."""

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import PumpAheadCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class PumpAheadData:
    """Runtime data for the PumpAhead integration."""

    coordinator: PumpAheadCoordinator


type PumpAheadConfigEntry = ConfigEntry[PumpAheadData]


async def async_setup_entry(hass: HomeAssistant, entry: PumpAheadConfigEntry) -> bool:
    """Set up PumpAhead from a config entry."""
    _LOGGER.debug("Setting up PumpAhead entry: %s", entry.entry_id)

    coordinator = PumpAheadCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = PumpAheadData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload integration when options change (e.g. live control toggle).
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: PumpAheadConfigEntry
) -> None:
    """Reload integration when options are updated."""
    _LOGGER.debug("Options updated for PumpAhead entry: %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PumpAheadConfigEntry) -> bool:
    """Unload a PumpAhead config entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    _LOGGER.debug("Unloaded PumpAhead entry: %s (ok=%s)", entry.entry_id, unload_ok)

    return unload_ok
