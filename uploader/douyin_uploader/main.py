# -*- coding: utf-8 -*-
from datetime import datetime

import asyncio
import inspect
import json
import os
import sys
from pathlib import Path

from patchright.async_api import Page
from patchright.async_api import Playwright
from patchright.async_api import async_playwright


def _snapshot_chrome_hwnds() -> set:
    """
    Windows only: 快照当前所有 Chrome_WidgetWin_1 窗口句柄集合。
    launch 前调用，用于之后取差集定位新窗口。非 Windows 返回空集合。
    """
    if sys.platform != "win32":
        return set()
    try:
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        found = []
        def _cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(hwnd, buf, 64)
                if buf.value == "Chrome_WidgetWin_1":
                    found.append(hwnd)
            return True
        user32.EnumWindows(WNDENUMPROC(_cb), 0)
        return set(found)
    except Exception:
        return set()


async def _reposition_browser_window(existing_hwnds: set, retries: int = 8, width: int = 960, height: int = 680, x: int = 50, y: int = 50):
    """
    Windows only: launch 后枚举 Chrome_WidgetWin_1 窗口，取与 existing_hwnds 的差集，
    定位新开的 Chrome 窗口并调整大小和位置。
    异步执行，不阻塞主流程。非 Windows 平台静默跳过。
    """
    if sys.platform != "win32":
        return

    try:
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.WinDLL('user32', use_last_error=True)
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

        new_hwnds = []

        def _cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(hwnd, buf, 64)
                if buf.value == "Chrome_WidgetWin_1" and hwnd not in existing_hwnds:
                    new_hwnds.append(hwnd)
            return True

        cb = WNDENUMPROC(_cb)

        for _ in range(retries):
            new_hwnds.clear()
            user32.EnumWindows(cb, 0)
            if new_hwnds:
                break
            await asyncio.sleep(1)

        if not new_hwnds:
            douyin_logger.debug(_msg("🪟", "未找到新 Chrome 窗口，跳过窗口调整"))
            return

        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        for hwnd in new_hwnds:
            user32.SetWindowPos(hwnd, 0, x, y, width, height, SWP_NOZORDER | SWP_NOACTIVATE)

        douyin_logger.debug(_msg("🪟", f"浏览器窗口已调整: {width}x{height} @ ({x},{y})"))

    except Exception as e:
        douyin_logger.debug(_msg("🪟", f"窗口调整失败（非关键）: {e}"))

from utils.config import DEBUG_MODE, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.login_qrcode import build_login_qrcode_path
from utils.login_qrcode import decode_qrcode_from_path
from utils.login_qrcode import print_terminal_qrcode
from utils.login_qrcode import remove_qrcode_file
from utils.login_qrcode import save_data_url_image
from utils.log import douyin_logger

DOUYIN_PUBLISH_STRATEGY_IMMEDIATE = "immediate"
DOUYIN_PUBLISH_STRATEGY_SCHEDULED = "scheduled"

_VERIFY_CODE_SUFFIX = "_verify_code.json"


def _verify_code_path(account_file: str) -> Path:
    return Path(account_file).parent / (Path(account_file).stem + _VERIFY_CODE_SUFFIX)


