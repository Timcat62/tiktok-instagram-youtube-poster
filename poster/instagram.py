"""Publication de Reels Instagram via l'API Graph (connexion Facebook, envoi direct du fichier local)."""
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
        raise RuntimeError(f"Réponse inattendue d'Instagram : {r.text[:300]}")
    if isinstance(data, dict) and "error" in data:
        err = data["error"]
        msg = err.get("error_user_msg") or err.get("message") or str(err)
        raise RuntimeError(f"Instagram : {msg}")
    r.raise_for_status()
    return data


def set_app(app_id: str, app_secret: str) -> None:
    store.update("instagram", app_id=app_id.strip(), app_secret=app_secret.strip())


def auth_url(state: str) -> str:
    acc = store.load("instagram")
    if not acc.get("app_id"):
        raise ValueError("Renseigne d'abord l'App ID et l'App Secret de ton app Meta.")
    return f"https://www.facebook.com/{API_VERSION}/dialog/oauth?" + urlencode({
        "client_id": acc["app_id"],
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "scope": SCOPES,
        "response_type": "code",
    })


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
            "Aucun compte Instagram professionnel trouvé. Vérifie que ton compte Instagram est en mode "
            "Professionnel (Créateur ou Entreprise), qu'il est lié à une Page Facebook, et que tu as "
            "autorisé cette Page pendant la connexion."
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
    raise ValueError("Compte introuvable.")


def status() -> dict:
    acc = store.load("instagram")
    exp = acc.get("expires_at")
    return {
        "configured": bool(acc.get("app_id") and acc.get("app_secret")),
        "app_id": acc.get("app_id", ""),
        "connected": bool(acc.get("token") and acc.get("account")) and not (exp and exp < time.time()),
        "expired": bool(exp and exp < time.time()),
        "expires_at": exp,
        "account": (acc.get("account") or {}).get("username"),
        "account_id": (acc.get("account") or {}).get("id"),
        "accounts": acc.get("accounts", []),
    }


class _ProgressFile:
    """Fichier lu par blocs qui remonte la progression de l'envoi."""

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


def publish(path, *, caption, thumb_offset_ms, report) -> dict:
    acc = store.load("instagram")
    token, ig = acc.get("token"), (acc.get("account") or {}).get("id")
    if not (token and ig):
        raise RuntimeError("Instagram n'est pas connecté.")

    report("Création du Reel…", 0.0)
    container = _check(requests.post(f"{GRAPH}/{ig}/media", data={
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "thumb_offset": int(thumb_offset_ms),
        "access_token": token,
    }, timeout=60))
    cid = container["id"]

    body = _ProgressFile(path, lambda p: report("Envoi de la vidéo…", p * 0.9))
    try:
        _check(requests.post(f"{RUPLOAD}/{cid}", headers={
            "Authorization": f"OAuth {token}",
            "offset": "0",
            "file_size": str(len(body)),
        }, data=body, timeout=(30, 3600)))
    finally:
        body.close()

    report("Traitement par Instagram…", 0.92)
    deadline = time.time() + 20 * 60
    while True:
        st = _check(requests.get(f"{GRAPH}/{cid}", params={
            "fields": "status_code,status", "access_token": token}, timeout=30))
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram a refusé la vidéo : {st.get('status') or code}")
        if time.time() > deadline:
            raise RuntimeError("Instagram met trop de temps à traiter la vidéo (plus de 20 min).")
        time.sleep(5)

    report("Publication…", 0.97)
    media = _check(requests.post(f"{GRAPH}/{ig}/media_publish", data={
        "creation_id": cid, "access_token": token}, timeout=60))
    url = None
    try:
        url = _check(requests.get(f"{GRAPH}/{media['id']}", params={
            "fields": "permalink", "access_token": token}, timeout=30)).get("permalink")
    except Exception:  # noqa: BLE001 - le lien est un bonus, la publication a réussi
        pass
    return {"url": url or f"https://www.instagram.com/{acc['account'].get('username', '')}/", "warning": None}
