# -*- coding: utf-8 -*-

import asyncio
import inspect
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from patchright.async_api import Page, Playwright, async_playwright

from utils.config import DEBUG_MODE, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.log import tmall_logger

TMALL_CREATOR_HOME_URL = "https://creator.guanghe.taobao.com/page/"
TMALL_VIDEO_PUBLISH_URL = "https://creator.guanghe.taobao.com/page/pubNew/video?pub_url=https%3A%2F%2Fhuodong.taobao.com%2Fwow%2Fz%2Fguang%2Fgg_publish%2Fgg-video%3Fugc_scene%3Dpc_newcreator_video%26pageType%3Dvideo%26site%3Dguangguang&pub_scene=gg"
TMALL_LOGIN_SUCCESS_HOST = "creator.guanghe.taobao.com"
TMALL_AUTH_HOSTS = {"passport.taobao.com"}
TMALL_PUBLISH_STRATEGY_IMMEDIATE = "immediate"
TMALL_PUBLISH_STRATEGY_SCHEDULED = "scheduled"


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


def _url_host(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _is_login_page_url(url: str) -> bool:
    host = _url_host(url)
    path = urlparse(url).path if url else ""
    return host == "login.taobao.com" or path.startswith("/login/")


def _is_auth_page_url(url: str) -> bool:
    return _url_host(url) in TMALL_AUTH_HOSTS


def _is_tmall_creator_home(url: str) -> bool:
    return _url_host(url) == TMALL_LOGIN_SUCCESS_HOST


async def _launch_browser(playwright, headless: bool):
    if LOCAL_CHROME_PATH:
        return await playwright.chromium.launch(
            headless=headless,
            executable_path=LOCAL_CHROME_PATH,
        )
    return await playwright.chromium.launch(headless=headless, channel="chrome")


async def cookie_auth(account_file):
    """
    验证淘宝光合平台 cookie 是否有效。

    加载 Playwright storage_state 后访问光合平台首页，如果仍停留在淘宝登录页，
    或页面未能进入 creator.guanghe.taobao.com，则按 cookie 失效处理。
    """
    async with async_playwright() as playwright:
        browser = await _launch_browser(playwright, headless=True)
        try:
            context = await browser.new_context(storage_state=account_file)
            context = await set_init_script(context)
            page = await context.new_page()
            await page.goto(TMALL_CREATOR_HOME_URL, wait_until="domcontentloaded")
            await asyncio.sleep(5)

            current_url = page.url
            if _is_login_page_url(current_url):
                return False
            if _is_tmall_creator_home(current_url):
                return True

            for _ in range(5):
                await asyncio.sleep(2)
                current_url = page.url
                if _is_login_page_url(current_url):
                    return False
                if _is_tmall_creator_home(current_url):
                    return True

            tmall_logger.warning(_msg("⚠️", f"cookie 校验未进入目标页: {current_url}"))
            return False
        except Exception as exc:
            tmall_logger.warning(_msg("😵", f"cookie 校验时出错，按失效处理: {exc}"))
            return False
        finally:
            await browser.close()


async def tmall_setup(
    account_file,
    handle=False,
    return_detail=False,
    qrcode_callback=None,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    """
    检查淘宝光合平台 cookie 有效性，失效且 handle=True 时打开浏览器让用户手动登录。
    """
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie文件不存在或已失效", account_file)
            return result if return_detail else False

        tmall_logger.info(_msg("🥹", "cookie 失效了，准备打开浏览器让用户手动登录淘宝光合平台"))
        result = await tmall_cookie_gen(
            account_file,
            headless=headless,
            qrcode_callback=qrcode_callback,
        )
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie有效", account_file)
    return result if return_detail else True


async def tmall_cookie_gen(
    account_file,
    headless: bool = LOCAL_CHROME_HEADLESS,
    qrcode_callback=None,
    poll_interval: int = 3,
    max_checks: int = 200,
):
    """
    打开淘宝光合平台入口，等待用户手动完成登录并进入光合平台。

    不自动输入账号密码，也不绕过任何安全验证。用户在可见浏览器里完成扫码、
    密码、短信或其它淘宝安全验证后，本函数保存 storage_state。
    """
    async with async_playwright() as playwright:
        browser = await _launch_browser(playwright, headless=headless)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        context = await set_init_script(context)
        result = _build_login_result(False, "failed", "淘宝光合平台登录失败", account_file)
        page = None

        try:
            page = await context.new_page()
            await page.goto(TMALL_CREATOR_HOME_URL, wait_until="domcontentloaded")
            tmall_logger.info(_msg("🧍", "已打开淘宝光合平台入口，请在浏览器中完成登录和验证"))
            await _emit_qrcode_callback(
                qrcode_callback,
                {
                    "type": "manual_login",
                    "login_url": page.url,
                    "target_url": TMALL_CREATOR_HOME_URL,
                    "account_file": str(account_file),
                },
            )

            for _ in range(max_checks):
                current_url = page.url

                if _is_tmall_creator_home(current_url):
                    tmall_logger.info(_msg("🥳", f"检测到已进入淘宝光合平台: {current_url}"))
                    break

                if _is_auth_page_url(current_url):
                    await asyncio.sleep(poll_interval)
                    continue

                if not _is_login_page_url(current_url):
                    try:
                        await page.goto(TMALL_CREATOR_HOME_URL, wait_until="domcontentloaded")
                    except Exception as exc:
                        tmall_logger.warning(_msg("⚠️", f"跳转光合平台时出错，继续等待: {exc}"))
                    await asyncio.sleep(poll_interval)
                    if _is_tmall_creator_home(page.url):
                        tmall_logger.info(_msg("🥳", f"检测到已进入淘宝光合平台: {page.url}"))
                        break

                await asyncio.sleep(poll_interval)
            else:
                result = _build_login_result(
                    False,
                    "timeout",
                    "等待淘宝光合平台登录超时",
                    account_file,
                    page.url,
                )
                return result

            await asyncio.sleep(3)
            await context.storage_state(path=account_file)
            tmall_logger.info(_msg("💾", f"cookie 已保存: {account_file}"))

            if await cookie_auth(account_file):
                tmall_logger.success(_msg("🥳", "淘宝光合平台登录成功，cookie 验证通过"))
                result = _build_login_result(True, "success", "淘宝光合平台登录成功", account_file, page.url)
            else:
                tmall_logger.error(_msg("😢", "淘宝光合平台登录流程结束，但 cookie 校验失败"))
                result = _build_login_result(
                    False,
                    "cookie_invalid",
                    "淘宝光合平台登录流程结束，但 cookie 校验失败",
                    account_file,
                    page.url,
                )
        except Exception as exc:
            result = _build_login_result(
                False,
                "failed",
                str(exc),
                account_file,
                current_url=page.url if page else "",
            )
        finally:
            if not result["success"]:
                tmall_logger.error(_msg("😢", f"登录失败: {result['message']}"))
            await context.close()
            await browser.close()

        return result


class TmallBaseUploader(BaseVideoUploader):
    def __init__(
        self,
        account_file,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        self.account_file = account_file
        self.debug = debug
        self.headless = headless
        self.local_executable_path = LOCAL_CHROME_PATH

    async def validate_base_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"cookie文件不存在，请先完成淘宝光合平台登录: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"cookie文件已失效，请先完成淘宝光合平台登录: {self.account_file}")


class TmallVideo(TmallBaseUploader):
    def __init__(
        self,
        file_path,
        title: str,
        desc: str | None,
        account_file,
        tags: list[str] | None = None,
        goods_id: str | None = None,
        activity_topic: str | None = None,
        schedule: datetime | None = None,
        publish_strategy: str = TMALL_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
        dry_run: bool = False,
    ):
        super().__init__(account_file=account_file, debug=debug, headless=headless)
        self.file_path = file_path
        self.title = title
        self.desc = desc or ""
        self.tags = tags or []
        self.goods_id = goods_id or ""
        self.activity_topic = activity_topic or ""
        self.dry_run = dry_run
        self.schedule = schedule
        self.publish_strategy = publish_strategy

    async def validate_upload_args(self):
        await self.validate_base_args()
        self.file_path = str(self.validate_video_file(self.file_path))
        if not self.title:
            raise ValueError("天猫光合视频标题不能为空")
        if len(self.title) > 30:
            raise ValueError("天猫光合视频标题不能超过30字")
        if not self.goods_id and not self.tags:
            desc_for_check = self.desc or ""
        else:
            # 描述框最终内容 = 描述 + 每个话题前一个空格 + "#" + tag
            tag_text = "".join(f" #{t}" for t in self._normalized_tags())
            desc_for_check = (self.desc or "") + tag_text
        if len(desc_for_check) > 1000:
            raise ValueError("天猫光合视频描述不能超过1000字")
        if len(self.tags) > 4:
            tmall_logger.warning(_msg("⚠️", f"话题标签最多4个，已自动截取前4个（传入了 {len(self.tags)} 个）"))
            self.tags = self.tags[:4]
        if self.goods_id and not self.goods_id.isdigit():
            raise ValueError("天猫光合商品ID必须为数字")
        if self.schedule:
            now = datetime.now()
            if self.schedule <= now:
                raise ValueError(f"定时发布时间必须是未来时间: {self.schedule}")

    async def _find_publish_frame(self, page: Page):
        for _ in range(30):
            for frame in page.frames:
                if "gg_publish/gg-video" in frame.url:
                    return frame
            await asyncio.sleep(1)
        raise RuntimeError("未找到淘宝光合视频发布 iframe")

    async def _wait_for_upload_ready(self, frame, timeout_seconds: int = 180):
        for i in range(timeout_seconds // 2):
            body = await frame.locator("body").inner_text(timeout=3000)
            if "上传失败" in body or "失败" in body:
                raise RuntimeError("视频上传失败，请检查页面提示")
            if "重新上传" in body and "视频封面" in body:
                tmall_logger.success(_msg("🥳", "视频上传完成，发布表单已可编辑"))
                return
            if i % 5 == 0:
                tmall_logger.info(_msg("🏃", "小人正在等待视频上传完成"))
            await asyncio.sleep(2)
        raise RuntimeError("等待视频上传完成超时")

    def _build_description(self) -> str:
        """返回纯描述文本。话题标签单独通过键盘输入触发平台的话题下拉建议，
        不再拼接到描述末尾（那样只是纯文本，不会成为平台识别的话题）。"""
        return self.desc or ""

    def _normalized_tags(self) -> list[str]:
        """清洗 tags：去 # 前缀、去空白、过滤空项。"""
        cleaned = []
        for tag in self.tags:
            t = tag.strip().lstrip("#")
            if t:
                cleaned.append(t)
        return cleaned

    async def _fill_title_and_desc(self, frame, page: Page):
        title_input = frame.locator('input[placeholder="加个标题让内容更吸引人"]').first
        await title_input.wait_for(state="visible", timeout=10000)
        await title_input.fill(self.title[:30])
        tmall_logger.info(_msg("✍️", f"视频标题已填写: {self.title[:30]}"))

        # 描述区是淘宝"仓颉"富文本编辑器（contenteditable div），不是真正的 textarea。
        # 页面上虽然有 <textarea>，但它是隐藏的 value 同步元素，会被前面的 rich-text-content
        # 遮挡无法点击、接收键盘事件。直接用 fill() 改 textarea.value 也不会触发 hashtag 识别。
        # 正确做法：定位到 div[data-cangjie-content="true"]，click 聚焦后逐字符 type。
        desc_editor = frame.locator('div[data-cangjie-content="true"]').first
        await desc_editor.wait_for(state="visible", timeout=10000)
        await desc_editor.click()

        # 清空已有内容（草稿可能自动保留上次输入）
        await page.keyboard.press("Meta+A")
        await page.keyboard.press("Delete")

        desc = self._build_description()
        if desc:
            await page.keyboard.type(desc[:1000])
            tmall_logger.info(_msg("✍️", f"视频描述已填写: {desc[:30]}"))

        tags = self._normalized_tags()
        if not tags:
            return

        # 描述末尾逐个敲话题。contenteditable 富文本会识别 "#xxx" 并把话题染蓝
        # （和用户手写 #狗粮 变蓝是同一个机制）。用空格分隔每个话题。
        for index, tag in enumerate(tags, start=1):
            tmall_logger.info(_msg("🏷️", f"小人正在添加第 {index} 个话题: #{tag}"))
            await page.keyboard.type(f" #{tag}")
            await asyncio.sleep(1)
            # 空格确认选中下拉建议里的第一项（若下拉未弹出则作为普通分隔符）
            await page.keyboard.press("Space")
            await asyncio.sleep(1)
        tmall_logger.info(_msg("🏷️", f"小人一共贴了 {len(tags)} 个话题"))

    async def _add_goods(self, frame, page: Page):
        if not self.goods_id:
            return

        tmall_logger.info(_msg("🛒", f"小人准备添加商品: {self.goods_id}"))
        await frame.get_by_text("添加商品", exact=True).first.click()
        dialog = frame.locator(".next-dialog").filter(has_text="关联商品").first
        await dialog.wait_for(state="visible", timeout=10000)

        search = dialog.locator('input[placeholder="输入商品关键词或商品ID"]').first
        await search.click()
        await page.keyboard.press("Meta+A")
        await page.keyboard.type(self.goods_id)

        result_area = dialog.locator('[role="tabpanel"].active, [class*="tab-content"], [class*="content--"]').first
        before_result_text = await result_area.inner_text(timeout=3000)

        search_icon = dialog.locator('i[role="button"][aria-label="搜索"].next-search-icon').first
        await search_icon.wait_for(state="visible", timeout=5000)
        await search_icon.click()
        tmall_logger.info(_msg("🔎", f"已点击放大镜搜索按钮按商品ID搜索: {self.goods_id}"))

        # 等待搜索结果真正加载完成：
        # - 出现 ¥ 符号 → 有商品卡片，加载完成
        # - 出现"没有更多"/"没有找到"等明确终态提示 → 无结果，加载完成
        # - 否则持续等待（"数据加载中..."只是中间态，不算完成）
        EMPTY_HINTS = ("没有更多了", "暂无数据", "没有找到", "没有搜到", "暂无商品", "无结果")
        LOADING_HINTS = ("加载中", "loading")
        result_text = before_result_text
        for _ in range(30):
            await asyncio.sleep(1)
            result_text = await result_area.inner_text(timeout=3000)
            # 有商品卡片了
            if "¥" in result_text:
                break
            # 明确无结果（区分于加载中）
            if any(h in result_text for h in EMPTY_HINTS) and not any(l in result_text for l in LOADING_HINTS):
                break
        else:
            raise RuntimeError(
                f"商品ID {self.goods_id} 搜索超时（30秒内未出现商品卡片也无明确无结果提示）。"
                "可能是网络慢或平台接口卡顿，建议用 --headed 重试观察。"
            )

        # 搜索结果页可能出现以下几种状态，分别给出不同的错误消息：
        # - 空白加载中（没有商品卡片也没有"无结果"提示）→ 搜索接口超时
        # - 明确的"暂无数据"/"没有找到" 提示 → 商品ID确实不存在或不属于本店
        # - 有商品卡片但无价格 → 商品状态异常
        result_text = await result_area.inner_text(timeout=3000)
        result_item = result_area.locator('[class*="item--"]').filter(has_text="¥").first
        item_count = await result_item.count()

        if item_count == 0:
            # 区分"平台明确告知无结果" vs "加载中/空白"
            empty_hints = ["暂无数据", "没有找到", "没有搜到", "暂无商品", "无结果"]
            if any(hint in result_text for hint in empty_hints):
                raise ValueError(
                    f"商品ID {self.goods_id} 在本店商品库中搜索不到。"
                    "请核实：1) ID是否正确；2) 商品是否上架；3) 商品是否属于该账号的店铺。"
                )
            if "加载中" in result_text or not result_text.strip():
                raise RuntimeError(
                    f"商品ID {self.goods_id} 搜索结果未加载完成（可能是网络慢或平台接口卡顿）。"
                    "建议稍后重试，或用 --headed 模式观察页面实际状态。"
                )
            # 其他不明情况，把页面文本片段附上便于排查
            raise ValueError(
                f"商品ID {self.goods_id} 搜索未返回有效商品卡片。"
                f"搜索结果区内容片段: {result_text[:100]!r}。"
                "请核实商品ID是否正确、是否属于该账号店铺。"
            )
        if "¥" not in result_text:
            raise ValueError(
                f"商品ID {self.goods_id} 搜到了卡片但无价格信息，商品可能处于下架/异常状态。"
                "请在淘宝商家后台核实商品状态。"
            )

        # 只允许选择搜索结果区中的第一个商品卡片，不能选择搜索前默认推荐列表。
        await result_item.locator('label[class*="checkbox"], label.next-checkbox-wrapper').first.click()
        await asyncio.sleep(1)

        selected_text = await dialog.inner_text(timeout=3000)
        if "已选商品" not in selected_text:
            raise RuntimeError(f"商品 {self.goods_id} 勾选失败")

        await dialog.get_by_role("button", name="确定").click()
        await dialog.wait_for(state="hidden", timeout=10000)
        tmall_logger.success(_msg("🛒", f"商品 {self.goods_id} 添加完成"))

    async def _add_activity_topic(self, frame, page: Page):
        """参与话题活动。

        两条路径：
        1. activity_topic 为空（默认）→ 点推荐区第一张卡片（平台自动推荐）。
           若平台未给推荐（area-recommend 为空）→ 静默跳过，不报错。
        2. activity_topic 有值 → 打开话题选择对话框 → 搜索关键词 →
           选搜索结果第一张卡片 → 确认提交。
           若搜索无结果 → 报错终止。
        """
        # ── 路径 1：直接点推荐卡片 ──────────────────────────────────
        if not self.activity_topic:
            rec_card = frame.locator(
                '[class*="topic-card-recommend--"]'
            ).first
            count = await rec_card.count()
            if count == 0:
                tmall_logger.info(_msg("📣", "平台暂无推荐话题活动，跳过"))
                return
            topic_name = await rec_card.evaluate(
                "el => (el.getAttribute('data-autolog') || el.innerText || '').split(':').pop().trim()"
            )
            await rec_card.click()
            await asyncio.sleep(1)
            tmall_logger.success(_msg("📣", f"已参与推荐话题活动: {topic_name}"))
            return

        # ── 路径 2：搜索指定关键词 ───────────────────────────────────
        tmall_logger.info(_msg("📣", f"准备搜索话题活动: {self.activity_topic}"))

        # 点"点击添加话题"区域打开对话框
        add_btn = frame.locator('[class*="topic-v2--select--"]').first
        await add_btn.click()

        dialog = frame.locator(".next-dialog").filter(has_text="话题选择").first
        await dialog.wait_for(state="visible", timeout=10000)

        # 搜索
        search_input = dialog.locator('input[placeholder="输入关键词搜索"]').first
        await search_input.click()
        await page.keyboard.type(self.activity_topic)
        await asyncio.sleep(0.5)

        search_btn = dialog.locator(".next-btn-primary").filter(has_text="搜索").first
        await search_btn.click()
        tmall_logger.info(_msg("🔎", f"已搜索话题关键词: {self.activity_topic}"))
        await asyncio.sleep(3)

        # 找搜索结果第一张可点击卡片
        # 结构：.topic-card--xxx > .topic-card-select--xxx（cursor:pointer）
        result_card = dialog.locator('[class*="topic-card-select--"]').first
        count = await result_card.count()
        if count == 0:
            await dialog.locator(".next-btn-normal").filter(has_text="取消").first.click()
            raise ValueError(
                f"话题活动搜索关键词 '{self.activity_topic}' 无结果。"
                "请核实关键词是否正确，或不传 --activity-topic 使用平台推荐话题。"
            )

        topic_name = await result_card.evaluate(
            "el => (el.getAttribute('data-autolog') || el.innerText || '').split(':').pop().split('\\n')[0].trim()"
        )
        await result_card.click()
        await asyncio.sleep(1)
        tmall_logger.info(_msg("📣", f"已选择话题: {topic_name}"))

        # 确认提交
        submit_btn = dialog.locator(".next-btn-primary").filter(has_text="确认提交").first
        await submit_btn.click()
        await dialog.wait_for(state="hidden", timeout=10000)
        tmall_logger.success(_msg("📣", f"话题活动已参与: {topic_name}"))

    async def _set_schedule(self, frame, page: Page):
        """设置定时发布时间，或确认使用立即发布。"""
        date_picker = frame.locator(".next-date-picker").first
        await date_picker.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)

        if not self.schedule:
            tmall_logger.info(_msg("📅", "立即发布模式，无需设置发布时间"))
            return

        # 点击"定时发布" radio。页面结构：
        #   <label.next-radio-wrapper>（innerText 为空）
        #   <span>定时发布</span>  ← 紧挨着 label 的 span
        #   <span.next-input ...>日期输入框</span>
        # 以"定时发布"文本节点为锚点反找 radio，比坐标硬编码稳得多。
        clicked = await frame.locator("body").evaluate(
            """() => {
              const textNodes = [...document.querySelectorAll('span, label')].filter(
                e => (e.innerText || '').trim() === '定时发布'
              );
              for (const tn of textNodes) {
                // 向前找兄弟节点里的 label.next-radio-wrapper
                let sib = tn.previousElementSibling;
                while (sib) {
                  if (sib.matches && sib.matches('label.next-radio-wrapper')) {
                    sib.click();
                    return true;
                  }
                  sib = sib.previousElementSibling;
                }
                // 或者父节点下找第一个 label.next-radio-wrapper
                const parent = tn.parentElement;
                if (parent) {
                  const lbl = parent.querySelector('label.next-radio-wrapper');
                  if (lbl) { lbl.click(); return true; }
                }
              }
              return false;
            }"""
        )
        if not clicked:
            raise RuntimeError("未找到定时发布 radio，无法设置定时发布")
        await asyncio.sleep(1)

        # 验证 date-picker 输入框已启用
        inp = frame.locator('input[placeholder="请选择日期和时间"]').first
        is_disabled = await inp.evaluate("el=>el.disabled")
        if is_disabled:
            raise RuntimeError("点击定时发布 radio 后日期输入框仍为禁用状态")

        # 点日历图标打开面板，等面板稳定后再操作
        cal = frame.locator("i.next-icon-calendar").first
        await cal.click()
        # 等面板里出现月份 button（确保面板已渲染）
        await frame.locator("button.next-calendar-btn-next-month").first.wait_for(
            state="visible", timeout=8000
        )
        await asyncio.sleep(0.5)

        # 选择日期：不要直接填输入框。Fusion DatePicker 输入框会改变面板页码，
        # 但不等于改变内部选中日期。这里按面板可见日期范围翻页，直到目标日期出现，
        # 然后点击目标格子，让组件内部状态真正更新。
        date_str = self.schedule.strftime("%Y/%m/%d")
        date_input = frame.locator('input[placeholder="YYYY/MM/DD"]').first
        await date_input.wait_for(state="visible", timeout=8000)

        target_date_key = self.schedule.strftime("%Y/%m/%d")
        day_result = None
        for _ in range(14):
            day_result = await frame.evaluate(
                """(targetTitle) => {
                    const cells = [...document.querySelectorAll('td[title]')];

                    function isDisabled(el) {
                        return el.getAttribute('aria-disabled') === 'true'
                            || el.classList.contains('next-calendar-cell-disabled')
                            || el.classList.contains('next-disabled')
                            || el.querySelector('.next-calendar-date-disabled') !== null;
                    }

                    const visibleTitles = cells.map(el => el.getAttribute('title')).filter(Boolean).sort();
                    const enabledTitles = cells.filter(el => !isDisabled(el))
                        .map(el => el.getAttribute('title')).filter(Boolean).sort();
                    const cell = cells.find(el => el.getAttribute('title') === targetTitle);

                    if (!cell) {
                        return {
                            found: false,
                            disabled: false,
                            first: enabledTitles[0] || '',
                            last: enabledTitles[enabledTitles.length - 1] || '',
                            visibleFirst: visibleTitles[0] || '',
                            visibleLast: visibleTitles[visibleTitles.length - 1] || '',
                        };
                    }
                    if (isDisabled(cell)) {
                        return {
                            found: true,
                            disabled: true,
                            first: enabledTitles[0] || '',
                            last: enabledTitles[enabledTitles.length - 1] || '',
                            visibleFirst: visibleTitles[0] || '',
                            visibleLast: visibleTitles[visibleTitles.length - 1] || '',
                        };
                    }
                    cell.click();
                    return {
                        found: true,
                        disabled: false,
                        first: enabledTitles[0] || '',
                        last: enabledTitles[enabledTitles.length - 1] || '',
                        visibleFirst: visibleTitles[0] || '',
                        visibleLast: visibleTitles[visibleTitles.length - 1] || '',
                    };
                }""",
                target_date_key,
            )
            if day_result.get("found"):
                break

            visible_first = day_result.get("visibleFirst") or ""
            visible_last = day_result.get("visibleLast") or ""
            if visible_first and target_date_key < visible_first:
                await frame.locator("button.next-calendar-btn-prev-month").first.click()
            elif visible_last and target_date_key > visible_last:
                await frame.locator("button.next-calendar-btn-next-month").first.click()
            else:
                break
            await asyncio.sleep(0.3)
        if not day_result.get("found"):
            raise RuntimeError(
                f"未在当前日历面板找到目标日期 {self.schedule.strftime('%Y-%m-%d')}。"
                f"当前面板显示范围约为 {day_result.get('visibleFirst') or '未知'}"
                f" 到 {day_result.get('visibleLast') or '未知'}，"
                f"可点击范围约为 {day_result.get('first') or '未知'}"
                f" 到 {day_result.get('last') or '未知'}。"
            )
        if day_result.get("disabled"):
            raise ValueError(
                f"天猫光合平台当前不允许选择定时日期 {self.schedule.strftime('%Y-%m-%d')}。"
                f"当前面板可点击范围约为 {day_result.get('first') or '未知'}"
                f" 到 {day_result.get('last') or '未知'}。"
                "请改用日历中可点击的日期后重试。"
            )

        await asyncio.sleep(0.5)
        tmall_logger.info(_msg("📅", f"已选择日期: {date_str}"))

        # 点"选择时间"按钮，切换到时:分滚轮面板
        time_btn = frame.locator("button").filter(has_text="选择时间").first
        await time_btn.click()
        await asyncio.sleep(1)

        # 在时滚轮（ul.next-time-picker-menu-hour）点击目标小时
        hour = self.schedule.hour
        minute = self.schedule.minute
        hour_item = frame.locator(f'ul.next-time-picker-menu-hour li[title="{hour}"]').first
        await hour_item.scroll_into_view_if_needed()
        await hour_item.click()
        tmall_logger.info(_msg("🕐", f"已选择小时: {hour}"))
        await asyncio.sleep(0.3)

        # 在分滚轮（ul.next-time-picker-menu-minute）点击目标分钟
        minute_item = frame.locator(f'ul.next-time-picker-menu-minute li[title="{minute}"]').first
        await minute_item.scroll_into_view_if_needed()
        await minute_item.click()
        tmall_logger.info(_msg("🕐", f"已选择分钟: {minute}"))
        await asyncio.sleep(0.3)

        # 点"确定"提交时间选择（按钮在面板右下角，用 JS 直接点避免遮挡）
        await frame.evaluate("""()=>{
            const btns = [...document.querySelectorAll('button.next-btn-primary')];
            const ok = btns.find(b => (b.innerText || '').trim() === '确定');
            if (ok) ok.click();
        }""")
        await asyncio.sleep(1)

        final_val = await inp.evaluate("el=>el.value")
        expected_val = self.schedule.strftime("%Y/%m/%d %H:%M")
        if final_val != expected_val:
            raise RuntimeError(
                f"定时发布时间设置后校验失败：期望 {expected_val}，页面实际为 {final_val}。"
                "已停止发布，避免误定时到错误日期。"
            )
        tmall_logger.success(_msg("📅", f"定时发布时间已设置: {final_val}"))

    async def _select_creator_declaration(self, frame) -> None:
        """选择创作者声明（必填），默认选「内容无需标注」（第一个选项）。

        页面结构（实测）：
          <div class="...claim...">          ← 创作者声明专属容器，class 含 "claim"
            <div role="radiogroup" class="next-radio-group ...">
              <label class="next-radio-wrapper">
                <span class="next-radio">...</span>
                <span class="next-radio-label">内容无需标注</span>
              </label>
              ...
            </div>
          </div>

        注意：页面上还有「商品/店铺/允许下载」等其他 radio，必须在 claim 容器内定位，
        不能全局查找 label.next-radio-wrapper，否则会误点其他选项。
        """
        # 在 claim 容器内找第一个 label（即「内容无需标注」）并点击
        clicked = await frame.locator("body").evaluate(
            """() => {
              // class 包含 "claim" 的容器即创作者声明区域（实测 class 含 publish-button--claim）
              const claimDiv = document.querySelector('[class*="claim"]');
              if (!claimDiv) return 'no_claim_div';
              const firstLabel = claimDiv.querySelector('label.next-radio-wrapper');
              if (!firstLabel) return 'no_label';
              firstLabel.click();
              return (firstLabel.innerText || '').trim();
            }"""
        )
        if clicked in ("no_claim_div", "no_label"):
            raise RuntimeError(
                f"未找到创作者声明选项（{clicked}），页面结构可能已变更，请用 --headed 观察。"
            )
        await asyncio.sleep(0.5)
        tmall_logger.success(_msg("📋", f"创作者声明已选择：{clicked}"))

    async def upload(self, playwright: Playwright) -> None:
        tmall_logger.info(_msg("🧍", "小人先检查 cookie 和视频文件"))
        await self.validate_upload_args()
        tmall_logger.info(_msg("🥳", "上传前检查通过"))

        browser = await _launch_browser(playwright, headless=self.headless)
        context = await browser.new_context(
            storage_state=self.account_file,
            viewport={"width": 1280, "height": 900},
        )
        context = await set_init_script(context)
        success = False
        page = None

        try:
            page = await context.new_page()
            await page.goto(TMALL_VIDEO_PUBLISH_URL, wait_until="domcontentloaded")
            tmall_logger.info(_msg("🧭", "小人正在赶往淘宝光合发视频页面"))
            frame = await self._find_publish_frame(page)
            await asyncio.sleep(3)

            tmall_logger.info(_msg("🏃", f"小人开始上传视频: {Path(self.file_path).name}"))
            file_input = frame.locator('input[type="file"]').first
            await file_input.set_input_files(self.file_path)
            await self._wait_for_upload_ready(frame)
            await self._fill_title_and_desc(frame, page)
            await self._add_goods(frame, page)
            await self._add_activity_topic(frame, page)
            await self._set_schedule(frame, page)
            await self._select_creator_declaration(frame)

            if self.dry_run:
                screenshot_path = f"/tmp/tmall_dry_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                tmall_logger.info(_msg("🧪", "Dry run 模式：跳过发布，所有基础设置已完成"))
                tmall_logger.info(_msg("📸", f"截图已保存: {screenshot_path}"))
                success = True
                return

            # 真实发布：根据策略点对应按钮
            if self.schedule:
                publish_btn = frame.locator("button.next-btn-primary").filter(has_text="定时发布").first
                tmall_logger.info(_msg("🚀", f"点击定时发布按钮: {self.schedule}"))
            else:
                publish_btn = frame.locator("button.next-btn-primary").filter(has_text="立即发布").first
                tmall_logger.info(_msg("🚀", "点击立即发布按钮"))
            await publish_btn.click()
            await asyncio.sleep(3)
            tmall_logger.success(_msg("🥳", "视频已提交发布"))
            success = True
        except Exception as exc:
            tmall_logger.error(_msg("❌", f"UPLOAD_FAILED: {exc}"))
            raise
        finally:
            if success:
                await context.storage_state(path=self.account_file)
                tmall_logger.success(_msg("🥳", "cookie 更新完毕"))
            elif page:
                try:
                    screenshot_path = f"/tmp/tmall_upload_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    tmall_logger.info(_msg("📸", f"失败现场截图已保存: {screenshot_path}"))
                except Exception:
                    pass
            await context.close()
            await browser.close()

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
