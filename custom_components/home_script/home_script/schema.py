from logging import getLogger

from .action import Action
from .condition import Condition
from .state_event import StateEvent

_LOGGER = getLogger(__name__)

EVENT_SOURCE = StateEvent
ACTION = Action | list[Action]
CONDITION = Condition


# I believe that deep is enough!!!!
ACTION_SCHEMA = dict[
    CONDITION,
    ACTION | dict[
        CONDITION,
        ACTION | dict[
            CONDITION,
            ACTION | dict[
                CONDITION,
                ACTION | dict[
                    CONDITION,
                    ACTION | dict[
                        CONDITION,
                        ACTION | dict[
                            CONDITION,
                            ACTION | dict[
                                CONDITION,
                                ACTION
                            ]
                        ]
                    ]
                ]
            ]
        ]
    ]
] | ACTION


EVENT_SCHEMA = dict[
    EVENT_SOURCE,
    ACTION_SCHEMA
]

NORMAL_SCHEMA = dict[EVENT_SOURCE, list[Action]]


def normalize_action_schema(condition_schema: ACTION_SCHEMA) -> dict[tuple[CONDITION, ...], list[Action]]:
    _LOGGER.debug("Compile condition schema of size")
    if not isinstance(condition_schema, dict):
        if isinstance(condition_schema, list):
            _LOGGER.debug("Got list of actions")
            assert all(isinstance(i, Action) for i in condition_schema), f"Invalid action in list {condition_schema}"
            return {(): condition_schema} if condition_schema else {}
        _LOGGER.debug("Got action")
        assert isinstance(condition_schema, Action), f"Invalid action {condition_schema}"
        return {(): [condition_schema]}
    _LOGGER.debug("Compile dict schema")
    result = {}
    for key, value in condition_schema.items():
        assert isinstance(key, Condition), f"Invalid condition {key}"
        sub_schema = normalize_action_schema(value)
        for sub_conditions, actions in sub_schema.items():
            result.setdefault((key,) + sub_conditions, []).extend(actions)
    return result


def _apply_conditions(event: EVENT_SOURCE, conditions: tuple[CONDITION, ...]) -> EVENT_SOURCE:
    _LOGGER.debug("Apply %s to %s", conditions, event)
    for item in conditions:
        event = (event >> item)
    return event


def normalize_schema(event_schema: EVENT_SCHEMA) -> NORMAL_SCHEMA:
    _LOGGER.debug("Normalize event schema")
    result: NORMAL_SCHEMA = {}
    for event_source, action in event_schema.items():
        sub_schema = normalize_action_schema(action)
        for conditions, actions in sub_schema.items():
            for item in actions:
                item.check()
            result.setdefault(_apply_conditions(event_source, conditions), []).extend(actions)
    return result
