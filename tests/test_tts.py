"""Tests for the text-to-speech platform."""

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.cloudflare_workers_ai.const import (
    API_BASE,
    CONF_TTS_MODEL,
    CONF_TTS_VOICE,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    DOMAIN,
    GATEWAY_BASE,
    MAX_TTS_CHARS,
)
from custom_components.cloudflare_workers_ai.models import FALLBACK_AURA_2_ES_VOICES
from homeassistant.components.tts import (
    ATTR_VOICE,
    DATA_COMPONENT,
    Voice,
    async_create_stream,
)
from homeassistant.components.tts.const import DATA_TTS_MANAGER
from homeassistant.components.tts.entity import TextToSpeechEntity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType

FIXTURES = Path(__file__).parent / "fixtures"
API_TOKEN = "test-api-token-secret"
GATEWAY_TOKEN = "test-gateway-token-secret"
RUN_URL = f"{API_BASE}/accounts/acc/ai/run/{DEFAULT_TTS_MODEL}"
MP3 = {"Content-Type": "audio/mpeg"}
QUOTA_BODY = {
    "success": False,
    "errors": [{"code": 4006, "message": "daily free allocation used up"}],
}


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def tts_cache_dir(tmp_path: Path) -> Any:
    """Keep the TTS file cache out of the shared test config folder."""
    with patch(
        "homeassistant.components.tts._init_tts_cache_dir",
        return_value=str(tmp_path),
    ):
        yield tmp_path


async def _setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    options: dict[str, str] | None = None,
) -> TextToSpeechEntity:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options=options or {})
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    entity_id = er.async_get(hass).async_get_entity_id(
        "tts", DOMAIN, f"{entry.entry_id}_tts"
    )
    assert entity_id is not None
    entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    assert entity is not None
    return entity


def _last_body(mock: AiohttpClientMocker) -> Any:
    return mock.mock_calls[-1][2]


