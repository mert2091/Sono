"""
Ana Uygulama Penceresi (Sono).
Özgün Stüdyo Kabuğu:
- Sol dikey Stüdyo Rayı (Sono amblemi, aktif şeritli navigasyon, anlık Koyu/Açık tema anahtarı)
- Üst dinamik çalışma çubuğu (Görünüm başlığı, hızlı Ekran Yakala kısayolu, canlı Gemini nabız rozeti)
- Ana sahne: Belge Sahnesi + Metin Stüdyosu + Hi-Fi Akustik Oynatıcı Konsolu
- Kitaplık (okuma ilerleme çubuklu kartlar) ve Akıllı Araçlar (ikon rozetli 2x2 ızgara)
"""

from __future__ import annotations

import os
import sys
import threading
from tkinter import filedialog
from typing import Optional
import customtkinter as ctk
from PIL import Image

import config
from services.ai_tools_service import ask_document_question, fix_and_enhance_text, summarize_text
from services.batch_service import (
    export_combined_text_to_single_mp3,
    process_files_to_combined_text,
)
from services.history_service import (
    add_history_entry,
    clear_all_history,
    delete_history_entry,
    get_all_history,
    update_history_progress,
)
from services.hotkey_service import GlobalHotkeyManager
from services.logger_service import get_logger
from services.ocr_service import extract_text_from_image
from services.settings_service import SettingsService, shortcut_to_tk_sequences
from services.translation_service import detect_and_translate
from services.tray_service import TrayService
from services.tts_service import TTSService
from services.update_service import (
    UpdateCheckResult,
    check_for_updates,
    download_update_file,
    is_safe_github_url,
    launch_updater_and_exit,
)
from ui.animations import LivePulseDot
from ui.clipboard_prompt import ClipboardPromptWindow
from ui.icons import get_icon
from ui.screen_capture_window import ScreenCaptureWindow
from ui.settings_panel import SettingsPanel
from ui.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    ACCENT_SOFT_BG,
    ACCENT_SOFT_BORDER,
    ACCENT_SOFT_TEXT,
    ACCENT_TEXT,
    BG_COLOR,
    CARD_BG,
    CARD_BORDER,
    DIVIDER_COLOR,
    HEADER_BG,
    INNER_BG,
    PADDING_CARD,
    RADIUS_BTN,
    RADIUS_CARD,
    RADIUS_INNER,
    RADIUS_PILL,
    RAIL_BG,
    RAIL_BORDER,
    RAIL_ITEM_ACTIVE,
    RAIL_ITEM_HOVER,
    RAIL_WIDTH,
    SECONDARY_BTN,
    SECONDARY_BTN_BORDER,
    SECONDARY_BTN_HOVER,
    SLIDER_TRACK,
    SPACING_CARD,
    STATUS_PILL_BG,
    STATUS_PILL_BORDER,
    STATUS_PILL_HOVER,
    STOP_BTN_BG,
    STOP_BTN_BORDER,
    STOP_BTN_HOVER,
    STOP_BTN_TEXT,
    SUCCESS_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
    TEXT_SUBTLE,
    apply_default_font,
    display_font,
    mono_font,
    notify_theme_changed,
    set_reduced_motion,
    ui_font,
)
from utils.text_utils import clean_text, split_into_paragraphs, split_paragraphs_with_spans
from version import APP_VERSION

try:
    from tkinterdnd2 import TkinterDnD

    class _AppBase(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = TkinterDnD._require(self)

    _DND_AVAILABLE = True
except Exception:
    _AppBase = ctk.CTk
    _DND_AVAILABLE = False


def get_asset_path(filename: str) -> str:
    """Normal çalışma ve PyInstaller paketinde assets/ dosya yolunu döndür."""
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "assets", filename)


