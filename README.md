<h1 align="center">Cloudflare Workers AI for Home Assistant</h1>

<p align="center">
  Speech-to-text and text-to-speech for the Home Assistant voice assistant (Assist), powered by Whisper and Deepgram Aura on Cloudflare Workers AI, free within the daily allocation.
</p>

<p align="center">
  <img alt="Home Assistant 2026.10.4+" src="https://img.shields.io/badge/Home%20Assistant-2026.10.4%2B-blue">
  <a href="https://github.com/kijart/ha-cloudflare-workers-ai/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/kijart/ha-cloudflare-workers-ai/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green">
</p>

## Features

- **Free within the daily allocation** — 10,000 neurons per day cover about 200 minutes of speech-to-text or 3,600 characters of text-to-speech. On the Workers Free plan, requests over the allocation fail instead of being billed. See [Costs and quota](#costs-and-quota).
- **Zero runtime dependencies** — `"requirements": []` in the manifest. HTTP goes through the aiohttp session of Home Assistant; no Cloudflare SDK is installed.
- **Minimal token permissions** — a token with only `Workers AI - Read` is enough for transcription, speech and model discovery, verified against the real API. See [docs/token.md](docs/token.md).
- **Models and voices discovered from Cloudflare** — the Whisper and Aura models and their voices are read from the Cloudflare catalog, so a new Aura language appears without an update. A retired model raises a repair issue instead of failing silently.
- **Whisper with silence filtering** — voice activity detection on, `condition_on_previous_text` off, and audio shorter than 0.3 s or longer than 30 s rejected locally, so silence and stuck microphones neither hallucinate text nor spend the allocation.
- **Tested** — unit tests with over 95 % coverage, `mypy --strict`, Ruff, `hassfest` and HACS validation in CI, plus a [live check](CONTRIBUTING.md#live-check) against the real API.
- **Home Assistant practices** — config flow with reauthentication and reconfiguration, diagnostics with the credentials redacted, and translated errors.
- **English and Spanish** user interface.

## Use cases

- **Voice assistant without AI hardware:** Assist on voice satellites or the mobile app, with transcription and speech in the cloud instead of on a small Home Assistant host.
- **Spanish voice control:** `aura-2-es` voices and Whisper in Spanish, with an initial prompt that lists room and device names.
- **Announcements:** `tts.speak` on any media player, for example for reminders or alerts from automations.

## Requirements

- Home Assistant 2026.10.4 or later.
- A Cloudflare account with Workers AI. The **Workers Free** plan is recommended: it turns the daily allocation into a spending limit.
- The Account ID and an account API token (see [docs/token.md](docs/token.md)).

## Installation

### HACS

1. In HACS, open the menu (⋮) → **Custom repositories**, add `https://github.com/kijart/ha-cloudflare-workers-ai` with the type **Integration**.
2. Download **Cloudflare Workers AI**, choosing a release.
3. Restart Home Assistant.

### Manual

1. Download the latest [release](https://github.com/kijart/ha-cloudflare-workers-ai/releases).
2. Copy `custom_components/cloudflare_workers_ai` into the `custom_components` folder of the Home Assistant configuration directory.
3. Restart Home Assistant.

### Removal

1. Go to **Settings → Devices & services → Cloudflare Workers AI**, open the menu (⋮) of the entry and choose **Delete**.
2. Remove the integration from HACS, or delete the `custom_components/cloudflare_workers_ai` folder, and restart Home Assistant.
3. Delete the API token in the Cloudflare dashboard.

## Configuration

1. Go to **Settings → Devices & services → Add integration** and choose **Cloudflare Workers AI**.
2. Enter the Account ID and the API token. The token is verified before the entry is created.
3. Optionally, open **Configure** on the entry to choose the models, the default voice and an initial prompt.
4. Go to **Settings → Voice assistants**, open a pipeline and select **Cloudflare Workers AI** as the speech-to-text and text-to-speech engines. The voice can be chosen per pipeline.

Setup fields:

| Option          | Values                                                                                     |
| --------------- | ------------------------------------------------------------------------------------------ |
| Account ID      | Cloudflare account ID                                                                      |
| API token       | Account API token with `Workers AI - Read`                                                 |
| Use AI Gateway  | Off (default) · On                                                                         |
| Gateway ID      | Name of the AI Gateway; required when AI Gateway is on                                     |
| Gateway token   | Token of an authenticated gateway; empty for a gateway without authentication              |

Options (**Configure**):

| Option                | Values                                                                                                            |
| --------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Speech-to-text model  | Whisper models in the catalog · default `@cf/openai/whisper-large-v3-turbo`                                       |
| Initial prompt        | Optional text with room and device names that helps the transcription                                             |
| Text-to-speech model  | Aura models in the catalog (`@cf/deepgram/aura-2-es`, `aura-2-en`, `aura-1`) · default `@cf/deepgram/aura-2-es`   |
| Voice                 | Voices of the selected Aura model · default `aquila`                                                              |

### How data is updated

Nothing is polled. Speech-to-text and text-to-speech call Cloudflare only when Assist or an action needs them, one request each. The model and voice catalog is fetched when the entry is set up (at startup, on reload and after saving the options) and each time **Configure** opens. If that fails, the defaults are offered and the saved settings keep working. The token and AI Gateway settings are changed with **Reconfigure**, without deleting the entry.

## Costs and quota

Prices and limits from the [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) page, checked in November 2026:

|                         |                                                                                                       |
| ----------------------- | ----------------------------------------------------------------------------------------------------- |
| Free allocation         | 10,000 neurons per day, shared by speech-to-text and text-to-speech; resets at 00:00 UTC              |
| Speech-to-text          | about 46.6 neurons per minute of audio: about 200 minutes per day                                     |
| Text-to-speech          | $0.03 per 1,000 characters: about 3,600 characters per day                                            |
| Over the allocation     | Workers Free: requests fail and nothing is billed · Workers Paid: $0.011 per 1,000 neurons            |
| Integration limits      | audio up to 30 s and text up to 2,000 characters per request                                          |

The plan is shown in the Cloudflare dashboard under **Workers & Pages → Plans** or **Billing → Subscriptions**. A paid plan for a domain is not Workers Paid. Home Assistant caches the generated speech, so repeated phrases are not synthesized again.

## Privacy

- **What leaves the home:** the recorded audio of each voice command and the text to be spoken, plus the requests that verify the token and list the models. Everything goes over HTTPS to `api.cloudflare.com`; with AI Gateway on, the audio and the text go to `gateway.ai.cloudflare.com` instead. Nothing else is contacted.
- **At Cloudflare:** Whisper and Aura-2 are listed with zero data retention by Cloudflare. The handling of the data is subject to the Cloudflare terms.
- **In Home Assistant:** the Account ID and the tokens are stored in the config entry under `.storage`, in plain text, as for every integration. They never appear in the logs, and diagnostics redact them.
- **AI Gateway (optional, off by default):** gateway logs keep requests and responses in Cloudflare unless logging is turned off in the gateway settings. Caching saves nothing here: every recording is different, and Home Assistant already caches the speech.

## Known limitations

- Only the Whisper family for speech-to-text and the Aura family for text-to-speech. Other models in the catalog, such as Deepgram Nova-3 and Flux, are not offered.
- Text-to-speech is not streamed: the audio is returned once it is complete.
- Text longer than 2,000 characters is rejected with an error, not truncated.
- The text-to-speech language is the language of the selected Aura model (`aura-2-es` → Spanish, `aura-2-en` and `aura-1` → English), one language per entry.
- Speech-to-text accepts 16 kHz, 16-bit mono PCM, as sent by Assist, between 0.3 and 30 seconds long.

## Troubleshooting

- **Daily quota exhausted:** speech-to-text returns no result and text-to-speech fails with "The Cloudflare Workers AI daily quota is exhausted". A warning is logged once per UTC day, the entities stay available and requests work again after 00:00 UTC. No reauthentication is needed.
- **Reauthentication required:** the token was rejected (expired, revoked, or blocked by its IP filter after the public IP changed). Open the reauthentication prompt in **Settings → Devices & services** and enter a new token, or fix the IP filter in Cloudflare and reload the entry. See [docs/token.md](docs/token.md).
- **Configured model is no longer available:** a repair issue appears when the catalog fetched at setup (startup, reload or saving the options) no longer lists the selected model. Choose another model in **Configure**; saving reloads the entry and clears the issue.
- **Only the default models are offered:** the catalog could not be fetched. The saved models keep working; open **Configure** again later.
- **More detail:** enable debug logging for the integration from its entry, or download its diagnostics, which redact the credentials.

## AI assistance

This project was developed with the help of AI coding assistants, used to generate and refactor code. All code has been manually reviewed and tested; the design, decisions and responsibility remain with the author.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), including how to add a language. Security problems: see [SECURITY.md](SECURITY.md).

## Credits

Inspired by [bjesus/ha-cloudflare-ai](https://github.com/bjesus/ha-cloudflare-ai). This project is new code and only uses it as a reference.

## License

[MIT](LICENSE)
