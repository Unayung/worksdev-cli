---
name: worksdev
description: Provision and manage LINE WORKS bots and OAuth apps from the CLI - create an app, grant scopes, mint a service-account key, create a bot, enable it in the admin console, and read back every credential an integration needs. Use when the user wants to onboard a new LINE WORKS bot, read or rotate app/bot credentials, or change an existing bot's webhook, avatar, events or managers.
---

# worksdev

Zero-dependency Python CLI driving the **LINE WORKS Developer Console**
(`dev.worksmobile.com`) and **Admin Console** (`admin.worksmobile.com`).

**Binary:** `worksdev` if on PATH, else `~/Projects/worksdev-cli/worksdev`.

**Always pass `--json`** when parsing. Envelope:
`{"ok":true,"data":...}` / `{"ok":false,"error":{"message":...,"code":N}}`.
Exit: `0` ok · `1` error · `2` usage · `3` auth · `4` network. On `3` the
session cookie is stale — tell the user to refresh it; do not retry.

## Why this exists

LINE WORKS has **no public API for provisioning**. OAuth apps, client secrets,
service accounts, RSA keys and bots exist only inside the web consoles. This
replays a browser session against the consoles' own private endpoints.

## Setup (once per machine)

```bash
worksdev doctor                        # verifies the session; auto-detects the dev tenant
worksdev config --admin-tenant E123456 # only needed for `admin` commands
```

Cookie: `~/.config/worksdev/cookie` (mode 600), or `WORKSDEV_COOKIE`. It falls
back to `~/.config/lineworks/cookie`. Tenant ids live in
`~/.config/worksdev/config.json`; the dev one self-detects, the admin one must
be read from the admin console's DevTools once.

## The whole job in one command

```bash
worksdev onboard "<App Name>" --description "<what it does>" \
    --bot-name "<Bot Name>" --account <openclaw-key> \
    --photo ./avatar.png --group \
    --callback-url https://host/lineworks/<key>/webhook \
    --key-out ~/.openclaw/keys/<key>.pem --yes
```

Runs: create app → grant `bot,bot.read` → create service account → mint RSA
key → create bot → enable in admin. Prints the openclaw
`channels.lineworks` + `accounts.<key>` blocks. **`--dry-run` first.**

On failure it stops and lists what already exists — finish with the discrete
commands below rather than re-running (the app name will now be taken).

## Commands

```bash
worksdev app list|show <app> [--reveal]      # --reveal for clientSecret
worksdev app create <name> [--type normal|scim|delegated] --yes
worksdev app grant <app> --scopes bot,bot.read --yes
worksdev app service-account <app> [--remove] --yes
worksdev app rsakey <app> --out k.pem [--rotate] --yes
worksdev app set <app> [--name|--description|--scopes|--redirect-urls|--ttl|--rotation] --yes
worksdev app delete <app> --yes

worksdev bot list|show <botNo> [--reveal]    # --reveal for botSecret
worksdev bot create <name> --description D [--photo|--group|--callback-url|--events|--message-types] --yes
worksdev bot set <botNo> [--name|--description|--photo|--callback-url|--events|--message-types|--group|--no-group|--manager] --yes
worksdev bot secret-reissue <botNo> --yes
worksdev bot delete <botNo> --yes

worksdev admin bot pending|list
worksdev admin bot enable <botNo> [--register-only] [--allow <userNos>] --yes
worksdev admin bot status <botNo> --status 1|2 --yes
worksdev admin bot remove <botNo> --yes

worksdev raw <path> [--html]                 # escape hatch
```

## Rules

- **Every write needs `--yes`; run `--dry-run` first** and show the user the
  diff or plan before committing. These act on a live corporate tenant.
- **Never run `app rsakey` on an app in use.** Each call mints a NEW key pair
  and invalidates the current one — anything authenticating with the old key
  breaks instantly. The command refuses an app that already has a key unless
  `--rotate` is passed; do not pass it without explicit instruction.
- **`bot secret-reissue` likewise** kills the current secret immediately.
- **Mask secrets by default.** `clientSecret` and `botSecret` print masked
  unless `--reveal`; only reveal when the user needs the value, and never echo
  one into a shared channel or a commit.
- After changing a bot's secret, webhook or an app's key, the consuming config
  (e.g. openclaw's `channels.lineworks`) must be updated too — say so.

## Key facts (reverse-engineered, verified)

- **Two consoles, two tenant ids, one cookie.** They are unrelated ids; the dev
  one self-detects, the admin one cannot. Admin calls carry
  `X-WORKS-ADMIN-VERSION: 2`.
- **Enabling a bot is two steps.** `admin bot enable` does both: `registerBot`
  enrols it at `status: 1` (off), then `updateBotStatus` flips it to `2`.
  A bot that is created but not enabled sits in `admin bot pending`.
- **Two different removals.** `admin bot remove` un-enrols (bot returns to
  pending and still exists); `bot delete` destroys it.
- **`bot set` and `app set` are read-modify-write.** The underlying endpoints
  take the whole object — `bot`'s silently blanks omitted fields, `app`'s
  rejects a partial payload with `400 INVALID_PARAMETER`. Both read current
  state first and carry over what you don't pass; trust the printed diff.
- **`app grant` vs `app set --scopes`** hit the same setting by different
  endpoints (bare strings vs `[{"scope": …}]`). Prefer `app grant`.
- **Avatars**: `--photo` takes an https URL (stored as-is) or a local file
  (uploaded first). A house default can live at
  `~/.config/worksdev/default-avatar.png`.
- **App and bot are separate objects** with separate names; `onboard`'s
  positional argument is the app, `--bot-name` is the bot.
- A new app has **no service account** until one is created — an app alone
  cannot do service-account JWT auth.
