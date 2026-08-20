"""Config flow for Sonos Smart Groups."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .const import CONF_LOCKS, DOMAIN

DEFAULT_LOCKS = "Home theater"


def _schema(current: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_LOCKS, default=current): TextSelector(
                TextSelectorConfig(multiline=False)
            )
        }
    )


class SonosSmartGroupsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-instance config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Sonos Smart Groups",
                data={},
                options={CONF_LOCKS: user_input.get(CONF_LOCKS, "")},
            )

        return self.async_show_form(step_id="user", data_schema=_schema(DEFAULT_LOCKS))

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return SonosSmartGroupsOptionsFlow()


class SonosSmartGroupsOptionsFlow(OptionsFlow):
    """Add, rename or remove precedence locks."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(CONF_LOCKS, DEFAULT_LOCKS)
        return self.async_show_form(step_id="init", data_schema=_schema(current))
