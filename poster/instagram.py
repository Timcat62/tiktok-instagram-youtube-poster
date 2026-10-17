"""Instagram Reels publishing via the Graph API (Facebook Login, direct upload of the local file)."""
import time
from urllib.parse import urlencode

import requests

from . import store

API_VERSION = "v25.0"
GRAPH = f"https://graph.facebook.com/{API_VERSION}"
RUPLOAD = f"https://rupload.facebook.com/ig-api-upload/{API_VERSION}"
SCOPES = ",".join([
    "instagram_basic",
    "instagram_content_publish",
    "pages_show_list",
    "pages_read_engagement",
    "business_management",
])
REDIRECT_URI = f"{store.BASE_URL}/auth/instagram/callback"


def _check(r: requests.Response) -> dict:
    try:
        data = r.json()
    except ValueError:
        r.raise_for_status()
        raise RuntimeError(f"Unexpected response from Instagram: {r.text[:300]}")
    if isinstance(data, dict) and "error" in data:
        err = data["error"]
        msg = err.get("error_user_msg") or err.get("message") or str(err)
        raise RuntimeError(f"Instagram: {msg}")
    r.raise_for_status()
    return data


def set_app(app_id: str, app_secret: str, config_id: str = "") -> None:
    store.update("instagram", app_id=app_id.strip(), app_secret=app_secret.strip(), config_id=config_id.strip())


def auth_url(state: str) -> str:
    acc = store.load("instagram")
    if not acc.get("app_id"):
        raise ValueError("Enter your Meta app's App ID and App Secret first.")
    params = {
        "client_id": acc["app_id"],
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "response_type": "code",
    }
    # "Facebook Login for Business" apps can use a configuration ID instead of a scope list.
    if acc.get("config_id"):
        params["config_id"] = acc["config_id"]
    else:
        params["scope"] = SCOPES
    return f"https://www.facebook.com/{API_VERSION}/dialog/oauth?" + urlencode(params)


def _long_lived(token: str) -> tuple[str, int | None]:
    acc = store.load("instagram")
    if not (acc.get("app_id") and acc.get("app_secret")):
        return token, None
    data = _check(requests.get(f"{GRAPH}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": acc["app_id"],
        "client_secret": acc["app_secret"],
        "fb_exchange_token": token,
    }, timeout=30))
    return data["access_token"], data.get("expires_in")


def _discover(token: str) -> list[dict]:
    data = _check(requests.get(f"{GRAPH}/me/accounts", params={
        "fields": "name,instagram_business_account{id,username}",
        "limit": 100,
        "access_token": token,
    }, timeout=30))
    accounts = []
    for page in data.get("data", []):
        ig = page.get("instagram_business_account")
        if ig:
            accounts.append({"id": ig["id"], "username": ig.get("username", ""), "page": page.get("name", "")})
    return accounts


def connect_with_token(token: str) -> None:
    token, expires_in = _long_lived(token.strip())
    accounts = _discover(token)
    if not accounts:
        raise RuntimeError(
            "No professional Instagram account found. Make sure your Instagram account is "
            "Professional (Creator or Business), linked to a Facebook Page, and that you "
            "selected that Page during login."
        )
    store.update(
        "instagram",
        token=token,
        expires_at=int(time.time()) + expires_in if expires_in else None,
        accounts=accounts,
        account=accounts[0],
    )


def handle_callback(code: str) -> None:
    acc = store.load("instagram")
    data = _check(requests.get(f"{GRAPH}/oauth/access_token", params={
        "client_id": acc["app_id"],
        "client_secret": acc["app_secret"],
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }, timeout=30))
    connect_with_token(data["access_token"])


def select_account(ig_id: str) -> None:
    acc = store.load("instagram")
    for a in acc.get("accounts", []):
        if a["id"] == ig_id:
            store.update("instagram", account=a)
            return
    raise ValueError("Account not found.")


