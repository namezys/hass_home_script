# home_script
HACS custom integration to write Python script and helpers to simplify these scripts

Right now I'm developing this component just for me.
It works (maybe work) only at my home.

This component:
* should create "home_script" in config directory
* put stubs into this directory
  * home_script
  * homeassistant
* load `home_script` module
* load app `*.py` files from `${config}/home_script`
* monitor this directory and reload on any changed

Reload:
* stop all managers (state event manager, time manager)
  * all code that use this manager will not called any more
* stop all current task initiated through this managers
* remove modules from module cache
  * this should result in destroying all objects in these modules
* start load

## Grammar

`CONDITION => condition(func | method)`

`ACTION => action(funct | method, ...) | ACTION(...)`

`ACTION_LIST => [ACTION, ...] | ACTION | None`

`CONDITION_SCHEMA_ITEM = CONDITION: ACTION_LISR`

`CONDITION_SCHEMA = { CONDITION_SCHEMA_ITEM } | ACTION_LIST`

`EVENT_SCHEMA_ITEM = EVENT : CONDITION_SCHEMA`

`EVENT_SCHEMA = { EVENT_SCHEMA_ITEM }`

### Helpers
`property_condition(ins, attr) = condition(lamnda: getattr(ins, attr))`