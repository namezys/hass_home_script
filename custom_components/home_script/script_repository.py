from __future__ import annotations

import hashlib
import importlib
import importlib.util
import inspect
import logging
import pathlib
import sys
import typing

import attrs

_LOGGER = logging.getLogger(__name__)

MAIN_MODULE = "home_script"
SCRIPT_MODULE = "home_script.custom."

FILE_PATTERS = ("*.py", "*.PY", "*.pY", "*.Py", )


def sha256sum(file_path: pathlib.Path) -> bytes:
    h = hashlib.sha256()
    h.update(file_path.open("rb").read())
    return h.digest()


def _is_script(file_path: pathlib.Path) -> bool:
    return file_path.suffix.lower() == ".py"


@attrs.define
class FileDetails:
    """
    All details about a file that can be useful during loading file as python module.
    """
    script_dir: pathlib.Path
    path: pathlib.Path
    hash_sum: bytes
    is_loaded: bool = False
    is_stopped: bool = False
    load_error: BaseException | None = None

    def __str__(self):
        if not self.is_script:
            return f"file {self.path}"
        name = f"script {self.name}"
        if self.is_loaded:
            return f"loaded {name}"
        if self.is_stopped:
            return f"stopped {name}"
        if self.load_error:
            return f"failed {name} ({self.load_error})"
        return name

    @property
    def is_script(self):
        return (self.script_dir / self.path).parent == self.script_dir

    @property
    def name(self) -> str:
        assert self.is_script, "Only script has name"
        return self.path.with_suffix("").name

    @property
    def full_name(self) -> str:
        return SCRIPT_MODULE + self.name

    def load(self):
        _LOGGER.debug("Load %s", self)
        try:
            assert self.name != "home_script", "Module name can not be 'home_script'"
            assert self.full_name not in sys.modules, f"Module {self.full_name} is loaded"
            spec = importlib.util.spec_from_file_location(self.full_name, self.script_dir / self.path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[self.full_name] = module
            spec.loader.exec_module(module)
            self.is_loaded = True
            _LOGGER.debug("Module loaded successful")
        except Exception as ex:
            _LOGGER.exception("Can not load %s: %s", self, ex)
            self.load_error = ex
            return None
        return module


@attrs.define
class ScriptRepository:
    """
    Get list of scripts from directories.
    Use only ".py" extension of files to get a list of python files

    :ivar script_dir_path: path to directory with script
    :ivar files: all found files
    """
    module_path: pathlib.Path
    script_dir_path: pathlib.Path
    files: dict[pathlib.Path, FileDetails] = attrs.field(init=False, factory=dict)
    main_module: typing.Any = None

    def __attrs_post_init__(self):
        if not self.script_dir_path.exists():
            self._fallback_in_case_of_no_path()
        else:
            self._load_files()

    def __str__(self):
        return f"scripts in {self.script_dir_path}"

    @property
    def scripts(self) -> tuple[FileDetails, ...]:
        return tuple(i for i in self.files.values() if i.is_script)

    @property
    def file_hashes(self) -> dict[pathlib.Path, bytes]:
        return {k: v.hash_sum for k, v in self.files.items()}

    def is_different_from(self, other: ScriptRepository | None) -> bool:
        return other is None or self.file_hashes != other.file_hashes

    def get_script(self, full_name: str) -> FileDetails | None:
        return next((i for i in self.scripts if i.full_name == full_name), None)

    def load(self, hass) -> bool:
        try:
            _LOGGER.info("Loading script from %s", self.script_dir_path)
            _LOGGER.debug("Found %s scripts", len(self.scripts))
            if not self.scripts:
                _LOGGER.debug("Nothing to load")
                return True
            assert len({i.name for i in self.scripts}) == len(self.scripts), "Duplication of script names"
            self._load_main_module(hass)
            old_paths = sys.path
            sys.path.insert(0, str(self.script_dir_path.absolute()))
            modules = []
            try:
                for item in self.scripts:
                    modules.append(item.load())
                modules = [i for i in modules if i]
            finally:
                _LOGGER.debug("Restore paths")
                del sys.path[0]
                assert sys.path == old_paths, "Path is changed after loading"
            if modules:
                self.main_module.load(modules)
        except Exception as ex:
            _LOGGER.exception("Could not load scripts: %s", ex)

    def _load_main_module(self, hass):
        _LOGGER.info("Load main module from %s", self.module_path)
        assert self.module_path.is_file(), f"Invalid module path {self.module_path}"
        spec = importlib.util.spec_from_file_location("home_script", self.module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[MAIN_MODULE] = module
        spec.loader.exec_module(module)
        _LOGGER.debug("Main module loaded")
        self.main_module = module
        module.init(hass, str(__name__).rsplit(".", 1)[0])

    def unload(self):
        if self.main_module is None:
            assert not self.scripts, "Scripts without main module"
            return True
        try:
            self._unload_main_module()
            self._unload_scripts()
        except Exception as ex:
            _LOGGER.exception("Can not unload all scripts: %s", ex)

    def _unload_main_module(self):
        _LOGGER.info("Unload main module %s", self.main_module)
        if self.scripts:
            self.main_module.unload()
        main_module_path = pathlib.Path(self.main_module.__file__).parent.absolute()
        # self.main_module.unload()
        _LOGGER.debug("Remove main module %s (%s) from cache", self.main_module, main_module_path)
        del sys.modules[MAIN_MODULE]

        _LOGGER.debug("Remove submodules and dependent modules")
        for key, module in list(sys.modules.items()):
            if not inspect.ismodule(module) or getattr(module, "__file__", None) is None:
                continue
            module_path = pathlib.Path(inspect.getfile(module)).absolute()
            if main_module_path not in module_path.parents:
                continue
            _LOGGER.debug("Remove submodule %s (%s)", module, module_path)
            del sys.modules[key]

    def _unload_scripts(self):
        _LOGGER.info("Unload scripts from %s", self.script_dir_path)
        for key, module in list(sys.modules.items()):
            if not inspect.ismodule(module) or getattr(module, "__file__", None) is None:
                continue
            module_path = pathlib.Path(inspect.getfile(module))
            if self.script_dir_path in module_path.parents:
                _LOGGER.debug("Unload %s: %s", key, module)
                del sys.modules[key]
                script = self.get_script(key)
                if script:
                    _LOGGER.debug("Unloaded %s", script)
                    script.is_stopped = True
        remain_scripts = [str(i) for i in self.scripts if i.is_loaded and not i.is_stopped]
        assert not remain_scripts, f"Some script was not unloaded: {', '.join(sorted(remain_scripts))}"
        _LOGGER.debug("Everything is unloaded")

    def _fallback_in_case_of_no_path(self):
        _LOGGER.debug("Path %s not found. Create it and use empty script list", self.script_dir_path)
        self.script_dir_path.mkdir(parents=True, exist_ok=True)

    def _load_files(self):
        _LOGGER.debug("Load files from %s", self.script_dir_path)
        for file_glob in FILE_PATTERS:
            for file_path in self.script_dir_path.rglob(file_glob):
                self._process_file(file_path.relative_to(self.script_dir_path))
        _LOGGER.debug("Finish load files")

    def _process_file(self, file_path: pathlib.Path):
        if not _is_script(file_path):
            _LOGGER.debug("Skip %s because not script", file_path)
            return
        if file_path in self.files:
            _LOGGER.debug("Skip processed %s", file_path)
            return
        hash_sum = sha256sum(self.script_dir_path / file_path)
        self.files[file_path] = FileDetails(self.script_dir_path, file_path, hash_sum)
