"""Config flow for Cloudflare Workers AI."""

from collections.abc import Mapping
import logging
from typing import Any

import probatio as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import build_client
from .api import CloudflareAuthError, CloudflareConnectionError
from .const import (
    CONF_ACCOUNT_ID,
    CONF_GATEWAY_ID,
    CONF_GATEWAY_TOKEN,
    CONF_USE_GATEWAY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

ENTRY_TITLE = "Cloudflare Workers AI"
_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT_ID): str,
        vol.Required(CONF_API_TOKEN): _PASSWORD,
        vol.Required(CONF_USE_GATEWAY, default=False): bool,
        vol.Optional(CONF_GATEWAY_ID): str,
        vol.Optional(CONF_GATEWAY_TOKEN): _PASSWORD,
    }
)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_TOKEN): _PASSWORD})


class CloudflareWorkersAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    async def _verify(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Validate the settings and return form errors."""
        if data.get(CONF_USE_GATEWAY) and not data.get(CONF_GATEWAY_ID):
            return {"base": "gateway_id_required"}
        try:
            await build_client(self.hass, data).verify_token()
        except CloudflareAuthError:
            return {"base": "invalid_auth"}
        except CloudflareConnectionError:
            return {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error verifying the token")
            return {"base": "unknown"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ACCOUNT_ID])
            self._abort_if_unique_id_configured()
            errors = await self._verify(user_input)
            if not errors:
                return self.async_create_entry(title=ENTRY_TITLE, data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API token."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._verify(entry.data | user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={CONF_ACCOUNT_ID: entry.data[CONF_ACCOUNT_ID]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the token and gateway settings of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ACCOUNT_ID])
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            errors = await self._verify(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )
