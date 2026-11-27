# API token

The integration needs the Cloudflare **Account ID** and an **account API token** dedicated to it. This guide creates a token with the minimal permission, optionally restricted by IP address and with an expiry date, and explains how to rotate it.

## Minimal permission

**`Workers AI - Read` is enough.** The Cloudflare documentation lists `Workers AI - Read` and `Workers AI - Edit` for Workers AI tokens, but `Edit` is not needed by this integration. Verified on 2026-11-27 with an account token that has only `Workers AI - Read`:

| Request                                                  | Used for                 | Result |
| -------------------------------------------------------- | ------------------------ | ------ |
| `GET /accounts/{account_id}/tokens/verify`               | Token verification       | OK     |
| `GET /accounts/{account_id}/ai/models/search`            | Model discovery          | OK     |
| `GET /accounts/{account_id}/ai/models/schema`            | Voice discovery          | OK     |
| `POST /accounts/{account_id}/ai/run/@cf/deepgram/aura-2-es` | Text-to-speech        | OK     |
| `POST /accounts/{account_id}/ai/run/@cf/openai/whisper-large-v3-turbo` | Speech-to-text | OK |

The same result was obtained with `scripts/live_check.py` (see [CONTRIBUTING.md](../CONTRIBUTING.md#live-check)), which runs all of these requests: the phrase "Enciende la luz del salón" was synthesized with Aura and transcribed back by Whisper, both with the regular token of the author and with a token with only `Workers AI - Read`.

## Creating the token

1. In the Cloudflare dashboard, copy the **Account ID** from the account home page (or from **Workers AI**).
2. Go to **Manage account → Account API tokens** and choose **Create token → Custom token**.
3. Set:
   - **Token name:** for example `home-assistant-workers-ai`.
   - **Permissions:** `Account` · `Workers AI` · `Read`.
   - **Account resources:** include only the account used by Home Assistant.
   - **Client IP Address Filtering** and **TTL:** optional, see below.
4. Create the token and copy it; Cloudflare shows it only once.
5. Enter the Account ID and the token in the integration.

The integration verifies the token with `GET /accounts/{account_id}/tokens/verify`, the endpoint for **account** API tokens, so an account token is the supported type. A wrong token is reported as "The API token is invalid or lacks the required permissions", and a network problem as "Unable to connect to Cloudflare".

## Restricting by IP address (optional)

Under **Client IP Address Filtering**, the operator **Is in** with the public IP address of the home limits the token to requests from it. A leaked token is then useless elsewhere.

> [!WARNING]
> Most home connections have a **dynamic** public IP. When it changes, Cloudflare rejects the token and Home Assistant asks for reauthentication. Update the filter in Cloudflare and reload the entry. If Home Assistant reaches Cloudflare over IPv6, the filter must include the IPv6 address or prefix too.

## Expiry (optional)

A **TTL** end date makes the token expire on its own. When it expires, Cloudflare rejects it, the speech-to-text and text-to-speech requests fail and Home Assistant shows **Reauthentication required** for the entry. A new token is then entered as described below.

## Rotation

1. Create a new token with the same settings.
2. Enter it in Home Assistant:
   - **Reconfigure:** **Settings → Devices & services → Cloudflare Workers AI**, menu (⋮) of the entry → **Reconfigure**. The AI Gateway settings can be changed in the same step.
   - **Reauthentication:** when the old token has already been rejected, the integration starts a reauthentication flow that asks only for the new token.
3. Delete the old token in Cloudflare.

Both flows verify the new token against the configured Account ID before saving it. The Account ID cannot change: **Reconfigure** refuses a different one, and using another account means adding another entry.

## AI Gateway token (optional)

An **authenticated** AI Gateway needs its own token, created in the gateway settings, which the integration sends in the `cf-aig-authorization` header of the model requests only. The API token above is still needed: requests through the gateway use both.
