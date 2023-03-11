import asyncio
import inspect
import types
import typing
from logging import getLogger

import attrs

from . import utils
from .condition import ConditionValue

T = typing.TypeVar('T')

_LOGGER = getLogger(__name__)


class ArgumentsNotCompatible(Exception):
    pass


@typing.overload
def _value(src: ConditionValue[T]) -> T | None: ...


@typing.overload
def _value(src: T) -> T: ...


def _value(src):
    return src() if isinstance(src, ConditionValue) else src


def _is_async(func) -> bool:
    if inspect.iscoroutinefunction(func):
        return True
    real_func = getattr(func, "__func__", None)
    if real_func is not None and inspect.iscoroutinefunction(real_func):
        return True
    return False


@attrs.frozen
class Function:
    function: typing.Callable | types.MethodType | typing.Coroutine = attrs.field()
    instance: object | None = attrs.field()
    is_async: bool = attrs.field()
    arguments: tuple[str, ...] = attrs.field(hash=False, eq=False)

    @staticmethod
    def create(func: typing.Callable | types.MethodType | typing.Coroutine, instance: object | None) -> "Function":
        is_method, params = utils.function_or_method_and_params(func)
        assert not is_method or instance is not None, f"Instance must be provided for unbound function {func}"
        return Function(func, instance, _is_async(func), params)

    def __str__(self):
        of_str = ""
        if self.instance is not None:
            of_str = f"[{self.instance}]"
        elif isinstance(self.function, types.MethodType):
            of_str = f"[{self.function.__self__}]"
        # return f"{self.function.__qualname__}({', '.join(self.arguments)}){of_str}"
        return f"{self.function.__qualname__}{of_str}"

    def run(self, act: "Action"):
        args, kwargs = self.args(act)
        return self.function(*args, **kwargs)

    def args(self, act: "Action") -> tuple[tuple, dict]:
        if len(act.args) > len(self.arguments):
            raise ArgumentsNotCompatible(f"{self} required more arguments than {act} has")
        args = tuple(_value(i) for i in act.args[:len(self.arguments)])
        remain_args = set(self.arguments[len(args):])
        unprovided_args = remain_args.difference(act.kwargs)
        if unprovided_args:
            raise ArgumentsNotCompatible(f"{act} does not has {unprovided_args} arguments that required by {self}")
        kwargs = {i: _value(v) for i, v in act.kwargs.items() if i in remain_args}
        if self.instance:
            args = (self.instance,) + args
        return args, kwargs


@attrs.frozen(slots=True)
class Action(typing.Generic[T]):
    """
    Represent action that can be called from script.

    Action can be run (async or sync) using stored arguments.
    If argument is ConditionValue, it will be resolved before call.

    Actions can be joined by operator "//"
    """
    functions: tuple[Function, ...]
    args: tuple = attrs.field(factory=tuple)
    kwargs: dict = attrs.field(factory=dict)

    def __str__(self):
        async_str = "async " if self.is_async else ""
        of_str = ""
        name = "|".join(str(i) for i in self.functions)
        return f"{async_str}action {name}({self._arg_str()}){of_str}"

    def _arg_str(self):
        args_str = ", ".join(str(i) for i in self.args)
        kwargs_str = ", ".join(f"{k}={v!r}" for k, v in self.kwargs.items() if v is not None)
        if args_str and kwargs_str:
            return args_str + ", " + kwargs_str
        return args_str + kwargs_str

    def __call__(self, *args, **kwargs) -> "Action":
        """
        Get new action with updated arguments.
        """
        if not args and not kwargs:
            return self
        return attrs.evolve(self, args=self.args + args, kwargs=self.kwargs | kwargs)

    @property
    def is_async(self) -> bool:
        return any(i.is_async for i in self.functions)

    def check(self):
        for func in self.functions:
            func.args(self)

    def run(self):
        assert not self.is_async, "Can not run async action"
        for func in self.functions:
            func.run(self)

    async def async_run(self):
        for func in self.functions:
            if func.is_async:
                await func.run(self)
            else:
                func.run(self)

    def __floordiv__(self, other: "Action") -> "Action":
        if other.args:
            raise ValueError("Left action in sequence can not have assigned args")
        common_kwargs = set(self.kwargs) & set(other.kwargs)
        if common_kwargs:
            raise ValueError(f"Actions in sequence has common kwargs: {', '.join(sorted(common_kwargs))}")
        return attrs.evolve(self, functions=self.functions + other.functions)


@attrs.frozen(slots=True)
class ActionDescriptor(typing.Generic[T]):
    function: typing.Callable

    def __get__(self, instance: T | None, owner: type[T] = None):
        if instance is None:
            return self
        return Action((Function.create(self.function, instance),))

    def __set__(self, instance, value):
        raise ValueError(f"{self} can not be set")

    def __str__(self):
        async_str = "async " if _is_async(self.function) else ""
        return f"{async_str}action {self.function.__qualname__} of unbound instance"

    @property
    def is_async(self) -> bool:
        return _is_async(self.function)


def action(func: typing.Callable | Action, *args, **kwargs) -> Action:
    """
    Create a new action using function, static method, method of class ot method of instance.
    """
    if isinstance(func, Action):
        assert not args and not kwargs
        return func(*args, **kwargs)
    if not callable(func):
        raise ValueError("Only function, static method or instance method can be an action ")
    is_method, params = utils.function_or_method_and_params(func)
    if is_method:
        if args or kwargs:
            raise ValueError("Actin descriptor can not be defined with args or kwargs")
        return typing.cast(Action, ActionDescriptor(func))

    return Action((Function.create(func, None),), args=args, kwargs=kwargs)


def sleep(seconds: float) -> Action:
    """
    Create an action that will wait.
    """

    async def _sleep():
        await asyncio.sleep(seconds)

    _sleep.__name__ = f"sleep[{seconds}]"
    _sleep.__qualname__ = _sleep.__name__
    return action(_sleep)
