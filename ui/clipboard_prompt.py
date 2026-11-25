"""
Pano İzleme "Okuyayım mı?" Bildirim Penceresi (Sono).
Sağ alt köşede yumuşak kayma animasyonu (animate_window_slide_in), çift tema
desteği ve alt kenarda otomatik kapanma geri sayım çizgisiyle açılır.
"""

from __future__ import annotations

import time
import tkinter as tk
from typing import Callable, Optional
import customtkinter as ctk

from ui.animations import animate_window_slide_in
from ui.icons import get_icon
from ui.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    ACCENT_SOFT_TEXT,
    ACCENT_TEXT,
    CARD_BG,
    CARD_BORDER,
    SECONDARY_BTN,
    SECONDARY_BTN_BORDER,
    SECONDARY_BTN_HOVER,
    TEXT_MAIN,
    TEXT_MUTED,
    is_reduced_motion,
    resolve_color,
    ui_font,
)


class ClipboardPromptWindow(ctk.CTkToplevel):
    """Sağ alt köşede kayarak açılan 'Okuyayım mı?' toast bildirim kartı."""

    def __init__(
        self,
        parent,
        text_preview: str,
        on_read: Callable[[], None],
        on_dismiss: Optional[Callable[[], None]] = None,
        auto_close_ms: int = 5000,
    ):
        super().__init__(parent)
        self._on_read = on_read
        self._on_dismiss = on_dismiss
        self._closed = False
        self._auto_close_ms = auto_close_ms
        self._t0 = time.monotonic()

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=CARD_BG)

        width, height = 392, 162
        scale = ctk.ScalingTracker.get_window_dpi_scaling(self)
        phys_w = int(round(width * scale))
        phys_h = int(round(height * scale))
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(16, sw - phys_w - 24)
        y = max(16, sh - phys_h - 76)

        card = ctk.CTkFrame(
            self,
            corner_radius=14,
            fg_color=CARD_BG,
            border_width=1,
            border_color=ACCENT_COLOR,
        )
        card.pack(fill="both", expand=True)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(12, 4))

        self._ic_wave = get_icon("audio-waveform", size=15, color=ACCENT_SOFT_TEXT)
        self._ic_close = get_icon("x", size=13, color=TEXT_MUTED)
        self._ic_speak = get_icon("volume-2", size=14, color=ACCENT_TEXT)

        ctk.CTkLabel(
            hdr,
            text=" Sono · Panoda yeni metin",
            image=self._ic_wave,
            compound="left",
            font=ui_font(12, "bold"),
            text_color=ACCENT_SOFT_TEXT,
        ).pack(side="left")

        ctk.CTkButton(
            hdr,
            text="",
            image=self._ic_close,
            width=26,
            height=26,
            fg_color="transparent",
            hover_color=SECONDARY_BTN,
            corner_radius=7,
            command=self._dismiss,
        ).pack(side="right")

        snippet = " ".join(text_preview.split())
        if len(snippet) > 95:
            snippet = snippet[:95].rstrip() + "…"

        ctk.CTkLabel(
            card,
            text=f'"{snippet}"',
            font=ui_font(12),
            text_color=TEXT_MAIN,
            wraplength=346,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=14, pady=(2, 10))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkLabel(
            btn_row,
            text="Sesli okuyayım mı?",
            font=ui_font(12),
            text_color=TEXT_MUTED,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text=" Sesli oku",
            image=self._ic_speak,
            compound="left",
            width=102,
            height=32,
            font=ui_font(12, "bold"),
            fg_color=ACCENT_COLOR,
            text_color=ACCENT_TEXT,
            hover_color=ACCENT_HOVER,
            corner_radius=9,
            command=self._accept,
        ).pack(side="right")

        ctk.CTkButton(
            btn_row,
            text="Kapat",
            width=66,
            height=32,
            font=ui_font(12),
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            text_color=TEXT_MAIN,
            hover_color=SECONDARY_BTN_HOVER,
            corner_radius=9,
            command=self._dismiss,
        ).pack(side="right", padx=(0, 6))

        # Alt kenarda otomatik kapanma çizgisi
        self._timer_canvas = tk.Canvas(
            card, height=3, bg=resolve_color(CARD_BORDER), highlightthickness=0, bd=0
        )
        self._timer_canvas.pack(fill="x", padx=12, pady=(0, 6))

        animate_window_slide_in(self, width, height, x, y, offset_y=20, duration_ms=200)

        if auto_close_ms > 0:
            self.after(auto_close_ms, self._dismiss)
            if not is_reduced_motion():
                self.after(30, self._tick_timer)

    def _tick_timer(self) -> None:
        if self._closed or not self.winfo_exists():
            return
        elapsed_ms = (time.monotonic() - self._t0) * 1000.0
        rem = max(0.0, 1.0 - elapsed_ms / max(1, self._auto_close_ms))
        w = self._timer_canvas.winfo_width()
        if w > 4:
            self._timer_canvas.delete("bar")
            self._timer_canvas.create_rectangle(
                0, 0, int(w * rem), 3, fill=resolve_color(ACCENT_COLOR), outline="", tags="bar"
            )
        if rem > 0.0:
            self.after(30, self._tick_timer)

    def _accept(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.destroy()
        self._on_read()

    def _dismiss(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.destroy()
        except Exception:
            pass
        if self._on_dismiss:
            self._on_dismiss()
