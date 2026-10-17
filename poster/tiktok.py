"""Publication TikTok via la Content Posting API (Login Kit « Desktop » avec PKCE)."""
import hashlib
import secrets
import time
from urllib.parse import urlencode

import requests

from . import store

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
API = "https://open.tiktokapis.com/v2"
SCOPES = "user.info.basic,video.publish,video.upload"
REDIRECT_URI = f"{store.BASE_URL}/auth/tiktok/callback/"

MB = 1024 * 1024


def _check(r: requests.Response) -> dict:
    try:
        data = r.json()
    except ValueError:
        r.raise_for_status()
        raise RuntimeError(f"Réponse inattendue de TikTok : {r.text[:300]}")
    err = data.get("error")
    if isinstance(err, dict) and err.get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok : {err.get('message') or err.get('code')}")
    if isinstance(err, str):  # format des erreurs OAuth
        raise RuntimeError(f"TikTok : {data.get('error_description') or err}")
    r.raise_for_status()
    return data


def set_app(client_key: str, client_secret: str) -> None:
    store.update("tiktok", client_key=client_key.strip(), client_secret=client_secret.strip())


def new_verifier() -> str:
    return secrets.token_urlsafe(64)[:64]


def auth_url(state: str, verifier: str) -> str:
    acc = store.load("tiktok")
    if not acc.get("client_key"):
        raise ValueError("Renseigne d'abord le Client key et le Client secret de ton app TikTok.")
    return AUTH_URL + "?" + urlencode({
        "client_key": acc["client_key"],
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": state,
        # Particularité TikTok (Desktop) : le challenge PKCE est le SHA-256 encodé en hexadécimal.
        "code_challenge": hashlib.sha256(verifier.encode()).hexdigest(),
        "code_challenge_method": "S256",
    })


def _save_token(data: dict) -> None:
    now = int(time.time())
    store.update(
        "tiktok",
        token={
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_at": now + int(data.get("expires_in", 86400)),
            "refresh_expires_at": now + int(data.get("refresh_expires_in", 365 * 86400)),
            "open_id": data.get("open_id"),
            "scope": data.get("scope"),
        },
    )


