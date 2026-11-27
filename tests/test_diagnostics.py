"""Tests for diagnostics."""

import json

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from homeassistant.core import HomeAssistant

API_TOKEN = "test-api-token-secret"
REDACTED = "**REDACTED**"


async def test_diagnostics_redacts_secrets(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Diagnostics hide the token and the account id and include the catalog."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert diag["entry"]["data"]["api_token"] == REDACTED
    assert diag["entry"]["data"]["account_id"] == REDACTED
    dumped = json.dumps(diag)
    assert API_TOKEN not in dumped
    assert '"acc"' not in dumped
    assert diag["catalog"]["discovered"] is True
    assert diag["catalog"]["stt_models"]
    assert diag["catalog"]["tts_models"]
    assert diag["catalog"]["voices"]
