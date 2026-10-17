"""Imported video management (one folder per video in data/uploads)."""
import json
import re
import shutil
import time
import uuid
from pathlib import Path

from . import store, video

ALLOWED_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def video_dir(video_id: str) -> Path:
    if not _ID_RE.match(video_id or ""):
        raise ValueError("Invalid video id")
    d = store.UPLOADS / video_id
    if not d.is_dir():
        raise FileNotFoundError("Video not found (it may have been deleted).")
    return d


def source_path(video_id: str) -> Path:
    d = video_dir(video_id)
    return next(d.glob("source.*"))


def load_meta(video_id: str) -> dict:
    return json.loads((video_dir(video_id) / "meta.json").read_text(encoding="utf-8"))


def save_upload(file_storage) -> dict:
    ext = Path(file_storage.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Unsupported format ({ext or 'unknown'}). Accepted formats: {', '.join(sorted(ALLOWED_EXT))}")
    video_id = uuid.uuid4().hex
    d = store.UPLOADS / video_id
    d.mkdir(parents=True)
    src = d / f"source{ext}"
    file_storage.save(src)
    try:
        meta = video.probe(src)
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise
    meta.update(id=video_id, filename=file_storage.filename, size=src.stat().st_size)
    (d / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def cleanup(max_age_days: int = 7) -> None:
    """Deletes videos imported more than max_age_days days ago."""
    limit = time.time() - max_age_days * 86400
    for d in store.UPLOADS.iterdir():
        if d.is_dir() and d.stat().st_mtime < limit:
            shutil.rmtree(d, ignore_errors=True)
