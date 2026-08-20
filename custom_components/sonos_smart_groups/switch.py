"""Precedence locks.

A precedence lock is a switch that also remembers *which speaker* claimed it.
Subordinate smart groups read the `principal` attribute to know where to send
their speakers, which a plain boolean helper could never tell them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util, slugify

from .const import (
    ATTR_PREVIOUS_PRINCIPAL,
    ATTR_PRINCIPAL,
    ATTR_TAKEN_AT,
    CONF_LOCKS,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one switch per configured precedence lock."""
    raw = entry.options.get(CONF_LOCKS, entry.data.get(CONF_LOCKS, ""))
    names = [part.strip() for part in str(raw).split(",") if part.strip()]
    async_add_entities(PrecedenceLock(entry, name) for name in names)


class PrecedenceLock(SwitchEntity, RestoreEntity):
    """A named precedence lock."""

    _attr_should_poll = False
    _attr_icon = "mdi:crown-outline"

    def __init__(self, entry: ConfigEntry, name: str) -> None:
        self._entry = entry
        self._label = name
        self._attr_unique_id = f"{entry.entry_id}_{slugify(name)}"
        self._attr_name = f"Precedence {name}"
        self._is_on = False
        self._principal: str | None = None
        self._previous_principal: str | None = None
        self._taken_at: datetime | None = None

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            ATTR_PRINCIPAL: self._principal,
            ATTR_PREVIOUS_PRINCIPAL: self._previous_principal,
            ATTR_TAKEN_AT: self._taken_at.isoformat() if self._taken_at else None,
        }

    async def async_added_to_hass(self) -> None:
        """Restore state and register so services can reach this entity."""
        await super().async_added_to_hass()

        if (last := await self.async_get_last_state()) is not None:
            self._is_on = last.state == "on"
            self._principal = last.attributes.get(ATTR_PRINCIPAL)
            self._previous_principal = last.attributes.get(ATTR_PREVIOUS_PRINCIPAL)

        self.hass.data.setdefault(DOMAIN, {}).setdefault("locks", {})[
            self.entity_id
        ] = self

    async def async_will_remove_from_hass(self) -> None:
        self.hass.data.get(DOMAIN, {}).get("locks", {}).pop(self.entity_id, None)
        await super().async_will_remove_from_hass()

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._is_on = True
        self._taken_at = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._is_on = False
        self._previous_principal = self._principal
        self._principal = None
        self.async_write_ha_state()

    @callback
    def set_principal(self, principal: str) -> None:
        """Record which speaker is leading while this lock is held."""
        if self._principal and self._principal != principal:
            self._previous_principal = self._principal
        self._principal = principal
        self.async_write_ha_state()
