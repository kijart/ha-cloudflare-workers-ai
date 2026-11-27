"""Tests for the options flow."""

import json
from pathlib import Path
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.cloudflare_workers_ai.const import (
    API_BASE,
    CONF_STT_MODEL,
    CONF_STT_PROMPT,
    CONF_TTS_MODEL,
    CONF_TTS_VOICE,
    DEFAULT_STT_MODEL,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
)
from custom_components.cloudflare_workers_ai.models import (
    TASK_ASR,
    TASK_TTS,
    ModelCatalog,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

FIXTURES = Path(__file__).parent / "fixtures"
VERIFY_URL = f"{API_BASE}/accounts/acc/tokens/verify"
SEARCH_URL = f"{API_BASE}/accounts/acc/ai/models/search"
DISCOVER = "custom_components.cloudflare_workers_ai.config_flow.async_discover"
OPTIONS = {
    CONF_STT_MODEL: DEFAULT_STT_MODEL,
    CONF_STT_PROMPT: "Home Assistant, Cloudflare",
    CONF_TTS_MODEL: DEFAULT_TTS_MODEL,
    CONF_TTS_VOICE: "carina",
}


async def _open(hass: HomeAssistant, entry: MockConfigEntry):
    if hass.config_entries.async_get_entry(entry.entry_id) is None:
        entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return await hass.config_entries.options.async_init(entry.entry_id)


def _choices(result, key: str) -> list[str]:
    for marker, validator in result["data_schema"].schema.items():
        if marker == key:
            return [o["value"] for o in validator.config["options"]]
    raise AssertionError(key)


async def test_options_lists_discovered_models_and_voices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Selectors offer the discovered models and voices."""
    result = await _open(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert "@cf/openai/whisper-large-v3-turbo" in _choices(result, CONF_STT_MODEL)
    assert "@cf/deepgram/aura-2-es" in _choices(result, CONF_TTS_MODEL)
    assert "aquila" in _choices(result, CONF_TTS_VOICE)


async def test_options_saves_and_reloads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Saving stores the options and reloads the entry."""
    result = await _open(hass, mock_config_entry)
    old_runtime_data = mock_config_entry.runtime_data
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], OPTIONS
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == OPTIONS
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not old_runtime_data


async def test_options_saves_empty_prompt_as_empty_string(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """An omitted prompt is stored as an empty string."""
    user_input = {k: v for k, v in OPTIONS.items() if k != CONF_STT_PROMPT}
    result = await _open(hass, mock_config_entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert mock_config_entry.options[CONF_STT_PROMPT] == ""


async def test_options_works_when_discovery_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Failed discovery offers the defaults and still saves."""
    aioclient_mock.get(
        VERIFY_URL, json=json.loads((FIXTURES / "verify_ok.json").read_text())
    )
    for task in (TASK_ASR, TASK_TTS):
        aioclient_mock.get(f"{SEARCH_URL}?task={task}", status=500, json={})
    result = await _open(hass, mock_config_entry)
    assert _choices(result, CONF_STT_MODEL) == [DEFAULT_STT_MODEL]
    assert _choices(result, CONF_TTS_MODEL) == [DEFAULT_TTS_MODEL]
    assert DEFAULT_TTS_VOICE in _choices(result, CONF_TTS_VOICE)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], OPTIONS
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_rejects_voice_not_in_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """A voice that the newly selected model lacks is rejected."""
    other = "@cf/deepgram/aura-2-en"
    catalog = ModelCatalog(
        stt_models=[DEFAULT_STT_MODEL],
        tts_models=[DEFAULT_TTS_MODEL, other],
        voices={DEFAULT_TTS_MODEL: ["aquila"], other: ["thalia"]},
        discovered=True,
    )
    with patch(DISCOVER, return_value=catalog):
        result = await _open(hass, mock_config_entry)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {**OPTIONS, CONF_TTS_MODEL: other, CONF_TTS_VOICE: "aquila"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_TTS_VOICE: "invalid_voice"}
    assert _choices(result, CONF_TTS_VOICE) == ["thalia"]
    marker = next(k for k in result["data_schema"].schema if k == CONF_TTS_MODEL)
    assert marker.description["suggested_value"] == other
    with patch(DISCOVER, return_value=catalog):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {**OPTIONS, CONF_TTS_MODEL: other, CONF_TTS_VOICE: "thalia"},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_TTS_MODEL] == other
    assert mock_config_entry.options[CONF_TTS_VOICE] == "thalia"


async def test_options_keeps_saved_model_missing_from_catalog(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """A saved model that is no longer discovered stays selectable."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**OPTIONS, CONF_STT_MODEL: "@cf/openai/whisper-gone"},
    )
    result = await _open(hass, mock_config_entry)
    assert "@cf/openai/whisper-gone" in _choices(result, CONF_STT_MODEL)


async def test_options_without_loaded_entry_uses_fallback(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An entry that is not loaded offers the default catalog."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert _choices(result, CONF_TTS_MODEL) == [DEFAULT_TTS_MODEL]


async def test_options_save_for_model_without_known_voices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """A model with no known voices does not block saving."""
    other = "@cf/deepgram/aura-2-en"
    catalog = ModelCatalog(
        stt_models=[DEFAULT_STT_MODEL],
        tts_models=[DEFAULT_TTS_MODEL, other],
        voices={DEFAULT_TTS_MODEL: ["aquila"], other: []},
        discovered=True,
    )
    with patch(DISCOVER, return_value=catalog):
        result = await _open(hass, mock_config_entry)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {**OPTIONS, CONF_TTS_MODEL: other, CONF_TTS_VOICE: "aquila"},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_TTS_MODEL] == other
