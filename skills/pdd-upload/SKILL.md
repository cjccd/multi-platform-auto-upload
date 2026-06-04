---
name: pdd-upload
description: 当需要完成拼多多 / 多多视频账号登录、Cookie 校验或视频上传时使用此 skill。通过 `uv run mpau` 执行，无需额外脚本。
---

# 拼多多上传 Skill

## 功能概览

| 功能 | 说明 |
| --- | --- |
| 账号登录 | 打开拼多多登录页，用户手动扫码或账号密码登录，并自动保存 Cookie |
| Cookie 校验 | 检查指定账号 Cookie 是否有效 |
| 视频上传 | 上传并发布多多视频，支持描述、话题、商品 ID 挂载、定时发布 |
| dry-run | 完成上传和填写，但不点击发布按钮 |

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

⛔ 不要跳过 `uv sync` 直接执行上传命令。

## 命令参考

### 登录

拼多多采用人工登录模式：命令会打开浏览器，用户在浏览器中完成扫码或账号密码登录。

```bash
uv run mpau pdd login --account <account_name> --headed
uv run mpau pdd login --account <account_name> --headless
```

### Cookie 校验

```bash
uv run mpau pdd check --account <account_name>
```

输出 `valid` 或 `invalid`。

### 视频上传

建议后台运行并把日志重定向到文件，Agent 通过轮询日志监控进度。

```bash
uv run mpau pdd upload-video \
  --account <account_name> \
  --file <absolute path to video file> \
  --desc "视频描述" \
  --tags "tag1,tag2,tag3" \
  --headed > /tmp/pdd_upload.log 2>&1 &
```

轮询日志：

```bash
while true; do
  cat /tmp/pdd_upload.log
  grep -q "视频发布成功\|cookie 更新完毕\|UPLOAD_FAILED\|ERROR" /tmp/pdd_upload.log 2>/dev/null && break
  sleep 5
done
```

**完整参数：**

| 参数 | 必填 | 说明 | 示例 |
| --- | --- | --- | --- |
| `--account <name>` | 是 | 本地账号昵称 | `--account shop1` |
| `--file <path>` | 是 | 视频文件绝对路径 | `--file /path/video.mp4` |
| `--desc <description>` | 是 | 视频描述；PDD 没有独立标题字段 | `--desc "零食测评"` |
| `--tags <tags>` | 否 | 逗号分隔标签，不带 `#` | `--tags "零食,测评"` |
| `--goods-id <ID>` | 否 | 拼多多商品 ID | `--goods-id "622747638382"` |
| `--schedule "YYYY-MM-DD HH:MM"` | 否 | 定时发布时间 | `--schedule "2026-06-05 10:00"` |
| `--dry-run` | 否 | 填写完成但不点击发布 | `--dry-run` |
| `--headless` / `--headed` | 否 | 无头/有头模式，默认建议有头 | `--headed` |
| `--debug` | 否 | 调试模式 | — |

## 平台规则

### 定时发布

- 定时时间必须是未来时间。
- 定时发布区域只有在关联商品后才出现，因此 `--schedule` 必须和 `--goods-id` 一起使用。
- 如果没有 `--goods-id`，页面不会出现定时选项。
- 时间格式必须是 `YYYY-MM-DD HH:MM`。

### 商品挂载

- `--goods-id` 是纯数字拼多多商品 ID。
- 商品 ID 可在拼多多商家后台商品管理中查看。
- 关联成功后，视频会展示商品浮窗。
- 如果商品不存在或已下架，上传会报错并停止，不会自动无商品发布。

### 跨域登录态

拼多多登录态主要在 `mms.pinduoduo.com`，视频发布在 `live.pinduoduo.com`。上传器会自动处理跨域 SSO 跳转，用户无需额外操作。

### dry-run

`--dry-run` 会完成视频上传、描述、商品、定时等设置，但不点击发布按钮，用于验证流程。截图保存到 `/tmp/pdd_dry_run.png`。

## 标准工作流

### 新账号首次使用

```text
1. uv sync
2. 执行登录流程：check → login → check
3. 执行上传任务
```

### 日常上传

