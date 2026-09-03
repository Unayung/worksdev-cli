# worksdev

Drive the **LINE WORKS Developer Console** (`dev.worksmobile.com`) from the
shell — read the registered OAuth apps and bots (client IDs, secrets, service
accounts, token settings), and register new ones.

Zero dependencies. Python 3.8+. Single file.

> **Unofficial.** Not affiliated with LINE WORKS / NAVER WORKS / Works Mobile.
> This drives the console's own private endpoints with your browser session
> cookie. They are undocumented and can change without notice. `create`
> registers real apps and bots in a real tenant — every write needs `--yes`.
> Use on your own account only and check your org's IT policy.

## Why this exists

The console is the *only* place app registrations live. The official LINE WORKS
API cannot list your apps, read a `clientSecret`, or register a new one — those
are console-only. So a CLI has to go through the console's own session.

Sibling to [`lineworks`](../lineworks-cli) (messaging, `talk.worksmobile.com`).
Same auth model, different host.

## Auth

The console login is NAVER SSO — RSA-encrypted password, a Fingerprint2 device
fingerprint and possibly 2-step verification. Scripting that is fragile and
risks locking a corporate account, so **this replays a browser session instead**
(the same call the console page makes).

Log in at `dev.worksmobile.com`, open DevTools → Network, click any
`/console/...` XHR and copy its whole `Cookie` request header (the session
cookies are `HttpOnly`, so `document.cookie` will not show them):

```bash
mkdir -p ~/.config/worksdev
umask 077
pbpaste > ~/.config/worksdev/cookie      # or paste with your editor
chmod 600 ~/.config/worksdev/cookie

worksdev doctor        # session ok · domain 4xxxxxxxx · 7 apps
```

`WORKSDEV_COOKIE` overrides the file. If `~/.config/worksdev/cookie` is absent
the `~/.config/lineworks/cookie` one is tried — both hosts sit under
`*.worksmobile.com`, so one SSO session often covers both.

The cookie is never printed. Exit `3` means the session expired — log in again
and refresh the file. A dead session does **not** 401; it redirects to the SSO
login page and returns `200 text/html`, which the CLI detects and reports as an
auth failure rather than "no apps".

## Tenant ids

Both consoles address your tenant by an id, and the two are **different and
unrelated** — the developer console uses a numeric `manageDomainId`, the admin
console an `E`-prefixed one embedded in its API path. Both belong to whoever
the cookie belongs to, so nothing is baked into the source.

```bash
worksdev config                       # show what is set
worksdev config --admin-tenant E123456
worksdev config --detect              # re-detect the dev console id
```

The **dev console id is detected automatically** on first use (the console
renders it into every page as a hidden `manageDomainId` input) and cached in
`~/.config/worksdev/config.json`.

The **admin id cannot be detected** — its gateway rejects any path that does
not already carry it, so there is no unprefixed endpoint to ask. Read it once
from any `/api/<THIS>/...` request in the admin console's DevTools Network tab
and set it with `config --admin-tenant`. Only the `admin` commands need it.

`WORKSDEV_DOMAIN` / `WORKSDEV_ADMIN_TENANT` override the config file, and
`--domain` / `--admin-tenant` override both.

## Commands

```bash
worksdev doctor                    # verify the session, count apps

worksdev app list                  # name · type · clientId · last modified
worksdev app list --reveal         # include client secrets

worksdev app show nike             # match by clientId, appId, or unique name
worksdev app show Uhrpj9zNnQppcyCqKZ0X
worksdev app show "Racco Bot" --reveal    # + clientSecret and publicKey

worksdev bot list                  # name · botNo

worksdev raw /console/gnb/get      # GET any console path
worksdev raw /console/bot/list --html      # for paths that serve HTML
```

### Onboarding a bot end to end

One command does app → scopes → service account → RSA key → bot → enable, and
prints the openclaw config block:

```bash
worksdev onboard "My Bot" --description "what it does" \
    --account mybot --group --key-out ~/.openclaw/keys/mybot.pem --yes
```

The app and the bot are separate objects and can have separate names — this
tenant pairs an app called `Racco-Nike App` with a bot called `學妹`. The
positional argument names the **app**; `--bot-name` names the **bot** (default:
the same), and `--account` is the key under `channels.lineworks.accounts`:

