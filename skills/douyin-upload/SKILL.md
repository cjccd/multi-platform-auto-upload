---
name: douyin-upload
description: 当需要登录抖音账号、校验 Cookie、上传视频或发布图文时使用此 skill。通过 `uv run mpau` 执行，无需额外脚本。
---

# 抖音上传 Skill

## 功能概览

| 功能 | 说明 |
| --- | --- |
| 账号登录 | 扫码登录抖音创作者后台并生成 Cookie |
| Cookie 校验 | 检查指定账号 Cookie 是否有效 |
| 视频上传 | 上传并发布抖音视频，支持标题、描述、标签、封面、商品链接、定时发布 |
| 图文发布 | 上传并发布抖音图文，支持多图、标题、正文、标签、定时发布 |
| 二次验证 | 上传触发短信验证码时，通过 `verify` 命令提交验证码 |
| dry-run | 填写发布信息但不点击发布，用于流程验证 |

## 项目路径

所有命令都在项目根目录执行：

```bash
cd <PROJECT_ROOT>
```

## 首次初始化

```bash
uv sync
uv run mpau --help
```

如使用 pip：

```bash
pip install -e .
mpau --help
```

⛔ 不要跳过依赖安装直接运行上传命令。首次安装浏览器驱动和依赖可能较慢。

## 命令契约

### 登录

```bash
# 有头模式，首次登录推荐
uv run mpau douyin login --account <account_name> --headed

# 无头模式
uv run mpau douyin login --account <account_name> --headless
```

### Cookie 校验

```bash
uv run mpau douyin check --account <account_name>
```

输出 `valid` 或 `invalid`。

### 视频上传

上传建议后台运行，并把 stdout/stderr 重定向到日志文件，Agent 通过轮询日志监控进度和验证码提示。

```bash
uv run mpau douyin upload-video \
  --account <account_name> \
  --file <absolute path to video file> \
  --title "视频标题" \
  --desc "视频描述" \
  --tags "tag1,tag2,tag3" \
  --headed > /tmp/douyin_upload.log 2>&1 &
```

轮询日志：

```bash
while true; do
  cat /tmp/douyin_upload.log
  grep -q "视频发布成功\|cookie 更新完毕\|upload.*success\|UPLOAD_FAILED\|ERROR" /tmp/douyin_upload.log 2>/dev/null && break
  sleep 5
done
```

⛔ 不要只执行一次 `sleep N && cat`。必须持续轮询日志，及时发现 `[VERIFY_REQUIRED]` 和成功/失败信号。

**视频参数：**

| 参数 | 说明 | 示例 |
| --- | --- | --- |
| `--account <name>` | 本地账号昵称 | `--account shop1` |
| `--file <path>` | 视频文件绝对路径 | `--file /path/video.mp4` |
| `--title <title>` | 视频标题 | `--title "新品测评"` |
| `--desc <desc>` | 视频描述 | `--desc "真实体验分享"` |
| `--tags <tags>` | 逗号分隔标签，不带 `#` | `--tags "宠物,测评"` |
| `--thumbnail <path>` | 兼容旧参数，作为竖版封面 | `--thumbnail /path/cover.jpg` |
| `--thumbnail-landscape <path>` | 横版封面 | `--thumbnail-landscape /path/cover-4x3.jpg` |
| `--thumbnail-portrait <path>` | 竖版封面 | `--thumbnail-portrait /path/cover-3x4.jpg` |
| `--product-link <url>` | 商品链接，需要账号有相关权限 | `--product-link https://...` |
| `--product-title <title>` | 商品短标题，建议 10 字内 | `--product-title "试用装"` |
| `--schedule "YYYY-MM-DD HH:MM"` | 定时发布，需至少提前约 2 小时 | `--schedule "2026-06-05 18:00"` |
| `--headless` / `--headed` | 无头/有头模式 | 首次建议 `--headed` |
| `--debug` | 调试模式，失败时保留更多信息 | — |
| `--dry-run` | 填好内容和声明但不点击发布 | — |

抖音可能要求「自主声明」。上传器默认选择「无需添加自主声明」。页面变化验证时建议先用 `--dry-run`。

### 图文发布

```bash
uv run mpau douyin upload-note \
  --account <account_name> \
  --images <image1 path> <image2 path> \
  --title "图文标题" \
  --note "图文正文" \
  --tags "tag1,tag2" \
  --headed > /tmp/douyin_upload.log 2>&1 &
```

**图文参数：**

| 参数 | 说明 |
| --- | --- |
| `--images <paths...>` | 图片路径列表 |
| `--title <title>` | 图文标题 |
| `--note <text>` | 图文正文 |
| `--tags <tags>` | 逗号分隔标签 |
| `--schedule "YYYY-MM-DD HH:MM"` | 定时发布 |
| `--headless` / `--headed` | 无头/有头模式 |

## 标准工作流

### 新账号首次使用

```text
1. uv sync / 安装依赖
2. 执行登录流程：check → login → check
3. 执行上传任务
```

### 日常上传

```text
1. mpau douyin check --account <name>
2. valid   → 直接上传
   invalid → 重新登录后上传
```

### 批量上传

CLI 一次只支持一个 `--file`。批量任务由 Agent 拆成多次单文件上传：

