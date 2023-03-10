import inspect
import pathlib
from logging import getLogger

_LOGGER = getLogger(__name__)


SCRIPT = """
stubgen -v -p homeassistant --ignore-errors --include-private -o "{script_dir}"
stubgen -v --ignore-errors --include-private "{module_dir}" -o "{script_dir}"
mv "{script_dir}/custom_components/home_script/home_script" "{script_dir}/home_script"
rm -rf "{script_dir}/custom_components"
rm -rf "{script_dir}/.mypy_cache"
"""


def generate_stub_files(script_dir: pathlib.Path):
    # Looks like there is only one way to generate stub in more or less correct way: run stubgen.
    # However, it is being developing and it's important to use dev version instead of included in HASS-OS.
    # So I decided to generate script that can run it instead of run it automatically
    module_dir = (pathlib.Path(inspect.getfile(generate_stub_files)) / ".." / "home_script").resolve()
    _LOGGER.debug("Generate stub script %s", script_dir)
    with (script_dir / "gen_stubs.sh").open("w") as f:
        f.write(SCRIPT.format(script_dir=script_dir, module_dir=module_dir))