async def test_tts_returns_mp3_with_selected_voice(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """The configured voice is sent and the MP3 bytes are returned."""
    entity = await _setup(hass, mock_config_entry, {CONF_TTS_VOICE: "javier"})
    mock_cloudflare.post(RUN_URL, content=b"ID3fake", headers=MP3)
    result = await entity.async_get_tts_audio("Hola", "es", {})
    assert _last_body(mock_cloudflare) == {"text": "Hola", "speaker": "javier"}
    assert result == ("mp3", b"ID3fake")


async def test_tts_through_home_assistant_manager(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Assist's path (TTS manager, not the entity directly) returns the MP3."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, content=b"ID3fake", headers=MP3)
    stream = async_create_stream(hass, entity.entity_id, language="es")
    stream.async_set_message("Hola")
    audio = b"".join([chunk async for chunk in stream.async_stream_result()])
    assert audio == b"ID3fake"
    assert _last_body(mock_cloudflare) == {"text": "Hola", "speaker": "aquila"}


async def test_tts_defaults_to_aquila(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Without options the default voice is used."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, content=b"ID3fake", headers=MP3)
    await entity.async_get_tts_audio("Hola", "es", {})
    assert _last_body(mock_cloudflare)["speaker"] == "aquila"


async def test_tts_voice_option_overrides_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """A per-call voice wins over the configured one."""
    entity = await _setup(hass, mock_config_entry, {CONF_TTS_VOICE: "javier"})
    mock_cloudflare.post(RUN_URL, content=b"ID3fake", headers=MP3)
    await entity.async_get_tts_audio("Hola", "es", {ATTR_VOICE: "diana"})
    assert _last_body(mock_cloudflare)["speaker"] == "diana"


async def test_tts_supported_voices_from_catalog(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Voices come from the discovered catalog, capitalized."""
    entity = await _setup(hass, mock_config_entry)
    voices = entity.async_get_supported_voices("es")
    assert voices is not None
    assert Voice("aquila", "Aquila") in voices
    assert entity.async_get_supported_voices("en") is None


async def test_tts_supported_voices_fall_back_for_default_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """An empty catalog falls back to the static Spanish voices."""
    entity = await _setup(hass, mock_config_entry)
    mock_config_entry.runtime_data.catalog.voices.clear()
    voices = entity.async_get_supported_voices("es")
    assert voices == [Voice(v, v.capitalize()) for v in FALLBACK_AURA_2_ES_VOICES]


async def test_tts_supported_voices_none_without_voices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """A non-default model without discovered voices lists none."""
    entity = await _setup(
        hass, mock_config_entry, {CONF_TTS_MODEL: "@cf/deepgram/aura-2-en"}
    )
    mock_config_entry.runtime_data.catalog.voices.clear()
    assert entity.async_get_supported_voices("en") is None


async def test_tts_language_from_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """The language follows the configured Aura model."""
    entity = await _setup(hass, mock_config_entry)
    assert entity.supported_languages == ["es"]
    assert entity.default_language == "es"
    assert entity.supported_options == [ATTR_VOICE]


async def test_tts_message_too_long_raises_without_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Text above the limit is rejected without calling the API."""
    entity = await _setup(hass, mock_config_entry)
    calls = mock_cloudflare.call_count
    with pytest.raises(HomeAssistantError) as err:
        await entity.async_get_tts_audio("a" * (MAX_TTS_CHARS + 1), "es", {})
    assert err.value.translation_key == "message_too_long"
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_placeholders == {"max_length": str(MAX_TTS_CHARS)}
    assert mock_cloudflare.call_count == calls


async def test_tts_message_at_limit_is_sent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Text of exactly the maximum length is accepted."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, content=b"ID3fake", headers=MP3)
    await entity.async_get_tts_audio("a" * MAX_TTS_CHARS, "es", {})


async def test_tts_quota_error_raises_and_warns_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An exhausted quota raises, warns once and does not start reauth."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, status=429, json=QUOTA_BODY)
    caplog.set_level(logging.WARNING)
    for _ in range(2):
        with pytest.raises(HomeAssistantError) as err:
            await entity.async_get_tts_audio("Hola", "es", {})
        assert err.value.translation_key == "quota_exceeded"
    warnings = [r for r in caplog.records if "quota exhausted" in r.getMessage()]
    assert len(warnings) == 1
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert not any(flow["context"]["source"] == "reauth" for flow in flows)
    assert entity.available is True


async def test_tts_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """A rejected token starts reauth and raises a translated error."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, status=401, json=load_fixture("error_auth.json"))
    with pytest.raises(HomeAssistantError) as err:
        await entity.async_get_tts_audio("Hola", "es", {})
    assert err.value.translation_key == "tts_failed"
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_tts_non_audio_response_is_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """A JSON body instead of audio is a failure."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, json={"success": True, "result": {}})
    with pytest.raises(HomeAssistantError) as err:
        await entity.async_get_tts_audio("Hola", "es", {})
    assert err.value.translation_key == "tts_failed"


async def test_tts_empty_audio_is_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """An empty audio body is a failure."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, content=b"", headers=MP3)
    with pytest.raises(HomeAssistantError) as err:
        await entity.async_get_tts_audio("Hola", "es", {})
    assert err.value.translation_key == "tts_failed"


async def test_tts_connection_error_is_error_without_token_in_log(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A network failure raises a translated error and never logs the token."""
    entity = await _setup(hass, mock_config_entry)
    mock_cloudflare.post(RUN_URL, exc=TimeoutError)
    with pytest.raises(HomeAssistantError) as err:
        await entity.async_get_tts_audio("Hola", "es", {})
    assert err.value.translation_key == "tts_failed"
    assert "Text-to-speech request failed" in caplog.text
    assert API_TOKEN not in caplog.text


async def test_tts_entity_metadata(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """The entity has a stable unique ID, translation key and device."""
    entity = await _setup(hass, mock_config_entry)
    assert entity.unique_id == f"{mock_config_entry.entry_id}_tts"
    registry_entry = er.async_get(hass).async_get(entity.entity_id)
    assert registry_entry is not None
    assert registry_entry.translation_key == "tts"
    # The TTS manager refuses engines without a name, so the translated name
    # must resolve (regression: a wrong strings.json shape left it as None).
    assert entity.name == "Text-to-speech"
    assert entity.entity_id == "tts.cloudflare_workers_ai_text_to_speech"
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Cloudflare"
    assert device.entry_type is DeviceEntryType.SERVICE


async def test_tts_default_options_follow_configured_voice(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """The configured voice is part of the options Home Assistant caches by."""
    entity = await _setup(hass, mock_config_entry, {CONF_TTS_VOICE: "javier"})
    manager = hass.data[DATA_TTS_MANAGER]
    _, javier = manager.process_options(entity, None, None)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_TTS_VOICE: "diana"}
    )
    _, diana = manager.process_options(entity, None, None)
    assert javier == {ATTR_VOICE: "javier"}
    assert diana == {ATTR_VOICE: "diana"}
    assert manager.process_options(entity, None, {ATTR_VOICE: "sirio"})[1] == {
        ATTR_VOICE: "sirio"
    }


async def test_tts_default_options_use_default_voice(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Without a configured voice the default voice is the default option."""
    entity = await _setup(hass, mock_config_entry)
    assert entity.default_options == {ATTR_VOICE: DEFAULT_TTS_VOICE}


async def test_tts_gateway_auth_error_raises_without_reauth(
    hass: HomeAssistant,
    gateway_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A rejected gateway raises a dedicated error and does not start reauth."""
    entity = await _setup(hass, gateway_config_entry)
    mock_cloudflare.post(
        f"{GATEWAY_BASE}/acc/gw/workers-ai/{DEFAULT_TTS_MODEL}",
        status=403,
        json=load_fixture("error_auth.json"),
    )
    with pytest.raises(HomeAssistantError) as err:
        await entity.async_get_tts_audio("Hola", "es", {})
    assert err.value.translation_key == "gateway_auth_failed"
    assert err.value.translation_domain == DOMAIN
    assert GATEWAY_TOKEN not in caplog.text
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert not any(flow["context"]["source"] == "reauth" for flow in flows)
