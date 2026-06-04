---
name: baijiahao-upload
description: 当需要通过 `mpau baijiahao` CLI 登录百家号、校验 Cookie 或上传视频时使用此 skill。
---

# 百家号上传 Skill

统一使用项目 CLI 作为唯一执行入口：

```bash
mpau baijiahao <action> ...
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

百家号和 TikTok 的 legacy uploader 使用 Playwright；其他主线浏览器 uploader 主要使用 Patchright。

## 命令

### 登录

百家号登录是人工登录模式：命令会打开浏览器，用户在浏览器中完成登录，然后继续被暂停的 Playwright 会话。

```bash
uv run mpau baijiahao login --account <account_name>
```

### 校验 Cookie

```bash
uv run mpau baijiahao check --account <account_name>
```

输出 `valid` 或 `invalid`。

### 上传视频

```bash
uv run mpau baijiahao upload-video \
  --account <account_name> \
  --file <absolute path to video file> \
  --title "视频标题" \
  --tags "tag1,tag2"
```

定时发布：

```bash
uv run mpau baijiahao upload-video \
  --account <account_name> \
  --file <absolute path to video file> \
  --title "视频标题" \
  --tags "tag1,tag2" \
  --schedule "2026-06-05 18:30"
```

## 注意事项

- 当前百家号仅支持视频上传。
- legacy uploader 的定时时间选择精度有限，提交后建议到百家号后台人工确认。
- Cookie 文件保存在 `cookies/baijiahao_<account_name>.json`。
- 不要打印、分享或提交 Cookie 文件。
