---
name: tmall-upload
description: 当需要登录淘宝/天猫光合、校验 Cookie 或上传光合视频时使用此 skill。通过 `uv run mpau` 执行，无需额外脚本。
---

# 天猫 / 淘宝光合上传 Skill

## 功能概览

| 功能 | 说明 |
| --- | --- |
| 账号登录 | 打开淘宝/天猫光合，用户在浏览器中完成扫码、密码或短信登录，并自动保存 Cookie |
| Cookie 校验 | 检查指定账号 Cookie 是否有效 |
| 视频上传 | 上传并发布光合视频，支持标题、描述、话题、活动话题、商品挂载、定时发布 |
| dry-run | 完成填写但不点击发布 |

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

淘宝/天猫光合采用人工登录模式：命令会打开浏览器，用户在浏览器中完成登录和风控验证。

```bash
uv run mpau tmall login --account <account_name> --headed
uv run mpau tmall login --account <account_name> --headless
```

### Cookie 校验

```bash
uv run mpau tmall check --account <account_name>
```

输出 `valid` 或 `invalid`。

### 视频上传

建议后台运行，并把 stdout/stderr 重定向到日志文件，Agent 通过轮询日志监控进度。

```bash
uv run mpau tmall upload-video \
  --account <account_name> \
  --file <absolute path to video file> \
  --title "视频标题" \
  --desc "视频描述" \
  --tags "tag1,tag2,tag3" \
  --headed > /tmp/tmall_upload.log 2>&1 &
```

轮询日志：

```bash
while true; do
  cat /tmp/tmall_upload.log
  grep -q "cookie 更新完毕\|UPLOAD_FAILED\|ERROR" /tmp/tmall_upload.log 2>/dev/null && break
  sleep 5
done
```

**完整参数：**

| 参数 | 必填 | 说明 | 示例 |
| --- | --- | --- | --- |
| `--account <name>` | 是 | 本地账号昵称 | `--account shop1` |
| `--file <path>` | 是 | 视频文件绝对路径 | `--file /path/video.mp4` |
| `--title <title>` | 是 | 视频标题，最多 30 字 | `--title "老年犬软粮测评"` |
| `--desc <desc>` | 否 | 视频描述，最多 1000 字 | `--desc "适合老年犬的软粮"` |
| `--tags <tags>` | 否 | 逗号分隔话题，最多保留 4 个 | `--tags "老年犬,软粮"` |
| `--goods-id <ID>` | 否 | 淘宝/天猫商品 ID，纯数字 | `--goods-id "1001817898897"` |
| `--activity-topic <keyword>` | 否 | 活动话题；空值使用平台推荐，传关键词则搜索 | `--activity-topic "宠物"` |
| `--schedule "YYYY-MM-DD HH:MM"` | 否 | 定时发布，必须是未来时间 | `--schedule "2026-06-05 10:30"` |
| `--dry-run` | 否 | 完成填写但不点击发布 | `--dry-run` |
| `--headless` / `--headed` | 否 | 无头/有头模式，默认建议有头 | `--headed` |
| `--debug` | 否 | 调试模式 | — |

## 平台规则

### 标题

- 必填，最多 30 字。
- 会作为光合视频标题展示。

### 描述和话题

- `--desc` 可选，最多 1000 字。
- `--tags` 会按话题形式输入到描述编辑器中。
- 最多保留 4 个标签，超过后自动截断并记录 warning。

### 商品挂载

- `--goods-id` 是纯数字淘宝/天猫商品 ID。
- 输入 ID 后，上传器会点击搜索图标并等待结果刷新。
- 如果无搜索结果、结果未加载、商品无价格或勾选失败，上传会报错停止。
- 不会自动改用默认推荐商品。

### 活动话题

光合的活动话题是官方投稿活动，与描述里的普通 `#tag` 不同。

两种模式：

- 不传 `--activity-topic`：自动选择平台推荐的第一张活动卡；如果平台暂无推荐，则静默跳过。
- 传关键词：打开话题选择弹窗，搜索关键词，选择第一个结果；无结果则报错停止。

### 定时发布

- 格式必须是 `YYYY-MM-DD HH:MM`。
- 必须是未来时间。
- 页面日历有可选范围，只有可点击日期才能发布。
- 上传器会点击日历并校验最终页面值是否等于目标时间。
- 如果日期不可选或时间校验失败，上传停止，不会自动切换立即发布。

### 创作者声明

上传器会自动选择「内容无需标注」。如果页面结构变化找不到选项，会报错提示用有头模式检查。

### dry-run

`--dry-run` 会完成视频上传、标题/描述、商品、活动话题、定时、创作者声明等步骤，但不点击发布按钮。截图保存到 `/tmp/tmall_dry_run_<timestamp>.png`。

## 登录流程

### Step 0：先校验 Cookie

```bash
uv run mpau tmall check --account <account_name>
```

- `valid`：跳过登录，继续原任务
- `invalid`：进入登录流程

### Step 1：使用 nohup 后台启动登录

