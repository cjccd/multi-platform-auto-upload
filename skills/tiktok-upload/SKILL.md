---
name: tiktok-upload
description: 当需要通过 `mpau tiktok` CLI 登录 TikTok Studio、校验 Cookie 或上传视频时使用此 skill。
---

# TikTok 上传 Skill

统一使用项目 CLI 作为唯一执行入口：

```bash
mpau tiktok <action> ...
```

## 项目路径

所有命令都在项目根目录执行：

```bash
cd <PROJECT_ROOT>
```

## 初始化

```bash
uv sync
python -m playwright install chromium
python -m patchright install chromium
```

TikTok 和百家号的 legacy uploader 使用 Playwright；其他主线浏览器 uploader 主要使用 Patchright。

## 命令

### 登录

TikTok 登录是人工登录模式：命令会打开浏览器，用户在浏览器中完成登录，然后继续被暂停的 Playwright 会话。

```bash
uv run mpau tiktok login --account <account_name>
```

### 校验 Cookie

```bash
uv run mpau tiktok check --account <account_name>
```

输出 `valid` 或 `invalid`。

### 上传视频

```bash
uv run mpau tiktok upload-video \
  --account <account_name> \
  --file <absolute path to video file> \
  --title "Video title" \
  --tags "tag1,tag2" \
  --thumbnail <optional cover image>
```

定时发布：

```bash
uv run mpau tiktok upload-video \
  --account <account_name> \
  --file <absolute path to video file> \
  --title "Video title" \
  --tags "tag1,tag2" \
  --schedule "2026-06-05 18:30"
```

## 注意事项

- 当前 TikTok 仅支持视频上传。
- uploader 会先把 TikTok Studio 切换到英文界面再上传。
- `--thumbnail` 是可选封面参数。
- Cookie 文件保存在 `cookies/tiktok_<account_name>.json`。
- 不要打印、分享或提交 Cookie 文件。
