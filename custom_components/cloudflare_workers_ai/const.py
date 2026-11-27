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
