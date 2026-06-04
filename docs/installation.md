# Installation

## Requirements

- Python `>=3.10,<3.13`
- Google Chrome
- `uv` is recommended
- `patchright` browser runtime
- `playwright` browser runtime for Baijiahao / TikTok legacy flows

## Install with uv

```bash
git clone https://github.com/cjccd/multi-platform-auto-upload.git
cd multi-platform-auto-upload

uv venv
source .venv/bin/activate
uv pip install -e .
```

Windows PowerShell:

```powershell
uv venv
.venv\Scripts\activate
uv pip install -e .
```

## Install without uv

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Browser runtimes

```bash
python -m patchright install chromium
python -m playwright install chromium
```

For slower networks:

```bash
PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright" python -m patchright install chromium
PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright" python -m playwright install chromium
```

## Optional runtime configuration

No config file is required by default. Use environment variables when you need to override runtime behavior:

```bash
export MPAU_CHROME_PATH="/path/to/chrome"
export MPAU_HEADLESS="true"
export MPAU_DEBUG="true"
```
