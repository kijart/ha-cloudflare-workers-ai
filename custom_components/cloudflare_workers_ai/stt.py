"""Speech-to-text platform using Cloudflare Workers AI Whisper."""

import base64
from collections.abc import AsyncIterable
import io
import logging
import wave

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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CloudflareWorkersAIConfigEntry
from .api import (
    CloudflareAuthError,
    CloudflareError,
    CloudflareGatewayAuthError,
    CloudflareQuotaError,
)
from .const import (
    CONF_STT_MODEL,
    CONF_STT_PROMPT,
    DEFAULT_STT_MODEL,
    MAX_STT_AUDIO_BYTES,
    MIN_STT_AUDIO_BYTES,
    STT_CHANNELS,
    STT_SAMPLE_RATE,
    STT_SAMPLE_WIDTH_BYTES,
    WHISPER_LANGUAGES,
)
from .entity import GATEWAY_REJECTED_MESSAGE, CloudflareWorkersAIEntity, warn_quota_once

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_ERROR = SpeechResult(None, SpeechResultState.ERROR)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CloudflareWorkersAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the speech-to-text entity."""
    async_add_entities([CloudflareSTTEntity(entry)])


def _to_wav(pcm: bytes) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(STT_CHANNELS)
        wav.setsampwidth(STT_SAMPLE_WIDTH_BYTES)
        wav.setframerate(STT_SAMPLE_RATE)
        wav.writeframes(pcm)
    return buffer.getvalue()


class CloudflareSTTEntity(CloudflareWorkersAIEntity, SpeechToTextEntity):
    """Whisper speech-to-text entity."""

    def __init__(self, entry: CloudflareWorkersAIConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__(entry, "stt")

    @property
    def supported_languages(self) -> list[str]:
        """Return the languages supported by Whisper."""
        return WHISPER_LANGUAGES

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return the supported audio formats."""
        return [AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return the supported audio codecs."""
        return [AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return the supported bit rates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return the supported sample rates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return the supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Transcribe an audio stream."""
        audio = bytearray()
        too_long = False
        async for chunk in stream:
            if len(audio) + len(chunk) > MAX_STT_AUDIO_BYTES:
                too_long = True
            elif not too_long:
                audio.extend(chunk)
        if too_long or len(audio) < MIN_STT_AUDIO_BYTES:
            return _ERROR

        options = self._entry.options
        payload: dict[str, object] = {
            "audio": base64.b64encode(_to_wav(bytes(audio))).decode(),
            "language": metadata.language,
            "vad_filter": True,
            "condition_on_previous_text": False,
        }
        if prompt := options.get(CONF_STT_PROMPT):
            payload["initial_prompt"] = prompt

        data = self._entry.runtime_data
        try:
            result = await data.client.run_json(
                options.get(CONF_STT_MODEL, DEFAULT_STT_MODEL), payload
            )
        except CloudflareAuthError:
            self._entry.async_start_reauth(self.hass)
            return _ERROR
        except CloudflareGatewayAuthError:
            _LOGGER.warning(GATEWAY_REJECTED_MESSAGE)
            return _ERROR
        except CloudflareQuotaError:
            warn_quota_once(data, _LOGGER)
            return _ERROR
        except CloudflareError as err:
            _LOGGER.warning("Speech-to-text request failed: %s", err)
            return _ERROR

        text = result.get("text")
        if not isinstance(text, str) or not text.strip():
            return _ERROR
        return SpeechResult(text.strip(), SpeechResultState.SUCCESS)
