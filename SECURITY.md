# Security policy

Cloudflare Workers AI for Home Assistant sends voice commands and the text to be spoken to Cloudflare Workers AI, and nowhere else. It has no runtime dependencies beyond Home Assistant, keeps the API token out of logs and diagnostics, and works with a token that can only read Workers AI. Reports that help keep it that way are very welcome.

## Supported versions

Only the latest release (the newest `x.y.z` tag on [GitHub Releases](https://github.com/kijart/ha-cloudflare-workers-ai/releases)) gets security fixes, whether it is installed through HACS or copied by hand.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub: open the **Security** tab of this repository and choose **Report a vulnerability**. Do not open a public issue or pull request for a security problem.

A useful report includes:

- what an attacker can achieve and under which conditions;
- steps to reproduce it, with the integration version, the Home Assistant version and how the integration was installed (HACS or manual).

Logs and diagnostics attached to a report must not contain a real token or Account ID.

## What to expect

This is a personal project maintained in spare time, so replies are best effort: an acknowledgement usually within a week, then updates in the private advisory until the issue is fixed or ruled out. Once a fix is released, the advisory is published, crediting the reporter if they wish.

## Scope

In scope:

- the API token, the AI Gateway token or the Account ID appearing in logs, diagnostics or error messages;
- the integration sending data anywhere other than `api.cloudflare.com` or `gateway.ai.cloudflare.com`, or sending it without HTTPS;
- a runtime dependency appearing: the manifest declares `"requirements": []`;
- the release pipeline and what it publishes: the GitHub workflows and the release tags.

Out of scope:

- the handling of the data by Cloudflare, which is subject to the Cloudflare terms (see the README's [Privacy](README.md#privacy) section);
- Home Assistant storing the credentials of integrations in plain text under `.storage`, which is how Home Assistant works and is documented;
- attacks that need a compromised Home Assistant host or an administrator account;
- vulnerabilities in Home Assistant itself: please report them to the [Home Assistant project](https://www.home-assistant.io/security/);
- missing hardening with no practical impact.