async def _handle_sms_verify(page: Page, account_file: str) -> bool:
    """
    检测并处理抖音短信验证码弹窗。
    检测到弹窗时：点"获取验证码" → stdout打印 [VERIFY_REQUIRED] 通知 Agent → 轮询 code 文件 → 填入 → 点验证。
    返回 True 表示已处理验证码弹窗（无论成功失败），False 表示未检测到弹窗。
    """
    # 用 second-verify-panel 检测，比外层容器更可靠（外层可能常驻DOM）
    verify_panel = page.locator("div.second-verify-panel")
    if not await verify_panel.count() or not await verify_panel.is_visible():
        return False

    # 弹窗内容直接在 second-verify-panel 下，不在 article 里（article count=0）
    # 所有子元素从 page 全局查找

    douyin_logger.info(_msg("📱", "检测到短信验证码弹窗，小人去点获取验证码"))

    # 提取手机号（用于提示用户）
    # class: uc-ui-verify_sms-verify_content_desc（全下划线）
    phone_hint = ""
    try:
        # 从 page 全局找，panel 下嵌套结构复杂
        desc = page.locator("p.uc-ui-verify_sms-verify_content_desc").first
        if await desc.count():
            phone_hint = (await desc.inner_text()).strip()
    except Exception:
        pass

    # 点"获取验证码"：父级 div.uc-ui-input_right（下划线），p 只有 uc-ui-typography_description
    send_btn = page.locator("div.uc-ui-input_right p.uc-ui-typography_description").first
    if await send_btn.count() and await send_btn.is_visible():
        await send_btn.click()
        douyin_logger.info(_msg("📤", "已点击获取验证码"))
        await asyncio.sleep(1)

    # stdout 打印机器可读行，Agent 实时读到后立刻问用户要验证码
    print(f"[VERIFY_REQUIRED] phone={phone_hint} account={Path(account_file).stem}", flush=True)
    douyin_logger.info(_msg("⏳", "等待 Agent 传入验证码..."))

    # 轮询等待 code 文件出现，最多等 5 分钟
    # 同时检测弹窗是否还在，消失说明超时自动关闭了（抖音弹窗有计时器），
    # 此时 input 已不可用，需要重新触发弹窗（下一轮 while True 会重新检测并点发布）
    code_path = _verify_code_path(account_file)
    code_path.unlink(missing_ok=True)
    for _ in range(150):
        await asyncio.sleep(2)
        if code_path.exists():
            break
        # 弹窗被关闭（抖音超时）→ 放弃本次，外层 while True 会重新发布并触发弹窗
        if not await verify_panel.is_visible():
            douyin_logger.warning(_msg("⚠️", "弹窗超时自动关闭，等待重新触发"))
            return False
    else:
        douyin_logger.error(_msg("😵", "等待验证码超时（5分钟），小人放弃了"))
        return True

    # 读取验证码
    try:
        code_data = json.loads(code_path.read_text(encoding="utf-8"))
        code = str(code_data.get("code", "")).strip()
    except Exception as e:
        douyin_logger.error(_msg("😵", f"读取验证码文件失败: {e}"))
        code_path.unlink(missing_ok=True)
        return True

    code_path.unlink(missing_ok=True)

    if not code:
        douyin_logger.error(_msg("😵", "验证码为空，跳过验证"))
        return True

    douyin_logger.info(_msg("🔢", "收到验证码，小人开始填入"))

    # 填入验证码
    # 注意：input 在点"获取验证码"后才渲染进DOM，需要等待出现
    # 优先用 placeholder 匹配，备用 type=number+maxlength=6
    code_input = None
    for sel in [
        "input[placeholder='请输入验证码']",
        'input[type="number"][maxlength="6"]',
        'input[maxlength="6"]',
    ]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=5000)
            code_input = loc
            douyin_logger.info(_msg("🔍", f"找到验证码输入框: {sel}"))
            break
        except Exception:
            pass

    if code_input is None:
        douyin_logger.error(_msg("😵", "找不到验证码输入框，跳过验证"))
        return True

    await code_input.click()
    # type=number 的 input 用 fill 可能不触发 React onChange，改用逐字 type
    await code_input.press_sequentially(code, delay=80)
    douyin_logger.info(_msg("⌨️", f"验证码已输入: {code}"))
    await asyncio.sleep(0.3)

    # 点"验证"按钮（等 disabled class 消失，最多5秒）
    # class: uc-ui-verify_sms-verify_button primary default uc-ui-button [disabled]
    # 取消按钮含 second，验证按钮不含 second，用 .default 区分
    # 取消按钮含 second class，验证按钮不含 second，用 :not(.second) 精确排除
    verify_btn = page.locator("div.uc-ui-verify_sms-verify_button.primary.default.uc-ui-button:not(.second)").first
    for i in range(10):
        if not await verify_btn.count():
            douyin_logger.warning(_msg("⚠️", "验证按钮消失，弹窗可能已关闭"))
            break
        btn_class = await verify_btn.get_attribute("class") or ""
        douyin_logger.info(_msg("🔎", f"验证按钮 class [{i}]: {btn_class}"))
        if "disabled" not in btn_class:
            await verify_btn.click()
            douyin_logger.info(_msg("✅", "已点击验证按钮"))
            break
        await asyncio.sleep(0.5)
    else:
        douyin_logger.warning(_msg("⚠️", "验证按钮一直是 disabled，尝试强制点击"))
        await verify_btn.click(force=True)

    douyin_logger.info(_msg("✅", "验证码已提交，等待验证结果"))

    # 等弹窗消失，最多等10秒，避免 continue 回来再次触发
    for _ in range(20):
        await asyncio.sleep(0.5)
        if not await verify_panel.is_visible():
            douyin_logger.info(_msg("✅", "弹窗已关闭"))
            break
    else:
        douyin_logger.warning(_msg("⚠️", "弹窗未消失，可能验证失败"))

    return True


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


async def _emit_qrcode_callback(qrcode_callback, payload: dict):
    if not qrcode_callback:
        return

    callback_result = qrcode_callback(payload)
    if inspect.isawaitable(callback_result):
        await callback_result


def _build_login_result(success: bool, status: str, message: str, account_file: str, qrcode: dict | None = None, current_url: str = "") -> dict:
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "qrcode": qrcode,
        "current_url": current_url,
    }


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, channel="chrome")
        try:
            context = await browser.new_context(storage_state=account_file)
            context = await set_init_script(context)
            page = await context.new_page()
            await page.goto("https://creator.douyin.com/creator-micro/content/upload")
            try:
                await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload", timeout=5000)
            except Exception:
                return False

            if await page.get_by_text("手机号登录").count() or await page.get_by_text("扫码登录").count():
                return False

            return True
        finally:
            await browser.close()


