"""Tests for the config flow."""

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.cloudflare_workers_ai.api import (
    CloudflareAuthError,
    CloudflareConnectionError,
)
from custom_components.cloudflare_workers_ai.const import (
    CONF_ACCOUNT_ID,
    CONF_GATEWAY_ID,
    CONF_GATEWAY_TOKEN,
    CONF_USE_GATEWAY,
    DOMAIN,
)
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

API_TOKEN = "test-api-token-secret"
USER_INPUT = {
    CONF_ACCOUNT_ID: "acc",
    CONF_API_TOKEN: API_TOKEN,
    CONF_USE_GATEWAY: False,
}
VERIFY = "custom_components.cloudflare_workers_ai.api.CloudflareClient.verify_token"
SETUP = "custom_components.cloudflare_workers_ai.async_setup_entry"


async def _start(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    return result["flow_id"]


async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_cloudflare: AiohttpClientMocker
) -> None:
    """A valid token creates the entry keyed by account ID."""
    flow_id = await _start(hass)
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cloudflare Workers AI"
    assert result["result"].unique_id == "acc"
    assert result["data"] == USER_INPUT


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (CloudflareAuthError, "invalid_auth"),
        (CloudflareConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_user_flow_errors_then_recovers(
    hass: HomeAssistant,
    mock_cloudflare: AiohttpClientMocker,
    exc: type[Exception],
    error: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Errors are shown and the flow can then complete."""
    flow_id = await _start(hass)
    with patch(VERIFY, side_effect=exc("boom")):
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert API_TOKEN not in caplog.text

    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_gateway_id_required_when_enabled(
    hass: HomeAssistant, mock_cloudflare: AiohttpClientMocker
) -> None:
    """Enabling the gateway without a gateway ID is rejected."""
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**USER_INPUT, CONF_USE_GATEWAY: True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "gateway_id_required"}


async def test_user_flow_with_gateway(
    hass: HomeAssistant, mock_cloudflare: AiohttpClientMocker
) -> None:
    """Gateway fields are stored and used for the verification request."""
    data = {
        **USER_INPUT,
        CONF_USE_GATEWAY: True,
        CONF_GATEWAY_ID: "gw",
        CONF_GATEWAY_TOKEN: "gw-token-secret",
    }
    flow_id = await _start(hass)
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(flow_id, data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == data


async def test_user_flow_aborts_if_account_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """A second entry for the same account is aborted."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """A valid new token is stored and the entry reloads."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: "new-api-token-secret"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == "new-api-token-secret"


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (CloudflareAuthError, "invalid_auth"),
        (CloudflareConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
    exc: type[Exception],
    error: str,
) -> None:
    """Verification errors are shown on the reauth form."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    with patch(VERIFY, side_effect=exc("boom")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: "new-api-token-secret"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert mock_config_entry.data[CONF_API_TOKEN] != "new-api-token-secret"


async def test_reconfigure_changes_token_and_gateway(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Token and gateway settings are updated for the same account."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    data = {
        **USER_INPUT,
        CONF_API_TOKEN: "new-api-token-secret",
        CONF_USE_GATEWAY: True,
        CONF_GATEWAY_ID: "gw",
    }
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == data


async def test_reconfigure_error_then_gateway_required(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Validation errors are shown on the reconfigure form."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_USE_GATEWAY: True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "gateway_id_required"}


async def test_reconfigure_other_account_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloudflare: AiohttpClientMocker,
) -> None:
    """Changing the account ID aborts and leaves the entry untouched."""
    mock_config_entry.add_to_hass(hass)
    original = dict(mock_config_entry.data)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_ACCOUNT_ID: "other"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert dict(mock_config_entry.data) == original


async def test_reconfigure_disabling_gateway_drops_stale_keys(
    hass: HomeAssistant, mock_cloudflare: AiohttpClientMocker
) -> None:
    """Gateway keys omitted from the form are removed from the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="acc",
        data={
            **USER_INPUT,
            CONF_USE_GATEWAY: True,
            CONF_GATEWAY_ID: "gw",
            CONF_GATEWAY_TOKEN: "gw-token-secret",
        },
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["reason"] == "reconfigure_successful"
    assert dict(entry.data) == USER_INPUT
