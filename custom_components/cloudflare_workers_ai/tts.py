"""Text-to-speech platform using Cloudflare Workers AI Deepgram Aura."""

import logging
from typing import Any

from homeassistant.components.tts import ATTR_VOICE, TextToSpeechEntity, TtsAudioType
from homeassistant.components.tts.models import Voice
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CloudflareWorkersAIConfigEntry
from .api import CloudflareAuthError, CloudflareError, CloudflareQuotaError
from .const import (
    CONF_TTS_MODEL,
    CONF_TTS_VOICE,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    DOMAIN,
    MAX_TTS_CHARS,
)
from .entity import CloudflareWorkersAIEntity, warn_quota_once
from .models import FALLBACK_AURA_2_ES_VOICES, tts_language

_LOGGER = logging.getLogger(__name__)

_FALLBACK_LANGUAGE = "en"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CloudflareWorkersAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the text-to-speech entity."""
    async_add_entities([CloudflareTTSEntity(entry)])


def _failed() -> HomeAssistantError:
    return HomeAssistantError(translation_domain=DOMAIN, translation_key="tts_failed")


class CloudflareTTSEntity(CloudflareWorkersAIEntity, TextToSpeechEntity):
    """Deepgram Aura text-to-speech entity."""

    _attr_supported_options = [ATTR_VOICE]

    def __init__(self, entry: CloudflareWorkersAIConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__(entry, "tts")

    @property
    def _model(self) -> str:
        return str(self._entry.options.get(CONF_TTS_MODEL, DEFAULT_TTS_MODEL))

    @property
    def default_language(self) -> str:
        """Return the language of the configured Aura model."""
        return tts_language(self._model) or _FALLBACK_LANGUAGE

    @property
    def supported_languages(self) -> list[str]:
        """Return the language of the configured Aura model."""
        return [self.default_language]

    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return the voices of the configured model for its language."""
        if language != self.default_language:
            return None
        voices = self._entry.runtime_data.catalog.voices.get(self._model)
        if not voices and self._model == DEFAULT_TTS_MODEL:
            voices = list(FALLBACK_AURA_2_ES_VOICES)
        if not voices:
            return None
        return [Voice(voice, voice.capitalize()) for voice in voices]

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Synthesize speech and return it as MP3."""
        if len(message) > MAX_TTS_CHARS:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="message_too_long",
                translation_placeholders={"max_length": str(MAX_TTS_CHARS)},
            )
        voice = options.get(ATTR_VOICE) or self._entry.options.get(
            CONF_TTS_VOICE, DEFAULT_TTS_VOICE
        )
        data = self._entry.runtime_data
        try:
            audio, content_type = await data.client.run_binary(
                self._model, {"text": message, "speaker": voice}
            )
        except CloudflareAuthError as err:
            self._entry.async_start_reauth(self.hass)
            raise _failed() from err
        except CloudflareQuotaError as err:
            warn_quota_once(data, _LOGGER)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="quota_exceeded"
            ) from err
        except CloudflareError as err:
            _LOGGER.warning("Text-to-speech request failed: %s", err)
            raise _failed() from err
        if not audio or not content_type.startswith("audio/"):
            _LOGGER.warning("Text-to-speech response is not audio: %s", content_type)
            raise _failed()
        return "mp3", audio
