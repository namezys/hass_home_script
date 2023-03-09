from logging import getLogger

from home_script.bus_event import BusEvent, bus_event_condition
from home_script.condition import condition
from homeassistant import core

_LOGGER = getLogger(__name__)


@condition
def is_night() -> bool:
    return True


@bus_event_condition
def is_event_good(event: core.Event) -> bool:
    return bool(event.data)


_LOGGER.debug("=======================================================================================================")
_LOGGER.debug("Example: event")

bus_event = BusEvent("TEST_EVENT_TYPE")

_LOGGER.debug("Event")
_LOGGER.debug("    %s", bus_event)
_LOGGER.debug("    %r", bus_event)

_LOGGER.debug("Event with one filter")
night_bus_event = bus_event >> is_night
_LOGGER.debug("    %s", night_bus_event)
_LOGGER.debug("    %r", night_bus_event)

_LOGGER.debug("Event with two filter")
two_filter_bus_event = bus_event >> is_night >> is_event_good
_LOGGER.debug("    %s", two_filter_bus_event)
_LOGGER.debug("    %r", two_filter_bus_event)
_LOGGER.debug("    %r", bus_event >> (is_night & is_event_good))
_LOGGER.debug("    %r", bus_event >> is_event_good >> is_night)
_LOGGER.debug("    %r", bus_event >> (is_event_good & is_night))

_LOGGER.debug("Event with OR filter")
two_filter_or_bus_event = bus_event >> (is_night | is_event_good)
_LOGGER.debug("    %s", two_filter_or_bus_event)
_LOGGER.debug("    %r", two_filter_or_bus_event)

_LOGGER.debug("Compare")
_LOGGER.debug("    %s", two_filter_bus_event == bus_event >> (is_night & is_event_good))

_LOGGER.debug("Run filters")
_LOGGER.debug("    %s", two_filter_bus_event.condition(event=core.Event("TEST")))
_LOGGER.debug("    %s", two_filter_bus_event.condition(event=core.Event("TEST", data={"a": "b"})))
