import asyncio
import typing
from logging import getLogger

import attrs
from homeassistant import core

from .action import Action

_LOGGER = getLogger(__name__)

T = typing.TypeVar('T')


@attrs.define(hash=True)
class Script:
    """
    Script is list of task.
    Only one task from script can be executed at any time.
    Usually, if new task should start, old tasks must be stopped.

    @ivar tasks: current active task
    """
    hass: core.HomeAssistant
    name: str
    tasks: set[asyncio.Task] = attrs.field(factory=set, hash=False)
    is_stopped: bool = attrs.field(default=False, hash=False)

    def __str__(self):
        args = []
        if self.is_stopped:
            args.append("stopped")
        if self.tasks:
            args.append(f"running tasks {len(self.tasks)}")
        result = f"script {self.name}"
        if self.is_stopped:
            result += " stopped"
        if self.tasks:
            result += f" with running tasks: {', '.join(i.get_name() for i in self.tasks)}"
        return result

    def stop(self):
        """
        Cancel all tasks and stop running any new tasks
        """
        _LOGGER.debug("Stop %s", self)
        self.is_stopped = True
        self.cancel_all_tasks()

    def cancel_all_tasks(self):
        _LOGGER.debug("Cancel all task of %s", self)
        for task in self.tasks:
            _LOGGER.debug("Cancel %s", task)
            task.cancel()

    def _add_task(self, task: asyncio.Task):
        _LOGGER.debug("Add task %s to %s", task, self)
        assert task not in self.tasks, "Duplication of task is impossible"
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def run_action(self, action: Action):
        if self.is_stopped:
            _LOGGER.debug("%s is stopped. Skip running %s", self, action)
            return
        _LOGGER.debug("Run %s of %s", action, self)
        if action.is_async:
            self._run_async_task(action)
        else:
            self._run_simple_task(action)

    def _run_async_task(self, action: Action):
        async def _task():
            try:
                _LOGGER.info("Run async task for %s", action)
                await action.async_run()
                _LOGGER.debug("Success run of %s", action)
            except asyncio.CancelledError:
                _LOGGER.debug("Task was canceled")
            except:  # noqa
                _LOGGER.exception("Error in %s", action)

        _LOGGER.debug("Plan %s", action)
        task = self.hass.async_create_task(_task())
        task.set_name(str(action))
        self._add_task(task)

    @staticmethod
    def _run_simple_task(action: Action):
        try:
            _LOGGER.info("Run %s", action)
            action.run()
            _LOGGER.debug("Success run of %s", action)
        except:  # noqa
            _LOGGER.exception("Error in %s", action)


@attrs.define
class ScriptManager:
    hass: core.HomeAssistant
    scripts: dict[str, Script] = attrs.field(factory=dict)

    @staticmethod
    def load(hass: core.HomeAssistant) -> "ScriptManager":
        return ScriptManager(hass)

    def __getitem__(self, item: str) -> Script:
        assert item, "Empty script name"
        assert isinstance(item, str), "Script name must be string"
        result = self.scripts.get(item)
        if result is None:
            result = Script(self.hass, item)
            self.scripts[item] = result
        return result

    def stop(self):
        _LOGGER.info("Stop all script")
        for script in self.scripts.values():
            script.stop()
