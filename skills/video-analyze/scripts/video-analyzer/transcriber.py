#!/usr/bin/env python3
"""
transcriber.py - Aliyun Bailian Paraformer-v2 transcription adapter.

This module intentionally avoids any internal service dependency. It uses the
Aliyun DashScope/Bailian API and reads the API key from one of these env vars:

    ALIYUN_API_KEY
    DASHSCOPE_API_KEY

The public video-analyze CLI treats ASR failures as non-fatal, so missing keys
still allow keyframe extraction to work.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows (PowerShell defaults to system encoding)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

MODEL = "paraformer-v2"
UPLOAD_POLICY_URL = "https://dashscope.aliyuncs.com/api/v1/uploads"
TRANSCRIPTION_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"
TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks"
POLL_INTERVAL_SECONDS = 3
MAX_POLLS = 100
LANGUAGE_HINTS = {"zh", "en", "ja", "ko", "de", "fr", "ru", "es"}


def get_api_key() -> str:
    """Return Aliyun Bailian/DashScope API key from environment."""
    api_key = os.environ.get("ALIYUN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Aliyun API key not found. Set ALIYUN_API_KEY or DASHSCOPE_API_KEY. "
            "You can still use frame extraction without ASR."
        )
    return api_key


def _request_json(url: str, *, api_key: str | None = None, method: str = "GET", payload: dict | None = None, headers: dict | None = None, timeout: int = 60) -> dict:
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    if api_key:
        request_headers.setdefault("Authorization", f"Bearer {api_key}")

    req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def get_upload_policy(api_key: str) -> dict:
    query = urllib.parse.urlencode({"action": "getPolicy", "model": MODEL})
    payload = _request_json(f"{UPLOAD_POLICY_URL}?{query}", api_key=api_key)
    data = payload.get("data")
    if not data:
        raise RuntimeError(f"Failed to get Aliyun upload policy: {payload.get('message') or payload}")
    return data


def _build_multipart_body(fields: dict[str, str], file_field: str, file_path: str) -> tuple[bytes, str]:
    boundary = f"----mpau-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")

    filename = Path(file_path).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    chunks.append(f"--{boundary}\r\n".encode("utf-8"))
    chunks.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("utf-8")
    )
    chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    with open(file_path, "rb") as file_obj:
        chunks.append(file_obj.read())
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))

    return b"".join(chunks), boundary


def upload_file_to_oss(api_key: str, file_path: str) -> str:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    policy = get_upload_policy(api_key)
    filename = Path(file_path).name
    object_key = f"{policy['upload_dir']}/{filename}"
    fields = {
        "OSSAccessKeyId": policy["oss_access_key_id"],
        "Signature": policy["signature"],
        "policy": policy["policy"],
        "x-oss-object-acl": policy["x_oss_object_acl"],
        "x-oss-forbid-overwrite": policy["x_oss_forbid_overwrite"],
        "key": object_key,
        "success_action_status": "200",
    }
    body, boundary = _build_multipart_body(fields, "file", file_path)
    req = urllib.request.Request(
        policy["upload_host"],
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Upload failed: HTTP {resp.status}")
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Upload failed: HTTP {exc.code}: {body_text}") from exc

    return f"oss://{object_key}"


def _language_hints(language: str | None) -> list[str]:
    if not language or language.lower() in {"auto", "none"}:
        return ["zh", "en"]
    normalized = language.lower().replace("_", "-").split("-", 1)[0]
    if normalized in LANGUAGE_HINTS:
        return [normalized]
    return ["zh", "en"]


def submit_transcription_task(api_key: str, oss_url: str, language: str | None = None) -> str:
    payload = {
        "model": MODEL,
        "input": {"file_urls": [oss_url]},
        "parameters": {"language_hints": _language_hints(language)},
    }
    result = _request_json(
        TRANSCRIPTION_URL,
        api_key=api_key,
        method="POST",
        payload=payload,
        headers={
            "X-DashScope-Async": "enable",
            "X-DashScope-OssResourceResolve": "enable",
        },
    )
    task_id = result.get("output", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"Failed to submit Aliyun ASR task: {result.get('message') or result}")
    return task_id


def get_task_result(api_key: str, task_id: str) -> dict:
    return _request_json(f"{TASK_URL}/{task_id}", api_key=api_key)


def fetch_transcript_text(transcription_url: str) -> str:
    try:
        with urllib.request.urlopen(transcription_url, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Failed to fetch transcription result: HTTP {exc.code}: {body}") from exc

    transcripts = payload.get("transcripts") or []
    return "\n".join(item.get("text", "") for item in transcripts if item.get("text"))


def poll_transcription(api_key: str, task_id: str) -> str:
    for _ in range(MAX_POLLS):
        time.sleep(POLL_INTERVAL_SECONDS)
        result = get_task_result(api_key, task_id)
        output = result.get("output") or {}
        status = output.get("task_status")

        if status == "SUCCEEDED":
            results = output.get("results") or []
            if not results:
                return ""
            texts = [fetch_transcript_text(item["transcription_url"]) for item in results if item.get("transcription_url")]
            return "\n".join(text for text in texts if text)

        if status == "FAILED":
            raise RuntimeError(f"Aliyun ASR task failed: {json.dumps(output, ensure_ascii=False)}")

    raise TimeoutError("Aliyun ASR task timed out")


def transcribe_file(file_path: str, language: str = "zh") -> str:
    """Transcribe audio/video file through Aliyun Bailian Paraformer-v2."""
    api_key = get_api_key()
    oss_url = upload_file_to_oss(api_key, file_path)
    task_id = submit_transcription_task(api_key, oss_url, language)
    return poll_transcription(api_key, task_id)


# ─── Find tool for extractor.py ──────────────────────────
def find_tool(name: str) -> str | None:
    """Find a tool binary: first try PATH, then scan common install locations."""
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA", "")
        try:
            winget_pkgs = Path(local_app) / "Microsoft" / "WinGet" / "Packages"
            if winget_pkgs.exists():
                for pkg_dir in winget_pkgs.iterdir():
                    for match in pkg_dir.rglob(f"{name}.exe"):
                        bin_dir = str(match.parent)
                        if bin_dir not in os.environ.get("PATH", ""):
                            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
                        return str(match)
        except Exception:
            pass
        try:
            scripts = os.path.join(os.path.dirname(sys.executable), "Scripts", f"{name}.exe")
            if os.path.exists(scripts):
                return scripts
        except Exception:
            pass
        return None

    for candidate_dir in ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
        candidate = os.path.join(candidate_dir, name)
        if os.path.isfile(candidate):
            if candidate_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = candidate_dir + os.pathsep + os.environ.get("PATH", "")
            return candidate
    return None


# ─── Adapter for video-analyzer ──────────────────────────
def transcribe_video(video_path: str, language: str = "zh") -> str:
    """Adapter used by analyzer_cli.py."""
    return transcribe_file(video_path, language)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe audio/video via Aliyun Bailian Paraformer-v2")
    parser.add_argument("file", help="Audio/video file path")
    parser.add_argument("--language", default="zh", help="Language hint, e.g. zh/en/auto (default: zh)")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    try:
        print(transcribe_file(args.file, args.language))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
