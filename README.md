# Multi Platform Auto Upload

[English](README.md) | [简体中文](README.zh-CN.md)

<p align="center">
  <img src="assets/hero.png" alt="Multi Platform Auto Upload hero banner" width="100%" />
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg" /></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10--3.12-3776AB.svg" />
  <img alt="CLI" src="https://img.shields.io/badge/CLI-mpau-00C2FF.svg" />
  <img alt="Agent Ready" src="https://img.shields.io/badge/AI%20Agent-Ready-8A2BE2.svg" />
  <img alt="Platforms" src="https://img.shields.io/badge/Platforms-10+-14B8A6.svg" />
</p>

<p align="center">
  <b>Stop letting AI agents click around blindly. Give them a real publishing CLI.</b>
</p>

<p align="center">
  <b>One command line for social media publishing, e-commerce content distribution and agent-driven automation.</b>
</p>

Multi Platform Auto Upload is a Python-based automation toolkit for creators, e-commerce sellers and AI agents. It turns repetitive publishing workflows into a unified command line interface: `mpau`.

Upload videos. Publish image/text notes. Attach product links. Schedule posts. Manage multiple accounts. Give your AI agent a tool it can actually call.

---

## Supported platforms

| Platform | Video | Image/Text | Schedule | Product Link / ID | CLI | Skill |
| --- | --- | --- | --- | --- | --- | --- |
| Douyin | ✅ | ✅ | ✅ | ✅ Product link | ✅ | ✅ |
| WeChat Channels | ✅ | - | ✅ | ✅ WeChat shop / showcase product | ✅ | ✅ |
| PDD / Duoduo Video | ✅ | - | ✅ | ✅ PDD product ID | ✅ | ✅ |
| Tmall / Taobao Guanghe | ✅ | - | ✅ | ✅ Taobao / Tmall product ID | ✅ | ✅ |
| JD Jingmai | ✅ | - | ✅ | ✅ JD product ID | ✅ | ✅ |
| Kuaishou | ✅ | ✅ | ✅ | - | ✅ | ✅ |
| Xiaohongshu | ✅ | ✅ | ✅ | - | ✅ | ✅ |
| Bilibili | ✅ | - | ✅ | - | ✅ | ✅ |
| Baijiahao | ✅ | - | ✅ | - | ✅ | ✅ |
| TikTok | ✅ | - | ✅ | - | ✅ | ✅ |

<p align="center">
  <b>Creators publish faster. Sellers distribute better. Agents stop guessing.</b>
</p>

A legacy XHS SDK uploader is also kept in the repository, but it is not part of the current main CLI workflow.

---

## Why this project?

Publishing content across platforms is repetitive, fragile and time-consuming:

- upload the same video to multiple platforms
- fill titles, descriptions and tags again and again
- attach product links or product IDs
- schedule posts for the right time
- manage multiple creator or shop accounts
- check whether login cookies are still valid
- monitor failures and retry manually

Browser agents are powerful, but publishing is not a task they should rediscover from screenshots every time.

`multi-platform-auto-upload` extracts those workflows into reusable uploaders, a unified CLI and ready-to-use Agent Skills.

---

## Highlights

- **One CLI, many platforms** — use `mpau` instead of maintaining scattered scripts.
- **Built for creators and sellers** — supports social media distribution and e-commerce product content.
- **Agent-ready by design** — includes packaged skills for OpenClaw, Hermes, Codex, Claude Code and other local agents.
- **Multi-account friendly** — each platform/account keeps its own local cookie file.
- **Product-link capable** — attach product links or product IDs for commerce workflows.
- **Scheduled publishing** — use one schedule format across supported platforms.
- **Optional video understanding** — keyframe extraction and speech-to-text for content-aware agent workflows.
- **Extensible uploader architecture** — platform logic lives under `uploader/`, making new integrations easier to add.

---

## Who is it for?

### Content creators

- distribute videos across multiple social platforms
- publish short videos and image/text notes
- prepare scheduled posts
- reduce repetitive backend operations

### E-commerce sellers and operators

- publish product videos
- attach product links or product IDs
- operate multiple stores and accounts
- automate merchant content workflows for platforms such as JD, PDD, Tmall/Taobao Guanghe and WeChat Channels

### AI agent builders

- give agents a deterministic publishing tool
- avoid asking agents to click through web pages from scratch
- plug platform-specific workflows into your own agent system
- combine content generation, video analysis and publishing into one pipeline

### Automation developers

- extend the existing uploader framework
- build internal publishing tools
- integrate publishing into a larger content operations system

---

## Quick start

### Requirements

- Python `>=3.10,<3.13`
- Google Chrome
- `uv` recommended
- `patchright` browser runtime
- `playwright` browser runtime for legacy Baijiahao / TikTok flows

### Install

```bash
git clone <your-repo-url> multi-platform-auto-upload
cd multi-platform-auto-upload

uv venv
source .venv/bin/activate
uv pip install -e .
```

Without `uv`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Install browser runtimes:

```bash
python -m patchright install chromium
python -m playwright install chromium
```

Optional runtime configuration can be provided through environment variables:

```bash
export MPAU_CHROME_PATH="/path/to/chrome"
export MPAU_HEADLESS="true"
export MPAU_DEBUG="true"
```

### Use the CLI

```bash
mpau --help
mpau douyin --help
mpau pdd --help
mpau jd --help
```

Login:

```bash
mpau douyin login --account shop1 --headed
```

Check login state:

