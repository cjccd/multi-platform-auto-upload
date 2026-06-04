# Multi Platform Auto Upload

[English](README.md) | 简体中文

**一个面向自媒体创作者、电商商家和 AI Agent 的多平台内容自动发布工具。**

它把短视频、图文、商品挂载、定时发布、账号 Cookie 管理和 Agent Skill 工作流收敛到一个统一 CLI：`mpau`。

> 不要再让 AI Agent 每次临场点网页，把发布流程沉淀成可复用、可验证、可扩展的 CLI。

如果你每天都在多个平台重复做这些事：登录后台、上传视频、填写标题描述、挂商品、设置定时、保存草稿、检查发布结果——这个项目就是为了把这些重复流程交给稳定脚本完成。

---

## 为什么需要这个项目

浏览器 Agent 很强，但“上传发布”这类任务有几个特点：

- 高频重复：每天都要做
- 页面流程固定：上传、填写、挂商品、发布
- 细节很多：Cookie、二维码、商品搜索、定时日历、草稿、日志监控
- 不适合每次都让 AI 临场看截图、猜按钮、重新探索页面

`multi-platform-auto-upload` 的思路是：

> 把平台发布流程沉淀成稳定 uploader + CLI，让 AI Agent 或用户只需要调用命令。

---

## 项目特色

- **一个 CLI，覆盖多平台**：统一使用 `mpau`，不需要为每个平台维护一套零散脚本。
- **社媒 + 电商双场景**：既支持自媒体平台，也支持电商内容平台和商品挂载。
- **面向 Agent 友好**：每个平台都配有 `skills/` 工作流文档，适合接入 OpenClaw、Hermes、Codex、Claude Code 等智能体。
- **本地账号隔离**：不同平台、不同账号使用独立 Cookie 文件，适合多账号运营。
- **可扩展 uploader 架构**：平台能力集中在 `uploader/`，后续可以继续扩展新平台。
- **附属视频理解能力**：可选的视频抽帧和语音转文字能力，方便 Agent 在发布前理解素材内容。

---

## 适合谁

### 自媒体创作者

- 多平台分发视频
- 抖音 / 快手 / 小红书 / Bilibili / 视频号 / 百家号 / TikTok 同步运营
- 批量上传和定时发布
- 减少重复后台操作

### 电商商家 / 运营

- 商品短视频发布
- 视频挂载商品链接或商品 ID
- 多店铺、多账号内容发布
- 京东、PDD、天猫/淘宝光合、视频号等商家内容后台自动化

### AI Agent 使用者 / 开发者

- 给 Agent 一个明确、可执行、可验证的发布工具
- 不需要让 Agent 每次都临场操作网页
- 通过 `skills/` 目录把平台流程交给 Agent 可靠执行

### 自动化开发者

- 想基于现有 uploader 扩展更多平台
- 想把内容生成、视频分析、发布流程串成自动化 pipeline
- 想在自己的运营系统里集成多平台发布能力

---

## 支持平台

| 平台 | 视频 | 图文 | 定时 | 商品/挂载 | CLI | Skill |
| --- | --- | --- | --- | --- | --- | --- |
| 抖音 | ✅ | ✅ | ✅ | ✅ 商品链接 | ✅ | ✅ |
| 视频号 | ✅ | 暂未开放 | ✅ | ✅ 微信小店/橱窗商品 | ✅ | ✅ |
| PDD / 多多视频 | ✅ | ❌ | ✅ | ✅ PDD 商品 ID | ✅ | ✅ |
| 天猫 / 淘宝光合 | ✅ | ❌ | ✅ | ✅ 淘宝/天猫商品 ID | ✅ | ✅ |
| 京东 / 京东京麦 | ✅ | ❌ | ✅ | ✅ 京东商品 ID | ✅ | ✅ |
| 快手 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| 小红书 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| Bilibili | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| 百家号 | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| TikTok | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |

另外保留了旧版 XHS SDK uploader，作为 legacy 代码，不作为当前主线入口。

---

## 核心能力

### 统一 CLI

所有平台都通过一个命令入口：

```bash
mpau <platform> <action> [options]
```

典型动作：

```bash
mpau douyin login --account shop1 --headed
mpau douyin check --account shop1
mpau douyin upload-video --account shop1 --file ./video.mp4 --title "标题"
```

### 多账号 Cookie 管理

每个平台按本地账号昵称保存 Cookie：

```text
cookies/<platform>_<account>.json
```

适合多账号、多店铺、多品牌运营。

