from pathlib import Path

from utils.config import BASE_DIR

Path(BASE_DIR / "cookies").mkdir(exist_ok=True)