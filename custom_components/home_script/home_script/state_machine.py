import typing
from logging import getLogger

import attrs

from .action import Action
from .condition import Condition
from .state_event import StateEvent

_LOGGER = getLogger(__name__)


@attrs.frozen
class State:
    name: str
    condition: Condition
    side_effect: list[Action] | Action | None = attrs.field(hash=False, default=None)
    activated_by: list[StateEvent] | StateEvent | None = attrs.field(hash=False, default=None)
    affect_by: list[StateEvent] | StateEvent | None = attrs.field(hash=False, default=None)
    depend_on: tuple["State", ...] | list[tuple["State", ...]] | None = attrs.field(hash=False, default=None)

    def __attrs_post_init__(self):
        global _state_manager
        _state_manager.add(self)

    def __str__(self):
        return "#" + self.name + "#"

    def __invert__(self) -> "State":
        if self.side_effect is not None:
            raise ValueError("Only states without side_effects can be inverted")
        return attrs.evolve(self, name="NOT " + self.name, condition=~self.condition)


@attrs.define
class StateManager:
    states: set[State] = attrs.field(factory=set)
    state_events: dict[State, list[StateEvent]] = attrs.field(factory=dict)
    state_activate_events: dict[State, list[StateEvent]] = attrs.field(factory=dict)
    state_bases: dict[State, list[list[list[State], Condition | None]]] = attrs.field(factory=dict)

    def add(self, state: State):
        _LOGGER.debug("Add %s", state)
        self.states.add(state)
        if state.activated_by is not None:
            _LOGGER.debug("Add %s that can be activated by events", state)
            event_list = state.activated_by if isinstance(state.activated_by, list) else [state.activated_by]
            self.state_activate_events.setdefault(state, []).extend(event_list)
        if state.affect_by is not None:
            _LOGGER.debug("Add %s that affected by event", state)
            event_list = state.affect_by if isinstance(state.affect_by, list) else [state.affect_by]
            self.state_events.setdefault(state, []).extend(event_list)
        if state.depend_on is not None:
            _LOGGER.debug("Add %s that depends on other states", state)
            depend_list = state.depend_on if isinstance(state.depend_on, list) else [state.depend_on]
            self.state_bases.setdefault(state, []).extend([list(i), None] for i in depend_list)


_state_manager = StateManager()


@attrs.define
class ScriptBuilder:
    state_to_events: dict[State, list[StateEvent]] = attrs.field(factory=dict)

    def build_state_to_event(self):
        self.state_to_events = {}
        all_states = set(_state_manager.states)
        count = 100
        while all_states and count > 0:
            for state in all_states:
                _LOGGER.debug("Try %s", state)
                if self._try_activate_events(state) or self._try_events(state) or self._try_bases(state):
                    all_states.remove(state)
                    break
        return self.state_to_events

    def _try_activate_events(self, state: State) -> bool:
        activate_events = _state_manager.state_activate_events.get(state)
        if activate_events is None:
            return False
        assert state not in _state_manager.state_events, f"{state} both in activated event and state event"
        for event in activate_events:
            _LOGGER.debug("%s is activated by %s", state, event)
            _LOGGER.debug("ADD %s >> %s", state, event)
            self.state_to_events.setdefault(state, []).append(event)
        return True

    def _try_events(self, state: State) -> bool:
        state_events = _state_manager.state_events.get(state)
        if state_events is None:
            return False
        for event in state_events:
            _LOGGER.debug("%s can be activated by %s", state, event)
            _LOGGER.debug("ADD %s >> %s", state, event >> state.condition)
            self.state_to_events.setdefault(state, []).append(event >> state.condition)
        return True

    def _try_bases(self, state: State) -> bool:
        bases = _state_manager.state_bases.get(state)
        if bases is None:
            return False
        _LOGGER.debug("Found bases for %s", state)
        for idx, (base_states, base_condition) in enumerate(bases):
            _LOGGER.debug("Bases states: %s", ", ".join(str(i) for i in base_states))
            if self._try_base_states(state, base_states, base_condition):
                del bases[idx]
                break
        if bases:
            return False
        _LOGGER.debug("All bases for %s processed", state)
        return True

    def _try_base_states(self, main_state: State, base_states: list[State], base_condition: Condition = None) -> bool:
        _LOGGER.debug("Process base states: %s", ", ".join(str(i) for i in base_states))
        events = [self.state_to_events.get(i) for i in base_states]
        if any(i is None for i in events):
            _LOGGER.debug("Can not found events for all bases")
            return False
        for idx, event_list in enumerate(events):
            _LOGGER.debug("%s event list:\n %s", idx, "\n".join(str(i) for i in event_list))
            other_states = list(base_states)
            del other_states[idx]
            _LOGGER.debug("Other states: %s", ", ".join(str(i) for i in other_states))
            if other_states:
                _LOGGER.debug("Process other states, start with base condition %s", base_condition)
                event_condition = base_condition
                for state in other_states:
                    if event_condition is None:
                        event_condition = state.condition
                    elif state.condition is not None:
                        event_condition = event_condition & state.condition
            else:
                _LOGGER.debug("No other states. Use base condition %s", base_condition)
                event_condition = base_condition
            _LOGGER.debug("Event condition: %s", event_condition)
            for event in event_list:
                _LOGGER.debug("For %s add %s with condition %s", main_state, event, event_condition)
                final_event = event if event_condition is None else (event >> event_condition)
                _LOGGER.debug("ADD %s >> %s", main_state, final_event)
                self.state_to_events.setdefault(main_state, []).append(final_event)
        return True

    def build_event_script(self, filter_events: set[State] = None):
        self.build_state_to_event()
        filter_events = filter_events if filter_events is not None else _state_manager.states
        result = {}
        for state, event_list in self.state_to_events.items():
            if state not in filter_events:
                _LOGGER.debug("%s is filtered out")
                continue
            if state.side_effect is None:
                _LOGGER.debug("%s does not have side effects")
                continue
            side_effects = state.side_effect if isinstance(state.side_effect, list) else [state.side_effect]
            for event in event_list:
                result.setdefault(event, []).extend(side_effects)
        return result


def build_script(filter_events: typing.Iterable[State] = None) -> dict[StateEvent, Action]:
    return ScriptBuilder().build_event_script(None if filter_events is None else set(filter_events))
