"""
Sono Metin Stüdyosu Paneli (TextPanel).
- Kayan göstergeli 200ms sekme şeridi (Metin · Çeviri · Özet · Soru-Cevap)
- Lucide ikonlu sade araç çubuğu + Kopyala onay dönüşümü (copy -> check)
- Üst kenara entegre canlı Akustik İlerleme/Parıltı Şeridi (AcousticProgressRibbon)
- Çift temalı editoryal okuma tipografisi + 3 katmanlı canlı kelime vurgusu
"""

from __future__ import annotations

import re
from tkinter import filedialog
from typing import Callable, Optional
import customtkinter as ctk

from services.export_service import (
    detect_language_local,
    export_to_docx,
    export_to_markdown,
    export_to_pdf,
)
from ui.animations import AcousticProgressRibbon, SlidingTabBar
from ui.icons import get_icon
from ui.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    ACCENT_SOFT_BG,
    ACCENT_SOFT_BORDER,
    ACCENT_SOFT_TEXT,
    ACCENT_TEXT,
    BTN_HEIGHT_MAIN,
    CARD_BG,
    CARD_BORDER,
    DIVIDER_COLOR,
    FONT_FAMILY,
    HL_ACTIVE_BG,
    HL_ACTIVE_FG,
    HL_DONE_FG,
    HL_UNREAD_FG,
    INNER_BG,
    PADDING_CARD,
    PRIMARY_BTN_BG,
    PRIMARY_BTN_HOVER,
    PRIMARY_BTN_TEXT,
    RADIUS_BTN,
    RADIUS_CARD,
    RADIUS_INNER,
    SECONDARY_BTN,
    SECONDARY_BTN_BORDER,
    SECONDARY_BTN_HOVER,
    STOP_BTN_HOVER,
    STOP_BTN_TEXT,
    SUCCESS_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
    WARN_COLOR,
    mono_font,
    register_theme_listener,
    resolve_color,
    ui_font,
    unregister_theme_listener,
)
from utils.text_utils import get_text_stats

_EMOJI_PREFIX_RE = re.compile(r"^[\s✓✅❌⚠️⏳🔊🎵🌙❓💡•●]+")


