import typing
from logging import getLogger

import attrs
from homeassistant import const, core

from .action import Action
from .script import Script
from .state_event import StateEvent

_LOGGER = getLogger(__name__)
_LOGGER_TRACE = getLogger(__name__ + ".trace")


@attrs.define
class StateChangedManager:
    """
    Wrapper to work with change state events.

    I catch all state change events and look for processing of event by entity id
    """
    hass: core.HomeAssistant
    entity_state_triggers: dict[str, list[tuple[StateEvent, Script, Action]]] = attrs.Factory(dict)
    cancel_callback: core.CALLBACK_TYPE | None = None

    @staticmethod
    def load(hass: core.HomeAssistant) -> "StateChangedManager":
        _LOGGER.debug("Load %s", StateChangedManager)
        instance = StateChangedManager(hass)
        instance.cancel_callback = hass.bus.async_listen(
            event_type=const.EVENT_STATE_CHANGED,
            listener=instance._event_listener,
            run_immediately=True,
        )
        return instance

    def unload(self):
        _LOGGER.debug("Unload %s", self)
        assert self.cancel_callback, "Cancel callback for listener not set"
        self.cancel_callback()

    @core.callback
    def _event_listener(self, event: core.Event) -> None:
        entity_id = event.data['entity_id']
        _LOGGER.debug("Change state event for %s", entity_id)
        old = typing.cast(core.State, event.data['old_state'])
        new = typing.cast(core.State, event.data['new_state'])

        action_plan = {}
        entity_state_triggers = self.entity_state_triggers.get(entity_id, [])
        for state_event, script, action in entity_state_triggers:
            if self._test_state_event(state_event, entity_id, old, new):
                action_plan.setdefault(script, []).append((state_event, action))
        _LOGGER.debug("Found %s script", len(action_plan))
        for script, action_list in action_plan.items():
            _LOGGER.debug("Run actions on %s", script)
            script.cancel_all_tasks()
            for (state_event, action) in action_list:
                _LOGGER.info("TRACE: %s", state_event)
                _LOGGER.info("TRACE: %s", script)
                _LOGGER.info("TRACE: %s", action)
                script.run_action(action)
        _LOGGER.debug("Finish processing of state event")

    @staticmethod
    def _test_state_event(state_event: StateEvent, entity_id: str, old: core.State, new: core.State) -> bool:
        if state_event.condition is None:
            return True
        if state_event.condition(entity_id=entity_id, old=old, new=new):
            return True
        return False

    def add(self, state_event: StateEvent, script: Script, action: Action):
        _LOGGER.debug("Register %s with %s and %s", state_event, script, action)
        assert state_event.entity_id, "Empty entity ID in entity state trigger"
        entity_triggers = self.entity_state_triggers.setdefault(state_event.entity_id, [])
        entity_triggers.append((state_event, script, action))
