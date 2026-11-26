"""
Kalıcı Ayarlar Servisi (settings.json).
Tüm kısayolları, özellik anahtarlarını, güncelleme ve genel tercihleri tek bir
settings.json dosyasında saklar ve yönetir.
"""

import copy
import json
import os
import sys
from typing import Any, Dict, Optional

from utils.paths import BASE_DIR as _BASE_DIR_PATH, SETTINGS_PATH as _SETTINGS_PATH

BASE_DIR = str(_BASE_DIR_PATH)
SETTINGS_PATH = str(_SETTINGS_PATH)

SHORTCUT_META = {
    "capture_screen": {
        "title": "Ekran bölgesini yakala ve oku",
        "desc": "Alanı seç, metin okunup seslendirilir.",
    },
    "play_pause": {
        "title": "Duraklat / devam et",
        "desc": "Sesli okuma sırasında.",
    },
    "prev_next_paragraph": {
        "title": "Önceki / sonraki paragraf",
        "desc": "Okuma sırasında paragraflar arasında atla.",
    },
    "read_aloud": {
        "title": "Sesli oku",
        "desc": "Aktif sekmedeki metni seslendirmeyi başlatır.",
    },
    "toggle_window": {
        "title": "Uygulamayı göster / gizle",
        "desc": "Sistem tepsisindeki uygulamayı çağırır.",
    },
}

