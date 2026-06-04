"""
extractor.py - Extract keyframes from video using ffmpeg.

Adaptive frame count based on video duration (density-aware):
  ≤15s     → 5 frames  (~3s interval, covers fast-cut ads)
  15s-60s  → 8 frames  (~3-7s interval)
  1-3min   → 8 frames  (~8-22s interval)
  3-10min  → 10 frames (~18-60s interval)
  >10min   → 12 frames (cap)

Frames are evenly distributed between 10% and 90% of duration
to avoid intro/outro black screens and logos.
"""

from __future__ import annotations

import os
import subprocess
import tempfile

from transcriber import find_tool

# ─── Adaptive frame count ────────────────────────────────
MIN_FRAMES = 5
MAX_FRAMES = 12


def _calc_frame_count(duration: float) -> int:
    """Determine how many frames to extract based on duration.

    Short videos (ads, promos) have high scene-change density,
    so they need more frames per second than long videos.
    """
    if duration <= 15:        # ≤15s (short ads)
        return 5
    elif duration <= 60:      # 15s-60s
        return 8
    elif duration <= 180:     # 1-3 min
        return 8
    elif duration <= 600:     # 3-10 min
        return 10
    else:                     # >10 min
        return MAX_FRAMES


def _calc_percentages(n: int) -> list[float]:
    """Generate n evenly spaced percentages between 10% and 90%."""
    if n == 1:
        return [0.5]
    return [0.1 + (0.8 * i / (n - 1)) for i in range(n)]


def get_video_duration(video_path: str) -> float | None:
    """Get video duration in seconds using ffprobe."""
    ffprobe = find_tool("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def extract_keyframes(video_path: str, output_dir: str | None = None, duration: float | None = None) -> list[str]:
    """Extract keyframes adaptively based on video duration.

    Args:
        video_path: Absolute path to video file.
        output_dir: Directory to save frames. If None, creates a temp dir.
        duration: Pre-fetched video duration in seconds. If None, calls ffprobe.

    Returns:
        List of absolute paths to extracted jpg files.

    Raises:
        RuntimeError: If ffmpeg/ffprobe not found or extraction fails.
    """
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg not found. Please install ffmpeg:\n"
            "  macOS: brew install ffmpeg\n"
            "  Windows: winget install Gyan.FFmpeg\n"
            "  Linux: sudo apt install ffmpeg"
        )

    if duration is None:
        duration = get_video_duration(video_path)
    if duration is None or duration <= 0:
        raise RuntimeError(f"Cannot determine video duration: {video_path}")

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="va_frames_")
    else:
        os.makedirs(output_dir, exist_ok=True)

    frame_count = _calc_frame_count(duration)
    percentages = _calc_percentages(frame_count)
    frame_paths = []

    for i, pct in enumerate(percentages):
        ts = duration * pct
        label = f"frame_{i+1:02d}_{int(pct * 100)}pct"
        out_path = os.path.join(output_dir, f"{label}.jpg")

        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-ss", f"{ts:.2f}",
                    "-i", video_path,
                    "-frames:v", "1",
                    "-q:v", "2",
                    out_path,
                    "-y",
                ],
                capture_output=True, check=True, timeout=30,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"ffmpeg frame extraction failed at {ts:.1f}s: {e.stderr.decode()[:200]}"
            )

        if not os.path.isfile(out_path):
            raise RuntimeError(f"Frame not created: {out_path}")

        frame_paths.append(out_path)

    return frame_paths
