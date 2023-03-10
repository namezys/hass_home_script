import asyncio
import importlib
import importlib.util
import inspect
import pathlib
import sys
import types
import typing
from logging import getLogger

import attrs

import const
from homeassistant import core
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP, EVENT_CORE_CONFIG_UPDATE
from .entity import ScriptEntity, StatusEntity
from .scripts_watch_dog import ScriptWatchDog

_LOGGER = getLogger(__name__)

LOAD_DELAY_S = 1
SCRIPT_SUFFIX = (".py", ".Py", ".pY", ".PY")


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
    status_entity: StatusEntity
    watch_dog: ScriptWatchDog | None

    is_loaded: bool = False
    _listeners: list[core.CALLBACK_TYPE] = attrs.field(factory=list)
    _load_task: asyncio.Task | None = None
    _main_module: types.ModuleType | None = None
    _script_modules: dict[str, types.ModuleType] = attrs.field(factory=dict)
    _script_entities: dict[str, ScriptEntity] = attrs.field(factory=dict)

    @staticmethod
    def create(hass: core.HomeAssistant):
        _LOGGER.debug("Load home script integration")
        script_dir = _script_dir(hass)
        _LOGGER.info("Home script directory: %s", script_dir)
        result = HomeScriptIntegration(
            hass=hass,
            script_dir=script_dir,
            status_entity=StatusEntity(hass),
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
            for listener in self._listeners:
                listener()
            self._listeners.clear()
            raise

    def _register_listeners(self, event_type: str, listener: typing.Callable):
        self._listeners.append(self.hass.bus.async_listen_once(event_type, listener))

    @core.callback
    def _hass_started_listener(self, _event: core.Event):
        _LOGGER.debug("HASS started. Plan to load home script")
        self._plan_load_task()

    @core.callback
    def _hass_stopped_listener(self, _event: core.Event):
        _LOGGER.debug("HASS stopped.")
        self.stop_and_unload()

    @core.callback
    def _hass_config_changed_listener(self, _event: core.Event):
        if not self.is_loaded:
            return
        _LOGGER.debug("Config changed. Plan to reload home script")
        self.stop_and_unload()

    @core.callback
    def _watch_dog_script_changed(self):
        _LOGGER.debug("Script changed")
        self._plan_load_task(reload_script=True)

    def _update_status(self, status: str):
        # noinspection PyBroadException
        try:
            self.status_entity.set_status(status)
        except Exception:
            _LOGGER.exception("Can not set status %s", str)

    def _plan_load_task(self, reload_script: bool = False):
        if reload_script and self.is_loaded:
            self.stop_and_unload()
        if self._load_task:
            _LOGGER.debug("Cancel load request")
            self._load_task.cancel()

        async def load_task():
            # noinspection PyBroadException
            try:
                _LOGGER.debug("Delay load of home script %s", LOAD_DELAY_S)
                await asyncio.sleep(LOAD_DELAY_S)
                self.load_and_start()
            except asyncio.CancelledError:
                pass
            except Exception:
                self._update_status(const.STATUS_ERROR)
                _LOGGER.exception("Can not load home script")

        self._update_status(const.STATUS_WAITING)
        self._load_task = self.hass.async_create_task(load_task())

    def load_and_start(self):
        _LOGGER.info("Load home script")
        assert not self.is_loaded, "Home script is loaded yet"
        self._update_status(const.STATUS_LOADING)
        self.watch_dog.start(self._watch_dog_script_changed)
        _LOGGER.info("Run load all home scripts from %s", self.script_dir)
        script_file_list = self.get_script_files()
        _LOGGER.debug("Plan load files %s", len(script_file_list))
        if not script_file_list:
            _LOGGER.info("Skips not found. Skip load")
            self.is_loaded = True
            self._update_status(const.STATUS_NO_SCRIPTS)
            return
        self._load_main_package()
        _LOGGER.debug("Add path to load")
        old_paths = sys.path
        sys.path.insert(0, str(self.script_dir))
        try:
            for script_file in script_file_list:
                self._load_script(script_file)
        finally:
            _LOGGER.debug("Restore paths")
            del sys.path[0]
            assert sys.path == old_paths, "Path is changed after loading"
        _LOGGER.debug("Everything is loaded.")

        self.is_loaded = True
        _LOGGER.info("Load completed")
        self._update_status(const.STATUS_RUN)

    def get_script_files(self) -> list[pathlib.Path]:
        result = []
        for item in self.script_dir.iterdir():
            if not item.is_file():
                _LOGGER.debug("Skip %s because not file", item)
                continue
            if item.suffix not in SCRIPT_SUFFIX:
                _LOGGER.debug("Skip %s because not python script", item)
                continue
            result.append(item)
        return result

    def _load_main_package(self):
        _LOGGER.info("Load main module")
        module_path = pathlib.Path(inspect.getfile(HomeScriptIntegration)) / ".." / "home_script" / "__init__.py"
        module_path = module_path.resolve()
        _LOGGER.debug("Main module path: %s", module_path)
        assert module_path.is_file(), f"Invalid module path {module_path}"
        spec = importlib.util.spec_from_file_location("home_script", module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["home_script"] = module
        spec.loader.exec_module(module)
        _LOGGER.debug("Main module loaded")
        self._main_module = module
        module.init(self.hass, str(__name__).rsplit(".", 1)[0])

    def _load_script(self, path: pathlib.Path):
        _LOGGER.debug("Load %s into %s", path, self)
        module_name = path.with_suffix("").name
        self._set_script_entity_status(module_name, const.STATUS_LOADING)
        # noinspection PyBroadException
        try:
            assert module_name != "home_script", "Module name can not be 'home_script'"
            assert module_name not in self._script_modules, f"Script {module_name} is loaded"
            _LOGGER.debug("Module name %s", module_name)
            if module_name in sys.modules:
                _LOGGER.debug("Module %s loaded", module_name)
                module = sys.modules[module_name]
                loaded_module_path = pathlib.Path(inspect.getfile(module)).resolve()
                assert loaded_module_path == path, \
                    f"Loaded module {module_name} has different path {loaded_module_path} from expected {path}"
            else:
                spec = importlib.util.spec_from_file_location(module_name, path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                _LOGGER.debug("Module loaded successful")
            self._set_script_entity_status(module_name, const.STATUS_RUN)
            self._script_modules[module_name] = module
        except Exception:
            self._set_script_entity_status(module_name, const.STATUS_ERROR)
            _LOGGER.exception("Can not load module %s", module_name)

    def _set_script_entity_status(self, script_name: str, status: str):
        _LOGGER.debug("Set status of %s to %s", script_name, status)
        # noinspection PyBroadException
        try:
            entity = self._script_entities.get(script_name)
            if entity is None:
                entity = ScriptEntity(self.hass, script_name)
                self._script_entities[script_name] = entity
            entity.set_status(status)
        except Exception:
            _LOGGER.exception("Can not set script %s status %s", script_name, status)

    def stop_and_unload(self):
        # noinspection PyBroadException
        try:
            assert self.is_loaded, "Home script is not loaded"
            _LOGGER.info("Stop and unload home script")
            self.watch_dog.stop()

            _LOGGER.info("Unload loaded scripts and home_script module")
            self._main_module.unload()
            self._main_module = None
            _LOGGER.debug("Remove main module from cache")
            del sys.modules['home_script']

            _LOGGER.debug("Remove dependent modules")
            for key, module in list(sys.modules.items()):
                if not inspect.ismodule(module) or getattr(module, "__file__", None) is None:
                    continue
                module_path = str(pathlib.Path(inspect.getfile(module)))
                if module_path.startswith(str(self.script_dir) + "/"):
                    _LOGGER.debug("Unload %s: %s", key, module)
                    del sys.modules[key]
                    if key in self._script_modules:
                        self._script_modules.pop(key)
                        self._set_script_entity_status(key, const.STATUS_STOPPED)
            assert not self._script_modules, f"Some modules not unloaded: {', '.join(sorted(self._script_modules))}"
            _LOGGER.debug("Everything is unloaded")

            _LOGGER.debug("Home script stopped")
            self.is_loaded = False
            self._update_status(const.STATUS_STOPPED)
        except Exception:
            _LOGGER.exception("Error during unload")