```bash
worksdev onboard "Racco-Helper App" --bot-name "測試助手" --account helper \
    --description "..." --yes
```

```
  app created: YVAfWDF0CpfaYt8W7aHuTA
  scopes granted: bot, bot.read
  service account: xxxxx.serviceaccount@example.com
  private key: mybot.pem (1704 bytes)
  bot created: 13076092
  bot secret read
  enabled in admin (status=2)
```

Each step prints as it lands; on failure it stops and lists what already
exists, so you finish with the discrete commands rather than re-running blind.
`--dry-run` prints the plan without touching anything.

The discrete equivalents, in order:

```bash
worksdev app create "My Bot" --yes
worksdev app grant "My Bot" --scopes bot,bot.read --yes
worksdev app service-account "My Bot" --yes
worksdev app rsakey "My Bot" --out mybot.pem --yes     # mints a NEW key
worksdev bot create "My Bot" --description "..." --group --yes
worksdev bot show <botNo> --reveal                     # the bot secret
worksdev admin bot enable <botNo> --yes                # register + switch on
```

### Admin console (tenant registry)

```bash
worksdev admin bot pending             # created but not yet in the tenant
worksdev admin bot list                # enrolled bots + status
worksdev admin bot enable <botNo> --yes
worksdev admin bot enable <botNo> --register-only --yes   # add, leave off
worksdev admin bot status <botNo> --status 1 --yes        # switch off
worksdev admin bot remove <botNo> --yes                   # back to pending
```

### Avatars

`--photo` takes either an `https://` URL (used as-is — the console accepts
external hosts) or a **local image file**, which is uploaded first:

```bash
worksdev bot create "My Bot" --description "..." --photo ./avatar.png --yes
worksdev onboard  "My Bot" --description "..." --photo ./avatar.png --yes
```

For a house avatar every bot should get, put it at
**`~/.config/worksdev/default-avatar.png`** (or point `WORKSDEV_DEFAULT_PHOTO`
at a file or URL) and omit `--photo`. The order is: `--photo` →
`WORKSDEV_DEFAULT_PHOTO` → `~/.config/worksdev/default-avatar.png` → the
console's grey placeholder.

`.png .jpg .jpeg .gif .webp` are accepted; anything else is refused before a
request is made. `--dry-run` never uploads — it prints `<would upload …>`.

### Changing an app after the fact

```bash
worksdev app set <app> --name "新名字" --dry-run
worksdev app set <app> --scopes bot,bot.read,user.read --yes
worksdev app set <app> --redirect-urls https://a/cb,https://b/cb --yes
worksdev app set <app> --ttl 86400 --rotation Y --yes
```

Also a read-modify-write: a partial `PATCH` is rejected with
`400 INVALID_PARAMETER`, so the full object goes every time. `--scopes` here
and `app grant` reach the same setting by different endpoints — `app grant` is
the narrower one and is what `onboard` uses.

### Changing a bot after the fact

```bash
worksdev bot set <botNo> --name "新名字" --dry-run     # shows a before/after diff
worksdev bot set <botNo> --photo ./avatar.png --yes
worksdev bot set <botNo> --callback-url https://host/lineworks/x/webhook \
    --events message,join --message-types text,image --yes
worksdev bot set <botNo> --callback-url "" --yes      # callbacks off
worksdev bot set <botNo> --no-group --yes
worksdev bot set <botNo> --manager 110002xxxxxxxxx --yes

worksdev bot secret-reissue <botNo> --yes             # new secret, old one dies
```

`bot set` is a **read-modify-write**: the console's modify endpoint takes the
whole bot object, so sending a partial payload would blank every field you
left out. It reads the current state first, applies only your flags, and
prints the diff. Flags you don't pass are carried over untouched — verified by
renaming a bot and confirming its callback URL, both event lists, group flag
and managers all survived.

**Two different removals.** `admin bot remove` un-enrols a bot from the tenant
— it drops back into `admin bot pending` and still exists. To destroy the bot
itself use the dev console:

```bash
worksdev bot delete <botNo> --yes      # GET /console/bot/remove/{botNo}
```

### Creating things

Both creates are writes against a live tenant, so they are opt-in twice:
`--dry-run` prints the exact request and sends nothing, and without `--yes`
nothing is sent at all.

