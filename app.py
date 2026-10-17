"""Social Poster: publish one video to YouTube (Shorts), Instagram (Reels) and TikTok at once.

Run: python app.py  (then http://localhost:8765 opens in your browser)
"""
import re
import secrets
import threading
import webbrowser
from urllib.parse import quote

from flask import Flask, Response, jsonify, redirect, request, send_from_directory
from werkzeug.exceptions import HTTPException

from poster import instagram, jobs, media, store, tiktok, video, youtube

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Pending OAuth states (anti-CSRF + TikTok PKCE verifier).
_pending_auth: dict[str, dict] = {}


def ok(**data):
    return jsonify({"ok": True, **data})


@app.errorhandler(Exception)
def _handle_error(e):
    if isinstance(e, HTTPException):
        if not request.path.startswith("/api/"):
            return e
        return jsonify({"ok": False, "error": e.description}), e.code
    app.logger.exception(e)
    status = 404 if isinstance(e, FileNotFoundError) else 400 if isinstance(e, ValueError) else 500
    return jsonify({"ok": False, "error": str(e) or e.__class__.__name__}), status


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


# ---------------------------------------------------------------- Accounts

@app.get("/api/status")
def api_status():
    return ok(
        youtube=youtube.status(),
        instagram=instagram.status(),
        tiktok=tiktok.status(),
        redirects={
            "instagram": instagram.REDIRECT_URI,
            "tiktok": tiktok.REDIRECT_URI,
        },
    )


@app.post("/api/accounts/youtube/client")
def yt_client():
    f = request.files.get("file")
    if not f:
        raise ValueError("No file received.")
    youtube.set_client_config(f.read())
    return ok()


@app.post("/api/accounts/youtube/connect")
def yt_connect():
    youtube.start_auth()
    return ok()


@app.post("/api/accounts/instagram/config")
def ig_config():
    body = request.get_json(force=True)
    if not body.get("app_id") or not body.get("app_secret"):
        raise ValueError("App ID and App Secret are required.")
    instagram.set_app(body["app_id"], body["app_secret"])
    return ok()


@app.post("/api/accounts/instagram/token")
def ig_token():
    token = (request.get_json(force=True).get("token") or "").strip()
    if not token:
        raise ValueError("Paste an access token.")
    instagram.connect_with_token(token)
    return ok()


@app.post("/api/accounts/instagram/select")
def ig_select():
    instagram.select_account(request.get_json(force=True).get("id", ""))
    return ok()


@app.post("/api/accounts/tiktok/config")
def tt_config():
    body = request.get_json(force=True)
    if not body.get("client_key") or not body.get("client_secret"):
        raise ValueError("Client key and Client secret are required.")
    tiktok.set_app(body["client_key"], body["client_secret"])
    return ok()


@app.get("/api/tiktok/creator_info")
def tt_creator_info():
    return ok(info=tiktok.creator_info())


@app.post("/api/accounts/<platform>/disconnect")
def disconnect(platform):
    keys = {"youtube": ("token", "account"), "instagram": ("token", "account", "accounts", "expires_at"),
            "tiktok": ("token", "account")}
    if platform not in keys:
        raise ValueError("Unknown platform")
    store.forget(platform, *keys[platform])
    return ok()


def _back(platform, error=None):
    q = f"error={quote(error)}&platform={platform}" if error else f"connected={platform}"
    return redirect(f"/?{q}#accounts")


@app.get("/auth/instagram/start")
def ig_start():
    state = secrets.token_urlsafe(24)
    try:
        url = instagram.auth_url(state)
    except ValueError as e:
        return _back("instagram", str(e))
    _pending_auth[state] = {"platform": "instagram"}
    return redirect(url)


@app.get("/auth/instagram/callback")
def ig_callback():
    pending = _pending_auth.pop(request.args.get("state", ""), None)
    if not pending or pending["platform"] != "instagram":
        return _back("instagram", "Login session expired, please try again.")
    if request.args.get("error"):
        return _back("instagram", request.args.get("error_description") or request.args["error"])
    try:
        instagram.handle_callback(request.args["code"])
    except Exception as e:  # noqa: BLE001
        return _back("instagram", str(e))
    return _back("instagram")


@app.get("/auth/tiktok/start")
def tt_start():
    state, verifier = secrets.token_urlsafe(24), tiktok.new_verifier()
    try:
        url = tiktok.auth_url(state, verifier)
    except ValueError as e:
        return _back("tiktok", str(e))
    _pending_auth[state] = {"platform": "tiktok", "verifier": verifier}
    return redirect(url)


@app.get("/auth/tiktok/callback/")
def tt_callback():
    pending = _pending_auth.pop(request.args.get("state", ""), None)
    if not pending or pending["platform"] != "tiktok":
        return _back("tiktok", "Login session expired, please try again.")
    if request.args.get("error"):
        return _back("tiktok", request.args.get("error_description") or request.args["error"])
    try:
        tiktok.handle_callback(request.args["code"], pending["verifier"])
    except Exception as e:  # noqa: BLE001
        return _back("tiktok", str(e))
    return _back("tiktok")


# ---------------------------------------------------------------- Videos

@app.post("/api/videos")
def upload_video():
    f = request.files.get("file")
    if not f:
        raise ValueError("No video received.")
    return ok(video=media.save_upload(f))


@app.get("/api/videos/<video_id>/frame")
def frame(video_id):
    t = float(request.args.get("t", 0))
    width = min(int(request.args.get("w", 720)), 1920)
    mode = request.args.get("mode") or None
    jpg = video.extract_frame(media.source_path(video_id), t, width=width, mode=mode)
    return Response(jpg, mimetype="image/jpeg", headers={"Cache-Control": "max-age=3600"})


# ---------------------------------------------------------------- Publishing

_HASHTAG_RE = re.compile(r"#?([^\s#,;]+)")


def _normalize_hashtags(raw) -> list[str]:
    if isinstance(raw, list):
        raw = " ".join(raw)
    seen, out = set(), []
    for m in _HASHTAG_RE.finditer(raw or ""):
        tag = "#" + m.group(1)
        if tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out


@app.post("/api/publish")
def publish():
    body = request.get_json(force=True)
    platforms = [p for p in body.get("platforms", []) if p in store.PLATFORMS]
    if not platforms:
        raise ValueError("Select at least one platform.")
    media.load_meta(body.get("video_id", ""))  # checks that the video exists
    opts = {
        "video_id": body["video_id"],
        "platforms": platforms,
        "title": body.get("title", ""),
        "description": body.get("description", ""),
        "hashtags": _normalize_hashtags(body.get("hashtags", "")),
        "cover_t": float(body.get("cover_t", 0)),
        "vertical_mode": body.get("vertical_mode", "blur"),
        "vertical_all": bool(body.get("vertical_all")),
        "youtube": body.get("youtube", {}),
        "tiktok": body.get("tiktok", {}),
    }
    return ok(job_id=jobs.start(opts))


@app.get("/api/jobs/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        raise FileNotFoundError("Publication not found")
    return ok(job=job)


def main():
    media.cleanup()
    url = store.BASE_URL
    print(f"\n  Social Poster is running: {url}\n  (Ctrl+C to stop)\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=store.PORT, threaded=True, debug=False)


if __name__ == "__main__":
    main()
