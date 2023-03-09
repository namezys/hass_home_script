import typing
from logging import getLogger

import attrs
from homeassistant import core
from homeassistant.helpers.entity import Entity

from .condition import Condition, condition_decorator_factory

__all__ = (
    "StateEvent",
    "state_event",
    "state_event_condition",
)

T = typing.TypeVar("T")

_LOGGER = getLogger(__name__)

STATE_EVENT_FILTER_ARGS = {'entity_id', 'old', 'new', }


@attrs.frozen(slots=True)
class StateEvent:
    """
    Event about state changed
    """
    entity_id: str
    condition: Condition | None = attrs.field(default=None)

    # noinspection PyUnresolvedReferences
    @condition.validator
    def _check_condition(self, _attribute, value):
        if value is not None and not value.is_compatible_with_arguments(STATE_EVENT_FILTER_ARGS):
            raise ValueError(f"{value} is not compatible with state event")

    def __str__(self):
        result = f"state event of {self.entity_id}"
        if self.condition is not None:
            return f"{result} with {self.condition}"
        return result

    def __rshift__(self, other: Condition) -> "StateEvent":
        new_condition = other if self.condition is None else (self.condition & other)
        return attrs.evolve(self, condition=new_condition)

    def old(self, acceptable_state: str, *args: str) -> "StateEvent":
        return self >> old_state_condition(acceptable_state, *args)

    def new(self, acceptable_state: str, *args: str) -> "StateEvent":
        return self >> new_state_condition(acceptable_state, *args)


def state_event_condition(f) -> Condition:
    return condition_decorator_factory(STATE_EVENT_FILTER_ARGS)(f)


def old_state_condition(acceptable_state: str, *args: str) -> Condition:
    state_set = {acceptable_state, *args}

    def _condition(entity_id: str, old: core.State, new: core.State):  # noqa
        return old.state in state_set

    _condition.__name__ = f"old_states[{', '.join(sorted(state_set))}]"
    _condition.__qualname__ = _condition.__name__
    return state_event_condition(_condition)


def new_state_condition(acceptable_state: str, *args: str) -> Condition:
    state_set = {acceptable_state, *args}

    def _condition(entity_id: str, old: core.State, new: core.State):  # noqa
        return new.state in state_set

    _condition.__name__ = f"new_states[{', '.join(sorted(state_set))}]"
    _condition.__qualname__ = _condition.__name__
    return state_event_condition(_condition)


def state_event(entity: Entity) -> StateEvent:
    return StateEvent(entity.entity_id)
