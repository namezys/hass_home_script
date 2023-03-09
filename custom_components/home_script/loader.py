import asyncio
import importlib
import importlib.util
import inspect
import pathlib
import sys
import types
from logging import getLogger

import attrs
from homeassistant import core

_LOGGER = getLogger(__name__)

SCRIPT_SUFFIX = (".py", ".Py", ".pY", ".PY")
LOAD_DELAY_S = 1


@attrs.define
class Loader:
    """
    Loader load main module, init it with actial instance of HASS core and
    load all custom modules.

    It owns both main module and custom modules.

    In case of reload it disable current instance of main module, remove everything from
    module cache, lost all link and hope that gc will destroy object.
    """
    hass: core.HomeAssistant
    main_module: types.ModuleType | None = None
    scripts: dict[str, types.ModuleType] = attrs.field(factory=dict)

    @property
    def config_dir(self) -> pathlib.Path:
        assert self.hass.config.config_dir, "Unknown config director"
        return (pathlib.Path(self.hass.config.config_dir) / "home_script").resolve()

    def load(self):
        _LOGGER.info("Run load all home scripts from %s", self.config_dir)
        script_file_list = self.get_script_path()
        _LOGGER.debug("Plan load files %s using %s", len(script_file_list), self)
        if not script_file_list:
            _LOGGER.info("Skips not found. Skip load")
            return
        self._load_main_package()
        _LOGGER.debug("Add path to load")
        old_paths = sys.path
        sys.path.insert(0, str(self.config_dir))
        try:
            for script_file in script_file_list:
                self._load_script(script_file)
        finally:
            _LOGGER.debug("Restore paths")
            del sys.path[0]
            assert sys.path == old_paths, "Path is changed after loading"
        _LOGGER.debug("Everything is loaded")

    def get_script_path(self) -> list[pathlib.Path]:
        result = []
        for item in self.config_dir.iterdir():
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
        module_path = pathlib.Path(inspect.getfile(Loader)) / ".." / "scripts" / "home_script" / "__init__.py"
        module_path = module_path.resolve()
        _LOGGER.debug("Main module path: %s", module_path)
        assert module_path.is_file(), f"Invalid module path {module_path}"
        spec = importlib.util.spec_from_file_location("home_script", module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["home_script"] = module
        spec.loader.exec_module(module)
        _LOGGER.debug("Main module loaded")
        self.main_module = module
        module.init(self.hass, str(__name__).rsplit(".", 1)[0])

    def _load_script(self, path: pathlib.Path):
        _LOGGER.debug("Load %s into %s", path, self)
        module_name = path.with_suffix("").name
        assert module_name != "home_script", "Module name can not be 'home_script'"
        assert module_name not in self.scripts, f"Script {module_name} is loaded"
        _LOGGER.debug("Module name %s", module_name)
        if module_name in sys.modules:
            _LOGGER.debug("Module %s loaded", module_name)
            module = sys.modules[module_name]
            loaded_module_path = pathlib.Path(inspect.getfile(module)).resolve()
            assert loaded_module_path == path, \
                f"Loaded module {module_name} has different path {loaded_module_path} from expected {path}"
            self.scripts[module_name] = module
            return
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        self.scripts[module_name] = module
        _LOGGER.debug("Module loaded successful")

    def unload(self):
        _LOGGER.info("Unload loaded scripts and home_script module")
        self.main_module.unload()
        self.main_module = None
        _LOGGER.debug("Remove main module from cache")
        del sys.modules['home_script']
        for item in list(sys.modules):
            if item.startswith("home_script."):
                _LOGGER.debug("Remove submodule %s", item)
                del sys.modules[item]
        _LOGGER.debug("Remove dependent modules")
        for key, module in list(sys.modules.items()):
            if not inspect.ismodule(module) or getattr(module, "__file__", None) is None:
                continue
            module_path = str(pathlib.Path(inspect.getfile(module)))
            if module_path.startswith(str(self.config_dir) + "/"):
                _LOGGER.debug("Unload %s: %s", key, module)
                del sys.modules[key]
        _LOGGER.debug("Everything is unloaded")


loader: Loader | None = None
load_task: asyncio.Task | None = None


def _clear_load_task(_):
    global load_task
    load_task = None


async def load_all_script(hass: core.HomeAssistant, delay: int):
    global loader
    _LOGGER.debug("Sleep for %s seconds", delay)
    await asyncio.sleep(delay)
    _LOGGER.info("Load all scripts")
    if loader is not None:
        loader.unload()
        loader = None
    loader = Loader(hass)
    loader.load()
    _LOGGER.debug("Load completed")
    loader.unload()


def create_listener(hass: core.HomeAssistant):
    @core.callback
    def event_listener(*args, **kwargs):
        global load_task
        _LOGGER.info("Plan load scripts in %s seconds", LOAD_DELAY_S)
        if load_task is not None:
            _LOGGER.debug("Cancel planned load")
            load_task.cancel()
            load_task = None
        load_task = hass.async_create_task(load_all_script(hass, LOAD_DELAY_S))
        load_task.add_done_callback(_clear_load_task)

    return event_listener
