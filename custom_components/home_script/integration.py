import asyncio
import inspect
import pathlib
import typing
from logging import getLogger

import attrs

from homeassistant import core
from homeassistant.const import (EVENT_CORE_CONFIG_UPDATE,
                                 EVENT_HOMEASSISTANT_STARTED,
                                 EVENT_HOMEASSISTANT_STOP)
from homeassistant.util.event_type import EventType
from . import const, entity
from .script_repository import ScriptRepository
from .scripts_watch_dog import ScriptWatchDog

_LOGGER = getLogger(__name__)

# delay to load script in general case
LOAD_DELAY_S = 5
# delay to load script on start up
LOAD_START_DELAY_S = 5


def _script_dir(hass: core.HomeAssistant) -> pathlib.Path:
    assert hass.config.config_dir, "Unknown config director"
    return (pathlib.Path(hass.config.config_dir) / "home_script").resolve()


@attrs.define
class HomeScriptIntegration:
    """
    Home script integration instance has all scripts together.

    During loading, it imports main module, init it with actual instance of HASS core and
    load all custom modules.

    It owns both main module and custom modules.

    In case of reload it disable current instance of main module, remove everything from
    module cache, lost all link and hope that gc will destroy object.
    """
    hass: core.HomeAssistant
    script_dir: pathlib.Path
    status_entity: entity.StatusEntity
    watch_dog: ScriptWatchDog | None
    script_repository: ScriptRepository | None = None

    _listeners: list[core.CALLBACK_TYPE] = attrs.field(factory=list)
    _load_task: asyncio.Task | None = None
    _script_entities: dict[str, entity.ModuleEntity] = attrs.field(factory=dict)

    @staticmethod
    def create(hass: core.HomeAssistant):
        _LOGGER.debug("Load home script integration")
        script_dir = _script_dir(hass)
        _LOGGER.info("Home script directory: %s", script_dir)
        result = HomeScriptIntegration(
            hass=hass,
            script_dir=script_dir,
            status_entity=entity.StatusEntity(hass),
            watch_dog=ScriptWatchDog.create(hass, str(script_dir)),
        )
        result.prepare()
        return result

    def prepare(self):
        _LOGGER.debug("Prepare home script integration to load")
        try:
            self._register_listeners(EVENT_HOMEASSISTANT_STARTED, self._hass_started_listener)
            self._register_listeners(EVENT_HOMEASSISTANT_STOP, self._hass_stopped_listener)
            self._register_listeners(EVENT_CORE_CONFIG_UPDATE, self._hass_config_changed_listener)
        except Exception:
            _LOGGER.exception("Prepare home script failed, remove all listeners")
            self._deregister_all_listeners()
            raise

    def _register_listeners(self, event_type: str | EventType, listener: typing.Callable):
        self._listeners.append(self.hass.bus.async_listen_once(event_type, listener))

    def _deregister_all_listeners(self):
        for listener in self._listeners:
            listener()
        self._listeners.clear()

    @core.callback
    def _hass_started_listener(self, _event: core.Event):
        _LOGGER.debug("HASS started. Plan to load home script")
        self._plan_load_task(load_delay=LOAD_START_DELAY_S)
        self.watch_dog.start(self._watch_dog_script_changed)

    @core.callback
    def _hass_stopped_listener(self, _event: core.Event):
        _LOGGER.debug("HASS stopped.")
        self.watch_dog.stop()
        if self._load_task:
            self._load_task.cancel()
        if self.script_repository:
            self.script_repository.unload()
        _LOGGER.debug("Home script stopped")

    @core.callback
    def _hass_config_changed_listener(self, _event: core.Event):
        _LOGGER.debug("Config changed. Plan to reload home script")
        self._plan_load_task(load_delay=LOAD_START_DELAY_S, force=True)

    @core.callback
    def _watch_dog_script_changed(self):
        _LOGGER.debug("Script changed. Plan to reload home script")
        self._plan_load_task()

    def _plan_load_task(self, load_delay: int = LOAD_DELAY_S, force: bool = False):
        # _LOGGER.debug("Plan load in %s (force %s)", load_delay, force)

        if self._load_task:
            # _LOGGER.debug("Cancel previous load request")
            self._load_task.cancel()

        async def load_task():
            # noinspection PyBroadException
            try:
                # _LOGGER.debug("Delay load of home script %s", load_delay)
                await asyncio.sleep(load_delay)
                self.load_and_start(force)
            except asyncio.CancelledError:
                pass
            except Exception:
                self._update_status(const.STATUS_ERROR)
                # _LOGGER.exception("Can not load home script")
            self._load_task = None

        self._update_status(const.STATUS_WAITING)
        self._load_task = self.hass.async_create_task(load_task())

    def load_and_start(self, force: bool = False):
        module_path = pathlib.Path(inspect.getfile(HomeScriptIntegration)) / ".." / "home_script" / "__init__.py"
        module_path = module_path.resolve()
        new_script_repository = ScriptRepository(module_path, self.script_dir)
        if not force and not new_script_repository.is_different_from(self.script_repository):
            _LOGGER.debug("Script repository is not changed. Skip loading")
            self._update_status(const.STATUS_RUN)
            return

        _LOGGER.info("Load home script")
        if self.script_repository:
            self.script_repository.unload()
            self._update_status(const.STATUS_STOPPED)

        self.script_repository = new_script_repository
        self._update_status(const.STATUS_LOADING)

        self.script_repository.load(self.hass)
        if not self.script_repository.scripts:
            _LOGGER.debug("Scripts not found")
            self._update_status(const.STATUS_NO_SCRIPTS)
        else:
            _LOGGER.debug("Everything is loaded. Home script is running")
            self._update_status(const.STATUS_RUN)

        _LOGGER.info("Load completed")

    def _update_status(self, status: str):
        # noinspection PyBroadException
        try:
            if self.status_entity.state != status:
                _LOGGER.debug("Set integration status %s", status)
                self.status_entity.set_status(status)
        except Exception:
            _LOGGER.exception("Can not set status %s", str)
        self._update_all_script_status()

    def _update_all_script_status(self):
        unknown_scripts = set(self._script_entities)
        if self.script_repository:
            for item in self.script_repository.scripts:
                # STATUS_LOADING, const.STATUS_ERROR, , const.STATUS_STOPPED
                if item.is_loaded:
                    status = const.STATUS_RUN
                elif item.load_error:
                    status = const.STATUS_ERROR
                else:
                    status = const.STATUS_LOADING
                self._set_script_entity_status(item.name, status)
                unknown_scripts.discard(item.name)
        for unknown_name in unknown_scripts:
            _LOGGER.debug("Found unknown script %s", unknown_name)
            self._set_script_entity_status(unknown_name, const.STATUS_ERROR)

    def _set_script_entity_status(self, name: str, status: str) -> None:
        # noinspection PyBroadException
        try:
            script_entity = self._script_entities.get(name)
            if script_entity is None:
                script_entity = self._script_entities[name] = entity.ModuleEntity(self.hass, name)
            if script_entity.state != status:
                _LOGGER.debug("Set status of script %s to %s", name, status)
                script_entity.set_status(status)
        except Exception:
            _LOGGER.exception("Can not set script %s status %s", name, status)