def status() -> dict:
    acc = store.load("instagram")
    exp = acc.get("expires_at")
    return {
        "configured": bool(acc.get("app_id") and acc.get("app_secret")),
        "app_id": acc.get("app_id", ""),
        "config_id": acc.get("config_id", ""),
        "connected": bool(acc.get("token") and acc.get("account")) and not (exp and exp < time.time()),
        "expired": bool(exp and exp < time.time()),
        "expires_at": exp,
        "account": (acc.get("account") or {}).get("username"),
        "account_id": (acc.get("account") or {}).get("id"),
        "accounts": acc.get("accounts", []),
    }


class _ProgressFile:
    """File read in blocks that reports upload progress."""

    def __init__(self, path, on_progress):
        self._f = open(path, "rb")
        self._size = path.stat().st_size
        self._sent = 0
        self._cb = on_progress

    def __len__(self):
        return self._size

    def read(self, n=-1):
        chunk = self._f.read(n)
        self._sent += len(chunk)
        self._cb(self._sent / self._size if self._size else 1.0)
        return chunk

    def close(self):
        self._f.close()


def _container_status(cid: str, token: str) -> tuple[str | None, str | None]:
    st = _check(requests.get(f"{GRAPH}/{cid}", params={
        "fields": "status_code,status", "access_token": token}, timeout=30))
    return st.get("status_code"), st.get("status")


def publish(path, *, caption, thumb_offset_ms, report) -> dict:
    acc = store.load("instagram")
    token, ig = acc.get("token"), (acc.get("account") or {}).get("id")
    if not (token and ig):
        raise RuntimeError("Instagram is not connected.")

    report("Creating Reel…", 0.0)
    container = _check(requests.post(f"{GRAPH}/{ig}/media", data={
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "thumb_offset": int(thumb_offset_ms),
        "access_token": token,
    }, timeout=60))
    cid = container["id"]

    upload_error = None
    for attempt in range(3):
        body = _ProgressFile(path, lambda p: report("Uploading video…", p * 0.9))
        try:
            r = requests.post(f"{RUPLOAD}/{cid}", headers={
                "Authorization": f"OAuth {token}",
                "offset": "0",
                "file_size": str(len(body)),
            }, data=body, timeout=(30, 3600))
        finally:
            body.close()
        if r.ok:
            upload_error = None
            break
        upload_error = f"HTTP {r.status_code}: {r.text[:400]}"
        # rupload sometimes answers 500 although it received the file and processing has started:
        # only re-send when Instagram says the error is retriable and nothing is being processed.
        if '"retriable":true' not in r.text.replace(" ", "") or _container_status(cid, token)[0] == "IN_PROGRESS":
            break
        report(f"Upload failed, retrying ({attempt + 1}/3)…", 0.0)
        time.sleep(5)

    report("Instagram is processing…", 0.92)
    deadline = time.time() + 20 * 60
    while True:
        code, status = _container_status(cid, token)
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED") or (upload_error and code not in ("IN_PROGRESS", "PUBLISHED")):
            msg = f"Instagram rejected the video: {status or code}"
            if upload_error:
                msg += f" (upload response: {upload_error})"
            raise RuntimeError(msg)
        if time.time() > deadline:
            raise RuntimeError("Instagram is taking too long to process the video (over 20 min).")
        time.sleep(5)

    report("Publishing…", 0.97)
    media = _check(requests.post(f"{GRAPH}/{ig}/media_publish", data={
        "creation_id": cid, "access_token": token}, timeout=60))
    url = None
    try:
        url = _check(requests.get(f"{GRAPH}/{media['id']}", params={
            "fields": "permalink", "access_token": token}, timeout=30)).get("permalink")
    except Exception:  # noqa: BLE001 - the link is a bonus, publishing succeeded
        pass
    return {"url": url or f"https://www.instagram.com/{acc['account'].get('username', '')}/", "warning": None}
