# -*- coding: utf-8 -*-
from datetime import datetime

import asyncio
import inspect
import os
import sys
from pathlib import Path

from patchright.async_api import Page
from patchright.async_api import Playwright
from patchright.async_api import async_playwright

from conf import DEBUG_MODE, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.log import pdd_logger

PDD_LOGIN_URL = "https://mms.pinduoduo.com/login/"
PDD_MMS_HOME_URL = "https://mms.pinduoduo.com/home"
PDD_VIDEO_PUBLISH_URL = "https://live.pinduoduo.com/n-creator/video/home?from=mms"
PDD_PUBLISH_STRATEGY_IMMEDIATE = "immediate"
PDD_PUBLISH_STRATEGY_SCHEDULED = "scheduled"


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


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
    current_url: str = "",
) -> dict:
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "current_url": current_url,
    }


async def cookie_auth(account_file):
    """
    验证拼多多 cookie 是否有效。
    加载 storage_state 访问 mms 后台首页，如果被重定向到登录页则 cookie 失效。

    注意：拼多多登录态在 mms.pinduoduo.com 域，视频发布在 live.pinduoduo.com 域。
    cookie_auth 只验证 mms 域的登录态；上传时需先访问 mms 激活 session，
    再跳转 live 域（浏览器自动走 SSO）。
    """
    async with async_playwright() as playwright:
        if LOCAL_CHROME_PATH:
            browser = await playwright.chromium.launch(headless=True, executable_path=LOCAL_CHROME_PATH)
        else:
            browser = await playwright.chromium.launch(headless=True, channel="chrome")
        try:
            context = await browser.new_context(storage_state=account_file)
            context = await set_init_script(context)
            page = await context.new_page()
            await page.goto(PDD_MMS_HOME_URL)
            await asyncio.sleep(3)

            # 判断是否被重定向到登录页
            current_url = page.url
            if "login" in current_url:
                return False

            return True
        except Exception as exc:
            pdd_logger.warning(_msg("😵", f"cookie 校验时出错，按失效处理: {exc}"))
            return False
        finally:
            await browser.close()