```bash
# OAuth app - the name is validated first, the same way the console does it
worksdev app create "My App" --dry-run
worksdev app create "My App" --yes
worksdev app create "My App" --type scim --yes        # or --type delegated
worksdev app show "My App" --reveal                   # then read the secret

# bot - name, description and a manager are mandatory
worksdev bot create "My Bot" --description "what it does" --yes

# a bot that receives events needs a callback URL; without one it is send-only
worksdev bot create "My Bot" --description "..." \
    --callback-url https://example.com/hook \
    --events message,join --message-types text,image \
    --group --yes
```

`--manager <userNo>` sets the bot's owner; it defaults to **you**, resolved
from the console header. `--type delegated` is super-admin only.

`--json` on any command for the envelope
(`{"ok":true,"data":...}` / `{"ok":false,"error":{...}}`).
Exit codes: `0` ok · `1` error · `2` usage · `3` auth · `4` network.

`--domain` (or `WORKSDEV_DOMAIN`) selects the tenant, defaulting to the one
this was built against; it is the `manageDomainId` in the console URLs, and
also each app's `domainId`.

## Notes (reverse-engineered)

- The app-list page is a thin shell: `appListView.js` → `getClientAppList()` →
  `GET /console/openapi/v2/app/list?manageDomainId=…&count=100&cursor=1`, with
  `X-Requested-With: XMLHttpRequest`. That one call is the whole tool.
- Response is `{"response":{"appList":[…]},"responseMetaData":{…}}`. Each app
  carries `appId`, `appName`, `clientId`, `clientSecret`, the service account
  (`accountId` / `accountEmail` / `accountUserNo`), `publicKey`,
  `accessTokenTtl`, `refreshTokenRotationYn`, `scimUseYn` and `clientAppType`
  (`NORMAL` / `OIDC`).
- **`clientSecret` is returned in plaintext by the list endpoint** — every app's,
  in one response. Output masks it unless `--reveal`, so a casual `app list`
  cannot dump your secrets into scrollback, a log or a shared terminal.
- **`app show` needs no detail endpoint** — the list already carries every
  field, so it filters client-side. A name that matches two apps is refused
  rather than guessed.
- Pagination (`count`/`cursor`) is exposed but not auto-walked; the response
  carries no cursor and this tenant has 7 apps. Revisit if a tenant exceeds
  `--count`.
- **Writes carry no CSRF token.** The console's own `ajaxWithManageDomainId`
  only appends `?manageDomainId=`; the session cookie alone authorises a
  create. That is their design, not an omission here.
- **App create is three endpoints, one per kind** — `POST /console/openapi/v2/`
  `app` (normal), `scim-app`, or `auth-delegated-app` — all with
  `{"appName": …}`, all returning the new `appId`. The console validates the
  name first via `POST …/app/appname/validate`, which 4xxs on a duplicate;
  `app create` does the same, so a clash fails before anything is created.
- **The bot console is older and speaks a different dialect.** It ignores
  `manageDomainId`, `POST /console/bot/register` answers `{"code":"00"}` for
  success and `"11"` for "tenant bot limit reached", and `/console/bot/list`
  returns an **HTML fragment**, not JSON — so `bot list` parses rows out of the
  markup, and the "HTML means logged out" rule is scoped to JSON endpoints.
- **Bot managers are user numbers**, and nothing in the console states your own
  outright — it is scraped from the profile-photo URL in `/console/gnb/get`.
- Bot `name`/`description`/`photoUrl` are per-language maps (`default`, `en`,
  `ja`, `ko`, `zh-CN`, `zh-TW`); the CLI writes `default` only.
  `interfaceType` is hardcoded to `1` (bot API 2.0), matching the console.
- A response of `{"code":"logout"}` or `{"isROS":"Y"}` is the console's own
  session/read-only-mode signal; both are caught rather than parsed as data.

### Provisioning (learned by doing it)

- **Two hosts, two tenant ids, one cookie.** The dev console is
  `dev.worksmobile.com` with a numeric `?manageDomainId=`; the admin console
  is `admin.worksmobile.com` with an `E`-prefixed id **in the path**. Neither is
  derivable from the other. The same session cookie authenticates both.
  Admin bot calls also need `X-WORKS-ADMIN-VERSION: 2`.
