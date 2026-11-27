# Releasing

Releases are automated with [release-please](https://github.com/googleapis/release-please-action) from the [Conventional Commits](https://www.conventionalcommits.org) on `main`.

## How a release happens

1. Every push to `main` updates an open release pull request with the next version, the `CHANGELOG.md` entry and the `version` field of `custom_components/cloudflare_workers_ai/manifest.json`. Only `feat`, `fix`, `perf` and `revert` commits are listed in the changelog and start a release; other types (`docs`, `refactor`, `style`, `test`, `build`, `ci`, `chore`) ship with the next release without a changelog entry.
2. Merging that pull request (with **Rebase and merge** or **Squash and merge**, to keep the history linear) creates the tag `X.Y.Z` (no `v` prefix) and the GitHub Release. HACS offers these releases as the installable versions.

The first release is `0.1.0`: `.release-please-manifest.json` starts at `0.0.0` and `initial-version` sets the first proposed version. Before 1.0.0, `feat` bumps the minor version and breaking changes do too.

## One-time setup

The release pull request, the tag and the release are created with a GitHub App token, so that they can trigger other workflows such as CI (events created with the default `GITHUB_TOKEN` cannot).

1. Install the existing releases GitHub App on `kijart/ha-cloudflare-workers-ai`. For a new app (Settings → Developer settings → GitHub Apps), disable webhooks and grant these repository permissions:
   - Contents: read and write
   - Pull requests: read and write
2. Note the app's **Client ID** and a private key.
3. In the repository settings (Secrets and variables → Actions), add:
   - variable `RELEASE_APP_CLIENT_ID`: the app's Client ID
   - secret `RELEASE_APP_PRIVATE_KEY`: the contents of the `.pem` private key

Actions are pinned to commit SHAs; Dependabot opens a weekly pull request to update them.

## HACS validation

The HACS job ignores the `brands` check, because the integration is not in [home-assistant/brands](https://github.com/home-assistant/brands): its icons ship in `custom_components/cloudflare_workers_ai/brand/` instead (supported since Home Assistant 2026.3; source in `docs/brand/icon.svg`). Remove `ignore: brands` from `.github/workflows/ci.yml` if HACS starts accepting local brand images, or if the icons are also submitted to that repository.

The same job checks the repository settings: the GitHub repository needs a description and topics (for example `home-assistant`, `hacs`, `cloudflare`, `stt`, `tts`), or the check fails.

## Version fields

The released version lives in `custom_components/cloudflare_workers_ai/manifest.json`, the file HACS and Home Assistant read, and release-please keeps it up to date. The `version` in `pyproject.toml` is a fixed `0.0.0` placeholder: the project is a virtual uv project (`package = false`) that only holds the development environment, so its version is never published, and keeping it in step would also require rewriting `uv.lock` in every release pull request.