```bash
nohup uv run mpau tmall login --account <account_name> --headed > /tmp/tmall_login_<account_name>.log 2>&1 < /dev/null &
```

启动后立即提示用户：

```text
浏览器正在启动，请稍等。

浏览器打开后会进入淘宝光合，并跳转到淘宝登录页。

请在浏览器中完成登录（扫码、密码或短信验证均可）。如果出现 passport.taobao.com 风控验证页，也请一并完成。

进入光合首页后告诉我“登录完成”，我会自动校验并继续。
```

然后停止等待用户确认。

### Step 1.5：确认登录进程仍在

```bash
sleep 5 && pgrep -f "mpau tmall login --account <account_name>" && echo "login_alive" || echo "login_missing"
```

- `login_alive`：等待用户完成登录
- `login_missing`：最多重启一次登录命令

⛔ 不要因为暂时没有日志输出就判断登录失败。登录流程可能长时间等待用户操作。

### Step 2：用户确认后校验

```bash
uv run mpau tmall check --account <account_name>
```

- `valid`：立即继续原任务
- `invalid`：提示登录可能未完成，询问是否重试

## Cookie 管理

Cookie 位置：

```text
cookies/tmall_<account_name>.json
```

规则：

- 成功上传后会刷新 Cookie
- Cookie 失效后重新登录
- 不要打印、分享、提交 Cookie 文件

## 上传监控规则

轮询 `/tmp/tmall_upload.log`：

```text
1. 启动后等待 20–30 秒再首次读取日志
2. “上传前检查通过” → Cookie 有效
3. “小人正在赶往淘宝光合发视频页面” → 打开发布页
4. “小人开始上传视频” + “小人正在等待视频上传完成” → 上传中
5. “视频上传完成，发布表单已可编辑” → 表单可填写
6. “视频标题已填写” / “视频描述已填写” → 元数据完成
7. “已点击放大镜搜索按钮” → 商品搜索中
8. “商品 xxx 添加完成” → 商品挂载成功
9. 活动话题：已参与推荐活动 / 已搜索并参与活动 / 平台暂无推荐则跳过
10. “定时发布时间已设置” → 定时完成
11. “创作者声明已选择：内容无需标注” → 声明完成
12. “点击定时发布按钮” 或 “点击立即发布按钮” → 提交中
13. “视频已提交发布” + “cookie 更新完毕” → 完成
14. “Dry run 模式：跳过发布” → 验证完成，未真实发布
15. 出现 “❌” / “UPLOAD_FAILED” / “ERROR” → 立即停止并摘录错误
```

常见错误：

| 错误 | 处理 |
| --- | --- |
| 商品 ID 在本店商品库中搜索不到 | 让用户核对 ID、上下架状态、是否属于当前店铺 |
| 商品 ID 搜索结果未加载完成 | 建议稍后重试或用 `--headed` 观察页面 |
| 商品卡片无价格信息 | 商品状态可能异常，让用户检查后台 |
| 商品 ID 搜索未触发或结果未刷新 | 建议用 `--headed` 重试 |
| 话题活动关键词无结果 | 让用户换关键词或不传 `--activity-topic` |
| 定时日期不可选 | 引用错误里的可点击范围，让用户换日期 |
| 定时时间校验失败 | 停止上传，避免错误定时 |
| Cookie 失效 | 执行登录流程后重试 |

卡住处理：

```bash
pkill -f "mpau tmall upload-video"
```

## 故障排查

| 现象 | 原因 | 处理方式 |
| --- | --- | --- |
| `mpau: command not found` | 未安装包或虚拟环境未激活 | `uv pip install -e .` |
| 浏览器不出现 | 浏览器驱动未安装 | `uv run python -m patchright install chromium` |
| Cookie 失效 | 长时间未使用或被踢 | 重新登录 |
| 登录后停留在淘宝页面 | 风控验证未完成 | 让用户完成全部验证步骤 |
| 商品搜索无结果 | ID 错误、商品下架、不属于账号 | 核对商品 ID |
| 商品搜索卡住 | 搜索未触发或接口慢 | 用 `--headed` 重试 |
| 定时失败 | 时间过去、格式错误或超出可选范围 | 使用未来且可点击的时间 |
| 视频重复提示 | 平台提示重复内容 | 仅为平台 warning，不一定影响发布 |

## 降级策略

| 不可用项 | 影响 | 处理方式 |
| --- | --- | --- |
| Chrome 未安装 | 无法启动浏览器 | 停止并提示安装 Chrome |
| 浏览器驱动缺失 | 浏览器启动失败 | 安装驱动后重试 |
| Cookie 失效 | 无法直接上传 | 登录后重试 |
| 网络不稳定 | 上传失败或超时 | 告知用户，确认后重试 |
| 商品 ID 无结果 | 商品挂载失败 | 停止上传，让用户核对 ID |
| 定时时间已过 | 上传前报错 | 让用户提供未来时间 |
| 定时日期超出可选范围 | 日期不可点 | 引用错误里的范围，让用户换时间 |
