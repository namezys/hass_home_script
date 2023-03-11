import inspect
import typing
from logging import getLogger

_LOGGER = getLogger(__name__)

__all__ = (
    "function_or_method_and_params",
    "format_schema",
)


def function_or_method_and_params(func_or_method: typing.Callable, skip_kwargs: bool = True) -> tuple[bool, tuple[str]]:
    signature = inspect.signature(func_or_method)
    skip_set = ("args", "kwargs") if skip_kwargs else ()
    params = tuple(i for i in signature.parameters if i not in skip_set)
    is_method = bool(params) and "self" == params[0]
    if is_method:
        params = params[1:]
    return is_method, params


def is_async(func) -> bool:
    if inspect.iscoroutinefunction(func):
        return True
    real_func = getattr(func, "__func__", None)
    if real_func is not None and inspect.iscoroutinefunction(real_func):
        return True
    return False


def format_schema(value, ind=0) -> str:
    """
    Output event/condition schema in beautiful (at least readable way)
    """
    ind_s = " " * ind
    ind_ss = " " * (ind + 2)
    if isinstance(value, dict):
        lines = (f"{ind_ss}{k}: {format_schema(v, ind + 2)}" for k, v in value.items())
        internal = ", \n".join(lines)
        return "{\n" + internal + "\n" + ind_s + "}"
    if isinstance(value, list):
        lines = (f"{ind_ss}{format_schema(i, ind + 2)}" for i in value)
        internal = ", \n".join(lines)
        return "[\n" + internal + "\n" + ind_s + "]"
    return str(value)
