from logging import getLogger

from home_script import StateEvent, state_event_condition, condition

from homeassistant import core

_LOGGER = getLogger(__name__)

state_event = StateEvent("light.top_light")


@condition
def is_night() -> bool:
    return True


# can not skip unused arguments in condition
# noinspection PyUnusedLocal
@state_event_condition
def is_good(entity_id: str, old: core.State, new: core.State) -> bool:
    return new.state == "3"


_LOGGER.debug("=======================================================================================================")
_LOGGER.debug("Example: state event")
_LOGGER.debug("     %s", state_event)
_LOGGER.debug("     %s", state_event)

_LOGGER.debug("With condition")
is_night_state_event = state_event >> is_night
_LOGGER.debug("    %s", is_night_state_event)
_LOGGER.debug("    %r", is_night_state_event)

_LOGGER.debug("With state event condition")
is_good_state_event = state_event >> is_good
_LOGGER.debug("    %s", is_good_state_event)
_LOGGER.debug("    %r", is_good_state_event)

_LOGGER.debug("With multiply conditions")
is_night_is_good_state_event = state_event >> is_night >> is_good
is_good_is_night_state_event = state_event >> is_good >> is_night
_LOGGER.debug("    %s", is_night_is_good_state_event)
_LOGGER.debug("    %s", state_event >> (is_night & is_good))
_LOGGER.debug("    %s", is_good_is_night_state_event)
_LOGGER.debug("    %s", state_event >> (is_night | is_good))

_LOGGER.debug("Old and new filters")
_LOGGER.debug("    %s", state_event.old("1", "3"))
_LOGGER.debug("    %s", state_event.new("4", "3"))
_LOGGER.debug("    %s", state_event.old("1", "2").new("4", "3"))

_LOGGER.debug("Compare: ")
_LOGGER.debug("    expect True: %s", is_night_is_good_state_event == (state_event >> (is_night & is_good)))

state_1 = core.State("a.a", "1")
state_2 = core.State("a.a", "2")
state_3 = core.State("a.a", "3")

_LOGGER.debug("Filters:")

_LOGGER.debug("   %s", is_night_is_good_state_event.condition(entity_id="a.a", old=state_1, new=state_2))
_LOGGER.debug("   %s", is_night_is_good_state_event.condition(entity_id="a.a", old=state_1, new=state_3))

old_new_state = state_event.old("1", "2").new("3")

_LOGGER.debug("   %s", old_new_state.condition(entity_id="a.a", old=state_3, new=state_1))
_LOGGER.debug("   %s", old_new_state.condition(entity_id="a.a", old=state_2, new=state_3))