### 视频 / 图文上传

已接入平台按各自能力支持：

- 视频上传
- 图文发布
- 标题 / 描述 / 标签
- 封面图
- 草稿或 dry-run 验证

### 商品挂载

面向电商场景增强：

- 抖音商品链接
- 视频号商品 ID
- PDD 商品 ID
- 淘宝/天猫商品 ID
- 京东商品 ID

### 定时发布

统一使用：

```bash
--schedule "YYYY-MM-DD HH:MM"
```

各平台会按自己的页面规则完成定时设置。

### Agent Skills

`skills/` 目录提供平台工作流说明，适合 AI Agent 使用：

- 如何初始化环境
- 如何登录账号
- 如何校验 Cookie
- 如何上传
- 如何监控日志和处理失败

### 附属功能：视频自动分析

视频分析不是主线上传流程的必需能力，而是一个可选的附属功能，适合在“发布前理解素材内容”的场景使用。

`skills/video-analyze` 支持：

- 本地 `ffmpeg/ffprobe` 抽取关键帧
- 阿里云百炼 `paraformer-v2` 语音转文字
- 输出 JSON，供 Agent 理解视频内容

典型用途：

- 自动抽取视频关键帧，让 Agent 看画面内容
- 自动转写视频里的口播或旁白
- 给后续生成标题、描述、标签提供素材理解基础
- 在批量发布前快速判断视频内容是否匹配平台和商品

---

## 安装

### 环境要求

- Python `>=3.10,<3.13`
- Google Chrome
- `uv`（推荐）
- `patchright` 浏览器驱动
- `playwright` 浏览器驱动（百家号 / TikTok legacy 流程需要）

### 安装项目

```bash
git clone <your-repo-url> multi-platform-auto-upload
cd multi-platform-auto-upload

uv venv
source .venv/bin/activate
uv pip install -e .
```

Windows PowerShell：

```powershell
uv venv
.venv\Scripts\activate
uv pip install -e .
```

不用 `uv` 也可以：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 安装浏览器驱动

```bash
python -m patchright install chromium
python -m playwright install chromium
```

国内网络可指定镜像：

```bash
PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright" python -m patchright install chromium
PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright" python -m playwright install chromium
```

### 配置文件

```bash
cp conf.example.py conf.py
```

常用配置：

```python
LOCAL_CHROME_PATH = ""       # 可选，自定义 Chrome 路径
LOCAL_CHROME_HEADLESS = True  # 默认是否无头运行
DEBUG_MODE = True             # 调试模式
```

---

## 快速开始

### 查看帮助

```bash
mpau --help
mpau douyin --help
mpau pdd --help
mpau jd --help
```

开发环境也可以直接运行：

```bash
python3 mpau_cli.py --help
```

### 登录账号

```bash
mpau douyin login --account shop1 --headed
```

### 校验登录状态

```bash
mpau douyin check --account shop1
```

输出：

```text
valid
```

或：

```text
invalid
```

### 上传视频

```bash
mpau douyin upload-video \
  --account shop1 \
  --file ./videos/demo.mp4 \
  --title "视频标题" \
  --desc "视频描述" \
  --tags "测评,好物,生活" \
  --headed
```

### 定时发布

```bash
mpau tmall upload-video \
  --account shop1 \
  --file ./videos/demo.mp4 \
  --title "新品测评" \
  --schedule "2026-06-05 20:00" \
  --headed
```

### 商品挂载

```bash
mpau jd upload-video \
  --account shop1 \
  --file ./videos/demo.mp4 \
  --title "新品真实测评" \
  --goods-id "10204078771126" \
  --headed
```

---

## CLI 设计

统一结构：

```bash
mpau <platform> <action> [options]
```

常见平台：

```text
douyin
tencent
pdd
tmall
jd
kuaishou
xiaohongshu
bilibili
baijiahao
tiktok
```

常见动作：

```text
login
check
upload-video
upload-note
verify
```

示例：

```bash
mpau xiaohongshu upload-note --account creator --images 1.png 2.png --title "标题"
mpau bilibili upload-video --account creator --file demo.mp4 --title "标题" --desc "简介" --tid 249
mpau tencent upload-video --account shop1 --file demo.mp4 --title "标题" --goods-id "10000517325762"
```

---

## Agent Skills

项目内置 `skills/`：

