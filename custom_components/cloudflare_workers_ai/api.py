"""Minimal Cloudflare Workers AI HTTP client."""

from http import HTTPStatus
import json
from typing import Any

import aiohttp

from .const import (
    API_BASE,
    AUTH_ERROR_CODES,
    GATEWAY_BASE,
    QUOTA_ERROR_CODES,
    REQUEST_TIMEOUT,
)


class CloudflareError(Exception):
    """Base error for the Cloudflare client."""


class CloudflareAuthError(CloudflareError):
    """The token was rejected."""


class CloudflareConnectionError(CloudflareError):
    """Network failure, timeout or server error."""


class CloudflareQuotaError(CloudflareError):
    """The daily quota is exhausted."""


class CloudflareResponseError(CloudflareError):
    """Other client error or unexpected body."""


def _parse_json(raw: bytes) -> Any:
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _errors(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        return []
    errors = body.get("errors")
    if not isinstance(errors, list):
        return []
    return [error for error in errors if isinstance(error, dict)]


def _describe(status: int, errors: list[dict[str, Any]]) -> str:
    details = "; ".join(f"{e.get('code')}: {e.get('message')}" for e in errors)
    return f"Cloudflare API returned HTTP {status}" + (
        f" ({details})" if details else ""
    )


def _raise_for_error(status: int, body: Any) -> None:
    errors = _errors(body)
    codes = {error.get("code") for error in errors}
    message = _describe(status, errors)
    if status == HTTPStatus.TOO_MANY_REQUESTS or codes & QUOTA_ERROR_CODES:
        raise CloudflareQuotaError(message)
    if (
        status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN)
        or codes & AUTH_ERROR_CODES
    ):
        raise CloudflareAuthError(message)
    if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        raise CloudflareConnectionError(message)
    raise CloudflareResponseError(message)


class CloudflareClient:
    """Client for the Workers AI REST API, optionally through AI Gateway."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        account_id: str,
        api_token: str,
        gateway_id: str | None = None,
        gateway_token: str | None = None,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._account_id = account_id
        self._api_token = api_token
        self._gateway_id = gateway_id
        self._gateway_token = gateway_token

    def _headers(self, *, via_gateway: bool) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._api_token}"}
        if via_gateway and self._gateway_token:
            headers["cf-aig-authorization"] = f"Bearer {self._gateway_token}"
        return headers

    def _run_url(self, model: str) -> str:
        # Model slashes must stay literal; encoded slashes return "No route".
        if self._gateway_id:
            return (
                f"{GATEWAY_BASE}/{self._account_id}/{self._gateway_id}"
                f"/workers-ai/{model}"
            )
        return f"{API_BASE}/accounts/{self._account_id}/ai/run/{model}"

    async def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        *,
        params: dict[str, str] | None = None,
        via_gateway: bool = False,
    ) -> tuple[bytes, str]:
        try:
            async with self._session.request(
                method,
                url,
                json=payload,
                params=params,
                headers=self._headers(via_gateway=via_gateway),
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                body = await response.read()
                if response.status >= HTTPStatus.BAD_REQUEST:
                    _raise_for_error(response.status, _parse_json(body))
                return body, response.headers.get("Content-Type", "")
        except TimeoutError as err:
            raise CloudflareConnectionError("Request to Cloudflare timed out") from err
        except aiohttp.ClientError as err:
            raise CloudflareConnectionError(
                f"Request to Cloudflare failed: {type(err).__name__}"
            ) from err

    async def verify_token(self) -> None:
        """Verify the account API token."""
        body, _ = await self._request(
            "GET", f"{API_BASE}/accounts/{self._account_id}/tokens/verify"
        )
        if not _is_success(_parse_json(body)):
            raise CloudflareResponseError("Token verification was not successful")

    async def run_json(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Run a model and return the unwrapped result."""
        body, _ = await self._request(
            "POST",
            self._run_url(model),
            payload,
            via_gateway=bool(self._gateway_id),
        )
        data = _parse_json(body)
        if not _is_success(data) or not isinstance(data.get("result"), dict):
            raise CloudflareResponseError("Unexpected response body from Cloudflare")
        result: dict[str, Any] = data["result"]
        return result

    async def run_binary(
        self, model: str, payload: dict[str, Any]
    ) -> tuple[bytes, str]:
        """Run a model that returns raw bytes."""
        return await self._request(
            "POST",
            self._run_url(model),
            payload,
            via_gateway=bool(self._gateway_id),
        )

    async def list_models(self, task: str) -> list[dict[str, Any]]:
        """List the models available for a task."""
        body, _ = await self._request(
            "GET",
            f"{API_BASE}/accounts/{self._account_id}/ai/models/search",
            params={"task": task},
        )
        data = _parse_json(body)
        if not _is_success(data) or not isinstance(data.get("result"), list):
            raise CloudflareResponseError("Unexpected response body from Cloudflare")
        return [model for model in data["result"] if isinstance(model, dict)]

    async def get_input_schema(self, model: str) -> dict[str, Any]:
        """Return the JSON schema of the input of a model."""
        body, _ = await self._request(
            "GET",
            f"{API_BASE}/accounts/{self._account_id}/ai/models/schema",
            params={"model": model},
        )
        data = _parse_json(body)
        result = data.get("result") if _is_success(data) else None
        schema = result.get("input") if isinstance(result, dict) else None
        if not isinstance(schema, dict):
            raise CloudflareResponseError("Unexpected response body from Cloudflare")
        return schema


def _is_success(data: Any) -> bool:
    return isinstance(data, dict) and data.get("success") is True
