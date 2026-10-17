"""Stockage local des réglages et des jetons de connexion (dossier data/, jamais versionné)."""
import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("POSTER_DATA_DIR", ROOT / "data"))
UPLOADS = DATA / "uploads"
ACCOUNTS = DATA / "accounts"

PORT = int(os.environ.get("PORT", "8765"))
BASE_URL = f"http://localhost:{PORT}"

PLATFORMS = ("youtube", "instagram", "tiktok")

_lock = threading.Lock()

for _d in (UPLOADS, ACCOUNTS):
    _d.mkdir(parents=True, exist_ok=True)


def _path(platform: str) -> Path:
    if platform not in PLATFORMS:
        raise ValueError(f"Plateforme inconnue : {platform}")
    return ACCOUNTS / f"{platform}.json"


def load(platform: str) -> dict:
    p = _path(platform)
    with _lock:
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}


def save(platform: str, data: dict) -> None:
    p = _path(platform)
    with _lock:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)


def update(platform: str, **fields) -> dict:
    data = load(platform)
    data.update(fields)
    save(platform, data)
    return data


def forget(platform: str, *keys: str) -> None:
    data = load(platform)
    for k in keys:
        data.pop(k, None)
    save(platform, data)
