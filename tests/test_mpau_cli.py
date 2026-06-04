import asyncio
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import mpau_cli


class SauCliParserTests(unittest.TestCase):
    def test_all_main_platform_help_entries_parse(self):
        parser = mpau_cli.build_parser()
        for platform in (
            "douyin",
            "kuaishou",
            "xiaohongshu",
            "bilibili",
            "baijiahao",
            "tiktok",
            "tencent",
            "pdd",
            "tmall",
            "jd",
        ):
            args = parser.parse_args([platform, "check", "--account", "shop1"])
            self.assertEqual(args.platform, platform)
            self.assertEqual(args.action, "check")

    def test_douyin_upload_video_accepts_dry_run_and_dual_thumbnails(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "demo.mp4"
            landscape_path = Path(tmp_dir) / "landscape.png"
            portrait_path = Path(tmp_dir) / "portrait.png"
            video_path.write_bytes(b"video")
            landscape_path.write_bytes(b"image")
            portrait_path.write_bytes(b"image")

            parser = mpau_cli.build_parser()
            args = parser.parse_args(
                [
                    "douyin",
                    "upload-video",
                    "--account",
                    "shop1",
                    "--file",
                    str(video_path),
                    "--title",
                    "视频标题",
                    "--thumbnail-landscape",
                    str(landscape_path),
                    "--thumbnail-portrait",
                    str(portrait_path),
                    "--dry-run",
                ]
            )

        self.assertEqual(args.thumbnail_landscape, landscape_path)
        self.assertEqual(args.thumbnail_portrait, portrait_path)
        self.assertTrue(args.dry_run)

    def test_bilibili_upload_video_accepts_tid(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "demo.mp4"
            video_path.write_bytes(b"video")

            parser = mpau_cli.build_parser()
            args = parser.parse_args(
                [
                    "bilibili",
                    "upload-video",
                    "--account",
                    "creator",
                    "--file",
                    str(video_path),
                    "--title",
                    "标题",
                    "--desc",
                    "简介",
                    "--tid",
                    "249",
                ]
            )

        self.assertEqual(args.tid, 249)

    def test_legacy_social_upload_flags_parse(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "demo.mp4"
            thumbnail_path = Path(tmp_dir) / "cover.png"
            video_path.write_bytes(b"video")
            thumbnail_path.write_bytes(b"image")
            parser = mpau_cli.build_parser()

            baijiahao_args = parser.parse_args(
                [
                    "baijiahao",
                    "upload-video",
                    "--account",
                    "creator",
                    "--file",
                    str(video_path),
                    "--title",
                    "标题",
                    "--tags",
                    "测试,视频",
                ]
            )
            tiktok_args = parser.parse_args(
                [
                    "tiktok",
                    "upload-video",
                    "--account",
                    "creator",
                    "--file",
                    str(video_path),
                    "--title",
                    "title",
                    "--tags",
                    "tag1,tag2",
                    "--thumbnail",
                    str(thumbnail_path),
                ]
            )

        self.assertEqual(baijiahao_args.tags, "测试,视频")
        self.assertEqual(tiktok_args.thumbnail, thumbnail_path)

    def test_ecommerce_upload_flags_parse(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "demo.mp4"
            video_path.write_bytes(b"video")
            parser = mpau_cli.build_parser()

            pdd_args = parser.parse_args(
                [
                    "pdd",
                    "upload-video",
                    "--account",
                    "shop1",
                    "--file",
                    str(video_path),
                    "--desc",
                    "视频描述",
                    "--goods-id",
                    "622747638382",
                    "--dry-run",
                ]
            )
            tmall_args = parser.parse_args(
                [
                    "tmall",
                    "upload-video",
                    "--account",
                    "shop1",
                    "--file",
                    str(video_path),
                    "--title",
                    "视频标题",
                    "--goods-id",
                    "1001817898897",
                    "--activity-topic",
                    "宠物",
                    "--dry-run",
                ]
            )
            jd_args = parser.parse_args(
                [
                    "jd",
                    "upload-video",
                    "--account",
                    "shop1",
                    "--file",
                    str(video_path),
                    "--title",
                    "五字标题测试",
                    "--goods-id",
                    "10204078771126",
                    "--original",
                    "--keep-browser",
                    "--dry-run",
                ]
            )

        self.assertEqual(pdd_args.goods_id, "622747638382")
        self.assertTrue(pdd_args.dry_run)
        self.assertEqual(tmall_args.activity_topic, "宠物")
        self.assertTrue(tmall_args.dry_run)
        self.assertTrue(jd_args.original)
        self.assertTrue(jd_args.keep_browser)
        self.assertTrue(jd_args.dry_run)


class SauCliDispatchTests(unittest.TestCase):
    def test_dispatch_kuaishou_upload_video_builds_request(self):
        args = Namespace(
            platform="kuaishou",
            action="upload-video",
            account="creator",
            file=Path("demo.mp4"),
            title="视频标题",
            desc="视频简介",
            tags="测试,视频",
            schedule=0,
            thumbnail=None,
            debug=False,
            headless=True,
        )
        with patch("mpau_cli.upload_kuaishou_video", new=AsyncMock()) as mock_upload:
            asyncio.run(mpau_cli.dispatch(args))

        request = mock_upload.await_args.args[0]
        self.assertEqual(request.title, "视频标题")
        self.assertEqual(request.description, "视频简介")
        self.assertTrue(request.headless)

    def test_dispatch_bilibili_upload_video_builds_request(self):
        args = Namespace(
            platform="bilibili",
            action="upload-video",
            account="creator",
            file=Path("demo.mp4"),
            title="视频标题",
            desc="视频简介",
            tid=249,
            tags="测试,视频",
            schedule=0,
        )
        with patch("mpau_cli.upload_bilibili_video", new=AsyncMock()) as mock_upload:
            asyncio.run(mpau_cli.dispatch(args))

        request = mock_upload.await_args.args[0]
        self.assertEqual(request.tid, 249)
        self.assertEqual(request.tags, ["测试", "视频"])

    def test_dispatch_tiktok_upload_video_builds_request(self):
        args = Namespace(
            platform="tiktok",
            action="upload-video",
            account="creator",
            file=Path("demo.mp4"),
            title="video title",
            tags="tag1,tag2",
            schedule=0,
            thumbnail=Path("cover.png"),
        )
        with patch("mpau_cli.upload_tiktok_video", new=AsyncMock()) as mock_upload:
            asyncio.run(mpau_cli.dispatch(args))

        request = mock_upload.await_args.args[0]
        self.assertEqual(request.tags, ["tag1", "tag2"])
        self.assertEqual(request.thumbnail_file, Path("cover.png"))

    def test_dispatch_baijiahao_upload_video_builds_request(self):
        args = Namespace(
            platform="baijiahao",
            action="upload-video",
            account="creator",
            file=Path("demo.mp4"),
            title="视频标题",
            tags="测试,视频",
            schedule=0,
        )
        with patch("mpau_cli.upload_baijiahao_video", new=AsyncMock()) as mock_upload:
            asyncio.run(mpau_cli.dispatch(args))

        request = mock_upload.await_args.args[0]
        self.assertEqual(request.title, "视频标题")
        self.assertEqual(request.tags, ["测试", "视频"])


if __name__ == "__main__":
    unittest.main()
