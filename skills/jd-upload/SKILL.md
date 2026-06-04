---
name: jd-upload
description: 当需要登录京东京麦、校验 Cookie 或向京东商家内容平台（逛-视频）上传视频时使用此 skill。通过 `uv run mpau` 执行，无需额外脚本。
---

# 京东上传 Skill

## 功能概览

| 功能 | 说明 |
| --- | --- |
| 账号登录 | 打开京东京麦发布中心，用户在浏览器中完成密码、短信或扫码登录，并自动保存 Cookie |
| Cookie 校验 | 检查指定账号 Cookie 是否有效 |
| 视频上传 | 上传京东商家视频，支持标题、商品挂载、原创开关、定时发布 |
| dry-run | 完成填写但不点击发布 |
| keep-browser | 发布后保留浏览器，便于人工检查 |

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

⛔ 不要跳过依赖安装直接运行上传命令。

## 命令参考

### 登录

京东京麦采用人工登录模式：命令会打开浏览器，用户在浏览器中完成登录和风控验证。

```bash
uv run mpau jd login --account <account_name> --headed
```

### Cookie 校验

```bash
uv run mpau jd check --account <account_name>
```

输出 `valid` 或 `invalid`。

### 视频上传

建议后台运行，并把 stdout/stderr 重定向到日志文件，Agent 通过轮询日志监控进度。

```bash
uv run mpau jd upload-video \
  --account <account_name> \
  --file <absolute path to video file> \
  --title "视频标题，5-27字" \
  --headed > /tmp/jd_upload.log 2>&1 &
```

轮询日志：

```bash
while true; do
  cat /tmp/jd_upload.log
  grep -q "cookie 更新完毕\|UPLOAD_FAILED\|ERROR" /tmp/jd_upload.log 2>/dev/null && break
  sleep 5
done
```

**完整参数：**

| 参数 | 必填 | 说明 | 示例 |
| --- | --- | --- | --- |
| `--account <name>` | 是 | 本地账号昵称 | `--account shop1` |
| `--file <path>` | 是 | 视频文件绝对路径，支持 mp4/mov/mkv 等 | `--file /path/video.mp4` |
| `--title <title>` | 是 | 视频标题，严格 5–27 字 | `--title "新品真实测评"` |
| `--goods-id <ID>` | 否 | 京东商品 ID，纯数字，走站内搜索 | `--goods-id "10204078771126"` |
| `--original` | 否 | 开启自主原创；账号无权限会失败并停止 | `--original` |
| `--schedule "YYYY-MM-DD HH:MM"` | 否 | 定时发布，必须是未来且在平台可选范围内 | `--schedule "2026-06-05 12:30"` |
| `--dry-run` | 否 | 完成填写但不点击发布 | `--dry-run` |
| `--keep-browser` | 否 | 流程结束后保留浏览器 | `--keep-browser` |
| `--headless` / `--headed` | 否 | 无头/有头模式，首次建议有头 | `--headed` |
| `--debug` | 否 | 调试模式 | — |

## 平台规则

### 标题

- 必填。
- 长度必须严格在 5–27 字之间。
- 标题太短或太长时，发布按钮会不可用，上传器会提前报错。

### 视频

- 京东接受 MP4 / MOV / MKV 等常见格式。
- 建议分辨率 720P 以上，时长 15 秒以上。

### 封面

- 当前实现使用京东自动抽取的候选封面。
- 暂不支持自定义封面。

### 商品挂载

- `--goods-id` 必须是纯数字京东商品 ID。
- uploader 使用「站内搜索」tab，不依赖动态 `rc-tabs-*` ID。
- 流程：点击 `+` → 打开商品抽屉 → 切到站内搜索 → 输入 ID → 查询 → 等待价格符号 → 勾选商品 → 确定。
- 搜索无结果、商品不可用、20 秒内未返回有效商品都会报错停止。
- 不会自动降级成无商品发布。

### 创作声明

京东创作声明是必填项。当前实现自动选择「内容无需标注」，这是最通用的安全选项。

### 自主原创

只有用户传 `--original` 才会尝试开启。

- 如果 switch 可用，则开启并校验。
- 如果账号无权限或当前类目不支持，上传会报错停止。
- 不要绕过或忽略该错误。

### 定时发布

- `--schedule` 格式必须是 `YYYY-MM-DD HH:MM`。
- 必须是未来时间。
- 京东日历有平台可选范围，通常约 30 天内。
- 如果指定日期不可点，上传器会报错并给出当前可点击范围。
- 不会自动改成立即发布或今天发布。

### dry-run

`--dry-run` 完成视频上传、标题、商品、创作声明、定时设置，但不点击发布按钮。截图保存到 `/tmp/jd_dry_run_<timestamp>.png`。

### keep-browser

`--keep-browser` 会在流程结束后保持浏览器打开，进程最多睡眠约 24 小时，便于检查页面状态。需要退出时可手动关闭浏览器或杀掉进程。

