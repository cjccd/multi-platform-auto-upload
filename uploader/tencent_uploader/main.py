# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect
import os
from datetime import datetime, timedelta
from pathlib import Path

from patchright.async_api import Page
from patchright.async_api import Playwright
from patchright.async_api import async_playwright

from utils.config import BASE_DIR, DEBUG_MODE, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.log import tencent_logger

TENCENT_LOGIN_URL = "https://channels.weixin.qq.com"
TENCENT_UPLOAD_URL = "https://channels.weixin.qq.com/platform/post/create"
TENCENT_MANAGE_URL = "https://channels.weixin.qq.com/platform/post/list"
TENCENT_PUBLISH_STRATEGY_IMMEDIATE = "immediate"
TENCENT_PUBLISH_STRATEGY_SCHEDULED = "scheduled"


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


def _resolve_account_file(account_file: str | Path) -> str:
    path = Path(account_file).expanduser()
    if path.is_absolute():
        return str(path)

    if len(path.parts) == 1:
        return str((Path(BASE_DIR) / "cookies" / "tencent_uploader" / path).resolve())

    return str(path.resolve())


async def _emit_qrcode_callback(qrcode_callback, payload: dict):
    if not qrcode_callback:
        return

    callback_result = qrcode_callback(payload)
    if inspect.isawaitable(callback_result):
        await callback_result


def _build_login_result(
    success: bool,
    status: str,
    message: str,
    account_file: str,
    qrcode: dict | None = None,
    current_url: str = "",
) -> dict:
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "qrcode": qrcode,
        "current_url": current_url,
    }


def _build_launch_kwargs(headless: bool) -> dict:
    launch_kwargs = {"headless": headless}
    if LOCAL_CHROME_PATH:
        launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
    else:
        launch_kwargs["channel"] = "chrome"
    return launch_kwargs


def _get_qrcode_utils():
    from utils.login_qrcode import build_login_qrcode_path
    from utils.login_qrcode import decode_qrcode_from_path
    from utils.login_qrcode import print_terminal_qrcode
    from utils.login_qrcode import remove_qrcode_file
    from utils.login_qrcode import save_data_url_image

    return {
        "build_login_qrcode_path": build_login_qrcode_path,
        "decode_qrcode_from_path": decode_qrcode_from_path,
        "print_terminal_qrcode": print_terminal_qrcode,
        "remove_qrcode_file": remove_qrcode_file,
        "save_data_url_image": save_data_url_image,
    }


def format_str_for_short_title(origin_title: str) -> str:
    allowed_special_chars = "《》“”:+?%°"
    filtered_chars = [char if char.isalnum() or char in allowed_special_chars else " " if char == "," else "" for char in origin_title]
    formatted_string = "".join(filtered_chars)

    if len(formatted_string) > 16:
        formatted_string = formatted_string[:16]
    elif len(formatted_string) < 6:
        formatted_string += " " * (6 - len(formatted_string))

    return formatted_string


async def cookie_auth(account_file):
    account_file = _resolve_account_file(account_file)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=True))
        try:
            context = await browser.new_context(storage_state=account_file)
            context = await set_init_script(context)
            page = await context.new_page()
            await page.goto(TENCENT_UPLOAD_URL)

            # cookie 失效时视频号会先短暂展示 create 页，再由 JS 重定向到 login.html
            # 因此等页面稳定后再判断最终 URL
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            await page.wait_for_timeout(1500)

            current_url = page.url
            # 只有跳到登录页（login.html / login）才视为失效；
            # /platform 主页或 /platform/post/create 都视为已登录
            if "login" in current_url and "platform" not in current_url:
                tencent_logger.info(_msg("🥹", f"cookie 已失效，被重定向到: {current_url}"))
                return False

            # 兜底：页面上有「扫码登录」提示也判失效
            qrcode_marker = page.get_by_text("扫码登录", exact=True).first
            if await qrcode_marker.count():
                tencent_logger.info(_msg("🥹", "cookie 已失效，页面出现扫码登录提示"))
                return False

            tencent_logger.success(_msg("🥳", "cookie 有效"))
            return True
        except Exception as exc:
            tencent_logger.warning(_msg("😵", f"cookie 校验时出错，按失效处理: {exc}"))
            return False
        finally:
            await browser.close()


async def _extract_tencent_qrcode_src(page: Page) -> str:
    if hasattr(page, "frame_locator"):
        try:
            iframe_locator = page.frame_locator('[src*="login-for-iframe"]')
            qr_code_img = iframe_locator.locator('div#app img.qrcode').first
            await qr_code_img.wait_for(state="visible", timeout=30000)
            src = await qr_code_img.get_attribute("src")
            if src and src.startswith("data:image/"):
                return src
        except Exception:
            pass

    selector_candidates = [
        "div.login-qrcode-wrap img.qrcode",
        "div.qrcode-wrap img.qrcode",
        "img.qrcode",
        'img[src^="data:image/"]',
    ]
    for selector in selector_candidates:
        qr_code_img = page.locator(selector).first
        try:
            if not await qr_code_img.count() or not await qr_code_img.is_visible():
                continue
            src = await qr_code_img.get_attribute("src")
            if src and src.startswith("data:image/"):
                return src
        except Exception:
            continue

    raise RuntimeError("未获取到视频号登录二维码地址")


