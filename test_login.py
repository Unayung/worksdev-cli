"""Offline checks for worksdev-login's pure logic. The login itself needs a
browser and a real account, so it is not covered here; the cookie-jar assembly
and tenant scraping are, since those fail silently and produce a broken config.

Skips cleanly if playwright is absent (the module imports it lazily, so import
still works, but be defensive)."""
import importlib.util
import pathlib
from importlib.machinery import SourceFileLoader

path = pathlib.Path(__file__).parent / "worksdev-login"
spec = importlib.util.spec_from_file_location(
    "worksdev_login", path, loader=SourceFileLoader("worksdev_login", str(path)))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# admin tenant is scraped from /api/<id>/ on the admin host
assert m._tenant_from_url("https://admin.worksmobile.com/api/E999999/botapi/x") == "E999999"
assert m._tenant_from_url("https://admin.worksmobile.com/api/v2/init") is None  # not a tenant
assert m._tenant_from_url("https://dev.worksmobile.com/console/bot/list") is None
assert m._tenant_from_url("/api/ABC123/admin/common/manager/info") == "ABC123"

# only worksmobile cookies, joined as a header; session cookie required
cookies = [
    {"name": "NEO_SES", "value": "abc+def", "domain": ".worksmobile.com"},
    {"name": "WORKS_USER_DOMAIN", "value": "example.com", "domain": ".worksmobile.com"},
    {"name": "_ga", "value": "GA1.1", "domain": ".google.com"},  # dropped
]
jar = m._build_jar(cookies)
assert jar == "NEO_SES=abc+def; WORKS_USER_DOMAIN=example.com", jar
assert "google" not in jar

# a jar with no session cookie is a failure, not a silent empty string
try:
    m._build_jar([{"name": "_ga", "value": "x", "domain": ".worksmobile.com"}])
    raise AssertionError("should reject a jar with no NEO_SES/WORKS_SES")
except m.LoginError:
    pass

print("ok")
