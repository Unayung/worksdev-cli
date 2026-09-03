---
name: worksdev
description: Provision and manage LINE WORKS bots and OAuth apps from the CLI - create an app, grant scopes, mint a service-account key, create a bot, enable it in the admin console, and read back every credential an integration needs. Use when the user wants to onboard a new LINE WORKS bot, read or rotate app/bot credentials, or change an existing bot's webhook, avatar, events or managers.
---

# worksdev

Zero-dependency Python CLI driving the **LINE WORKS Developer Console**
(`dev.worksmobile.com`) and **Admin Console** (`admin.worksmobile.com`).

**Binary:** `worksdev` if on PATH, else `~/Projects/worksdev-cli/worksdev`.
Companion `worksdev-login` turns an id + password into a session (needs
playwright); the main CLI stays zero-dependency and only replays a cookie.

**Always pass `--json`** when parsing. Envelope:
`{"ok":true,"data":...}` / `{"ok":false,"error":{"message":...,"code":N}}`.
Exit: `0` ok · `1` error · `2` usage · `3` auth · `4` network. On `3` the
session cookie is stale — tell the user to refresh it; do not retry.

## Why this exists

LINE WORKS has **no public API for provisioning**. OAuth apps, client secrets,
service accounts, RSA keys and bots exist only inside the web consoles. This
replays a browser session against the consoles' own private endpoints.

## Onboarding a bot from zero

Do these **in order**. Steps 1–2 are once per machine; skipping step 2 makes
step 3 refuse to start.

**1. Session.** Check first — do not assume it is set up:

```bash
worksdev doctor        # "session ok · domain … · N apps"
```

Exit `3` or "no session cookie" means there is no valid session (must be a
**tenant admin**). Two ways to create one:

- **id + password** — `worksdev-login --save` (needs playwright; prompts for
  the password or reads `WORKSDEV_ID`/`WORKSDEV_PASSWORD`). This is the path
  for a self-service/web flow, and it also captures **both** tenant ids so it
  covers step 2. As a library: `wl.login(id, pw)` → `{cookie, domain,
  adminTenant}`; hand `cookie` to worksdev via `WORKSDEV_COOKIE`. Never pass
  the password as a CLI argument (shell history, `ps`).
- **paste a cookie** — user logs in at `dev.worksmobile.com`, copies the whole
  `Cookie` header from any `/console/...` XHR in DevTools, saves it to
  `~/.config/worksdev/cookie` (mode 600). Cookies are `HttpOnly`; you cannot
  read them for the user.

`doctor` auto-detects and caches the developer console tenant id either way.

**2. Admin tenant id.** Required by the final onboarding step; auto-captured by
`worksdev-login` but *not* detectable from a pasted cookie:

```bash
worksdev config        # does it list adminTenant?
```

If missing, ask the user to open `admin.worksmobile.com` → DevTools → Network
and read the id from any `/api/<THIS>/...` request, then
`worksdev config --admin-tenant <id>`. `onboard` checks this up front and
aborts before creating anything, so a missing id cannot strand a half-built
app and bot.

**3. Onboard.** Dry-run, show the user the plan, then commit:

```bash
worksdev onboard "<App Name>" --description "<what it does>" \
    --bot-name "<Bot Name>" --account <key> \
    --callback-url https://host/lineworks/<key>/webhook \
    --group --photo ./avatar.png \
    --key-out ~/.openclaw/keys/<key>.pem --dry-run   # then --yes
```

Runs: create app → grant `bot,bot.read` → create service account → mint RSA
key → create bot → enable in admin. Prints the openclaw `channels.lineworks`
and `accounts.<key>` blocks.

**4. Verify.** The last line must read `enabled in admin (status=2)`.
Confirm with `worksdev admin bot list` — the bot is there with `status=2` and
absent from `worksdev admin bot pending`. **`status=2` is what makes the bot
addable by people**; `status=1` means enrolled but switched off, fixed with
`worksdev admin bot enable <botNo> --yes`.

**5. Wire it up.** Paste the printed blocks into the consuming config (for
openclaw, `~/.openclaw/openclaw.json`) and restart its gateway.

Being *addable* needs only step 3. **Replying** also needs the callback URL to
be publicly reachable with the agent running behind it — if a bot can be added
but never answers, suspect the webhook, not the credentials.

If `onboard` fails midway it prints what already exists; finish with the
discrete commands below rather than re-running, since the app name is now
taken.

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
