import typing
from logging import getLogger

from homeassistant import core
from homeassistant.helpers.entity import Entity

from . import const

_LOGGER = getLogger(__name__)


class StatusEntity(Entity):
    """
    Status of integration
    """

    _attr_name = "Home Script"
    _status = None
    entity_id = const.STATUS_ENTITY_ID

    def __init__(self, hass: core.HomeAssistant):
        self.hass = hass
        self._status = const.STATUS_INVALID

    def set_status(self, status: str):
        assert status in const.STATUS_SET, "Invalid status"
        self._status = status
        self.async_write_ha_state()

    @property
    def state(self) -> typing.Literal["invalid", "waiting", "loading", "run"]:
        return self._status

    @property
    def extra_state_attributes(self) -> dict[str, typing.Any]:
        return {}


class ModuleEntity(Entity):
    """
    Status of each script.

    Entity is exists only for existing scripts
    """

    _attr_name = "Home Script Module"
    _status = const.STATUS_INVALID

    def __init__(self, hass: core.HomeAssistant, script_name: str):
        self.hass = hass
        self.entity_id = f"{const.DOMAIN}.module_{script_name}"
        self._attr_name = f"Custom home script module {script_name}"

    def set_status(self, status: str):
        assert status in [const.STATUS_LOADING, const.STATUS_ERROR, const.STATUS_RUN, const.STATUS_STOPPED], \
            "Invalid status"
        self._status = status
        self.async_write_ha_state()

    @property
    def state(self) -> str:
        return self._status
