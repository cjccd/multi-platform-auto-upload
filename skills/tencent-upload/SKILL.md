---
name: tencent-upload
description: 当需要登录微信视频号助手、校验 Cookie 或上传视频号视频时使用此 skill。通过 `uv run mpau` 执行，无需额外脚本。
---

# 视频号上传 Skill

## 功能概览

| 功能 | 说明 |
| --- | --- |
| 账号登录 | 打开视频号助手，用户使用微信扫码登录，并自动保存 Cookie |
| Cookie 校验 | 检查指定账号 Cookie 是否有效 |
| 视频上传 | 上传并发布视频号视频，支持标题、描述、话题、封面、短标题、原创声明、商品挂载、定时发布、保存草稿 |
| 草稿 | 使用 `--draft` 保存草稿，不点击发布 |

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

视频号登录使用微信扫码。有头模式会打开可见浏览器窗口；无头模式会生成二维码图片作为兜底。

```bash
uv run mpau tencent login --account <account_name> --headed
uv run mpau tencent login --account <account_name> --headless
```

### Cookie 校验

```bash
uv run mpau tencent check --account <account_name>
```

输出：

- `valid`：Cookie 有效
- `invalid`：Cookie 不存在或已失效，需要重新登录

### 视频上传

建议后台运行，并把 stdout/stderr 重定向到日志文件，Agent 通过轮询日志监控进度。

```bash
uv run mpau tencent upload-video \
  --account <account_name> \
  --file <absolute path to video file> \
  --title "视频标题" \
  --desc "视频描述" \
  --tags "tag1,tag2,tag3" \
  --headed > /tmp/tencent_upload.log 2>&1 &
```

轮询日志：

```bash
while true; do
  cat /tmp/tencent_upload.log
  grep -q "视频发布成功\|视频草稿保存成功\|cookie 更新完毕\|已终止上传\|上传失败\|RuntimeError\|ERROR" /tmp/tencent_upload.log 2>/dev/null && break
  sleep 5
done
```

**完整参数：**

| 参数 | 必填 | 说明 | 示例 |
| --- | --- | --- | --- |
| `--account <name>` | 是 | 本地账号昵称 | `--account shop1` |
| `--file <path>` | 是 | 视频文件绝对路径 | `--file /path/video.mp4` |
| `--title <title>` | 是 | 写入正文第一行；视频号无独立标题框 | `--title "新品测评"` |
| `--desc <desc>` | 否 | 写在标题和话题之后 | `--desc "真实体验分享"` |
| `--tags <tags>` | 否 | 逗号分隔标签，不带 `#` | `--tags "宠物,测评"` |
| `--goods-id <ID>` | 否 | 微信小店/橱窗商品 ID | `--goods-id "10000517325762"` |
| `--schedule "YYYY-MM-DD HH:MM"` | 否 | 定时发布，需大于当前时间约 2 小时且在页面可选范围内 | `--schedule "2026-06-05 13:01"` |
| `--thumbnail <path>` | 否 | 自定义封面 | `--thumbnail /path/cover.jpg` |
| `--short-title <title>` | 否 | 视频号短标题，约 16 字内 | `--short-title "新品测评"` |
| `--category <category>` | 否 | 声明原创时选择的原创类型 | `--category "生活"` |
| `--draft` | 否 | 保存草稿，不点击发布 | `--draft` |
| `--headless` / `--headed` | 否 | 无头/有头模式，默认建议有头 | `--headed` |
| `--debug` | 否 | 调试模式 | — |

## 平台规则

### 正文、标题和话题

视频号没有单独标题输入框。上传器按以下顺序写入正文编辑器：

```text
标题第一行
#tag1 #tag2
描述
```

`--tags` 使用逗号分隔，上传器会自动加 `#` 并确认话题。

### 短标题

- `--short-title` 可选。
- 如果未提供，上传器会根据 `--title` 自动生成：过滤特殊字符、超过 16 字截断、不足 6 字补空格。
- 如果页面没有短标题输入框，上传器会跳过，不中断上传。

### 封面

- `--thumbnail` 可选。
- 上传器会尝试打开 3:4 封面编辑入口，上传图片并确认。
- 如果当前页面没有封面入口，会记录日志并跳过，不中断上传。

### 原创声明

视频号原创声明入口会因账号权限和页面版本不同而变化。上传器会自动探测可用入口：

- 旧版「视频为原创」复选框
- 新版「声明原创」复选框
- 原创声明协议弹窗
- `--category` 指定原创类型时的分类选择

如果账号没有原创权限，页面通常不展示入口，上传器会跳过，不报错。

### 商品挂载

- `--goods-id` 用于挂载微信小店/橱窗商品。
- 流程：点击链接 → 选择商品 → 搜索商品 ID → 勾选商品 → 添加。
- 如果平台提示不能添加商品、商品未找到或商品无法勾选，上传会报错停止并保存截图。
- 商品找不到时，不允许继续发布，必须让用户确认商品是否属于当前橱窗/小店、是否上架。

### 定时发布

- 格式必须是 `YYYY-MM-DD HH:MM`。
- 时间需大于当前时间约 2 小时。
- 视频号页面通常只支持约 30 天内的可选日期。
- 上传器会校验页面最终值是否等于目标时间。
- 定时失败时会停止上传，不会自动改成立即发布。

### 保存草稿

`--draft` 会点击保存草稿，不点击发布。适合测试流程。

如果日志显示「保存草稿超时」，代表保存状态检测失败，需要用户到后台草稿箱确认，不代表一定已经发布。

## 标准工作流