- **`POST /console/bot/register` fails with a bare `{"code":"21"}` if you omit
  either `allowDomainIdList` or a real `photoUrl`.** `[0]` means all domains;
  an empty `photoUrl` map is rejected, so the console's placeholder image is
  sent when none is given. The error names neither field.
- **Enabling a bot is TWO admin calls.** `registerBot {botNo}` only enrols it,
  at `status: 1` (off) — verified against six existing bots all sitting at
  `status: 2`. `updateBotStatus {botNo, status: 2, allowUserNoList}` is what
  actually switches it on; `allowUserNoList: [0]` is the console's "everyone".
  `admin bot enable` does both unless you pass `--register-only`.
- **`removeBot` un-enrols, it does not delete.** The bot returns to the
  `admin bot pending` pool and still exists in the dev console's bot list.
  Destroying it is the dev console's own **`GET /console/bot/remove/{botNo}`**
  — a GET that mutates, with no body and no `manageDomainId`. It is reached
  from the bot's *modify* page, so deleting a bot navigates away and DevTools
  drops the request unless "Preserve log" is on.
- **A bot secret contains `+`.** It is scraped from the bot info page; matching
  it with an alphabet guess truncates it silently at the first `+`, producing a
  config that looks fine and fails to authenticate. The regex anchors on the
  closing tag instead, and there is a test for it.
- **The `rsakey/download` endpoint mints a new key on every call** — two calls
  return two different PEMs, and the app's `publicKey` follows the latest. So
  `app rsakey` refuses an app that already has a key unless `--rotate` is
  passed. Never point it at an app something is running on.
- The app kind decides the delete path: `app`, `scim-app` or
  `auth-delegated-app`; `app delete` picks it from `clientAppType`.
- **`PATCH /console/openapi/v2/app/{appId}` is not a patch.** Sending only
  `{"appName": …}` answers `400 INVALID_PARAMETER` — all ten fields are
  required (`appName`, `appDescription`, `redirectUrlList`, `apiScopeList`,
  `accessType`, `logoutRedirectUrlList`, `accessTokenTtl`,
  `refreshTokenRotationYn`, `userAccessType`, `accessUserIdNoList`). Rejecting
  loudly is kinder than the bot endpoint, which accepts a short payload and
  quietly blanks the rest.
- **`apiScopeList` has two shapes.** The PATCH wants objects
  (`[{"scope": "bot"}]`); the dedicated `PUT …/api-scope` wants bare strings
  (`["bot"]`). Same setting, same console, two encodings.
- Reading an app back needs three sources: the list API (name, description,
  `accessTokenTtl`, `refreshTokenRotationYn`), the **edit form**
  (`redirectUrlList`, `apiScopeList`, `accessType` — its radios are
  server-rendered with `checked`, unlike the bot form's), and
  `…/app-users` (`userAccessType`, `accessUserIdNoList`).
- **`POST /console/bot/modify` shares its payload builder with `register`** —
  it is a whole-object write, not a patch. Renaming a bot by posting
  `{botNo, name}` would silently clear its callback URL, event lists, managers
  and group flag; the bot keeps running and just stops receiving anything.
- **The current state has to be read from two places.** The modify form
  (`GET /console/bot/modify/view/{botNo}`) is authoritative for the i18n maps,
  callback URL and the event checkboxes, but it does **not** contain the
  managers — the console fills those in by XHR after load. Those come from the
  admin console's `getBotInfo`. If the manager read fails, `bot set` refuses to
  write rather than submit a payload that would orphan the bot.
  That form 500s for a deleted bot, which is a useful liveness check.
- An i18n map only carries the languages whose form row has class `on`, so a
  bot with just a default name round-trips as `{"default": …}` and not as six
  keys, five of them empty.
- **`GET /console/bot/modify-secret/{botNo}`** re-issues the bot secret — again
  a GET that mutates, and the old secret stops working immediately.
- **Avatar upload** is `POST /console/bot/img/upload`, multipart, field name
  `imageFile`, answering `{"photoUrl": …}` — a
  `/gateway/image/view?path=…/bot_profile/…` URL you then put in the bot's
  `photoUrl` map. Verified byte-identical on the way back out. `photoUrl` also
  accepts a plain external URL, which is how one live bot points at
  `cdn.phototourl.com`.