async def _save_tencent_qrcode(page: Page, account_file: str, previous_qrcode_path: Path | None = None, qrcode_callback=None) -> dict:
    qrcode_utils = _get_qrcode_utils()
    qrcode_src = await _extract_tencent_qrcode_src(page)
    qrcode_path = qrcode_utils["save_data_url_image"](
        qrcode_src,
        qrcode_utils["build_login_qrcode_path"](account_file, suffix="tencent_login_qrcode"),
    )
    if previous_qrcode_path and previous_qrcode_path != qrcode_path:
        if qrcode_utils["remove_qrcode_file"](previous_qrcode_path):
            tencent_logger.info(_msg("🧹", f"临时二维码文件已清理: {previous_qrcode_path}"))

    tencent_logger.info(_msg("🖼️", f"二维码已经准备好啦，已保存到: {qrcode_path}"))
    qrcode_content = qrcode_utils["decode_qrcode_from_path"](qrcode_path)
    if qrcode_content:
        qrcode_utils["print_terminal_qrcode"](qrcode_content, qrcode_path, "微信")
    else:
        tencent_logger.warning(
            _msg(
                "😵",
                f"没能从二维码图片里解析出可打印内容，所以这次没法在终端重绘二维码；请直接打开 {qrcode_path} 扫码",
            )
        )

    qrcode_info = {
        "image_path": str(qrcode_path),
        "image_data_url": qrcode_src,
    }
    await _emit_qrcode_callback(qrcode_callback, qrcode_info)
    return qrcode_info


async def _is_tencent_login_completed(page: Page) -> bool:
    publish_markers = [
        page.locator('div:has-text("发表视频")').first,
        page.locator('button:has-text("发表")').first,
        page.locator('button:has-text("保存草稿")').first,
    ]
    for marker in publish_markers:
        try:
            if await marker.count() and await marker.is_visible():
                return True
        except Exception:
            continue

    if not (page.url.startswith(TENCENT_UPLOAD_URL) or page.url.startswith(TENCENT_MANAGE_URL)):
        return False

    login_markers = [
        page.locator("div.login-qrcode-wrap").first,
        page.locator("div.qrcode-wrap").first,
        page.locator("img.qrcode").first,
        page.locator('span:has-text("微信扫码登录 视频号助手")').first,
    ]
    for marker in login_markers:
        try:
            if await marker.count() and await marker.is_visible():
                return False
        except Exception:
            continue

    return True


async def _is_tencent_qrcode_expired(page: Page) -> bool:
    tip_selectors = [
        'div.mask.show p.refresh-tip:has-text("二维码已过期，点击刷新")',
        'div.mask.show p.refresh-tip:has-text("网络不可用，点击刷新")',
        'p.refresh-tip:has-text("二维码已过期，点击刷新")',
        'p.refresh-tip:has-text("网络不可用，点击刷新")',
    ]
    for selector in tip_selectors:
        tip = page.locator(selector).first
        try:
            if await tip.count() and await tip.is_visible():
                return True
        except Exception:
            continue
    return False


async def _is_tencent_qrcode_scanned(page: Page) -> bool:
    scanned_tips = [
        'div.qr-tip div:has-text("已扫码")',
        'div.qr-tip div:has-text("需在手机上进行确认")',
    ]
    for selector in scanned_tips:
        tip = page.locator(selector).first
        try:
            if await tip.count() and await tip.is_visible():
                return True
        except Exception:
            continue
    return False


async def _refresh_tencent_qrcode(page: Page) -> None:
    visible_refresh_selectors = [
        "div.login-qrcode-wrap div.mask.show div.refresh-wrap",
        "div.login-qrcode-wrap div.mask.show .refresh-wrap",
    ]
    for selector in visible_refresh_selectors:
        refresh_wrap = page.locator(selector).first
        try:
            if not await refresh_wrap.count() or not await refresh_wrap.is_visible():
                continue
            await refresh_wrap.click()
            return
        except Exception:
            continue

    tip_selectors = [
        'div.mask.show p.refresh-tip:has-text("二维码已过期，点击刷新")',
        'div.mask.show p.refresh-tip:has-text("网络不可用，点击刷新")',
        'p.refresh-tip:has-text("二维码已过期，点击刷新")',
        'p.refresh-tip:has-text("网络不可用，点击刷新")',
    ]
    for selector in tip_selectors:
        tip = page.locator(selector).first
        try:
            if not await tip.count() or not await tip.is_visible():
                continue
            refresh_wrap = tip.locator("xpath=ancestor::div[contains(@class, 'refresh-wrap')]").first
            if await refresh_wrap.count():
                await refresh_wrap.click()
            else:
                await tip.click()
            return
        except Exception:
            continue

    fallback_refresh = page.locator("div.login-qrcode-wrap div.refresh-wrap").first
    if await fallback_refresh.count():
        await fallback_refresh.click()
        return

    raise RuntimeError("未找到可点击的视频号二维码刷新区域")


async def _wait_for_tencent_login(
    page: Page,
    account_file: str,
    qrcode_info: dict,
    qrcode_callback=None,
    poll_interval: int = 3,
    max_checks: int = 100,
) -> dict:
    qrcode_path = Path(qrcode_info["image_path"])
    scanned_logged = False
    for _ in range(max_checks):
        if await _is_tencent_login_completed(page):
            tencent_logger.info(_msg("🥳", f"扫码成功，已经跳转到登录后页面: {page.url}"))
            return _build_login_result(True, "success", "视频号扫码登录成功", account_file, qrcode_info, page.url)

        if not scanned_logged and await _is_tencent_qrcode_scanned(page):
            tencent_logger.info(_msg("📱", "已经扫码啦，还差手机端确认一下"))
            scanned_logged = True

        if await _is_tencent_qrcode_expired(page):
            tencent_logger.warning(_msg("😵", "二维码失效了，小人马上去刷新"))
            await _refresh_tencent_qrcode(page)
            await asyncio.sleep(1)
            qrcode_info = await _save_tencent_qrcode(
                page,
                account_file,
                previous_qrcode_path=qrcode_path,
                qrcode_callback=qrcode_callback,
            )
            qrcode_path = Path(qrcode_info["image_path"])

        await asyncio.sleep(poll_interval)

    return _build_login_result(False, "timeout", "等待视频号扫码登录超时", account_file, qrcode_info, page.url)