```bash
mpau douyin check --account shop1
```

Upload a video:

```bash
mpau douyin upload-video \
  --account shop1 \
  --file ./videos/demo.mp4 \
  --title "Product review" \
  --desc "A short product review video" \
  --tags "review,shopping,life" \
  --headed
```

Schedule a post:

```bash
mpau tmall upload-video \
  --account shop1 \
  --file ./videos/demo.mp4 \
  --title "New product review" \
  --schedule "2026-06-05 20:00" \
  --headed
```

Attach a product ID:

```bash
mpau jd upload-video \
  --account shop1 \
  --file ./videos/demo.mp4 \
  --title "Real product review" \
  --goods-id "10204078771126" \
  --headed
```

---

## CLI design

All platforms share the same command structure:

```bash
mpau <platform> <action> [options]
```

Common platforms:

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

Common actions:

```text
login
check
upload-video
upload-note
verify
```

Examples:

```bash
mpau xiaohongshu upload-note --account creator --images 1.png 2.png --title "My note"
mpau bilibili upload-video --account creator --file demo.mp4 --title "My video" --desc "Intro" --tid 249
mpau tencent upload-video --account shop1 --file demo.mp4 --title "Product video" --goods-id "10000517325762"
```

---

## Account and cookie management

Accounts are managed by local account names. Cookie files are stored as:

```text
cookies/<platform>_<account>.json
```

For example:

```text
cookies/douyin_shop1.json
cookies/jd_shop1.json
cookies/xiaohongshu_creator.json
```

Cookie files are credentials. Do not commit them, print them or share them. They are ignored by `.gitignore` by default.

---

## Agent Skills

This repository includes ready-to-use skills under `skills/`:

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

These skills are not required to use the CLI, but they are one of the main advantages of this project.

They tell an agent:

- which CLI commands to run
- how to login and check cookies
- how to upload content
- how to monitor logs and failures
- when to ask the user for manual login or verification

### Integrate with your own agent

You can use this project with OpenClaw, Hermes, Codex, Claude Code, Claude Desktop or any local agent that can read files and execute commands.

#### Option 1: Let the agent use this repository directly

```bash
git clone <your-repo-url> multi-platform-auto-upload
cd multi-platform-auto-upload
uv venv
source .venv/bin/activate
uv pip install -e .
python -m patchright install chromium
python -m playwright install chromium
```

Then tell your agent:

```text
This is the multi-platform-auto-upload project.
Read the corresponding SKILL.md under skills/ before publishing.
Use the mpau CLI for platform publishing. Do not manually click through web pages unless the skill says so.
```

#### Option 2: Copy skills into your agent skill directory

```bash
cp -R skills/douyin-upload <YOUR_AGENT_SKILLS_DIR>/
cp -R skills/pdd-upload <YOUR_AGENT_SKILLS_DIR>/
cp -R skills/jd-upload <YOUR_AGENT_SKILLS_DIR>/
```

Make sure `mpau` is available in the environment:

```bash
mpau --help
```

#### Option 3: Use it as an internal publishing backend

Recommended flow for teams:

```text
1. Install this project on an operator machine or internal server.
2. Login to each platform account once and generate local cookies.
3. Let your agent choose the right skill for the task.
4. The agent calls mpau check / upload.
5. The agent reads logs and reports success, failure or required manual action.
```

In this model, the agent handles planning and orchestration; the uploaders handle platform-specific publishing details.

---

## Add-on: video analysis

Video analysis is an optional add-on. It is not required for the main publishing workflow.

`skills/video-analyze` can turn a video into structured material for agents:

- extract keyframes with `ffmpeg/ffprobe`
- transcribe speech with Aliyun Bailian `paraformer-v2`
- output JSON for downstream reasoning

Initialize:

```bash
cd skills/video-analyze/scripts/video-analyzer
uv sync
```

Install ffmpeg:

```bash
brew install ffmpeg
```

Set ASR key:

```bash
export ALIYUN_API_KEY="sk-xxx"
```

Run:

```bash
uv run va extract --file /path/to/video.mp4
```

Example output:

```json
{
  "frames": ["/tmp/va_frames_xxx/frame_01_10pct.jpg"],
  "transcript": "transcribed speech...",
  "duration": 45.2,
  "audio_empty": false
}
```

If no ASR key is configured, keyframe extraction still works and the transcript will be empty.

Use this when you want an agent to understand the video before choosing titles, tags, product links or target platforms.

---

## Project structure

```text
multi-platform-auto-upload/
├── mpau_cli.py              # CLI entry
├── pyproject.toml           # Python package config
├── uploader/                # Platform uploaders
├── utils/                   # Shared utilities
├── skills/                  # Agent Skills
└── tests/                   # Lightweight tests
```

---

## Development

Run tests:

```bash
python3 -m unittest -v tests.test_mpau_cli
```

Verify CLI help:

```bash
python3 mpau_cli.py --help
python3 mpau_cli.py douyin --help
python3 mpau_cli.py pdd --help
python3 mpau_cli.py tiktok --help
```

---

## Before publishing your fork

Make sure you do not publish local runtime data:

- no `cookies/`
- no `logs/`
- no real video files
- no `.venv/`
- no `__pycache__/`
- no QR code images
- no personal account or shop credentials

---

## License

MIT License. See [LICENSE](LICENSE).

---

## Disclaimer

This project is intended for content creation, self-owned account operation and legitimate automation workflows. Please follow the rules of each platform and do not use automation to publish illegal, harmful or abusive content.
