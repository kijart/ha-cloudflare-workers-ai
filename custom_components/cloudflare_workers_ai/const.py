"""Constants for the Cloudflare Workers AI integration."""

DOMAIN = "cloudflare_workers_ai"

CONF_ACCOUNT_ID = "account_id"
CONF_USE_GATEWAY = "use_gateway"
CONF_GATEWAY_ID = "gateway_id"
CONF_GATEWAY_TOKEN = "gateway_token"
CONF_STT_MODEL = "stt_model"
CONF_STT_PROMPT = "stt_initial_prompt"
CONF_TTS_MODEL = "tts_model"
CONF_TTS_VOICE = "tts_voice"

DEFAULT_STT_MODEL = "@cf/openai/whisper-large-v3-turbo"
DEFAULT_TTS_MODEL = "@cf/deepgram/aura-2-es"
DEFAULT_TTS_VOICE = "aquila"

ISSUE_MODEL_UNAVAILABLE = "model_unavailable"

API_BASE = "https://api.cloudflare.com/client/v4"
GATEWAY_BASE = "https://gateway.ai.cloudflare.com/v1"

REQUEST_TIMEOUT = 30
MIN_STT_AUDIO_MS = 300
MAX_STT_AUDIO_SECONDS = 30
MAX_TTS_CHARS = 2000

# Daily free allocation exhausted
QUOTA_ERROR_CODES = frozenset({4006})
# 6003: invalid request headers (HTTP 400 for a malformed token); 10000: authentication error
AUTH_ERROR_CODES = frozenset({6003, 10000})

STT_SAMPLE_RATE = 16000
STT_SAMPLE_WIDTH_BYTES = 2
STT_CHANNELS = 1
STT_BYTES_PER_SECOND = STT_SAMPLE_RATE * STT_SAMPLE_WIDTH_BYTES * STT_CHANNELS
MIN_STT_AUDIO_BYTES = STT_BYTES_PER_SECOND * MIN_STT_AUDIO_MS // 1000
MAX_STT_AUDIO_BYTES = STT_BYTES_PER_SECOND * MAX_STT_AUDIO_SECONDS

WHISPER_LANGUAGES = [
    "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs", "ca",
    "cs", "cy", "da", "de", "el", "en", "es", "et", "eu", "fa", "fi", "fo", "fr",
    "gl", "gu", "ha", "he", "hi", "hr", "ht", "hu", "hy", "id", "is", "it", "ja",
    "jw", "ka", "kk", "km", "kn", "ko", "la", "lb", "ln", "lo", "lt", "lv", "mg",
    "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my", "ne", "nl", "nn", "no", "oc",
    "pa", "pl", "ps", "pt", "ro", "ru", "sa", "sd", "si", "sk", "sl", "sn", "so",
    "sq", "sr", "su", "sv", "sw", "ta", "te", "tg", "th", "tk", "tl", "tr", "tt",
    "uk", "ur", "uz", "vi", "yi", "yo", "zh",
]  # fmt: skip