async def tencent_cookie_gen(
    account_file,
    qrcode_callback=None,
    poll_interval: int = 3,
    max_checks: int = 100,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    account_file = _resolve_account_file(account_file)
    Path(account_file).parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=headless))
        context = await browser.new_context()
        qrcode_path = None
        result = _build_login_result(False, "failed", "视频号登录失败", account_file)
        try:
            page = await context.new_page()
            await page.goto(TENCENT_LOGIN_URL)
            qrcode_info = await _save_tencent_qrcode(page, account_file, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"])
            tencent_logger.info(_msg("🧍", "请扫码，小人正在耐心等待登录完成"))
            result = await _wait_for_tencent_login(
                page,
                account_file,
                qrcode_info,
                qrcode_callback=qrcode_callback,
                poll_interval=poll_interval,
                max_checks=max_checks,
            )
            if result["success"]:
                await asyncio.sleep(2)
                await context.storage_state(path=account_file)
                if not await cookie_auth(account_file):
                    result = _build_login_result(
                        False,
                        "cookie_invalid",
                        "视频号扫码流程结束，但 cookie 校验失败",
                        account_file,
                        qrcode_info,
                        page.url,
                    )
            return result
        except Exception as exc:
            result = _build_login_result(
                False,
                "failed",
                str(exc),
                account_file,
                current_url=page.url if "page" in locals() else "",
            )
            return result
        finally:
            qrcode_utils = _get_qrcode_utils()
            if qrcode_utils["remove_qrcode_file"](qrcode_path):
                tencent_logger.info(_msg("🧹", f"临时二维码文件已清理: {qrcode_path}"))
            if not result["success"]:
                tencent_logger.error(_msg("😢", f"登录失败: {result['message']}"))
            await context.close()
            await browser.close()


async def tencent_setup(
    account_file,
    handle=False,
    return_detail=False,
    qrcode_callback=None,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    account_file = _resolve_account_file(account_file)
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie文件不存在或已失效", account_file)
            return result if return_detail else False

        tencent_logger.info(_msg("🥹", "cookie 失效了，准备打开浏览器重新登录"))
        result = await tencent_cookie_gen(account_file, qrcode_callback=qrcode_callback, headless=headless)
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie有效", account_file)
    return result if return_detail else True


async def get_tencent_cookie(account_file, qrcode_callback=None, headless: bool = LOCAL_CHROME_HEADLESS):
    return await tencent_cookie_gen(account_file, qrcode_callback=qrcode_callback, headless=headless)


async def weixin_setup(
    account_file,
    handle=False,
    return_detail=False,
    qrcode_callback=None,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    return await tencent_setup(
        account_file,
        handle=handle,
        return_detail=return_detail,
        qrcode_callback=qrcode_callback,
        headless=headless,
    )


class TencentBaseUploader(BaseVideoUploader):
    def __init__(
        self,
        publish_date: datetime | int,
        account_file,
        publish_strategy: str = TENCENT_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        self.publish_date = publish_date
        self.account_file = _resolve_account_file(account_file)
        self.publish_strategy = publish_strategy
        self.debug = debug
        self.headless = headless
        self.local_executable_path = LOCAL_CHROME_PATH

    async def validate_base_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"cookie文件不存在，请先完成视频号登录: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"cookie文件已失效，请先完成视频号登录: {self.account_file}")
        if self.publish_strategy not in {TENCENT_PUBLISH_STRATEGY_IMMEDIATE, TENCENT_PUBLISH_STRATEGY_SCHEDULED}:
            raise ValueError(f"不支持的发布策略: {self.publish_strategy}")

        if self.publish_strategy == TENCENT_PUBLISH_STRATEGY_SCHEDULED:
            self.publish_date = self.validate_publish_date(self.publish_date)
            self.validate_tencent_schedule_range(self.publish_date)
        else:
            self.publish_date = 0

    @staticmethod
    def validate_tencent_schedule_range(publish_date: datetime) -> None:
        """视频号页面当前只提供约 30 天内的可选定时日期，超过范围应在上传前终止。"""
        now = datetime.now(tz=publish_date.tzinfo) if publish_date.tzinfo else datetime.now()
        max_publish_time = now.replace(second=0, microsecond=0) + timedelta(days=30)
        if publish_date > max_publish_time:
            raise ValueError(
                "视频号定时发布时间超出当前可选范围，已终止上传。"
                f"目标时间: {publish_date.strftime('%Y-%m-%d %H:%M')}；"
                f"当前最多支持约 30 天内定时，最晚可选时间约为: {max_publish_time.strftime('%Y-%m-%d %H:%M')}。"
                "请改成更近的发布时间后重试。"
            )

    async def set_schedule_time_tencent(self, page: Page, publish_date: datetime):
        target_time = publish_date.strftime("%H:%M")
        target_date = publish_date.strftime("%Y-%m-%d")
        tencent_logger.info(_msg("🕒", f"小人准备设置定时发布时间: {target_date} {target_time}"))

        label_element = page.locator("label").filter(has_text="定时").nth(1)
        await label_element.click()
        await page.click('input[placeholder="请选择发表时间"]')

        current_month = publish_date.strftime("%m月")
        page_month = await page.inner_text('span.weui-desktop-picker__panel__label:has-text("月")')
        if page_month != current_month:
            await page.click("button.weui-desktop-btn__icon__right")

        elements = await page.query_selector_all("table.weui-desktop-picker__table a")
        date_clicked = False
        for element in elements:
            if "weui-desktop-picker__disabled" in await element.evaluate("el => el.className"):
                continue
            text = await element.inner_text()
            if text.strip() == str(publish_date.day):
                await element.click()
                date_clicked = True
                break
        if not date_clicked:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"/tmp/tencent_schedule_date_unavailable_{publish_date.strftime('%Y%m%d_%H%M')}_{ts}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            raise RuntimeError(
                "视频号页面没有提供该定时发布日期，已终止上传。"
                f"目标时间: {target_date} {target_time}；"
                "通常是发布时间超出视频号当前可选范围，或该日期暂不可选。"
                f"请改成页面可选的发布时间后重试。截图: {screenshot_path}"
            )

        time_input = page.locator('input[placeholder="请选择时间"]').first
        await time_input.wait_for(state="visible", timeout=5000)
        await time_input.click()
        await time_input.fill(target_time)
        await page.keyboard.press("Enter")
        await page.locator("div.input-editor").click()
        await page.wait_for_timeout(500)

        actual_time = await time_input.evaluate("el => el.value || ''")
        if actual_time != target_time:
            tencent_logger.warning(
                _msg("😵", f"fill() 后时间框实际值为 '{actual_time}'，准备使用原生 input setter 兜底")
            )
            await time_input.click()
            await page.evaluate(
                """
                ({ selector, value }) => {
                    const input = document.querySelector(selector);
                    if (!input) {
                        throw new Error(`未找到时间输入框: ${selector}`);
                    }
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype,
                        'value'
                    ).set;
                    nativeInputValueSetter.call(input, value);
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
                    input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', bubbles: true }));
                    input.blur();
                }
                """,
                {"selector": 'input[placeholder="请选择时间"]', "value": target_time},
            )
            await page.locator("div.input-editor").click()
            await page.wait_for_timeout(500)
            actual_time = await time_input.evaluate("el => el.value || ''")

        if actual_time != target_time:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"/tmp/tencent_schedule_time_failed_{publish_date.strftime('%Y%m%d_%H%M')}_{ts}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            raise RuntimeError(
                f"定时时间设置失败：期望 {target_time}，页面实际值 '{actual_time}'。截图: {screenshot_path}"
            )

        tencent_logger.success(_msg("🕒", f"定时发布时间已设置: {target_date} {target_time}"))

    async def open_upload_page(self, page: Page) -> None:
        await page.goto(TENCENT_UPLOAD_URL)
        await page.wait_for_url(TENCENT_UPLOAD_URL)

    async def upload_video_file(self, page: Page, file_path: str) -> None:
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(file_path)

    async def set_short_title(self, page: Page, title: str, short_title: str | None = None) -> None:
        short_title_element = (
            page.get_by_text("短标题", exact=True)
            .locator("..")
            .locator("xpath=following-sibling::div")
            .locator('span input[type="text"]')
        )
        if await short_title_element.count():
            await short_title_element.fill(short_title or format_str_for_short_title(title))

    async def fill_title_and_tags(self, page: Page) -> None:
        await page.locator("div.input-editor").click()
        await page.keyboard.type(self.title)
        await page.keyboard.press("Enter")
        for tag in self.tags:
            await page.keyboard.type("#" + tag)
            await page.keyboard.press("Space")
        tencent_logger.info(_msg("🏷️", f"成功添加 hashtag: {len(self.tags)}"))

    async def fill_description(self, page: Page) -> None:
        await page.keyboard.press("Enter")
        await page.keyboard.type(self.desc)
        tencent_logger.info(_msg("🏷️", f"成功添加 desc: {len(self.desc)}"))

    async def apply_collection(self, page: Page) -> None:
        collection_elements = (
            page.get_by_text("添加到合集")
            .locator("xpath=following-sibling::div")
            .locator(".option-list-wrap > div")
        )
        if await collection_elements.count() > 1:
            await page.get_by_text("添加到合集").locator("xpath=following-sibling::div").click()
            await collection_elements.first.click()

    async def apply_original_statement(self, page: Page) -> None:
        """尝试勾选页面上的声明原创 checkbox。
        视频号页面原创声明入口有两种形态：
          形态 A（旧版）：label="视频为原创" 的 checkbox
          形态 B（新版）：字段标题「声明原创」+ 旁边 checkbox，label 文字含「声明后，作品将展示原创标记」
        能点就点，没有就跳过，不报错。
        """
        # ── 形态 A：label="视频为原创" ──────────────────────────────────────
        cb_a = page.get_by_label("视频为原创")
        if await cb_a.count() and await cb_a.is_visible():
            if not await cb_a.is_checked():
                await cb_a.check()
            tencent_logger.info(_msg("✅", "已勾选「视频为原创」"))

        # ── 形态 B（新版）：「声明原创」字段旁 checkbox ───────────────────────
        # selector 候选：先找 label 含关键词，再找字段行内 input
        cb_b_candidates = [
            page.locator('label').filter(has_text="声明后，作品将展示原创标记").locator('input[type="checkbox"]').first,
            page.locator('label').filter(has_text="声明后").locator('input[type="checkbox"]').first,
            # 字段容器：div.form-item 或 tr 包含「声明原创」文本，内部 input
            page.locator('div.form-item, tr').filter(has_text="声明原创").locator('input[type="checkbox"]').first,
        ]
        cb_b_clicked = False
        for cb_b in cb_b_candidates:
            try:
                if not await cb_b.count() or not await cb_b.is_visible():
                    continue
                if await cb_b.is_disabled():
                    tencent_logger.info(_msg("⚠️", "「声明原创」checkbox 存在但不可点击，跳过"))
                    break
                if not await cb_b.is_checked():
                    await cb_b.click()
                    await page.wait_for_timeout(800)  # 等弹窗出现
                tencent_logger.info(_msg("✅", "已勾选「声明原创」"))
                cb_b_clicked = True
                break
            except Exception:
                continue

        # ── 原创声明协议弹窗（点击 checkbox 后可能弹出）────────────────────
        # 弹窗「原创权益」所有元素都在 shadow DOM 里，普通 locator 无法找到。
        # 用 JS 穿透 shadow DOM：找弹窗标题「原创权益」→ 找未勾选 checkbox → 点击 → 点「声明原创」按钮
        await page.wait_for_timeout(800)
        try:
            result = await page.evaluate("""
            () => {
                function getAllElements(root, results=[]) {
                    for (const el of root.querySelectorAll('*')) {
                        results.push(el);
                        if (el.shadowRoot) getAllElements(el.shadowRoot, results);
                    }
                    return results;
                }
                const all = getAllElements(document);

                // 检测弹窗是否存在（找标题「原创权益」）
                const title = all.find(el =>
                    el.tagName === 'H3' &&
                    (el.innerText || el.textContent || '').includes('原创权益')
                );
                if (!title) return { dialog: false };

                // 找弹窗内未勾选的协议 checkbox（第一个未勾选的 input[type=checkbox]）
                const dialogRoot = title.getRootNode();
                const checkboxes = dialogRoot.querySelectorAll('input[type="checkbox"]');
                let agreeCb = null;
                for (const cb of checkboxes) {
                    if (!cb.checked) { agreeCb = cb; break; }
                }
                if (!agreeCb) return { dialog: true, cbFound: false, reason: '未找到未勾选的协议 checkbox' };

                agreeCb.click();

                return { dialog: true, cbFound: true, checked: agreeCb.checked };
            }
            """)

            if not result.get("dialog"):
                pass  # 弹窗未出现，跳过
            elif not result.get("cbFound"):
                tencent_logger.warning(_msg("⚠️", f"原创声明协议弹窗出现但未找到协议 checkbox：{result.get('reason')}"))
            else:
                await page.wait_for_timeout(400)
                # 点击「声明原创」按钮（同样在 shadow DOM 里，用 JS 找不含 _disabled 的那个）
                btn_clicked = await page.evaluate("""
                () => {
                    function getAllElements(root, results=[]) {
                        for (const el of root.querySelectorAll('*')) {
                            results.push(el);
                            if (el.shadowRoot) getAllElements(el.shadowRoot, results);
                        }
                        return results;
                    }
                    const all = getAllElements(document);
                    const btn = all.find(el =>
                        el.tagName === 'BUTTON' &&
                        (el.innerText || '').trim() === '声明原创' &&
                        !el.className.includes('btn_disabled') &&
                        !el.disabled
                    );
                    if (btn) { btn.click(); return true; }
                    return false;
                }
                """)
                if btn_clicked:
                    tencent_logger.info(_msg("✅", "已确认原创声明协议并点击「声明原创」"))
                else:
                    tencent_logger.warning(_msg("⚠️", "协议 checkbox 已勾选，但「声明原创」按钮未找到或仍禁用"))
        except Exception as exc:
            tencent_logger.warning(_msg("⚠️", f"处理原创声明协议弹窗时出现异常，跳过: {exc}"))

        # ── 旧版原创分类（有 category 时才执行）──────────────────────────────
        if not getattr(self, "category", None):
            return

        try:
            declare_area = page.locator('div.label span:has-text("声明原创")')
            if not await declare_area.count():
                return

            declare_cb = page.locator("div.declare-original-checkbox input.ant-checkbox-input")
            if await declare_cb.count() and not await declare_cb.is_disabled():
                if not await declare_cb.is_checked():
                    await declare_cb.click()
                checked = page.locator(
                    "div.declare-original-dialog "
                    "label.ant-checkbox-wrapper.ant-checkbox-wrapper-checked:visible"
                )
                if not await checked.count():
                    await page.locator("div.declare-original-dialog input.ant-checkbox-input:visible").click()

            original_type_form = page.locator('div.original-type-form > div.form-label:has-text("原创类型"):visible')
            if await original_type_form.count():
                await page.locator("div.form-content:visible").click()
                await page.locator(
                    "div.form-content:visible "
                    "ul.weui-desktop-dropdown__list "
                    f'li.weui-desktop-dropdown__list-ele:has-text("{self.category}")'
                ).first.click()
                await page.wait_for_timeout(1000)

            declare_button = page.locator('button:has-text("声明原创"):visible')
            if await declare_button.count():
                await declare_button.click()
        except Exception as exc:
            tencent_logger.warning(_msg("⚠️", f"原创分类设置时出现异常，跳过: {exc}"))

    async def wait_for_upload_complete(self, page: Page) -> None:
        """等视频上传 + 封面生成都完成。
        页面所有元素均在 shadow DOM 内，用 JS 穿透检测：
        1. 出现 div.tag-inner 文字为「删除」→ 视频本体上传完毕
        2. 「生成中」消失 或「发表」按钮不含 btn_disabled → 封面生成完毕
        最多等 6 分钟。
        """
        max_wait_seconds = 360
        elapsed = 0
        video_uploaded = False
        cover_ready = False

        JS_CHECK = """
        () => {
            function getAll(root, results=[]) {
                for (const el of root.querySelectorAll('*')) {
                    results.push(el);
                    if (el.shadowRoot) getAll(el.shadowRoot, results);
                }
                return results;
            }
            const all = getAll(document);

            // 阶段1：div.tag-inner 文字为「删除」
            const hasDelete = all.some(el =>
                el.className === 'tag-inner' &&
                (el.innerText || el.textContent || '').trim() === '删除' &&
                el.offsetParent !== null
            );

            // 阶段2a：「生成中」是否可见
            const hasGenerating = all.some(el =>
                (el.innerText || el.textContent || '').trim() === '生成中' &&
                el.children.length === 0 &&
                el.offsetParent !== null
            );

            // 阶段2b：发表按钮是否存在且不含 btn_disabled
            const publishBtn = all.find(el =>
                el.tagName === 'BUTTON' &&
                (el.innerText || '').trim() === '发表'
            );
            const publishEnabled = publishBtn
                ? !publishBtn.className.includes('btn_disabled') && !publishBtn.disabled
                : false;

            return { hasDelete, hasGenerating, publishEnabled };
        }
        """

        while elapsed < max_wait_seconds:
            try:
                # 检测上传出错（错误提示仍用普通 selector，兼容旧版）
                upload_failed = await page.locator("div.status-msg.error").count()
                if upload_failed:
                    tencent_logger.error(_msg("😵", "发现上传出错了，准备重试"))
                    await self.handle_upload_error(page)
                    elapsed += 2
                    await asyncio.sleep(2)
                    continue

                state = await page.evaluate(JS_CHECK)
                has_delete = state.get("hasDelete", False)
                has_generating = state.get("hasGenerating", False)
                publish_enabled = state.get("publishEnabled", False)

                # 阶段 1
                if not video_uploaded and has_delete:
                    video_uploaded = True
                    tencent_logger.info(_msg("📤", "视频文件已上传完成，等待封面生成..."))

                # 阶段 2
                if video_uploaded:
                    if not has_generating or publish_enabled:
                        cover_ready = True
                        tencent_logger.info(_msg("🥳", "视频上传完毕（封面已生成）"))
                        return

                tencent_logger.info(
                    _msg(
                        "🏃",
                        f"正在上传视频中... (视频={'✓' if video_uploaded else '×'} 封面={'✓' if cover_ready else '×'})",
                    )
                )
            except Exception:
                tencent_logger.info(_msg("🏃", "正在上传视频中..."))

            await asyncio.sleep(2)
            elapsed += 2

        raise RuntimeError(
            f"等待视频上传完成超时（{max_wait_seconds}s）："
            f"视频本体已上传={video_uploaded}, 封面已生成={cover_ready}"
        )

    async def submit_publish(self, page: Page) -> None:
        is_draft = getattr(self, "is_draft", False)

        if is_draft:
            await self._save_as_draft(page)
        else:
            await self._publish_now(page)

    async def _save_as_draft(self, page: Page) -> None:
        clicked = await page.evaluate("""
        () => {
            function getAll(root, results=[]) {
                for (const el of root.querySelectorAll('*')) {
                    results.push(el);
                    if (el.shadowRoot) getAll(el.shadowRoot, results);
                }
                return results;
            }
            const btn = getAll(document).find(el =>
                el.tagName === 'BUTTON' &&
                /保存草稿/.test(el.innerText || '')
            );
            if (btn) { btn.click(); return true; }
            return false;
        }
        """)
        if not clicked:
            raise RuntimeError("未找到「保存草稿」按钮")
        tencent_logger.info(_msg("🚀", "已点击「保存草稿」按钮，等待保存完成..."))

        for _ in range(20):
            if page.is_closed():
                raise RuntimeError("页面在等待「保存草稿」完成期间被关闭")

            try:
                if "post/list" in page.url or "draft" in page.url:
                    tencent_logger.success(_msg("🥳", "视频草稿保存成功（已跳转）"))
                    return
            except Exception:
                pass

            try:
                # 用 JS 检测「已保存」toast（也在 shadow DOM）
                has_saved = await page.evaluate("""
                () => {
                    function getAll(root, res=[]) {
                        for (const el of root.querySelectorAll('*')) {
                            res.push(el);
                            if (el.shadowRoot) getAll(el.shadowRoot, res);
                        }
                        return res;
                    }
                    return getAll(document).some(el =>
                        /已保存/.test(el.innerText || '') &&
                        el.children.length === 0 &&
                        el.offsetParent !== null
                    );
                }
                """)
                if has_saved:
                    tencent_logger.success(_msg("🥳", "视频草稿保存成功"))
                    return
            except Exception:
                pass

            await asyncio.sleep(1)

        raise RuntimeError("保存草稿超时（20s 未检测到「已保存」提示或跳转）")

    async def _publish_now(self, page: Page) -> None:
        clicked = await page.evaluate("""
        () => {
            function getAll(root, results=[]) {
                for (const el of root.querySelectorAll('*')) {
                    results.push(el);
                    if (el.shadowRoot) getAll(el.shadowRoot, results);
                }
                return results;
            }
            const btn = getAll(document).find(el =>
                el.tagName === 'BUTTON' &&
                (el.innerText || '').trim() === '发表' &&
                !el.className.includes('btn_disabled') &&
                !el.disabled
            );
            if (btn) { btn.click(); return true; }
            return false;
        }
        """)
        if not clicked:
            raise RuntimeError("未找到可点击的「发表」按钮")
        tencent_logger.info(_msg("🚀", "已点击「发表」按钮，等待跳转..."))

        for _ in range(30):
            if page.is_closed():
                raise RuntimeError("页面在等待「发表」跳转期间被关闭")
            try:
                if TENCENT_MANAGE_URL in page.url:
                    tencent_logger.success(_msg("🥳", "视频发布成功"))
                    return
            except Exception:
                pass
            await asyncio.sleep(1)

        try:
            current_url = page.url
        except Exception:
            current_url = ""
        raise RuntimeError(f"等待「发表」跳转超时（30s），当前 URL: {current_url}")


class TencentVideo(TencentBaseUploader):
    def __init__(
        self,
        title,
        file_path,
        tags,
        publish_date: datetime | int,
        account_file,
        category=None,
        is_draft=False,
        desc: str | None = None,
        thumbnail_path: str | None = None,
        short_title: str | None = None,
        goods_id: str | None = None,
        publish_strategy: str = TENCENT_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        super().__init__(
            publish_date=publish_date,
            account_file=account_file,
            publish_strategy=publish_strategy,
            debug=debug,
            headless=headless,
        )
        self.title = title
        self.file_path = file_path
        self.tags = tags or []
        self.category = category
        self.is_draft = is_draft
        self.desc = desc or ""
        self.thumbnail_path = thumbnail_path
        self.short_title = short_title
        self.goods_id = goods_id.strip() if goods_id else ""

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("视频模式下，title 是必须的")
        self.file_path = str(self.validate_video_file(self.file_path))
        if self.thumbnail_path:
            self.thumbnail_path = str(self.validate_image_file(self.thumbnail_path))

    async def handle_upload_error(self, page: Page) -> None:
        tencent_logger.info(_msg("😵", "视频出错了，重新上传中"))
        await page.locator('div.media-status-content div.tag-inner:has-text("删除")').click()
        await page.get_by_role("button", name="删除", exact=True).click()
        await self.upload_video_file(page, self.file_path)

    async def set_thumbnail(self, page: Page) -> None:
        if not self.thumbnail_path:
            return

        tencent_logger.info(_msg("🖼️", "小人准备设置封面"))

        cover_entry_selectors = [
            'div.vertical-cover-wrap:has-text("个人主页卡片"):has-text("3:4")',
            'div.vertical-cover-wrap:has-text("3:4")',
            'div.vertical-cover-wrap:has-text("个人主页卡片")',
        ]
        for selector in cover_entry_selectors:
            cover_entry = page.locator(selector).first
            try:
                if not await cover_entry.count():
                    continue
                await cover_entry.wait_for(state="visible", timeout=3000)
                await cover_entry.click()
                await page.wait_for_timeout(500)
                break
            except Exception:
                continue

        cover_dialog = page.locator("div.weui-desktop-dialog").filter(has_text="编辑个人主页卡片").first
        if not await cover_dialog.count():
            tencent_logger.info(_msg("🧍", "当前页面没有出现封面编辑弹窗，小人先跳过自定义封面"))
            return

        try:
            await cover_dialog.wait_for(state="visible", timeout=5000)
        except Exception:
            tencent_logger.warning(_msg("😵", "封面编辑弹窗暂时不可见，这次先跳过自定义封面"))
            return

        file_input = cover_dialog.locator('.single-cover-uploader-wrap input[type="file"]').first
        await file_input.wait_for(state="attached", timeout=10000)
        await file_input.set_input_files(self.thumbnail_path)
        await page.wait_for_timeout(1000)

        crop_dialog = page.locator("div.weui-desktop-dialog").filter(has_text="裁剪封面图").first
        if await crop_dialog.count():
            try:
                await crop_dialog.wait_for(state="visible", timeout=10000)
                crop_confirm_button = crop_dialog.locator(
                    'div.weui-desktop-dialog__ft button.weui-desktop-btn_primary:has-text("确定")'
                ).first
                if await crop_confirm_button.count():
                    await crop_confirm_button.wait_for(state="visible", timeout=5000)
                    await crop_confirm_button.click()
                    await page.wait_for_timeout(1000)
            except Exception as exc:
                tencent_logger.warning(_msg("😵", f"封面裁剪确认时出错，小人继续尝试保存主弹窗: {exc}"))

        confirm_button = cover_dialog.locator(
            'div.weui-desktop-dialog__ft button.weui-desktop-btn_primary:has-text("确认")'
        ).first
        await confirm_button.wait_for(state="visible", timeout=10000)
        await confirm_button.click()
        tencent_logger.success(_msg("🥳", "封面已经设置完成"))

    async def prepare_video_for_publish(self, page: Page) -> None:
        await self.fill_title_and_tags(page)
        await self.fill_description(page)
        await self.apply_original_statement(page)

    async def attach_goods(self, page: Page) -> None:
        """挂载微信橱窗商品。搜不到商品时抛异常，中断上传流程。"""
        if not self.goods_id:
            return

        tencent_logger.info(_msg("🛍️", f"开始挂载商品: {self.goods_id}"))

        # 步骤 1: 点击「链接」下拉，选择「商品」
        link_wrap = page.locator('.post-with-link .link-display-wrap').first
        await link_wrap.wait_for(state="visible", timeout=10000)
        await link_wrap.click()
        await page.wait_for_timeout(500)

        goods_option = page.locator('.link-option-item').filter(has_text="商品").first
        await goods_option.wait_for(state="visible", timeout=5000)
        await goods_option.click()
        await page.wait_for_timeout(1500)

        # 步骤 2: 检测「无法添加商品」阻断弹窗（每日上限等）
        forbid_dialog = page.locator('div.weui-desktop-dialog').filter(has_text="无法添加商品").first
        if await forbid_dialog.count() and await forbid_dialog.is_visible():
            msg_el = forbid_dialog.locator('.forbid-dialog-wordings').first
            detail = "视频号返回: 无法添加商品到视频"
            if await msg_el.count():
                detail = (await msg_el.inner_text()).strip() or detail
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"/tmp/tencent_goods_forbid_{self.goods_id}_{ts}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            tencent_logger.error(_msg("❌", f"商品挂载被视频号拒绝: {detail}"))
            raise RuntimeError(
                f"商品挂载被视频号拒绝: {detail} 截图: {screenshot_path}"
            )

        # 步骤 3: 点击「选择需要添加的商品」触发橱窗选择弹窗
        product_trigger = page.locator('text=选择需要添加的商品').first
        await product_trigger.wait_for(state="visible", timeout=10000)
        await product_trigger.click()
        await page.wait_for_timeout(2000)

        # 步骤 4: 在「从橱窗添加商品」弹窗内搜索商品 ID
        dialog = page.locator('div.weui-desktop-dialog').filter(has_text="从橱窗添加商品").first
        await dialog.wait_for(state="visible", timeout=10000)

        search_input = dialog.locator('input[placeholder*="商品名称/编码"]').first
        await search_input.wait_for(state="visible", timeout=5000)
        await search_input.fill(self.goods_id)
        await page.wait_for_timeout(300)

        await dialog.locator('button:has-text("筛选")').first.click()
        await page.wait_for_timeout(2500)

        # 步骤 5: 检测空态——没搜到就中断
        placeholder = dialog.locator('.ant-table-placeholder').first
        rows = dialog.locator('table.ant-table-body-outer table tbody.ant-table-tbody > tr[data-row-key], table tbody.ant-table-tbody > tr.ant-table-row')
        row_count = await rows.count()
        placeholder_visible = bool(await placeholder.count()) and await placeholder.is_visible()

        if placeholder_visible or row_count == 0:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"/tmp/tencent_goods_notfound_{self.goods_id}_{ts}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            tencent_logger.error(_msg("❌", f"商品 {self.goods_id} 未找到，截图: {screenshot_path}"))
            raise RuntimeError(
                f"商品 {self.goods_id} 在橱窗中未找到，已中断上传流程。"
                f"请先到微信小店/带货助手-选品广场确认该商品已关联。截图: {screenshot_path}"
            )

        # 步骤 6: 勾选第一行的 radio（antd 自定义 radio，点 cell 即可）
        first_row = rows.first
        selection_cell = first_row.locator('td.ant-table-selection-column').first
        if await selection_cell.count():
            await selection_cell.click()
        else:
            # fallback: 点整行
            await first_row.click()
        await page.wait_for_timeout(500)

        # 步骤 7: 点右下角「添加(1)」按钮
        add_button = dialog.locator('button').filter(has_text="添加").first
        add_text = (await add_button.inner_text()).strip()
        if "(0)" in add_text or add_text == "添加":
            # 没有成功勾选（按钮没更新成 添加(1)）
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"/tmp/tencent_goods_notselected_{self.goods_id}_{ts}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            tencent_logger.error(_msg("❌", f"商品勾选失败，按钮文本='{add_text}', 截图: {screenshot_path}"))
            raise RuntimeError(
                f"商品 {self.goods_id} 勾选失败（添加按钮仍显示 '{add_text}'），已中断上传流程。截图: {screenshot_path}"
            )

        await add_button.click()
        await page.wait_for_timeout(1500)
        tencent_logger.success(_msg("🛍️", f"商品 {self.goods_id} 挂载成功"))

    async def upload(self, playwright: Playwright) -> None:
        tencent_logger.info(_msg("🧍", "小人先检查 cookie、视频文件和发布时间"))
        await self.validate_upload_args()
        tencent_logger.info(_msg("🥳", "上传前检查通过"))

        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=self.headless))
        context = await browser.new_context(storage_state=self.account_file)

        try:
            page = await context.new_page()
            await self.open_upload_page(page)
            tencent_logger.info(_msg("🏃", f"小人开始搬运视频: {self.title}"))

            await self.upload_video_file(page, self.file_path)
            await self.prepare_video_for_publish(page)
            await self.wait_for_upload_complete(page)
            await self.set_thumbnail(page)
            await self.attach_goods(page)

            if self.publish_strategy == TENCENT_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
                await self.set_schedule_time_tencent(page, self.publish_date)

            await self.set_short_title(page, self.title, self.short_title)
            await self.submit_publish(page)

            await context.storage_state(path=self.account_file)
            tencent_logger.success(_msg("🥳", "cookie 更新完毕"))
        finally:
            await context.close()
            await browser.close()

    async def tencent_upload_video(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.tencent_upload_video()


class TencentNote(TencentBaseUploader):
    def __init__(
        self,
        image_paths,
        note,
        tags,
        publish_date: datetime | int,
        account_file,
        title: str | None = None,
        publish_strategy: str = TENCENT_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
        is_draft: bool = False,
    ):
        super().__init__(
            publish_date=publish_date,
            account_file=account_file,
            publish_strategy=publish_strategy,
            debug=debug,
            headless=headless,
        )
        self.image_paths = image_paths
        self.note = note or ""
        self.title = title or (self.note[:30] if self.note else "")
        self.tags = tags or []
        self.is_draft = is_draft

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("图文模式下，title 是必须的")
        if not self.image_paths:
            raise ValueError("图文模式下，图片是必须的")

        if isinstance(self.image_paths, (str, Path)):
            self.image_paths = [self.image_paths]

        normalized_image_paths = []
        for image_path in self.image_paths:
            normalized_image_paths.append(str(self.validate_image_file(image_path)))
        self.image_paths = normalized_image_paths

    async def switch_to_note_mode(self, page: Page) -> None:
        raise NotImplementedError("请在 TencentNote.switch_to_note_mode 中补充视频号切换到图文发布模式的逻辑")

    async def upload_note_images(self, page: Page) -> None:
        raise NotImplementedError("请在 TencentNote.upload_note_images 中补充视频号图文图片上传逻辑")

    async def fill_note_title_and_tags(self, page: Page) -> None:
        raise NotImplementedError("请在 TencentNote.fill_note_title_and_tags 中补充视频号图文标题/话题填写逻辑")

    async def fill_note_body(self, page: Page) -> None:
        return None

    async def prepare_note_for_publish(self, page: Page) -> None:
        await self.fill_note_title_and_tags(page)
        await self.fill_note_body(page)
        await self.apply_collection(page)
        await self.apply_original_statement(page)

    async def upload_note_content(self, page: Page) -> None:
        await self.switch_to_note_mode(page)
        await self.upload_note_images(page)
        await self.prepare_note_for_publish(page)

    async def upload(self, playwright: Playwright) -> None:
        tencent_logger.info(_msg("🧍", "小人先检查 cookie、图文图片和发布时间"))
        await self.validate_upload_args()
        tencent_logger.info(_msg("🥳", "图文上传前检查通过"))

        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=self.headless))
        context = await browser.new_context(storage_state=self.account_file)
        context = await set_init_script(context)

        try:
            page = await context.new_page()
            await self.open_upload_page(page)
            tencent_logger.info(_msg("🏃", f"小人开始搬运图文，共 {len(self.image_paths)} 张图片"))

            await self.upload_note_content(page)

            if self.publish_strategy == TENCENT_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
                await self.set_schedule_time_tencent(page, self.publish_date)

            await self.submit_publish(page)

            await context.storage_state(path=self.account_file)
            tencent_logger.success(_msg("🥳", "cookie 更新完毕"))
        finally:
            await context.close()
            await browser.close()

    async def tencent_upload_note(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.tencent_upload_note()
