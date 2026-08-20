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
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CONF_FLAVOUR,
    CONF_LOCKS,
    DEFAULT_FLAVOUR,
    DOMAIN,
    FLAVOUR_MUSIC_ASSISTANT,
    FLAVOUR_SONOS,
)

DEFAULT_LOCKS = "Home theater"


def _schema(locks: str, flavour: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_LOCKS, default=locks): TextSelector(
                TextSelectorConfig(multiline=False)
            ),
            vol.Optional(CONF_FLAVOUR, default=flavour): SelectSelector(
                SelectSelectorConfig(
                    mode=SelectSelectorMode.LIST,
                    translation_key=CONF_FLAVOUR,
                    options=[
                        SelectOptionDict(value=FLAVOUR_SONOS, label="Sonos"),
                        SelectOptionDict(
                            value=FLAVOUR_MUSIC_ASSISTANT, label="Music Assistant"
                        ),
                    ],
                )
            ),
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
                options={
                    CONF_LOCKS: user_input.get(CONF_LOCKS, ""),
                    CONF_FLAVOUR: user_input.get(CONF_FLAVOUR, DEFAULT_FLAVOUR),
                },
            )

        return self.async_show_form(
            step_id="user", data_schema=_schema(DEFAULT_LOCKS, DEFAULT_FLAVOUR)
        )

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

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                self.config_entry.options.get(CONF_LOCKS, DEFAULT_LOCKS),
                self.config_entry.options.get(CONF_FLAVOUR, DEFAULT_FLAVOUR),
            ),
        )
