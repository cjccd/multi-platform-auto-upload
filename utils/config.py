from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
LOCAL_CHROME_PATH = os.getenv("MPAU_CHROME_PATH", "")
LOCAL_CHROME_HEADLESS = os.getenv("MPAU_HEADLESS", "true").strip().lower() not in {"0", "false", "no", "off"}
DEBUG_MODE = os.getenv("MPAU_DEBUG", "true").strip().lower() not in {"0", "false", "no", "off"}
