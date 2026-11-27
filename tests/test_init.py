"""Tests for the entry lifecycle."""

import json
from pathlib import Path
import re
from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.cloudflare_workers_ai import build_client
from custom_components.cloudflare_workers_ai.const import (
    API_BASE,
    CONF_ACCOUNT_ID,
    CONF_GATEWAY_ID,
    CONF_GATEWAY_TOKEN,
    CONF_STT_MODEL,
    CONF_TTS_MODEL,
    CONF_USE_GATEWAY,
    DEFAULT_TTS_MODEL,
    DOMAIN,
)
from custom_components.cloudflare_workers_ai.models import TASK_ASR, TASK_TTS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

FIXTURES = Path(__file__).parent / "fixtures"
API_TOKEN = "test-api-token-secret"
VERIFY_URL = f"{API_BASE}/accounts/acc/tokens/verify"
SEARCH_URL = f"{API_BASE}/accounts/acc/ai/models/search"
SCHEMA_URL = f"{API_BASE}/accounts/acc/ai/models/schema"


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """The entry loads with a discovered catalog and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)
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
    mock_config_entry.add_to_hass(hass)
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


async def _setup(
    hass: HomeAssistant, entry: MockConfigEntry, options: dict[str, str]
) -> None:
    hass.config_entries.async_update_entry(entry, options=options)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _issue(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> ir.Issue | None:
    return ir.async_get(hass).async_get_issue(
        DOMAIN, f"model_unavailable_{key}_{entry.entry_id}"
    )


async def test_missing_configured_model_creates_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """A configured model absent from the catalog raises a repair issue."""
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, {CONF_TTS_MODEL: "@cf/deepgram/aura-2-xx"})

    issue = _issue(hass, mock_config_entry, "tts")
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "model_unavailable"
    assert issue.translation_placeholders == {"model": "@cf/deepgram/aura-2-xx"}
    assert _issue(hass, mock_config_entry, "stt") is None


async def test_missing_stt_model_creates_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """The speech-to-text model is checked as well."""
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, {CONF_STT_MODEL: "@cf/openai/whisper-gone"})

    assert _issue(hass, mock_config_entry, "stt") is not None
    assert _issue(hass, mock_config_entry, "tts") is None


async def test_no_issue_when_defaults_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Absent options resolve to available default models."""
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, {})

    assert _issue(hass, mock_config_entry, "stt") is None
    assert _issue(hass, mock_config_entry, "tts") is None


async def test_no_issue_when_discovery_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A fallback catalog cannot tell whether a model is retired."""
    aioclient_mock.get(VERIFY_URL, json=load_fixture("verify_ok.json"))
    for task in (TASK_ASR, TASK_TTS):
        aioclient_mock.get(
            f"{SEARCH_URL}?task={task}",
            status=403,
            json=load_fixture("error_auth.json"),
        )
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, {CONF_TTS_MODEL: "@cf/deepgram/aura-2-xx"})

    assert mock_config_entry.runtime_data.catalog.discovered is False
    assert _issue(hass, mock_config_entry, "tts") is None


async def test_issue_removed_when_model_available_again(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """The issue disappears once the configured model is offered again."""
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, {CONF_TTS_MODEL: "@cf/deepgram/aura-2-xx"})
    assert _issue(hass, mock_config_entry, "tts") is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_TTS_MODEL: DEFAULT_TTS_MODEL}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _issue(hass, mock_config_entry, "tts") is None


async def test_issues_removed_with_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Removing the entry deletes its repair issues."""
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, {CONF_TTS_MODEL: "@cf/deepgram/aura-2-xx"})
    assert _issue(hass, mock_config_entry, "tts") is not None

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _issue(hass, mock_config_entry, "tts") is None


async def test_no_issue_for_listed_model_when_schema_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A model listed by the search is not reported after a schema error."""
    aioclient_mock.get(VERIFY_URL, json=load_fixture("verify_ok.json"))
    aioclient_mock.get(
        f"{SEARCH_URL}?task={TASK_ASR}", json=load_fixture("models_search_asr.json")
    )
    aioclient_mock.get(
        f"{SEARCH_URL}?task={TASK_TTS}", json=load_fixture("models_search_tts.json")
    )
    aioclient_mock.get(re.compile(re.escape(SCHEMA_URL)), status=500)
    mock_config_entry.add_to_hass(hass)
    await _setup(hass, mock_config_entry, {CONF_TTS_MODEL: "@cf/deepgram/aura-2-en"})

    assert mock_config_entry.runtime_data.catalog.discovered is True
    assert _issue(hass, mock_config_entry, "tts") is None
