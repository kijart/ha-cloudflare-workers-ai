"""Diagnostics for Cloudflare Workers AI."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from . import CloudflareWorkersAIConfigEntry
from .const import CONF_ACCOUNT_ID, CONF_GATEWAY_TOKEN

TO_REDACT = {CONF_API_TOKEN, CONF_GATEWAY_TOKEN, CONF_ACCOUNT_ID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CloudflareWorkersAIConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": dict(entry.options),
        },
        "catalog": asdict(entry.runtime_data.catalog),
    }
