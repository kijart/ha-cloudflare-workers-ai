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


class CloudflareWorkersAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_USE_GATEWAY] and not user_input.get(CONF_GATEWAY_ID):
                errors["base"] = "gateway_id_required"
            else:
                await self.async_set_unique_id(user_input[CONF_ACCOUNT_ID])
                self._abort_if_unique_id_configured()
                try:
                    await build_client(self.hass, user_input).verify_token()
                except CloudflareAuthError:
                    errors["base"] = "invalid_auth"
                except CloudflareConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error verifying the token")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(title=ENTRY_TITLE, data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication (placeholder until the reauth task)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Placeholder reauthentication form."""
        return self.async_show_form(step_id="reauth_confirm")
