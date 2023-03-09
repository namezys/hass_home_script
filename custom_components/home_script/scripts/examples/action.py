from logging import getLogger

from home_script import action

_LOGGER = getLogger(__name__)


@action
def global_action():
    _LOGGER.debug("       -> global action")


@action
async def async_global_action():
    _LOGGER.debug("       -> async_global action")


def second_global_function(a, b):
    _LOGGER.debug("       -> second global function: %s and %s", a, b)


async def async_second_global_function(a, b):
    _LOGGER.debug("       -> second global function: %s and %s", a, b)


double_global_action = action(global_action)


# noinspection PyNestedDecorators
class Object:
    global_function = action(second_global_function, 1, b="b")
    async_global_function = action(async_second_global_function, 2, b="a")

    @action
    @staticmethod
    def static_method():
        _LOGGER.debug("        -> static method")

    @action
    @staticmethod
    async def async_static_method():
        _LOGGER.debug("        -> async_static method")

    @action
    def method(self):
        _LOGGER.debug("        -> method")

    @action
    async def async_method(self):
        _LOGGER.debug("        -> async method")

    def simple_method(self, a, c):
        _LOGGER.debug("        -> simple method: %s:%s:%s", self, a, c)

    async def async_simple_method(self, b, c):
        _LOGGER.debug("        -> async simple method: %s:%s:%s", self, b, c)

    def __str__(self):
        return "test_object"


obj = Object()

_LOGGER.debug("=======================================================================================================")
_LOGGER.debug("Example: action")

_LOGGER.debug("global")

_LOGGER.debug("    %s", global_action)
_LOGGER.debug("    %r", global_action)
_LOGGER.debug("    %s", async_global_action)
_LOGGER.debug("    %r", async_global_action)

_LOGGER.debug("Class global")
_LOGGER.debug("    %s", Object.global_function)
_LOGGER.debug("    %r", Object.global_function)
_LOGGER.debug("    %s", Object.async_global_function)
_LOGGER.debug("    %r", Object.async_global_function)

_LOGGER.debug("Class static")
_LOGGER.debug("    %s", Object.static_method)
_LOGGER.debug("    %r", Object.static_method)
_LOGGER.debug("    %s", Object.async_static_method)
_LOGGER.debug("    %r", Object.async_static_method)

_LOGGER.debug("Class method")
_LOGGER.debug("    %s", Object.method)
_LOGGER.debug("    %r", Object.method)
_LOGGER.debug("    %s", Object.async_method)
_LOGGER.debug("    %r", Object.async_method)

_LOGGER.debug("Object global")
_LOGGER.debug("    %s", obj.global_function)
_LOGGER.debug("    %r", obj.global_function)
_LOGGER.debug("    %s", obj.async_global_function)
_LOGGER.debug("    %r", obj.async_global_function)

_LOGGER.debug("Object static")
_LOGGER.debug("    %s", obj.static_method)
_LOGGER.debug("    %r", obj.static_method)
_LOGGER.debug("    %s", obj.async_static_method)
_LOGGER.debug("    %r", obj.async_static_method)

_LOGGER.debug("Object method")
_LOGGER.debug("    %s", obj.method)
_LOGGER.debug("    %r", obj.method)
_LOGGER.debug("    %s", obj.async_method)
_LOGGER.debug("    %r", obj.async_method)

_LOGGER.debug("From object method")

simple_method = action(obj.simple_method, 1, 2)
async_simple_method = action(obj.async_simple_method, b='b', c='c')
_LOGGER.debug("   %s", simple_method)
_LOGGER.debug("   %r", simple_method)
_LOGGER.debug("   %s", async_simple_method)
_LOGGER.debug("   %r", async_simple_method)
