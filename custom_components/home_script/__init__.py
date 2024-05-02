from logging import getLogger

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from . import integration, const

_LOGGER = getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    "name": str,
    vol.Optional("source", default="home_script"): cv.string,
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    _LOGGER.info("Setup home script integration")
    hass.data[const.DOMAIN] = integration.HomeScriptIntegration.create(hass)
    return True


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_unload_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_remove_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> None:
    pass
