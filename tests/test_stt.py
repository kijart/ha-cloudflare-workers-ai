"""Tests for the speech-to-text platform."""

import base64
from collections.abc import AsyncIterator
import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.cloudflare_workers_ai.const import (
    API_BASE,
    CONF_STT_PROMPT,
    DEFAULT_STT_MODEL,
    DOMAIN,
    GATEWAY_BASE,
    MAX_STT_AUDIO_BYTES,
    STT_BYTES_PER_SECOND,
)
from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
    async_get_speech_to_text_entity,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

FIXTURES = Path(__file__).parent / "fixtures"
API_TOKEN = "test-api-token-secret"
GATEWAY_TOKEN = "test-gateway-token-secret"
PLATFORMS = "custom_components.cloudflare_workers_ai.PLATFORMS"
RUN_URL = f"{API_BASE}/accounts/acc/ai/run/{DEFAULT_STT_MODEL}"
METADATA = SpeechMetadata(
    language="es",
    format=AudioFormats.WAV,
    codec=AudioCodecs.PCM,
    bit_rate=AudioBitRates.BITRATE_16,
    sample_rate=AudioSampleRates.SAMPLERATE_16000,
    channel=AudioChannels.CHANNEL_MONO,
)
OK_BODY = {"success": True, "errors": [], "result": {"text": " enciende la luz "}}
QUOTA_BODY = {
    "success": False,
    "errors": [{"code": 4006, "message": "daily free allocation used up"}],
}


async def _stream(pcm: bytes) -> AsyncIterator[bytes]:
    for start in range(0, len(pcm), 4096):
        yield pcm[start : start + 4096]


def _pcm(seconds: float) -> bytes:
    return bytes(int(STT_BYTES_PER_SECOND * seconds))


async def _setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    options: dict[str, str] | None = None,
) -> SpeechToTextEntity:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options=options or {})
    with patch(PLATFORMS, [Platform.STT]):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    entity_id = er.async_get(hass).async_get_entity_id(
        "stt", DOMAIN, f"{entry.entry_id}_stt"
    )
    assert entity_id is not None
    entity = async_get_speech_to_text_entity(hass, entity_id)
    assert entity is not None
    return entity


