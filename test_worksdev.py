"""Checks for the bits that fail silently: logged-out detection (an expired
session returns 200 HTML, not 401), secret masking, and app matching."""
import importlib.util
import pathlib
from importlib.machinery import SourceFileLoader

# the CLI has no .py extension, so the loader has to be named explicitly
path = pathlib.Path(__file__).parent / "worksdev"
spec = importlib.util.spec_from_file_location(
    "worksdev", path, loader=SourceFileLoader("worksdev", str(path)))
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

# an expired session 302s to SSO and returns 200 text/html - the failure mode
# that would otherwise parse as "no apps" instead of "log in again"
assert w.looks_logged_out("https://auth.worksmobile.com/login/...", "text/html")
assert w.looks_logged_out("https://dev.worksmobile.com/console/x", "text/html")
assert w.looks_logged_out("https://dev.worksmobile.com/login", "application/json")
assert not w.looks_logged_out(
    "https://dev.worksmobile.com/console/openapi/v2/app/list?x=1",
    "application/json")

app = {"appName": "Racco Bot", "clientId": "abc123", "appId": "Z9",
       "clientSecret": "s3cr3t"}
assert w.mask(app, reveal=False)["clientSecret"] == "••••••"
assert w.mask(app, reveal=True)["clientSecret"] == "s3cr3t"
assert app["clientSecret"] == "s3cr3t", "mask must not mutate the original"
assert w.mask({"clientSecret": ""}, reveal=False)["clientSecret"] == ""

apps = [app, {"appName": "Racco-Nike App", "clientId": "d4", "appId": "Y8"}]
assert w.pick(apps, "abc123") is app          # clientId
assert w.pick(apps, "Z9") is app              # appId
assert w.pick(apps, "racco bot") is app       # exact name, case-insensitive
assert w.pick(apps, "nike") is apps[1]        # unique substring
for bad in ("racco", "nope"):                 # ambiguous and missing both refuse
    try:
        w.pick(apps, bad)
        raise AssertionError(f"{bad!r} should not resolve")
    except SystemExit:
        pass

# bot/list serves HTML, so the content-type tell must not fire there
assert not w.looks_logged_out("https://dev.worksmobile.com/console/bot/list",
                              "text/html", expect_json=False)
assert w.looks_logged_out("https://auth.worksmobile.com/login", "text/html",
                          expect_json=False), "a redirect is still a redirect"

# bot rows come out of an HTML fragment; names may be CJK
html = ('<li data-bot_no="12729222"><strong class="bot_name _botName">提米</strong>'
        '</li><li data-bot_no="11520938">'
        '<strong class="bot_name _botName">Raccoon AI Eva</strong></li>')
assert w.parse_bots(html) == [{"botNo": "12729222", "name": "提米"},
                              {"botNo": "11520938", "name": "Raccoon AI Eva"}]
assert w.parse_bots("<div>no bots</div>") == []

assert w.csv_opt("message,join", w.CHANNEL_EVENTS, "event") == ["message", "join"]
assert w.csv_opt("", w.CHANNEL_EVENTS, "event") == []
try:
    w.csv_opt("message,nope", w.CHANNEL_EVENTS, "event")
    raise AssertionError("unknown event should refuse")
except SystemExit:
    pass

# a bot secret contains '+'; an alphabet-guessing regex truncated it silently
info = ('<th colspan="2">Bot Secret</th>\n<td>\n'
        '<span class="msg" id="botSecret"> mxbCHF+uk31rIK59j80DWS6cWK1Swx </span>')
assert w._SECRET_RE.search(info).group(1).strip() == "mxbCHF+uk31rIK59j80DWS6cWK1Swx"

assert w.cells("提米 App") == 8, "2+2 for the CJK pair, not 1+1"
assert w.cells("Racco Bot") == len("Racco Bot")

print("ok")
