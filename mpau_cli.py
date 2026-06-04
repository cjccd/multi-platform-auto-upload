from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from conf import BASE_DIR
from uploader.bilibili_uploader.runtime import run_biliup_command
from uploader.douyin_uploader.main import (
    DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
    DOUYIN_PUBLISH_STRATEGY_SCHEDULED,
    DouYinNote,
    DouYinVideo,
    cookie_auth as douyin_cookie_auth,
    douyin_setup,
)
from uploader.ks_uploader.main import (
    KUAISHOU_PUBLISH_STRATEGY_IMMEDIATE,
    KUAISHOU_PUBLISH_STRATEGY_SCHEDULED,
    KSNote,
    KSVideo,
    cookie_auth as kuaishou_cookie_auth,
    ks_setup,
)
from uploader.pdd_uploader.main import (
    PDD_PUBLISH_STRATEGY_IMMEDIATE,
    PDD_PUBLISH_STRATEGY_SCHEDULED,
    PDDVideo,
    cookie_auth as pdd_cookie_auth,
    pdd_setup,
)
from uploader.tmall_uploader.main import (
    TMALL_PUBLISH_STRATEGY_IMMEDIATE,
    TMALL_PUBLISH_STRATEGY_SCHEDULED,
    TmallVideo,
    cookie_auth as tmall_cookie_auth,
    tmall_setup,
)
from uploader.jd_uploader.main import (
    JD_PUBLISH_STRATEGY_IMMEDIATE,
    JD_PUBLISH_STRATEGY_SCHEDULED,
    JDVideo,
    cookie_auth as jd_cookie_auth,
    jd_setup,
)
from uploader.tencent_uploader.main import (
    TENCENT_PUBLISH_STRATEGY_IMMEDIATE,
    TENCENT_PUBLISH_STRATEGY_SCHEDULED,
    TencentVideo,
    cookie_auth as tencent_cookie_auth,
    tencent_setup,
)
from uploader.xiaohongshu_uploader.main import (
    XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
    XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
    XiaoHongShuNote,
    XiaoHongShuVideo,
    cookie_auth as xiaohongshu_cookie_auth,
    xiaohongshu_setup,
)

SCHEDULE_FORMAT = "%Y-%m-%d %H:%M"

@dataclass(slots=True)
class DouyinVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    description: str
    tags: list[str]
    publish_date: datetime | int
    thumbnail_file: Path | None = None
    thumbnail_landscape_file: Path | None = None
    thumbnail_portrait_file: Path | None = None
    product_link: str = ""
    product_title: str = ""
    publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE
    debug: bool = True
    headless: bool = True
    dry_run: bool = False

@dataclass(slots=True)
class DouyinNoteUploadRequest:
    account_name: str
    image_files: list[Path]
    title: str
    note: str
    tags: list[str]
    publish_date: datetime | int
    publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE
    debug: bool = True
    headless: bool = True

@dataclass(slots=True)
class KuaishouVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    description: str
    tags: list[str]
    publish_date: datetime | int
    thumbnail_file: Path | None = None
    publish_strategy: str = KUAISHOU_PUBLISH_STRATEGY_IMMEDIATE
    debug: bool = True
    headless: bool = True

@dataclass(slots=True)
class KuaishouNoteUploadRequest:
    account_name: str
    image_files: list[Path]
    title: str
    note: str
    tags: list[str]
    publish_date: datetime | int
    publish_strategy: str = KUAISHOU_PUBLISH_STRATEGY_IMMEDIATE
    debug: bool = True
    headless: bool = True

@dataclass(slots=True)
class XiaohongshuVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    description: str
    tags: list[str]
    publish_date: datetime | int
    thumbnail_file: Path | None = None
    publish_strategy: str = XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE
    debug: bool = True
    headless: bool = True

@dataclass(slots=True)
class XiaohongshuNoteUploadRequest:
    account_name: str
    image_files: list[Path]
    title: str
    note: str
    tags: list[str]
    publish_date: datetime | int
    publish_strategy: str = XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE
    debug: bool = True
    headless: bool = True

@dataclass(slots=True)
class BilibiliVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    description: str
    tid: int
    tags: list[str]
    publish_date: datetime | int

@dataclass(slots=True)
class BaijiahaoVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    tags: list[str]
    publish_date: datetime | int

@dataclass(slots=True)
class TiktokVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    tags: list[str]
    publish_date: datetime | int
    thumbnail_file: Path | None = None

@dataclass(slots=True)
class PddVideoUploadRequest:
    account_name: str
    video_file: Path
    description: str
    tags: list[str]
    publish_date: datetime | int
    goods_id: str = ""
    publish_strategy: str = PDD_PUBLISH_STRATEGY_IMMEDIATE
    debug: bool = True
    headless: bool = True
    dry_run: bool = False

@dataclass(slots=True)
class TmallVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    description: str
    tags: list[str]
    goods_id: str = ""
    activity_topic: str = ""
    schedule: datetime | None = None
    publish_strategy: str = TMALL_PUBLISH_STRATEGY_IMMEDIATE
    debug: bool = True
    headless: bool = True
    dry_run: bool = False

@dataclass(slots=True)
class JdVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    goods_id: str = ""
    schedule: datetime | None = None
    original: bool = False
    debug: bool = True
    headless: bool = True
    dry_run: bool = False
    keep_browser: bool = False

@dataclass(slots=True)
class TencentVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    description: str
    tags: list[str]
    publish_date: datetime | int
    thumbnail_file: Path | None = None
    short_title: str | None = None
    category: str | None = None
    goods_id: str = ""
    is_draft: bool = False
    publish_strategy: str = TENCENT_PUBLISH_STRATEGY_IMMEDIATE
    debug: bool = True
    headless: bool = True

def has_interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()

def resolve_runtime_home() -> Path:
    return Path(BASE_DIR)

def resolve_account_file(platform: str, account_name: str) -> Path:
    account_file = resolve_runtime_home() / "cookies" / f"{platform}_{account_name}.json"
    account_file.parent.mkdir(exist_ok=True)
    return account_file

def parse_tags(raw_tags: str | None) -> list[str]:
    if not raw_tags:
        return []

    tags: list[str] = []
    for item in raw_tags.split(","):
        cleaned = item.strip().lstrip("#")
        if cleaned:
            tags.append(cleaned)
    return tags

def parse_image_files(raw_files: Iterable[Path]) -> list[Path]:
    return [Path(file) for file in raw_files]

