"""
Sono Belge & Görsel Sahnesi (ImagePanel).
Çift temalı (Açık / Koyu), Lucide vektör ikonlu, hover akustik halkalı ve
canlı Gemini OCR tarama ışınlı (StudioDropzoneBackdrop) belge yükleme kartı.
"""

from __future__ import annotations

import threading
import customtkinter as ctk
from tkinter import filedialog
from typing import Any, Callable, Dict, List, Optional
from PIL import Image

from services.document_service import is_document_file, load_document
from services.logger_service import get_logger
from ui.animations import StudioDropzoneBackdrop
from ui.crop_window import CropWindow
from ui.icons import get_icon
from ui.theme import (
    ACCENT_SOFT_TEXT,
    CARD_BG,
    CARD_BORDER,
    INNER_BG,
    RADIUS_BTN,
    SECONDARY_BTN_HOVER,
    TEXT_MAIN,
    TEXT_MUTED,
    TEXT_SUBTLE,
    mono_font,
    ui_font,
)
from utils.image_utils import (
    get_image_info,
    grab_clipboard_image,
    resize_for_preview,
    rotate_image,
)

logger = get_logger("image_panel")

_PANEL_PAD = 24
_SECTION_GAP = 16
_PAPER_BG = ("#FFFFFF", "#F4F2EE")


