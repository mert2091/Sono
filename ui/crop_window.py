"""
Görsel Kırpma ve Seçim Penceresi (Sono).
Çift temalı (Açık / Koyu) ve Lucide vektör ikonlu alan kırpma aracı.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable
import customtkinter as ctk
from PIL import Image, ImageTk

from ui.icons import get_icon
from ui.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    ACCENT_TEXT,
    BG_COLOR,
    BTN_HEIGHT_MAIN,
    CARD_BG,
    CARD_BORDER,
    INNER_BG,
    RADIUS_BTN,
    RADIUS_CARD,
    SECONDARY_BTN,
    SECONDARY_BTN_BORDER,
    SECONDARY_BTN_HOVER,
    TEXT_MAIN,
    TEXT_MUTED,
    register_theme_listener,
    resolve_color,
    ui_font,
    unregister_theme_listener,
)


class CropWindow(ctk.CTkToplevel):
    """Görsel üzerinde seçim ve kırpma yapmayı sağlayan modal pencere."""

    def __init__(
        self,
        parent,
        image: Image.Image,
        on_crop_complete: Callable[[Image.Image], None],
    ):
        super().__init__(parent)
        self.title("Alan Kırp · Sono")
        self.geometry("860x660")
        self.minsize(620, 480)
        self.configure(fg_color=BG_COLOR)

        self._original_image = image
        self._on_crop_complete = on_crop_complete

        self._start_x = None
        self._start_y = None
        self._cur_rect = None
        self._scale_ratio = 1.0

        self.transient(parent)
        self.grab_set()
        self._apply_icon()
        self.after(250, self._apply_icon)

        self._setup_ui()
        register_theme_listener(self._on_theme_change)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.after(100, self._render_canvas_image)

    def _apply_icon(self) -> None:
        import os
        from ui.app import get_asset_path

        ico_path = get_asset_path("ses-studyosu.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

    def _setup_ui(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.grid(row=0, column=0, padx=18, pady=(14, 8), sticky="ew")

        self._ic_crop = get_icon("crop", size=16, color=ACCENT_COLOR)
        self._ic_check = get_icon("check", size=15, color=ACCENT_TEXT)

        ctk.CTkLabel(
            top_bar,
            text=" Fareyle sol tuşa basılı tutarak okunacak metnin etrafına çerçeve çizin.",
            image=self._ic_crop,
            compound="left",
            font=ui_font(13, "semibold"),
            text_color=TEXT_MAIN,
        ).pack(side="left")

        self.canvas_frame = ctk.CTkFrame(
            self,
            corner_radius=RADIUS_CARD,
            fg_color=INNER_BG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.canvas_frame.grid(row=1, column=0, padx=18, pady=6, sticky="nsew")
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self.canvas_frame,
            bg=resolve_color(INNER_BG),
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        self.canvas.bind("<ButtonPress-1>", self._on_button_press)
        self.canvas.bind("<B1-Motion>", self._on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_release)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=18, pady=(8, 14), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            btn_frame,
            text="Seçimi tamamladıktan sonra kırpıp OCR başlatın.",
            font=ui_font(12),
            text_color=TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w")

        btn_box = ctk.CTkFrame(btn_frame, fg_color="transparent")
        btn_box.grid(row=0, column=1, sticky="e")

        self.cancel_btn = ctk.CTkButton(
            btn_box,
            text="İptal",
            width=90,
            height=BTN_HEIGHT_MAIN - 6,
            font=ui_font(12),
            command=self.destroy,
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            text_color=TEXT_MAIN,
            hover_color=SECONDARY_BTN_HOVER,
            corner_radius=RADIUS_BTN,
        )
        self.cancel_btn.pack(side="left", padx=(0, 8))

        self.crop_btn = ctk.CTkButton(
            btn_box,
            text=" Seçili alanı oku",
            image=self._ic_check,
            compound="left",
            width=164,
            height=BTN_HEIGHT_MAIN - 6,
            font=ui_font(13, "bold"),
            command=self._apply_crop,
            fg_color=ACCENT_COLOR,
            text_color=ACCENT_TEXT,
            hover_color=ACCENT_HOVER,
            corner_radius=RADIUS_BTN,
            state="disabled",
        )
        self.crop_btn.pack(side="left")

    def _on_theme_change(self, _mode: str) -> None:
        if not self.winfo_exists():
            return
        self.canvas.configure(bg=resolve_color(INNER_BG))
        if self._cur_rect:
            self.canvas.itemconfigure(self._cur_rect, outline=resolve_color(ACCENT_COLOR))

    def _on_destroy(self, _event=None) -> None:
        unregister_theme_listener(self._on_theme_change)

    def _render_canvas_image(self) -> None:
        self.update_idletasks()
        c_w = self.canvas.winfo_width() or 800
        c_h = self.canvas.winfo_height() or 500

        img = self._original_image
        self._scale_ratio = min(c_w / img.width, c_h / img.height, 1.0)

        disp_w = int(img.width * self._scale_ratio)
        disp_h = int(img.height * self._scale_ratio)

        self._resized_img = img.resize((disp_w, disp_h), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(self._resized_img)

        self._offset_x = (c_w - disp_w) // 2
        self._offset_y = (c_h - disp_h) // 2

        self.canvas.delete("all")
        self.canvas.create_image(
            self._offset_x,
            self._offset_y,
            anchor="nw",
            image=self._tk_img,
        )

    def _on_button_press(self, event) -> None:
        self._start_x = event.x
        self._start_y = event.y
        if self._cur_rect:
            self.canvas.delete(self._cur_rect)
        self._cur_rect = self.canvas.create_rectangle(
            self._start_x,
            self._start_y,
            self._start_x,
            self._start_y,
            outline=resolve_color(ACCENT_COLOR),
            width=2,
            dash=(5, 3),
        )

    def _on_move_press(self, event) -> None:
        if self._cur_rect:
            self.canvas.coords(self._cur_rect, self._start_x, self._start_y, event.x, event.y)

    def _on_button_release(self, event) -> None:
        self._end_x = event.x
        self._end_y = event.y
        w = abs(self._end_x - self._start_x)
        h = abs(self._end_y - self._start_y)
        self.crop_btn.configure(state="normal" if (w > 15 and h > 15) else "disabled")

    def _apply_crop(self) -> None:
        x1 = min(self._start_x, self._end_x) - self._offset_x
        y1 = min(self._start_y, self._end_y) - self._offset_y
        x2 = max(self._start_x, self._end_x) - self._offset_x
        y2 = max(self._start_y, self._end_y) - self._offset_y

        orig_x1 = max(0, int(x1 / self._scale_ratio))
        orig_y1 = max(0, int(y1 / self._scale_ratio))
        orig_x2 = min(self._original_image.width, int(x2 / self._scale_ratio))
        orig_y2 = min(self._original_image.height, int(y2 / self._scale_ratio))

        if orig_x2 > orig_x1 and orig_y2 > orig_y1:
            cropped = self._original_image.crop((orig_x1, orig_y1, orig_x2, orig_y2))
            self._on_crop_complete(cropped)
            self.destroy()