async def douyin_setup(account_file, handle=False, return_detail=False, qrcode_callback=None, headless: bool = LOCAL_CHROME_HEADLESS):
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie文件不存在或已失效", account_file)
            return result if return_detail else False
        douyin_logger.info(_msg("🥹", "cookie 失效了，准备打开浏览器重新登录"))
        result = await douyin_cookie_gen(account_file, qrcode_callback=qrcode_callback, headless=headless)
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie有效", account_file)
    return result if return_detail else True


async def _extract_douyin_qrcode_src(page: Page) -> str:
    scan_login_tab = page.get_by_text("扫码登录", exact=True).first
    await scan_login_tab.wait_for(timeout=30000)

    qrcode_img = (
        scan_login_tab
        .locator("..")
        .locator("xpath=following-sibling::div[1]")
        .locator('img[aria-label="二维码"]')
        .first
    )

    if not await qrcode_img.count():
        qrcode_img = page.get_by_role("img", name="二维码").first

    await qrcode_img.wait_for(state="visible", timeout=30000)
    src = await qrcode_img.get_attribute("src")
    if not src:
        raise RuntimeError("未获取到抖音登录二维码地址")

    return src


async def _save_douyin_qrcode(page: Page, account_file: str, previous_qrcode_path: Path | None = None, qrcode_callback=None) -> dict:
    qrcode_src = await _extract_douyin_qrcode_src(page)
    qrcode_path = save_data_url_image(qrcode_src, build_login_qrcode_path(account_file))
    if previous_qrcode_path and previous_qrcode_path != qrcode_path:
        if remove_qrcode_file(previous_qrcode_path):
            douyin_logger.info(_msg("🧹", f"临时二维码文件已清理: {previous_qrcode_path}"))
    douyin_logger.info(_msg("🖼️", f"二维码已经准备好啦，已保存到: {qrcode_path}"))
    qrcode_content = decode_qrcode_from_path(qrcode_path)
    if qrcode_content:
        print_terminal_qrcode(qrcode_content, qrcode_path, "抖音APP")
    else:
        douyin_logger.warning(_msg("😵", f"终端没法完整显示二维码，请打开 {qrcode_path} 扫码"))
    qrcode_info = {
        "image_path": str(qrcode_path),
        "image_data_url": qrcode_src,
    }
    await _emit_qrcode_callback(qrcode_callback, qrcode_info)
    return qrcode_info


async def _is_douyin_login_completed(page: Page) -> bool:
    if not page.url.startswith("https://creator.douyin.com/creator-micro/home"):
        return False

    login_markers = [
        page.get_by_text("扫码登录", exact=True).first,
        page.get_by_text("手机号登录", exact=True).first,
        page.get_by_text("二维码失效", exact=True).first,
        page.get_by_role("img", name="二维码").first,
    ]

    for marker in login_markers:
        if not await marker.count():
            continue
        try:
            if await marker.is_visible():
                return False
        except Exception:
            continue

    return True


