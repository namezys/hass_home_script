"""
Example is based on using standard helpers from HASS
"""

from logging import getLogger
from . import hass

# from .examples import condition as _ # noqa
# from .examples import bus_event as _ # noqa
# from .examples import state_event as _ # noqa
# from .examples import action as _ # noqa

from home_script import HomeScript
from home_script.condition import condition, property_condition
from home_script.action import action, sleep
from home_script.home_object import HomeObject
from home_script.state_event import state_event

import datetime

_LOGGER = getLogger(__name__)

hs = HomeScript.load(hass)


@condition
def is_night():
    hour = datetime.datetime.now().hour
    return 0 <= hour < 6


class Home(HomeObject):
    somebody_at_home = hs.input_booleans["input_boolean.somebody_at_home"]

    on_away = state_event(somebody_at_home).new("off")


class Entrance(HomeObject):

    class TopLight:
        top_light_on_off = hs.input_booleans["input_boolean.top_light"]
        top_light_brightness = hs.input_numbers["input_number.top_light_brightness"]

        is_on = property_condition(top_light_on_off, "is_on")
        is_off = ~is_on

        turn_on = (
            action(top_light_brightness.async_set_value, value=100) //
            sleep(0.5) //
            action(top_light_on_off.async_turn_on)
        )

        turn_off = action(top_light_on_off.async_turn_off)

        toggle = {
            is_on: turn_off(),
            is_off: turn_on(value=is_night[80, 100]),
        }

    top_light = TopLight()
    switch = hs.input_selects["input_select.switch"]

    on_switch_click = state_event(switch).old("click").new("off")
    on_switch_long_click = state_event(switch).old("click").new("long")


class LivingRoom(HomeObject):
    cinema_mode = hs.input_booleans["input_boolean.cinema_mode"]

    is_cinema_on = property_condition(cinema_mode, "is_on")

    on_cinema_on = state_event(cinema_mode).new("on")


SCRIPT = {
    Entrance.on_switch_click: {
        Entrance.top_light.is_on: Entrance.top_light.turn_off(),
        Entrance.top_light.is_off: {
            ~LivingRoom.is_cinema_on: Entrance.top_light.turn_on(value=is_night[80, 100]),
            LivingRoom.is_cinema_on: Entrance.top_light.turn_on(value=30),
        }
    },
    Entrance.on_switch_long_click: Entrance.top_light.turn_on(value=100),
    LivingRoom.on_cinema_on: {
        Entrance.top_light.is_on: Entrance.top_light.turn_on(value=30),
    },
    Home.on_away: Entrance.top_light.turn_off(),
}


SCRIPT_2 = {
    Entrance.on_switch_click: Entrance.top_light.toggle,
    Entrance.on_switch_long_click: Entrance.top_light.turn_on(value=100),
    LivingRoom.on_cinema_on: {
        Entrance.top_light.is_on: Entrance.top_light.turn_on(value=30),
    },
    Home.on_away: Entrance.top_light.turn_off(),
}

SCRIPT_3 = {
    Entrance.on_switch_click: Entrance.top_light.toggle,
    Entrance.on_switch_long_click: Entrance.top_light.turn_on(value=100),
    LivingRoom.on_cinema_on >> Entrance.top_light.is_on: Entrance.top_light.turn_on(value=30),
    Home.on_away: Entrance.top_light.turn_off(),
}


hs.add_event_script("test", SCRIPT)
