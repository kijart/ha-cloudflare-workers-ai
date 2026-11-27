"""Tests for the Cloudflare Workers AI HTTP client."""

import asyncio
import json
from pathlib import Path
from typing import Any

import aiohttp
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.cloudflare_workers_ai.api import (
    CloudflareAuthError,
    CloudflareClient,
    CloudflareConnectionError,
    CloudflareError,
    CloudflareQuotaError,
    CloudflareResponseError,
)
from custom_components.cloudflare_workers_ai.const import API_BASE, GATEWAY_BASE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

FIXTURES = Path(__file__).parent / "fixtures"
AUTH_ERROR_BODY = json.loads((FIXTURES / "error_auth.json").read_text())
MALFORMED_HEADER_BODY = json.loads(
    (FIXTURES / "verify_malformed_header.json").read_text()
)
QUOTA_ERROR_BODY = {
    "success": False,
    "errors": [
        {
            "code": 4006,
            "message": "you have used up your daily free allocation of 10,000 neurons",
        }
    ],
}
STT_MODEL = "@cf/openai/whisper-large-v3-turbo"
API_TOKEN = "test-api-token-secret"
RUN_URL = f"{API_BASE}/accounts/acc/ai/run/{STT_MODEL}"


def _client(hass: HomeAssistant, **kwargs: str) -> CloudflareClient:
    return CloudflareClient(async_get_clientsession(hass), "acc", API_TOKEN, **kwargs)


async def test_run_json_keeps_model_slashes(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Model slashes stay literal and the result is unwrapped."""
    aioclient_mock.post(
        RUN_URL, json={"success": True, "result": {"text": "hola"}, "errors": None}
    )
    result = await _client(hass).run_json(STT_MODEL, {"audio": "x"})
    assert result == {"text": "hola"}
    assert "%2F" not in str(aioclient_mock.mock_calls[0][1])
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == f"Bearer {API_TOKEN}"
    assert "cf-aig-authorization" not in aioclient_mock.mock_calls[0][3]


async def test_run_json_via_gateway_url_and_headers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Gateway calls use the gateway URL and both auth headers."""
    url = f"{GATEWAY_BASE}/acc/gw/workers-ai/{STT_MODEL}"
    aioclient_mock.post(url, json={"success": True, "result": {"text": "hola"}})
    client = _client(hass, gateway_id="gw", gateway_token="gt")
    assert await client.run_json(STT_MODEL, {"audio": "x"}) == {"text": "hola"}
    call = aioclient_mock.mock_calls[0]
    assert str(call[1]) == url
    assert call[3]["cf-aig-authorization"] == "Bearer gt"
    assert call[3]["Authorization"] == f"Bearer {API_TOKEN}"


async def test_gateway_without_token_omits_header(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An unauthenticated gateway sends no cf-aig-authorization header."""
    url = f"{GATEWAY_BASE}/acc/gw/workers-ai/{STT_MODEL}"
    aioclient_mock.post(url, json={"success": True, "result": {}})
    await _client(hass, gateway_id="gw").run_json(STT_MODEL, {})
    assert "cf-aig-authorization" not in aioclient_mock.mock_calls[0][3]


async def test_run_binary_returns_bytes_and_content_type(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Binary responses return body and content type."""
    model = "@cf/deepgram/aura-2-es"
    aioclient_mock.post(
        f"{API_BASE}/accounts/acc/ai/run/{model}",
        content=b"ID3audio",
        headers={"Content-Type": "audio/mpeg"},
    )
    body, content_type = await _client(hass).run_binary(model, {"text": "hola"})
    assert (body, content_type) == (b"ID3audio", "audio/mpeg")


@pytest.mark.parametrize(
    ("status", "body", "exc"),
    [
        (401, AUTH_ERROR_BODY, CloudflareAuthError),
        (403, AUTH_ERROR_BODY, CloudflareAuthError),
        (429, QUOTA_ERROR_BODY, CloudflareQuotaError),
        (429, "", CloudflareQuotaError),
        (400, QUOTA_ERROR_BODY, CloudflareQuotaError),
        (
            400,
            {"success": False, "errors": [{"code": 5000, "message": "bad"}]},
            CloudflareResponseError,
        ),
        (400, MALFORMED_HEADER_BODY, CloudflareAuthError),
        (404, {"success": False, "errors": None}, CloudflareResponseError),
        (502, "", CloudflareConnectionError),
        (500, "<html>oops</html>", CloudflareConnectionError),
        (418, "not json", CloudflareResponseError),
    ],
)
async def test_errors_are_typed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    body: Any,
    exc: type[CloudflareError],
) -> None:
    """HTTP errors map to typed exceptions."""
    if isinstance(body, dict):
        aioclient_mock.post(RUN_URL, status=status, json=body)
    else:
        aioclient_mock.post(RUN_URL, status=status, text=body)
    with pytest.raises(exc):
        await _client(hass).run_json(STT_MODEL, {})


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        {"success": False, "errors": []},
        {"success": True},
        {"success": True, "result": "text"},
        [1, 2],
    ],
)
async def test_unexpected_success_body_is_response_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, body: Any
) -> None:
    """A 200 without a usable result is a response error."""
    if isinstance(body, str):
        aioclient_mock.post(RUN_URL, text=body)
    else:
        aioclient_mock.post(RUN_URL, json=body)
    with pytest.raises(CloudflareResponseError):
        await _client(hass).run_json(STT_MODEL, {})


