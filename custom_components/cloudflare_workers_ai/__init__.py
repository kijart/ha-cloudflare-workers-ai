"""The Cloudflare Workers AI integration."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    CloudflareAuthError,
    CloudflareClient,
    CloudflareConnectionError,
    CloudflareResponseError,
)
from .const import (
    CONF_ACCOUNT_ID,
    CONF_GATEWAY_ID,
    CONF_GATEWAY_TOKEN,
    CONF_USE_GATEWAY,
)
from .models import ModelCatalog, async_discover

PLATFORMS: list[Platform] = [Platform.STT, Platform.TTS]


@dataclass
class CloudflareWorkersAIData:
    """Runtime data of a config entry."""

    client: CloudflareClient
    catalog: ModelCatalog
    quota_warned_on: date | None = None


type CloudflareWorkersAIConfigEntry = ConfigEntry[CloudflareWorkersAIData]


def build_client(hass: HomeAssistant, data: Mapping[str, Any]) -> CloudflareClient:
    """Build an API client from config entry data."""
    use_gateway = data.get(CONF_USE_GATEWAY, False)
    return CloudflareClient(
        async_get_clientsession(hass),
        data[CONF_ACCOUNT_ID],
        data[CONF_API_TOKEN],
        gateway_id=data.get(CONF_GATEWAY_ID) if use_gateway else None,
        gateway_token=data.get(CONF_GATEWAY_TOKEN) if use_gateway else None,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: CloudflareWorkersAIConfigEntry
) -> bool:
    """Set up Cloudflare Workers AI from a config entry."""
    client = build_client(hass, entry.data)
    try:
        await client.verify_token()
    except CloudflareAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except (CloudflareConnectionError, CloudflareResponseError) as err:
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = CloudflareWorkersAIData(
        client=client, catalog=await async_discover(client)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CloudflareWorkersAIConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
