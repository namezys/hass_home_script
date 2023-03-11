import types
import typing
from logging import getLogger

import attrs

from . import utils

__all__ = (
    "Condition",
    "ConditionValue",

    "condition",
    "property_condition",
    "condition_decorator_factory",
)

T = typing.TypeVar("T")

_LOGGER = getLogger(__name__)


@attrs.frozen(slots=True)
class Condition:
    """
    Condition can be True or False.
    Condition can have keyword arguments. All arguments must be provided to get condition value.

    @ivar arguments: list of arguments that must be provided for this condition (None means all argument ignored)
    @ivar is_inverted: invert result
    """
    arguments: frozenset[str] | None = attrs.field()
    is_inverted: bool

    def __call__(self, **kwargs) -> bool:
        assert self.arguments is None or set(kwargs) == self.arguments, \
            f"Expect condition arguments {', '.join(sorted(self.arguments))}, got {', '.join(sorted(kwargs))}"
        if self.is_inverted:
            return not self._run(**kwargs)
        return self._run(**kwargs)

    def __invert__(self: T) -> T:
        return attrs.evolve(self, is_inverted=not self.is_inverted)

    def __bool__(self) -> bool:
        return self()

    def __getitem__(self, item: tuple[T | None, T | None]) -> "ConditionValue[T]":
        return ConditionValue[T](self, item[0], item[1])

    def __and__(self, other: "Condition") -> "Condition":
        arguments = other.arguments if self.arguments is None else self.arguments
        return ConditionAnd(arguments, False, (self, other))

    def __or__(self, other: "Condition") -> "Condition":
        arguments = other.arguments if self.arguments is None else self.arguments
        return ConditionOr(arguments, False, (self, other))

    def _run(self, **kwargs) -> bool:
        raise NotImplemented

    def is_compatible_with_arguments(self, arguments: set[str] | None) -> bool:
        return self.arguments is None or arguments == self.arguments

    def is_compatible(self, other: "Condition"):
        return other.arguments is None or other.arguments == self.arguments

    def short_str(self):
        return "--"


def _validate_filters(instance: Condition, _attribute, value):
    if len(value) < 2:
        raise ValueError("Expect at least tow condition")
    invalid_conditions = [i for i in value if not instance.is_compatible(i)]
    if invalid_conditions:
        raise ValueError(f"Invalid conditions: {', '.join(str(i) for i in invalid_conditions)}")


@attrs.frozen(slots=True)
class ConditionAnd(Condition):
    conditions: tuple[Condition, ...] = attrs.field(validator=_validate_filters)

    def __str__(self):
        return f"condition {self.short_str()}"

    def short_str(self):
        return f"{'NOT ' if self.is_inverted else ''}({' AND '.join(i.short_str() for i in self.conditions)})"

    def _run(self, **kwargs) -> bool:
        assert self.conditions
        for item in self.conditions:
            if not item(**kwargs):
                _LOGGER.debug("Failed %s in statement %s", item, self)
                return False
        # _LOGGER.debug("All of %s is success", self)
        return True

    def __and__(self, other):
        if self.is_inverted:
            return super().__and__(other)
        conditions = self.conditions + (other, )
        if self.arguments is None:
            return attrs.evolve(self, arguments=other.arguments, conditions=conditions)
        return attrs.evolve(self, conditions=conditions)


@attrs.frozen(slots=True)
class ConditionOr(Condition):
    conditions: tuple[Condition, ...] = attrs.field(validator=_validate_filters)

    def __str__(self):
        return f"condition {self.short_str()}"

    def short_str(self):
        return f"{'NOT ' if self.is_inverted else ''}({' OR '.join(i.short_str() for i in self.conditions)})"

    def _run(self, **kwargs) -> bool:
        assert self.conditions
        for item in self.conditions:
            if item(**kwargs):
                # _LOGGER.debug("Success %s in %s", item, self)
                return True
        _LOGGER.debug("All conditions in statement %s is failed", self)
        return False

    def __or__(self, other):
        if self.is_inverted:
            return super().__or__(other)
        conditions = self.conditions + (other, )
        if self.arguments is None:
            return attrs.evolve(self, arguments=other.arguments, conditions=conditions)
        return attrs.evolve(self, conditions=conditions)


