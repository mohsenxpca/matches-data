"""Blogger API call() for the price pages on GitHub Actions (stands in for outage/make_pages.py + blogger_api.py on Mohsen's PC).
Logs in with the BLOGGER_* secrets; backs off on 429 like the original."""
import json, os, time, urllib.error, urllib.parse, urllib.request

API = "https://www.googleapis.com/blogger/v3"
_tok = {}


def _sec(n):
    return os.environ.get(n, "").strip().strip('"')


def _access():
    if _tok.get("exp", 0) > time.time():
        return _tok["t"]
    body = urllib.parse.urlencode({"client_id": _sec("BLOGGER_CLIENT_ID"), "client_secret": _sec("BLOGGER_CLIENT_SECRET"),
                                   "refresh_token": _sec("BLOGGER_REFRESH_TOKEN"), "grant_type": "refresh_token"}).encode()
    r = json.loads(urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body), timeout=30).read())
    _tok.update(t=r["access_token"], exp=time.time() + r.get("expires_in", 3600) - 60)
    return _tok["t"]


def _call(method, path, params=None, body=None):
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": "Bearer " + _access(), "Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Blogger API {e.code}: {e.read().decode()[:300]}") from None


def call(*a):
    for wait in (0, 30, 60, 120, 240):
        time.sleep(wait)
        try:
            return _call(*a)
        except RuntimeError as e:
            if "429" not in str(e):
                raise
            print("rate limited, waiting", wait * 2 or 30)
    raise RuntimeError("still rate limited")
