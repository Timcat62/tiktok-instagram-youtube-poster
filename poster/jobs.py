"""Runs publications in the background, with per-platform progress tracking."""
import threading
import time
import traceback
import uuid

from . import instagram, tiktok, video, youtube
from .media import video_dir, load_meta, source_path

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def build_caption(description: str, hashtags: list[str]) -> str:
    tags = " ".join(hashtags)
    return "\n\n".join(p for p in (description.strip(), tags) if p)


def get(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return None if job is None else {**job, "platforms": {k: dict(v) for k, v in job["platforms"].items()},
                                         "prep": dict(job["prep"])}


def _set(job, target, **fields):
    with _lock:
        (job["prep"] if target == "prep" else job["platforms"][target]).update(fields)


def start(opts: dict) -> str:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "created": time.time(),
        "done": False,
        "prep": {"state": "running", "message": "Preparing…", "progress": 0.0},
        "platforms": {p: {"state": "waiting", "message": "Waiting", "progress": 0.0, "url": None, "warning": None}
                      for p in opts["platforms"]},
    }
    with _lock:
        _jobs[job_id] = job
    threading.Thread(target=_run, args=(job, opts), daemon=True).start()
    return job_id


def _prepare(job, opts):
    vid = opts["video_id"]
    folder = video_dir(vid)
    src = source_path(vid)
    meta = load_meta(vid)
    platforms = opts["platforms"]
    horizontal = meta["orientation"] == "horizontal"
    mode = opts.get("vertical_mode") if opts.get("vertical_mode") in video.VERTICAL_MODES else "blur"

    files = {}
    vertical_file = None

    def make_vertical():
        nonlocal vertical_file
        if vertical_file is None:
            dst = folder / f"vertical_{mode}.mp4"
            if not dst.exists():
                _set(job, "prep", message="Converting to vertical 9:16…", progress=0.0)
                tmp = folder / f"vertical_{mode}.tmp.mp4"
                video.to_vertical(src, tmp, mode, meta, lambda p: _set(job, "prep", progress=p))
                tmp.replace(dst)
            vertical_file = dst
        return vertical_file

    if "youtube" in platforms:
        files["youtube"] = make_vertical() if horizontal else src

    others = [p for p in platforms if p != "youtube"]
    if others:
        if horizontal and opts.get("vertical_all"):
            other_file = make_vertical()
        elif video.needs_compat(meta):
            dst = folder / "compat.mp4"
            if not dst.exists():
                _set(job, "prep", message="Re-encoding for Instagram/TikTok compatibility…", progress=0.0)
                tmp = folder / "compat.tmp.mp4"
                video.to_compat(src, tmp, meta, lambda p: _set(job, "prep", progress=p))
                tmp.replace(dst)
            other_file = dst
        else:
            other_file = src
        for p in others:
            files[p] = other_file

    cover_t = max(0.0, min(float(opts.get("cover_t", 0)), max(meta["duration"] - 0.05, 0)))
    cover_path = folder / "cover.jpg"
    cover_src = files.get("youtube", src)
    cover_path.write_bytes(video.extract_frame(cover_src, cover_t, width=1280 if cover_src == src and horizontal else 1080))

    return files, meta, cover_t, cover_path


def _publish_one(job, platform, file, opts, meta, cover_t, cover_path):
    def report(message, progress):
        _set(job, platform, message=message, progress=round(float(progress), 3))

    _set(job, platform, state="running", message="Starting…")
    caption = build_caption(opts.get("description", ""), opts.get("hashtags", []))
    try:
        if platform == "youtube":
            title = (opts.get("title") or "").strip() or (opts.get("description") or "").strip().split("\n")[0]
            is_short = meta["duration"] <= video.SHORT_MAX_SECONDS
            res = youtube.publish(
                file, title=title, description=caption, tags=opts.get("hashtags", []),
                privacy=opts.get("youtube", {}).get("privacy", "public"),
                cover_path=cover_path, is_short=is_short, report=report,
            )
        elif platform == "instagram":
            res = instagram.publish(file, caption=caption, thumb_offset_ms=cover_t * 1000, report=report)
        elif platform == "tiktok":
            t = opts.get("tiktok", {})
            res = tiktok.publish(
                file, caption=caption, cover_ms=cover_t * 1000,
                privacy=t.get("privacy", ""), mode=t.get("mode", "direct"),
                disable_comment=t.get("disable_comment", True),
                disable_duet=t.get("disable_duet", True),
                disable_stitch=t.get("disable_stitch", True),
                brand_organic=t.get("brand_organic", False),
                brand_content=t.get("brand_content", False),
                report=report,
            )
        else:
            raise RuntimeError("Unknown platform")
        _set(job, platform, state="done", progress=1.0, url=res.get("url"), warning=res.get("warning"),
             message=res.get("message") or "Published!")
    except Exception as e:  # noqa: BLE001 - each platform fails independently
        traceback.print_exc()
        _set(job, platform, state="error", message=str(e) or e.__class__.__name__)


def _run(job, opts):
    try:
        files, meta, cover_t, cover_path = _prepare(job, opts)
        _set(job, "prep", state="done", message="Video ready", progress=1.0)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        _set(job, "prep", state="error", message=str(e))
        for p in opts["platforms"]:
            _set(job, p, state="error", message="Could not prepare the video")
        job["done"] = True
        return

    threads = [threading.Thread(target=_publish_one, args=(job, p, files[p], opts, meta, cover_t, cover_path), daemon=True)
               for p in opts["platforms"]]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    job["done"] = True
