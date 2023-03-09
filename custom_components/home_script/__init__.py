from logging import getLogger

import voluptuous as vol
from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED

from .const import DOMAIN
from .loader import create_listener

_LOGGER = getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    "name": str
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    _LOGGER.info("Setup home script integration")
    _LOGGER.debug("Add load scripts after HASS started")
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, create_listener(hass))
    return True


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_unload_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_remove_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> None:
    pass
