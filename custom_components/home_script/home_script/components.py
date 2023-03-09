import typing
from logging import getLogger

import attrs
from homeassistant import core
from homeassistant.helpers import entity, entity_component

EntityT = typing.TypeVar('EntityT', bound=entity.Entity)

_LOGGER = getLogger(__name__)


@attrs.define
class ComponentEntities(typing.Generic[EntityT]):
    """
    Wrapper to get typed entity by entity_id.
    """
    hass: core.HomeAssistant
    domain: str
    component: entity_component.EntityComponent[EntityT] | None

    @staticmethod
    def load(hass: core.HomeAssistant, domain: str):
        data_instances = hass.data[entity_component.DATA_INSTANCES]
        try:
            _LOGGER.debug("Load component entities for domain %s", domain)
            component = typing.cast(entity_component.EntityComponent[EntityT], data_instances[domain])
        except KeyError:
            _LOGGER.info("Can not find domain %s", domain)
            component = None
        return ComponentEntities(hass, domain, component)

    def __getitem__(self, item: str) -> EntityT:
        if self.component is None:
            data_instances = self.hass.data[entity_component.DATA_INSTANCES]
            raise ValueError(f"Can not find EntityComponent for domain {self.domain}. "
                             f"Known domains are: {','.join(sorted(data_instances.keys()))}")
        result = self.component.get_entity(item)
        if result is None:
            raise KeyError(f"Entity '{item}' not found")
        return result
