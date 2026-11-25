"""
Merkezi Dosya Yolu Çözümleyici (Sono).
Normal çalışma ve PyInstaller (--onefile / --onedir) derlemelerinde
.env, history.db, settings.json ve logs/ yollarını tek bir BASE_DIR üzerinden çözer.
"""

from pathlib import Path
import sys


def get_base_dir() -> Path:
    """Frozen (.exe) ortamda exe klasörünü, geliştirme ortamında proje kökünü döndürür."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR: Path = get_base_dir()
ENV_PATH: Path = BASE_DIR / ".env"
HISTORY_DB_PATH: Path = BASE_DIR / "history.db"
SETTINGS_PATH: Path = BASE_DIR / "settings.json"
LOG_DIR: Path = BASE_DIR / "logs"
LOG_FILE: Path = LOG_DIR / "sono.log"
