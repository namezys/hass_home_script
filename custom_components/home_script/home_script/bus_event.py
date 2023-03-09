import typing
from logging import getLogger

import attrs

from .condition import Condition, condition_decorator_factory

__all__ = (
    "BusEvent",
    "bus_event",
    "bus_event_condition",
)

T = typing.TypeVar("T")

_LOGGER = getLogger(__name__)

EVENT_FILTER_ARGS = {'event', }


@attrs.frozen(slots=True)
class BusEvent:
    """
    HASS event that defined only by type.

    TODO: implement wait
    """
    event_type: str
    condition: Condition | None = attrs.field(default=None)

    # noinspection PyUnresolvedReferences
    @condition.validator
    def _check_condition(self, _attribute, value):
        if value is not None and not value.is_compatible_with_arguments(EVENT_FILTER_ARGS):
            raise ValueError(f"{value} is not compatible with bus event filter")
        return value

    def __str__(self):
        result = f"bus event {self.event_type}"
        if self.condition is not None:
            return f"{result} with filter {self.condition}"
        return result

    def __rshift__(self, other: Condition) -> "BusEvent":
        new_filter = other if self.condition is None else (self.condition & other)
        return attrs.evolve(self, condition=new_filter)


def bus_event_condition(func) -> Condition:
    """
    Create condition with argument "event: core.Event"
    """
    return condition_decorator_factory(EVENT_FILTER_ARGS)(func)


def bus_event(event_type: str) -> BusEvent:
    """
    Create bus event of provided type
    """
    return BusEvent(event_type)
