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
    CONF_CONTROLLER,
    CONF_LOCKS,
    DEFAULT_CONTROLLER,
    DOMAIN,
    CONTROLLER_MUSIC_ASSISTANT,
    CONTROLLER_SONOS,
)

DEFAULT_LOCKS = "Home theater"


def _schema(locks: str, controller: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_LOCKS, default=locks): TextSelector(
                TextSelectorConfig(multiline=False)
            ),
            vol.Optional(CONF_CONTROLLER, default=controller): SelectSelector(
                SelectSelectorConfig(
                    mode=SelectSelectorMode.LIST,
                    translation_key=CONF_CONTROLLER,
                    options=[
                        SelectOptionDict(value=CONTROLLER_SONOS, label="Sonos"),
                        SelectOptionDict(
                            value=CONTROLLER_MUSIC_ASSISTANT, label="Music Assistant"
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
                    CONF_CONTROLLER: user_input.get(CONF_CONTROLLER, DEFAULT_CONTROLLER),
                },
            )

        return self.async_show_form(
            step_id="user", data_schema=_schema(DEFAULT_LOCKS, DEFAULT_CONTROLLER)
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
                self.config_entry.options.get(CONF_CONTROLLER, DEFAULT_CONTROLLER),
            ),
        )