def parse_schedule(raw_schedule: str | None) -> datetime | int:
    if not raw_schedule:
        return 0
    return datetime.strptime(raw_schedule, SCHEDULE_FORMAT)

async def login_douyin_account(account_name: str, headless: bool = True) -> dict:
    account_file = resolve_account_file("douyin", account_name)
    return await douyin_setup(str(account_file), handle=True, return_detail=True, headless=headless)

async def check_douyin_account(account_name: str) -> bool:
    account_file = resolve_account_file("douyin", account_name)
    if not account_file.exists():
        return False
    return await douyin_cookie_auth(str(account_file))

async def login_kuaishou_account(account_name: str, headless: bool = True) -> dict:
    account_file = resolve_account_file("kuaishou", account_name)
    return await ks_setup(str(account_file), handle=True, return_detail=True, headless=headless)

async def check_kuaishou_account(account_name: str) -> bool:
    account_file = resolve_account_file("kuaishou", account_name)
    if not account_file.exists():
        return False
    return await kuaishou_cookie_auth(str(account_file))

async def login_xiaohongshu_account(account_name: str, headless: bool = True) -> dict:
    account_file = resolve_account_file("xiaohongshu", account_name)
    return await xiaohongshu_setup(str(account_file), handle=True, return_detail=True, headless=headless)

async def check_xiaohongshu_account(account_name: str) -> bool:
    account_file = resolve_account_file("xiaohongshu", account_name)
    if not account_file.exists():
        return False
    return await xiaohongshu_cookie_auth(str(account_file))

async def login_bilibili_account(account_name: str) -> dict:
    account_file = resolve_account_file("bilibili", account_name)
    if not has_interactive_terminal():
        return {
            "success": False,
            "message": (
                "Bilibili login requires a local interactive terminal. "
                f"Please run `mpau bilibili login --account {account_name}` yourself in a local terminal. "
                "If the terminal QR code does not render completely, open `./qrcode.png` and scan that image."
            ),
            "account_file": str(account_file),
        }

    result = run_biliup_command(["-u", str(account_file), "login"], interactive=True)
    success = result.returncode == 0
    return {
        "success": success,
        "message": (result.stderr or result.stdout or "").strip() or "Bilibili login completed" if success else (result.stderr or result.stdout or "").strip() or "Bilibili login failed",
        "account_file": str(account_file),
    }

async def check_bilibili_account(account_name: str) -> bool:
    account_file = resolve_account_file("bilibili", account_name)
    if not account_file.exists():
        return False
    result = run_biliup_command(["-u", str(account_file), "renew"])
    return result.returncode == 0

async def login_baijiahao_account(account_name: str) -> dict:
    from uploader.baijiahao_uploader.main import baijiahao_setup

    account_file = resolve_account_file("baijiahao", account_name)
    success = await baijiahao_setup(str(account_file), handle=True)
    return {
        "success": bool(success),
        "message": "Baijiahao login completed" if success else "Baijiahao login failed",
        "account_file": str(account_file),
    }

async def check_baijiahao_account(account_name: str) -> bool:
    from uploader.baijiahao_uploader.main import cookie_auth as baijiahao_cookie_auth

    account_file = resolve_account_file("baijiahao", account_name)
    if not account_file.exists():
        return False
    return await baijiahao_cookie_auth(str(account_file))

async def login_tiktok_account(account_name: str) -> dict:
    from uploader.tk_uploader.main_chrome import tiktok_setup

    account_file = resolve_account_file("tiktok", account_name)
    success = await tiktok_setup(str(account_file), handle=True)
    return {
        "success": bool(success),
        "message": "TikTok login completed" if success else "TikTok login failed",
        "account_file": str(account_file),
    }

async def check_tiktok_account(account_name: str) -> bool:
    from uploader.tk_uploader.main_chrome import cookie_auth as tiktok_cookie_auth

    account_file = resolve_account_file("tiktok", account_name)
    if not account_file.exists():
        return False
    return await tiktok_cookie_auth(str(account_file))

async def login_pdd_account(account_name: str, headless: bool = True) -> dict:
    account_file = resolve_account_file("pdd", account_name)
    return await pdd_setup(str(account_file), handle=True, return_detail=True, headless=headless)

async def check_pdd_account(account_name: str) -> bool:
    account_file = resolve_account_file("pdd", account_name)
    if not account_file.exists():
        return False
    return await pdd_cookie_auth(str(account_file))

async def login_tmall_account(account_name: str, headless: bool = True) -> dict:
    account_file = resolve_account_file("tmall", account_name)
    return await tmall_setup(str(account_file), handle=True, return_detail=True, headless=headless)

async def check_tmall_account(account_name: str) -> bool:
    account_file = resolve_account_file("tmall", account_name)
    if not account_file.exists():
        return False
    return await tmall_cookie_auth(str(account_file))

async def login_jd_account(account_name: str, headless: bool = True) -> dict:
    account_file = resolve_account_file("jd", account_name)
    return await jd_setup(str(account_file), handle=True, return_detail=True, headless=headless)

async def check_jd_account(account_name: str) -> bool:
    account_file = resolve_account_file("jd", account_name)
    if not account_file.exists():
        return False
    return await jd_cookie_auth(str(account_file))

async def upload_jd_video(request: JdVideoUploadRequest) -> Path:
    account_file = resolve_account_file("jd", request.account_name)
    is_ready = await jd_setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"JD cookie is missing or expired: {account_file}. Run `mpau jd login --account {request.account_name}` first."
        )

    app = JDVideo(
        file_path=str(request.video_file),
        title=request.title,
        account_file=str(account_file),
        goods_id=request.goods_id,
        schedule=request.schedule,
        original=request.original,
        debug=request.debug,
        headless=request.headless,
        dry_run=request.dry_run,
        keep_browser=request.keep_browser,
    )
    await app.main()
    return account_file

async def login_tencent_account(account_name: str, headless: bool = True) -> dict:
    account_file = resolve_account_file("tencent", account_name)
    return await tencent_setup(str(account_file), handle=True, return_detail=True, headless=headless)

async def check_tencent_account(account_name: str) -> bool:
    account_file = resolve_account_file("tencent", account_name)
    if not account_file.exists():
        return False
    return await tencent_cookie_auth(str(account_file))

