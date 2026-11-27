"""Model families and runtime model discovery."""

from dataclasses import dataclass
import re

from .api import CloudflareClient, CloudflareError
from .const import DEFAULT_STT_MODEL, DEFAULT_TTS_MODEL

TASK_ASR = "Automatic Speech Recognition"
TASK_TTS = "Text-to-Speech"

FALLBACK_AURA_2_ES_VOICES: tuple[str, ...] = (
    "aquila",
    "alvaro",
    "carina",
    "celeste",
    "diana",
    "estrella",
    "javier",
    "nestor",
    "selena",
    "sirio",
)

AURA_1_LANGUAGE = "en"
_AURA_LANGUAGE = re.compile(r"^@cf/deepgram/aura-2-([a-z]{2})$")


@dataclass(frozen=True)
class ModelFamily:
    """A group of models that share a task and request format."""

    key: str
    task: str
    pattern: re.Pattern[str]


FAMILIES: tuple[ModelFamily, ...] = (
    ModelFamily(
        "whisper", TASK_ASR, re.compile(r"^@cf/openai/whisper-large-v3-turbo$")
    ),
    ModelFamily("aura", TASK_TTS, re.compile(r"^@cf/deepgram/aura-(1|2-[a-z]{2})$")),
)


def family_for(model: str) -> ModelFamily | None:
    """Return the family of a model, or None if unsupported."""
    return next((f for f in FAMILIES if f.pattern.match(model)), None)


def tts_language(model: str) -> str | None:
    """Return the language code of an Aura model."""
    if model == "@cf/deepgram/aura-1":
        return AURA_1_LANGUAGE
    match = _AURA_LANGUAGE.match(model)
    return match.group(1) if match else None


@dataclass
class ModelCatalog:
    """Models and voices offered by the integration."""

    stt_models: list[str]
    tts_models: list[str]
    voices: dict[str, list[str]]
    discovered: bool


def fallback_catalog() -> ModelCatalog:
    """Return the catalog made of the default models."""
    return ModelCatalog(
        stt_models=[DEFAULT_STT_MODEL],
        tts_models=[DEFAULT_TTS_MODEL],
        voices={DEFAULT_TTS_MODEL: list(FALLBACK_AURA_2_ES_VOICES)},
        discovered=False,
    )


def _ordered(models: set[str], default: str) -> list[str]:
    return sorted(models, key=lambda model: (model != default, model))


async def _family_models(
    client: CloudflareClient, family: ModelFamily, default: str
) -> list[str]:
    found = {
        name
        for model in await client.list_models(family.task)
        if isinstance(name := model.get("name"), str) and family_for(name) == family
    }
    return _ordered(found, default)


async def _voices(client: CloudflareClient, model: str) -> list[str] | None:
    try:
        schema = await client.get_input_schema(model)
        voices = schema["properties"]["speaker"]["enum"]
    except CloudflareError, KeyError, TypeError:
        return list(FALLBACK_AURA_2_ES_VOICES) if model == DEFAULT_TTS_MODEL else None
    if not isinstance(voices, list) or not voices:
        return None
    return [str(voice) for voice in voices]


async def async_discover(client: CloudflareClient) -> ModelCatalog:
    """Discover models and voices, falling back to the defaults on error."""
    asr, tts = FAMILIES
    try:
        stt_models = await _family_models(client, asr, DEFAULT_STT_MODEL)
        tts_models = await _family_models(client, tts, DEFAULT_TTS_MODEL)
        voices: dict[str, list[str]] = {}
        for model in tts_models:
            if (model_voices := await _voices(client, model)) is not None:
                voices[model] = model_voices
    except CloudflareError:
        return fallback_catalog()
    if not stt_models or not voices:
        return fallback_catalog()
    return ModelCatalog(
        stt_models=stt_models,
        tts_models=list(voices),
        voices=voices,
        discovered=True,
    )
