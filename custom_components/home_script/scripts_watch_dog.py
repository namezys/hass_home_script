import typing
from logging import getLogger

import attrs
import watchdog
import watchdog.observers
from watchdog.events import FileSystemEvent, FileSystemEventHandler, FileSystemMovedEvent

from homeassistant import core

_LOGGER = getLogger(__name__)


def _is_skip(path):
    path = str(path)
    return path.endswith("~") or "/__pycache__" in path


class WatchDogHandler(FileSystemEventHandler):
    """
    Class for handling watchdog events.

    To avoid firing many event in case of consequence changes, collect events
    """
    hass: core.HomeAssistant
    callback: typing.Callable[..., None] | None = None

    def __init__(self, hass: core.HomeAssistant):
        self.hass = hass

    def process(self, event: FileSystemEvent) -> None:
        """Send watchdog events to main loop task."""
        _LOGGER.debug("Watchdog found change in directory with scripts: %s", event)
        callback = self.callback
        if callback:
            # noinspection PyTypeChecker
            self.hass.add_job(self.callback)

    def on_modified(self, event: FileSystemEvent) -> None:
        """File modified."""
        if _is_skip(event.src_path) or event.is_directory:
            return
        self.process(event)

    def on_moved(self, event: FileSystemMovedEvent) -> None:
        """File moved."""
        if _is_skip(event.src_path) and _is_skip(event.dest_path):
            return
        self.process(event)

    def on_created(self, event: FileSystemEvent) -> None:
        """File created."""
        if _is_skip(event.src_path):
            return
        self.process(event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        """File deleted."""
        if _is_skip(event.src_path):
            return
        self.process(event)


@attrs.define
class ScriptWatchDog:
    handler: WatchDogHandler
    script_dir: str
    observer: watchdog.observers.Observer | None = None

    @staticmethod
    def create(hass: core.HomeAssistant, script_dir: str):
        handler = WatchDogHandler(hass)
        return ScriptWatchDog(handler, script_dir)

    def start(self, callback: typing.Callable):
        _LOGGER.debug("Start watch dog")
        assert self.observer is None, "Restart without stop"
        self.handler.callback = callback
        self.observer = watchdog.observers.Observer()
        self.observer.schedule(self.handler, self.script_dir, recursive=True)
        self.observer.start()

    def stop(self):
        _LOGGER.debug("Stop watch dog")
        self.observer.stop()
        self.observer.join()
        self.handler.callback = None
        self.observer = None
