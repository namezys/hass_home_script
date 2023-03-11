"""
Home script module is interface to access to HASS from home scripts
"""

import typing
from logging import getLogger

import attrs
from homeassistant import core
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.counter import Counter
from homeassistant.components.input_boolean import InputBoolean
from homeassistant.components.input_number import InputNumber
from homeassistant.components.input_select import InputSelect
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sun import Sun
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import Entity

from .action import Action, action, sleep
from .bus_event import BusEvent, bus_event, bus_event_condition
from .components import ComponentEntities, ProxyComponentEntities
from .condition import Condition, ConditionValue, condition, property_condition
from .home_object import HomeObject
from .proxies.light import ProxyLightEntity as LightEntity
from .schema import EVENT_SCHEMA, normalize_schema
from .script import Script, ScriptManager
from .state_event import StateEvent, state_event, state_event_condition
from .state_event_manager import StateChangedManager
from .utils import format_schema

_LOGGER = getLogger(__name__)

EntityT = typing.TypeVar('EntityT', bound=Entity)

__all__ = [
    "Action",
    "action",
    "sleep",

    "BusEvent",
    "bus_event_condition",
    "bus_event",

    "Condition",
    "ConditionValue",
    "condition",
    "property_condition",

    "HomeObject",

    "StateEvent",
    "state_event_condition",
    "state_event",

    "format_schema",

    "BinarySensorEntity",
    "Counter",
    "InputBoolean",
    "InputNumber",
    "InputSelect",
    "LightEntity",
    "SensorEntity",
    "SwitchEntity",
]


@attrs.define
class HomeScript:
    hass: core.HomeAssistant
    state_event_manager: StateChangedManager | None
    script_manager: ScriptManager
    sun: Sun
    binary_sensors: ComponentEntities[BinarySensorEntity]
    counter: ComponentEntities[Counter]
    input_booleans: ComponentEntities[InputBoolean]
    input_numbers: ComponentEntities[InputNumber]
    input_selects: ComponentEntities[InputSelect]
    lights: ProxyComponentEntities[LightEntity]
    sensors: ComponentEntities[SensorEntity]
    switches: ComponentEntities[SwitchEntity]

    @staticmethod
    def load(hass: core.HomeAssistant) -> 'HomeScript':
        _LOGGER.debug("Load %s", HomeScript)
        return HomeScript(
            hass=hass,
            state_event_manager=StateChangedManager.load(hass),
            script_manager=ScriptManager.load(hass),
            sun=hass.data['sun'],
            binary_sensors=ComponentEntities.load(hass, "binary_sensor"),
            counter=ComponentEntities.load(hass, "counter"),
            input_booleans=ComponentEntities.load(hass, "input_boolean"),
            input_numbers=ComponentEntities.load(hass, "input_number"),
            input_selects=ComponentEntities.load(hass, "input_select"),
            lights=ProxyComponentEntities.load(hass, "light", LightEntity),
            sensors=ComponentEntities.load(hass, "sensor"),
            switches=ComponentEntities.load(hass, "switch"),
        )

    def unload(self):
        _LOGGER.debug("Unload %s", self)
        self.state_event_manager.unload()
        self.state_event_manager = None

    def add_event_script(self, script_name: str, event_schema: EVENT_SCHEMA):
        _LOGGER.info("Add event schema to script %s", script_name)
        schema_script = self.script_manager[script_name]
        normal_schema = schema.normalize_schema(event_schema)
        _LOGGER.debug("Add %s schema items", len(normal_schema))
        for event, action_list in normal_schema.items():
            if isinstance(event, StateEvent):
                self._add_state_event_actions(event, schema_script, action_list)
            else:
                raise AssertionError(f"Unknown event {event} of type {type(event)}. Expect {StateEvent}")
        _LOGGER.debug("Schema was added")

    def _add_state_event_actions(self, event: StateEvent, schema_script: Script, action_list: list[Action]):
        _LOGGER.debug("Add %s to state event manager", event)
        for item in action_list:
            self.state_event_manager.add(event, schema_script, item)


home_script: HomeScript = None
logger_name: str = None


def init(hass: core.HomeAssistant, module_logger_name: str):
    global home_script
    global logger_name
    assert home_script is None, "Init before unload"
    _LOGGER.info("Load main module home script")
    home_script = HomeScript.load(hass)
    logger_name = module_logger_name


def unload():
    global home_script
    assert home_script is not None, "Unload without load"
    home_script.unload()
    home_script = None


def get_logger(name: str):
    global logger_name
    if name.startswith("home_script."):
        return getLogger(name)
    return getLogger(logger_name + ".custom_module." + name)