```bash
pkill -f "mpau jd upload-video"
```

## 登录流程

### Step 0：先校验 Cookie

```bash
uv run mpau jd check --account <account_name>
```

- `valid`：跳过登录，继续原任务
- `invalid`：进入登录流程

### Step 1：使用 nohup 后台启动登录

```bash
nohup uv run mpau jd login --account <account_name> --headed > /tmp/jd_login_<account_name>.log 2>&1 < /dev/null &
```

启动后立即提示用户：

```text
浏览器正在启动，请稍等。

浏览器打开后会进入京东京麦发布中心，并跳转到京东登录页。

请在浏览器中完成登录（密码、短信验证或扫码均可）。如果出现 passport.jd.com 或 safe.jd.com 风控验证页，也请一并完成。

进入京麦发布中心后告诉我“登录完成”，我会自动校验并继续。
```

然后停止等待用户确认。

### Step 1.5：确认登录进程仍在

```bash
sleep 5 && pgrep -f "mpau jd login --account <account_name>" && echo "login_alive" || echo "login_missing"
```

- `login_alive`：等待用户完成登录
- `login_missing`：最多重启一次登录命令

⛔ 不要因为日志暂时没有输出就判断失败。

### Step 2：用户确认后校验

```bash
uv run mpau jd check --account <account_name>
```

- `valid`：立即继续原任务
- `invalid`：提示登录可能未完成，询问是否重试

## Cookie 管理

Cookie 位置：

```text
cookies/jd_<account_name>.json
```

规则：

- 成功登录和成功上传后会刷新 Cookie
- Cookie 失效后重新登录
- 不要打印、分享、提交 Cookie 文件

## 上传监控规则

轮询 `/tmp/jd_upload.log`：

```text
1. 启动后等待 10–20 秒再首次读取日志
2. “上传前检查通过” → Cookie 有效
3. “小人正在赶往京东京麦发视频页面” → 打开发布页
4. “小人开始上传视频” + “小人正在等待视频上传完成” → 上传中
5. “视频上传完成（Ns 后发布按钮可点）” → 可填写信息
6. “填写正文标题” → 标题已填
7. 商品流程：准备添加商品 → 已点查询 → 已勾选商品 → 商品已关联
8. “创作声明已选择: 内容无需标注” → 声明完成
9. 原创流程：自主原创已开启；如果 switch 不可用则停止
10. 定时流程：已选择日期/小时/分钟 → 定时发布时间已设置
11. dry-run：Dry run 模式：跳过发布
12. 真实发布：点击发布按钮
13. 成功：视频已提交发布 + cookie 更新完毕
14. 失败：❌ / UPLOAD_FAILED / ERROR，立即停止并摘录错误
```

### 验证码 / 安全验证

点击发布后，京东可能出现安全验证码（如旋转图）。日志会显示「检测到安全验证码，上传已暂停」。

处理方式：

- 告知用户在浏览器中完成验证码。
- 不要把这个状态当作失败。
- 等待日志出现「验证码已完成」。
- 如果 10 分钟未解决，则上传失败，需要重新上传。

## 常见错误处理

| 错误 | 处理 |
| --- | --- |
| 京东视频标题长度必须 5-27 字 | 让用户提供合法标题 |
| 京东商品 ID 必须为纯数字 | 让用户检查 ID |
| 商品 ID 在京东站内搜索无结果 | 让用户核对 ID 或商品状态，不自动重试 |
| 商品 ID 在京东站内搜索不可用 | 报告失效原因，让用户检查商品是否上架 |
| 该账号的自主原创 switch 当前不可用 | 提示账号无权限或类目不支持，去掉 `--original` 后重试 |
| 等待视频上传完成超时 | 建议用 `--headed` 重试 |
| 定时日期不可选 | 引用错误中的可点击范围，让用户改日期 |
| 点击发布后未检测到成功信号 | 建议有头模式重试并人工确认后台 |

卡住处理：

```bash
pkill -f "mpau jd upload-video"
```

## 故障排查

| 现象 | 原因 | 处理方式 |
| --- | --- | --- |
| `mpau: command not found` | 未安装包或虚拟环境未激活 | `uv pip install -e .` |
| 浏览器不出现 | 浏览器驱动未安装 | `uv run python -m patchright install chromium` |
| Cookie 失效 | 长时间未使用 | 重新登录 |
| 登录后仍在 passport/safe 页面 | 风控验证未完成 | 让用户完成所有验证步骤 |
| 商品搜索无结果 | ID 错误、商品下架或不可用 | 核对商品 ID 和商品状态 |
| 标题不合法 | 长度不在 5–27 字 | 修改标题 |
| 定时失败 | 时间过去、格式错误或超出日历范围 | 使用未来且可点击的时间 |

## 暂不支持

以下能力后续再补：

- 活动话题
- 分章节
- 自定义封面
- 标签类型