async def upload_pdd_video(request: PddVideoUploadRequest) -> Path:
    account_file = resolve_account_file("pdd", request.account_name)
    is_ready = await pdd_setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"PDD cookie is missing or expired: {account_file}. Run `mpau pdd login --account {request.account_name}` first."
        )

    app = PDDVideo(
        file_path=str(request.video_file),
        tags=request.tags,
        publish_date=request.publish_date,
        account_file=str(account_file),
        desc=request.description,
        goods_id=request.goods_id,
        publish_strategy=request.publish_strategy,
        debug=request.debug,
        headless=request.headless,
        dry_run=request.dry_run,
    )
    await app.main()
    return account_file

async def upload_kuaishou_video(request: KuaishouVideoUploadRequest) -> Path:
    account_file = resolve_account_file("kuaishou", request.account_name)
    is_ready = await ks_setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"Kuaishou cookie is missing or expired: {account_file}. Run `mpau kuaishou login --account {request.account_name}` first."
        )

    app = KSVideo(
        title=request.title,
        file_path=str(request.video_file),
        desc=request.description,
        tags=request.tags,
        publish_date=request.publish_date,
        account_file=str(account_file),
        thumbnail_path=str(request.thumbnail_file) if request.thumbnail_file else None,
        publish_strategy=request.publish_strategy,
        debug=request.debug,
        headless=request.headless,
    )
    await app.main()
    return account_file

async def upload_kuaishou_note(request: KuaishouNoteUploadRequest) -> Path:
    account_file = resolve_account_file("kuaishou", request.account_name)
    is_ready = await ks_setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"Kuaishou cookie is missing or expired: {account_file}. Run `mpau kuaishou login --account {request.account_name}` first."
        )

    app = KSNote(
        image_paths=[str(path) for path in request.image_files],
        title=request.title,
        note=request.note,
        tags=request.tags,
        publish_date=request.publish_date,
        account_file=str(account_file),
        publish_strategy=request.publish_strategy,
        debug=request.debug,
        headless=request.headless,
    )
    await app.main()
    return account_file

async def upload_xiaohongshu_video(request: XiaohongshuVideoUploadRequest) -> Path:
    account_file = resolve_account_file("xiaohongshu", request.account_name)
    is_ready = await xiaohongshu_setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"Xiaohongshu cookie is missing or expired: {account_file}. Run `mpau xiaohongshu login --account {request.account_name}` first."
        )

    app = XiaoHongShuVideo(
        title=request.title,
        file_path=str(request.video_file),
        desc=request.description,
        tags=request.tags,
        publish_date=request.publish_date,
        account_file=str(account_file),
        thumbnail_path=str(request.thumbnail_file) if request.thumbnail_file else None,
        publish_strategy=request.publish_strategy,
        debug=request.debug,
        headless=request.headless,
    )
    await app.main()
    return account_file

async def upload_xiaohongshu_note(request: XiaohongshuNoteUploadRequest) -> Path:
    account_file = resolve_account_file("xiaohongshu", request.account_name)
    is_ready = await xiaohongshu_setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"Xiaohongshu cookie is missing or expired: {account_file}. Run `mpau xiaohongshu login --account {request.account_name}` first."
        )

    app = XiaoHongShuNote(
        image_paths=[str(path) for path in request.image_files],
        title=request.title,
        note=request.note,
        desc=request.note,
        tags=request.tags,
        publish_date=request.publish_date,
        account_file=str(account_file),
        publish_strategy=request.publish_strategy,
        debug=request.debug,
        headless=request.headless,
    )
    await app.main()
    return account_file

async def upload_bilibili_video(request: BilibiliVideoUploadRequest) -> Path:
    account_file = resolve_account_file("bilibili", request.account_name)
    if not account_file.exists():
        raise RuntimeError(
            f"Bilibili account file is missing: {account_file}. Run `mpau bilibili login --account {request.account_name}` first."
        )

    arguments = [
        "-u",
        str(account_file),
        "upload",
        str(request.video_file),
        "--title",
        request.title,
        "--desc",
        request.description,
        "--tid",
        str(request.tid),
    ]
    if request.tags:
        arguments.extend(["--tag", ",".join(request.tags)])
    if isinstance(request.publish_date, datetime):
        arguments.extend(["--dtime", str(int(request.publish_date.timestamp()))])

    result = run_biliup_command(arguments)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "").strip() or "Bilibili upload failed")
    return account_file

async def upload_baijiahao_video(request: BaijiahaoVideoUploadRequest) -> Path:
    from uploader.baijiahao_uploader.main import BaiJiaHaoVideo, baijiahao_setup

    account_file = resolve_account_file("baijiahao", request.account_name)
    is_ready = await baijiahao_setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"Baijiahao cookie is missing or expired: {account_file}. Run `mpau baijiahao login --account {request.account_name}` first."
        )

    app = BaiJiaHaoVideo(
        request.title,
        str(request.video_file),
        request.tags,
        request.publish_date,
        str(account_file),
    )
    await app.main()
    return account_file

async def upload_tiktok_video(request: TiktokVideoUploadRequest) -> Path:
    from uploader.tk_uploader.main_chrome import TiktokVideo, tiktok_setup

    account_file = resolve_account_file("tiktok", request.account_name)
    is_ready = await tiktok_setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"TikTok cookie is missing or expired: {account_file}. Run `mpau tiktok login --account {request.account_name}` first."
        )

    app = TiktokVideo(
        request.title,
        str(request.video_file),
        request.tags,
        request.publish_date,
        str(account_file),
        str(request.thumbnail_file) if request.thumbnail_file else None,
    )
    await app.main()
    return account_file

async def upload_tmall_video(request: TmallVideoUploadRequest) -> Path:
    account_file = resolve_account_file("tmall", request.account_name)
    is_ready = await tmall_setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"Tmall cookie is missing or expired: {account_file}. Run `mpau tmall login --account {request.account_name}` first."
        )

    app = TmallVideo(
        file_path=str(request.video_file),
        title=request.title,
        desc=request.description,
        account_file=str(account_file),
        tags=request.tags,
        goods_id=request.goods_id,
        activity_topic=request.activity_topic,
        schedule=request.schedule,
        publish_strategy=request.publish_strategy,
        debug=request.debug,
        headless=request.headless,
        dry_run=request.dry_run,
    )
    await app.main()
    return account_file

async def upload_tencent_video(request: TencentVideoUploadRequest) -> Path:
    account_file = resolve_account_file("tencent", request.account_name)
    is_ready = await tencent_setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"Tencent cookie is missing or expired: {account_file}. Run `mpau tencent login --account {request.account_name}` first."
        )

    app = TencentVideo(
        title=request.title,
        file_path=str(request.video_file),
        tags=request.tags,
        publish_date=request.publish_date,
        account_file=str(account_file),
        category=request.category,
        is_draft=request.is_draft,
        desc=request.description,
        thumbnail_path=str(request.thumbnail_file) if request.thumbnail_file else None,
        short_title=request.short_title,
        goods_id=request.goods_id or None,
        publish_strategy=request.publish_strategy,
        debug=request.debug,
        headless=request.headless,
    )
    await app.main()
    return account_file

