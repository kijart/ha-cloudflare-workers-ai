# Model families

A model is offered only if it belongs to a family declared in `custom_components/cloudflare_workers_ai/models.py` (`FAMILIES`). A family has a key, a task and a pattern that matches the model IDs it covers; discovery lists the catalog models of that task and keeps those that match.

Today there are two families:

| Key | Task | Models |
| --- | --- | --- |
| `whisper` | Automatic Speech Recognition | `@cf/openai/whisper-large-v3-turbo` |
| `aura` | Text-to-Speech | `@cf/deepgram/aura-1`, `@cf/deepgram/aura-2-<language>` |

The patterns are narrow on purpose: a model is added only after its request and response were verified against the real API. `@cf/openai/whisper` is left out because it only accepts a byte array or binary body, while `stt.py` sends JSON with the audio in base64.

## Adding a family with a binary request body

Requests are currently built in `stt.py` and `tts.py`, and `api.py` always sends JSON. Supporting a model that takes raw audio needs these changes:

1. **`api.py`:** let `_request` accept raw bytes and a `Content-Type` instead of a JSON payload, and add a `run_audio` method that posts them to the model URL. The existing `run_binary` is about binary *responses* (the MP3 returned by Aura), not binary requests.
2. **`models.py`:** extend `ModelFamily` with the request builder (audio and options in, payload or bytes out) and the response parser (response body in, transcript out), and give the new family its pattern.
3. **`stt.py`:** pick the family with `family_for(model)` and dispatch to its builder and parser, instead of building the Whisper payload inline.
4. **Tests and docs:** record a real response as a fixture, cover the request and the parsing, and update the README limitations.

The `scripts/live_check.py` run described in [CONTRIBUTING.md](../CONTRIBUTING.md#live-check) is the way to check the new model against the real API.