### 新账号首次使用

```text
1. uv sync
2. 执行登录流程：check → login → check
3. 执行上传任务
```

### 日常上传

```text
1. mpau tencent check --account <name>
2. valid   → 直接上传
   invalid → 登录后上传
```

### 测试上传不发布

优先使用 `--draft`：

```bash
uv run mpau tencent upload-video \
  --account <account_name> \
  --file <absolute path to video file> \
  --title "测试标题" \
  --desc "测试描述" \
  --tags "测试" \
  --draft \
  --headed > /tmp/tencent_upload.log 2>&1 &
```

⛔ 视频号没有 `--dry-run` 参数，不要添加；需要避免真实发布时使用 `--draft`。

### 批量上传

CLI 一次只支持一个 `--file`。批量任务由 Agent 拆成多次单文件上传：

```text
1. 列出文件
2. 让用户确认上传列表、标题规则、描述/标签、商品 ID、是否定时或草稿
3. 只做一次登录校验
4. 逐个上传
5. 单个失败则记录原因并继续
6. 最后输出成功/失败汇总
```

## 登录流程

### Step 0：先校验 Cookie

```bash
uv run mpau tencent check --account <account_name>
```

- `valid`：跳过登录，继续原任务
- `invalid`：进入登录流程

### Step 1：清理旧二维码

```bash
rm -f cookies/*_login_qrcode_*.png
```

### Step 2：使用 nohup 后台启动登录

```bash
nohup uv run mpau tencent login --account <account_name> --headed > /tmp/tencent_login_<account_name>.log 2>&1 < /dev/null &
```

启动后立即提示用户：

```text
浏览器正在启动，请稍等。

浏览器打开后，请使用微信扫码登录视频号助手。

如果没有看到浏览器，或当前是远程环境，请告诉我，我会发送二维码图片。

完成登录后告诉我“登录完成”，我会自动校验并继续。
```

然后停止等待用户确认。

### 二维码图片兜底

如果用户看不到浏览器，轮询二维码文件：

```bash
for i in $(seq 1 45); do
  QR=$(ls -t cookies/*_login_qrcode_*.png 2>/dev/null | head -1)
  if [ -n "$QR" ]; then echo "$QR"; break; fi
  sleep 2
done
```

拿到路径后用平台支持的图片展示方式展示给用户，不要读取或打印 Cookie。

### Step 3：用户确认后校验

```bash
uv run mpau tencent check --account <account_name>
```

- `valid`：登录成功，立即继续原任务
- `invalid`：提示登录可能未完成，询问是否重试

## Cookie 管理

Cookie 位置：

```text
cookies/tencent_<account_name>.json
```

规则：

- 成功上传后会刷新 Cookie
- Cookie 失效后重新登录
- 不要打印、分享、提交 Cookie 文件

## 上传监控规则

轮询 `/tmp/tencent_upload.log`：

```text
1. 启动后等待 20–30 秒再首次读取日志
2. “上传前检查通过” → Cookie 有效
3. “小人开始搬运视频” → 进入上传流程
4. “成功添加 hashtag” / “成功添加 desc” → 正文填写完成
5. “正在上传视频中...” → 等待视频上传和封面生成
6. “视频上传完毕（封面已生成）” → 视频上传完成
7. “封面已经设置完成” → 自定义封面完成；没有该日志不一定失败，可能未提供封面
8. “开始挂载商品” → 商品挂载中
9. “商品 xxx 挂载成功” → 商品挂载完成
10. “定时发布时间已设置” → 定时完成
11. “视频草稿保存成功” → 草稿保存完成
12. “视频发布成功” + “cookie 更新完毕” → 发布完成
13. 出现 RuntimeError / ERROR / 上传失败 → 立即停止并摘录错误
```

常见失败处理：

| 错误 | 处理 |
| --- | --- |
| 商品挂载被视频号拒绝 | 引用错误原文，通常是权限、限额或平台限制，不继续发布 |
| 商品在橱窗中未找到 | 让用户确认商品是否已加入当前橱窗/小店 |
| 商品勾选失败 | 建议有头模式观察页面 |
| 定时时间超出范围 | 让用户选择约 30 天内页面可选时间 |
| 定时时间设置失败 | 停止上传，避免错误定时 |
| 保存草稿超时 | 提示用户检查草稿箱或用有头模式重试 |
| 等待视频上传完成超时 | 网络或平台上传问题，建议稍后有头重试 |
| Cookie 失效 | 执行登录流程后重试 |

卡住处理：

```bash
pkill -f "mpau tencent upload-video"
```

## 故障排查

| 现象 | 原因 | 处理方式 |
| --- | --- | --- |
| `mpau: command not found` | 未安装包或虚拟环境未激活 | `uv pip install -e .` |
| 浏览器不出现 | 浏览器驱动未安装或首次下载中 | `uv run python -m patchright install chromium` |
| Cookie 失效 | 登录态过期或被踢 | 重新登录 |
| 扫码后仍 invalid | 手机端未确认或页面未跳转 | 完成确认后重新 check |
| 商品搜不到 | 商品不在当前橱窗/小店、ID 错误或下架 | 核对商品 |
| 不能添加商品 | 权限、限额或平台限制 | 引用平台错误，不自动发布 |
| 定时失败 | 时间过近、格式错误或超出范围 | 使用可选未来时间 |
| 文件路径存在但报错 | Windows 中文路径编码问题 | 使用 `Get-ChildItem` 获取 `.FullName` |

## 暂不支持

- 地理位置
- 活动
- 图文发布 CLI