async def test_stt_sends_wav_base64_with_whisper_params(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """The audio is sent as a base64 WAV with the Whisper parameters."""
    entity = await _setup(hass, mock_config_entry, {CONF_STT_PROMPT: "salón, cocina"})
    mock_cloudflare.post(RUN_URL, json=OK_BODY)
    result = await entity.async_process_audio_stream(METADATA, _stream(_pcm(1)))
    body = mock_cloudflare.mock_calls[-1][2]
    assert base64.b64decode(body["audio"])[:4] == b"RIFF"
    assert body["language"] == "es"
    assert body["vad_filter"] is True
    assert body["condition_on_previous_text"] is False
    assert body["initial_prompt"] == "salón, cocina"
    assert result == SpeechResult("enciende la luz", SpeechResultState.SUCCESS)


async def test_stt_omits_initial_prompt_when_empty(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """An empty prompt is not sent."""
    entity = await _setup(hass, mock_config_entry, {CONF_STT_PROMPT: ""})
    mock_cloudflare.post(RUN_URL, json=OK_BODY)
    await entity.async_process_audio_stream(METADATA, _stream(_pcm(1)))
    assert "initial_prompt" not in mock_cloudflare.mock_calls[-1][2]


@pytest.mark.parametrize("seconds", [0, 0.2])
async def test_stt_short_or_empty_audio_skips_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
    seconds: float,
) -> None:
    """Empty or too short audio returns an error without calling the API."""
    entity = await _setup(hass, mock_config_entry)
    calls = mock_cloudflare.call_count
    result = await entity.async_process_audio_stream(METADATA, _stream(_pcm(seconds)))
    assert result == SpeechResult(None, SpeechResultState.ERROR)
    assert mock_cloudflare.call_count == calls


async def test_stt_audio_over_limit_is_rejected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Audio above the maximum returns an error without calling the API."""
    entity = await _setup(hass, mock_config_entry)
    calls = mock_cloudflare.call_count
    pcm = _pcm(31)
    assert len(pcm) > MAX_STT_AUDIO_BYTES
    result = await entity.async_process_audio_stream(METADATA, _stream(pcm))
    assert result == SpeechResult(None, SpeechResultState.ERROR)
    assert mock_cloudflare.call_count == calls


async def test_stt_empty_text_is_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Blank text is an error."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, json={"success": True, "result": {"text": "  "}})
    result = await entity.async_process_audio_stream(METADATA, _stream(_pcm(1)))
    assert result == SpeechResult(None, SpeechResultState.ERROR)


async def test_stt_silence_response_is_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """The real response to silence is an error."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, json=load_fixture("whisper_silence_result.json"))
    result = await entity.async_process_audio_stream(METADATA, _stream(_pcm(1)))
    assert result == SpeechResult(None, SpeechResultState.ERROR)


async def test_stt_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """A rejected token returns an error and starts reauth."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, status=401, json=load_fixture("error_auth.json"))
    result = await entity.async_process_audio_stream(METADATA, _stream(_pcm(1)))
    await hass.async_block_till_done()
    assert result == SpeechResult(None, SpeechResultState.ERROR)
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_stt_connection_error_is_error_without_token_in_log(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A network failure returns an error and never logs the token."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, exc=TimeoutError)
    result = await entity.async_process_audio_stream(METADATA, _stream(_pcm(1)))
    assert result == SpeechResult(None, SpeechResultState.ERROR)
    assert "Speech-to-text request failed" in caplog.text
    assert API_TOKEN not in caplog.text


async def test_stt_quota_error_warns_once_no_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An exhausted quota warns once per UTC day and keeps the entity available."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, status=429, json=QUOTA_BODY)
    caplog.set_level(logging.WARNING)

    def warnings() -> list[logging.LogRecord]:
        return [r for r in caplog.records if "quota exhausted" in r.getMessage()]

    for _ in range(2):
        result = await entity.async_process_audio_stream(METADATA, _stream(_pcm(1)))
        assert result == SpeechResult(None, SpeechResultState.ERROR)
    assert len(warnings()) == 1

    freezer.tick(24 * 3600)
    await entity.async_process_audio_stream(METADATA, _stream(_pcm(1)))
    assert len(warnings()) == 2

    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert not any(flow["context"]["source"] == "reauth" for flow in flows)
    assert entity.available is True


async def test_stt_entity_metadata(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """The entity declares the Assist audio format and its device."""
    entity = await _setup(hass, mock_config_entry)
    assert entity.supported_formats == [AudioFormats.WAV]
    assert entity.supported_codecs == [AudioCodecs.PCM]
    assert entity.supported_sample_rates == [AudioSampleRates.SAMPLERATE_16000]
    assert entity.supported_bit_rates == [AudioBitRates.BITRATE_16]
    assert entity.supported_channels == [AudioChannels.CHANNEL_MONO]
    assert "es" in entity.supported_languages
    assert entity.unique_id == f"{mock_config_entry.entry_id}_stt"
    registry_entry = er.async_get(hass).async_get(entity.entity_id)
    assert registry_entry is not None
    assert registry_entry.translation_key == "stt"


def load_fixture(name: str) -> Any:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text())


async def test_stt_gateway_auth_error_warns_without_reauth(
    hass: HomeAssistant,
    gateway_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A rejected gateway returns an error, warns and does not start reauth."""
    entity = await _setup(hass, gateway_config_entry)
    mock_cloudflare.post(
        f"{GATEWAY_BASE}/acc/gw/workers-ai/{DEFAULT_STT_MODEL}",
        status=401,
        json=load_fixture("error_auth.json"),
    )
    caplog.set_level(logging.WARNING)
    result = await entity.async_process_audio_stream(METADATA, _stream(_pcm(1)))
    await hass.async_block_till_done()
    assert result == SpeechResult(None, SpeechResultState.ERROR)
    assert "AI Gateway rejected the request" in caplog.text
    assert GATEWAY_TOKEN not in caplog.text
    assert API_TOKEN not in caplog.text
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert not any(flow["context"]["source"] == "reauth" for flow in flows)
