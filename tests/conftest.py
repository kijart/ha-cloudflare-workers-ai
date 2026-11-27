"""Shared fixtures."""

import json
from pathlib import Path
import re

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.cloudflare_workers_ai.const import (
    API_BASE,
    CONF_ACCOUNT_ID,
    CONF_USE_GATEWAY,
    DOMAIN,
)
from custom_components.cloudflare_workers_ai.models import TASK_ASR, TASK_TTS
from homeassistant.const import CONF_API_TOKEN

FIXTURES = Path(__file__).parent / "fixtures"
API_TOKEN = "test-api-token-secret"
ACCOUNT_URL = f"{API_BASE}/accounts/acc"
VERIFY_URL = f"{ACCOUNT_URL}/tokens/verify"
SEARCH_URL = f"{ACCOUNT_URL}/ai/models/search"
SCHEMA_URL = f"{ACCOUNT_URL}/ai/models/schema"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of custom integrations in every test."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for account "acc"."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Cloudflare Workers AI",
        unique_id="acc",
        data={
            CONF_ACCOUNT_ID: "acc",
            CONF_API_TOKEN: API_TOKEN,
            CONF_USE_GATEWAY: False,
        },
    )


@pytest.fixture
def mock_cloudflare(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock a successful token verification and model discovery."""
    aioclient_mock.get(VERIFY_URL, json=load_fixture("verify_ok.json"))
    aioclient_mock.get(
        f"{SEARCH_URL}?task={TASK_ASR}", json=load_fixture("models_search_asr.json")
    )
    aioclient_mock.get(
        f"{SEARCH_URL}?task={TASK_TTS}", json=load_fixture("models_search_tts.json")
    )
    aioclient_mock.get(
        re.compile(re.escape(SCHEMA_URL)), json=load_fixture("schema_aura_2_es.json")
    )
    return aioclient_mock