@pytest.mark.parametrize("exc", [asyncio.TimeoutError, aiohttp.ClientError])
async def test_network_failures_map_to_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, exc: type[Exception]
) -> None:
    """Timeouts and network errors map to CloudflareConnectionError."""
    aioclient_mock.post(RUN_URL, exc=exc)
    with pytest.raises(CloudflareConnectionError):
        await _client(hass).run_json(STT_MODEL, {})
    aioclient_mock.get(f"{API_BASE}/accounts/acc/tokens/verify", exc=exc)
    with pytest.raises(CloudflareConnectionError):
        await _client(hass).verify_token()


async def test_run_binary_error_is_typed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Binary calls raise typed errors too."""
    aioclient_mock.post(RUN_URL, status=429, json=QUOTA_ERROR_BODY)
    with pytest.raises(CloudflareQuotaError):
        await _client(hass).run_binary(STT_MODEL, {})


async def test_verify_token_ok_and_invalid(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verification uses the account endpoint, bypassing any gateway."""
    url = f"{API_BASE}/accounts/acc/tokens/verify"
    client = _client(hass, gateway_id="gw", gateway_token="gt")
    aioclient_mock.get(url, json={"success": True, "result": {"status": "active"}})
    await client.verify_token()
    assert str(aioclient_mock.mock_calls[0][1]) == url
    assert "cf-aig-authorization" not in aioclient_mock.mock_calls[0][3]

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        url,
        status=401,
        json={
            "success": False,
            "errors": [{"code": 1000, "message": "Invalid API Token"}],
        },
    )
    with pytest.raises(CloudflareAuthError):
        await client.verify_token()

    aioclient_mock.clear_requests()
    aioclient_mock.get(url, status=400, json=MALFORMED_HEADER_BODY)
    with pytest.raises(CloudflareAuthError):
        await client.verify_token()

    aioclient_mock.clear_requests()
    aioclient_mock.get(url, json={"success": False, "errors": []})
    with pytest.raises(CloudflareResponseError):
        await client.verify_token()


async def test_token_never_in_exception_text(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Exception text never contains the API or gateway token."""
    aioclient_mock.post(RUN_URL, status=401, json=AUTH_ERROR_BODY)
    client = _client(hass, gateway_id="gw", gateway_token="gateway-secret-value")
    aioclient_mock.post(
        f"{GATEWAY_BASE}/acc/gw/workers-ai/{STT_MODEL}",
        status=401,
        json=AUTH_ERROR_BODY,
    )
    with pytest.raises(CloudflareAuthError) as err:
        await client.run_json(STT_MODEL, {})
    assert API_TOKEN not in str(err.value)
    assert "gateway-secret-value" not in str(err.value)
