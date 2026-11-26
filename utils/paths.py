"""

Merkezi Dosya Yolu Çözümleyici (Sono).

Frozen (.exe) ortamda kullanıcı verilerini (.env, history.db, settings.json, logs/)

%APPDATA%/Sono altında tutar; böylece Masaüstü veya .exe klasörü kirlenmez.

Geliştirme ortamında proje kökünü (BASE_DIR) kullanır.

"""



import os

from pathlib import Path

import sys





def get_base_dir() -> Path:

    """Frozen (.exe) ortamda exe klasörünü, geliştirme ortamında proje kökünü döndürür."""

    if getattr(sys, "frozen", False):

        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent





def get_data_dir() -> Path:

    """

    Kullanıcı veri dizinini döndürür:

    - Frozen (.exe): %APPDATA%/Sono (Windows) veya ~/.sono

    - Geliştirme (python main.py): Proje kökü (BASE_DIR)

    """

    if getattr(sys, "frozen", False):

        if sys.platform == "win32":

            appdata = os.environ.get("APPDATA")

            base = Path(appdata) if appdata else (Path.home() / "AppData" / "Roaming")

            data_dir = base / "Sono"

        else:

            data_dir = Path.home() / ".sono"

        data_dir.mkdir(parents=True, exist_ok=True)

        return data_dir

    return get_base_dir()





BASE_DIR: Path = get_base_dir()

DATA_DIR: Path = get_data_dir()

ENV_PATH: Path = DATA_DIR / ".env"

HISTORY_DB_PATH: Path = DATA_DIR / "history.db"

SETTINGS_PATH: Path = DATA_DIR / "settings.json"

LOG_DIR: Path = DATA_DIR / "logs"

LOG_FILE: Path = LOG_DIR / "sono.log"

