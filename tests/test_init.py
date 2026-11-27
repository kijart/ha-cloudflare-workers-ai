"""Tests for the entry lifecycle."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.cloudflare_workers_ai import build_client, config_flow
from custom_components.cloudflare_workers_ai.const import (
    API_BASE,
    CONF_ACCOUNT_ID,
    CONF_GATEWAY_ID,
    CONF_GATEWAY_TOKEN,
    CONF_USE_GATEWAY,
)
from custom_components.cloudflare_workers_ai.models import TASK_ASR, TASK_TTS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

FIXTURES = Path(__file__).parent / "fixtures"
API_TOKEN = "test-api-token-secret"
VERIFY_URL = f"{API_BASE}/accounts/acc/tokens/verify"
SEARCH_URL = f"{API_BASE}/accounts/acc/ai/models/search"
PLATFORMS = "custom_components.cloudflare_workers_ai.PLATFORMS"


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """The entry loads with a discovered catalog and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)
    with patch(PLATFORMS, []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert mock_config_entry.runtime_data.catalog.discovered is True

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A rejected token puts the entry in setup error and starts reauth."""
    aioclient_mock.get(VERIFY_URL, status=401, json=load_fixture("error_auth.json"))
    assert config_flow.CloudflareWorkersAIConfigFlow.async_step_reauth
    mock_config_entry.add_to_hass(hass)
    with patch(PLATFORMS, []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(mock_config_entry.domain)
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_setup_connection_failure_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A timeout during verification schedules a retry."""
    aioclient_mock.get(VERIFY_URL, exc=TimeoutError)
    mock_config_entry.add_to_hass(hass)
    with patch(PLATFORMS, []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_unexpected_response_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An unexpected API response schedules a retry."""
    aioclient_mock.get(VERIFY_URL, status=500, json={"success": False})
    mock_config_entry.add_to_hass(hass)
    with patch(PLATFORMS, []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_succeeds_when_discovery_forbidden(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A 403 on model search falls back to the default catalog."""
    aioclient_mock.get(VERIFY_URL, json=load_fixture("verify_ok.json"))
    for task in (TASK_ASR, TASK_TTS):
        aioclient_mock.get(
            f"{SEARCH_URL}?task={task}",
            status=403,
            json=load_fixture("error_auth.json"),
        )
    mock_config_entry.add_to_hass(hass)
    with patch(PLATFORMS, []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.catalog.discovered is False


async def test_build_client_ignores_gateway_when_disabled(
    hass: HomeAssistant,
) -> None:
    """Gateway settings are only applied when use_gateway is true."""
    data = {
        CONF_ACCOUNT_ID: "acc",
        CONF_API_TOKEN: API_TOKEN,
        CONF_USE_GATEWAY: False,
        CONF_GATEWAY_ID: "gw",
        CONF_GATEWAY_TOKEN: "gw-token-secret",
    }
    assert vars(build_client(hass, data))["_gateway_id"] is None
    gateway_client = build_client(hass, {**data, CONF_USE_GATEWAY: True})
    assert vars(gateway_client)["_gateway_id"] == "gw"


def load_fixture(name: str) -> Any:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text())