```text
1. 列出待上传文件
2. 让用户确认文件列表、标题规则、标签规则、是否定时
3. 只做一次登录校验
4. 逐个上传
5. 单个失败则记录原因并继续下一个
6. 最后输出成功/失败汇总
```

## 登录流程

### Step 0：先校验 Cookie

```bash
uv run mpau douyin check --account <account_name>
```

- 输出 `valid`：跳过登录，继续原任务
- 输出 `invalid`：进入登录流程

⛔ 不要跳过这一步直接登录。如果 Cookie 有效，登录命令可能很快退出，导致 Agent误等二维码。

### Step 1：清理旧二维码

```bash
rm -f cookies/*_login_qrcode_*.png
```

### Step 2：后台启动登录并立刻提示用户

```bash
uv run mpau douyin login --account <account_name> --headed &
```

启动后立即告诉用户：

```text
浏览器正在启动，请稍等。首次运行可能需要下载浏览器驱动，1–2 分钟没有窗口是正常的。

浏览器打开后，请使用抖音 App 扫码登录。

如果出现身份验证、短信验证码、人脸验证等页面，请在浏览器中手动完成。

完成后告诉我“登录完成”，我会自动校验并继续。
```

然后停止等待用户确认，不要继续轮询或重复启动登录。

### Step 3：远程环境二维码兜底

如果用户看不到浏览器窗口，轮询二维码文件并展示：

```bash
for i in $(seq 1 45); do
  QR=$(ls -t cookies/*_login_qrcode_*.png 2>/dev/null | head -1)
  if [ -n "$QR" ]; then echo "$QR"; break; fi
  sleep 2
done
```

拿到路径后用平台支持的图片展示方式展示给用户，不要打印 Cookie 内容。

### Step 4：用户确认后校验

```bash
uv run mpau douyin check --account <account_name>
```

- `valid`：登录成功，立即继续原任务
- `invalid`：提示用户登录可能未完成，询问是否重试

## 短信验证码流程

上传日志出现：

```text
[VERIFY_REQUIRED] phone=xxx account=yyy
```

说明抖音触发短信验证。

### Step 1：立刻询问用户验证码

```text
抖音触发了短信验证，系统已经自动点击“获取验证码”。请查看 {phone} 收到的短信，并把验证码告诉我。
```

### Step 2：提交验证码

```bash
uv run mpau douyin verify --account <account> --code <code>
```

输出 `verify_code_submitted` 后，继续轮询上传日志。

⛔ 不要在验证码状态下反复等待超过 2 分钟不处理。

## Cookie 管理

Cookie 位置：

```text
cookies/douyin_<account_name>.json
```

规则：

- Cookie 会在成功登录和成功上传后刷新
- Cookie 失效后重新登录
- 不要打印、分享、提交 Cookie 文件

## 上传监控规则

轮询 `/tmp/douyin_upload.log`：

```text
1. 启动后等待 20–30 秒再首次读取日志
2. 出现上传中日志 → 正常等待
3. 出现上传完成日志 → 进入发布阶段
4. 出现 [VERIFY_REQUIRED] → 执行短信验证码流程
5. 发布阶段超过 2 分钟无进展 → 判断可能卡住
6. 全流程超过 10 分钟无成功信号 → 判断可能卡住
7. 成功信号：视频发布成功 + cookie 更新完毕
8. 失败信号：UPLOAD_FAILED / ERROR / ❌，立即停止并摘录错误
```

卡住处理：

```bash
pkill -f "mpau douyin upload"
```

然后建议用户用 `--headed --debug` 重试，并在浏览器里手动完成验证。

## Windows 非 ASCII 路径规则

Windows PowerShell 5.1 对中文路径可能编码错误。遇到中文路径时，不要直接把路径写进命令，使用变量：

```powershell
$file = (Get-ChildItem "D:\Downloads\" -Filter "*20250530*" | Select-Object -First 1).FullName
uv run mpau douyin upload-video --account <account> --file "$file" --title "Title"
```

## 故障排查

| 现象 | 原因 | 处理方式 |
| --- | --- | --- |
| `mpau: command not found` | 未安装包或虚拟环境未激活 | `uv pip install -e .` 或激活虚拟环境 |
| `uv: command not found` | 未安装 uv | `pip install uv` 或使用 pip 安装项目 |
| 浏览器不出现 | 浏览器驱动未安装或首次下载中 | `uv run python -m patchright install chromium` |
| Cookie 失效 | 长时间未使用或账号被踢 | 重新登录 |
| 商品链接未设置 | 账号无商品权限 | 开通权限；视频本身可继续发布 |
| 定时失败 | 时间不足 2 小时或格式错误 | 使用未来时间，格式 `YYYY-MM-DD HH:MM` |
| 二维码过期 | 扫码超时 | 登录流程会刷新二维码 |
| 扫码后卡住 | 平台要求二次验证 | 在有头浏览器里完成验证 |

## 降级策略

| 不可用项 | 影响 | 处理方式 |
| --- | --- | --- |
| Chrome 未安装 | 无法启动浏览器 | 停止并提示安装 Chrome |
| patchright 浏览器驱动缺失 | 浏览器启动失败 | 安装 chromium 驱动后重试 |
| Cookie 失效 | 无法直接上传 | 执行登录流程 |
| 网络不稳定 | 上传失败或超时 | 提示用户稍后重试，建议 `--headed` |
| 商品权限不足 | 商品挂载失败 | 不绕过权限，提示用户确认账号权限 |