class ImagePanel(ctk.CTkFrame):
    """Belge ve Görsel Yükleme, Önizleme ve Kırpma Kartı."""

    SUPPORTED_FORMATS = [
        ("Tüm Desteklenen Dosyalar", "*.png *.jpg *.jpeg *.bmp *.webp *.pdf *.pptx *.docx *.txt"),
        ("Görsel Dosyaları", "*.png *.jpg *.jpeg *.bmp *.webp *.gif"),
        ("PDF Belgeleri", "*.pdf"),
        ("PowerPoint Sunumları", "*.pptx"),
        ("Word Belgeleri", "*.docx"),
        ("Metin Dosyaları", "*.txt"),
        ("Tüm Dosyalar", "*.*"),
    ]

    def __init__(
        self,
        master,
        on_image_loaded: Callable[[Image.Image], None],
        on_document_loaded: Optional[Callable[[str, str], None]] = None,
        on_copy: Optional[Callable[[], None]] = None,
        on_export_txt: Optional[Callable[[], None]] = None,
        on_export_mp3: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(
            master,
            corner_radius=0,
            fg_color="transparent",
            border_width=0,
            **kwargs,
        )
        self._on_copy_cb = on_copy
        self._on_export_txt_cb = on_export_txt
        self._on_export_mp3_cb = on_export_mp3
        self._on_image_loaded = on_image_loaded
        self._on_document_loaded = on_document_loaded

        self._current_image: Optional[Image.Image] = None
        self._ctk_image = None
        self._doc_pages: List[Dict[str, Any]] = []
        self._current_page_idx: int = 0
        self._last_doc_path: str = ""
        self._is_loading_doc: bool = False

        self._setup_ui()
        self._setup_dnd()

    def _setup_ui(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Başlık Satırı ──
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(
            row=0,
            column=0,
            padx=_PANEL_PAD,
            pady=(_PANEL_PAD, _SECTION_GAP),
            sticky="ew",
        )
        header_frame.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="Kaynak sayfa",
            font=ui_font(13, "semibold"),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        self.info_lbl = ctk.CTkLabel(
            header_frame,
            text="Dosya bekleniyor",
            font=mono_font(11),
            text_color=TEXT_SUBTLE,
            fg_color="transparent",
            padx=0,
            pady=0,
        )
        self.info_lbl.grid(row=0, column=1, sticky="e")

        # ── 2. Etkileşimli Bırakma & Sayfa Önizleme Alanı ──
        self.drop_frame = ctk.CTkFrame(
            self,
            corner_radius=6,
            border_width=0,
            fg_color=INNER_BG,
        )
        self.drop_frame.grid(
            row=1,
            column=0,
            padx=_PANEL_PAD,
            pady=(0, _SECTION_GAP),
            sticky="nsew",
        )
        self.drop_frame.grid_rowconfigure(0, weight=1)
        self.drop_frame.grid_columnconfigure(0, weight=1)

        # Arka plan (kesik çerçeve + canlı OCR tarama çizgisi)
        self._backdrop = StudioDropzoneBackdrop(self.drop_frame, bg_token=INNER_BG)
        self._backdrop.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.placeholder_box = ctk.CTkFrame(self.drop_frame, fg_color="transparent")
        self.placeholder_box.grid(row=0, column=0, padx=16, pady=16)

        # Sade Upload İkonu
        self._upload_icon = get_icon("cloud-upload", size=24, color=TEXT_MUTED, stroke_width=1.5)
        self.upload_icon_lbl = ctk.CTkLabel(
            self.placeholder_box,
            text="",
            image=self._upload_icon,
            fg_color="transparent",
        )
        self.upload_icon_lbl.pack(pady=(0, 12))

        self.drop_text_main = ctk.CTkLabel(
            self.placeholder_box,
            text="Görsel veya belgeyi bırak",
            font=ui_font(14, "semibold"),
            text_color=TEXT_MAIN,
        )
        self.drop_text_main.pack(pady=(0, 4))

        self.drop_text_sub = ctk.CTkLabel(
            self.placeholder_box,
            text="ya da Ctrl+V ile ekran görüntüsü yapıştır",
            font=ui_font(12),
            text_color=TEXT_MUTED,
        )
        self.drop_text_sub.pack(pady=(0, 12))

        # Sessiz Format Listesi
        self.drop_formats_lbl = ctk.CTkLabel(
            self.placeholder_box,
            text="PNG · JPG · PDF · PPTX · DOCX",
            font=mono_font(11),
            text_color=TEXT_SUBTLE,
        )
        self.drop_formats_lbl.pack()

        # Tıklayınca dosya seçici aç + Hover çerçeve vurgusu
        for clickable in (
            self.drop_frame,
            self._backdrop,
            self.placeholder_box,
            self.upload_icon_lbl,
            self.drop_text_main,
            self.drop_text_sub,
            self.drop_formats_lbl,
        ):
            clickable.bind("<Enter>", lambda _e: self._backdrop.set_hovered(True), add="+")
            clickable.bind("<Leave>", lambda _e: self._backdrop.set_hovered(False), add="+")
        for opener in (
            self._backdrop,
            self.placeholder_box,
            self.upload_icon_lbl,
            self.drop_text_main,
            self.drop_text_sub,
            self.drop_formats_lbl,
        ):
            opener.configure(cursor="hand2")
            opener.bind("<Button-1>", self._on_dropzone_click, add="+")

        # Görsel önizleme etiketi
        self.preview_image_lbl = ctk.CTkLabel(self.drop_frame, text="", fg_color="transparent")

        # Belge (PDF/DOCX/PPTX) yüklendiğinde gösterilen sade özet
        self._doc_icon = get_icon("file-text", size=24, color=TEXT_MUTED, stroke_width=1.5)
        self.doc_state_box = ctk.CTkFrame(self.drop_frame, fg_color="transparent")
        self.doc_icon_badge = ctk.CTkLabel(
            self.doc_state_box,
            text="",
            image=self._doc_icon,
            fg_color="transparent",
        )
        self.doc_icon_badge.pack(pady=(0, 12))
        self.doc_title_lbl = ctk.CTkLabel(
            self.doc_state_box,
            text="",
            font=ui_font(14, "semibold"),
            text_color=TEXT_MAIN,
            wraplength=240,
            justify="center",
        )
        self.doc_title_lbl.pack(pady=(0, 4))
        self.doc_hint_lbl = ctk.CTkLabel(
            self.doc_state_box,
            text="",
            font=ui_font(12),
            text_color=TEXT_MUTED,
            wraplength=240,
            justify="center",
        )
        self.doc_hint_lbl.pack()

        # ── 3. Sayfa/Slayt Gezintisi (yalnız çok sayfalı belgelerde görünür) ──
        self.pagination_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.pagination_frame.grid(
            row=2,
            column=0,
            padx=_PANEL_PAD,
            pady=(0, _SECTION_GAP),
            sticky="ew",
        )
        self.pagination_frame.grid_columnconfigure(1, weight=1)

        self._prev_icon = get_icon("chevron-left", size=14, color=TEXT_MUTED)
        self._next_icon = get_icon("chevron-right", size=14, color=TEXT_MUTED)

        self.prev_page_btn = ctk.CTkButton(
            self.pagination_frame,
            text="Önceki",
            image=self._prev_icon,
            compound="left",
            width=76,
            height=28,
            font=ui_font(11),
            command=self._prev_page,
            fg_color="transparent",
            border_width=1,
            border_color=CARD_BORDER,
            hover_color=SECONDARY_BTN_HOVER,
            text_color=TEXT_MUTED,
            corner_radius=8,
        )
        self.prev_page_btn.grid(row=0, column=0, padx=(0, 4))

        self.page_status_lbl = ctk.CTkLabel(
            self.pagination_frame,
            text="Sayfa 1 / 1",
            font=mono_font(12),
            text_color=TEXT_SUBTLE,
        )
        self.page_status_lbl.grid(row=0, column=1)

        self.next_page_btn = ctk.CTkButton(
            self.pagination_frame,
            text="Sonraki",
            image=self._next_icon,
            compound="right",
            width=76,
            height=28,
            font=ui_font(11),
            command=self._next_page,
            fg_color="transparent",
            border_width=1,
            border_color=CARD_BORDER,
            hover_color=SECONDARY_BTN_HOVER,
            text_color=TEXT_MUTED,
            corner_radius=8,
        )
        self.next_page_btn.grid(row=0, column=2, padx=(4, 0))
        self.pagination_frame.grid_remove()

        # ── 4. Görsel Yardımcı Araçları (Tek satırda 4 sade metin buton) ──
        tools_frame = ctk.CTkFrame(self, fg_color="transparent")
        tools_frame.grid(
            row=3,
            column=0,
            padx=_PANEL_PAD,
            pady=(0, _SECTION_GAP),
            sticky="ew",
        )
        tools_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        tool_btn_cfg = dict(
            width=0,
            height=28,
            font=ui_font(11),
            fg_color="transparent",
            border_width=1,
            border_color=CARD_BORDER,
            hover_color=SECONDARY_BTN_HOVER,
            text_color=TEXT_MUTED,
            text_color_disabled=TEXT_SUBTLE,
            corner_radius=8,
            state="disabled",
        )

        self.rotate_btn = ctk.CTkButton(
            tools_frame,
            text="Döndür",
            command=self._rotate_current_image,
            **tool_btn_cfg,
        )
        self.rotate_btn.grid(row=0, column=0, padx=(0, 3), sticky="ew")

        self.crop_btn = ctk.CTkButton(
            tools_frame,
            text="Kırp",
            command=self._open_crop_window,
            **tool_btn_cfg,
        )
        self.crop_btn.grid(row=0, column=1, padx=3, sticky="ew")

        self.rescan_btn = ctk.CTkButton(
            tools_frame,
            text="Yeniden tara",
            command=self._rescan_current_image,
            **tool_btn_cfg,
        )
        self.rescan_btn.grid(row=0, column=2, padx=3, sticky="ew")

        self.remove_btn = ctk.CTkButton(
            tools_frame,
            text="Temizle",
            command=self.clear_image,
            **tool_btn_cfg,
        )
        self.remove_btn.grid(row=0, column=3, padx=(3, 0), sticky="ew")

        # ── 5. 2x2 Belge İstatistik Kutusu (.facts) ──
        stats_box = ctk.CTkFrame(
            self,
            fg_color=CARD_BORDER,
            corner_radius=12,
            border_width=1,
            border_color=CARD_BORDER,
        )
        stats_box.grid(
            row=4,
            column=0,
            padx=_PANEL_PAD,
            pady=(0, _SECTION_GAP),
            sticky="ew",
        )
        stats_box.grid_columnconfigure((0, 1), weight=1, uniform="facts")

        self._stat_vals: Dict[str, ctk.CTkLabel] = {}
        stat_defs = [
            ("words", "Kelime", "0", 0, 0),
            ("read", "Okunan", "0", 0, 1),
            ("duration", "Süre", "0:00", 1, 0),
            ("lang", "Kaynak dil", "—", 1, 1),
        ]
        for key, lbl_txt, init_val, r_idx, c_idx in stat_defs:
            cell = ctk.CTkFrame(stats_box, fg_color=CARD_BG, corner_radius=0)
            cell.grid(
                row=r_idx,
                column=c_idx,
                padx=(1 if c_idx == 1 else 0, 0),
                pady=(1 if r_idx == 1 else 0, 0),
                sticky="nsew",
            )
            ctk.CTkLabel(
                cell,
                text=lbl_txt,
                font=ui_font(12),
                text_color=TEXT_SUBTLE,
                anchor="w",
            ).pack(anchor="w", padx=14, pady=(12, 4))
            val_lbl = ctk.CTkLabel(
                cell,
                text=init_val,
                font=mono_font(15, "bold"),
                text_color=TEXT_MAIN,
                anchor="w",
            )
            val_lbl.pack(anchor="w", padx=14, pady=(0, 12))
            self._stat_vals[key] = val_lbl

        # ── 6. Alt Dışa Aktarma Butonları: [Kopyala] [TXT] [MP3] (.exp) ──
        exp_row = ctk.CTkFrame(self, fg_color="transparent")
        exp_row.grid(
            row=5,
            column=0,
            padx=_PANEL_PAD,
            pady=(0, _PANEL_PAD),
            sticky="ew",
        )
        exp_row.grid_columnconfigure(0, weight=13)
        exp_row.grid_columnconfigure(1, weight=10)
        exp_row.grid_columnconfigure(2, weight=10)

        self._ic_exp_copy = get_icon("copy", size=14, color=TEXT_MAIN, stroke_width=1.5)
        self._ic_exp_dl = get_icon("download", size=14, color=TEXT_MAIN, stroke_width=1.5)

        exp_btn_cfg = dict(
            width=0,
            height=34,
            font=ui_font(12, "semibold"),
            fg_color="transparent",
            border_width=1,
            border_color=CARD_BORDER,
            hover_color=SECONDARY_BTN_HOVER,
            text_color=TEXT_MAIN,
            corner_radius=RADIUS_BTN,
        )

        self.exp_copy_btn = ctk.CTkButton(
            exp_row,
            text=" Kopyala",
            image=self._ic_exp_copy,
            compound="left",
            command=lambda: self._on_copy_cb() if self._on_copy_cb else None,
            **exp_btn_cfg,
        )
        self.exp_copy_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.exp_txt_btn = ctk.CTkButton(
            exp_row,
            text=" TXT",
            image=self._ic_exp_dl,
            compound="left",
            command=lambda: self._on_export_txt_cb() if self._on_export_txt_cb else None,
            **exp_btn_cfg,
        )
        self.exp_txt_btn.grid(row=0, column=1, padx=4, sticky="ew")

        self.exp_mp3_btn = ctk.CTkButton(
            exp_row,
            text=" MP3",
            image=self._ic_exp_dl,
            compound="left",
            command=lambda: self._on_export_mp3_cb() if self._on_export_mp3_cb else None,
            **exp_btn_cfg,
        )
        self.exp_mp3_btn.grid(row=0, column=2, padx=(4, 0), sticky="ew")

    def update_stats(
        self,
        words: int = 0,
        read_words: int = 0,
        duration_str: str = "0:00",
        source_lang: str = "—",
    ) -> None:
        """Sağ paneldeki 2x2 belge istatistik kutusunu günceller."""
        if not hasattr(self, "_stat_vals"):
            return
        self._stat_vals["words"].configure(text=f"{words:,}".replace(",", "."))
        self._stat_vals["read"].configure(text=f"{read_words:,}".replace(",", "."))
        self._stat_vals["duration"].configure(text=duration_str or "0:00")
        self._stat_vals["lang"].configure(text=(source_lang or "—")[:12])

    # ── Canlı OCR Tarama Animasyonu Kontrolü ─────────────────────

    def set_ocr_scanning(self, active: bool) -> None:
        """Gemini OCR çalışırken belge sahnesinde tarama ışınını başlatır/durdurur."""
        self._backdrop.set_scanning(active)
        if active:
            self.info_lbl.configure(
                text="Gemini okuyor…",
                fg_color="transparent",
                text_color=ACCENT_SOFT_TEXT,
            )
        elif self._current_image is not None:
            self.info_lbl.configure(
                text=get_image_info(self._current_image),
                fg_color="transparent",
                text_color=TEXT_SUBTLE,
            )

    # ── Sürükle-Bırak ve Dosya Yükleme ───────────────────────────

    def _setup_dnd(self) -> None:
        try:
            from tkinterdnd2 import DND_FILES
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)
            self.drop_frame.dnd_bind("<<DropEnter>>", lambda _e: self._backdrop.set_hovered(True))
            self.drop_frame.dnd_bind("<<DropLeave>>", lambda _e: self._backdrop.set_hovered(False))
        except Exception:
            pass

    def _on_drop(self, event) -> None:
        self._backdrop.set_hovered(False)
        file_path = event.data.strip().strip("{}")
        self._load_any_file(file_path)

    def _on_dropzone_click(self, _event=None) -> None:
        if self._current_image is None and not self._doc_pages and not self._is_loading_doc:
            self._open_file_dialog()

    def open_file(self) -> None:
        """Harici tetikleyiciler (kenar çubuğu / kısayol) için dosya seçiciyi açar."""
        self._open_file_dialog()

    def _open_file_dialog(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Dosya Seç (Görsel, PDF, Slayt veya Word)",
            filetypes=self.SUPPORTED_FORMATS,
        )
        if file_path:
            self._load_any_file(file_path)

    def _load_any_file(self, path: str) -> None:
        if self._is_loading_doc:
            return
        if is_document_file(path):
            self._handle_document_file(path)
        else:
            self._load_image_from_path(path)

    def _handle_document_file(self, path: str) -> None:
        if self._is_loading_doc:
            return
        self._is_loading_doc = True
        self._backdrop.set_scanning(True)
        self.info_lbl.configure(
            text="Yükleniyor…", fg_color="transparent", text_color=ACCENT_SOFT_TEXT
        )
        self.pagination_frame.grid_remove()
        self._backdrop.set_scanning(True)
        self._show_doc_state("Belge çözümleniyor…", "Sayfalar çıkarılıyor, lütfen bekleyin.")

        def task() -> None:
            try:
                pages = load_document(path)
                self.after(0, lambda p=pages, fp=path: self._on_document_load_success(p, fp))
            except Exception as e:
                err_text = str(e)
                logger.exception("Belge yükleme hatası (%s): %s", path, err_text)
                self.after(0, lambda _err=err_text: self._on_document_load_error(_err))

        threading.Thread(target=task, daemon=True).start()

    def _on_document_load_success(self, pages: List[Dict[str, Any]], path: str) -> None:
        self._is_loading_doc = False
        self._backdrop.set_scanning(False)
        self._doc_pages = pages
        self._current_page_idx = 0
        self._last_doc_path = path

        if len(self._doc_pages) > 1:
            self.pagination_frame.grid()
            self._update_pagination_ui()
        else:
            self.pagination_frame.grid_remove()

        self._display_current_page(path)

        self.info_lbl.configure(
            text=f"{len(self._doc_pages)} Sayfa",
            fg_color="transparent",
            text_color=TEXT_SUBTLE,
        )
        self.remove_btn.configure(state="normal")
        self.rotate_btn.configure(state="disabled")
        self.crop_btn.configure(state="disabled")
        self.rescan_btn.configure(state="disabled")

    def _on_document_load_error(self, _err_text: str = "") -> None:
        self._is_loading_doc = False
        self._backdrop.set_scanning(False)
        self.info_lbl.configure(text="Açılamadı", fg_color="transparent", text_color=TEXT_SUBTLE)
        self._show_doc_state(
            "Belge açılamadı",
            "Dosyanın bozuk veya şifreli olmadığından emin olup tekrar deneyin.\n"
            "(Ayrıntılar logs/sono.log dosyasına kaydedildi.)",
        )

    def _display_current_page(self, path: str) -> None:
        if not self._doc_pages:
            return
        page = self._doc_pages[self._current_page_idx]
        title = page["title"]
        text = page["text"]

        self._show_doc_state(
            title,
            "Metin soldaki stüdyoya aktarıldı.\nSesli dinleyebilir, özetleyebilir veya çevirebilirsiniz.",
        )
        self._current_image = None
        self._ctk_image = None

        if self._on_document_loaded:
            self._on_document_loaded(title, text)

    def _restore_dropzone_surface(self) -> None:
        self.drop_frame.configure(fg_color=INNER_BG, corner_radius=6, border_width=0)
        self._backdrop.place(relx=0, rely=0, relwidth=1, relheight=1)
        try:
            self._backdrop.lower()
        except Exception:
            pass

    def _show_doc_state(self, title: str, hint: str) -> None:
        self._restore_dropzone_surface()
        self.placeholder_box.grid_remove()
        self.preview_image_lbl.grid_remove()
        try:
            self.preview_image_lbl._label.configure(image="")
        except Exception:
            pass
        self.preview_image_lbl.configure(image=None)
        self.doc_title_lbl.configure(text=title)
        self.doc_hint_lbl.configure(text=hint)
        self.doc_state_box.grid(row=0, column=0, padx=20, pady=20)

    def go_to_page(self, index: int) -> None:
        if not self._doc_pages:
            return
        idx = max(0, min(int(index), len(self._doc_pages) - 1))
        if idx != self._current_page_idx:
            self._current_page_idx = idx
            self._display_current_page(self._last_doc_path)
            self._update_pagination_ui()

    def page_count(self) -> int:
        return len(self._doc_pages)

    def _prev_page(self) -> None:
        if self._current_page_idx > 0:
            self._current_page_idx -= 1
            self._update_pagination_ui()
            self._display_current_page("")

    def _next_page(self) -> None:
        if self._current_page_idx < len(self._doc_pages) - 1:
            self._current_page_idx += 1
            self._update_pagination_ui()
            self._display_current_page("")

    def _update_pagination_ui(self) -> None:
        total = len(self._doc_pages)
        cur = self._current_page_idx + 1
        self.page_status_lbl.configure(text=f"Sayfa {cur} / {total}")
        self.prev_page_btn.configure(state="normal" if cur > 1 else "disabled")
        self.next_page_btn.configure(state="normal" if cur < total else "disabled")

    def paste_from_clipboard(self) -> None:
        image = grab_clipboard_image()
        if image:
            self.pagination_frame.grid_remove()
            self._doc_pages = []
            self._set_image(image)

    def _load_image_from_path(self, path: str) -> None:
        try:
            import os

            if os.path.getsize(path) > 50 * 1024 * 1024:
                self._show_doc_state(
                    "Görsel çok büyük",
                    "Güvenlik nedeniyle 50 MB'tan büyük görsel dosyaları açılamaz.",
                )
                return
            with Image.open(path) as img:
                img.load()
                image = img.convert("RGB") if img.mode != "RGB" else img.copy()
            self.pagination_frame.grid_remove()
            self._doc_pages = []
            self._set_image(image)
        except Image.DecompressionBombError:
            logger.warning("Aşırı büyük çözünürlüklü görsel (DecompressionBomb) engellendi: %s", path)
            self._show_doc_state(
                "Görsel engellendi",
                "Bu görsel güvenlik çözünürlük sınırını aşıyor.",
            )
        except Exception as e:
            logger.exception("Görsel yüklenemedi (%s): %s", path, e)

    def _rotate_current_image(self) -> None:
        if self._current_image:
            rotated = rotate_image(self._current_image, 90)
            self._set_image(rotated)

    def _open_crop_window(self) -> None:
        if self._current_image:
            CropWindow(
                self,
                image=self._current_image,
                on_crop_complete=self._on_crop_applied,
            )

    def _on_crop_applied(self, cropped_image: Image.Image) -> None:
        self._set_image(cropped_image)

    def set_image_preview(self, image: Image.Image) -> None:
        """Görseli OCR callback'i tetiklemeden önizlemede gösterir."""
        self.pagination_frame.grid_remove()
        self._doc_pages = []
        self._set_image(image, trigger_callback=False)

    def _set_image(self, image: Image.Image, trigger_callback: bool = True) -> None:
        self._current_image = image
        self.info_lbl.configure(
            text=get_image_info(image), fg_color="transparent", text_color=TEXT_SUBTLE
        )

        preview = resize_for_preview(image, max_width=236, max_height=320)
        self._ctk_image = ctk.CTkImage(
            light_image=preview,
            dark_image=preview,
            size=(preview.width, preview.height),
        )

        self._backdrop.place_forget()
        self.drop_frame.configure(
            fg_color=_PAPER_BG,
            corner_radius=6,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.placeholder_box.grid_remove()
        self.doc_state_box.grid_remove()
        self.preview_image_lbl.grid(row=0, column=0, padx=14, pady=14, sticky="nsew")
        self.preview_image_lbl.configure(image=self._ctk_image, text="")

        self.rotate_btn.configure(state="normal")
        self.crop_btn.configure(state="normal")
        self.rescan_btn.configure(state="normal")
        self.remove_btn.configure(state="normal")

        if trigger_callback and self._on_image_loaded:
            self._on_image_loaded(image)

    def clear_image(self) -> None:
        self._current_image = None
        self._ctk_image = None
        self._doc_pages = []
        self._backdrop.set_scanning(False)
        self.pagination_frame.grid_remove()
        self._restore_dropzone_surface()

        self.preview_image_lbl.grid_remove()
        self.doc_state_box.grid_remove()
        self.placeholder_box.grid(row=0, column=0, padx=16, pady=16)

        self.info_lbl.configure(
            text="Dosya bekleniyor", fg_color="transparent", text_color=TEXT_SUBTLE
        )
        self.rotate_btn.configure(state="disabled")
        self.crop_btn.configure(state="disabled")
        self.rescan_btn.configure(state="disabled")
        self.remove_btn.configure(state="disabled")

    def _rescan_current_image(self) -> None:
        if self._current_image is not None and self._on_image_loaded:
            self._on_image_loaded(self._current_image)

    @property
    def current_image(self) -> Optional[Image.Image]:
        return self._current_image