```text
skills/douyin-upload/
skills/tencent-upload/
skills/pdd-upload/
skills/tmall-upload/
skills/jd-upload/
skills/kuaishou-upload/
skills/xiaohongshu-upload/
skills/bilibili-upload/
skills/baijiahao-upload/
skills/tiktok-upload/
skills/video-analyze/
```

这些不是必须安装才能使用 CLI，但它们对 AI Agent 很有用：

- 明确每个平台该调用哪些命令
- 约束登录、校验、上传、日志监控顺序
- 避免 Agent 每次都重新读页面、猜流程
- 让 Agent 更适合做批量发布和故障处理

### 集成到自己的智能体

如果你想把本项目接入自己的智能体系统，例如 OpenClaw、Hermes、Codex、Claude Code、Claude Desktop 或其他支持工具/技能目录的 Agent，可以按下面方式处理。

#### 方式一：让智能体直接使用本项目目录

适合本地开发和个人使用。

```bash
git clone <your-repo-url> multi-platform-auto-upload
cd multi-platform-auto-upload
uv venv
source .venv/bin/activate
uv pip install -e .
python -m patchright install chromium
python -m playwright install chromium
```

然后把项目目录交给 Agent，并告诉它：

```text
这是 multi-platform-auto-upload 项目。
请优先阅读 skills/ 下对应平台的 SKILL.md。
所有平台发布都通过 mpau CLI 执行，不要直接临场操作网页。
```

#### 方式二：把 skills 复制到智能体技能目录

适合有独立技能目录的 Agent。

示例：

```bash
cp -R skills/douyin-upload <YOUR_AGENT_SKILLS_DIR>/
cp -R skills/pdd-upload <YOUR_AGENT_SKILLS_DIR>/
cp -R skills/jd-upload <YOUR_AGENT_SKILLS_DIR>/
```

同时确保项目本身已安装，Agent 所在环境可以调用：

```bash
mpau --help
```

#### 方式三：作为内部发布工具接入 Agent 工作流

适合团队或运营系统。

推荐流程：

```text
1. 在服务器或运营电脑安装本项目
2. 登录各平台账号，生成本地 Cookie
3. 让 Agent 根据任务选择对应 skill
4. Agent 调用 mpau 执行 check / upload
5. Agent 通过日志判断成功、失败或需要人工登录
```

这样 Agent 负责调度和判断，平台细节由 uploader 负责执行。

---

## 附属功能：视频分析

`skills/video-analyze` 可把视频转换成 Agent 更容易理解的结构化材料。它不是发布主链路的一部分，不影响 `mpau upload` 系列命令。

- 抽取关键帧图片
- 转写语音文本
- 输出 JSON

初始化：

```bash
cd skills/video-analyze/scripts/video-analyzer
uv sync
```

安装 ffmpeg：

```bash
brew install ffmpeg
```

配置阿里云百炼 API Key：

```bash
export ALIYUN_API_KEY="sk-xxx"
```

运行：

```bash
uv run va extract --file /path/to/video.mp4
```

输出示例：

```json
{
  "frames": ["/tmp/va_frames_xxx/frame_01_10pct.jpg"],
  "transcript": "转写文本...",
  "duration": 45.2,
  "audio_empty": false
}
```

如果没有配置 ASR Key，抽帧仍然可用，语音文本为空。

这部分适合需要“先理解视频，再决定标题、标签、商品或平台”的高级工作流；如果你只是手动提供标题和描述，可以完全不使用它。

---

## 项目结构

```text
multi-platform-auto-upload/
├── mpau_cli.py              # CLI 主入口
├── pyproject.toml           # Python 包配置
├── conf.example.py          # 配置模板
├── uploader/                # 平台上传器
├── utils/                   # 公共工具
├── skills/                  # Agent Skills
└── tests/                   # 轻量测试
```

---

## 开发与测试

运行测试：

```bash
python3 -m unittest -v tests.test_mpau_cli
```

验证 CLI：

```bash
python3 mpau_cli.py --help
python3 mpau_cli.py douyin --help
python3 mpau_cli.py pdd --help
python3 mpau_cli.py tiktok --help
```

---

## 发布前检查

发布到 GitHub 前请确认：

- 没有 `cookies/`
- 没有 `logs/`
- 没有真实视频文件
- 没有 `.venv/`
- 没有 `__pycache__/`
- 没有个人账号、店铺 Cookie、二维码图片
- README 与当前 CLI 命令一致

---

## 免责声明

本项目仅用于辅助内容创作、商家自有账号运营和合法自动化测试。请遵守各平台规则，不要上传违规内容，不要滥用自动化能力。
