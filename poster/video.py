"""ffmpeg-based video tools: probing, frame extraction, vertical conversion."""
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

SHORT_W, SHORT_H = 1080, 1920
SHORT_MAX_SECONDS = 180

VERTICAL_MODES = ("blur", "black", "crop")

# On Windows, prevents a console window from popping up on every ffmpeg call.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # ffmpeg binary shipped through pip, nothing to install manually

    return imageio_ffmpeg.get_ffmpeg_exe()


def probe(path: Path) -> dict:
    """Reads video info (displayed dimensions, duration, codec...)."""
    r = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=_NO_WINDOW,
    )
    out = r.stderr

    duration = 0.0
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", out)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

    vline = next(
        (l for l in out.splitlines() if "Video:" in l and "attached pic" not in l), None
    )
    if not vline:
        raise ValueError("No video track found in this file.")

    codec = re.search(r"Video: (\w+)", vline).group(1)
    dims = re.search(r"[ ,](\d{2,5})x(\d{2,5})[ ,\]]", vline)
    if not dims:
        raise ValueError("Could not read the video dimensions.")
    width, height = int(dims.group(1)), int(dims.group(2))

    fps_m = re.search(r"([\d.]+) fps", vline)
    fps = float(fps_m.group(1)) if fps_m else 30.0

    # Phone videos are often stored in landscape with a rotation flag.
    rot = re.search(r"rotation of (-?[\d.]+) degrees", out) or re.search(r"rotate\s*:\s*(-?\d+)", out)
    if rot and round(abs(float(rot.group(1)))) % 180 == 90:
        width, height = height, width

    cont = re.search(r"Input #0, (.+?), from", out)
    container = cont.group(1) if cont else ""

    if width > height * 1.05:
        orientation = "horizontal"
    elif height > width * 1.05:
        orientation = "vertical"
    else:
        orientation = "square"

    return {
        "width": width,
        "height": height,
        "duration": round(duration, 3),
        "fps": fps,
        "codec": codec,
        "container": container,
        "has_audio": "Audio:" in out,
        "orientation": orientation,
    }


def vertical_filter(mode: str) -> str:
    """ffmpeg filter that fits a video into a 9:16 (1080x1920) frame."""
    W, H = SHORT_W, SHORT_H
    if mode == "crop":
        return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
    if mode == "black":
        return (
            f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
        )
    # Blurred background: blur computed at low resolution then upscaled (much faster).
    return (
        "split=2[bg][fg];"
        "[bg]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,"
        f"boxblur=10:2,eq=brightness=-0.06,scale={W}:{H}[bgb];"
        f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs];"
        "[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )


def extract_frame(src: Path, t: float, width: int | None = None, mode: str | None = None) -> bytes:
    """Returns a JPEG frame at time t (seconds)."""
    filters = []
    if mode in VERTICAL_MODES:
        filters.append(vertical_filter(mode))
    if width:
        filters.append(f"scale={int(width)}:-2")
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(src),
           "-frames:v", "1"]
    if filters:
        cmd += ["-vf", ",".join(filters)]
    cmd += ["-q:v", "3", "-f", "image2pipe", "-vcodec", "mjpeg", "-"]
    r = subprocess.run(cmd, capture_output=True, creationflags=_NO_WINDOW)
    if r.returncode != 0 or not r.stdout:
        # Past the end (last frame): step back a little.
        if t > 0.2:
            return extract_frame(src, t - 0.2, width, mode)
        raise RuntimeError(r.stderr.decode("utf-8", "replace") or "Could not extract frame")
    return r.stdout


def _encode(src: Path, dst: Path, vf: str | None, duration: float, on_progress=None, max_fps: float | None = None,
            add_silence: bool = False) -> Path:
    cmd = [ffmpeg_exe(), "-y", "-hide_banner", "-i", str(src)]
    if add_silence:
        # Some platforms reject videos without an audio track: add a silent one.
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    filters = [vf] if vf else []
    if max_fps:
        filters.append(f"fps={max_fps:g}")
    if filters:
        cmd += ["-vf", ",".join(filters)]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-maxrate", "12M", "-bufsize", "24M",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats", "-loglevel", "error",
        str(dst),
    ]
    log_path = dst.with_suffix(".log")
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log, text=True, creationflags=_NO_WINDOW)
        for line in proc.stdout:
            if line.startswith("out_time_us=") and on_progress and duration > 0:
                try:
                    done = int(line.split("=", 1)[1]) / 1_000_000
                    on_progress(min(done / duration, 1.0))
                except ValueError:
                    pass
        proc.wait()
    if proc.returncode != 0:
        err = log_path.read_text(encoding="utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg conversion failed: {err[-500:]}")
    return dst


def to_vertical(src: Path, dst: Path, mode: str, meta: dict, on_progress=None) -> Path:
    """Converts a (horizontal) video to 1080x1920 so it is recognized as a Short."""
    return _encode(src, dst, vertical_filter(mode), meta["duration"], on_progress,
                   max_fps=60 if meta["fps"] > 60.5 else None)


def needs_compat(meta: dict) -> bool:
    """Instagram is the strictest: H.264/HEVC in MP4/MOV, 1920 px max, 60 fps max."""
    container_ok = any(c in meta["container"] for c in ("mp4", "mov"))
    return (
        meta["codec"] not in ("h264", "hevc")
        or not container_ok
        or max(meta["width"], meta["height"]) > 1920
        or meta["fps"] > 60.5
    )


def to_compat(src: Path, dst: Path, meta: dict, on_progress=None) -> Path:
    """Re-encodes to an H.264 MP4 that works everywhere, downscaling to 1920 px max if needed."""
    w, h = meta["width"], meta["height"]
    factor = min(1.0, 1920 / max(w, h))
    tw, th = int(w * factor) // 2 * 2, int(h * factor) // 2 * 2
    return _encode(src, dst, f"scale={tw}:{th},setsar=1", meta["duration"], on_progress,
                   max_fps=60 if meta["fps"] > 60.5 else None, add_silence=not meta["has_audio"])