```text
1. mpau pdd check --account <name>
2. valid   → 直接上传
   invalid → 登录后上传
```

### 批量上传

CLI 一次只支持单文件。批量任务由 Agent 拆成多次上传：

```text
1. 列出文件
2. 让用户确认上传列表、描述规则、标签、商品 ID、是否定时
3. 只做一次登录校验
4. 逐个上传
5. 单个失败则记录原因并继续
6. 最后输出汇总
```

## 登录流程

### Step 0：先校验 Cookie

```bash
uv run mpau pdd check --account <account_name>
```

- `valid`：跳过登录，继续原任务
- `invalid`：进入登录流程

⛔ 不要跳过这一步直接启动登录。

### Step 1：后台启动登录并提示用户

```bash
uv run mpau pdd login --account <account_name> --headed &
```

启动后立即提示用户：

```text
浏览器正在启动，请稍等。

浏览器打开后会显示拼多多登录页，请直接在浏览器中完成登录（扫码或账号密码均可）。

完成后告诉我“登录完成”，我会自动校验并继续。
```

然后停止等待用户确认，不要继续轮询或执行其他动作。

### Step 2：用户确认后校验

```bash
uv run mpau pdd check --account <account_name>
```

- `valid`：登录成功，立即继续原任务
- `invalid`：提示登录可能未完成，询问是否重试

## Cookie 管理

Cookie 位置：

```text
cookies/pdd_<account_name>.json
```

规则：

- 成功上传后会刷新 Cookie
- Cookie 失效后重新登录
- 不要打印、分享、提交 Cookie 文件

## 上传监控规则

轮询 `/tmp/pdd_upload.log`：

```text
1. 启动后等待 20–30 秒再首次读取日志
2. “小人正在努力上传视频” → 正常上传中
3. “视频已经传完啦” → 进入发布设置阶段
4. “商品 xxx 添加完成” → 商品挂载成功
5. “定时发布时间已设置” → 定时设置成功
6. “已点击发布按钮” → 等待发布结果
7. “视频发布成功” + “cookie 更新完毕” → 完成
8. “Dry run 模式：跳过发布” → 验证完成，未真实发布
9. 出现 “❌” / “UPLOAD_FAILED” / “ERROR” → 立即停止并摘录错误
```

常见错误：

| 错误 | 处理 |
| --- | --- |
| 商品不存在或已下架 | 让用户核对商品 ID，不自动重试 |
| Cookie 不存在或已失效 | 执行登录流程后重试 |
| 视频上传超时 | 建议用 `--headed` 重试，可能是网络问题 |
| 发布后未检测到成功信号 | 建议用 `--headed` 重试并人工确认后台状态 |

卡住处理：

```bash
pkill -f "mpau pdd upload-video"
```

## 故障排查

| 现象 | 原因 | 处理方式 |
| --- | --- | --- |
| `mpau: command not found` | 未安装包或虚拟环境未激活 | `uv pip install -e .` |
| 浏览器不出现 | 浏览器驱动未安装 | `uv run python -m patchright install chromium` |
| Cookie 失效 | 登录态过期 | 重新登录 |
| 定时选项不可见 | 未提供 `--goods-id` | 定时发布必须先关联商品 |
| 商品搜索无结果 | ID 错误、商品下架或不属于账号 | 核对商品 ID |
| 发布卡住 | 可能触发平台验证或网络问题 | 用 `--headed` 重试 |
| 文件存在但报 File not found | Windows 非 ASCII 路径编码问题 | 使用 `Get-ChildItem` 获取 `.FullName` 后传入 |

## 降级策略

| 不可用项 | 影响 | 处理方式 |
| --- | --- | --- |
| Chrome 未安装 | 无法启动浏览器 | 停止并提示安装 Chrome |
| 浏览器驱动缺失 | 浏览器启动失败 | 安装驱动后重试 |
| Cookie 失效 | 无法直接上传 | 登录后重试 |
| 网络不稳定 | 上传失败或超时 | 告知用户，确认后重试 |
| 商品 ID 无结果 | 商品挂载失败 | 停止上传，让用户核对 ID |
| 定时时间已过 | 日期不可选 | 让用户提供未来时间 |