async def upload_video(request: DouyinVideoUploadRequest) -> Path:
    account_file = resolve_account_file("douyin", request.account_name)
    is_ready = await douyin_setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"Douyin cookie is missing or expired: {account_file}. Run `mpau douyin login --account {request.account_name}` first."
        )

    app = DouYinVideo(
        request.title,
        str(request.video_file),
        request.tags,
        request.publish_date,
        str(account_file),
        desc=request.description,
        thumbnail_landscape_path=(
            str(request.thumbnail_landscape_file) if request.thumbnail_landscape_file else None
        ),
        thumbnail_portrait_path=str(
            request.thumbnail_portrait_file or request.thumbnail_file
        ) if request.thumbnail_portrait_file or request.thumbnail_file else None,
        productLink=request.product_link,
        productTitle=request.product_title,
        publish_strategy=request.publish_strategy,
        debug=request.debug,
        headless=request.headless,
        dry_run=request.dry_run,
    )
    await app.douyin_upload_video()
    return account_file

async def upload_note(request: DouyinNoteUploadRequest) -> Path:
    account_file = resolve_account_file("douyin", request.account_name)
    is_ready = await douyin_setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"Douyin cookie is missing or expired: {account_file}. Run `mpau douyin login --account {request.account_name}` first."
        )

    app = DouYinNote(
        image_paths=[str(path) for path in request.image_files],
        title=request.title,
        note=request.note,
        tags=request.tags,
        publish_date=request.publish_date,
        account_file=str(account_file),
        publish_strategy=request.publish_strategy,
        debug=request.debug,
        headless=request.headless,
    )
    await app.douyin_upload_note()
    return account_file

def existing_file_path(value: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"File not found: {value}")
    return path

def schedule_value(value: str):
    try:
        return parse_schedule(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid schedule '{value}'. Expected format: {SCHEDULE_FORMAT}"
        ) from exc

def add_runtime_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    headless_group = parser.add_mutually_exclusive_group()
    headless_group.add_argument("--headed", dest="headless", action="store_false", help="Run with browser UI")
    headless_group.add_argument("--headless", dest="headless", action="store_true", help="Run in headless mode")
    parser.set_defaults(headless=False)

