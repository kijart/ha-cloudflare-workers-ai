"""Check the integration client against the real Cloudflare Workers AI API.

Reads CF_ACCOUNT_ID and CF_API_TOKEN (and optionally CF_GATEWAY_ID and
CF_GATEWAY_TOKEN) from the environment. Never prints credentials.
Exits with a non-zero code when any step fails.
"""

import asyncio
import base64
import os
from pathlib import Path
import sys
import unicodedata

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.cloudflare_workers_ai.api import (
    CloudflareClient,
    CloudflareError,
)
from custom_components.cloudflare_workers_ai.const import (
    DEFAULT_STT_MODEL,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
)
from custom_components.cloudflare_workers_ai.models import async_discover

PHRASE = "Enciende la luz del salón"
EXPECTED_WORDS = ("luz", "salon")


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


async def _check(client: CloudflareClient) -> bool:
    await client.verify_token()
    print("verify_token: ok")

    catalog = await async_discover(client)
    print(f"discovered: {catalog.discovered}")
    print(f"stt models: {', '.join(catalog.stt_models)}")
    for model in catalog.tts_models:
        print(f"tts model {model}: {', '.join(catalog.voices.get(model, []))}")
    if not catalog.discovered:
        print("FAIL: model discovery fell back to the defaults")
        return False

    audio, content_type = await client.run_binary(
        DEFAULT_TTS_MODEL, {"text": PHRASE, "speaker": DEFAULT_TTS_VOICE}
    )
    print(f"tts {DEFAULT_TTS_MODEL}: {len(audio)} bytes, {content_type}")
    if not audio or not content_type.startswith("audio/"):
        print("FAIL: text-to-speech did not return audio")
        return False

    result = await client.run_json(
        DEFAULT_STT_MODEL,
        {
            "audio": base64.b64encode(audio).decode(),
            "language": "es",
            "vad_filter": True,
            "condition_on_previous_text": False,
        },
    )
    text = str(result.get("text", "")).strip()
    print(f"stt {DEFAULT_STT_MODEL}: {text!r}")
    missing = [word for word in EXPECTED_WORDS if word not in _normalize(text)]
    if missing:
        print(f"FAIL: transcript lacks {', '.join(missing)}")
        return False
    return True


async def main() -> int:
    """Run the live check and return the exit code."""
    account_id = os.environ.get("CF_ACCOUNT_ID")
    api_token = os.environ.get("CF_API_TOKEN")
    if not account_id or not api_token:
        print("FAIL: CF_ACCOUNT_ID and CF_API_TOKEN must be set")
        return 2
    gateway_id = os.environ.get("CF_GATEWAY_ID") or None
    print(f"via AI Gateway: {'yes' if gateway_id else 'no'}")
    async with aiohttp.ClientSession() as session:
        client = CloudflareClient(
            session,
            account_id,
            api_token,
            gateway_id=gateway_id,
            gateway_token=os.environ.get("CF_GATEWAY_TOKEN") or None,
        )
        try:
            passed = await _check(client)
        except CloudflareError as err:
            print(f"FAIL: {type(err).__name__}: {err}")
            return 1
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
