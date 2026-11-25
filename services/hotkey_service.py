"""
Windows Global Kısayol Servisi (ctypes RegisterHotKey).
Ekstra kütüphane veya yönetici izni gerektirmeden uygulama arka plandayken bile
global kısayolları (ör. Ctrl+Shift+O) yakalar.
"""

import ctypes
import ctypes.wintypes as wintypes
import sys
import threading
from typing import Callable, Dict, Optional, Tuple

from services.logger_service import get_logger

logger = get_logger("hotkey")

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

_SPECIAL_VK = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "backspace": 0x08,
    "delete": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "prior": 0x21,
    "pagedown": 0x22,
    "next": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
}
for _i in range(1, 13):
    _SPECIAL_VK[f"f{_i}"] = 0x6F + _i


def parse_hotkey_win32(keys: str) -> Optional[Tuple[int, int]]:
    """'Ctrl+Shift+O' gibi dizeyi Win32 (modifiers, vk_code) çiftine çevirir."""
    if not keys or keys == "Left/Right":
        return None
    parts = [p.strip() for p in keys.split("+") if p.strip()]
    if not parts:
        return None

    mods = 0
    vk = None
    for p in parts:
        pl = p.lower()
        if pl in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif pl == "shift":
            mods |= MOD_SHIFT
        elif pl == "alt":
            mods |= MOD_ALT
        elif pl in ("win", "super", "meta"):
            mods |= MOD_WIN
        elif pl in _SPECIAL_VK:
            vk = _SPECIAL_VK[pl]
        elif len(p) == 1 and p.isascii() and p.isalnum():
            vk = ord(p.upper())

    if vk is None:
        return None
    return (mods | MOD_NOREPEAT, vk)


class GlobalHotkeyManager:
    """Arka plan Win32 mesaj döngüsüyle global kısayolları yönetir."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._bindings: Dict[int, Tuple[int, int, Callable[[], None]]] = {}
        self._next_id = 100
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()

    def set_hotkeys(self, items: list[Tuple[str, Callable[[], None]]]) -> None:
        """
        Mevcut tüm global kısayolları temizleyip yenilerini kaydeder.
        items: [(keys_str, callback), ...]
        """
        self.stop()
        if sys.platform != "win32":
            return

        parsed_list = []
        for keys_str, cb in items:
            parsed = parse_hotkey_win32(keys_str)
            if parsed:
                parsed_list.append((parsed[0], parsed[1], cb))

        if not parsed_list:
            return

        self._stop_event.clear()
        self._ready_event.clear()
        self._bindings = {}
        for mods, vk, cb in parsed_list:
            self._next_id += 1
            self._bindings[self._next_id] = (mods, vk, cb)

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        msg = wintypes.MSG()
        registered_ids = []
        try:
            self._thread_id = kernel32.GetCurrentThreadId()
            # Win32 mesaj kuyruğunu PostThreadMessageW gelmeden önce oluştur
            user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

            for hk_id, (mods, vk, _) in list(self._bindings.items()):
                try:
                    if user32.RegisterHotKey(None, hk_id, mods, vk):
                        registered_ids.append(hk_id)
                    else:
                        err_code = kernel32.GetLastError()
                        logger.warning(
                            "Global kısayol kaydedilemedi (id=%s, mods=0x%X, vk=0x%X, winerr=%s).",
                            hk_id,
                            mods,
                            vk,
                            err_code,
                        )
                except Exception as e:
                    logger.warning("RegisterHotKey hatası (id=%s): %s", hk_id, e)
        finally:
            self._ready_event.set()

        try:
            while not self._stop_event.is_set():
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:
                    break
                if msg.message == WM_HOTKEY:
                    hk_id = msg.wParam
                    entry = self._bindings.get(hk_id)
                    if entry:
                        _, _, cb = entry
                        try:
                            cb()
                        except Exception:
                            pass
        finally:
            for hk_id in registered_ids:
                try:
                    user32.UnregisterHotKey(None, hk_id)
                except Exception:
                    pass
            self._thread_id = None

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._ready_event.wait(timeout=0.5)
            tid = self._thread_id
            if sys.platform == "win32" and tid:
                try:
                    ctypes.windll.user32.PostThreadMessageW(tid, WM_QUIT, 0, 0)
                except Exception:
                    pass
            self._thread.join(timeout=0.8)
        self._thread = None
        self._thread_id = None
        self._bindings.clear()