@attrs.frozen(slots=True)
class FuncCondition(Condition):
    """
    Independent condition that can be determinate without arguments
    """
    function: typing.Callable[[...], bool] | typing.Callable[[object, ...], bool] = attrs.field()
    instance: object | None = None

    def __str__(self):
        invert_str = 'not ' if self.is_inverted else ''
        # args_str = ', '.join(sorted(self.arguments)) if self.arguments is not None else '*'
        result = f"condition {invert_str}{self.function.__qualname__}"
        if self.instance is not None:
            of_str = f" of {self.instance}"
        elif isinstance(self.function, types.MethodType):
            of_str = f" of {self.function.__self__}"
        else:
            of_str = ""
        return result + of_str

    def short_str(self):
        invert_str = 'NOT ' if self.is_inverted else ''
        # args_str = ', '.join(sorted(self.arguments)) if self.arguments is not None else '*'
        result = f"{invert_str}{self.function.__qualname__}"
        if self.instance is not None:
            of_str = f" of {self.instance}"
        elif isinstance(self.function, types.MethodType):
            of_str = f" of {self.function.__self__}"
        else:
            of_str = ""
        return result + of_str

    def _run(self, **kwargs) -> bool:
        if self.arguments is None:
            kwargs = {}
        return self.function(**kwargs) if self.instance is None else self.function(self.instance, **kwargs)


@attrs.frozen(slots=True, repr=False)
class ConditionValue(typing.Generic[T]):
    condition: Condition = attrs.field()
    true_case: T | None
    false_case: T | None

    # noinspection PyUnresolvedReferences
    @condition.validator
    def _check_condition(self, _attribute, value):
        if not isinstance(value, Condition):
            raise ValueError("Invalid condition type")

    def __str__(self):
        return f"{self.true_case} if {self.condition} else {self.false_case}"

    def __repr__(self):
        return f"<{self.condition.short_str()}[{self.true_case}, {self.false_case}]>"

    def __call__(self, **kwargs) -> T | None:
        return self.true_case if self.condition(**kwargs) else self.false_case


@attrs.frozen(slots=True)
class ConditionDescriptor:
    arguments: set[str] | None
    function: typing.Callable[[object, ...], bool]

    def __get__(self, instance: T | None, owner: type[T] = None):
        if instance is None:
            return self
        return FuncCondition(self.arguments, False, self.function, instance)

    def __set__(self, instance, value):
        raise ValueError(f"{self} can not be changed")

    def __str__(self):
        return f"condition {self.function.__qualname__} of unbound instance"


def condition_decorator_factory(arguments: set[str] | None) -> typing.Callable[[typing.Callable], Condition]:
    arguments = frozenset(arguments) if arguments is not None else None

    def _condition(func: typing.Callable[[], bool] | typing.Callable[[object], bool]):
        if not callable(func):
            raise ValueError("Only function, static method or instance method can be a condition")
        is_method, params = utils.function_or_method_and_params(func)
        if arguments is None and params or arguments is not None and frozenset(params) != arguments:
            raise ValueError(f"Condition can not have parameters, got: {', '.join(sorted(params))}")
        if is_method:
            return ConditionDescriptor(arguments, func)
        return FuncCondition(arguments, False, func)

    return _condition


def condition(func) -> Condition:
    return condition_decorator_factory(None)(func)


def property_condition(instance, attr) -> Condition:
    if not hasattr(instance, attr):
        raise ValueError(f"{instance} does not have attribute {attr}")

    def _f():
        return getattr(instance, attr)

    _f.__name__ = f"property {attr}[{instance}]"
    _f.__qualname__ = _f.__name__
    return condition(_f)
