"""Publication YouTube via l'API YouTube Data v3 (OAuth Google, client de type « Application de bureau »)."""
import json
import threading

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from . import store

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

auth_status = {"running": False, "error": None}


def set_client_config(raw: bytes) -> None:
    try:
        cfg = json.loads(raw)
    except ValueError:
        raise ValueError("Ce fichier n'est pas un JSON valide.")
    if "installed" not in cfg:
        raise ValueError(
            "Ce fichier ne correspond pas à un client OAuth « Application de bureau ». "
            "Crée un identifiant de type « Application de bureau » dans Google Cloud."
        )
    store.update("youtube", client_config=cfg)


def get_credentials() -> Credentials | None:
    acc = store.load("youtube")
    tok = acc.get("token")
    if not tok:
        return None
    creds = Credentials.from_authorized_user_info(tok, SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        store.update("youtube", token=json.loads(creds.to_json()))
    return creds


def _auth_worker(client_config: dict) -> None:
    try:
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(
            port=0,
            open_browser=True,
            timeout_seconds=300,
            authorization_prompt_message="",
            success_message="Connexion YouTube réussie ! Tu peux fermer cet onglet et revenir sur l'application.",
            prompt="consent",
            access_type="offline",
        )
        if not creds or not creds.valid:
            raise RuntimeError("Connexion annulée ou expirée.")
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
        if not items:
            raise RuntimeError("Aucune chaîne YouTube trouvée sur ce compte Google.")
        store.update(
            "youtube",
            token=json.loads(creds.to_json()),
            account={"id": items[0]["id"], "name": items[0]["snippet"]["title"]},
        )
        auth_status["error"] = None
    except Exception as e:  # noqa: BLE001 - affiché tel quel dans l'interface
        auth_status["error"] = str(e) or e.__class__.__name__
    finally:
        auth_status["running"] = False


def start_auth() -> None:
    cfg = store.load("youtube").get("client_config")
    if not cfg:
        raise ValueError("Importe d'abord le fichier client_secret.json de Google Cloud.")
    if auth_status["running"]:
        return
    auth_status.update(running=True, error=None)
    threading.Thread(target=_auth_worker, args=(cfg,), daemon=True).start()


def status() -> dict:
    acc = store.load("youtube")
    return {
        "configured": bool(acc.get("client_config")),
        "connected": bool(acc.get("token")),
        "account": (acc.get("account") or {}).get("name"),
        "auth_running": auth_status["running"],
        "auth_error": auth_status["error"],
    }


def _clean(text: str) -> str:
    # YouTube refuse les caractères < et > dans le titre et la description.
    return text.replace("<", "‹").replace(">", "›")


def publish(path, *, title, description, tags, privacy, cover_path, is_short, report) -> dict:
    creds = get_credentials()
    if not creds:
        raise RuntimeError("YouTube n'est pas connecté.")
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    title = _clean(title).strip()[:100] or "Nouvelle vidéo"
    description = _clean(description)
    if is_short and "#shorts" not in (title + description).lower():
        description = (description + "\n\n#Shorts").strip()

    clean_tags, total = [], 0
    for t in tags:
        t = _clean(t.lstrip("#"))
        if t and total + len(t) + 1 <= 480:
            clean_tags.append(t)
            total += len(t) + 1

    body = {
        "snippet": {"title": title, "description": description[:5000], "tags": clean_tags, "categoryId": "22"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True,
                            mimetype="application/octet-stream")
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    report("Envoi de la vidéo…", 0.0)
    response = None
    while response is None:
        progress, response = request.next_chunk(num_retries=3)
        if progress:
            report("Envoi de la vidéo…", progress.progress())
    video_id = response["id"]

    warning = None
    if cover_path:
        report("Ajout de la miniature…", 1.0)
        try:
            yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(cover_path), mimetype="image/jpeg")).execute()
        except HttpError as e:
            warning = (
                "Vidéo publiée, mais la miniature n'a pas pu être appliquée "
                "(la chaîne doit être validée par téléphone pour les miniatures personnalisées). "
                f"Détail : {e.reason if hasattr(e, 'reason') else e}"
            )

    url = f"https://youtube.com/shorts/{video_id}" if is_short else f"https://youtu.be/{video_id}"
    return {"url": url, "warning": warning}
