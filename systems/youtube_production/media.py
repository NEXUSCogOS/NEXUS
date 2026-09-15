"""Real, minimal, credential-free media production. NEXUS Federation F8,
mission sections 10 (voice), 11 (visuals), 16 (editing/rendering),
19 (thumbnail), 20 (metadata).

Deliberately does NOT reuse the pre-existing pipeline's DaVinci-Resolve
render path (confirmed absent from this machine, YOUTUBE_F8_FORENSIC_
REPORT.md) or its Slack-gated approval/Google-API-upload path. Uses only
what YOUTUBE_F8_FORENSIC_REPORT.md confirmed is REALLY, locally available:
macOS `say` (real TTS, no cloud credentials), Pillow (real image
rendering), ffmpeg (real muxing). Every output file is a real file on
disk with a real sha256 hash -- nothing here is a simulated/stubbed
return value.
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from schema import GeneratedAssetRecord, RenderRecord, ThumbnailCandidate


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_voice(text: str, out_path: Path, voice: str = "Samantha") -> tuple[Path, dict]:
    """Real macOS `say` invocation -> a real .aiff file. Raises if `say`
    is unavailable rather than silently returning a fake path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    result = subprocess.run(
        ["say", "-v", voice, "-o", str(out_path), text],
        capture_output=True, text=True, timeout=60,
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"macOS `say` failed (rc={result.returncode}): {result.stderr}")
    return out_path, {
        "generator": "macos_say", "voice": voice, "elapsed_seconds": elapsed,
        "returncode": result.returncode, "output_bytes": out_path.stat().st_size,
    }


def _load_font(size: int) -> ImageFont.ImageFont:
    for candidate in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def generate_visual_still(text: str, out_path: Path, size=(1280, 720), bg=(18, 22, 30), fg=(240, 240, 245)) -> Path:
    """Real Pillow-rendered still image -- a title-card style visual
    carrying evidence-derived text, not a stock photo and not
    misrepresented as documentary footage (mission section 15)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color=bg)
    draw = ImageDraw.Draw(img)
    font = _load_font(40)

    # naive word-wrap
    words = text.split()
    lines, current = [], ""
    for w in words:
        trial = (current + " " + w).strip()
        if draw.textlength(trial, font=font) > size[0] - 120:
            lines.append(current)
            current = w
        else:
            current = trial
    if current:
        lines.append(current)

    line_height = 56
    total_h = line_height * len(lines)
    y = (size[1] - total_h) // 2
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((size[0] - w) / 2, y), line, font=font, fill=fg)
        y += line_height

    img.save(out_path, format="PNG")
    return out_path


def render_video(
    *,
    audio_path: Path,
    still_paths: list[Path],
    out_path: Path,
    resolution: str = "1280x720",
) -> RenderRecord:
    """Real ffmpeg invocation: loops the still image(s) for the audio's
    real duration, muxes real audio, writes a real .mp4. Raises on
    failure rather than fabricating a render record."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    # Real audio duration via ffprobe.
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True, timeout=30,
    )
    duration = float(probe.stdout.strip() or 0.0)

    still = still_paths[0]
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(still), "-i", str(audio_path),
            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p", "-shortest", "-s", resolution,
            str(out_path),
        ],
        capture_output=True, text=True, timeout=120,
    )
    elapsed = time.monotonic() - started

    if result.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"ffmpeg render failed (rc={result.returncode}): {result.stderr[-2000:]}")

    return RenderRecord(
        render_id="",  # filled by caller with a deterministic id
        production_mission_id="",  # filled by caller
        input_script_hash="",  # filled by caller
        input_asset_hashes=[_sha256_file(p) for p in still_paths] + [_sha256_file(audio_path)],
        render_settings={"resolution": resolution, "codec": "libx264/aac", "backend": "ffmpeg"},
        duration_seconds=duration,
        resolution=resolution,
        codec="h264/aac",
        output_hash=_sha256_file(out_path),
        output_path=str(out_path),
        elapsed_compute_seconds=elapsed,
        storage_bytes=out_path.stat().st_size,
    )


def generate_thumbnail(text: str, out_path: Path) -> Path:
    return generate_visual_still(text, out_path, size=(1280, 720), bg=(30, 20, 20), fg=(255, 230, 200))
