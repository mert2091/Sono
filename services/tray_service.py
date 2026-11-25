"""
Sistem Tepsisi (System Tray) Servisi (Sono).
pystray kullanarak Windows bildirim alanında Sono simgesini ve sağ tık menüsünü yönetir.
"""

import os
import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw

try:
    import pystray
    _PYSTRAY_AVAILABLE = True
except Exception:
    pystray = None
    _PYSTRAY_AVAILABLE = False


class TrayService:
    """Windows sistem tepsisi simgesi yöneticisi."""

    def __init__(
        self,
        icon_path: str,
        on_show: Callable[[], None],
        on_capture: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._icon_path = icon_path
        self._on_show = on_show
        self._on_capture = on_capture
        self._on_quit = on_quit
        self._icon = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def is_available(self) -> bool:
        return _PYSTRAY_AVAILABLE

    @property
    def is_running(self) -> bool:
        return self._running

    def _load_icon_image(self) -> Image.Image:
        if self._icon_path and os.path.exists(self._icon_path):
            try:
                return Image.open(self._icon_path).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
            except Exception:
                pass
        # Yedek basit Sono ikonu
        img = Image.new("RGBA", (64, 64), (15, 17, 21, 255))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((2, 2, 61, 61), radius=14, fill=(23, 26, 33, 255), outline=(127, 155, 255, 255), width=3)
        return img

    def start(self) -> bool:
        if not _PYSTRAY_AVAILABLE or self._running:
            return self._running

        menu = pystray.Menu(
            pystray.MenuItem("Sono'yu Göster", lambda icon, item: self._on_show(), default=True),
            pystray.MenuItem("Ekran Bölgesi Yakala", lambda icon, item: self._on_capture()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Çıkış", lambda icon, item: self._on_quit()),
        )

        self._icon = pystray.Icon(
            "Sono",
            self._load_icon_image(),
            "Sono — Belge ve Ses Stüdyosu",
            menu,
        )
        self._running = True

        def _run():
            try:
                self._icon.run()
            except Exception:
                pass
            finally:
                self._running = False

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