DEFAULT_SETTINGS: Dict[str, Any] = {
    "shortcuts_enabled": True,
    "shortcuts": {
        "capture_screen": {"keys": "Ctrl+Shift+O", "enabled": True},
        "play_pause": {"keys": "Space", "enabled": True},
        "prev_next_paragraph": {"keys": "Left/Right", "enabled": True},
        "read_aloud": {"keys": "Ctrl+Enter", "enabled": True},
        "toggle_window": {"keys": "", "enabled": False},
    },
    "features": {
        "highlight_sentence": True,
        "resume_last_position": True,
        "clipboard_monitor": False,
        "minimize_to_tray": False,
        "start_with_windows": False,
        "reduced_motion": False,
    },
    "updates": {
        "github_repo": "mert2091/Sono",
        "auto_check": True,
    },
    "general": {
        "theme": "dark",
        "export_dir": "",
    },
    "audio": {
        "voice": "tr-TR-EmelNeural",
        "speed": 1.0,
        "volume": 100,
    },
    "studio": {
        "target_lang": "Türkçe",
        "side_by_side": False,
        "font_size": 14,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class SettingsService:
    """settings.json dosyasını okuyan, güncelleyen ve kaydeden servis."""

    def __init__(self, path: str = SETTINGS_PATH):
        self.path = path
        self.data: Dict[str, Any] = copy.deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self.data = _deep_merge(DEFAULT_SETTINGS, loaded)
                    return self.data
            except Exception:
                pass
        self.data = copy.deepcopy(DEFAULT_SETTINGS)
        self.save()
        return self.data

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ayarlar kaydedilemedi: {e}")

    # ── Kısayol Yardımcıları ──────────────────────────────────────

    def is_shortcuts_enabled(self) -> bool:
        return bool(self.data.get("shortcuts_enabled", True))

    def set_shortcuts_enabled(self, enabled: bool) -> None:
        self.data["shortcuts_enabled"] = bool(enabled)
        self.save()

    def get_shortcut(self, action_id: str) -> Dict[str, Any]:
        return self.data["shortcuts"].get(action_id, {"keys": "", "enabled": False})

    def find_shortcut_conflict(self, action_id: str, new_keys: str) -> Optional[str]:
        """Aynı tuş kombinasyonu başka bir kısayolda kullanılıyorsa adını döndür."""
        norm = normalize_shortcut_keys(new_keys).lower()
        if not norm:
            return None
        for other_id, cfg in self.data["shortcuts"].items():
            if other_id == action_id:
                continue
            existing = normalize_shortcut_keys(cfg.get("keys") or "").lower()
            if existing and existing == norm:
                return SHORTCUT_META.get(other_id, {}).get("title", other_id)
        return None

    def set_shortcut_keys(self, action_id: str, new_keys: str) -> None:
        if action_id in self.data["shortcuts"]:
            cleaned = normalize_shortcut_keys(new_keys)
            self.data["shortcuts"][action_id]["keys"] = cleaned
            if cleaned:
                self.data["shortcuts"][action_id]["enabled"] = True
            self.save()

    def set_shortcut_enabled(self, action_id: str, enabled: bool) -> None:
        if action_id in self.data["shortcuts"]:
            self.data["shortcuts"][action_id]["enabled"] = bool(enabled)
            self.save()

    def reset_shortcuts(self) -> None:
        self.data["shortcuts_enabled"] = True
        self.data["shortcuts"] = copy.deepcopy(DEFAULT_SETTINGS["shortcuts"])
        self.save()

    # ── Özellik Anahtarları ───────────────────────────────────────

    def get_feature(self, key: str) -> bool:
        return bool(self.data["features"].get(key, False))

    def set_feature(self, key: str, value: bool) -> None:
        self.data["features"][key] = bool(value)
        if key == "start_with_windows":
            set_windows_startup(bool(value))
        self.save()

    # ── Güncellemeler & Genel ─────────────────────────────────────

    def get_update_setting(self, key: str, default: Any = "") -> Any:
        return self.data["updates"].get(key, default)

    def set_update_setting(self, key: str, value: Any) -> None:
        self.data["updates"][key] = value
        self.save()

    def get_general(self, key: str, default: Any = "") -> Any:
        return self.data["general"].get(key, default)

    def set_general(self, key: str, value: Any) -> None:
        self.data["general"][key] = value
        self.save()

    def get_audio(self, key: str, default: Any = None) -> Any:
        return self.data.setdefault("audio", {}).get(key, default)

    def set_audio(self, key: str, value: Any) -> None:
        self.data.setdefault("audio", {})[key] = value
        self.save()

    def get_studio(self, key: str, default: Any = None) -> Any:
        return self.data.setdefault("studio", {}).get(key, default)

    def set_studio(self, key: str, value: Any) -> None:
        self.data.setdefault("studio", {})[key] = value
        self.save()


_MOD_ORDER = ("Ctrl", "Shift", "Alt")
_CANONICAL_MOD_MAP = {
    "ctrl": "Ctrl",
    "control": "Ctrl",
    "shift": "Shift",
    "alt": "Alt",
}
_CANONICAL_KEY_MAP = {
    "space": "Space",
    "enter": "Enter",
    "return": "Enter",
    "left": "Left",
    "right": "Right",
    "up": "Up",
    "down": "Down",
    "tab": "Tab",
    "backspace": "BackSpace",
    "delete": "Delete",
    "insert": "Insert",
    "home": "Home",
    "end": "End",
    "pageup": "PageUp",
    "prior": "PageUp",
    "pagedown": "PageDown",
    "next": "PageDown",
    "esc": "Escape",
    "escape": "Escape",
}
for _fn in range(1, 13):
    _CANONICAL_KEY_MAP[f"f{_fn}"] = f"F{_fn}"


def normalize_shortcut_keys(keys: str) -> str:
    """
    Kısayol tuş dizesini kanonik biçime getirir:
    - Modifier sırası her zaman Ctrl -> Shift -> Alt olarak sabitlenir ve tekrarlar silinir.
    - Return -> Enter, Prior -> PageUp, Next -> PageDown, tek ASCII harf -> büyük harf yapılır.
    """
    raw = (keys or "").strip()
    if not raw:
        return ""
    if raw == "Left/Right":
        return "Left/Right"

    parts = [p.strip() for p in raw.split("+") if p.strip()]
    mods_found: set[str] = set()
    main_key: Optional[str] = None

    for p in parts:
        pl = p.lower()
        if pl in _CANONICAL_MOD_MAP:
            mods_found.add(_CANONICAL_MOD_MAP[pl])
        elif pl in _CANONICAL_KEY_MAP:
            main_key = _CANONICAL_KEY_MAP[pl]
        elif len(p) == 1 and p.isascii() and p.isalnum():
            main_key = p.upper()
        else:
            main_key = p

    if not main_key:
        return ""

    ordered_mods = [m for m in _MOD_ORDER if m in mods_found]
    return "+".join(ordered_mods + [main_key]) if ordered_mods else main_key


def format_keys_for_display(keys: str) -> list[str]:
    """Kayıtlı tuş dizesini görsel keycap parçalarına ayırır."""
    if not keys:
        return []
    if keys == "Left/Right":
        return ["←", "→"]
    display_map = {
        "Space": "Boşluk",
        "Return": "Enter",
        "Enter": "Enter",
        "Left": "←",
        "Right": "→",
        "Up": "↑",
        "Down": "↓",
        "Escape": "Esc",
        "Esc": "Esc",
        "BackSpace": "Geri Sil",
        "Delete": "Sil",
        "Insert": "Ins",
        "Home": "Home",
        "End": "End",
        "PageUp": "PgUp",
        "Prior": "PgUp",
        "PageDown": "PgDn",
        "Next": "PgDn",
        "Tab": "Tab",
    }
    parts = [p.strip() for p in keys.split("+") if p.strip()]
    return [display_map.get(p, p) for p in parts]


def shortcut_to_tk_sequences(keys: str) -> list[str]:
    """
    'Ctrl+Shift+O', '1', 'Space' gibi dizeleri güvenli Tkinter KeyPress bind dizilerine çevirir.
    - Rakamlar için <1> (sol fare tıkı) yerine her zaman <KeyPress-1> kullanır.
    - Harf kısayollarında Shift ve CapsLock uyumu için hem birincil hem ikincil harf durumunu döndürür.
    """
    if not keys or keys == "Left/Right":
        return []
    parts = [p.strip() for p in keys.split("+") if p.strip()]
    if not parts:
        return []

    mod_map = {
        "ctrl": "Control",
        "control": "Control",
        "shift": "Shift",
        "alt": "Alt",
    }
    key_map = {
        "space": "space",
        "enter": "Return",
        "return": "Return",
        "left": "Left",
        "right": "Right",
        "up": "Up",
        "down": "Down",
        "tab": "Tab",
        "backspace": "BackSpace",
        "delete": "Delete",
        "insert": "Insert",
        "home": "Home",
        "end": "End",
        "pageup": "Prior",
        "prior": "Prior",
        "pagedown": "Next",
        "next": "Next",
        "escape": "Escape",
        "esc": "Escape",
    }
    for i in range(1, 13):
        key_map[f"f{i}"] = f"F{i}"

    mods_found: set[str] = set()
    raw_main: Optional[str] = None
    for p in parts:
        pl = p.lower()
        if pl in mod_map:
            mods_found.add(mod_map[pl])
        else:
            raw_main = p

    if not raw_main:
        return []

    ordered_mods = [m for m in ("Control", "Shift", "Alt") if m in mods_found]
    prefix = ("-".join(ordered_mods) + "-") if ordered_mods else ""

    pl = raw_main.lower()
    if pl in key_map:
        return [f"<{prefix}KeyPress-{key_map[pl]}>"]

    if len(raw_main) == 1 and raw_main.isascii():
        if raw_main.isalpha():
            upper_c = raw_main.upper()
            lower_c = raw_main.lower()
            if "Shift" in mods_found:
                return [f"<{prefix}KeyPress-{upper_c}>", f"<{prefix}KeyPress-{lower_c}>"]
            return [f"<{prefix}KeyPress-{lower_c}>", f"<{prefix}KeyPress-{upper_c}>"]
        if raw_main.isdigit():
            return [f"<{prefix}KeyPress-{raw_main}>"]

    return []


def shortcut_to_tk_sequence(keys: str) -> Optional[str]:
    """Geriye dönük uyumluluk: birincil Tkinter bind dizisini döndürür."""
    seqs = shortcut_to_tk_sequences(keys)
    return seqs[0] if seqs else None


def set_windows_startup(enabled: bool) -> bool:
    """Windows başlangıcına Sono'yu ekler veya kaldırır."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    main_py = os.path.join(BASE_DIR, "main.py")
                    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
                    exe = pythonw if os.path.exists(pythonw) else sys.executable
                    cmd = f'"{exe}" "{main_py}"'
                winreg.SetValueEx(key, "Sono", 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, "Sono")
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print(f"Windows başlangıç kaydı güncellenemedi: {e}")
        return False
