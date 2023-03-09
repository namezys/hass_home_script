from logging import getLogger

from home_script.condition import condition, ConditionValue, Condition, condition_decorator_factory

_LOGGER = getLogger(__name__)


@condition
def is_night() -> bool:
    return True


@condition
def is_day() -> bool:
    return False


# noinspection PyNestedDecorators
class Object:

    def __str__(self):
        return "test_object"

    @condition
    @staticmethod
    def is_static_method():
        return False

    @condition
    def is_method(self) -> bool:
        return False

    def is_other_method(self) -> bool:
        return bool(self)


obj = Object()

_LOGGER.debug("=======================================================================================================")
_LOGGER.debug("Example: condition")

_LOGGER.debug("Global function")
_LOGGER.debug("    %s", is_night)
_LOGGER.debug("    %r", is_night)
_LOGGER.debug("    value: %s", is_night())

_LOGGER.debug("    invert: %s", ~is_night)
_LOGGER.debug("    invert value: %s", (~is_night)())


def _log_dependent_value(condition_value: ConditionValue[int], name: str):
    _LOGGER.debug("    condition value: %s", name)
    _LOGGER.debug("        %s", condition_value)
    _LOGGER.debug("        %r", condition_value)
    _LOGGER.debug("        value: %s", condition_value())


night_value_chose = is_night[80, 100]
_log_dependent_value(night_value_chose, "night or day value")

only_night_value = is_night[50, None]
_log_dependent_value(only_night_value, "only night value")

_LOGGER.debug("Class static method")

_LOGGER.debug("    %s", Object.is_static_method)
_LOGGER.debug("    %r", Object.is_static_method)
_LOGGER.debug("    value %s", Object.is_static_method())

_LOGGER.debug("Class method")

_LOGGER.debug("    %s", Object.is_method)
_LOGGER.debug("    %r", Object.is_method)

_LOGGER.debug("Object static method")

_LOGGER.debug("    %s", obj.is_static_method)
_LOGGER.debug("    %r", obj.is_static_method)
_LOGGER.debug("    value %s", obj.is_static_method())

_LOGGER.debug("Object method")

_LOGGER.debug("    %s", obj.is_method)
_LOGGER.debug("    %r", obj.is_method)
_LOGGER.debug("    value: %s", obj.is_method())
_LOGGER.debug("    invert: %s", ~obj.is_method)
_LOGGER.debug("    invert value: %s", (~obj.is_method)())

method_value = obj.is_method["s", "ss"]

_LOGGER.debug("    value: %s", method_value())

_LOGGER.debug("Manual construction from instance method")

is_other_method = condition(obj.is_other_method)

_LOGGER.debug("    %s", is_other_method)
_LOGGER.debug("    %r", is_other_method)
_LOGGER.debug("    value: %s", is_other_method())

_LOGGER.debug("Logic")


def _log_logic(name: str, c: Condition):
    _LOGGER.debug("    %s: %s = %s", name, c, bool(c))


_log_logic("a & b", is_night & Object.is_static_method)
_log_logic("a & ~b", is_night & ~Object.is_static_method)
_log_logic("~(a & b) & c", ~(is_night & Object.is_static_method) & obj.is_method)
_log_logic("a | b", is_night | Object.is_static_method)
_log_logic("a | ~b", is_night | ~Object.is_static_method)
_log_logic("~(a | b) | c", ~(is_night | Object.is_static_method) & obj.is_method)

_log_logic("a & b | c", is_night & Object.is_static_method | obj.is_method)

_LOGGER.debug("Specified condition")

spec_condition = condition_decorator_factory({'spec'})

_LOGGER.debug("Spec condition")


@spec_condition
def is_spec(spec: int):
    return spec == 123


_LOGGER.debug("    %s", is_spec)
_LOGGER.debug("    %r", is_spec)
_LOGGER.debug("    value: %s", is_spec(spec=11))
_LOGGER.debug("    value: %s", is_spec(spec=123))

spec_value = is_spec["T", "F"]

_LOGGER.debug("    spec value: %s", spec_value)
_LOGGER.debug("    spec value: %r", spec_value)
_LOGGER.debug("    spec value: %s", spec_value(spec=11))
_LOGGER.debug("    spec value: %s", spec_value(spec=123))

_LOGGER.debug("Spec login condition")

spec_and_is_night = is_spec & is_night

_LOGGER.debug("    %s - %s", spec_and_is_night, spec_and_is_night.arguments)
_LOGGER.debug("    %r - %s", spec_and_is_night, spec_and_is_night.arguments)
_LOGGER.debug("    value: %s", spec_and_is_night(spec=11))
_LOGGER.debug("    value: %s", spec_and_is_night(spec=123))

is_day_and_spec = is_day | is_spec

_LOGGER.debug("    %s - %s", is_day_and_spec, is_day_and_spec.arguments)
_LOGGER.debug("    %r - %s", is_day_and_spec, is_day_and_spec.arguments)
_LOGGER.debug("    value: %s", is_day_and_spec(spec=11))
_LOGGER.debug("    value: %s", is_day_and_spec(spec=123))
