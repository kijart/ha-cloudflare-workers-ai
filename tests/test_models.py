"""Tests for model families and runtime discovery."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.cloudflare_workers_ai.api import CloudflareClient
from custom_components.cloudflare_workers_ai.const import (
    API_BASE,
    DEFAULT_STT_MODEL,
    DEFAULT_TTS_MODEL,
)
from custom_components.cloudflare_workers_ai.models import (
    FALLBACK_AURA_2_ES_VOICES,
    TASK_ASR,
    TASK_TTS,
    async_discover,
    fallback_catalog,
    family_for,
    tts_language,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

FIXTURES = Path(__file__).parent / "fixtures"
ASR_BODY = json.loads((FIXTURES / "models_search_asr.json").read_text())
TTS_BODY = json.loads((FIXTURES / "models_search_tts.json").read_text())
SCHEMA_BODY = json.loads((FIXTURES / "schema_aura_2_es.json").read_text())
API_TOKEN = "test-api-token-secret"
SEARCH_URL = f"{API_BASE}/accounts/acc/ai/models/search"
SCHEMA_URL = f"{API_BASE}/accounts/acc/ai/models/schema"
AURA_ES = "@cf/deepgram/aura-2-es"
AURA_EN = "@cf/deepgram/aura-2-en"
AURA_1 = "@cf/deepgram/aura-1"


def _client(hass: HomeAssistant, **kwargs: str) -> CloudflareClient:
    return CloudflareClient(async_get_clientsession(hass), "acc", API_TOKEN, **kwargs)


def _mock_search(mock: AiohttpClientMocker) -> None:
    mock.get(f"{SEARCH_URL}?task={TASK_ASR}", json=ASR_BODY)
    mock.get(f"{SEARCH_URL}?task={TASK_TTS}", json=TTS_BODY)


def _mock_schema(mock: AiohttpClientMocker, model: str, **kwargs: Any) -> None:
    mock.get(f"{SCHEMA_URL}?model={model}", **kwargs)


def test_family_for_matches_only_known_cf_models() -> None:
    """Only Whisper and Aura models of Workers AI belong to a family."""
    whisper = family_for("@cf/openai/whisper-large-v3-turbo")
    aura = family_for(AURA_ES)
    assert whisper is not None
    assert whisper.key == "whisper"
    assert aura is not None
    assert aura.key == "aura"
    assert family_for("@cf/deepgram/nova-3") is None
    assert family_for("openai/tts-1") is None
    assert family_for("@cf/myshell-ai/melotts") is None


def test_tts_language() -> None:
    """The language comes from the Aura model name."""
    assert tts_language(AURA_ES) == "es"
    assert tts_language(AURA_1) == "en"
    assert tts_language("@cf/openai/whisper") is None


def test_fallback_catalog() -> None:
    """The fallback catalog holds the defaults."""
    catalog = fallback_catalog()
    assert catalog.stt_models == [DEFAULT_STT_MODEL]
    assert catalog.tts_models == [DEFAULT_TTS_MODEL]
    assert catalog.voices == {DEFAULT_TTS_MODEL: list(FALLBACK_AURA_2_ES_VOICES)}
    assert catalog.discovered is False


async def test_discover_filters_and_reads_voices(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Models are filtered by family and voices come from the schema."""
    _mock_search(aioclient_mock)
    for model in (AURA_ES, AURA_EN, AURA_1):
        _mock_schema(aioclient_mock, model, json=SCHEMA_BODY)
    catalog = await async_discover(_client(hass))
    assert catalog.discovered is True
    assert catalog.stt_models == [
        DEFAULT_STT_MODEL,
        "@cf/openai/whisper",
    ]
    assert "@cf/deepgram/nova-3" not in catalog.stt_models
    assert catalog.tts_models == [AURA_ES, AURA_1, AURA_EN]
    assert "aquila" in catalog.voices[AURA_ES]
    assert set(catalog.voices) == set(catalog.tts_models)


async def test_discover_schema_failure_uses_fallback_only_for_aura_2_es(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A failing schema keeps aura-2-es with fallback voices and drops others."""
    _mock_search(aioclient_mock)
    _mock_schema(aioclient_mock, AURA_ES, status=500)
    _mock_schema(aioclient_mock, AURA_EN, status=500)
    _mock_schema(aioclient_mock, AURA_1, json={"success": True, "result": {}})
    catalog = await async_discover(_client(hass))
    assert catalog.discovered is True
    assert catalog.tts_models == [AURA_ES]
    assert catalog.voices == {AURA_ES: list(FALLBACK_AURA_2_ES_VOICES)}


@pytest.mark.parametrize("failure", [403, 500, asyncio.TimeoutError])
async def test_discover_falls_back_on_any_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    failure: int | type[Exception],
) -> None:
    """Any Cloudflare error yields the fallback catalog."""
    if isinstance(failure, int):
        aioclient_mock.get(SEARCH_URL, status=failure)
    else:
        aioclient_mock.get(SEARCH_URL, exc=failure)
    assert await async_discover(_client(hass)) == fallback_catalog()


async def test_discovery_calls_bypass_the_gateway(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Model listing and schema calls go direct, without the gateway header."""
    _mock_search(aioclient_mock)
    _mock_schema(aioclient_mock, AURA_ES, json=SCHEMA_BODY)
    client = _client(hass, gateway_id="gw", gateway_token="gt")
    assert await client.list_models(TASK_TTS)
    assert await client.get_input_schema(AURA_ES)
    assert len(aioclient_mock.mock_calls) == 2
    for call in aioclient_mock.mock_calls:
        assert str(call[1]).startswith(API_BASE)
        assert "cf-aig-authorization" not in call[3]
        assert call[3]["Authorization"] == f"Bearer {API_TOKEN}"
