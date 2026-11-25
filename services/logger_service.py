"""
Merkezi Hata ve Olay Kayıt Servisi (Sono).
Tüm önemli olayları ve hataları dönen (rotating) logs/sono.log dosyasına kaydeder.
"""

import logging
from logging.handlers import RotatingFileHandler
import os

from utils.paths import (
    BASE_DIR as _BASE_DIR_PATH,
    LOG_DIR as _LOG_DIR_PATH,
    LOG_FILE as _LOG_FILE_PATH,
)

BASE_DIR = str(_BASE_DIR_PATH)
LOG_DIR = str(_LOG_DIR_PATH)
LOG_FILE = str(_LOG_FILE_PATH)

_INITIALIZED = False


def get_log_file_path() -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    return LOG_FILE


def setup_logging() -> logging.Logger:
    global _INITIALIZED
    os.makedirs(LOG_DIR, exist_ok=True)
    root_logger = logging.getLogger("sono")
    if not _INITIALIZED:
        root_logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        root_logger.addHandler(handler)
        _INITIALIZED = True
    return root_logger


def get_logger(name: str = "sono") -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"sono.{name}" if not name.startswith("sono") else name)