class App(_AppBase):
    """Sono — Çift Temalı Yapay Zeka Belge ve Ses Stüdyosu."""

    VIEW_META = {
        "home": ("Stüdyo", "Belgeyi yükle, çevir, özetle ve doğal sesle dinle."),
        "library": ("Kitaplık", "Daha önce okuttuğun ve çevirdiğin belgeler cihazında saklanır."),
        "tools": ("Akıllı Araçlar", "Ekran yakalama, toplu seslendirme ve uyku zamanlayıcısı."),
        "settings": ("Ayarlar", "Tema, kısayollar, yapay zeka anahtarı ve güncellemeler."),
    }

    def __init__(self):
        apply_default_font()
        super().__init__()

        self.title("Sono")
        self.geometry("1280x820")
        self.minsize(1060, 700)

        self.settings = SettingsService()
        saved_theme = self.settings.get_general("theme", "dark")
        if saved_theme not in ("dark", "light"):
            saved_theme = "dark"
        set_reduced_motion(self.settings.get_feature("reduced_motion"))
        ctk.set_appearance_mode(saved_theme)
        self.configure(fg_color=BG_COLOR)
        self._current_theme = saved_theme
        self._active_view = "home"

        self.tts_service = TTSService()
        self._current_image: Optional[Image.Image] = None
        self._active_history_id: Optional[int] = None
        self._active_resume_paragraph: int = 0
        self._playback_gen: int = 0
        self._header_logo_img: Optional[ctk.CTkImage] = None
        self._nav_items: dict[str, dict] = {}
        self._views: dict[str, ctk.CTkFrame] = {}
        self._dynamic_shortcut_binds: list[tuple[str, str]] = []
        self._last_update_result: Optional[UpdateCheckResult] = None
        self._global_hotkeys = GlobalHotkeyManager()
        self._capture_in_progress = False
        self._last_clipboard_text: str = ""
        self._clipboard_after_id: Optional[str] = None
        self._lib_search_after_id: Optional[str] = None
        self._active_clipboard_prompt: Optional[ClipboardPromptWindow] = None
        self._sleep_remaining_sec: int = 0
        self._sleep_armed_sec: int = 0
        self._sleep_after_id: Optional[str] = None
        self._tray_service = TrayService(
            icon_path=get_asset_path("ses-studyosu-logo.png"),
            on_show=lambda: self.after(0, self._restore_from_tray),
            on_capture=lambda: self.after(0, self._start_screen_capture),
            on_quit=lambda: self.after(0, lambda: self.on_closing(force_quit=True)),
        )

        self._apply_window_icon()
        self.after(250, self._apply_window_icon)
        self.after(600, self._apply_window_icon)

        self._setup_ui()
        self._bind_shortcuts()
        self._init_tray_and_clipboard()
        self._refresh_api_badge()
        if not config.has_api_key():
            self.after(150, self._prompt_missing_api_key)
        self.after(2000, self._maybe_auto_check_updates)

    def _refresh_api_badge(self, ready: Optional[bool] = None, busy: bool = False) -> None:
        is_ready = config.has_api_key() if ready is None else bool(ready)
        if not hasattr(self, "api_badge_frame"):
            return

        if busy:
            self.api_badge_frame.configure(fg_color=ACCENT_SOFT_BG, border_color=ACCENT_SOFT_BORDER)
            self.api_badge_lbl.configure(text="Gemini çalışıyor…", text_color=ACCENT_SOFT_TEXT)
            self.gemini_dot.set_bg_token(ACCENT_SOFT_BG)
            self.gemini_dot.set_mode("busy")
        elif is_ready:
            self.api_badge_frame.configure(fg_color=STATUS_PILL_BG, border_color=STATUS_PILL_BORDER)
            self.api_badge_lbl.configure(text="Gemini hazır", text_color=SUCCESS_COLOR)
            self.gemini_dot.set_bg_token(STATUS_PILL_BG)
            self.gemini_dot.set_mode("ready")
        else:
            self.api_badge_frame.configure(fg_color=STOP_BTN_BG, border_color=STOP_BTN_BORDER)
            self.api_badge_lbl.configure(text="API anahtarı gerekli", text_color=STOP_BTN_TEXT)
            self.gemini_dot.set_bg_token(STOP_BTN_BG)
            self.gemini_dot.set_mode("error")

    def _prompt_missing_api_key(self) -> None:
        self._switch_view("settings", settings_tab="ai")
        self.text_panel.set_status("Başlamak için Ayarlar → Yapay Zeka ekranından Gemini API anahtarınızı girin.")

    def _maybe_prompt_invalid_key(self, err_text: str) -> None:
        low = (err_text or "").lower()
        if "api anahtarı" in low and ("geçersiz" in low or "girilmemiş" in low or "yetkisiz" in low):
            self._refresh_api_badge(False)
            self._switch_view("settings", settings_tab="ai")
            if hasattr(self, "settings_panel") and hasattr(self.settings_panel, "api_key_feedback_lbl"):
                self.settings_panel.api_key_feedback_lbl.configure(
                    text=err_text, text_color=STOP_BTN_TEXT
                )

    def _apply_window_icon(self) -> None:
        ico_path = get_asset_path("ses-studyosu.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(default=ico_path)
                self.iconbitmap(ico_path)
            except Exception:
                pass

    def _load_brand_and_icons(self) -> None:
        logo_path = get_asset_path("ses-studyosu-logo.png")
        if os.path.exists(logo_path):
            try:
                pil_logo = Image.open(logo_path).convert("RGBA")
                self._header_logo_img = ctk.CTkImage(
                    light_image=pil_logo, dark_image=pil_logo, size=(34, 34)
                )
            except Exception:
                self._header_logo_img = None

        self._ic_rail = {
            "home_idle": get_icon("audio-waveform", size=20, color=TEXT_MUTED),
            "home_act": get_icon("audio-waveform", size=20, color=ACCENT_COLOR, stroke_width=2.1),
            "library_idle": get_icon("book-open", size=20, color=TEXT_MUTED),
            "library_act": get_icon("book-open", size=20, color=ACCENT_COLOR, stroke_width=2.1),
            "tools_idle": get_icon("sparkles", size=20, color=TEXT_MUTED),
            "tools_act": get_icon("sparkles", size=20, color=ACCENT_COLOR, stroke_width=2.1),
            "settings_idle": get_icon("sliders-horizontal", size=20, color=TEXT_MUTED),
            "settings_act": get_icon("sliders-horizontal", size=20, color=ACCENT_COLOR, stroke_width=2.1),
            "sun": get_icon("sun", size=18, color=TEXT_MAIN),
            "moon": get_icon("moon", size=18, color=TEXT_MAIN),
        }
        self._ic_scan = get_icon("scan", size=15, color=TEXT_MAIN)
        self._ic_search = get_icon("search", size=15, color=TEXT_MUTED)
        self._ic_trash_err = get_icon("trash", size=14, color=STOP_BTN_TEXT)
        self._ic_arrow_r = get_icon("arrow-right", size=14, color=ACCENT_TEXT)
        self._ic_close_sm = get_icon("x", size=14, color=TEXT_MUTED)
        self._ic_empty_lib = get_icon("book-open", size=28, color=ACCENT_SOFT_TEXT, stroke_width=1.7)

    # ── Ana Kabuk Kurulumu (Sol Stüdyo Rayı + Sağ Çalışma Alanı) ──

    def _setup_ui(self) -> None:
        self._load_brand_and_icons()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)  # Sol Stüdyo Rayı
        self.grid_columnconfigure(1, weight=0)  # 1px dikey ayırıcı
        self.grid_columnconfigure(2, weight=1)  # Sağ Çalışma Alanı

        # ── 1. SOL STÜDYO RAYI ──
        rail = ctk.CTkFrame(self, width=RAIL_WIDTH, fg_color=RAIL_BG, corner_radius=0)
        rail.grid(row=0, column=0, sticky="nsew")
        rail.grid_propagate(False)
        rail.grid_rowconfigure(2, weight=1)
        rail.grid_columnconfigure(0, weight=1)

        # Üst: Sono Amblemi
        brand_wrap = ctk.CTkFrame(rail, fg_color="transparent")
        brand_wrap.grid(row=0, column=0, pady=(16, 18))

        logo_btn = ctk.CTkButton(
            brand_wrap,
            text="" if self._header_logo_img else "S",
            image=self._header_logo_img,
            width=44,
            height=44,
            font=display_font(18, "bold"),
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
            hover_color=RAIL_ITEM_HOVER,
            text_color=ACCENT_COLOR,
            corner_radius=13,
            command=lambda: self._switch_view("home"),
        )
        logo_btn.pack()

        ctk.CTkLabel(
            brand_wrap,
            text="SONO",
            font=mono_font(10, "bold"),
            text_color=TEXT_SUBTLE,
        ).pack(pady=(5, 0))

        # Orta: Dikey Navigasyon Öğeleri
        nav_stack = ctk.CTkFrame(rail, fg_color="transparent")
        nav_stack.grid(row=1, column=0, sticky="ew", padx=6)

        nav_defs = [
            ("home", "Stüdyo"),
            ("library", "Kitaplık"),
            ("tools", "Araçlar"),
            ("settings", "Ayarlar"),
        ]
        for key, label in nav_defs:
            self._make_rail_item(nav_stack, key, label)

        # Alt: Anlık Tema Değiştirici (Koyu <-> Açık)
        bottom_rail = ctk.CTkFrame(rail, fg_color="transparent")
        bottom_rail.grid(row=3, column=0, sticky="ew", padx=8, pady=(8, 16))

        is_dark = self._current_theme == "dark"
        self.theme_btn = ctk.CTkButton(
            bottom_rail,
            text="Açık" if is_dark else "Koyu",
            image=self._ic_rail["sun"] if is_dark else self._ic_rail["moon"],
            compound="top",
            width=58,
            height=54,
            font=ui_font(10, "semibold"),
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
            hover_color=RAIL_ITEM_HOVER,
            text_color=TEXT_MUTED,
            corner_radius=12,
            command=self._toggle_theme,
        )
        self.theme_btn.pack(fill="x")

        # Dikey ayırıcı çizgi
        v_sep = ctk.CTkFrame(self, width=1, fg_color=RAIL_BORDER, corner_radius=0)
        v_sep.grid(row=0, column=1, sticky="ns")

        # ── 2. SAĞ ÇALIŞMA ALANI (Üst Çubuk + Aktif Sahne) ──
        main_col = ctk.CTkFrame(self, fg_color=BG_COLOR, corner_radius=0)
        main_col.grid(row=0, column=2, sticky="nsew")
        main_col.grid_rowconfigure(0, weight=0)
        main_col.grid_rowconfigure(1, weight=0)
        main_col.grid_rowconfigure(2, weight=1)
        main_col.grid_columnconfigure(0, weight=1)

        # İnce Entegre Üst Başlık Çubuğu
        header = ctk.CTkFrame(main_col, fg_color=HEADER_BG, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(14, 12))
        header.grid_columnconfigure(0, weight=1)

        title_stack = ctk.CTkFrame(header, fg_color="transparent")
        title_stack.grid(row=0, column=0, sticky="w")

        self.view_title_lbl = ctk.CTkLabel(
            title_stack,
            text="Stüdyo",
            font=display_font(20, "bold"),
            text_color=TEXT_MAIN,
        )
        self.view_title_lbl.pack(anchor="w")

        self.view_sub_lbl = ctk.CTkLabel(
            title_stack,
            text=self.VIEW_META["home"][1],
            font=ui_font(12),
            text_color=TEXT_MUTED,
        )
        self.view_sub_lbl.pack(anchor="w")

        # Sağ Üst Aksiyonlar: Hızlı Ekran Yakala + Canlı Gemini Durumu
        right_hdr = ctk.CTkFrame(header, fg_color="transparent")
        right_hdr.grid(row=0, column=1, sticky="e")

        self.quick_capture_btn = ctk.CTkButton(
            right_hdr,
            text=" Ekran yakala",
            image=self._ic_scan,
            compound="left",
            height=34,
            font=ui_font(12, "semibold"),
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
            hover_color=SECONDARY_BTN_HOVER,
            text_color=TEXT_MAIN,
            corner_radius=10,
            command=self._start_screen_capture,
        )
        self.quick_capture_btn.pack(side="left", padx=(0, 10))

        # Canlı nabız noktalı tıklanabilir Gemini durum kapsülü
        self.api_badge_frame = ctk.CTkFrame(
            right_hdr,
            height=34,
            fg_color=STATUS_PILL_BG,
            border_width=1,
            border_color=STATUS_PILL_BORDER,
            corner_radius=17,
            cursor="hand2",
        )
        self.api_badge_frame.pack(side="left")
        self.api_badge_frame.grid_rowconfigure(0, weight=1)

        self.gemini_dot = LivePulseDot(
            self.api_badge_frame,
            size=16,
            bg_token=STATUS_PILL_BG,
            on_click=lambda: self._switch_view("settings", settings_tab="ai"),
        )
        self.gemini_dot.grid(row=0, column=0, padx=(11, 5), pady=8)

        self.api_badge_lbl = ctk.CTkLabel(
            self.api_badge_frame,
            text="Gemini hazır",
            font=ui_font(12, "semibold"),
            text_color=SUCCESS_COLOR,
            cursor="hand2",
        )
        self.api_badge_lbl.grid(row=0, column=1, padx=(0, 13), pady=6)

        for w in (self.api_badge_frame, self.api_badge_lbl):
            w.bind("<Button-1>", lambda _e: self._switch_view("settings", settings_tab="ai"))

        # Yatay 1px ayırıcı
        h_sep = ctk.CTkFrame(main_col, height=1, fg_color=DIVIDER_COLOR, corner_radius=0)
        h_sep.grid(row=1, column=0, sticky="ew")

        # Aktif Görünüm Sahnesi
        self.stage = ctk.CTkFrame(main_col, fg_color="transparent")
        self.stage.grid(row=2, column=0, sticky="nsew", padx=20, pady=16)
        self.stage.grid_rowconfigure(0, weight=1)
        self.stage.grid_columnconfigure(0, weight=1)

        self._build_home_view()
        self._build_library_view()
        self._build_tools_view()
        self._build_settings_view()

        self._switch_view("home")

    def _make_rail_item(self, parent, key: str, label: str) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)
        row.grid_columnconfigure(1, weight=1)

        indicator = ctk.CTkFrame(row, width=3, height=24, corner_radius=2, fg_color="transparent")
        indicator.grid(row=0, column=0, padx=(0, 3), sticky="w")

        btn = ctk.CTkButton(
            row,
            text=label,
            image=self._ic_rail[f"{key}_idle"],
            compound="top",
            width=58,
            height=54,
            font=ui_font(10, "semibold"),
            fg_color="transparent",
            hover_color=RAIL_ITEM_HOVER,
            text_color=TEXT_MUTED,
            corner_radius=12,
            command=lambda k=key: self._switch_view(k),
        )
        btn.grid(row=0, column=1, sticky="ew")
        self._nav_items[key] = {"btn": btn, "indicator": indicator}

    # ── Görünüm 1: Ana Sayfa (Stüdyo) ────────────────────────────

    def _build_home_view(self) -> None:
        from ui.audio_panel import AudioPanel
        from ui.image_panel import ImagePanel
        from ui.text_panel import TextPanel

        view = ctk.CTkFrame(self.stage, fg_color="transparent")
        view.grid_rowconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=0)
        view.grid_columnconfigure(0, weight=1)

        cards_workspace = ctk.CTkFrame(view, fg_color="transparent")
        cards_workspace.grid(row=0, column=0, sticky="nsew", pady=(0, SPACING_CARD))
        cards_workspace.grid_rowconfigure(0, weight=1)
        cards_workspace.grid_columnconfigure(0, weight=42, uniform="studio")
        cards_workspace.grid_columnconfigure(1, weight=58, uniform="studio")

        self.image_panel = ImagePanel(
            cards_workspace,
            on_image_loaded=self._on_image_loaded,
            on_document_loaded=self._on_document_loaded,
        )
        self.image_panel.grid(row=0, column=0, padx=(0, SPACING_CARD // 2), sticky="nsew")

        self.text_panel = TextPanel(
            cards_workspace,
            on_translate=self._on_translate_clicked,
            on_read=self._on_read_clicked,
            on_export_mp3=self._on_export_mp3_clicked,
            on_summarize=self._on_summarize_clicked,
            on_enhance=self._on_enhance_clicked,
            on_ask_question=self._on_ask_question_clicked,
            on_jump_to_offset=self._on_jump_to_offset,
        )
        self.text_panel.grid(row=0, column=1, padx=(SPACING_CARD // 2, 0), sticky="nsew")

        self.audio_panel = AudioPanel(
            view, self.tts_service, on_stop=self._on_playback_stopped
        )
        self.audio_panel.grid(row=1, column=0, sticky="ew")

        self._views["home"] = view

    # ── Görünüm 2: Kitaplık ──────────────────────────────────────

    def _build_library_view(self) -> None:
        view = ctk.CTkFrame(self.stage, fg_color="transparent")
        view.grid_rowconfigure(1, weight=1)
        view.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(view, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        top.grid_columnconfigure(0, weight=1)

        # Arama kutusu + ikon kapsülü
        search_box = ctk.CTkFrame(
            top,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
            corner_radius=RADIUS_BTN,
            height=38,
        )
        search_box.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(search_box, text="", image=self._ic_search, width=20).pack(
            side="left", padx=(10, 4), pady=6
        )
        self.lib_search_entry = ctk.CTkEntry(
            search_box,
            placeholder_text="Başlık veya metin içinde ara…",
            width=260,
            height=34,
            font=ui_font(12),
            fg_color="transparent",
            border_width=0,
            text_color=TEXT_MAIN,
            placeholder_text_color=TEXT_MUTED,
        )
        self.lib_search_entry.pack(side="left", padx=(0, 10), pady=2)
        self.lib_search_entry.bind("<KeyRelease>", self._schedule_library_refresh)

        right_hdr = ctk.CTkFrame(top, fg_color="transparent")
        right_hdr.grid(row=0, column=1, sticky="e")

        self.lib_count_lbl = ctk.CTkLabel(
            right_hdr,
            text="0 kayıt",
            font=mono_font(11, "bold"),
            text_color=TEXT_MUTED,
            fg_color=SECONDARY_BTN,
            corner_radius=8,
            padx=10,
            pady=5,
        )
        self.lib_count_lbl.pack(side="left", padx=(0, 10))

        clear_btn = ctk.CTkButton(
            right_hdr,
            text=" Geçmişi temizle",
            image=self._ic_trash_err,
            compound="left",
            height=36,
            font=ui_font(12, "semibold"),
            fg_color=STOP_BTN_BG,
            border_width=1,
            border_color=STOP_BTN_BORDER,
            text_color=STOP_BTN_TEXT,
            hover_color=STOP_BTN_HOVER,
            corner_radius=RADIUS_BTN,
            command=self._clear_library,
        )
        clear_btn.pack(side="left")

        self.lib_scroll = ctk.CTkScrollableFrame(
            view,
            corner_radius=RADIUS_CARD,
            fg_color=INNER_BG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.lib_scroll.grid(row=1, column=0, sticky="nsew")
        self.lib_scroll.grid_columnconfigure(0, weight=1)

        self._views["library"] = view

    def _schedule_library_refresh(self, _event=None) -> None:
        if self._lib_search_after_id is not None:
            try:
                self.after_cancel(self._lib_search_after_id)
            except Exception:
                pass
            self._lib_search_after_id = None
        self._lib_search_after_id = self.after(180, self._run_debounced_library_refresh)

    def _run_debounced_library_refresh(self) -> None:
        self._lib_search_after_id = None
        self._refresh_library()

    def _refresh_library(self) -> None:
        for w in self.lib_scroll.winfo_children():
            w.destroy()

        query = self.lib_search_entry.get().strip().lower() if hasattr(self, "lib_search_entry") else ""
        items = get_all_history(limit=60)
        if query:
            items = [
                it
                for it in items
                if query in (it.get("title") or "").lower()
                or query in (it.get("text_content") or "").lower()
            ]

        if hasattr(self, "lib_count_lbl"):
            self.lib_count_lbl.configure(text=f"{len(items)} kayıt")

        if not items:
            empty_box = ctk.CTkFrame(self.lib_scroll, fg_color="transparent")
            empty_box.pack(pady=70)
            ctk.CTkLabel(
                empty_box,
                text="",
                image=self._ic_empty_lib,
                width=58,
                height=58,
                corner_radius=16,
                fg_color=ACCENT_SOFT_BG,
            ).pack(pady=(0, 14))
            ctk.CTkLabel(
                empty_box,
                text="Henüz kayıtlı belge yok" if not query else "Aramayla eşleşen belge bulunamadı",
                font=ui_font(15, "bold"),
                text_color=TEXT_MAIN,
            ).pack(pady=(0, 4))
            ctk.CTkLabel(
                empty_box,
                text="Stüdyo ekranında okuttuğun belgeler burada otomatik arşivlenir.",
                font=ui_font(12),
                text_color=TEXT_MUTED,
            ).pack()
            return

        for item in items:
            card = ctk.CTkFrame(
                self.lib_scroll,
                corner_radius=RADIUS_INNER,
                fg_color=CARD_BG,
                border_width=1,
                border_color=CARD_BORDER,
            )
            card.pack(fill="x", padx=8, pady=5)
            card.grid_columnconfigure(1, weight=1)

            badge_text = (item.get("source_type") or "BELGE").upper()[:6]
            ctk.CTkLabel(
                card,
                text=badge_text,
                width=58,
                height=38,
                corner_radius=10,
                fg_color=ACCENT_SOFT_BG,
                text_color=ACCENT_SOFT_TEXT,
                font=mono_font(10, "bold"),
            ).grid(row=0, column=0, rowspan=3, padx=(14, 14), pady=12)

            raw_title = (item.get("title") or "Belge Metni").lstrip("📄📑📋🖼️ ").strip() or "Belge Metni"
            ctk.CTkLabel(
                card,
                text=raw_title,
                font=ui_font(14, "bold"),
                text_color=TEXT_MAIN,
                anchor="w",
            ).grid(row=0, column=1, sticky="w", pady=(10, 2))

            last_p = int(item.get("last_paragraph") or 0)
            tot_p = int(item.get("total_paragraphs") or 0)
            has_resume = last_p > 0 and tot_p > 0
            resume_part = f"  ·  Paragraf {last_p + 1}/{tot_p}" if has_resume else ""
            sub = f"{item.get('created_at', '')}  ·  {item.get('word_count', 0)} kelime{resume_part}"
            ctk.CTkLabel(
                card,
                text=sub,
                font=mono_font(11),
                text_color=ACCENT_SOFT_TEXT if has_resume else TEXT_MUTED,
                anchor="w",
            ).grid(row=1, column=1, sticky="w", pady=(0, 6 if has_resume else 10))

            if has_resume:
                pbar = ctk.CTkProgressBar(
                    card,
                    height=4,
                    width=180,
                    fg_color=SLIDER_TRACK,
                    progress_color=ACCENT_COLOR,
                    corner_radius=2,
                )
                pbar.set(min(1.0, (last_p + 1) / max(1, tot_p)))
                pbar.grid(row=2, column=1, sticky="w", pady=(0, 10))

            btn_row = ctk.CTkFrame(card, fg_color="transparent")
            btn_row.grid(row=0, column=2, rowspan=3, padx=14, pady=10)

            ctk.CTkButton(
                btn_row,
                text="Devam et " if has_resume else "Aç ",
                image=self._ic_arrow_r,
                compound="right",
                width=98 if has_resume else 76,
                height=34,
                font=ui_font(12, "bold"),
                fg_color=ACCENT_COLOR,
                text_color=ACCENT_TEXT,
                hover_color=ACCENT_HOVER,
                corner_radius=9,
                command=lambda i=item: self._load_from_history(i),
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                btn_row,
                text="",
                image=self._ic_close_sm,
                width=34,
                height=34,
                fg_color=SECONDARY_BTN,
                border_width=1,
                border_color=SECONDARY_BTN_BORDER,
                hover_color=STOP_BTN_HOVER,
                corner_radius=9,
                command=lambda i_id=item["id"]: self._delete_library_item(i_id),
            ).pack(side="left")

    def _delete_library_item(self, item_id: int) -> None:
        delete_history_entry(item_id)
        self._refresh_library()

    def _clear_library(self) -> None:
        clear_all_history()
        self._refresh_library()

    # ── Görünüm 3: Akıllı Araçlar ────────────────────────────────

    def _build_tools_view(self) -> None:
        view = ctk.CTkFrame(self.stage, fg_color="transparent")
        view.grid_columnconfigure((0, 1), weight=1, uniform="tools")

        self._make_tool_card(
            view,
            0,
            0,
            icon_name="scan",
            title="Ekran bölgesi yakala ve oku",
            desc="Ekranı karartıp fareyle seçtiğin alanı anında Gemini ile çözümler ve seslendirmeye başlar.",
            status_text="Aktif · Global kısayol destekli",
            buttons=[("Şimdi yakala", self._start_screen_capture, True)],
        )

        self._batch_status_lbl = self._make_tool_card(
            view,
            0,
            1,
            icon_name="layers",
            title="Toplu işleme & MP3 birleştirme",
            desc="Birden fazla PDF, DOCX, PPTX veya görseli sırayla okut ya da tek bir MP3 sesli kitapta birleştir.",
            status_text="Aktif · Çoklu dosya destekli",
            buttons=[
                ("Tek MP3 yap", self._start_batch_mp3, False),
                ("Sırayla oku", self._start_batch_read, True),
            ],
        )

        self._sleep_status_lbl = self._make_tool_card(
            view,
            1,
            0,
            icon_name="moon-star",
            title="Uyku zamanlayıcısı",
            desc="Sesli okuma başladıktan sonra belirlediğin süre dolduğunda oynatıcıyı yumuşakça durdurur.",
            status_text="Kapalı",
            buttons=[
                ("İptal", self._cancel_sleep_timer, False),
                ("60 dk", lambda: self._start_sleep_timer(60), False),
                ("30 dk", lambda: self._start_sleep_timer(30), False),
                ("15 dk", lambda: self._start_sleep_timer(15), False),
                ("1 dk", lambda: self._start_sleep_timer(1), True),
            ],
        )

        self._make_tool_card(
            view,
            1,
            1,
            icon_name="clipboard-check",
            title="Pano izleme & Sistem tepsisi",
            desc="Kopyaladığın metinlerde 'Okuyayım mı?' bildirimi sunar; pencere kapanınca arka planda hazır bekler.",
            status_text="Aktif · Ayarlar'dan yönetilir",
            buttons=[("Tepsiye küçült", self._minimize_to_tray_now, False)],
        )

        self._views["tools"] = view

    def _make_tool_card(
        self,
        parent,
        row: int,
        col: int,
        icon_name: str,
        title: str,
        desc: str,
        status_text: str,
        buttons: list[tuple[str, callable, bool]],
    ) -> ctk.CTkLabel:
        card = ctk.CTkFrame(
            parent,
            corner_radius=RADIUS_CARD,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        card.grid(
            row=row,
            column=col,
            sticky="nsew",
            padx=(0, 8) if col == 0 else (8, 0),
            pady=(0, 16),
        )

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=PADDING_CARD, pady=(PADDING_CARD, 10))

        ic = get_icon(icon_name, size=20, color=ACCENT_SOFT_TEXT, stroke_width=1.9)
        badge = ctk.CTkLabel(
            top_row,
            text="",
            image=ic,
            width=40,
            height=40,
            corner_radius=11,
            fg_color=ACCENT_SOFT_BG,
        )
        badge.pack(side="left", padx=(0, 12))

        title_lbl = ctk.CTkLabel(
            top_row,
            text=title,
            font=ui_font(15, "bold"),
            text_color=TEXT_MAIN,
            anchor="w",
        )
        title_lbl.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            card,
            text=desc,
            font=ui_font(12),
            text_color=TEXT_MUTED,
            wraplength=440,
            justify="left",
            anchor="w",
        ).pack(anchor="w", padx=PADDING_CARD, pady=(0, 18))

        footer_row = ctk.CTkFrame(card, fg_color="transparent")
        footer_row.pack(fill="x", padx=PADDING_CARD, pady=(0, PADDING_CARD))

        is_active = "Aktif" in status_text
        status_lbl = ctk.CTkLabel(
            footer_row,
            text=status_text,
            font=ui_font(11, "semibold"),
            text_color=SUCCESS_COLOR if is_active else ACCENT_SOFT_TEXT,
            fg_color=STATUS_PILL_BG if is_active else ACCENT_SOFT_BG,
            corner_radius=8,
            padx=10,
            pady=4,
        )
        status_lbl.pack(side="left")

        for btn_lbl, btn_cmd, is_primary in buttons:
            ctk.CTkButton(
                footer_row,
                text=btn_lbl,
                height=34,
                width=62 if len(btn_lbl) <= 6 else 108,
                font=ui_font(12, "bold" if is_primary else "normal"),
                fg_color=ACCENT_COLOR if is_primary else SECONDARY_BTN,
                border_width=0 if is_primary else 1,
                border_color=SECONDARY_BTN_BORDER,
                text_color=ACCENT_TEXT if is_primary else TEXT_MAIN,
                hover_color=ACCENT_HOVER if is_primary else SECONDARY_BTN_HOVER,
                corner_radius=9,
                command=btn_cmd,
            ).pack(side="right", padx=(6, 0))

        return status_lbl

    # ── Görünüm 4: Ayarlar ───────────────────────────────────────

    def _build_settings_view(self) -> None:
        self.settings_panel = SettingsPanel(
            self.stage,
            settings=self.settings,
            on_back_to_studio=lambda: self._switch_view("home"),
            on_shortcuts_changed=self._reload_shortcuts,
            on_feature_changed=self._on_feature_changed,
            on_theme_changed=self._apply_theme_mode,
            on_check_updates=lambda: self._on_check_updates(silent=False),
            on_install_update=self._on_install_update,
            on_api_key_updated=self._on_api_key_updated,
            on_recording_state_changed=self._on_shortcut_recording_changed,
            current_version=f"v{APP_VERSION}",
        )
        self._views["settings"] = self.settings_panel

    def _on_shortcut_recording_changed(self, recording: bool) -> None:
        if recording:
            self._global_hotkeys.stop()
        else:
            self._reload_shortcuts()

    def _on_api_key_updated(self, is_ready: bool) -> None:
        self._refresh_api_badge(is_ready)
        if is_ready:
            self.text_panel.set_status("Gemini API anahtarı doğrulandı ve kullanıma hazır.")

    # ── Güncelleme Sistemi (GitHub Releases) ─────────────────────

    def _maybe_auto_check_updates(self) -> None:
        if not self.settings.get_update_setting("auto_check", True):
            return
        repo = (self.settings.get_update_setting("github_repo", "") or "").strip()
        if repo:
            self._on_check_updates(silent=True)

    def _on_check_updates(self, silent: bool = False) -> None:
        repo = (self.settings.get_update_setting("github_repo", "") or "").strip()
        if not silent:
            self.settings_panel.set_update_checking()

        def task():
            res = check_for_updates(repo, current_version=APP_VERSION)
            self._last_update_result = res

            def apply_ui():
                if not silent or res.ok:
                    self.settings_panel.apply_update_result(res)
                if res.ok and res.update_available:
                    self.text_panel.set_status(
                        f"Yeni Sono sürümü hazır: {res.latest_version} (Ayarlar'dan kur)"
                    )

            self.after(0, apply_ui)

        threading.Thread(target=task, daemon=True).start()

    def _on_install_update(self) -> None:
        res = self._last_update_result
        if not res or not res.ok or not res.update_available:
            self.settings_panel.set_download_error("Önce 'Güncellemeleri denetle' ile yeni sürümü kontrol edin.")
            return

        if not res.download_url:
            import webbrowser

            if res.release_page_url and is_safe_github_url(res.release_page_url):
                webbrowser.open(res.release_page_url)
                self.settings_panel.set_download_error(
                    "Bu sürümde doğrudan indirilebilir .exe/.zip eki yok; GitHub Release sayfası tarayıcıda açıldı."
                )
            else:
                self.settings_panel.set_download_error(
                    "Geçerli bir GitHub Release indirme bağlantısı bulunamadı."
                )
            return

        def task():
            try:
                def on_prog(dl: int, tot: int):
                    self.after(0, lambda: self.settings_panel.set_download_progress(dl, tot))

                downloaded_path = download_update_file(
                    res.download_url, res.asset_name, on_progress=on_prog
                )

                def finish_and_restart():
                    launch_updater_and_exit(downloaded_path)
                    self.on_closing(force_quit=True)

                self.after(0, finish_and_restart)
            except Exception as e:
                err_msg = f"İndirme başarısız: {e}"
                self.after(0, lambda: self.settings_panel.set_download_error(err_msg))

        threading.Thread(target=task, daemon=True).start()

    def _switch_view(self, view_name: str, settings_tab: Optional[str] = None) -> None:
        self._active_view = view_name
        for v in self._views.values():
            v.grid_forget()

        if view_name in self._views:
            self._views[view_name].grid(row=0, column=0, sticky="nsew")

        if view_name == "library":
            self._refresh_library()
        elif view_name == "settings":
            self.settings_panel.select_tab(settings_tab or "shortcuts_features")

        # Üst başlık metni ve pencere başlığı
        v_title, v_sub = self.VIEW_META.get(view_name, ("Stüdyo", ""))
        self.view_title_lbl.configure(text=v_title)
        self.view_sub_lbl.configure(text=v_sub)

        title_map = {
            "home": "Sono",
            "library": "Kitaplık · Sono",
            "tools": "Araçlar · Sono",
            "settings": "Ayarlar · Sono",
        }
        self.title(title_map.get(view_name, "Sono"))

        for name, item in self._nav_items.items():
            btn = item["btn"]
            ind = item["indicator"]
            if name == view_name:
                ind.configure(fg_color=ACCENT_COLOR)
                btn.configure(
                    image=self._ic_rail[f"{name}_act"],
                    fg_color=RAIL_ITEM_ACTIVE,
                    border_width=1,
                    border_color=CARD_BORDER,
                    text_color=ACCENT_COLOR,
                )
            else:
                ind.configure(fg_color="transparent")
                btn.configure(
                    image=self._ic_rail[f"{name}_idle"],
                    fg_color="transparent",
                    border_width=0,
                    text_color=TEXT_MUTED,
                )

    # ── Kısayollar ────────────────────────────────────────────────

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-KeyPress-v>", self._on_paste)
        self.bind("<Control-KeyPress-V>", self._on_paste)
        self._reload_shortcuts()

    def _safe_bind_shortcut(self, keys_str: str, handler) -> None:
        for seq in shortcut_to_tk_sequences(keys_str):
            try:
                fid = self.bind(seq, handler, add="+")
                self._dynamic_shortcut_binds.append((seq, fid))
            except Exception as e:
                get_logger("app").warning("Kısayol bağlanamadı (%s -> %s): %s", keys_str, seq, e)

    def _reload_shortcuts(self) -> None:
        for seq, func_id in self._dynamic_shortcut_binds:
            try:
                self.unbind(seq, func_id)
            except Exception:
                pass
        self._dynamic_shortcut_binds.clear()
        self._global_hotkeys.stop()

        if not self.settings.is_shortcuts_enabled():
            return

        pp = self.settings.get_shortcut("play_pause")
        if pp.get("enabled") and pp.get("keys"):
            self._safe_bind_shortcut(pp["keys"], self._shortcut_play_pause)

        pn = self.settings.get_shortcut("prev_next_paragraph")
        if pn.get("enabled") and pn.get("keys"):
            if pn["keys"] == "Left/Right":
                fid_l = self.bind("<Left>", self._shortcut_prev_para, add="+")
                fid_r = self.bind("<Right>", self._shortcut_next_para, add="+")
                self._dynamic_shortcut_binds.append(("<Left>", fid_l))
                self._dynamic_shortcut_binds.append(("<Right>", fid_r))
            else:
                self._safe_bind_shortcut(pn["keys"], self._shortcut_next_para)

        ra = self.settings.get_shortcut("read_aloud")
        if ra.get("enabled") and ra.get("keys"):
            self._safe_bind_shortcut(ra["keys"], self._shortcut_read_aloud)

        global_list = []
        cap = self.settings.get_shortcut("capture_screen")
        if cap.get("enabled") and cap.get("keys"):
            global_list.append((cap["keys"], lambda: self.after(0, self._start_screen_capture)))
            self._safe_bind_shortcut(cap["keys"], self._shortcut_capture_screen)

        tog = self.settings.get_shortcut("toggle_window")
        if tog.get("enabled") and tog.get("keys"):
            global_list.append((tog["keys"], lambda: self.after(0, self._toggle_window_visibility)))

        if global_list:
            self._global_hotkeys.set_hotkeys(global_list)

    def _toggle_window_visibility(self) -> None:
        if hasattr(self, "settings_panel") and self.settings_panel.is_recording:
            return
        if self.state() == "withdrawn":
            self.deiconify()
            self.lift()
            self.focus_force()
        else:
            self.withdraw()

    # ── Ekran Bölgesi Yakalama ───────────────────────────────────

    def _start_screen_capture(self) -> None:
        if hasattr(self, "settings_panel") and self.settings_panel.is_recording:
            return
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        self._was_visible_before_capture = self.state() != "withdrawn"
        if self._was_visible_before_capture:
            self.withdraw()
        self.after(200, self._open_capture_overlay)

    def _open_capture_overlay(self) -> None:
        try:
            ScreenCaptureWindow(
                self,
                on_captured=self._on_screen_captured,
                on_cancel=self._on_screen_capture_cancelled,
            )
        except Exception as e:
            self._capture_in_progress = False
            self.deiconify()
            self.text_panel.set_status(f"❌ Ekran yakalama başlatılamadı: {e}")

    def _on_screen_capture_cancelled(self) -> None:
        self._capture_in_progress = False
        if getattr(self, "_was_visible_before_capture", True):
            self.deiconify()
            self.lift()

    def _on_screen_captured(self, cropped_image: Image.Image) -> None:
        self._capture_in_progress = False
        self.deiconify()
        self.lift()
        self.focus_force()
        self._switch_view("home")

        self._current_image = cropped_image
        self.image_panel.set_image_preview(cropped_image)
        self._run_ocr(cropped_image, auto_read=True, history_title="Ekran Yakalama")

    def _is_typing_in_input(self) -> bool:
        focused = self.focus_get()
        return bool(focused and focused.winfo_class() in ("Text", "Entry", "TEntry"))

    def _shortcut_play_pause(self, _event=None) -> None:
        if self._active_view == "settings" or self._is_typing_in_input():
            return
        if self.tts_service.is_playing or self.tts_service.is_paused:
            self.audio_panel._toggle_pause()

    def _shortcut_prev_para(self, _event=None) -> None:
        if self._active_view == "settings" or self._is_typing_in_input():
            return
        if self.tts_service.is_playing or self.tts_service.is_paused:
            self.audio_panel._prev_paragraph()

    def _shortcut_next_para(self, _event=None) -> None:
        if self._active_view == "settings" or self._is_typing_in_input():
            return
        if self.tts_service.is_playing or self.tts_service.is_paused:
            self.audio_panel._next_paragraph()

    def _shortcut_capture_screen(self, _event=None) -> None:
        if (
            self._active_view == "settings"
            or self._is_typing_in_input()
            or (hasattr(self, "settings_panel") and self.settings_panel.is_recording)
        ):
            return
        self._start_screen_capture()

    def _shortcut_read_aloud(self, _event=None) -> None:
        if self._active_view == "settings":
            return
        self._switch_view("home")
        self.text_panel._handle_read()

    def _on_paste(self, _event) -> None:
        if self._active_view == "settings" or self._is_typing_in_input():
            return
        self._switch_view("home")
        self.image_panel.paste_from_clipboard()

    # ── Canlı Tema Geçişi (Koyu <-> Açık) ────────────────────────

    def _apply_theme_mode(self, mode: str) -> None:
        mode = "light" if str(mode).lower() == "light" else "dark"
        ctk.set_appearance_mode(mode)
        self._current_theme = mode
        if hasattr(self, "theme_btn"):
            is_dark = mode == "dark"
            self.theme_btn.configure(
                image=self._ic_rail["sun"] if is_dark else self._ic_rail["moon"],
                text="Açık" if is_dark else "Koyu",
            )
        if hasattr(self, "settings_panel") and hasattr(self.settings_panel, "sync_theme_selection"):
            self.settings_panel.sync_theme_selection(mode)
        notify_theme_changed(mode)

    def _toggle_theme(self) -> None:
        new_mode = "light" if self._current_theme == "dark" else "dark"
        self.settings.set_general("theme", new_mode)
        self._apply_theme_mode(new_mode)

    def _load_from_history(self, item: dict) -> None:
        text = item.get("text_content") or ""
        translation = item.get("translation_content") or ""
        self._active_history_id = item.get("id")
        last_p = int(item.get("last_paragraph") or 0)

        self.text_panel.set_ocr_text(text)
        if translation:
            self.text_panel.set_translation_text(translation)

        if self.settings.get_feature("resume_last_position") and last_p > 0:
            self._active_resume_paragraph = last_p
            paras = split_into_paragraphs(text)
            if last_p < len(paras):
                self.text_panel.highlight_paragraph(last_p, paras)
                self.text_panel.set_status(
                    f"Belge kitaplıktan yüklendi · Paragraf {last_p + 1}/{len(paras)}'den devam edebilirsin."
                )
            else:
                self._active_resume_paragraph = 0
                self.text_panel.set_status("Belge kitaplıktan yüklendi.")
        else:
            self._active_resume_paragraph = 0
            self.text_panel.set_status("Belge kitaplıktan yüklendi.")

        self._switch_view("home")

    # ── Belge ve OCR Olayları ─────────────────────────────────────

    def _on_image_loaded(self, image: Image.Image) -> None:
        self._current_image = image
        self._run_ocr(image)

    def _on_document_loaded(self, title: str, text: str) -> None:
        self.text_panel.set_ocr_text(text)
        self.text_panel.set_status(f"{title} yüklendi.")
        self._active_resume_paragraph = 0
        self._active_history_id = add_history_entry(title=title, text=text, source_type="Belge")

    def _run_ocr(
        self,
        image: Image.Image,
        auto_read: bool = False,
        history_title: str = "Görsel OCR",
    ) -> None:
        self._refresh_api_badge(busy=True)
        self.image_panel.set_ocr_scanning(True)
        self.text_panel.set_status("⏳ Gemini ile metin okunuyor…")
        self.text_panel.set_progress(0.4)
        self.text_panel.ocr_textbox.delete("1.0", "end")
        self.text_panel.ocr_textbox.insert(
            "1.0", "Görsel analiz ediliyor ve metin çıkarılıyor…\nLütfen bekleyin."
        )
        self.text_panel.translate_btn.configure(state="disabled")
        self.text_panel.read_btn.configure(state="disabled")

        def task():
            try:
                def on_retry(wait_s: float, attempt: int):
                    self.after(
                        0,
                        lambda w=int(wait_s), a=attempt: self.text_panel.set_status(
                            f"⏳ Gemini limitine takıldı, {w} sn sonra yeniden deneniyor ({a})…"
                        ),
                    )

                text = extract_text_from_image(image, on_retry=on_retry)
                text = clean_text(text)
                self.after(
                    0,
                    lambda: self._on_ocr_complete(text, auto_read=auto_read, history_title=history_title),
                )
            except Exception as e:
                err_text = str(e)
                self.after(0, lambda: self.image_panel.set_ocr_scanning(False))
                self.after(0, lambda: self._refresh_api_badge())
                self.after(0, lambda: self.text_panel.set_status("❌ OCR başarısız"))
                self.after(0, lambda: self.text_panel.set_progress(0))
                self.after(
                    0,
                    lambda: self.text_panel.set_ocr_text(
                        f"Görseldeki metin okunamadı.\n\nDetay:\n{err_text}"
                    ),
                )
                self.after(0, lambda: self.text_panel.translate_btn.configure(state="normal"))
                self.after(0, lambda: self.text_panel.read_btn.configure(state="normal"))
                self.after(0, lambda msg=err_text: self._maybe_prompt_invalid_key(msg))

        threading.Thread(target=task, daemon=True).start()

    def _on_ocr_complete(
        self,
        text: str,
        auto_read: bool = False,
        history_title: str = "Görsel OCR",
    ) -> None:
        self.image_panel.set_ocr_scanning(False)
        self._refresh_api_badge()
        self.text_panel.set_ocr_text(text)
        self.text_panel.set_status("Metin başarıyla çıkarıldı.")
        self.text_panel.set_progress(1.0)
        self.text_panel.translate_btn.configure(state="normal")
        self.text_panel.read_btn.configure(state="normal")
        self.after(1200, lambda: self.text_panel.set_progress(0))
        self._active_resume_paragraph = 0
        self._active_history_id = add_history_entry(title=history_title, text=text, source_type="Görsel")
        if auto_read and text.strip():
            self._on_read_clicked(text)

    # ── Çeviri İşlemleri ──────────────────────────────────────────

    def _on_translate_clicked(self, target_lang: str) -> None:
        text = self.text_panel.get_active_text()
        if not text:
            return

        self._refresh_api_badge(busy=True)
        self.text_panel.set_status(f"⏳ {target_lang} diline çevriliyor…")
        self.text_panel.set_progress(0.5)
        self.text_panel.translate_btn.configure(state="disabled")

        def task():
            try:
                def on_retry(wait_s: float, attempt: int):
                    self.after(
                        0,
                        lambda w=int(wait_s), a=attempt: self.text_panel.set_status(
                            f"⏳ Gemini limitine takıldı, {w} sn sonra yeniden deneniyor ({a})…"
                        ),
                    )

                result = detect_and_translate(text, target_language=target_lang, on_retry=on_retry)
                self.after(0, lambda: self._on_translate_complete(result, text))
            except Exception as e:
                err_text = str(e)
                self.after(0, lambda: self._refresh_api_badge())
                self.after(0, lambda: self.text_panel.set_status(f"❌ Çeviri hatası: {err_text[:80]}"))
                self.after(0, lambda: self.text_panel.set_progress(0))
                self.after(0, lambda: self.text_panel.translate_btn.configure(state="normal"))
                self.after(0, lambda msg=err_text: self._maybe_prompt_invalid_key(msg))

        threading.Thread(target=task, daemon=True).start()

    def _on_translate_complete(self, result: dict, orig_text: str) -> None:
        self._refresh_api_badge()
        self.text_panel.set_translation_text(
            result["translation"],
            source_lang=result.get("source_language", ""),
            target_lang=result.get("target_language", ""),
        )
        self.text_panel.set_status(
            f"Çevrildi — {result['source_language']} → {result['target_language']}"
        )
        self.text_panel.set_progress(1.0)
        self.text_panel.translate_btn.configure(state="normal")
        self.after(1200, lambda: self.text_panel.set_progress(0))

        add_history_entry(
            title=f"Çeviri ({result['target_language']})",
            text=orig_text,
            translation=result["translation"],
            source_type="Çeviri",
        )

    # ── AI Akıllı Araçları ────────────────────────────────────────

    def _on_summarize_clicked(self) -> None:
        text = self.text_panel.get_active_text()
        if not text:
            self.text_panel.set_status("⚠️ Özet için metin bulunamadı.")
            return

        self._refresh_api_badge(busy=True)
        self.text_panel.set_status("⏳ Gemini ile özet çıkarılıyor…")
        self.text_panel.set_progress(0.5)
        self.text_panel.summary_btn.configure(state="disabled")

        def task():
            try:
                summary = summarize_text(text)
                self.after(0, lambda: self.text_panel.set_summary_text(summary))
                self.after(0, lambda: self.text_panel.set_status("Özet başarıyla çıkarıldı."))
                self.after(0, lambda: self.text_panel.set_progress(1.0))
                self.after(1200, lambda: self.text_panel.set_progress(0))
            except Exception as e:
                err_text = str(e)
                self.after(0, lambda: self.text_panel.set_status(f"❌ Özet hatası: {err_text}"))
                self.after(0, lambda: self.text_panel.set_progress(0))
            finally:
                self.after(0, lambda: self._refresh_api_badge())
                self.after(0, lambda: self.text_panel.summary_btn.configure(state="normal"))

        threading.Thread(target=task, daemon=True).start()

    def _on_enhance_clicked(self) -> None:
        text = self.text_panel.get_active_text()
        if not text:
            self.text_panel.set_status("⚠️ Düzeltilecek metin yok.")
            return

        self._refresh_api_badge(busy=True)
        self.text_panel.set_status("⏳ İmla ve OCR hataları düzeltiliyor…")
        self.text_panel.set_progress(0.5)
        self.text_panel.enhance_btn.configure(state="disabled")

        def task():
            try:
                enhanced = fix_and_enhance_text(text)
                self.after(0, lambda: self.text_panel.set_ocr_text(enhanced))
                self.after(0, lambda: self.text_panel.set_status("Metin ve imla düzeltildi."))
                self.after(0, lambda: self.text_panel.set_progress(1.0))
                self.after(1200, lambda: self.text_panel.set_progress(0))
            except Exception as e:
                err_text = str(e)
                self.after(0, lambda: self.text_panel.set_status(f"❌ Düzeltme hatası: {err_text}"))
                self.after(0, lambda: self.text_panel.set_progress(0))
            finally:
                self.after(0, lambda: self._refresh_api_badge())
                self.after(0, lambda: self.text_panel.enhance_btn.configure(state="normal"))

        threading.Thread(target=task, daemon=True).start()

    def _on_ask_question_clicked(self, question: str) -> None:
        doc_text = self.text_panel.get_ocr_text()
        if not doc_text:
            self.text_panel.set_status("⚠️ Önce bir belge yükleyin.")
            return

        self._refresh_api_badge(busy=True)
        self.text_panel.set_status(f"⏳ '{question}' sorusu yanıtlanıyor…")
        self.text_panel.set_progress(0.5)

        def task():
            try:
                answer = ask_document_question(doc_text, question)
                self.after(0, lambda: self.text_panel.append_qa_answer(question, answer))
                self.after(0, lambda: self.text_panel.set_status("Yanıt oluşturuldu."))
                self.after(0, lambda: self.text_panel.set_progress(1.0))
                self.after(1200, lambda: self.text_panel.set_progress(0))
            except Exception as e:
                err_text = str(e)
                self.after(0, lambda: self.text_panel.set_status(f"❌ Soru hatası: {err_text}"))
                self.after(0, lambda: self.text_panel.set_progress(0))
            finally:
                self.after(0, lambda: self._refresh_api_badge())

        threading.Thread(target=task, daemon=True).start()

    # ── Toplu İşleme ve Uyku Zamanlayıcısı ───────────────────────

    def _pick_multiple_files(self) -> list[str]:
        paths = filedialog.askopenfilenames(
            title="Birden Fazla Belge veya Görsel Seç",
            filetypes=[
                ("Tüm Desteklenen Dosyalar", "*.pdf *.pptx *.docx *.txt *.png *.jpg *.jpeg *.webp *.bmp"),
                ("Belgeler", "*.pdf *.pptx *.docx *.txt"),
                ("Görseller", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("Tüm Dosyalar", "*.*"),
            ],
        )
        return list(paths) if paths else []

    def _start_batch_read(self) -> None:
        files = self._pick_multiple_files()
        if not files:
            return

        self._batch_status_lbl.configure(
            text=f"İşleniyor (0/{len(files)})…", text_color=ACCENT_SOFT_TEXT, fg_color=ACCENT_SOFT_BG
        )
        self.text_panel.set_status(f"⏳ {len(files)} dosya sırayla okunuyor…")

        def task():
            def on_prog(idx, total, fname):
                self.after(
                    0,
                    lambda i=idx, t=total, n=fname: self._batch_status_lbl.configure(
                        text=f"{i}/{t}: {n[:22]}"
                    ),
                )

            combined, errors = process_files_to_combined_text(files, on_progress=on_prog)

            def finish():
                if not combined.strip():
                    self._batch_status_lbl.configure(
                        text="Metin çıkarılamadı", text_color=STOP_BTN_TEXT, fg_color=STOP_BTN_BG
                    )
                    self.text_panel.set_status("❌ Seçilen dosyalardan metin çıkarılamadı.")
                    return

                self._batch_status_lbl.configure(
                    text=f"Tamamlandı ({len(files)} dosya)",
                    text_color=SUCCESS_COLOR,
                    fg_color=STATUS_PILL_BG,
                )
                self._switch_view("home")
                self.text_panel.set_ocr_text(combined)
                self._active_resume_paragraph = 0
                self._active_history_id = add_history_entry(
                    title=f"Toplu Okuma ({len(files)} dosya)",
                    text=combined,
                    source_type="Toplu",
                )
                if errors:
                    self.text_panel.set_status(
                        f"⚠️ {len(files) - len(errors)}/{len(files)} dosya okundu, seslendirme başlıyor."
                    )
                self._on_read_clicked(combined)

            self.after(0, finish)

        threading.Thread(target=task, daemon=True).start()

    def _start_batch_mp3(self) -> None:
        files = self._pick_multiple_files()
        if not files:
            return

        initial_dir = self.settings.get_general("export_dir", "") or None
        output_path = filedialog.asksaveasfilename(
            title="Birleştirilmiş MP3 Dosyasını Kaydet",
            defaultextension=".mp3",
            initialdir=initial_dir,
            initialfile="Sono_Toplu_Sesli_Kitap.mp3",
            filetypes=[("MP3 Ses Dosyası", "*.mp3")],
        )
        if not output_path:
            return

        self._batch_status_lbl.configure(
            text=f"Metinler çıkarılıyor (0/{len(files)})…",
            text_color=ACCENT_SOFT_TEXT,
            fg_color=ACCENT_SOFT_BG,
        )
        self.text_panel.set_status(f"⏳ {len(files)} dosya tek MP3 olarak hazırlanıyor…")

        def task():
            try:
                def on_file_prog(idx, total, fname):
                    self.after(
                        0,
                        lambda i=idx, t=total, n=fname: self._batch_status_lbl.configure(
                            text=f"Okunuyor {i}/{t}: {n[:18]}"
                        ),
                    )

                combined, _ = process_files_to_combined_text(files, on_progress=on_file_prog)
                if not combined.strip():
                    raise ValueError("Seçilen dosyalardan metin çıkarılamadı.")

                def on_mp3_prog(idx, total):
                    self.after(
                        0,
                        lambda i=idx, t=total: self._batch_status_lbl.configure(
                            text=f"MP3 birleştiriliyor ({i}/{t})…"
                        ),
                    )

                export_combined_text_to_single_mp3(
                    self.tts_service, combined, output_path, on_chunk_progress=on_mp3_prog
                )

                def on_done():
                    self._batch_status_lbl.configure(
                        text="MP3 hazır", text_color=SUCCESS_COLOR, fg_color=STATUS_PILL_BG
                    )
                    self.text_panel.set_status(f"Toplu MP3 kaydedildi: {output_path}")

                self.after(0, on_done)
            except Exception as e:
                err_msg = str(e)
                self.after(
                    0,
                    lambda: (
                        self._batch_status_lbl.configure(
                            text="Hata oluştu", text_color=STOP_BTN_TEXT, fg_color=STOP_BTN_BG
                        ),
                        self.text_panel.set_status(f"❌ Toplu MP3 hatası: {err_msg}"),
                    ),
                )

        threading.Thread(target=task, daemon=True).start()

    def _start_sleep_timer(self, minutes: int) -> None:
        self._start_sleep_timer_seconds(max(1, int(minutes) * 60))

    def _start_sleep_timer_seconds(self, seconds: int) -> None:
        self._cancel_sleep_timer(silent=True)
        sec = max(1, int(seconds))
        if self.tts_service.is_playing or self.tts_service.is_paused:
            self._sleep_armed_sec = 0
            self._sleep_remaining_sec = sec
            self._tick_sleep_timer()
        else:
            self._sleep_armed_sec = sec
            mins, rem = divmod(sec, 60)
            self._sleep_status_lbl.configure(
                text=f"Hazır ({mins:02d}:{rem:02d} · okuma başlayınca)",
                text_color=ACCENT_SOFT_TEXT,
                fg_color=ACCENT_SOFT_BG,
            )
            self.audio_panel.set_sleep_badge(f"{mins:02d}:{rem:02d} (hazır)", active=False)
            self.text_panel.set_status(
                f"🌙 Uyku zamanlayıcısı hazır: Sesli okuma başlayınca {mins:02d}:{rem:02d} sonra duracak."
            )

    def _activate_armed_sleep_timer(self) -> None:
        if self._sleep_armed_sec > 0:
            sec = self._sleep_armed_sec
            self._sleep_armed_sec = 0
            self._sleep_remaining_sec = sec
            self._tick_sleep_timer()

    def _tick_sleep_timer(self) -> None:
        if self._sleep_remaining_sec <= 0:
            self._sleep_after_id = None
            self._sleep_status_lbl.configure(
                text="Kapalı", text_color=ACCENT_SOFT_TEXT, fg_color=ACCENT_SOFT_BG
            )
            self.audio_panel.set_sleep_badge("")
            if self.tts_service.is_playing or self.tts_service.is_paused:
                self.audio_panel._stop()
            self.text_panel.set_status("Uyku zamanlayıcısı tamamlandı, sesli okuma durduruldu.")
            return

        mins, secs = divmod(self._sleep_remaining_sec, 60)
        self._sleep_status_lbl.configure(
            text=f"Kalan: {mins:02d}:{secs:02d}",
            text_color=SUCCESS_COLOR,
            fg_color=STATUS_PILL_BG,
        )
        self.audio_panel.set_sleep_badge(f"{mins:02d}:{secs:02d}", active=True)
        self._sleep_remaining_sec -= 1
        self._sleep_after_id = self.after(1000, self._tick_sleep_timer)

    def _cancel_sleep_timer(self, silent: bool = False) -> None:
        if self._sleep_after_id is not None:
            try:
                self.after_cancel(self._sleep_after_id)
            except Exception:
                pass
            self._sleep_after_id = None
        self._sleep_remaining_sec = 0
        self._sleep_armed_sec = 0
        if hasattr(self, "_sleep_status_lbl"):
            self._sleep_status_lbl.configure(
                text="Kapalı", text_color=ACCENT_SOFT_TEXT, fg_color=ACCENT_SOFT_BG
            )
        if hasattr(self, "audio_panel"):
            self.audio_panel.set_sleep_badge("")
        if not silent:
            self.text_panel.set_status("Uyku zamanlayıcısı iptal edildi.")

    def _on_playback_stopped(self) -> None:
        self._playback_gen += 1
        self.text_panel.clear_highlight()

    def _on_jump_to_offset(self, char_offset: int) -> None:
        if not (self.tts_service.is_playing or self.tts_service.is_paused):
            return
        raw_full = self.text_panel._get_active_textbox()._textbox.get("1.0", "end-1c")
        if not raw_full or char_offset < 0 or char_offset >= len(raw_full):
            return

        start_pos = char_offset
        if raw_full[start_pos].isspace():
            while start_pos < len(raw_full) and raw_full[start_pos].isspace():
                start_pos += 1
        else:
            while start_pos > 0 and not raw_full[start_pos - 1].isspace():
                start_pos -= 1

        remaining = raw_full[start_pos:].strip()
        if remaining:
            self._on_read_clicked(remaining, mode="cursor", base_offset=start_pos)

    def _init_tray_and_clipboard(self) -> None:
        if self.settings.get_feature("minimize_to_tray"):
            self._tray_service.start()
        if self.settings.get_feature("clipboard_monitor"):
            self._start_clipboard_polling()

    def _start_clipboard_polling(self) -> None:
        if self._clipboard_after_id is not None:
            return
        self._last_clipboard_text = self._safe_get_clipboard_text()
        self._clipboard_after_id = self.after(700, self._poll_clipboard)

    def _stop_clipboard_polling(self) -> None:
        if self._clipboard_after_id is not None:
            try:
                self.after_cancel(self._clipboard_after_id)
            except Exception:
                pass
            self._clipboard_after_id = None

    def _safe_get_clipboard_text(self) -> str:
        try:
            txt = self.clipboard_get()
            return txt.strip() if isinstance(txt, str) else ""
        except Exception:
            return ""

    @staticmethod
    def _looks_like_sensitive_secret(text: str) -> bool:
        """Panoya kopyalanan API anahtarı, token, özel anahtar veya parolaları filtreler."""
        import re

        s = (text or "").strip()
        if not s:
            return True
        if "-----BEGIN " in s and "KEY-----" in s:
            return True
        if re.search(
            r"(?:^|\b)(?:AIza[0-9A-Za-z_\-]{20,}|AQ\.[0-9A-Za-z_\-\.]{16,}|sk-[0-9A-Za-z_\-]{16,}|ghp_[0-9A-Za-z]{20,}|github_pat_[0-9A-Za-z_]{20,}|xox[baprs]-[0-9A-Za-z\-]{10,}|eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,})",
            s,
        ):
            return True
        if re.match(r"^(?:GEMINI_API_KEY|API_KEY|SECRET|TOKEN|PASSWORD)\s*=", s, flags=re.IGNORECASE):
            return True
        # Boşluksuz, tek parça ve karmaşık parola/token benzeri uzun dize (URL değilse)
        if not any(ch.isspace() for ch in s) and len(s) >= 16 and not s.lower().startswith(("http://", "https://")):
            has_digit = any(c.isdigit() for c in s)
            has_upper = any(c.isupper() for c in s)
            has_lower = any(c.islower() for c in s)
            has_sym = any(not c.isalnum() for c in s)
            if (has_digit + has_upper + has_lower + has_sym) >= 3:
                return True
        return False

    def _poll_clipboard(self) -> None:
        self._clipboard_after_id = None
        if not self.settings.get_feature("clipboard_monitor"):
            return
        try:
            current = self._safe_get_clipboard_text()
            if current and len(current) >= 12 and current != self._last_clipboard_text:
                self._last_clipboard_text = current
                if not self._looks_like_sensitive_secret(current):
                    self._show_clipboard_prompt(current)
        except Exception:
            pass
        if self.settings.get_feature("clipboard_monitor"):
            self._clipboard_after_id = self.after(700, self._poll_clipboard)

    def _show_clipboard_prompt(self, text: str) -> None:
        if self._active_clipboard_prompt is not None:
            try:
                self._active_clipboard_prompt.destroy()
            except Exception:
                pass
            self._active_clipboard_prompt = None

        def _accept_read():
            self._active_clipboard_prompt = None
            self._restore_from_tray()
            self._switch_view("home")
            self.text_panel.set_ocr_text(text)
            self._active_resume_paragraph = 0
            self._active_history_id = add_history_entry(
                title="Pano Metni", text=text, source_type="Pano"
            )
            self._on_read_clicked(text)

        def _dismiss():
            self._active_clipboard_prompt = None

        self._active_clipboard_prompt = ClipboardPromptWindow(
            self,
            text_preview=text,
            on_read=_accept_read,
            on_dismiss=_dismiss,
        )

    def _minimize_to_tray_now(self) -> None:
        if self._tray_service.is_available:
            self._tray_service.start()
            self.withdraw()
        else:
            self.iconify()

    def _restore_from_tray(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_feature_changed(self, key: str, value: bool) -> None:
        if key == "highlight_sentence" and not value:
            self.text_panel.clear_highlight()
        elif key == "minimize_to_tray":
            if value:
                self._tray_service.start()
            else:
                self._tray_service.stop()
        elif key == "clipboard_monitor":
            if value:
                self._start_clipboard_polling()
            else:
                self._stop_clipboard_polling()
        elif key == "reduced_motion":
            set_reduced_motion(value)
            notify_theme_changed(self._current_theme)

    def _on_read_clicked(
        self, text: str, mode: str = "full", base_offset: Optional[int] = None
    ) -> None:
        if base_offset is None:
            raw_full = self.text_panel._get_active_textbox()._textbox.get("1.0", "end-1c")
            found = raw_full.find(text)
            base_offset = found if found != -1 else 0

        para_spans = split_paragraphs_with_spans(text, base_offset=base_offset)
        if not para_spans:
            return
        paragraphs = [p for p, _, _ in para_spans]
        read_start_pos = base_offset if mode == "selection" else 0

        start_idx = 0
        if (
            mode == "full"
            and self.settings.get_feature("resume_last_position")
            and 0 < self._active_resume_paragraph < len(paragraphs)
        ):
            start_idx = self._active_resume_paragraph
        self._active_resume_paragraph = 0
        active_hist_id = self._active_history_id if mode == "full" else None

        self._playback_gen += 1
        session_gen = self._playback_gen

        self._activate_armed_sleep_timer()

        def on_para_change(index: int) -> None:
            if active_hist_id and self.settings.get_feature("resume_last_position"):
                update_history_progress(active_hist_id, index, len(paragraphs))

            def _ui_para():
                if session_gen != self._playback_gen:
                    return
                self.audio_panel.update_progress(index, len(paragraphs))

            self.after(0, _ui_para)

        def on_word_change(para_idx: int, rel_start: int, rel_end: int) -> None:
            if not self.settings.get_feature("highlight_sentence"):
                return
            if para_idx < 0 or para_idx >= len(para_spans):
                return
            _, p_start, p_end = para_spans[para_idx]
            abs_start = p_start + max(0, rel_start)
            abs_end = min(p_end, p_start + max(rel_start + 1, rel_end))

            def _ui_word():
                if session_gen != self._playback_gen:
                    return
                self.text_panel.highlight_word_span_abs(
                    abs_start, abs_end, read_start_pos=read_start_pos
                )

            self.after(0, _ui_word)

        def on_time_tick(elapsed_sec: int, total_sec: int, pct: float) -> None:
            def _ui_tick():
                if session_gen != self._playback_gen:
                    return
                self.audio_panel.update_time(elapsed_sec, total_sec, pct)

            self.after(0, _ui_tick)

        def on_complete() -> None:
            if active_hist_id:
                update_history_progress(active_hist_id, 0, len(paragraphs))

            def _ui_done():
                if session_gen != self._playback_gen:
                    return
                self.text_panel.set_status("Sesli okuma tamamlandı.")
                self.audio_panel.on_playback_complete()
                self.text_panel.clear_highlight()

            self.after(0, _ui_done)

        self.audio_panel.update_progress(start_idx, len(paragraphs))
        if mode == "selection":
            self.text_panel.set_status("🔊 Seçili metin okunuyor…")
        elif mode == "cursor":
            self.text_panel.set_status("🔊 Tıklanan kelimeden devam ediyor…")
        elif start_idx > 0:
            self.text_panel.set_status(
                f"🔊 Kaldığı yerden devam ediyor (Paragraf {start_idx + 1}/{len(paragraphs)})…"
            )
        else:
            self.text_panel.set_status(f"🔊 Sesli okuma başladı ({len(paragraphs)} paragraf)…")
        self.tts_service.play_paragraphs(
            paragraphs,
            start_index=start_idx,
            on_paragraph_change=on_para_change,
            on_word_change=on_word_change,
            on_time_tick=on_time_tick,
            on_complete=on_complete,
        )

    def _on_export_mp3_clicked(self, output_path: str) -> None:
        text = self.text_panel.get_active_text()
        if not text:
            return

        self.text_panel.set_status("⏳ MP3 dosyası oluşturuluyor…")
        self.text_panel.set_progress(0.5)

        def task():
            try:
                self.tts_service.export_to_mp3(text, output_path)
                self.after(0, lambda: self.text_panel.set_status(f"MP3 kaydedildi: {output_path}"))
                self.after(0, lambda: self.text_panel.set_progress(1.0))
                self.after(1500, lambda: self.text_panel.set_progress(0))
            except Exception as e:
                err_text = str(e)
                self.after(0, lambda: self.text_panel.set_status(f"❌ MP3 hatası: {err_text}"))
                self.after(0, lambda: self.text_panel.set_progress(0))

        threading.Thread(target=task, daemon=True).start()

    def on_closing(self, force_quit: bool = False) -> None:
        if (
            not force_quit
            and self.settings.get_feature("minimize_to_tray")
            and self._tray_service.is_available
        ):
            self._tray_service.start()
            self.withdraw()
            return

        self._stop_clipboard_polling()
        if self._lib_search_after_id is not None:
            try:
                self.after_cancel(self._lib_search_after_id)
            except Exception:
                pass
            self._lib_search_after_id = None

        if self._sleep_after_id is not None:
            try:
                self.after_cancel(self._sleep_after_id)
            except Exception:
                pass
            self._sleep_after_id = None

        if self._active_clipboard_prompt is not None:
            try:
                self._active_clipboard_prompt.destroy()
            except Exception:
                pass
            self._active_clipboard_prompt = None

        self._tray_service.stop()
        self._global_hotkeys.stop()
        self.tts_service.shutdown()
        self.destroy()
