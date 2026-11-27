# Contributing

Contributions are welcome, and translations are the easiest way to help: a new language, or a fix to a string that reads wrong. Bug reports and small fixes are welcome too. For larger changes, such as support for another model family, please open an [issue](https://github.com/kijart/ha-cloudflare-workers-ai/issues) first to agree on the approach. [docs/model-families.md](docs/model-families.md) describes how a new family is added.

Security problems are not reported in issues: see [SECURITY.md](SECURITY.md).

## Running the integration locally

Requires [uv](https://docs.astral.sh/uv/). The Python version is pinned in `.python-version`, and the development dependencies, including `pytest-homeassistant-custom-component`, are locked in `uv.lock`.

```sh
make install    # create .venv with the locked dependencies
make test       # run the tests with coverage (fails below 95 %)
make lint       # ruff check, ruff format --check and mypy --strict
make format     # apply ruff fixes and formatting
```

CI runs `make lint` and `make test`, plus `hassfest` and the HACS validation. The tests simulate the Cloudflare API with recorded responses and never reach the network.

To try a change in Home Assistant, copy `custom_components/cloudflare_workers_ai` into the `custom_components` folder of a development instance and restart it. Debug logs are under the `custom_components.cloudflare_workers_ai` logger.

### Live check

`scripts/live_check.py` runs the integration client against the real API: it verifies the token, discovers the models and voices, synthesizes "Enciende la luz del salón" with Aura and transcribes it back with Whisper. It exits with a non-zero code if any step fails or the transcript lacks "luz" and "salón". It makes about eight requests, only two of which run a model and spend a few neurons of the daily allocation, so it is run by hand and is not part of CI or `pytest`.

```sh
export CF_ACCOUNT_ID=...      # Account ID
export CF_API_TOKEN=...       # account API token with Workers AI - Read
# optional: export CF_GATEWAY_ID=... CF_GATEWAY_TOKEN=...
uv run python scripts/live_check.py
```

The script prints model IDs, voices, byte counts and the transcript, never the token or the Account ID. A change to `api.py` or `models.py` is worth checking with it before opening a pull request.

## Translations

The UI text lives in [`strings.json`](custom_components/cloudflare_workers_ai/strings.json), the English base. [`translations/en.json`](custom_components/cloudflare_workers_ai/translations/en.json) is an identical copy, and each other language has its own file, such as [`translations/es.json`](custom_components/cloudflare_workers_ai/translations/es.json).

### Fixing a string

Change only the value in the language file. For an English string, change both `strings.json` and `translations/en.json`.

### Adding a language

The steps use French (`fr`) as the example.

1. Copy `translations/en.json` to `translations/fr.json` and translate every value.
2. Update the "English and Spanish" feature line of the [README](README.md#features).

### Rules for strings

- **Every key** of `strings.json` is present in the new file, with the same structure.
- **Placeholders** such as `{account_id}`, `{model}` and `{max_length}` stay as they are (not translated); they can move within the sentence.
- **Not translated:** product and model names such as Cloudflare, Workers AI, AI Gateway, Whisper and Aura.
- **Tone:** short and impersonal, without addressing the reader ("Enter a new API token.", "The account ID must match the one already configured."). In Spanish, no *tú* or *usted*.

### Checking a translation

Set the language in the Home Assistant user profile, then open the integration setup, **Configure**, and the reauthentication and reconfiguration steps.

## Commits and pull requests

1. Fork the repository and create a branch from `main` (e.g. `feat/i18n-french`).
2. Keep each pull request to one change, and run `make lint` and `make test` before opening it.
3. Open the pull request against `main`, describing what changes and how it was checked.

Commit messages and pull request titles follow [Conventional Commits](https://www.conventionalcommits.org/): a single line of at most 72 characters, in English, in the imperative and without a final period (`fix(stt): reject audio shorter than 0.3 s`). Release Please reads them to decide the next version and write the changelog:

| Type | Use | Release |
| --- | --- | --- |
| `feat` | New feature (e.g. `feat(i18n): add French`) | minor (`x.Y.0`) |
| `fix` | Bug fix (e.g. `fix(tts): keep the saved voice after a reload`) | patch (`x.y.Z`) |
| `perf` | Performance improvement | patch |
| `revert` | Reverts an earlier commit | patch |
| `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore` | Changes that users don't see | none on their own |

A breaking change adds `!` after the type (`feat!: …`). While the version is below 1.0 it makes a minor release; from 1.0 on, a major one (`X.0.0`).

## License

Contributions are licensed under the project's [MIT License](LICENSE).
