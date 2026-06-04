"""
analyzer_cli.py - CLI entry point for video-analyzer.

Usage:
    uv run va extract --file /path/to/video.mp4 [--output-dir /tmp/va_xxx] [--language zh]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

# Windows UTF-8 fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def existing_file_path(value: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"File not found: {value}")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="va",
        description="Video content analyzer: keyframe extraction + ASR transcription.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    extract_parser = sub.add_parser("extract", help="Extract keyframes and transcribe audio")
    extract_parser.add_argument("--file", required=True, type=existing_file_path, help="Video file path")
    extract_parser.add_argument("--output-dir", default=None, help="Directory to save keyframe images (default: auto temp dir)")
    extract_parser.add_argument("--language", default="zh", help="ASR language code (default: zh)")

    return parser


def cmd_extract(args: argparse.Namespace) -> int:
    from extractor import extract_keyframes, get_video_duration
    from transcriber import transcribe_video

    video_path = str(args.file)

    # Step 1: Get duration
    print(f"[va] Analyzing: {video_path}", file=sys.stderr)
    duration = get_video_duration(video_path)
    if duration:
        print(f"[va] Duration: {duration:.1f}s ({duration/60:.1f}min)", file=sys.stderr)

    # Step 2: Extract keyframes
    print("[va] Extracting keyframes...", file=sys.stderr)
    try:
        frames = extract_keyframes(video_path, output_dir=args.output_dir, duration=duration)
        print(f"[va] Extracted {len(frames)} frames", file=sys.stderr)
    except RuntimeError as e:
        print(f"[va] Frame extraction failed: {e}", file=sys.stderr)
        frames = []

    # Step 3: ASR transcription
    print("[va] Transcribing audio...", file=sys.stderr)
    transcript = ""
    audio_empty = False
    try:
        transcript = transcribe_video(video_path, language=args.language)
        if not transcript or not transcript.strip():
            audio_empty = True
            print("[va] No speech detected (silent or music-only)", file=sys.stderr)
        else:
            print(f"[va] Transcript: {len(transcript)} chars", file=sys.stderr)
    except Exception as e:
        audio_empty = True
        print(f"[va] ASR failed (non-fatal): {e}", file=sys.stderr)

    # Step 4: Output JSON to stdout
    result = {
        "frames": frames,
        "transcript": transcript,
        "duration": round(duration, 1) if duration else None,
        "audio_empty": audio_empty,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "extract":
            return cmd_extract(args)
        raise RuntimeError(f"Unknown command: {args.command}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