def build_parser() -> argparse.ArgumentParser:
    schedule_help = SCHEDULE_FORMAT.replace("%", "%%")
    parser = argparse.ArgumentParser(
        prog="mpau",
        description="CLI for multi-platform-auto-upload.",
    )
    platform_parsers = parser.add_subparsers(dest="platform", required=True)

    douyin_parser = platform_parsers.add_parser("douyin", help="Douyin operations")
    douyin_actions = douyin_parser.add_subparsers(dest="action", required=True)

    for action_name in ("login", "check"):
        action_parser = douyin_actions.add_parser(action_name, help=f"Douyin {action_name}")
        action_parser.add_argument("--account", required=True, help="Douyin user-defined account_name")
        if action_name == "login":
            add_runtime_flags(action_parser)

    upload_video_parser = douyin_actions.add_parser("upload-video", help="Upload one video to Douyin")
    upload_video_parser.add_argument("--account", required=True, help="Douyin user-defined account_name")
    upload_video_parser.add_argument("--file", required=True, type=existing_file_path, help="Video file path")
    upload_video_parser.add_argument("--title", required=True, help="Video title")
    upload_video_parser.add_argument("--desc", default="", help="Optional video description")
    upload_video_parser.add_argument("--tags", default="", help="Comma-separated tags, such as tag1,tag2")
    upload_video_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")
    upload_video_parser.add_argument("--thumbnail", type=existing_file_path, help="Optional thumbnail path")
    upload_video_parser.add_argument("--thumbnail-landscape", type=existing_file_path, help="Optional 4:3 landscape thumbnail path")
    upload_video_parser.add_argument("--thumbnail-portrait", type=existing_file_path, help="Optional 3:4 portrait thumbnail path")
    upload_video_parser.add_argument("--product-link", default="", help="Optional product link")
    upload_video_parser.add_argument("--product-title", default="", help="Optional product title")
    upload_video_parser.add_argument("--dry-run", action="store_true", help="Upload and fill fields but do not publish")
    add_runtime_flags(upload_video_parser)

    upload_note_parser = douyin_actions.add_parser("upload-note", help="Upload one note to Douyin")
    upload_note_parser.add_argument("--account", required=True, help="Douyin user-defined account_name")
    upload_note_parser.add_argument("--images", required=True, nargs="+", type=existing_file_path, help="Image file paths")
    upload_note_parser.add_argument("--title", required=True, help="Note title")
    upload_note_parser.add_argument("--note", default="", help="Optional note content")
    upload_note_parser.add_argument("--tags", default="", help="Comma-separated tags, such as tag1,tag2")
    upload_note_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")
    add_runtime_flags(upload_note_parser)

    verify_parser = douyin_actions.add_parser("verify", help="Submit SMS verification code for pending Douyin upload")
    verify_parser.add_argument("--account", required=True, help="Douyin user-defined account_name")
    verify_parser.add_argument("--code", required=True, help="6-digit SMS verification code")

    kuaishou_parser = platform_parsers.add_parser("kuaishou", help="Kuaishou operations")
    kuaishou_actions = kuaishou_parser.add_subparsers(dest="action", required=True)

    for action_name in ("login", "check"):
        action_parser = kuaishou_actions.add_parser(action_name, help=f"Kuaishou {action_name}")
        action_parser.add_argument("--account", required=True, help="Kuaishou user-defined account_name")
        if action_name == "login":
            add_runtime_flags(action_parser)

    kuaishou_upload_video_parser = kuaishou_actions.add_parser("upload-video", help="Upload one video to Kuaishou")
    kuaishou_upload_video_parser.add_argument("--account", required=True, help="Kuaishou user-defined account_name")
    kuaishou_upload_video_parser.add_argument("--file", required=True, type=existing_file_path, help="Video file path")
    kuaishou_upload_video_parser.add_argument("--title", required=True, help="Video title")
    kuaishou_upload_video_parser.add_argument("--desc", default="", help="Optional video description")
    kuaishou_upload_video_parser.add_argument("--tags", default="", help="Comma-separated tags, such as tag1,tag2")
    kuaishou_upload_video_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")
    kuaishou_upload_video_parser.add_argument("--thumbnail", type=existing_file_path, help="Optional thumbnail path")
    add_runtime_flags(kuaishou_upload_video_parser)

    kuaishou_upload_note_parser = kuaishou_actions.add_parser("upload-note", help="Upload one note to Kuaishou")
    kuaishou_upload_note_parser.add_argument("--account", required=True, help="Kuaishou user-defined account_name")
    kuaishou_upload_note_parser.add_argument("--images", required=True, nargs="+", type=existing_file_path, help="Image file paths")
    kuaishou_upload_note_parser.add_argument("--title", required=True, help="Note title")
    kuaishou_upload_note_parser.add_argument("--note", default="", help="Optional note content")
    kuaishou_upload_note_parser.add_argument("--tags", default="", help="Comma-separated tags, such as tag1,tag2")
    kuaishou_upload_note_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")
    add_runtime_flags(kuaishou_upload_note_parser)

    xiaohongshu_parser = platform_parsers.add_parser("xiaohongshu", help="Xiaohongshu operations")
    xiaohongshu_actions = xiaohongshu_parser.add_subparsers(dest="action", required=True)

    for action_name in ("login", "check"):
        action_parser = xiaohongshu_actions.add_parser(action_name, help=f"Xiaohongshu {action_name}")
        action_parser.add_argument("--account", required=True, help="Xiaohongshu user-defined account_name")
        if action_name == "login":
            add_runtime_flags(action_parser)

    xiaohongshu_upload_video_parser = xiaohongshu_actions.add_parser("upload-video", help="Upload one video to Xiaohongshu")
    xiaohongshu_upload_video_parser.add_argument("--account", required=True, help="Xiaohongshu user-defined account_name")
    xiaohongshu_upload_video_parser.add_argument("--file", required=True, type=existing_file_path, help="Video file path")
    xiaohongshu_upload_video_parser.add_argument("--title", required=True, help="Video title")
    xiaohongshu_upload_video_parser.add_argument("--desc", default="", help="Optional video description")
    xiaohongshu_upload_video_parser.add_argument("--tags", default="", help="Comma-separated tags, such as tag1,tag2")
    xiaohongshu_upload_video_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")
    xiaohongshu_upload_video_parser.add_argument("--thumbnail", type=existing_file_path, help="Optional thumbnail path")
    add_runtime_flags(xiaohongshu_upload_video_parser)

    xiaohongshu_upload_note_parser = xiaohongshu_actions.add_parser("upload-note", help="Upload one note to Xiaohongshu")
    xiaohongshu_upload_note_parser.add_argument("--account", required=True, help="Xiaohongshu user-defined account_name")
    xiaohongshu_upload_note_parser.add_argument("--images", required=True, nargs="+", type=existing_file_path, help="Image file paths")
    xiaohongshu_upload_note_parser.add_argument("--title", required=True, help="Note title")
    xiaohongshu_upload_note_parser.add_argument("--note", default="", help="Optional note content")
    xiaohongshu_upload_note_parser.add_argument("--tags", default="", help="Comma-separated tags, such as tag1,tag2")
    xiaohongshu_upload_note_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")
    add_runtime_flags(xiaohongshu_upload_note_parser)

    bilibili_parser = platform_parsers.add_parser("bilibili", help="Bilibili operations")
    bilibili_actions = bilibili_parser.add_subparsers(dest="action", required=True)

    for action_name in ("login", "check"):
        action_parser = bilibili_actions.add_parser(action_name, help=f"Bilibili {action_name}")
        action_parser.add_argument("--account", required=True, help="Bilibili user-defined account_name")

    bilibili_upload_video_parser = bilibili_actions.add_parser("upload-video", help="Upload one video to Bilibili")
    bilibili_upload_video_parser.add_argument("--account", required=True, help="Bilibili user-defined account_name")
    bilibili_upload_video_parser.add_argument("--file", required=True, type=existing_file_path, help="Video file path")
    bilibili_upload_video_parser.add_argument("--title", required=True, help="Video title")
    bilibili_upload_video_parser.add_argument("--desc", required=True, help="Video description")
    bilibili_upload_video_parser.add_argument("--tid", required=True, type=int, help="Bilibili category id")
    bilibili_upload_video_parser.add_argument("--tags", default="", help="Comma-separated tags, such as tag1,tag2")
    bilibili_upload_video_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")

    baijiahao_parser = platform_parsers.add_parser("baijiahao", help="Baijiahao operations")
    baijiahao_actions = baijiahao_parser.add_subparsers(dest="action", required=True)

    for action_name in ("login", "check"):
        action_parser = baijiahao_actions.add_parser(action_name, help=f"Baijiahao {action_name}")
        action_parser.add_argument("--account", required=True, help="Baijiahao user-defined account_name")

    baijiahao_upload_video_parser = baijiahao_actions.add_parser("upload-video", help="Upload one video to Baijiahao")
    baijiahao_upload_video_parser.add_argument("--account", required=True, help="Baijiahao user-defined account_name")
    baijiahao_upload_video_parser.add_argument("--file", required=True, type=existing_file_path, help="Video file path")
    baijiahao_upload_video_parser.add_argument("--title", required=True, help="Video title")
    baijiahao_upload_video_parser.add_argument("--tags", default="", help="Comma-separated tags, such as tag1,tag2")
    baijiahao_upload_video_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")

    tiktok_parser = platform_parsers.add_parser("tiktok", help="TikTok operations")
    tiktok_actions = tiktok_parser.add_subparsers(dest="action", required=True)

    for action_name in ("login", "check"):
        action_parser = tiktok_actions.add_parser(action_name, help=f"TikTok {action_name}")
        action_parser.add_argument("--account", required=True, help="TikTok user-defined account_name")

    tiktok_upload_video_parser = tiktok_actions.add_parser("upload-video", help="Upload one video to TikTok")
    tiktok_upload_video_parser.add_argument("--account", required=True, help="TikTok user-defined account_name")
    tiktok_upload_video_parser.add_argument("--file", required=True, type=existing_file_path, help="Video file path")
    tiktok_upload_video_parser.add_argument("--title", required=True, help="Video title")
    tiktok_upload_video_parser.add_argument("--tags", default="", help="Comma-separated tags, such as tag1,tag2")
    tiktok_upload_video_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")
    tiktok_upload_video_parser.add_argument("--thumbnail", type=existing_file_path, help="Optional thumbnail path")

    pdd_parser = platform_parsers.add_parser("pdd", help="Pinduoduo (Duoduo Video) operations")
    pdd_actions = pdd_parser.add_subparsers(dest="action", required=True)

    for action_name in ("login", "check"):
        action_parser = pdd_actions.add_parser(action_name, help=f"PDD {action_name}")
        action_parser.add_argument("--account", required=True, help="PDD user-defined account_name")
        if action_name == "login":
            add_runtime_flags(action_parser)

    pdd_upload_video_parser = pdd_actions.add_parser("upload-video", help="Upload one video to Pinduoduo (Duoduo Video)")
    pdd_upload_video_parser.add_argument("--account", required=True, help="PDD user-defined account_name")
    pdd_upload_video_parser.add_argument("--file", required=True, type=existing_file_path, help="Video file path")
    pdd_upload_video_parser.add_argument("--desc", required=True, help="Video description")
    pdd_upload_video_parser.add_argument("--tags", default="", help="Comma-separated tags, such as tag1,tag2")
    pdd_upload_video_parser.add_argument("--goods-id", default="", help="Pinduoduo goods ID to attach to the video")
    pdd_upload_video_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")
    pdd_upload_video_parser.add_argument("--dry-run", action="store_true", help="Set everything up but do not actually publish")
    add_runtime_flags(pdd_upload_video_parser)

    tmall_parser = platform_parsers.add_parser("tmall", help="Tmall/Taobao Guanghe operations")
    tmall_actions = tmall_parser.add_subparsers(dest="action", required=True)

    for action_name in ("login", "check"):
        action_parser = tmall_actions.add_parser(action_name, help=f"Tmall {action_name}")
        action_parser.add_argument("--account", required=True, help="Tmall user-defined account_name")
        if action_name == "login":
            add_runtime_flags(action_parser)

    tmall_upload_video_parser = tmall_actions.add_parser("upload-video", help="Upload one video to Taobao/Tmall Guanghe")
    tmall_upload_video_parser.add_argument("--account", required=True, help="Tmall user-defined account_name")
    tmall_upload_video_parser.add_argument("--file", required=True, type=existing_file_path, help="Video file path")
    tmall_upload_video_parser.add_argument("--title", required=True, help="Video title, max 30 characters")
    tmall_upload_video_parser.add_argument("--desc", default="", help="Optional video description, max 1000 characters")
    tmall_upload_video_parser.add_argument("--tags", default="", help="Comma-separated topics; they are appended to description with # prefix")
    tmall_upload_video_parser.add_argument("--goods-id", default="", help="Taobao/Tmall goods ID to attach to the video")
    tmall_upload_video_parser.add_argument("--activity-topic", default="", help="Activity topic keyword: empty=auto-pick platform recommendation, keyword=search and pick first result")
    tmall_upload_video_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")
    tmall_upload_video_parser.add_argument("--dry-run", action="store_true", help="Upload and fill fields but do not publish")
    add_runtime_flags(tmall_upload_video_parser)

    jd_parser = platform_parsers.add_parser("jd", help="JD Jingmai (京东京麦) operations")
    jd_actions = jd_parser.add_subparsers(dest="action", required=True)

    for action_name in ("login", "check"):
        action_parser = jd_actions.add_parser(action_name, help=f"JD {action_name}")
        action_parser.add_argument("--account", required=True, help="JD user-defined account_name")
        if action_name == "login":
            add_runtime_flags(action_parser)

    jd_upload_video_parser = jd_actions.add_parser("upload-video", help="Upload one video to JD Jingmai (逛-视频)")
    jd_upload_video_parser.add_argument("--account", required=True, help="JD user-defined account_name")
    jd_upload_video_parser.add_argument("--file", required=True, type=existing_file_path, help="Video file path (.mp4/.mov/.mkv)")
    jd_upload_video_parser.add_argument("--title", required=True, help="Video title, 5-27 characters")
    jd_upload_video_parser.add_argument("--goods-id", default="", help="JD goods ID (numeric, searched via 站内搜索 tab)")
    jd_upload_video_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")
    jd_upload_video_parser.add_argument("--original", action="store_true", help="Mark as original content (自主原创). Fails if account does not have the feature enabled")
    jd_upload_video_parser.add_argument("--dry-run", action="store_true", help="Set up everything but skip the publish button")
    jd_upload_video_parser.add_argument("--keep-browser", action="store_true", help="Keep browser open after publish (sleep 24h); useful for inspection")
    add_runtime_flags(jd_upload_video_parser)

    tencent_parser = platform_parsers.add_parser("tencent", help="Tencent WeChat Channel (视频号) operations")
    tencent_actions = tencent_parser.add_subparsers(dest="action", required=True)

    for action_name in ("login", "check"):
        action_parser = tencent_actions.add_parser(action_name, help=f"Tencent {action_name}")
        action_parser.add_argument("--account", required=True, help="Tencent user-defined account_name")
        if action_name == "login":
            add_runtime_flags(action_parser)

    tencent_upload_video_parser = tencent_actions.add_parser("upload-video", help="Upload one video to WeChat Channel (视频号)")
    tencent_upload_video_parser.add_argument("--account", required=True, help="Tencent user-defined account_name")
    tencent_upload_video_parser.add_argument("--file", required=True, type=existing_file_path, help="Video file path")
    tencent_upload_video_parser.add_argument("--title", required=True, help="Video title")
    tencent_upload_video_parser.add_argument("--desc", default="", help="Optional video description")
    tencent_upload_video_parser.add_argument("--tags", default="", help="Comma-separated tags, such as tag1,tag2")
    tencent_upload_video_parser.add_argument("--schedule", type=schedule_value, help=f"Schedule time in {schedule_help}")
    tencent_upload_video_parser.add_argument("--thumbnail", type=existing_file_path, help="Optional thumbnail path")
    tencent_upload_video_parser.add_argument("--short-title", default=None, help="Optional short title (max 16 chars)")
    tencent_upload_video_parser.add_argument("--category", default=None, help="Optional original content category")
    tencent_upload_video_parser.add_argument("--goods-id", default="", help="WeChat shop goods ID to attach as a product link")
    tencent_upload_video_parser.add_argument("--draft", dest="is_draft", action="store_true", help="Save as draft instead of publishing")
    add_runtime_flags(tencent_upload_video_parser)

    return parser

