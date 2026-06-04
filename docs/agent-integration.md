# Agent Integration

Multi Platform Auto Upload is designed to be used by both humans and AI agents.

Agents should call `mpau` instead of manually clicking through publishing pages.

## Built-in skills

This repository includes platform-specific skills:

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

## Option 1: Let the agent use this repository directly

```bash
git clone https://github.com/cjccd/multi-platform-auto-upload.git
cd multi-platform-auto-upload
uv venv
source .venv/bin/activate
uv pip install -e .
python -m patchright install chromium
python -m playwright install chromium
```

Tell your agent:

```text
This is the multi-platform-auto-upload project.
Read the corresponding SKILL.md under skills/ before publishing.
Use the mpau CLI for platform publishing. Do not manually click through web pages unless the skill says so.
```

## Option 2: Copy skills into your agent skill directory

```bash
cp -R skills/douyin-upload <YOUR_AGENT_SKILLS_DIR>/
cp -R skills/pdd-upload <YOUR_AGENT_SKILLS_DIR>/
cp -R skills/jd-upload <YOUR_AGENT_SKILLS_DIR>/
```

Make sure `mpau` is available:

```bash
mpau --help
```

## Recommended workflow

```text
1. Install this project on an operator machine or internal server.
2. Login to each platform account once and generate local cookies.
3. Let your agent choose the right skill for the task.
4. The agent calls mpau check / upload.
5. The agent reads logs and reports success, failure or required manual action.
```