async def pdd_setup(
    account_file,
    handle=False,
    return_detail=False,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    """
    检查拼多多 cookie 有效性，失效且 handle=True 时走手动登录流程。
    """
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie文件不存在或已失效", account_file)
            return result if return_detail else False
        pdd_logger.info(_msg("🥹", "cookie 失效了，准备打开浏览器让用户手动登录"))
        result = await pdd_cookie_gen(account_file, headless=headless)
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie有效", account_file)
    return result if return_detail else True


async def pdd_cookie_gen(
    account_file,
    headless: bool = LOCAL_CHROME_HEADLESS,
    poll_interval: int = 3,
    max_checks: int = 200,
):
    """
    打开拼多多登录页，等待用户手动完成登录（扫码或账号密码），
    登录成功后保存 cookie。

    不做任何自动化登录操作，仅打开页面并等待。
    """
    async with async_playwright() as playwright:
        if LOCAL_CHROME_PATH:
            browser = await playwright.chromium.launch(headless=headless, executable_path=LOCAL_CHROME_PATH)
        else:
            browser = await playwright.chromium.launch(
                headless=headless,
                channel="chrome",
            )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        context = await set_init_script(context)
        result = _build_login_result(False, "failed", "拼多多登录失败", account_file)
        try:
            page = await context.new_page()
            await page.goto(PDD_LOGIN_URL)
            pdd_logger.info(_msg("🧍", "已打开拼多多登录页面，请在浏览器中完成登录"))

            # 轮询等待用户完成登录：检测 URL 变化离开登录页
            for _ in range(max_checks):
                current_url = page.url
                # 登录成功后会跳转离开 /login/ 页面
                if "login" not in current_url and "mms.pinduoduo.com/login" not in current_url:
                    pdd_logger.info(_msg("🥳", f"检测到页面已跳转: {current_url}"))
                    break
                await asyncio.sleep(poll_interval)
            else:
                result = _build_login_result(
                    False, "timeout", "等待拼多多登录超时", account_file, page.url
                )
                return result

            # 等几秒让 cookie 完全写入
            await asyncio.sleep(3)
            await context.storage_state(path=account_file)
            pdd_logger.info(_msg("💾", f"cookie 已保存: {account_file}"))

            # 验证保存的 cookie 是否有效
            if await cookie_auth(account_file):
                pdd_logger.success(_msg("🥳", "拼多多登录成功，cookie 验证通过"))
                result = _build_login_result(
                    True, "success", "拼多多登录成功", account_file, page.url
                )
            else:
                pdd_logger.error(_msg("😢", "拼多多登录流程结束，但 cookie 校验失败"))
                result = _build_login_result(
                    False, "cookie_invalid", "拼多多登录流程结束，但 cookie 校验失败",
                    account_file, page.url,
                )
        except Exception as exc:
            result = _build_login_result(
                False, "failed", str(exc), account_file,
                current_url=page.url if "page" in locals() else "",
            )
        finally:
            if not result["success"]:
                pdd_logger.error(_msg("😢", f"登录失败: {result['message']}"))
            await context.close()
            await browser.close()
        return result


class PDDBaseUploader(BaseVideoUploader):
    def __init__(
        self,
        publish_date: datetime | int,
        account_file,
        publish_strategy: str = PDD_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        self.publish_date = publish_date
        self.account_file = account_file
        self.publish_strategy = publish_strategy
        self.debug = debug
        self.headless = headless
        self.local_executable_path = LOCAL_CHROME_PATH
        self.date_format = "%Y-%m-%d %H:%M"

    async def validate_base_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"cookie文件不存在，请先完成拼多多登录: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"cookie文件已失效，请先完成拼多多登录: {self.account_file}")

        if self.publish_strategy not in {PDD_PUBLISH_STRATEGY_IMMEDIATE, PDD_PUBLISH_STRATEGY_SCHEDULED}:
            raise ValueError(f"不支持的发布策略: {self.publish_strategy}")

        if self.publish_strategy == PDD_PUBLISH_STRATEGY_SCHEDULED:
            # 拼多多定时发布区域只在添加商品后才渲染，必须同时提供 goods_id
            goods_id = getattr(self, "goods_id", "")
            if not goods_id:
                raise ValueError(
                    "定时发布必须同时提供 --goods-id：拼多多定时发布选项只有在关联商品后才会出现"
                )
            self.publish_date = self.validate_publish_date(self.publish_date)
        else:
            self.publish_date = 0


class PDDVideo(PDDBaseUploader):
    def __init__(
        self,
        file_path,
        tags,
        publish_date: datetime | int,
        account_file,
        desc: str | None = None,
        goods_id: str | None = None,
        publish_strategy: str = PDD_PUBLISH_STRATEGY_IMMEDIATE,
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
        self.file_path = file_path
        self.tags = tags or []
        self.desc = desc or ""
        self.goods_id = goods_id or ""
        self.dry_run = dry_run

    async def validate_upload_args(self):
        await self.validate_base_args()
        self.file_path = str(self.validate_video_file(self.file_path))

    async def _wait_for_upload_complete(self, page: Page, max_retries: int = 120):
        """等待视频上传完成，检测'视频上传成功'文案出现。"""
        for i in range(max_retries):
            success_text = page.get_by_text("视频上传成功", exact=False)
            if await success_text.count():
                pdd_logger.success(_msg("🥳", "视频已经传完啦"))
                return

            if i % 10 == 0:
                pdd_logger.info(_msg("🏃", "小人正在努力上传视频"))

            await asyncio.sleep(2)

        raise RuntimeError("视频上传超时，小人等不下去了")

    async def _fill_description(self, page: Page):
        """填写视频描述到 sabo 编辑器。"""
        if not self.desc:
            return
        editor = page.locator('div.sabo-root[contenteditable="true"]').first
        await editor.wait_for(state="visible", timeout=10000)
        await editor.click()
        await page.keyboard.press("Meta+KeyA")
        await page.keyboard.press("Delete")
        await page.keyboard.type(self.desc)
        pdd_logger.info(_msg("✍️", f"视频描述已填写: {self.desc[:30]}"))

    async def _add_tags(self, page: Page):
        """在编辑器中添加话题标签。"""
        if not self.tags:
            return

        editor = page.locator('div.sabo-root[contenteditable="true"]').first
        await editor.click()
        # 移到末尾
        await page.keyboard.press("End")

        for index, tag in enumerate(self.tags, start=1):
            pdd_logger.info(_msg("🏷️", f"小人正在添加第 {index} 个话题: #{tag}"))
            await page.keyboard.type(f" #{tag}")
            await asyncio.sleep(1)
            # 等话题建议弹出并消失，或直接按空格确认
            await page.keyboard.press("Space")
            await asyncio.sleep(1)

        pdd_logger.info(_msg("🏷️", f"小人一共贴了 {len(self.tags)} 个话题"))

    async def _add_goods(self, page: Page):
        """通过商品ID添加推广商品。"""
        if not self.goods_id:
            return

        pdd_logger.info(_msg("🛒", f"小人准备添加商品: {self.goods_id}"))

        # 点击"添加商品"按钮
        add_goods_btn = page.get_by_text("添加商品", exact=True).first
        await add_goods_btn.wait_for(state="visible", timeout=10000)
        await add_goods_btn.click()
        await asyncio.sleep(2)

        # 等待弹窗出现
        modal = page.locator('div[data-testid="beast-core-modal"]')
        await modal.wait_for(state="visible", timeout=10000)

        # 切到"商品ID" tab
        goods_id_tab = modal.locator(
            'div[data-testid="beast-core-tab-itemLabel"]:has-text("商品ID")'
        ).first
        await goods_id_tab.click()
        await asyncio.sleep(1)
        pdd_logger.info(_msg("🔀", "已切到商品ID搜索"))

        # 填入商品ID
        id_input = modal.locator(
            'input[data-testid="beast-core-inputNumber-htmlInput"]'
        ).first
        await id_input.wait_for(state="visible", timeout=5000)
        await id_input.fill(self.goods_id)
        await asyncio.sleep(1)

        await asyncio.sleep(1)

        # 商品ID 模式：填完ID直接点"下一步"
        # 用页面级文字定位，不依赖 testid，兼容页面改版
        next_btn = page.get_by_role("button", name="下一步").first
        await next_btn.wait_for(state="visible", timeout=8000)
        await next_btn.click()
        pdd_logger.info(_msg("🛒", "已点击下一步"))
        await asyncio.sleep(3)

        # 处理可能的第二步确认弹窗
        # 检查弹窗是否还在，如果还在可能有确认步骤
        if await modal.is_visible():
            confirm_btn = page.get_by_role("button", name="确认").first
            if not await confirm_btn.count():
                confirm_btn = page.get_by_role("button", name="下一步").first
            if await confirm_btn.count() and await confirm_btn.is_visible():
                await confirm_btn.click()
                pdd_logger.info(_msg("🛒", "已确认商品选择"))
                await asyncio.sleep(2)

        # 等待弹窗关闭：商品ID正确且添加成功时弹窗会关闭；未关闭则中断，避免误发布
        try:
            await modal.wait_for(state="hidden", timeout=10000)
        except Exception as exc:
            screenshot_path = f"/tmp/pdd_goods_add_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            pdd_logger.info(_msg("📸", f"商品添加失败现场截图已保存: {screenshot_path}"))
            raise ValueError(f"商品添加失败，请检查商品ID是否正确: {self.goods_id}") from exc

        pdd_logger.success(_msg("🛒", f"商品 {self.goods_id} 添加完成"))

    async def _set_content_declaration(self, page: Page):
        """设置必填的内容声明下拉，默认选择「内容无需标注」。

        实测 DOM（2026-05-26）：
        - 入口容器：class 包含 ContentDeclaration_statement
        - 下拉入口：data-testid="beast-core-select" / beast-core-select-header / input[placeholder="请选择"]
        - 选项节点：class 包含 ContentDeclaration_title
        """
        pdd_logger.info(_msg("📌", "小人准备设置内容声明"))

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

        statement = page.locator('[class*="ContentDeclaration_statement"]').first
        if await statement.count() and await statement.is_visible():
            dropdown_candidates = [
                statement.locator('[data-testid="beast-core-select"]').first,
                statement.locator('[data-testid="beast-core-select-header"]').first,
                statement.locator('input[placeholder="请选择"]').first,
            ]
        else:
            # 兼容旧结构：内容声明区域未使用 ContentDeclaration_statement 类名时，退回到标题附近。
            dropdown_candidates = [
                page.locator('div:has-text("内容声明")').locator('[data-testid="beast-core-select"]').last,
                page.locator('div:has-text("内容声明")').locator('input[placeholder="请选择"]').last,
                page.locator('input[placeholder="请选择"]').last,
            ]

        dropdown = None
        for candidate in dropdown_candidates:
            if await candidate.count() and await candidate.is_visible():
                dropdown = candidate
                break

        if dropdown is None:
            raise RuntimeError("未找到内容声明下拉入口")

        await dropdown.click()
        await asyncio.sleep(1)

        # PDD 当前版本下拉选项 class 包含 ContentDeclaration_title；
        # 有些场景仍包在 beast-core-portal 中，有些场景截图显示 portal testid 不存在，
        # 因此不要依赖 portal，只限定内容声明专属选项 class，避免误点上方 radio 的 Option 容器。
        option = page.locator('div[class*="ContentDeclaration_title"]').filter(
            has_text="内容无需标注"
        ).first
        await option.wait_for(state="visible", timeout=5000)

        selected_text = (await option.inner_text()).strip()
        await option.click()
        await asyncio.sleep(1)

        # 校验不能仍停留在“请选择”。
        if await statement.count():
            current_text = (await statement.inner_text()).strip()
            if "请选择" in current_text and "内容无需标注" not in current_text:
                raise RuntimeError(f"内容声明点击后未生效，当前区域文本: {current_text[:200]}")

        pdd_logger.info(_msg("📌", f"内容声明已选择: {selected_text or '内容无需标注'}"))

    async def _set_schedule_time(self, page: Page):
        """
        设置定时发布时间（日期 + 时间）。

        拼多多 datePicker/timePicker 的 input 均为 readonly，必须通过 UI 交互：
        1. 点击"定时发布" radio
        2. 点击 datePicker input 打开日历面板
        3. 翻月（若需要）：点击 header 区域的右箭头 SVG（testid=beast-core-icon-right）
        4. 点击目标日期 td（同月用普通 td，下月溢出用 outOfMonth td，均无 disabled）
        5. 点击 timePicker input 打开时间滚动列表，分别选时/分/秒
        6. 点击"确认"按钮

        DOM 结构（实测）：
        - 日历容器根节点：testid="beast-core-datePicker-dropdown-contentRoot"
          - child[0] RPR_headerWrapper: 含 testid="beast-core-datePicker-dropdown-header"
            - 左箭头 SVG: testid="beast-core-icon-left"
            - 月份文字（innerText 形如 "4月"）
            - 右箭头 SVG: testid="beast-core-icon-right"
          - child[1] RPR_contentPickerWrapper: 含 table[testid="beast-core-datePicker-table"]
          - child[2] RPR_footerWrapper: 含"确认"button + timePicker
        - td class 含 RPR_disabled_* → 不可点；含 RPR_outOfMonth_* 但无 disabled → 可点（下月溢出日）
        """
        if self.publish_strategy != PDD_PUBLISH_STRATEGY_SCHEDULED or self.publish_date == 0:
            return

        import re as _re

        pdd_logger.info(_msg("🕒", "小人准备设置定时发布时间"))

        # 滚到底部确保发布设置可见
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

        # 点击"定时发布" radio
        schedule_radio = page.locator(
            'label[data-testid="beast-core-radio"]'
        ).filter(has_text="定时发布")
        await schedule_radio.first.click()
        await asyncio.sleep(2)

        # 点击 datePicker input 打开日历面板
        date_input = page.locator(
            'input[data-testid="beast-core-datePicker-htmlInput"]'
        ).first
        await date_input.wait_for(state="visible", timeout=5000)
        await date_input.click()
        await asyncio.sleep(2)

        target_day = str(self.publish_date.day)
        target_hour = f"{self.publish_date.hour:02d}"
        target_min = f"{self.publish_date.minute:02d}"
        target_sec = f"{self.publish_date.second:02d}"
        target_year = self.publish_date.year
        target_month = self.publish_date.month

        # === 等待日历面板出现 ===
        table = page.locator('table[data-testid="beast-core-datePicker-table"]')
        await table.wait_for(state="visible", timeout=5000)

        # === 翻月：header innerText 只含月份数字（如 "4月"），需结合 today td 推断年份 ===
        # 翻月按钮：header 区域的 SVG icon，右箭头 testid="beast-core-icon-right"
        header_section = page.locator('section[data-testid="beast-core-datePicker-dropdown-header"]')
        right_arrow = page.locator('[data-testid="beast-core-icon-right"]').first

        for _ in range(13):
            # 读 header 月份文字
            header_text = (await header_section.inner_text()).strip() if await header_section.count() else ""
            m = _re.search(r"(\d{1,2})月", header_text)
            if not m:
                pdd_logger.warning(_msg("⚠️", f"无法解析日历月份标题: {header_text!r}"))
                break

            cur_month_display = int(m.group(1))

            # 用 today td 确定当前显示的年份（today 在当月则年份就是今年，否则靠翻月次数推算）
            # 简化：直接比较月份差，今天是 4 月，目标是 5 月，翻 1 次
            # 用页面上 RPR_today_ 所在 td 的位置判断当前显示年月
            today_td = table.locator('td[class*="RPR_today"]')
            if await today_td.count():
                # today 在当前日历里，说明当前显示的是今天所在月
                today_text = (await today_td.first.inner_text()).strip()
                from datetime import date as _date
                today = _date.today()
                cur_year = today.year
                cur_month = today.month
            else:
                # today 不在当前日历（已翻过去），根据 header 月份推断
                # 翻过的月数 = 循环次数，直接用 cur_month_display 和上次状态
                # 取 outOfMonth td 的最大值判断是否跨年（粗略处理）
                cur_year = target_year
                cur_month = cur_month_display

            if cur_year == target_year and cur_month == target_month:
                break

            if (cur_year, cur_month) < (target_year, target_month):
                # 向后翻月
                if not await right_arrow.count():
                    pdd_logger.warning(_msg("⚠️", "找不到右箭头翻月按钮"))
                    break
                await right_arrow.click()
                await asyncio.sleep(0.5)
                # 刷新 td 引用
                all_tds_temp = table.locator("td")
                _ = await all_tds_temp.count()  # 触发 DOM 刷新
            else:
                left_arrow = page.locator('[data-testid="beast-core-icon-left"]').first
                if not await left_arrow.count():
                    pdd_logger.warning(_msg("⚠️", "找不到左箭头翻月按钮"))
                    break
                await left_arrow.click()
                await asyncio.sleep(0.5)

        # === 选择日期：遍历 td，找文字匹配且无 disabled 的 ===
        all_tds = table.locator("td")
        td_count = await all_tds.count()

        clicked = False
        for i in range(td_count):
            td = all_tds.nth(i)
            text = (await td.inner_text()).strip()
            if text == target_day:
                td_cls = await td.get_attribute("class") or ""
                if "RPR_disabled" not in td_cls:
                    await td.click()
                    clicked = True
                    is_out = "outOfMonth" in td_cls
                    pdd_logger.info(_msg("📅", f"已选择日期: {target_month}月{target_day}日{'（溢出格）' if is_out else ''}"))
                    break

        if not clicked:
            raise RuntimeError(
                f"找不到可点击的日期格子: {target_year}-{target_month:02d}-{target_day.zfill(2)}，"
                "目标日期可能已过去或超出可选范围"
            )

        await asyncio.sleep(1)

        # === 选择时间 ===
        # 点击 timePicker input 打开时间滚动列表
        time_input = page.locator(
            'input[data-testid="beast-core-timePicker-html-input"]'
        ).first
        if await time_input.count():
            await time_input.click()
            await asyncio.sleep(2)

            # timePicker 有 3 个 <ul class="TPK_ul_*"> 列：小时/分钟/秒
            # 每列中 <li class="cIL_item_*"> 是可点击的时间项
            columns = page.locator('ul[class*="TPK_ul"]')
            col_count = await columns.count()

            if col_count >= 3:
                for col_idx, target_val in enumerate([target_hour, target_min, target_sec]):
                    col = columns.nth(col_idx)
                    items = col.locator('li[class*="cIL_item"]')
                    item_count = await items.count()
                    found = False
                    for j in range(item_count):
                        item = items.nth(j)
                        text = (await item.inner_text()).strip()
                        if text == target_val:
                            await item.scroll_into_view_if_needed()
                            await asyncio.sleep(0.2)
                            await item.click()
                            found = True
                            break
                    if not found:
                        pdd_logger.warning(
                            _msg("⚠️", f"时间列 {col_idx} 找不到 '{target_val}'")
                        )
                pdd_logger.info(
                    _msg("⏰", f"已设置时间: {target_hour}:{target_min}:{target_sec}")
                )
            else:
                pdd_logger.warning(
                    _msg("⚠️", f"时间选择列数不足: 期望3列, 实际{col_count}列")
                )
            await asyncio.sleep(1)

        # === 点击"确认"按钮 ===
        confirm_btn = page.locator(
            'div[data-testid="beast-core-portal"] button'
        ).filter(has_text="确认").first
        if await confirm_btn.count() and await confirm_btn.is_visible():
            await confirm_btn.click()
            pdd_logger.info(_msg("✅", "已点击确认"))
            await asyncio.sleep(1)

        # 验证最终值
        final_val = await date_input.input_value()
        pdd_logger.info(_msg("🕒", f"定时发布时间已设置: {final_val}"))

    async def upload(self, playwright: Playwright) -> None:
        """拼多多视频上传主流程。"""
        pdd_logger.info(_msg("🧍", "小人先检查 cookie、视频文件和发布时间"))
        await self.validate_upload_args()
        pdd_logger.info(_msg("🥳", "上传前检查通过"))

        if self.local_executable_path:
            browser = await playwright.chromium.launch(
                headless=self.headless,
                executable_path=self.local_executable_path,
            )
        else:
            browser = await playwright.chromium.launch(
                headless=self.headless,
                channel="chrome",
            )
        context = await browser.new_context(storage_state=self.account_file)
        context = await set_init_script(context)

        upload_success = False
        try:
            page = await context.new_page()

            # === Step 1: 拼多多跨域 SSO 导航 ===
            await page.goto(PDD_MMS_HOME_URL)
            await asyncio.sleep(2)
            await page.goto(PDD_VIDEO_PUBLISH_URL)
            pdd_logger.info(_msg("🧭", "小人正在赶往拼多多视频发布页"))

            # 等待发布页落地完成（"添加视频"按钮出现说明页面可交互）
            add_video_btn = page.get_by_text("添加视频", exact=True)
            await add_video_btn.wait_for(state="visible", timeout=30000)
            pdd_logger.info(_msg("🥳", "发布页已加载完成"))
            await asyncio.sleep(2)

            # === Step 2: 上传视频文件 ===
            pdd_logger.info(_msg("🏃", f"小人开始搬运视频: {Path(self.file_path).name}"))
            file_input = page.locator('input[type="file"][accept*=".mp4"]').first
            await file_input.set_input_files(self.file_path)

            # 等待上传表单渲染（"添加视频描述"和"一键发布"出现说明上传已开始）
            for _ in range(40):
                await asyncio.sleep(3)
                desc_count = await page.get_by_text("添加视频描述").count()
                pub_count = await page.get_by_text("一键发布").count()
                if desc_count > 0 and pub_count > 0:
                    pdd_logger.info(_msg("🥳", "视频上传表单已渲染"))
                    await asyncio.sleep(2)
                    break
            else:
                raise RuntimeError("等待上传表单渲染超时")

            # === Step 3: 等待视频上传完成 ===
            await self._wait_for_upload_complete(page)

            # === Step 4: 填写视频描述 ===
            await self._fill_description(page)

            # === Step 5: 添加话题/标签 ===
            await self._add_tags(page)

            # === Step 6: 添加推广商品（如有） ===
            await self._add_goods(page)
            await asyncio.sleep(2)

            # === Step 7: 设置定时发布（如需） ===
            await self._set_schedule_time(page)

            # === Step 8: 设置内容声明（必填） ===
            await self._set_content_declaration(page)

            # === Step 9: 点击发布（dry_run 模式跳过） ===
            if self.dry_run:
                pdd_logger.info(_msg("🧪", "Dry run 模式：跳过发布，所有设置已完成"))
                await page.screenshot(path="/tmp/pdd_dry_run.png", full_page=True)
                pdd_logger.info(_msg("📸", "截图已保存: /tmp/pdd_dry_run.png"))
                upload_success = True
            else:
                pdd_logger.info(_msg("🏃", "小人正在冲刺发布视频"))
                publish_btn = page.locator(
                    "div.video-list_singlePublish__UqpN1 button"
                ).first
                if not await publish_btn.count():
                    # 备选：底部"一键发布"
                    publish_btn = page.locator(
                        "div.VideoListFooter_footer__1PdYJ button"
                    ).filter(has_text="一键发布").first

                await publish_btn.wait_for(state="visible", timeout=10000)
                await publish_btn.click()
                pdd_logger.info(_msg("🏃", "已点击发布按钮"))

            # === Step 9: 等待发布成功（dry_run 模式已在 Step 8 处理） ===
            if not self.dry_run:
                publish_url = page.url  # 记录发布时的 URL（含 video/home）
                for _ in range(30):
                    await asyncio.sleep(2)
                    current_url = page.url

                    # 离开发布页 → 跳转成功（最可靠的信号）
                    if current_url != publish_url and "live.pinduoduo.com" in current_url:
                        pdd_logger.success(_msg("🥳", f"视频发布成功，页面已跳转: {current_url}"))
                        upload_success = True
                        break

                    # toast 文案出现（发布后短暂展示）
                    success_toast = page.get_by_text("发布成功", exact=False)
                    if await success_toast.count():
                        pdd_logger.success(_msg("🥳", "检测到发布成功提示"))
                        upload_success = True
                        break

                    # 发布表单消失（上传表单被替换说明发布完成）
                    file_input = page.locator('input[type="file"][accept*=".mp4"]')
                    if not await file_input.count():
                        pdd_logger.success(_msg("🥳", "视频发布成功，上传表单已消失"))
                        upload_success = True
                        break

                if not upload_success:
                    pdd_logger.error(_msg("❌", "发布失败：等待 60 秒未检测到成功信号"))

        except Exception as exc:
            pdd_logger.error(_msg("❌", f"UPLOAD_FAILED: {exc}"))
            raise
        finally:
            if upload_success:
                await context.storage_state(path=self.account_file)
                pdd_logger.success(_msg("🥳", "cookie 更新完毕"))
                await asyncio.sleep(2)
            else:
                # 失败时保留现场截图，方便排查
                try:
                    screenshot_path = f"/tmp/pdd_upload_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    pdd_logger.info(_msg("📸", f"失败现场截图已保存: {screenshot_path}"))
                except Exception:
                    pass
            await context.close()
            await browser.close()

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