class TextPanel(ctk.CTkFrame):
    """Editoryal Metin Stüdyosu Kartı."""

    AVAILABLE_LANGUAGES = [
        "Türkçe",
        "İngilizce",
        "Almanca",
        "Fransızca",
        "İspanyolca",
        "İtalyanca",
        "Rusça",
        "Arapça",
        "Japonca",
    ]

    def __init__(
        self,
        master,
        on_translate: Callable[[str], None],
        on_read: Callable[[str], None],
        on_export_mp3: Callable[[str], None],
        on_summarize: Optional[Callable[[], None]] = None,
        on_enhance: Optional[Callable[[], None]] = None,
        on_ask_question: Optional[Callable[[str], None]] = None,
        on_jump_to_offset: Optional[Callable[[int], None]] = None,
        settings=None,
        **kwargs,
    ):
        super().__init__(
            master,
            corner_radius=RADIUS_CARD,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
            **kwargs,
        )
        self._on_translate = on_translate
        self._on_read = on_read
        self._on_export_mp3 = on_export_mp3
        self._on_summarize = on_summarize
        self._on_enhance = on_enhance
        self._on_ask_question = on_ask_question
        self._on_jump_to_offset = on_jump_to_offset
        self.settings = settings

        saved_font = 14
        saved_lang = "Türkçe"
        saved_side_by_side = False
        if self.settings:
            try:
                f_val = int(self.settings.get_studio("font_size", 14))
                saved_font = max(10, min(28, f_val))
            except (TypeError, ValueError):
                saved_font = 14
            l_val = self.settings.get_studio("target_lang", "Türkçe")
            if l_val in self.AVAILABLE_LANGUAGES:
                saved_lang = l_val
            saved_side_by_side = bool(self.settings.get_studio("side_by_side", False))

        self._font_size = saved_font
        self._active_tab = "Metin"
        self._side_by_side = False
        self._detected_lang = "Otomatik"
        self._last_target_lang = saved_lang
        self._copy_reset_after: Optional[str] = None
        self._last_hl_state: Optional[tuple] = None

        self._setup_ui()
        if saved_side_by_side:
            self._set_side_by_side(True, save=False)
        register_theme_listener(self._on_theme_change)
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _setup_ui(self) -> None:
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Başlık + Yazı Boyutu Kontrolü ──
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=PADDING_CARD, pady=(PADDING_CARD, 8), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="Metin",
            font=ui_font(14, "semibold"),
            text_color=TEXT_MAIN,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        # Kompakt font boyut kontrolü: [ A- | 14 | A+ ]
        font_pill = ctk.CTkFrame(
            header_frame,
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            corner_radius=8,
        )
        font_pill.grid(row=0, column=1, sticky="e")

        self.btn_font_dec = ctk.CTkButton(
            font_pill,
            text="A-",
            width=32,
            height=24,
            font=ui_font(11, "semibold"),
            command=self._decrease_font,
            fg_color="transparent",
            hover_color=SECONDARY_BTN_HOVER,
            text_color=TEXT_MAIN,
            corner_radius=6,
        )
        self.btn_font_dec.pack(side="left", padx=(2, 0), pady=2)

        self.font_size_lbl = ctk.CTkLabel(
            font_pill,
            text=f"{self._font_size}",
            width=24,
            font=mono_font(11, "bold"),
            text_color=TEXT_MUTED,
        )
        self.font_size_lbl.pack(side="left")

        self.btn_font_inc = ctk.CTkButton(
            font_pill,
            text="A+",
            width=32,
            height=24,
            font=ui_font(11, "semibold"),
            command=self._increase_font,
            fg_color="transparent",
            hover_color=SECONDARY_BTN_HOVER,
            text_color=TEXT_MAIN,
            corner_radius=6,
        )
        self.btn_font_inc.pack(side="left", padx=(0, 2), pady=2)

        # ── 2. Kayan Göstergeli Sekme Şeridi ──
        self.tab_bar = SlidingTabBar(
            self,
            tabs=["Metin", "Çeviri", "Özet", "Soru-Cevap"],
            on_change=self._switch_tab,
            initial="Metin",
            bg_token=CARD_BG,
        )
        self.tab_bar.grid(row=1, column=0, padx=PADDING_CARD, pady=(0, 8), sticky="ew")
        self.tab_buttons = self.tab_bar.buttons

        # ── 3. Çerçevesiz Sade Araç Çubuğu ──
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=2, column=0, padx=PADDING_CARD, pady=(0, 8), sticky="ew")

        self._ic_copy = get_icon("copy", size=14, color=TEXT_MUTED, stroke_width=1.5)
        self._ic_check = get_icon("check", size=14, color=SUCCESS_COLOR, stroke_width=1.5)
        self._ic_txt = get_icon("file-down", size=14, color=TEXT_MUTED, stroke_width=1.5)
        self._ic_export = get_icon("file-output", size=14, color=TEXT_MUTED, stroke_width=1.5)
        self._ic_mp3 = get_icon("download", size=14, color=TEXT_MUTED, stroke_width=1.5)
        self._ic_summary = get_icon("file-text", size=14, color=TEXT_MUTED, stroke_width=1.5)
        self._ic_enhance = get_icon("type", size=14, color=TEXT_MUTED, stroke_width=1.5)
        self._ic_clear = get_icon("trash", size=14, color=TEXT_MUTED, stroke_width=1.5)

        # Sol küme: Belge & Dışa Aktarma
        self.copy_btn = self._make_tool_btn(toolbar, " Kopyala", self._copy_to_clipboard, icon=self._ic_copy)
        self.copy_btn.pack(side="left", padx=(0, 4))

        self.save_txt_btn = self._make_tool_btn(toolbar, " TXT", self._save_as_txt, icon=self._ic_txt)
        self.save_txt_btn.pack(side="left", padx=2)

        self.export_doc_btn = self._make_tool_btn(
            toolbar, " Dışa aktar", self._export_document, icon=self._ic_export
        )
        self.export_doc_btn.pack(side="left", padx=2)

        self.export_mp3_btn = self._make_tool_btn(toolbar, " MP3", self._export_audio, icon=self._ic_mp3)
        self.export_mp3_btn.pack(side="left", padx=2)

        ctk.CTkFrame(toolbar, width=1, height=16, fg_color=DIVIDER_COLOR).pack(
            side="left", padx=8, pady=6
        )

        # Sağ küme: Temizle + Metin İşlemleri
        self.clear_btn = ctk.CTkButton(
            toolbar,
            text="",
            image=self._ic_clear,
            width=28,
            height=28,
            fg_color="transparent",
            border_width=0,
            hover_color=STOP_BTN_HOVER,
            corner_radius=6,
            command=self._clear_active_text,
        )
        self.clear_btn.pack(side="right", padx=(4, 0))

        self.enhance_btn = self._make_tool_btn(
            toolbar, " Düzelt", self._handle_enhance, icon=self._ic_enhance
        )
        self.enhance_btn.pack(side="right", padx=2)

        self.summary_btn = self._make_tool_btn(
            toolbar, " Özetle", self._handle_summarize, icon=self._ic_summary
        )
        self.summary_btn.pack(side="right", padx=2)

        # ── 4. Editoryal İç Metin Havuzu + Üst İlerleme Şeridi ──
        self.content_frame = ctk.CTkFrame(
            self,
            corner_radius=RADIUS_INNER,
            fg_color=INNER_BG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.content_frame.grid(row=3, column=0, padx=PADDING_CARD, pady=(0, 8), sticky="nsew")
        self.content_frame.grid_rowconfigure(0, weight=0)
        self.content_frame.grid_rowconfigure(1, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Canlı ilerleme şeridi
        self.progress_ribbon = AcousticProgressRibbon(self.content_frame, bg_token=INNER_BG, height=2)
        self.progress_ribbon.grid(row=0, column=0, sticky="ew", padx=8, pady=(4, 0))

        self.ocr_textbox = self._make_textbox(
            "Görselden okunan veya belgeden çıkarılan metin burada görüntülenir.\n\n"
            "Dilerseniz doğrudan buraya yazabilir ya da metin yapıştırabilirsiniz."
        )

        # Çeviri kapsayıcısı (Tek görünüm + Yan yana Orijinal/Çeviri)
        self.trans_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.trans_container.grid_rowconfigure(1, weight=1)
        self.trans_container.grid_columnconfigure(0, weight=1)

        trans_top_bar = ctk.CTkFrame(self.trans_container, fg_color="transparent")
        trans_top_bar.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        trans_top_bar.grid_columnconfigure(0, weight=1)

        self.detected_lang_lbl = ctk.CTkLabel(
            trans_top_bar,
            text="Algılanan dil: Otomatik",
            font=ui_font(11),
            text_color=TEXT_MUTED,
            fg_color="transparent",
            padx=4,
            pady=2,
        )
        self.detected_lang_lbl.grid(row=0, column=0, sticky="w")

        self._ic_split_idle = get_icon("columns-2", size=14, color=TEXT_MAIN, stroke_width=1.5)
        self._ic_split_active = get_icon("columns-2", size=14, color=PRIMARY_BTN_TEXT, stroke_width=1.5)

        self.side_by_side_btn = ctk.CTkButton(
            trans_top_bar,
            text=" Yan yana",
            image=self._ic_split_idle,
            compound="left",
            width=96,
            height=28,
            font=ui_font(11, "semibold"),
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            text_color=TEXT_MAIN,
            hover_color=SECONDARY_BTN_HOVER,
            corner_radius=8,
            command=self._toggle_side_by_side,
        )
        self.side_by_side_btn.grid(row=0, column=1, sticky="e")

        self.trans_split_frame = ctk.CTkFrame(self.trans_container, fg_color="transparent")
        self.trans_split_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        self.trans_split_frame.grid_rowconfigure(0, weight=1)
        self.trans_split_frame.grid_columnconfigure(0, weight=1)

        self.orig_side_panel = ctk.CTkFrame(
            self.trans_split_frame,
            fg_color=CARD_BG,
            corner_radius=8,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.orig_side_panel.grid_rowconfigure(1, weight=1)
        self.orig_side_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.orig_side_panel,
            text="Orijinal metin",
            font=ui_font(11, "semibold"),
            text_color=TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))
        self.orig_side_textbox = self._make_textbox("", parent=self.orig_side_panel)
        self.orig_side_textbox.grid(row=1, column=0, sticky="nsew", padx=4, pady=(2, 4))

        self.trans_textbox = self._make_textbox(
            "Çeviri sonucu bu alanda görüntülenir.", parent=self.trans_split_frame
        )
        self.trans_textbox.grid(row=0, column=0, sticky="nsew")

        self.summary_textbox = self._make_textbox("Belge özeti bu alanda görüntülenir.")

        # Soru-Cevap görünümü
        self.qa_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.qa_container.grid_rowconfigure(1, weight=1)
        self.qa_container.grid_columnconfigure(0, weight=1)

        qa_bar = ctk.CTkFrame(self.qa_container, fg_color="transparent")
        qa_bar.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        qa_bar.grid_columnconfigure(0, weight=1)

        self.qa_entry = ctk.CTkEntry(
            qa_bar,
            placeholder_text="Belge hakkında soru sor",
            height=36,
            font=ui_font(12),
            fg_color=CARD_BG,
            border_color=CARD_BORDER,
            text_color=TEXT_MAIN,
            placeholder_text_color=TEXT_MUTED,
            corner_radius=RADIUS_BTN,
        )
        self.qa_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.qa_entry.bind("<Return>", lambda _e: self._handle_ask_question())

        self._ic_send = get_icon("send", size=14, color=PRIMARY_BTN_TEXT, stroke_width=1.5)
        self.qa_ask_btn = ctk.CTkButton(
            qa_bar,
            text=" Sor",
            image=self._ic_send,
            compound="left",
            width=72,
            height=36,
            font=ui_font(12, "semibold"),
            command=self._handle_ask_question,
            fg_color=PRIMARY_BTN_BG,
            text_color=PRIMARY_BTN_TEXT,
            hover_color=PRIMARY_BTN_HOVER,
            corner_radius=RADIUS_BTN,
        )
        self.qa_ask_btn.grid(row=0, column=1)

        self.qa_textbox = self._make_textbox(
            "Belge hakkında sorduğunuz soruların yanıtları burada listelenir.",
            parent=self.qa_container,
        )
        self.qa_textbox.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))

        self.ocr_textbox.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))

        # ── 5. Durum ve Tabular İstatistik Satırı ──
        status_bar = ctk.CTkFrame(self, fg_color="transparent")
        status_bar.grid(row=4, column=0, padx=PADDING_CARD, pady=(0, 8), sticky="ew")
        status_bar.grid_columnconfigure(1, weight=1)

        self._ic_status_ok = get_icon("circle-check", size=14, color=TEXT_MUTED, stroke_width=1.5)
        self._ic_status_info = get_icon("info", size=14, color=ACCENT_COLOR, stroke_width=1.5)
        self._ic_status_warn = get_icon("info", size=14, color=WARN_COLOR, stroke_width=1.5)
        self._ic_status_err = get_icon("info", size=14, color=STOP_BTN_TEXT, stroke_width=1.5)

        self.status_icon_lbl = ctk.CTkLabel(status_bar, text="", image=self._ic_status_ok, width=16)
        self.status_icon_lbl.grid(row=0, column=0, sticky="w", padx=(0, 6))

        self.status_lbl = ctk.CTkLabel(
            status_bar,
            text="Hazır",
            font=ui_font(12),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.status_lbl.grid(row=0, column=1, sticky="w")

        self.stats_lbl = ctk.CTkLabel(
            status_bar,
            text="0 kelime · 0 krk · ~0 dk",
            font=mono_font(11),
            text_color=TEXT_MUTED,
            anchor="e",
        )
        self.stats_lbl.grid(row=0, column=2, sticky="e")

        # ── 6. Alt İşlem Satırı: [Hedef dil ▾] [Metni çevir] [Sesli oku] ──
        actions_bar = ctk.CTkFrame(self, fg_color="transparent")
        actions_bar.grid(row=5, column=0, padx=PADDING_CARD, pady=(0, PADDING_CARD), sticky="ew")
        actions_bar.grid_columnconfigure(1, weight=1)
        actions_bar.grid_columnconfigure(2, weight=1)

        lang_box = ctk.CTkFrame(actions_bar, fg_color="transparent")
        lang_box.grid(row=0, column=0, padx=(0, 8), sticky="w")

        ctk.CTkLabel(
            lang_box, text="Dil", font=ui_font(12), text_color=TEXT_MUTED
        ).pack(side="left", padx=(0, 8))

        self.lang_dropdown = ctk.CTkOptionMenu(
            lang_box,
            values=self.AVAILABLE_LANGUAGES,
            command=self._on_target_lang_change,
            width=124,
            height=BTN_HEIGHT_MAIN,
            font=ui_font(12, "semibold"),
            fg_color=SECONDARY_BTN,
            button_color=SECONDARY_BTN_BORDER,
            button_hover_color=SECONDARY_BTN_HOVER,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SECONDARY_BTN,
            dropdown_text_color=TEXT_MAIN,
            text_color=TEXT_MAIN,
            corner_radius=RADIUS_BTN,
        )
        self.lang_dropdown.set(self._last_target_lang)
        self.lang_dropdown.pack(side="left")

        self._ic_translate = get_icon("languages", size=16, color=TEXT_MAIN, stroke_width=1.5)
        self._ic_speak = get_icon("volume-2", size=16, color=PRIMARY_BTN_TEXT, stroke_width=1.7)

        self.translate_btn = ctk.CTkButton(
            actions_bar,
            text=" Metni çevir",
            image=self._ic_translate,
            compound="left",
            height=BTN_HEIGHT_MAIN,
            font=ui_font(13, "semibold"),
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            text_color=TEXT_MAIN,
            hover_color=SECONDARY_BTN_HOVER,
            corner_radius=RADIUS_BTN,
            command=self._handle_translate,
        )
        self.translate_btn.grid(row=0, column=1, padx=(0, 8), sticky="ew")

        self.read_btn = ctk.CTkButton(
            actions_bar,
            text=" Sesli oku",
            image=self._ic_speak,
            compound="left",
            height=BTN_HEIGHT_MAIN,
            font=ui_font(13, "semibold"),
            fg_color=PRIMARY_BTN_BG,
            text_color=PRIMARY_BTN_TEXT,
            hover_color=PRIMARY_BTN_HOVER,
            corner_radius=RADIUS_BTN,
            command=self._handle_read,
        )
        self.read_btn.grid(row=0, column=2, sticky="ew")

    # ── Yardımcı Yapıcılar ────────────────────────────────────────

    def _make_tool_btn(
        self, parent, text: str, command, icon=None, accent_soft: bool = False
    ) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            image=icon,
            compound="left",
            height=28,
            width=10,
            font=ui_font(12),
            fg_color="transparent",
            border_width=0,
            text_color=TEXT_MUTED,
            hover_color=SECONDARY_BTN,
            corner_radius=6,
            command=command,
        )

    def _make_textbox(self, placeholder_text: str = "", parent=None) -> ctk.CTkTextbox:
        target = parent if parent else self.content_frame
        tb = ctk.CTkTextbox(
            target,
            font=ui_font(self._font_size),
            text_color=TEXT_MAIN,
            fg_color="transparent",
            wrap="word",
            corner_radius=RADIUS_INNER,
            padx=10,
            pady=8,
        )
        # Editoryal okuma rahatlığı için satır ve paragraf aralığı
        try:
            tb._textbox.configure(spacing1=3, spacing2=3, spacing3=7, insertbackground=resolve_color(ACCENT_COLOR))
        except Exception:
            pass
        tb.insert("1.0", placeholder_text)
        tb.bind("<KeyRelease>", lambda _e: self._update_stats())
        tb._textbox.bind("<ButtonRelease-1>", lambda e, t=tb: self._on_textbox_click(t, e), add="+")
        self._setup_bold_tag(tb)
        return tb

    def _on_textbox_click(self, textbox: ctk.CTkTextbox, event=None) -> None:
        if not self._on_jump_to_offset:
            return
        inner = textbox._textbox
        try:
            if inner.tag_ranges("sel"):
                return
            if event is not None:
                clicked_idx = inner.index(f"@{event.x},{event.y}")
                inner.mark_set("insert", clicked_idx)
            else:
                clicked_idx = inner.index("insert")
            prefix = inner.get("1.0", clicked_idx)
            self._on_jump_to_offset(len(prefix))
        except Exception:
            pass

    def _setup_bold_tag(self, textbox: ctk.CTkTextbox) -> None:
        import tkinter.font as tkfont

        try:
            base_font = tkfont.Font(font=textbox._textbox.cget("font"))
            actual = base_font.actual()
            bold_font = tkfont.Font(
                family=actual.get("family", FONT_FAMILY),
                size=actual.get("size", -self._font_size),
                weight="bold",
            )
        except Exception:
            bold_font = tkfont.Font(family=FONT_FAMILY, size=-self._font_size, weight="bold")
        textbox._textbox.tag_configure("bold", font=bold_font, foreground=resolve_color(TEXT_MAIN))

    def _on_theme_change(self, _mode: str) -> None:
        if not self.winfo_exists():
            return
        cursor_col = resolve_color(ACCENT_COLOR)
        for tb in (
            self.ocr_textbox,
            self.trans_textbox,
            self.orig_side_textbox,
            self.summary_textbox,
            self.qa_textbox,
        ):
            try:
                tb._textbox.configure(insertbackground=cursor_col)
                self._setup_bold_tag(tb)
            except Exception:
                pass
        if self._last_hl_state is not None:
            tb, s, e, r = self._last_hl_state
            self._apply_monkeytype_highlight(tb, s, e, read_start_pos=r)

    def _on_destroy(self, _event=None) -> None:
        if self._copy_reset_after is not None:
            try:
                self.after_cancel(self._copy_reset_after)
            except Exception:
                pass
            self._copy_reset_after = None
        unregister_theme_listener(self._on_theme_change)

    # ── Sekme Değiştirici ─────────────────────────────────────────

    def _switch_tab(self, tab_name: str) -> None:
        self._active_tab = tab_name
        self.tab_bar.select(tab_name, notify=False)

        self.ocr_textbox.grid_remove()
        self.trans_container.grid_remove()
        self.summary_textbox.grid_remove()
        self.qa_container.grid_remove()

        if tab_name == "Metin":
            self.ocr_textbox.grid(row=1, column=0, sticky="nsew", padx=6, pady=(2, 6))
        elif tab_name == "Çeviri":
            self._sync_orig_side_panel()
            self.trans_container.grid(row=1, column=0, sticky="nsew", padx=4, pady=(2, 4))
        elif tab_name == "Özet":
            self.summary_textbox.grid(row=1, column=0, sticky="nsew", padx=6, pady=(2, 6))
        elif tab_name == "Soru-Cevap":
            self.qa_container.grid(row=1, column=0, sticky="nsew", padx=6, pady=(2, 6))

        self._update_stats()

    def _toggle_side_by_side(self) -> None:
        self._set_side_by_side(not self._side_by_side, save=True)

    def _set_side_by_side(self, enabled: bool, save: bool = True) -> None:
        self._side_by_side = bool(enabled)
        self.orig_side_panel.grid_forget()
        self.trans_textbox.grid_forget()

        if self._side_by_side:
            self._sync_orig_side_panel()
            self.trans_split_frame.grid_columnconfigure(0, weight=1)
            self.trans_split_frame.grid_columnconfigure(1, weight=1)
            self.orig_side_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
            self.trans_textbox.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
            self.side_by_side_btn.configure(
                image=self._ic_split_active,
                fg_color=PRIMARY_BTN_BG,
                text_color=PRIMARY_BTN_TEXT,
                border_color=PRIMARY_BTN_BG,
                hover_color=PRIMARY_BTN_HOVER,
            )
        else:
            self.trans_split_frame.grid_columnconfigure(0, weight=1)
            self.trans_split_frame.grid_columnconfigure(1, weight=0)
            self.trans_textbox.grid(row=0, column=0, sticky="nsew")
            self.side_by_side_btn.configure(
                image=self._ic_split_idle,
                fg_color=SECONDARY_BTN,
                text_color=TEXT_MAIN,
                border_color=SECONDARY_BTN_BORDER,
                hover_color=SECONDARY_BTN_HOVER,
            )
        if save and self.settings:
            self.settings.set_studio("side_by_side", self._side_by_side)

    def _on_target_lang_change(self, lang: str) -> None:
        self._last_target_lang = lang
        if self.settings:
            self.settings.set_studio("target_lang", lang)

    def _sync_orig_side_panel(self) -> None:
        orig = self.get_ocr_text()
        self.orig_side_textbox.configure(state="normal")
        self.orig_side_textbox.delete("1.0", "end")
        self.orig_side_textbox.insert("1.0", orig)
        self.orig_side_textbox.configure(state="disabled")

    # ── Markdown `**` Biçimlendirme ───────────────────────────────

    def _render_formatted_text(self, textbox: ctk.CTkTextbox, raw_text: str) -> None:
        textbox.delete("1.0", "end")
        pattern = re.compile(r"\*\*(.*?)\*\*")
        last_idx = 0
        for match in pattern.finditer(raw_text):
            start, end = match.span()
            bold_text = match.group(1)
            if start > last_idx:
                textbox.insert("end", raw_text[last_idx:start])
            textbox.insert("end", bold_text, "bold")
            last_idx = end
        if last_idx < len(raw_text):
            textbox.insert("end", raw_text[last_idx:])

    # ── Metin Erişim ve Durum Metotları ──────────────────────────

    def _get_active_textbox(self) -> ctk.CTkTextbox:
        if self._active_tab == "Çeviri":
            return self.trans_textbox
        if self._active_tab == "Özet":
            return self.summary_textbox
        if self._active_tab == "Soru-Cevap":
            return self.qa_textbox
        return self.ocr_textbox

    def get_active_text(self) -> str:
        return self._get_active_textbox().get("1.0", "end").strip()

    def get_ocr_text(self) -> str:
        return self.ocr_textbox.get("1.0", "end").strip()

    def set_ocr_text(self, text: str) -> None:
        self._render_formatted_text(self.ocr_textbox, text)
        self._detected_lang = detect_language_local(text)
        self.detected_lang_lbl.configure(text=f"Algılanan dil: {self._detected_lang}")
        self._sync_orig_side_panel()
        self._switch_tab("Metin")
        self._update_stats()

    def set_translation_text(
        self, text: str, source_lang: str = "", target_lang: str = ""
    ) -> None:
        self._render_formatted_text(self.trans_textbox, text)
        if source_lang:
            self._detected_lang = source_lang
        if target_lang:
            self._last_target_lang = target_lang
        self.detected_lang_lbl.configure(
            text=f"Algılanan dil: {self._detected_lang}  →  {self._last_target_lang}"
        )
        self._sync_orig_side_panel()
        self._switch_tab("Çeviri")
        self._update_stats()

    def set_summary_text(self, text: str) -> None:
        self._render_formatted_text(self.summary_textbox, text)
        self._switch_tab("Özet")
        self._update_stats()

    def append_qa_answer(self, question: str, answer: str) -> None:
        current = self.qa_textbox.get("1.0", "end").strip()
        new_block = f"Soru: {question}\nYanıt: {answer}\n{'─' * 42}\n\n"
        if "soruların yanıtları burada" in current:
            self.qa_textbox.delete("1.0", "end")
            self.qa_textbox.insert("1.0", new_block)
        else:
            self.qa_textbox.insert("1.0", new_block)
        self._switch_tab("Soru-Cevap")

    def set_status(self, message: str) -> None:
        raw = (message or "").strip()
        if raw.startswith("❌") or "Hata" in raw or "Başarısız" in raw or "hata" in raw:
            col, icon = STOP_BTN_TEXT, self._ic_status_err
        elif raw.startswith("⚠️") or "gerekli" in raw.lower():
            col, icon = WARN_COLOR, self._ic_status_warn
        elif raw.startswith("⏳") or raw.startswith("🔊") or raw.startswith("🌙"):
            col, icon = ACCENT_COLOR, self._ic_status_info
        else:
            col, icon = TEXT_MUTED, self._ic_status_ok

        clean = _EMOJI_PREFIX_RE.sub("", raw).strip() or "Hazır"
        self.status_icon_lbl.configure(image=icon)
        self.status_lbl.configure(text=clean, text_color=col)

    def set_progress(self, value: float) -> None:
        self.progress_ribbon.set_progress(value)

    def _update_stats(self) -> None:
        text = self.get_active_text()
        stats = get_text_stats(text)
        self.stats_lbl.configure(
            text=f"{stats['words']} kelime · {stats['chars']} krk · {stats['reading_time_str']}"
        )

    # ── Font Boyutu ──────────────────────────────────────────────

    def _increase_font(self) -> None:
        if self._font_size < 28:
            self._font_size += 2
            self._apply_font_size()

    def _decrease_font(self) -> None:
        if self._font_size > 10:
            self._font_size -= 2
            self._apply_font_size()

    def _apply_font_size(self) -> None:
        self.font_size_lbl.configure(text=f"{self._font_size}")
        normal_font = ui_font(self._font_size)
        for tb in (
            self.ocr_textbox,
            self.trans_textbox,
            self.orig_side_textbox,
            self.summary_textbox,
            self.qa_textbox,
        ):
            tb.configure(font=normal_font)
            self._setup_bold_tag(tb)
        if self.settings:
            self.settings.set_studio("font_size", self._font_size)

    # ── Eylemler ─────────────────────────────────────────────────

    def _handle_translate(self) -> None:
        text = self.get_active_text()
        if not text:
            self.set_status("⚠️ Çevrilecek metin bulunamadı.")
            return
        self._on_translate(self.lang_dropdown.get())

    def get_reading_slice_with_offset(self) -> tuple[str, str, int]:
        tb = self._get_active_textbox()
        inner = tb._textbox
        try:
            sel_ranges = inner.tag_ranges("sel")
            if sel_ranges:
                raw_sel = inner.get(sel_ranges[0], sel_ranges[1])
                selected = raw_sel.strip()
                if selected:
                    lead = len(raw_sel) - len(raw_sel.lstrip())
                    sel_offset = len(inner.get("1.0", sel_ranges[0])) + lead
                    return selected, "selection", sel_offset
        except Exception:
            pass

        raw_full = inner.get("1.0", "end-1c")
        full_text = raw_full.strip()
        if not full_text:
            return "", "full", 0

        lead_full = len(raw_full) - len(raw_full.lstrip())
        try:
            cursor_idx = inner.index("insert")
            end_idx = inner.index("end-1c")
            if cursor_idx not in ("1.0", end_idx):
                raw_cursor = inner.get(cursor_idx, "end-1c")
                from_cursor = raw_cursor.strip()
                if from_cursor and len(from_cursor) < len(full_text):
                    lead_cur = len(raw_cursor) - len(raw_cursor.lstrip())
                    cur_offset = len(inner.get("1.0", cursor_idx)) + lead_cur
                    return from_cursor, "cursor", cur_offset
        except Exception:
            pass

        return full_text, "full", lead_full

    def get_reading_slice(self) -> tuple[str, str]:
        text, mode, _ = self.get_reading_slice_with_offset()
        return text, mode

    def _handle_read(self) -> None:
        tb = self._get_active_textbox()
        inner = tb._textbox
        try:
            sel_ranges = inner.tag_ranges("sel")
            if sel_ranges:
                raw_sel = inner.get(sel_ranges[0], sel_ranges[1])
                selected = raw_sel.strip()
                if selected:
                    lead = len(raw_sel) - len(raw_sel.lstrip())
                    sel_offset = len(inner.get("1.0", sel_ranges[0])) + lead
                    try:
                        self._on_read(selected, "selection", sel_offset)
                    except TypeError:
                        self._on_read(selected, "selection")
                    return
        except Exception:
            pass

        raw_full = inner.get("1.0", "end-1c")
        full_text = raw_full.strip()
        if not full_text:
            self.set_status("⚠️ Okunacak metin bulunamadı.")
            return
        lead_full = len(raw_full) - len(raw_full.lstrip())
        try:
            self._on_read(full_text, "restart", lead_full)
        except TypeError:
            self._on_read(full_text, "full")

    def _handle_summarize(self) -> None:
        if self._on_summarize:
            self._on_summarize()

    def _handle_enhance(self) -> None:
        if self._on_enhance:
            self._on_enhance()

    def _handle_ask_question(self) -> None:
        q = self.qa_entry.get().strip()
        if not q:
            return
        if self._on_ask_question:
            self._on_ask_question(q)
            self.qa_entry.delete(0, "end")

    def _copy_to_clipboard(self) -> None:
        text = self.get_active_text()
        if not text:
            self.set_status("⚠️ Kopyalanacak metin yok.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.set_status("Metin panoya kopyalandı.")

        # Kopyala -> Onay mikro-etkileşimi (1.6 sn sonra eski haline döner)
        self.copy_btn.configure(image=self._ic_check, text=" Kopyalandı", text_color=SUCCESS_COLOR)
        if self._copy_reset_after is not None:
            try:
                self.after_cancel(self._copy_reset_after)
            except Exception:
                pass
        self._copy_reset_after = self.after(1600, self._reset_copy_btn)

    def _reset_copy_btn(self) -> None:
        self._copy_reset_after = None
        if self.winfo_exists():
            self.copy_btn.configure(image=self._ic_copy, text=" Kopyala", text_color=TEXT_MUTED)

    def _save_as_txt(self) -> None:
        text = self.get_active_text()
        if not text:
            self.set_status("⚠️ Kaydedilecek metin yok.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Metin Dosyası", "*.txt"), ("Tüm Dosyalar", "*.*")],
            title="Metni TXT Olarak Kaydet",
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.set_status(f"Kaydedildi: {file_path}")
            except Exception as e:
                self.set_status(f"❌ Kaydetme hatası: {e}")

    def _export_document(self) -> None:
        text = self.get_active_text()
        if not text:
            self.set_status("⚠️ Dışa aktarılacak metin yok.")
            return
        file_path = filedialog.asksaveasfilename(
            title="Metni Dışa Aktar (Word, PDF veya Markdown)",
            defaultextension=".docx",
            filetypes=[
                ("Word Belgesi (*.docx)", "*.docx"),
                ("PDF Belgesi (*.pdf)", "*.pdf"),
                ("Markdown Dosyası (*.md)", "*.md"),
            ],
        )
        if not file_path:
            return
        orig = self.get_ocr_text() if self._active_tab == "Çeviri" else ""
        ext = file_path.lower()
        try:
            if ext.endswith(".pdf"):
                export_to_pdf(
                    file_path,
                    translated_text=text,
                    original_text=orig,
                    source_lang=self._detected_lang,
                    target_lang=self._last_target_lang,
                )
            elif ext.endswith(".md"):
                export_to_markdown(
                    file_path,
                    translated_text=text,
                    original_text=orig,
                    source_lang=self._detected_lang,
                    target_lang=self._last_target_lang,
                )
            else:
                export_to_docx(
                    file_path,
                    translated_text=text,
                    original_text=orig,
                    source_lang=self._detected_lang,
                    target_lang=self._last_target_lang,
                )
            self.set_status(f"Dışa aktarıldı: {file_path}")
        except Exception as e:
            self.set_status(f"❌ Dışa aktarma hatası: {e}")

    def _export_audio(self) -> None:
        text = self.get_active_text()
        if not text:
            self.set_status("⚠️ MP3 için önce metin girin.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("MP3 Ses Dosyası", "*.mp3"), ("Tüm Dosyalar", "*.*")],
            title="Konuşmayı MP3 Olarak Kaydet",
        )
        if file_path:
            self._on_export_mp3(file_path)

    def _clear_active_text(self) -> None:
        tb = self._get_active_textbox()
        tb.delete("1.0", "end")
        self._last_hl_state = None
        self._update_stats()
        self.set_status("Metin temizlendi.")

    # ── 3-Katmanlı Canlı Kelime Vurgulama ────────────────────────

    def clear_highlight(self) -> None:
        self._last_hl_state = None
        for tb in (self.ocr_textbox, self.orig_side_textbox, self.trans_textbox, self.summary_textbox, self.qa_textbox):
            try:
                for tag in ("highlight", "read_done", "unread"):
                    tb._textbox.tag_remove(tag, "1.0", "end")
            except Exception:
                pass

    def _apply_monkeytype_highlight(
        self,
        tb: ctk.CTkTextbox,
        start_pos: int,
        end_pos: int,
        read_start_pos: int = 0,
    ) -> None:
        inner = tb._textbox
        full_raw = inner.get("1.0", "end-1c")
        text_len = len(full_raw)
        if text_len <= 0:
            return

        start_pos = max(0, min(start_pos, text_len - 1))
        end_pos = max(start_pos + 1, min(end_pos, text_len))
        # Satır sonlarını vurgu bandına dahil edip tam satır taşmasını önle
        while end_pos > start_pos + 1 and full_raw[end_pos - 1] in ("\n", "\r"):
            end_pos -= 1
        while start_pos < end_pos - 1 and full_raw[start_pos] in ("\n", "\r"):
            start_pos += 1
        read_start_pos = max(0, min(read_start_pos, start_pos))
        self._last_hl_state = (tb, start_pos, end_pos, read_start_pos)

        for tag in ("highlight", "read_done", "unread"):
            inner.tag_remove(tag, "1.0", "end")

        done_fg = resolve_color(HL_DONE_FG)
        hl_bg = resolve_color(HL_ACTIVE_BG)
        hl_fg = resolve_color(HL_ACTIVE_FG)
        unread_fg = resolve_color(HL_UNREAD_FG)

        read_start_idx = f"1.0+{read_start_pos}c"
        start_idx = f"1.0+{start_pos}c"
        end_idx = f"1.0+{end_pos}c"

        if start_pos > read_start_pos:
            inner.tag_add("read_done", read_start_idx, start_idx)
            inner.tag_configure("read_done", foreground=done_fg)

        inner.tag_add("highlight", start_idx, end_idx)
        inner.tag_configure("highlight", background=hl_bg, foreground=hl_fg)

        if end_pos < text_len:
            inner.tag_add("unread", end_idx, "end-1c")
            inner.tag_configure("unread", foreground=unread_fg)

        inner.tag_raise("highlight")
        if inner.bbox(start_idx) is None or inner.bbox(end_idx) is None:
            inner.see(start_idx)

    def highlight_word_span_abs(
        self,
        abs_start: int,
        abs_end: int,
        read_start_pos: int = 0,
        target_textbox: Optional[ctk.CTkTextbox] = None,
    ) -> None:
        tb = target_textbox or self._get_active_textbox()
        self._apply_monkeytype_highlight(tb, abs_start, abs_end, read_start_pos=read_start_pos)
        if self._side_by_side and tb is self.ocr_textbox:
            try:
                self._apply_monkeytype_highlight(
                    self.orig_side_textbox, abs_start, abs_end, read_start_pos=read_start_pos
                )
            except Exception:
                pass

    def highlight_paragraph(self, index: int, paragraphs: list[str]) -> None:
        tb = self._get_active_textbox()
        full_text = tb.get("1.0", "end-1c")
        if index >= len(paragraphs):
            return
        target_para = paragraphs[index]
        pos = full_text.find(target_para)
        if pos == -1:
            return
        self._apply_monkeytype_highlight(tb, pos, pos + len(target_para))

    def highlight_word_span(
        self, paragraph_index: int, paragraphs: list[str], rel_start: int, rel_end: int
    ) -> None:
        tb = self._get_active_textbox()
        full_text = tb.get("1.0", "end-1c")
        if not full_text or paragraph_index >= len(paragraphs):
            return
        target_para = paragraphs[paragraph_index]
        para_pos = full_text.find(target_para)
        if para_pos == -1:
            return
        abs_start = para_pos + max(0, rel_start)
        abs_end = min(len(full_text), para_pos + max(rel_start + 1, rel_end))
        self._apply_monkeytype_highlight(tb, abs_start, abs_end)

    def highlight_sentence(self, paragraph_index: int, paragraphs: list[str], sentence_text: str) -> None:
        tb = self._get_active_textbox()
        full_text = tb.get("1.0", "end-1c")
        if not full_text or paragraph_index >= len(paragraphs):
            return
        target_para = paragraphs[paragraph_index]
        para_pos = full_text.find(target_para)
        search_from = para_pos if para_pos != -1 else 0
        needle = (sentence_text or "").strip()
        pos = -1
        if needle:
            pos = full_text.find(needle, search_from)
            if pos == -1 and len(needle) > 18:
                pos = full_text.find(needle[:18], search_from)
        if pos == -1:
            if para_pos == -1:
                return
            pos = para_pos
            end_pos = para_pos + len(target_para)
        else:
            end_pos = pos + len(needle)
        self._apply_monkeytype_highlight(tb, pos, end_pos)
