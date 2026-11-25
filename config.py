"""
Konfigürasyon modülü.
.env dosyasından (utils.paths.ENV_PATH) API anahtarını yükler ve güvenli biçimde kaydeder.
"""

import os
from dotenv import load_dotenv

from utils.paths import ENV_PATH

_PLACEHOLDER_KEYS = {
    "",
    "your_gemini_api_key_here",
    "your_api_key_here",
    "buraya_kendi_api_anahtarinizi_yazin",
    "buraya_api_anahtarinizi_yazin",
}

# Uygulama kök dizinindeki .env dosyasını yükle
load_dotenv(ENV_PATH)


def _clean_key(raw: str) -> str:
    val = (raw or "").strip().strip('"').strip("'")
    if any(ch in val for ch in ("\r", "\n")) or any(ch.isspace() for ch in val):
        return ""
    return "" if val in _PLACEHOLDER_KEYS else val


def get_api_key() -> str:
    """Aktif Gemini API anahtarını döndürür (yoksa boş dize)."""
    return _clean_key(os.getenv("GEMINI_API_KEY", ""))


def has_api_key() -> bool:
    """Geçerli formatta kayıtlı bir API anahtarı olup olmadığını döndürür."""
    return bool(get_api_key())


def save_api_key(new_key: str) -> None:
    """
    API anahtarını uygulama kökündeki .env dosyasına (ENV_PATH) kaydeder
    ve yeniden başlatma gerekmeden aktif süreçte günceller.
    """
    global GEMINI_API_KEY
    raw = (new_key or "").strip().strip('"').strip("'")
    if any(ch in raw for ch in ("\r", "\n")) or any(ch.isspace() for ch in raw):
        raise ValueError("API anahtarı satır sonu veya boşluk içeremez.")
    cleaned = _clean_key(raw)

    lines: list[str] = []
    if ENV_PATH.exists():
        try:
            lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
        except Exception:
            lines = []

    updated = False
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("GEMINI_API_KEY="):
            new_lines.append(f"GEMINI_API_KEY={cleaned}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        if not new_lines:
            new_lines.append("# Google Gemini API Anahtarı (https://aistudio.google.com/app/apikey)")
        new_lines.append(f"GEMINI_API_KEY={cleaned}")

    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    os.environ["GEMINI_API_KEY"] = cleaned
    GEMINI_API_KEY = cleaned


# Geriye dönük uyumluluk için modül düzeyi değişken (yoksa boş dize, açılışta çökmez)
GEMINI_API_KEY: str = get_api_key()