async def dispatch(args: argparse.Namespace) -> int:
    if args.platform == "douyin":
        if args.action == "login":
            result = await login_douyin_account(args.account, headless=args.headless)
            if not result["success"]:
                raise RuntimeError(result["message"])
            print(f"Douyin login flow completed: {result['account_file']}")
            return 0

        if args.action == "check":
            is_valid = await check_douyin_account(args.account)
            print("valid" if is_valid else "invalid")
            return 0 if is_valid else 1

        if args.action == "verify":
            from uploader.douyin_uploader.main import _verify_code_path
            import json
            account_file = resolve_account_file("douyin", args.account)
            code_path = _verify_code_path(str(account_file))
            code_path.write_text(json.dumps({"code": args.code}, ensure_ascii=False), encoding="utf-8")
            print(f"verify_code_submitted: {args.code}")
            return 0

        publish_strategy = DOUYIN_PUBLISH_STRATEGY_SCHEDULED if args.schedule else DOUYIN_PUBLISH_STRATEGY_IMMEDIATE

        if args.action == "upload-video":
            request = DouyinVideoUploadRequest(
                account_name=args.account,
                video_file=args.file,
                title=args.title,
                description=args.desc,
                tags=parse_tags(args.tags),
                publish_date=args.schedule or 0,
                thumbnail_file=args.thumbnail,
                thumbnail_landscape_file=args.thumbnail_landscape,
                thumbnail_portrait_file=args.thumbnail_portrait,
                product_link=args.product_link,
                product_title=args.product_title,
                publish_strategy=publish_strategy,
                debug=args.debug,
                headless=args.headless,
                dry_run=args.dry_run,
            )
            await upload_video(request)
            print(f"Douyin video upload submitted: {request.video_file}")
            return 0

        if args.action == "upload-note":
            request = DouyinNoteUploadRequest(
                account_name=args.account,
                image_files=parse_image_files(args.images),
                title=args.title,
                note=args.note,
                tags=parse_tags(args.tags),
                publish_date=args.schedule or 0,
                publish_strategy=publish_strategy,
                debug=args.debug,
                headless=args.headless,
            )
            await upload_note(request)
            print(f"Douyin note upload submitted: {len(request.image_files)} images")
            return 0

        raise RuntimeError(f"Unsupported Douyin action: {args.action}")

    if args.platform == "kuaishou":
        if args.action == "login":
            result = await login_kuaishou_account(args.account, headless=args.headless)
            if not result["success"]:
                raise RuntimeError(result["message"])
            print(f"Kuaishou login flow completed: {result['account_file']}")
            return 0

        if args.action == "check":
            is_valid = await check_kuaishou_account(args.account)
            print("valid" if is_valid else "invalid")
            return 0 if is_valid else 1

        publish_strategy = KUAISHOU_PUBLISH_STRATEGY_SCHEDULED if args.schedule else KUAISHOU_PUBLISH_STRATEGY_IMMEDIATE

        if args.action == "upload-video":
            request = KuaishouVideoUploadRequest(
                account_name=args.account,
                video_file=args.file,
                title=args.title,
                description=args.desc,
                tags=parse_tags(args.tags),
                publish_date=args.schedule or 0,
                thumbnail_file=args.thumbnail,
                publish_strategy=publish_strategy,
                debug=args.debug,
                headless=args.headless,
            )
            await upload_kuaishou_video(request)
            print(f"Kuaishou video upload submitted: {request.video_file}")
            return 0

        if args.action == "upload-note":
            request = KuaishouNoteUploadRequest(
                account_name=args.account,
                image_files=parse_image_files(args.images),
                title=args.title,
                note=args.note,
                tags=parse_tags(args.tags),
                publish_date=args.schedule or 0,
                publish_strategy=publish_strategy,
                debug=args.debug,
                headless=args.headless,
            )
            await upload_kuaishou_note(request)
            print(f"Kuaishou note upload submitted: {len(request.image_files)} images")
            return 0

        raise RuntimeError(f"Unsupported Kuaishou action: {args.action}")

    if args.platform == "xiaohongshu":
        if args.action == "login":
            result = await login_xiaohongshu_account(args.account, headless=args.headless)
            if not result["success"]:
                raise RuntimeError(result["message"])
            print(f"Xiaohongshu login flow completed: {result['account_file']}")
            return 0

        if args.action == "check":
            is_valid = await check_xiaohongshu_account(args.account)
            print("valid" if is_valid else "invalid")
            return 0 if is_valid else 1

        publish_strategy = XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED if args.schedule else XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE

        if args.action == "upload-video":
            request = XiaohongshuVideoUploadRequest(
                account_name=args.account,
                video_file=args.file,
                title=args.title,
                description=args.desc,
                tags=parse_tags(args.tags),
                publish_date=args.schedule or 0,
                thumbnail_file=args.thumbnail,
                publish_strategy=publish_strategy,
                debug=args.debug,
                headless=args.headless,
            )
            await upload_xiaohongshu_video(request)
            print(f"Xiaohongshu video upload submitted: {request.video_file}")
            return 0

        if args.action == "upload-note":
            request = XiaohongshuNoteUploadRequest(
                account_name=args.account,
                image_files=parse_image_files(args.images),
                title=args.title,
                note=args.note,
                tags=parse_tags(args.tags),
                publish_date=args.schedule or 0,
                publish_strategy=publish_strategy,
                debug=args.debug,
                headless=args.headless,
            )
            await upload_xiaohongshu_note(request)
            print(f"Xiaohongshu note upload submitted: {len(request.image_files)} images")
            return 0

        raise RuntimeError(f"Unsupported Xiaohongshu action: {args.action}")

    if args.platform == "bilibili":
        if args.action == "login":
            result = await login_bilibili_account(args.account)
            if not result["success"]:
                raise RuntimeError(result["message"])
            print(f"Bilibili login flow completed: {result['account_file']}")
            return 0

        if args.action == "check":
            is_valid = await check_bilibili_account(args.account)
            print("valid" if is_valid else "invalid")
            return 0 if is_valid else 1

        if args.action == "upload-video":
            request = BilibiliVideoUploadRequest(
                account_name=args.account,
                video_file=args.file,
                title=args.title,
                description=args.desc,
                tid=args.tid,
                tags=parse_tags(args.tags),
                publish_date=args.schedule or 0,
            )
            await upload_bilibili_video(request)
            print(f"Bilibili video upload submitted: {request.video_file}")
            return 0

        raise RuntimeError(f"Unsupported Bilibili action: {args.action}")

    if args.platform == "baijiahao":
        if args.action == "login":
            result = await login_baijiahao_account(args.account)
            if not result["success"]:
                raise RuntimeError(result["message"])
            print(f"Baijiahao login flow completed: {result['account_file']}")
            return 0

        if args.action == "check":
            is_valid = await check_baijiahao_account(args.account)
            print("valid" if is_valid else "invalid")
            return 0 if is_valid else 1

        if args.action == "upload-video":
            request = BaijiahaoVideoUploadRequest(
                account_name=args.account,
                video_file=args.file,
                title=args.title,
                tags=parse_tags(args.tags),
                publish_date=args.schedule or 0,
            )
            await upload_baijiahao_video(request)
            print(f"Baijiahao video upload submitted: {request.video_file}")
            return 0

        raise RuntimeError(f"Unsupported Baijiahao action: {args.action}")

    if args.platform == "tiktok":
        if args.action == "login":
            result = await login_tiktok_account(args.account)
            if not result["success"]:
                raise RuntimeError(result["message"])
            print(f"TikTok login flow completed: {result['account_file']}")
            return 0

        if args.action == "check":
            is_valid = await check_tiktok_account(args.account)
            print("valid" if is_valid else "invalid")
            return 0 if is_valid else 1

        if args.action == "upload-video":
            request = TiktokVideoUploadRequest(
                account_name=args.account,
                video_file=args.file,
                title=args.title,
                tags=parse_tags(args.tags),
                publish_date=args.schedule or 0,
                thumbnail_file=args.thumbnail,
            )
            await upload_tiktok_video(request)
            print(f"TikTok video upload submitted: {request.video_file}")
            return 0

        raise RuntimeError(f"Unsupported TikTok action: {args.action}")

    if args.platform == "pdd":
        if args.action == "login":
            result = await login_pdd_account(args.account, headless=args.headless)
            if not result["success"]:
                raise RuntimeError(result["message"])
            print(f"PDD login flow completed: {result['account_file']}")
            return 0

        if args.action == "check":
            is_valid = await check_pdd_account(args.account)
            print("valid" if is_valid else "invalid")
            return 0 if is_valid else 1

        publish_strategy = PDD_PUBLISH_STRATEGY_SCHEDULED if args.schedule else PDD_PUBLISH_STRATEGY_IMMEDIATE

        if args.action == "upload-video":
            request = PddVideoUploadRequest(
                account_name=args.account,
                video_file=args.file,
                description=args.desc,
                tags=parse_tags(args.tags),
                publish_date=args.schedule or 0,
                goods_id=args.goods_id,
                publish_strategy=publish_strategy,
                debug=args.debug,
                headless=args.headless,
                dry_run=args.dry_run,
            )
            await upload_pdd_video(request)
            print(f"PDD video upload submitted: {request.video_file}")
            return 0

        raise RuntimeError(f"Unsupported PDD action: {args.action}")

    if args.platform == "tmall":
        if args.action == "login":
            result = await login_tmall_account(args.account, headless=args.headless)
            if not result["success"]:
                raise RuntimeError(result["message"])
            print(f"Tmall login flow completed: {result['account_file']}")
            return 0

        if args.action == "check":
            is_valid = await check_tmall_account(args.account)
            print("valid" if is_valid else "invalid")
            return 0 if is_valid else 1

        if args.action == "upload-video":
            publish_strategy = TMALL_PUBLISH_STRATEGY_SCHEDULED if args.schedule else TMALL_PUBLISH_STRATEGY_IMMEDIATE
            request = TmallVideoUploadRequest(
                account_name=args.account,
                video_file=args.file,
                title=args.title,
                description=args.desc,
                tags=parse_tags(args.tags),
                goods_id=args.goods_id,
                activity_topic=args.activity_topic,
                schedule=args.schedule if isinstance(args.schedule, datetime) else None,
                publish_strategy=publish_strategy,
                debug=args.debug,
                headless=args.headless,
                dry_run=args.dry_run,
            )
            await upload_tmall_video(request)
            print(f"Tmall video upload submitted: {request.video_file}")
            return 0

        raise RuntimeError(f"Unsupported Tmall action: {args.action}")

    if args.platform == "jd":
        if args.action == "login":
            result = await login_jd_account(args.account, headless=args.headless)
            if not result["success"]:
                raise RuntimeError(result["message"])
            print(f"JD login flow completed: {result['account_file']}")
            return 0

        if args.action == "check":
            is_valid = await check_jd_account(args.account)
            print("valid" if is_valid else "invalid")
            return 0 if is_valid else 1

        if args.action == "upload-video":
            request = JdVideoUploadRequest(
                account_name=args.account,
                video_file=args.file,
                title=args.title,
                goods_id=args.goods_id,
                schedule=args.schedule if isinstance(args.schedule, datetime) else None,
                original=args.original,
                debug=args.debug,
                headless=args.headless,
                dry_run=args.dry_run,
                keep_browser=args.keep_browser,
            )
            await upload_jd_video(request)
            print(f"JD video upload submitted: {request.video_file}")
            return 0

        raise RuntimeError(f"Unsupported JD action: {args.action}")

    if args.platform == "tencent":
        if args.action == "login":
            result = await login_tencent_account(args.account, headless=args.headless)
            if not result["success"]:
                raise RuntimeError(result["message"])
            print(f"Tencent login flow completed: {result['account_file']}")
            return 0

        if args.action == "check":
            is_valid = await check_tencent_account(args.account)
            if is_valid:
                print("valid")
                return 0
            print(
                f"invalid: cookie 不存在或已失效，请重新登录："
                f" mpau tencent login --account {args.account} --headed"
            )
            return 1

        publish_strategy = TENCENT_PUBLISH_STRATEGY_SCHEDULED if args.schedule else TENCENT_PUBLISH_STRATEGY_IMMEDIATE

        if args.action == "upload-video":
            request = TencentVideoUploadRequest(
                account_name=args.account,
                video_file=args.file,
                title=args.title,
                description=args.desc,
                tags=parse_tags(args.tags),
                publish_date=args.schedule or 0,
                thumbnail_file=args.thumbnail,
                short_title=args.short_title,
                category=args.category,
                goods_id=args.goods_id,
                is_draft=args.is_draft,
                publish_strategy=publish_strategy,
                debug=args.debug,
                headless=args.headless,
            )
            await upload_tencent_video(request)
            print(f"Tencent video upload submitted: {request.video_file}")
            return 0

        raise RuntimeError(f"Unsupported Tencent action: {args.action}")

    raise RuntimeError(f"Unsupported platform: {args.platform}")

def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return asyncio.run(dispatch(args))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
