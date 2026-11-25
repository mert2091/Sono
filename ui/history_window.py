"""
Geçmiş & Kütüphane Penceresi (Sono).
Çift temalı (Açık / Koyu) ve Lucide vektör ikonlu bağımsız kütüphane penceresi.
"""

from __future__ import annotations

from typing import Callable
import customtkinter as ctk

from services.history_service import clear_all_history, delete_history_entry, get_all_history
from ui.icons import get_icon
from ui.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    ACCENT_SOFT_BG,
    ACCENT_SOFT_TEXT,
    ACCENT_TEXT,
    BG_COLOR,
    CARD_BG,
    CARD_BORDER,
    INNER_BG,
    RADIUS_BTN,
    RADIUS_CARD,
    SECONDARY_BTN,
    SECONDARY_BTN_BORDER,
    STOP_BTN_BG,
    STOP_BTN_BORDER,
    STOP_BTN_HOVER,
    STOP_BTN_TEXT,
    TEXT_MAIN,
    TEXT_MUTED,
    mono_font,
    ui_font,
)


class HistoryWindow(ctk.CTkToplevel):
    """Geçmiş belgeleri gösteren ve yöneten pencere."""

    def __init__(self, parent, on_select_entry: Callable[[str, str], None]):
        super().__init__(parent)
        self.title("Belge Kütüphanesi · Sono")
        self.geometry("800x580")
        self.minsize(600, 420)
        self.configure(fg_color=BG_COLOR)

        self._on_select_entry = on_select_entry
        self._items = []

        self._ic_book = get_icon("book-open", size=18, color=ACCENT_COLOR)
        self._ic_trash = get_icon("trash", size=14, color=STOP_BTN_TEXT)
        self._ic_arrow = get_icon("arrow-right", size=13, color=ACCENT_TEXT)
        self._ic_close = get_icon("x", size=13, color=TEXT_MUTED)

        self.transient(parent)
        self._apply_icon()
        self.after(250, self._apply_icon)
        self._setup_ui()
        self._load_items()

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
        top_bar.grid(row=0, column=0, padx=18, pady=14, sticky="ew")
        top_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            top_bar,
            text=" Okuma ve Çeviri Geçmişi",
            image=self._ic_book,
            compound="left",
            font=ui_font(16, "bold"),
            text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            top_bar,
            text=" Geçmişi temizle",
            image=self._ic_trash,
            compound="left",
            width=140,
            height=34,
            font=ui_font(12, "semibold"),
            fg_color=STOP_BTN_BG,
            border_width=1,
            border_color=STOP_BTN_BORDER,
            text_color=STOP_BTN_TEXT,
            hover_color=STOP_BTN_HOVER,
            corner_radius=RADIUS_BTN,
            command=self._clear_all,
        ).grid(row=0, column=1, sticky="e")

        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            corner_radius=RADIUS_CARD,
            fg_color=INNER_BG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.scroll_frame.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

    def _load_items(self) -> None:
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        self._items = get_all_history(limit=50)
        if not self._items:
            ctk.CTkLabel(
                self.scroll_frame,
                text="Henüz kaydedilmiş bir geçmiş bulunmuyor.\nOkuttuğunuz belgeler otomatik olarak burada saklanır.",
                font=ui_font(13),
                text_color=TEXT_MUTED,
            ).pack(pady=60)
            return

        for item in self._items:
            self._create_item_card(item)

    def _create_item_card(self, item: dict) -> None:
        card = ctk.CTkFrame(
            self.scroll_frame,
            corner_radius=12,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        card.pack(fill="x", pady=4, padx=6)
        card.grid_columnconfigure(1, weight=1)

        badge = (item.get("source_type") or "BELGE").upper()[:6]
        ctk.CTkLabel(
            card,
            text=badge,
            width=54,
            height=34,
            corner_radius=8,
            fg_color=ACCENT_SOFT_BG,
            text_color=ACCENT_SOFT_TEXT,
            font=mono_font(10, "bold"),
        ).grid(row=0, column=0, rowspan=2, padx=(12, 12), pady=10)

        ctk.CTkLabel(
            card,
            text=item.get("title") or "Belge Metni",
            font=ui_font(13, "bold"),
            text_color=TEXT_MAIN,
            anchor="w",
        ).grid(row=0, column=1, sticky="w", pady=(10, 0))

        sub_info = f"{item.get('created_at')}  ·  {item.get('word_count')} kelime"
        ctk.CTkLabel(
            card,
            text=sub_info,
            font=mono_font(11),
            text_color=TEXT_MUTED,
            anchor="w",
        ).grid(row=1, column=1, sticky="w", pady=(0, 10))

        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.grid(row=0, column=2, rowspan=2, padx=12, pady=8)

        ctk.CTkButton(
            btn_box,
            text="Aç ",
            image=self._ic_arrow,
            compound="right",
            width=72,
            height=32,
            font=ui_font(12, "bold"),
            command=lambda i=item: self._select_item(i),
            fg_color=ACCENT_COLOR,
            text_color=ACCENT_TEXT,
            hover_color=ACCENT_HOVER,
            corner_radius=8,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_box,
            text="",
            image=self._ic_close,
            width=32,
            height=32,
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            hover_color=STOP_BTN_HOVER,
            corner_radius=8,
            command=lambda i_id=item["id"]: self._delete_item(i_id),
        ).pack(side="left")

    def _select_item(self, item: dict) -> None:
        text = item.get("text_content") or ""
        trans = item.get("translation_content") or ""
        self._on_select_entry(text, trans)
        self.destroy()

    def _delete_item(self, item_id: int) -> None:
        delete_history_entry(item_id)
        self._load_items()

    def _clear_all(self) -> None:
        clear_all_history()
        self._load_items()
