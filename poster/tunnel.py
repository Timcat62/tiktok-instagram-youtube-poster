"""Temporarily exposes ONE local file on a public https URL (Cloudflare quick tunnel, no account).

Instagram's direct upload endpoint (rupload) often fails with "ProcessingFailedError", while
publishing from a public `video_url` works. This module serves only the given file, under a
random path, from a dedicated mini server, and closes everything when done.
"""
import platform
import re
import secrets
import shutil
import stat
import subprocess
import tarfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import requests
from flask import Flask, send_file
from werkzeug.serving import make_server

from . import store

_BIN_DIR = store.DATA / "bin"
_RELEASES = "https://github.com/cloudflare/cloudflared/releases/latest/download/"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_lock = threading.Lock()


class TunnelError(RuntimeError):
    """The temporary public link could not be opened."""


def _asset_name() -> str:
    system, machine = platform.system(), platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "amd64"
    if system == "Windows":
        return "cloudflared-windows-amd64.exe"
    if system == "Darwin":
        return f"cloudflared-darwin-{arch}.tgz"
    return f"cloudflared-linux-{arch}"


def cloudflared_exe(report=None) -> str:
    """Returns the cloudflared binary, downloading it once (~50 MB) if needed."""
    existing = shutil.which("cloudflared")
    if existing:
        return existing
    exe = _BIN_DIR / ("cloudflared.exe" if platform.system() == "Windows" else "cloudflared")
    with _lock:
        if exe.exists():
            return str(exe)
        _BIN_DIR.mkdir(parents=True, exist_ok=True)
        if report:
            report("Downloading the Cloudflare tunnel tool (first time only)…", 0.0)
        asset = _asset_name()
        tmp = _BIN_DIR / (asset + ".part")
        with requests.get(_RELEASES + asset, stream=True, timeout=(30, 600)) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    f.write(chunk)
        if asset.endswith(".tgz"):
            with tarfile.open(tmp) as tar:
                member = next(m for m in tar.getmembers() if m.name.endswith("cloudflared"))
                with tar.extractfile(member) as src, open(exe, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            tmp.unlink()
        else:
            tmp.replace(exe)
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return str(exe)


@contextmanager
def public_url(path: Path, report=None, timeout: float = 90):
    """Context manager yielding a public https URL that serves `path` until the block exits."""
    try:
        exe = cloudflared_exe(report)
    except Exception as e:  # noqa: BLE001 - download/network problem
        raise TunnelError(f"Could not get the Cloudflare tunnel tool ({e}).")
    token = secrets.token_urlsafe(24)
    filename = "video" + path.suffix.lower()

    app = Flask("poster-file-share")

    @app.get(f"/{token}/{filename}")
    def _serve():
        return send_file(path, mimetype="video/mp4", conditional=True)

    @app.errorhandler(404)
    def _nothing(_e):
        return "", 404

    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    local_port = server.server_port

    proc = subprocess.Popen(
        [exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{local_port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        creationflags=_NO_WINDOW,
    )
    try:
        if report:
            report("Opening a temporary public link for Instagram…", 0.0)
        base = _wait_for_url(proc, timeout)
        url = f"{base}/{token}/{filename}"
        _wait_until_reachable(url, timeout)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        server.shutdown()


def _wait_for_url(proc, timeout) -> str:
    found = {}

    def reader():
        for line in proc.stderr:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and "url" not in found:
                found["url"] = m.group(0)

    threading.Thread(target=reader, daemon=True).start()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if "url" in found:
            return found["url"]
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    raise TunnelError("Could not open the temporary Cloudflare link (check your internet connection or firewall).")


def _wait_until_reachable(url, timeout):
    """The tunnel's DNS name can take a few seconds to resolve."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, headers={"Range": "bytes=0-0"}, timeout=10)
            if r.status_code in (200, 206):
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise TunnelError("The temporary Cloudflare link did not become reachable in time.")
