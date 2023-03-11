"""
Proxy for light entity that export attributes explicitly
"""
import typing
from logging import getLogger

import homeassistant.util.color as color_util
from homeassistant.components import light
from homeassistant.components.light import LightEntity
from homeassistant.helpers.entity import Entity

from .. import utils
from ..action import Action, Function

_LOGGER = getLogger(__name__)

T = typing.TypeVar('T')

MAIN_TURN_ON_PARAMS = (
    light.ATTR_EFFECT,
    light.ATTR_FLASH,
    light.ATTR_TRANSITION,

    light.ATTR_BRIGHTNESS,
    light.ATTR_COLOR_TEMP,
    light.ATTR_COLOR_TEMP_KELVIN,
    light.ATTR_HS_COLOR,
    light.ATTR_RGB_COLOR,
    light.ATTR_RGBW_COLOR,
    light.ATTR_RGBWW_COLOR,
    light.ATTR_WHITE,
    light.ATTR_XY_COLOR,
)

BRIGHTNESS_ATTRS = {
    light.ATTR_BRIGHTNESS, light.ATTR_BRIGHTNESS_PCT, light.ATTR_BRIGHTNESS_STEP, light.ATTR_BRIGHTNESS_STEP_PCT
}

COLOR_TEMP_ATTRS = {
    light.ATTR_COLOR_TEMP, light.ATTR_COLOR_TEMP_KELVIN, light.ATTR_KELVIN,
}

COLOR_ATTRS = {
    light.ATTR_HS_COLOR, light.ATTR_RGB_COLOR, light.ATTR_RGBW_COLOR, light.ATTR_RGBWW_COLOR, light.ATTR_XY_COLOR
}

TURN_OFF_PARAMS = {
    light.ATTR_FLASH, light.ATTR_TRANSITION
}


def _light_turn_on_params(entity: LightEntity) -> set[str]:
    _LOGGER.debug("Get turn on params for %s", entity)
    turn_on_params = set(light.filter_turn_on_params(entity, {i: None for i in MAIN_TURN_ON_PARAMS}))
    _LOGGER.debug("Main params: %s", turn_on_params)
    if turn_on_params.intersection(BRIGHTNESS_ATTRS):
        _LOGGER.debug("Add all brightness params")
        turn_on_params.update(BRIGHTNESS_ATTRS)
    if turn_on_params.intersection(COLOR_TEMP_ATTRS):
        _LOGGER.debug("Remove dedicated temp arguments")
        turn_on_params.difference_update(COLOR_TEMP_ATTRS)
        turn_on_params.add(light.ATTR_COLOR_TEMP_KELVIN)

    result = {light.ATTR_PROFILE, } | turn_on_params
    _LOGGER.debug("Result: %s", result)
    return result


def _light_turn_off_params(entity: LightEntity) -> set[str]:
    _LOGGER.debug("Get turn off params for %s", entity)
    result = set(light.filter_turn_off_params(entity, {i: None for i in TURN_OFF_PARAMS}))
    _LOGGER.debug("Result: %s", result)
    return result


class ParamAction(Action):

    @classmethod
    def create(cls: type[T], bound_method, arguments: set[str]) -> T:
        is_method, args = utils.function_or_method_and_params(bound_method, skip_kwargs=False)
        assert args == ("kwargs",), "Unexpected method"
        assert is_method, "Expect only method"
        instance = getattr(bound_method, "__self__")
        assert instance, "Method without instance"
        _, proxy_call_args = utils.function_or_method_and_params(cls.__call__, skip_kwargs=False)
        unsupported_args = arguments.difference(proxy_call_args)
        assert not unsupported_args, f"Requested arguments does not supported by proxy: {', '.join(unsupported_args)}"
        func = Function(bound_method, None, is_async=utils.is_async(bound_method), arguments=tuple(arguments))
        return typing.cast(TurnOnAction, Action((func,), kwargs={i: None for i in arguments}))


class TurnOnAction(ParamAction):
    def __call__(self, /, profile: str = None,
                 effect: str = None, flash: str = None, transition: float = None,

                 brightness: int = None, brightness_pct: int = None, white: int = None,
                 brightness_step: int = None, brightness_step_pct: int = None,

                 color_temp_kelvin: int = None,

                 hs_color: tuple[float, float] = None,
                 rgb_color: tuple[int, int, int] = None,
                 rgbw_color: tuple[int, int, int, int] = None,
                 rgbww_color: tuple[int, int, int, int, int] = None,
                 xy_color: tuple[float, float] = None,
                 ):
        ...


class TurnOffAction(ParamAction):

    def __call__(self, /,
                 flash: str = None, transition: float = None
                 ):
        ...


class ProxyLightEntity(Entity):
    turn_on: TurnOnAction
    turn_off: TurnOffAction

    _entity: LightEntity
    _turn_on_arguments: set[str]

    def __init__(self, entity: LightEntity):
        assert isinstance(entity, LightEntity), f"Unexpected entity for light proxy {entity}"
        self._entity = entity
        self._turn_on_arguments = _light_turn_on_params(entity)
        self._turn_off_arguments = _light_turn_off_params(entity)
        self.turn_on = TurnOnAction.create(self._async_turn_on, self._turn_on_arguments)
        self.turn_off = TurnOffAction.create(self._async_turn_off, self._turn_off_arguments)

    def __str__(self):
        return f"proxy[{self._entity}]"

    async def _async_turn_on(self, **kwargs):
        _, kwargs = self._validate_turn_on_arguments((), kwargs)
        return await self._entity.async_turn_on(**kwargs)

    def _validate_turn_on_arguments(self, args: tuple, kwargs: dict) -> tuple[tuple, dict]:
        _LOGGER.debug("Validate turn on arguments")
        if args:
            raise ValueError("Position arguments are not allowed")
        kwargs = light.LIGHT_TURN_ON_SCHEMA(kwargs)
        unsupported_args = set(kwargs).difference(self._turn_on_arguments)
        if unsupported_args:
            raise ValueError(f"Unsupported arguments: {', '.join(sorted(unsupported_args))}")
        effect = kwargs.get(light.ATTR_EFFECT)
        if effect is not None and effect not in self._entity.effect_list:
            raise ValueError(f"Unsupported effect `{effect}`")
        profile = kwargs.get(light.ATTR_PROFILE)
        if profile is not None and profile not in self._entity.hass.data[light.DATA_PROFILES].data:
            raise ValueError(f"Unknown profile `{profile}`")
        color_name = kwargs.get(light.ATTR_COLOR_NAME)
        if color_name is not None:
            color_util.color_name_to_rgb(color_name)

        return args, kwargs

    async def _async_turn_off(self, **kwargs):
        _, kwargs = self._validate_turn_off_arguments((), kwargs)
        return await self._entity.async_turn_off(**kwargs)

    def _validate_turn_off_arguments(self, args: tuple, kwargs: dict) -> type[tuple, dict]:
        _LOGGER.debug("Validate turn off arguments")
        if args:
            raise ValueError("Position arguments are not allowed")
        kwargs = light.LIGHT_TURN_OFF_SCHEMA(kwargs)
        unsupported_args = set(kwargs).difference(self._turn_off_arguments)
        if unsupported_args:
            raise ValueError(f"Unsupported arguments: {', '.join(sorted(unsupported_args))}")
        return args, kwargs
