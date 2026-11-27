"""The Cloudflare Workers AI integration."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
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
    CONF_STT_MODEL,
    CONF_TTS_MODEL,
    CONF_USE_GATEWAY,
    DEFAULT_STT_MODEL,
    DEFAULT_TTS_MODEL,
    DOMAIN,
    ISSUE_MODEL_UNAVAILABLE,
)
from .models import ModelCatalog, async_discover

PLATFORMS: list[Platform] = [Platform.STT, Platform.TTS]
ISSUE_KEYS = ("stt", "tts")


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


def _issue_id(entry: ConfigEntry, key: str) -> str:
    return f"{ISSUE_MODEL_UNAVAILABLE}_{key}_{entry.entry_id}"


def _update_model_issues(
    hass: HomeAssistant, entry: CloudflareWorkersAIConfigEntry
) -> None:
    """Create or delete repair issues for models missing from the catalog.

    A fallback catalog cannot tell whether a model is retired, so issues are
    left untouched in that case.
    """
    catalog = entry.runtime_data.catalog
    if not catalog.discovered:
        return
    configured = {
        "stt": (
            entry.options.get(CONF_STT_MODEL, DEFAULT_STT_MODEL),
            catalog.stt_models,
        ),
        "tts": (
            entry.options.get(CONF_TTS_MODEL, DEFAULT_TTS_MODEL),
            catalog.tts_models,
        ),
    }
    for key, (model, available) in configured.items():
        if model in available:
            ir.async_delete_issue(hass, DOMAIN, _issue_id(entry, key))
            continue
        ir.async_create_issue(
            hass,
            DOMAIN,
            _issue_id(entry, key),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_MODEL_UNAVAILABLE,
            translation_placeholders={"model": model},
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
    _update_model_issues(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_remove_entry(
    hass: HomeAssistant, entry: CloudflareWorkersAIConfigEntry
) -> None:
    """Delete the repair issues of a removed config entry."""
    for key in ISSUE_KEYS:
        ir.async_delete_issue(hass, DOMAIN, _issue_id(entry, key))


async def async_unload_entry(
    hass: HomeAssistant, entry: CloudflareWorkersAIConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