async def _wait_for_douyin_login(page: Page, account_file: str, qrcode_info: dict, qrcode_callback=None, poll_interval: int = 3, max_checks: int = 100) -> dict:
    qrcode_path = Path(qrcode_info["image_path"])
    for _ in range(max_checks):
        if await _is_douyin_login_completed(page):
            douyin_logger.info(_msg("🥳", f"扫码成功，已经跳转到登录后页面: {page.url}"))
            return _build_login_result(True, "success", "抖音扫码登录成功", account_file, qrcode_info, page.url)

        expired_box = page.get_by_text("二维码失效", exact=True).locator("..").first
        if await expired_box.count() and await expired_box.is_visible():
            douyin_logger.warning(_msg("😵", "二维码失效了，小人马上去刷新"))
            await expired_box.click()
            await asyncio.sleep(1)
            qrcode_info = await _save_douyin_qrcode(page, account_file, qrcode_path, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"])

        await asyncio.sleep(poll_interval)

    return _build_login_result(False, "timeout", "等待抖音扫码登录超时", account_file, qrcode_info, page.url)


async def douyin_cookie_gen(
    account_file,
    qrcode_callback=None,
    poll_interval: int = 3,
    max_checks: int = 100,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    async with async_playwright() as playwright:
        _existing_hwnds = _snapshot_chrome_hwnds()
        browser = await playwright.chromium.launch(
            headless=headless,
            channel="chrome",
            args=["--force-device-scale-factor=1"],
        )
        if not headless:
            asyncio.create_task(_reposition_browser_window(_existing_hwnds))
        context = await browser.new_context(
            no_viewport=True,
        )
        context = await set_init_script(context)
        qrcode_path = None
        result = _build_login_result(False, "failed", "抖音登录失败", account_file)
        try:
            page = await context.new_page()
            await page.goto("https://creator.douyin.com/")
            qrcode_info = await _save_douyin_qrcode(page, account_file, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"])
            douyin_logger.info(_msg("🧍", "请扫码，小人正在耐心等待登录完成"))
            result = await _wait_for_douyin_login(
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
                        "抖音扫码流程结束，但 cookie 校验失败",
                        account_file,
                        qrcode_info,
                        page.url,
                    )
        except Exception as exc:
            result = _build_login_result(False, "failed", str(exc), account_file, current_url=page.url if "page" in locals() else "")
        finally:
            if remove_qrcode_file(qrcode_path):
                douyin_logger.info(_msg("🧹", f"临时二维码文件已清理: {qrcode_path}"))
            if not result["success"]:
                douyin_logger.error(_msg("😢", f"登录失败: {result['message']}"))
            await context.close()
            await browser.close()
        return result


class DouYinBaseUploader(BaseVideoUploader):
    def __init__(
        self,
        publish_date: datetime | int,
        account_file,
        publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        self.publish_date = publish_date
        self.account_file = account_file
        self.publish_strategy = publish_strategy
        self.debug = debug
        self.date_format = "%Y年%m月%d日 %H:%M"
        self.local_executable_path = LOCAL_CHROME_PATH
        self.headless = headless

    async def validate_base_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"cookie文件不存在，请先完成抖音登录: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"cookie文件已失效，请先完成抖音登录: {self.account_file}")
        if self.publish_strategy not in {DOUYIN_PUBLISH_STRATEGY_IMMEDIATE, DOUYIN_PUBLISH_STRATEGY_SCHEDULED}:
            raise ValueError(f"不支持的发布策略: {self.publish_strategy}")

        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_SCHEDULED:
            self.publish_date = self.validate_publish_date(self.publish_date)
        else:
            self.publish_date = 0

    async def set_schedule_time_douyin(self, page, publish_date):
        label_element = page.locator("[class^='radio']:has-text('定时发布')")
        await label_element.click()
        await asyncio.sleep(1)
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")

        await asyncio.sleep(1)
        await page.locator('.semi-input[placeholder="日期和时间"]').click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")
        await asyncio.sleep(1)

    async def fill_title_and_description(self, page: Page, title: str, description: str, tags: list[str] | None = None):
        description_section = (
            page.get_by_text("作品描述", exact=True)
            .locator("xpath=ancestor::div[2]")
            .locator("xpath=following-sibling::div[1]")
        )

        title_input = description_section.locator('input[type="text"]').first
        await title_input.wait_for(state="visible", timeout=10000)
        await title_input.fill(title[:30])

        description_editor = description_section.locator('.zone-container[contenteditable="true"]').first
        await description_editor.wait_for(state="visible", timeout=10000)
        await description_editor.click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.press("Delete")
        await page.keyboard.type(description)

        for tag in tags or []:
            await page.keyboard.type(" #" + tag)
            await page.keyboard.press("Space")

    async def set_location(self, page: Page, location: str = ""):
        if not location:
            return
        await page.locator('div.semi-select span:has-text("输入地理位置")').click()
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(2000)
        await page.keyboard.type(location)
        await page.wait_for_selector('div[role="listbox"] [role="option"]', timeout=5000)
        await page.locator('div[role="listbox"] [role="option"]').first.click()

    async def handle_product_dialog(self, page: Page, product_title: str):
        await page.wait_for_timeout(2000)
        await page.wait_for_selector('input[placeholder="请输入商品短标题"]', timeout=10000)
        short_title_input = page.locator('input[placeholder="请输入商品短标题"]')
        if not await short_title_input.count():
            douyin_logger.error(_msg("😵", "没找到商品短标题输入框"))
            return False

        product_title = product_title[:10]
        await short_title_input.fill(product_title)
        await page.wait_for_timeout(1000)

        finish_button = page.locator('button:has-text("完成编辑")')
        if "disabled" not in await finish_button.get_attribute("class"):
            await finish_button.click()
            douyin_logger.debug(_msg("🥳", "已点击“完成编辑”按钮"))
            await page.wait_for_selector(".semi-modal-content", state="hidden", timeout=5000)
            return True

        douyin_logger.error(_msg("😵", "“完成编辑”按钮是灰的，小人先把弹窗关掉"))
        cancel_button = page.locator('button:has-text("取消")')
        if await cancel_button.count():
            await cancel_button.click()
        else:
            close_button = page.locator(".semi-modal-close")
            await close_button.click()
        await page.wait_for_selector(".semi-modal-content", state="hidden", timeout=5000)
        return False

    async def set_product_link(self, page: Page, product_link: str, product_title: str):
        await page.wait_for_timeout(2000)
        try:
            await page.wait_for_selector("text=添加标签", timeout=10000)
            dropdown = page.get_by_text("添加标签").locator("..").locator("..").locator("..").locator(".semi-select").first
            if not await dropdown.count():
                douyin_logger.error(_msg("😵", "没找到标签下拉框"))
                return False
            douyin_logger.debug(_msg("🧍", "找到标签下拉框，小人准备选择“购物车”"))
            await dropdown.click()
            await page.wait_for_selector('[role="listbox"]', timeout=5000)
            await page.locator('[role="option"]:has-text("购物车")').click()
            douyin_logger.debug(_msg("🥳", "已经选中“购物车”"))

            await page.wait_for_selector('input[placeholder="粘贴商品链接"]', timeout=5000)
            input_field = page.locator('input[placeholder="粘贴商品链接"]')
            await input_field.fill(product_link)
            douyin_logger.debug(_msg("🔗", f"商品链接已经填好了: {product_link}"))

            add_button = page.locator('span:has-text("添加链接")')
            button_class = await add_button.get_attribute("class")
            if "disable" in button_class:
                douyin_logger.error(_msg("😵", "“添加链接”按钮现在点不了"))
                return False
            await add_button.click()
            douyin_logger.debug(_msg("🥳", "已点击“添加链接”按钮"))

            await page.wait_for_timeout(2000)
            error_modal = page.locator("text=未搜索到对应商品")
            if await error_modal.count():
                confirm_button = page.locator('button:has-text("确定")')
                await confirm_button.click()
                douyin_logger.error(_msg("😢", "这个商品链接无效"))
                return False

            if not await self.handle_product_dialog(page, product_title):
                return False

            douyin_logger.debug(_msg("🥳", "商品链接设置好了"))
            return True
        except Exception as e:
            douyin_logger.error(_msg("😢", f"设置商品链接时出错: {str(e)}"))
            return False

    async def set_self_declaration(self, page: Page, declaration_text: str = "无需添加自主声明") -> None:
        """设置抖音自主声明，默认选择「无需添加自主声明」。

        抖音新版发布页把自主声明做成一行入口，点击后打开弹窗，弹窗内是单选项。
        该字段可能分批灰度；页面不存在时跳过，存在但选择失败时报错，避免继续误发布。
        """
        douyin_logger.info(_msg("📋", f"小人准备设置自主声明：{declaration_text}"))

        entry = page.get_by_text("自主声明", exact=True).first
        try:
            await entry.wait_for(state="visible", timeout=5000)
        except Exception:
            douyin_logger.info(_msg("📋", "当前页面没有自主声明入口，跳过设置"))
            return

        already_selected = await page.get_by_text(declaration_text, exact=True).count()
        placeholder_visible = False
        try:
            placeholder_visible = await page.get_by_text("请选择自主声明", exact=True).first.is_visible()
        except Exception:
            placeholder_visible = False
        if already_selected and not placeholder_visible:
            douyin_logger.info(_msg("📋", f"自主声明已是：{declaration_text}"))
            return

        clicked = await page.locator("body").evaluate(
            """() => {
              const label = [...document.querySelectorAll('body *')]
                .find(el => (el.innerText || '').trim() === '自主声明');
              if (!label) return 'no_label';

              let node = label;
              for (let i = 0; i < 6 && node; i += 1, node = node.parentElement) {
                const text = node.innerText || '';
                if (text.includes('请选择自主声明') || text.includes('无需添加自主声明')) {
                  node.click();
                  return text.trim().replace(/\s+/g, ' ').slice(0, 120);
                }
              }

              const clickable = label.closest('div');
              if (!clickable) return 'no_clickable';
              clickable.click();
              return 'clicked_label_parent';
            }"""
        )
        if clicked in ("no_label", "no_clickable"):
            raise RuntimeError(f"未找到自主声明入口（{clicked}），页面结构可能已变更")

        dialog = page.locator("div.semi-modal-content:visible, div[role='dialog']:visible").filter(
            has_text="对作品内容添加声明"
        ).first
        try:
            await dialog.wait_for(state="visible", timeout=5000)
        except Exception:
            # 兼容非 semi 弹窗：只要选项已经可见，也继续尝试点击。
            dialog = page.locator("body")

        option = dialog.get_by_text(declaration_text, exact=True).first
        try:
            await option.wait_for(state="visible", timeout=5000)
        except Exception as exc:
            raise RuntimeError(f"自主声明弹窗已打开，但未找到选项：{declaration_text}") from exc

        option_box = await option.bounding_box()
        if not option_box:
            raise RuntimeError(f"无法获取自主声明选项位置：{declaration_text}")

        # Semi Radio 的真实可点击圆点在文案左侧，直接点文案会被相邻 label 拦截，
        # DOM click 又可能不触发 React 状态。这里用鼠标点击圆点坐标，最接近人工操作。
        await page.mouse.click(option_box["x"] - 20, option_box["y"] + option_box["height"] / 2)
        douyin_logger.info(_msg("📋", f"自主声明弹窗选项已点击：{declaration_text}"))

        for _ in range(10):
            is_checked = await dialog.evaluate(
                """(root, text) => {
                  const addon = [...root.querySelectorAll('*')].find(el => (el.innerText || '').trim() === text);
                  if (!addon) return false;
                  const row = addon.parentElement;
                  const prev = addon.previousElementSibling;
                  const input = row?.querySelector('input[type=radio]') || prev?.querySelector('input[type=radio]');
                  const checkedNode = row?.querySelector('.semi-radio-checked') || prev?.matches?.('.semi-radio-checked');
                  return Boolean(input?.checked || checkedNode);
                }""",
                declaration_text,
            )
            if is_checked:
                break
            await asyncio.sleep(0.3)
        else:
            raise RuntimeError(f"自主声明选项点击后未变为选中状态：{declaration_text}")

        confirm_button = dialog.get_by_role("button", name="确定").first
        if not await confirm_button.count():
            confirm_button = page.get_by_role("button", name="确定").last

        for _ in range(10):
            button_class = await confirm_button.get_attribute("class") or ""
            disabled = await confirm_button.get_attribute("disabled")
            if disabled is None and "disabled" not in button_class:
                await confirm_button.click()
                break
            await asyncio.sleep(0.3)
        else:
            await confirm_button.click(force=True)

        try:
            await dialog.wait_for(state="hidden", timeout=5000)
        except Exception as exc:
            raise RuntimeError(f"自主声明确认后弹窗未关闭：{declaration_text}") from exc

        selected = page.get_by_text(declaration_text, exact=True).first
        if not await selected.count() or await page.get_by_text("请选择自主声明", exact=True).first.is_visible():
            raise RuntimeError(f"自主声明选择后未回填：{declaration_text}")

        douyin_logger.success(_msg("📋", f"自主声明已选择：{declaration_text}"))


class DouYinVideo(DouYinBaseUploader):
    def __init__(
        self,
        title,
        file_path,
        tags,
        publish_date: datetime | int,
        account_file,
        thumbnail_landscape_path=None,
        productLink="",
        productTitle="",
        thumbnail_portrait_path=None,
        desc: str | None = None,
        publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
        dry_run: bool = False,
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
        self.tags = tags
        self.thumbnail_landscape_path = thumbnail_landscape_path
        self.thumbnail_portrait_path = thumbnail_portrait_path
        self.productLink = productLink
        self.productTitle = productTitle
        self.desc = desc or ""
        self.dry_run = dry_run

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("视频模式下，title 是必须的")

        self.file_path = str(self.validate_video_file(self.file_path))
        if self.thumbnail_landscape_path:
            self.thumbnail_landscape_path = str(self.validate_image_file(self.thumbnail_landscape_path))
        if self.thumbnail_portrait_path:
            self.thumbnail_portrait_path = str(self.validate_image_file(self.thumbnail_portrait_path))

    async def handle_upload_error(self, page):
        douyin_logger.warning(_msg("😵", "视频上传摔了一跤，小人马上重新上传"))
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def handle_auto_video_cover(self, page):
        if await page.get_by_text("请设置封面后再发布").first.is_visible():
            douyin_logger.info(_msg("🧍", "发布前还得先把封面弄好"))
            recommend_cover = page.locator('[class^="recommendCover-"]').first
            if await recommend_cover.count():
                douyin_logger.info(_msg("🏃", "小人去选第一个推荐封面"))
                try:
                    await recommend_cover.click()
                    await asyncio.sleep(1)
                    confirm_text = "是否确认应用此封面？"
                    if await page.get_by_text(confirm_text).first.is_visible():
                        douyin_logger.info(_msg("🪟", f"弹出确认框了: {confirm_text}"))
                        await page.get_by_role("button", name="确定").click()
                        douyin_logger.info(_msg("🥳", "推荐封面已经应用"))
                        await asyncio.sleep(1)
                    douyin_logger.info(_msg("🥳", "封面选择流程完成"))
                    return True
                except Exception as e:
                    douyin_logger.warning(_msg("😵", f"推荐封面没选成功: {e}"))
        return False

    async def set_thumbnail(self, page: Page):
        if not self.thumbnail_landscape_path and not self.thumbnail_portrait_path:
            return

        douyin_logger.info(_msg("🏃", "小人正在设置视频封面"))
        await page.click('text="选择封面"')
        cover_locator_str = 'div[id*="creator-content-modal"]'
        cover_locator = page.locator(cover_locator_str)
        await page.wait_for_selector(cover_locator_str)

        upload_input = cover_locator.locator("div[class^='semi-upload upload'] >> input.semi-upload-hidden-input")

        if self.thumbnail_landscape_path:
            await page.wait_for_timeout(1000)
            await upload_input.set_input_files(self.thumbnail_landscape_path)
            await page.wait_for_timeout(2000)
            douyin_logger.info(_msg("🖼️", "横版封面上传完成"))

        if self.thumbnail_portrait_path:
            await cover_locator.locator("div[class*='steps'] div").nth(1).click()
            await page.wait_for_timeout(1000)
            await upload_input.set_input_files(self.thumbnail_portrait_path)
            await page.wait_for_timeout(2000)
            douyin_logger.info(_msg("🖼️", "竖版封面上传完成"))

        await cover_locator.locator('button:visible:has-text("完成")').click()
        douyin_logger.info(_msg("🥳", "视频封面设置完成"))
        await page.wait_for_selector("div.extractFooter", state="detached")

    async def upload(self, playwright: Playwright) -> None:
        douyin_logger.info(_msg("🧍", "小人先检查 cookie、视频文件、封面和发布时间"))
        await self.validate_upload_args()
        douyin_logger.info(_msg("🥳", "上传前检查通过"))

        _existing_hwnds = _snapshot_chrome_hwnds()
        browser = await playwright.chromium.launch(headless=self.headless, channel="chrome")
        if not self.headless:
            asyncio.create_task(_reposition_browser_window(_existing_hwnds))
        context = await browser.new_context(
            storage_state=f"{self.account_file}",
            permissions=["geolocation"],
        )
        context = await set_init_script(context)

        page = await context.new_page()
        await page.goto("https://creator.douyin.com/creator-micro/content/upload")
        douyin_logger.info(_msg("🏃", f"小人开始搬运视频: {self.title}.mp4"))
        douyin_logger.info(_msg("🧭", "小人正在赶往上传主页"))
        await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload")
        await page.locator("div[class^='container'] input").set_input_files(self.file_path)

        while True:
            try:
                await page.wait_for_url(
                    "https://creator.douyin.com/creator-micro/content/publish?enter_from=publish_page",
                    timeout=3000,
                )
                douyin_logger.info(_msg("🥳", "已经进入 version_1 发布页面"))
                break
            except Exception:
                try:
                    await page.wait_for_url(
                        "https://creator.douyin.com/creator-micro/content/post/video?enter_from=publish_page",
                        timeout=3000,
                    )
                    douyin_logger.info(_msg("🥳", "已经进入 version_2 发布页面"))
                    break
                except Exception:
                    douyin_logger.debug(_msg("🧍", "还没进到视频发布页面，小人继续等一会"))
                    await asyncio.sleep(0.5)

        await asyncio.sleep(1)
        douyin_logger.info(_msg("✍️", "小人开始填标题、描述和话题"))
        await self.fill_title_and_description(page, self.title, self.desc or self.title, self.tags)
        douyin_logger.info(_msg("🏷️", f"小人一共贴了 {len(self.tags)} 个话题"))

        while True:
            try:
                number = await page.locator('[class^="long-card"] div:has-text("重新上传")').count()
                if number > 0:
                    douyin_logger.success(_msg("🥳", "视频已经传完啦"))
                    break
                douyin_logger.info(_msg("🏃", "小人正在努力上传视频"))
                await asyncio.sleep(2)
                if await page.locator('div.progress-div > div:has-text("上传失败")').count():
                    douyin_logger.error(_msg("😵", "检测到上传失败，小人准备重试"))
                    await self.handle_upload_error(page)
            except Exception:
                douyin_logger.debug(_msg("🧍", "小人还在等视频上传完成"))
                await asyncio.sleep(2)

        if self.productLink and self.productTitle:
            douyin_logger.info(_msg("🛒", "小人正在设置商品链接"))
            await self.set_product_link(page, self.productLink, self.productTitle)
            douyin_logger.info(_msg("🥳", "商品链接设置完成"))

        await self.set_thumbnail(page)
        await self.set_self_declaration(page)

        third_part_element = '[class^="info"] > [class^="first-part"] div div.semi-switch'
        if await page.locator(third_part_element).count():
            if "semi-switch-checked" not in await page.eval_on_selector(third_part_element, "div => div.className"):
                await page.locator(third_part_element).locator("input.semi-switch-native-control").click()

        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time_douyin(page, self.publish_date)

        if self.dry_run:
            screenshot_path = f"/tmp/douyin_dry_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            douyin_logger.info(_msg("🧪", "Dry run 模式：跳过发布，所有基础设置已完成"))
            douyin_logger.info(_msg("📸", f"截图已保存: {screenshot_path}"))
            await context.storage_state(path=self.account_file)
            douyin_logger.success(_msg("🥳", "cookie 更新完毕"))
            await asyncio.sleep(2)
            await context.close()
            await browser.close()
            return

        while True:
            # 优先检测验证码弹窗，移出 try 块避免异常被吞
            if await _handle_sms_verify(page, self.account_file):
                douyin_logger.info(_msg("🏃", "验证完成，小人继续冲刺发布"))
                await asyncio.sleep(1)
                continue

            try:
                publish_button = page.get_by_role("button", name="发布", exact=True)
                if await publish_button.count():
                    await publish_button.click()
                await page.wait_for_url(
                    "https://creator.douyin.com/creator-micro/content/manage**",
                    timeout=3000,
                )
                douyin_logger.success(_msg("🥳", "视频发布成功，小人开心收工"))
                break
            except Exception:
                await self.handle_auto_video_cover(page)
                douyin_logger.info(_msg("🏃", "小人正在冲刺发布视频"))
                if self.debug:
                    await page.screenshot(full_page=True)
                await asyncio.sleep(0.5)

        await context.storage_state(path=self.account_file)
        douyin_logger.success(_msg("🥳", "cookie 更新完毕"))
        await asyncio.sleep(2)
        await context.close()
        await browser.close()

    async def douyin_upload_video(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.douyin_upload_video()


class DouYinNote(DouYinBaseUploader):
    def __init__(
        self,
        image_paths,
        note,
        tags,
        publish_date: datetime | int,
        account_file,
        title: str | None = None,
        publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
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
        self.image_paths = image_paths
        self.note = note or ""
        self.title = title or (self.note[:30] if self.note else "")
        self.tags = tags or []

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("图文模式下，title 是必须的")
        if not self.image_paths:
            raise ValueError("图文模式下，图片是必须的")

        if isinstance(self.image_paths, (str, Path)):
            self.image_paths = [self.image_paths]

        if len(self.image_paths) > 35:
            raise ValueError("图文模式下最多只支持上传 35 张图片")

        normalized_image_paths = []
        for image_path in self.image_paths:
            normalized_image_paths.append(str(self.validate_image_file(image_path)))
        self.image_paths = normalized_image_paths

    async def upload_note_content(self, page: Page) -> None:
        douyin_logger.info(_msg("🏃", f"小人开始搬运图文，共 {len(self.image_paths)} 张图片"))
        douyin_logger.info(_msg("🔀", "小人正在切换到图文发布"))
        await page.get_by_text("发布图文", exact=True).click()
        await page.wait_for_timeout(1000)

        douyin_logger.info(_msg("📤", "小人正在上传图片"))
        await page.locator("div[class^='container'] input[accept*='image']").set_input_files(self.image_paths)

        while True:
            try:
                await page.wait_for_url(
                    "**/creator-micro/content/post/image?**",
                    timeout=3000,
                )
                douyin_logger.info(_msg("🥳", "已经进入图文发布页面"))
                break
            except Exception:
                douyin_logger.debug(_msg("🧍", "小人还在等图片上传完成"))
                await asyncio.sleep(0.5)

        await asyncio.sleep(1)
        douyin_logger.info(_msg("✍️", "小人开始填标题、描述和话题"))
        await self.fill_title_and_description(page, self.title, self.note, self.tags)
        douyin_logger.info(_msg("🏷️", f"小人一共贴了 {len(self.tags)} 个话题"))

        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time_douyin(page, self.publish_date)

        while True:
            try:
                publish_button = page.get_by_role("button", name="发布", exact=True)
                if await publish_button.count():
                    await publish_button.click()
                await page.wait_for_url(
                    "**/creator-micro/content/manage?enter_from=publish**",
                    timeout=3000,
                )
                douyin_logger.success(_msg("🥳", "图文发布成功，小人开心收工"))
                break
            except Exception:
                douyin_logger.info(_msg("🏃", "小人正在冲刺发布图文"))
                await asyncio.sleep(0.5)

    async def upload(self, playwright: Playwright) -> None:
        douyin_logger.info(_msg("🧍", "小人先检查 cookie、图片和发布时间"))
        await self.validate_upload_args()
        douyin_logger.info(_msg("🥳", "图文上传前检查通过"))

        _existing_hwnds = _snapshot_chrome_hwnds()
        browser = await playwright.chromium.launch(headless=self.headless, channel="chrome")
        if not self.headless:
            asyncio.create_task(_reposition_browser_window(_existing_hwnds))
        context = await browser.new_context(
            storage_state=f"{self.account_file}",
            permissions=["geolocation"],
        )
        context = await set_init_script(context)

        upload_success = False
        try:
            page = await context.new_page()
            await page.goto("https://creator.douyin.com/creator-micro/content/upload")
            douyin_logger.info(_msg("🧭", "小人正在赶往图文发布页"))
            await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload")

            await self.upload_note_content(page)
            upload_success = True
        finally:
            if upload_success:
                await context.storage_state(path=self.account_file)
                douyin_logger.success(_msg("🥳", "cookie 更新完毕"))
                await asyncio.sleep(2)
            await context.close()
            await browser.close()

    async def douyin_upload_note(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