def handle_callback(code: str, verifier: str) -> None:
    acc = store.load("tiktok")
    data = _check(requests.post(f"{API}/oauth/token/", data={
        "client_key": acc["client_key"],
        "client_secret": acc["client_secret"],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30))
    _save_token(data)
    info = _check(requests.get(f"{API}/user/info/", params={"fields": "open_id,display_name,avatar_url"},
                               headers={"Authorization": f"Bearer {data['access_token']}"}, timeout=30))
    user = info.get("data", {}).get("user", {})
    store.update("tiktok", account={"name": user.get("display_name", ""), "avatar": user.get("avatar_url")})


def access_token() -> str:
    acc = store.load("tiktok")
    tok = acc.get("token")
    if not tok:
        raise RuntimeError("TikTok n'est pas connecté.")
    if tok["expires_at"] - 300 > time.time():
        return tok["access_token"]
    if not tok.get("refresh_token") or tok.get("refresh_expires_at", 0) < time.time():
        raise RuntimeError("La connexion TikTok a expiré : reconnecte ton compte dans l'onglet Comptes.")
    data = _check(requests.post(f"{API}/oauth/token/", data={
        "client_key": acc["client_key"],
        "client_secret": acc["client_secret"],
        "grant_type": "refresh_token",
        "refresh_token": tok["refresh_token"],
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30))
    _save_token(data)
    return data["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}


def creator_info() -> dict:
    token = access_token()
    return _check(requests.post(f"{API}/post/publish/creator_info/query/", headers=_headers(token),
                                json={}, timeout=30)).get("data", {})


def status() -> dict:
    acc = store.load("tiktok")
    tok = acc.get("token") or {}
    return {
        "configured": bool(acc.get("client_key") and acc.get("client_secret")),
        "client_key": acc.get("client_key", ""),
        "connected": bool(tok) and tok.get("refresh_expires_at", 0) > time.time(),
        "account": (acc.get("account") or {}).get("name"),
    }


def _content_type(path) -> str:
    ext = path.suffix.lower()
    return {".mov": "video/quicktime", ".webm": "video/webm"}.get(ext, "video/mp4")


def publish(path, *, caption, cover_ms, privacy, mode, disable_comment, disable_duet, disable_stitch, report) -> dict:
    token = access_token()
    size = path.stat().st_size

    # Règles TikTok : morceaux de 5 à 64 Mo, le dernier absorbe le reste (128 Mo max).
    if size <= 64 * MB:
        chunk_size, count = size, 1
    else:
        chunk_size = 10 * MB
        count = size // chunk_size

    source_info = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk_size, "total_chunk_count": count}

    report("Préparation de l'envoi…", 0.0)
    if mode == "draft":
        init = _check(requests.post(f"{API}/post/publish/inbox/video/init/", headers=_headers(token),
                                    json={"source_info": source_info}, timeout=60))
    else:
        info = creator_info()
        options = info.get("privacy_level_options") or []
        if options and privacy not in options:
            raise RuntimeError(f"Visibilité « {privacy} » non autorisée pour ce compte (possibles : {', '.join(options)}).")
        post_info = {
            "title": caption[:2200],
            "privacy_level": privacy,
            "disable_comment": bool(disable_comment),
            "disable_duet": bool(disable_duet),
            "disable_stitch": bool(disable_stitch),
            "video_cover_timestamp_ms": int(cover_ms),
        }
        init = _check(requests.post(f"{API}/post/publish/video/init/", headers=_headers(token),
                                    json={"post_info": post_info, "source_info": source_info}, timeout=60))

    publish_id = init["data"]["publish_id"]
    upload_url = init["data"]["upload_url"]

    with open(path, "rb") as f:
        for i in range(count):
            start = i * chunk_size
            end = size - 1 if i == count - 1 else start + chunk_size - 1
            chunk = f.read(end - start + 1)
            for attempt in range(3):
                r = requests.put(upload_url, data=chunk, headers={
                    "Content-Type": _content_type(path),
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {start}-{end}/{size}",
                }, timeout=(30, 1800))
                if r.status_code in (200, 201, 206):
                    break
                if r.status_code < 500 or attempt == 2:
                    raise RuntimeError(f"TikTok a refusé l'envoi (HTTP {r.status_code}) : {r.text[:300]}")
                time.sleep(3)
            report("Envoi de la vidéo…", (end + 1) / size * 0.9)

    report("Traitement par TikTok…", 0.92)
    deadline = time.time() + 20 * 60
    while time.time() < deadline:
        st = _check(requests.post(f"{API}/post/publish/status/fetch/", headers=_headers(access_token()),
                                  json={"publish_id": publish_id}, timeout=30)).get("data", {})
        s = st.get("status")
        if s == "PUBLISH_COMPLETE":
            name = (store.load("tiktok").get("account") or {}).get("name", "")
            warning = None
            if privacy == "SELF_ONLY":
                warning = "Publiée en « Moi uniquement » (privé). Tant que ton app TikTok n'est pas auditée, c'est la seule option."
            return {"url": None, "warning": warning,
                    "message": f"Publiée sur le compte {name}" if name else "Publiée !"}
        if s == "SEND_TO_USER_INBOX":
            return {"url": None, "warning": None,
                    "message": "Vidéo envoyée dans tes brouillons TikTok : ouvre l'app TikTok (notifications) pour finaliser la publication."}
        if s == "FAILED":
            raise RuntimeError(f"TikTok a refusé la vidéo : {st.get('fail_reason', 'raison inconnue')}")
        time.sleep(5)
    return {"url": None, "warning": "TikTok traite encore la vidéo : vérifie ton profil dans quelques minutes.", "message": None}
