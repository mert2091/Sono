"""
Tam Ekran Bölgesi Yakalama Penceresi (Sono).
Çift tema uyumlu: raw tk.Canvas öğeleri için `resolve_color()` kullanır.
"""

from __future__ import annotations

import time
import tkinter as tk
from typing import Callable, Optional
from PIL import Image, ImageEnhance, ImageGrab, ImageTk

from ui.theme import ACCENT_COLOR, CARD_BG, CARD_BORDER, FONT_MONO, TEXT_MAIN, resolve_color


class ScreenCaptureWindow(tk.Toplevel):
    """Ekranı karartıp fareyle dikdörtgen alan seçtiren tam ekran katman."""

    def __init__(
        self,
        parent,
        on_captured: Callable[[Image.Image], None],
        on_cancel: Optional[Callable[[], None]] = None,
        screenshot: Optional[Image.Image] = None,
    ):
        super().__init__(parent)
        self._on_captured = on_captured
        self._on_cancel = on_cancel

        self._accent_hex = resolve_color(ACCENT_COLOR)
        self._card_bg_hex = resolve_color(CARD_BG)
        self._card_border_hex = resolve_color(CARD_BORDER)
        self._text_main_hex = resolve_color(TEXT_MAIN)

        if screenshot is not None:
            self._full_image = screenshot.convert("RGB")
        else:
            try:
                self._full_image = ImageGrab.grab(all_screens=False).convert("RGB")
            except Exception:
                self._full_image = ImageGrab.grab().convert("RGB")

        self._screen_w = self.winfo_screenwidth()
        self._screen_h = self.winfo_screenheight()
        self._scale_x = self._full_image.width / max(self._screen_w, 1)
        self._scale_y = self._full_image.height / max(self._screen_h, 1)

        self._disp_bright = self._full_image.resize(
            (self._screen_w, self._screen_h), Image.Resampling.LANCZOS
        )
        self._disp_dim = ImageEnhance.Brightness(self._disp_bright).enhance(0.42)

        self._tk_dim = ImageTk.PhotoImage(self._disp_dim)
        self._tk_crop_preview: Optional[ImageTk.PhotoImage] = None

        self._start_x = 0
        self._start_y = 0
        self._rect_id = None
        self._preview_id = None
        self._size_bg_id = None
        self._size_txt_id = None
        self._dragging = False
        self._last_preview_ts: float = 0.0
        self._preview_interval_sec: float = 0.024

        self.overrideredirect(True)
        self.geometry(f"{self._screen_w}x{self._screen_h}+0+0")
        self.attributes("-topmost", True)
        self.configure(cursor="crosshair")

        self.canvas = tk.Canvas(
            self,
            width=self._screen_w,
            height=self._screen_h,
            highlightthickness=0,
            bd=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_dim)

        banner_w, banner_h = 390, 38
        bx1 = (self._screen_w - banner_w) // 2
        by1 = 24
        self.canvas.create_rectangle(
            bx1,
            by1,
            bx1 + banner_w,
            by1 + banner_h,
            fill=self._card_bg_hex,
            outline=self._card_border_hex,
            width=1,
        )
        self.canvas.create_text(
            self._screen_w // 2,
            by1 + banner_h // 2,
            text="Okumak istediğin alanı fareyle seç  ·  İptal: Esc",
            fill=self._text_main_hex,
            font=("Segoe UI", 10, "bold"),
        )

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._cancel)
        self.bind("<Escape>", self._cancel)

        self.focus_force()
        self.grab_set()

    def _on_press(self, event) -> None:
        self._start_x = event.x
        self._start_y = event.y
        self._dragging = True
        self._last_preview_ts = 0.0
        self._clear_selection_items()

    def _on_drag(self, event) -> None:
        if not self._dragging:
            return
        x1 = max(0, min(self._start_x, event.x))
        y1 = max(0, min(self._start_y, event.y))
        x2 = min(self._screen_w, max(self._start_x, event.x))
        y2 = min(self._screen_h, max(self._start_y, event.y))
        w = x2 - x1
        h = y2 - y1

        now = time.monotonic()
        if w >= 4 and h >= 4 and (
            self._preview_id is None or (now - self._last_preview_ts) >= self._preview_interval_sec
        ):
            self._last_preview_ts = now
            bright_crop = self._disp_bright.crop((x1, y1, x2, y2))
            self._tk_crop_preview = ImageTk.PhotoImage(bright_crop)
            if self._preview_id is None:
                self._preview_id = self.canvas.create_image(
                    x1, y1, anchor="nw", image=self._tk_crop_preview
                )
            else:
                self.canvas.coords(self._preview_id, x1, y1)
                self.canvas.itemconfigure(self._preview_id, image=self._tk_crop_preview)

        if self._rect_id is None:
            self._rect_id = self.canvas.create_rectangle(
                x1, y1, x2, y2, outline=self._accent_hex, width=2
            )
        else:
            self.canvas.coords(self._rect_id, x1, y1, x2, y2)

        label_y = y1 - 24 if y1 > 32 else y2 + 6
        if self._size_bg_id is None:
            self._size_bg_id = self.canvas.create_rectangle(
                x1,
                label_y,
                x1 + 92,
                label_y + 20,
                fill=self._card_bg_hex,
                outline=self._accent_hex,
                width=1,
            )
        else:
            self.canvas.coords(self._size_bg_id, x1, label_y, x1 + 92, label_y + 20)

        if self._size_txt_id is None:
            self._size_txt_id = self.canvas.create_text(
                x1 + 46,
                label_y + 10,
                text=f"{w} × {h}",
                fill=self._text_main_hex,
                font=(FONT_MONO, 8, "bold"),
            )
        else:
            self.canvas.coords(self._size_txt_id, x1 + 46, label_y + 10)
            self.canvas.itemconfigure(self._size_txt_id, text=f"{w} × {h}")

        if self._preview_id is not None:
            self.canvas.tag_raise(self._rect_id, self._preview_id)
            self.canvas.tag_raise(self._size_bg_id, self._rect_id)
            self.canvas.tag_raise(self._size_txt_id, self._size_bg_id)

    def _on_release(self, event) -> None:
        if not self._dragging:
            return
        self._dragging = False
        x1 = max(0, min(self._start_x, event.x))
        y1 = max(0, min(self._start_y, event.y))
        x2 = min(self._screen_w, max(self._start_x, event.x))
        y2 = min(self._screen_h, max(self._start_y, event.y))

        if (x2 - x1) < 12 or (y2 - y1) < 12:
            self._cancel()
            return

        rx1 = max(0, int(round(x1 * self._scale_x)))
        ry1 = max(0, int(round(y1 * self._scale_y)))
        rx2 = min(self._full_image.width, int(round(x2 * self._scale_x)))
        ry2 = min(self._full_image.height, int(round(y2 * self._scale_y)))

        cropped = self._full_image.crop((rx1, ry1, rx2, ry2))
        self.destroy()
        self._on_captured(cropped)

    def _clear_selection_items(self) -> None:
        for item_id in (self._preview_id, self._rect_id, self._size_bg_id, self._size_txt_id):
            if item_id is not None:
                self.canvas.delete(item_id)
        self._preview_id = None
        self._rect_id = None
        self._size_bg_id = None
        self._size_txt_id = None

    def _cancel(self, _event=None) -> None:
        self.destroy()
        if self._on_cancel:
            self._on_cancel()
