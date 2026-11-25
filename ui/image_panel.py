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
    ACCENT_COLOR,
    ACCENT_HOVER,
    ACCENT_SOFT_BG,
    ACCENT_SOFT_BORDER,
    ACCENT_SOFT_TEXT,
    ACCENT_TEXT,
    BTN_HEIGHT_MAIN,
    CARD_BG,
    CARD_BORDER,
    INNER_BG,
    PADDING_CARD,
    RADIUS_BTN,
    RADIUS_CARD,
    RADIUS_INNER,
    SECONDARY_BTN,
    SECONDARY_BTN_BORDER,
    SECONDARY_BTN_HOVER,
    TEXT_MAIN,
    TEXT_MUTED,
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
        self._on_image_loaded = on_image_loaded
        self._on_document_loaded = on_document_loaded

        self._current_image: Optional[Image.Image] = None
        self._ctk_image = None
        self._doc_pages: List[Dict[str, Any]] = []
        self._current_page_idx: int = 0
        self._is_loading_doc: bool = False

        self._setup_ui()
        self._setup_dnd()

    def _setup_ui(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Başlık Satırı ──
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=PADDING_CARD, pady=(PADDING_CARD, 12), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="Belge Sahnesi",
            font=ui_font(15, "bold"),
            text_color=TEXT_MAIN,
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        self.info_lbl = ctk.CTkLabel(
            header_frame,
            text="Dosya bekleniyor",
            font=mono_font(11),
            text_color=TEXT_MUTED,
            fg_color=SECONDARY_BTN,
            corner_radius=8,
            padx=10,
            pady=3,
        )
        self.info_lbl.grid(row=0, column=1, sticky="e")

        # ── 2. Etkileşimli Bırakma & OCR Tarama Alanı ──
        self.drop_frame = ctk.CTkFrame(
            self,
            corner_radius=RADIUS_INNER,
            border_width=0,
            fg_color=INNER_BG,
        )
        self.drop_frame.grid(row=1, column=0, padx=PADDING_CARD, pady=(0, 14), sticky="nsew")
        self.drop_frame.grid_rowconfigure(0, weight=1)
        self.drop_frame.grid_columnconfigure(0, weight=1)

        # Animasyonlu arka plan (kesik çerçeve + hover akustik halkaları + OCR tarama ışını)
        self._backdrop = StudioDropzoneBackdrop(self.drop_frame, bg_token=INNER_BG)
        self._backdrop.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.placeholder_box = ctk.CTkFrame(self.drop_frame, fg_color="transparent")
        self.placeholder_box.grid(row=0, column=0, padx=18, pady=18)

        # Upload İkon Rozeti
        self._upload_icon = get_icon("cloud-upload", size=24, color=ACCENT_SOFT_TEXT, stroke_width=1.85)
        self.upload_icon_lbl = ctk.CTkLabel(
            self.placeholder_box,
            text="",
            image=self._upload_icon,
            width=54,
            height=54,
            corner_radius=16,
            fg_color=ACCENT_SOFT_BG,
        )
        self.upload_icon_lbl.pack(pady=(0, 14))

        self.drop_text_main = ctk.CTkLabel(
            self.placeholder_box,
            text="Görsel veya belgeyi bırak",
            font=ui_font(15, "bold"),
            text_color=TEXT_MAIN,
        )
        self.drop_text_main.pack(pady=(0, 4))

        self.drop_text_sub = ctk.CTkLabel(
            self.placeholder_box,
            text="ya da Ctrl+V ile ekran görüntüsü yapıştır",
            font=ui_font(12),
            text_color=TEXT_MUTED,
        )
        self.drop_text_sub.pack(pady=(0, 16))

        # Monospace Format Çipleri
        formats_box = ctk.CTkFrame(self.placeholder_box, fg_color="transparent")
        formats_box.pack()

        for fmt in ["PNG", "JPG", "PDF", "PPTX", "DOCX"]:
            pill = ctk.CTkLabel(
                formats_box,
                text=fmt,
                font=mono_font(10, "bold"),
                text_color=TEXT_MUTED,
                fg_color=SECONDARY_BTN,
                corner_radius=6,
                padx=8,
                pady=3,
            )
            pill.pack(side="left", padx=3)

        # Tıklayınca dosya seçici aç + Hover akustik halka tetikleyici
        for clickable in (
            self.drop_frame,
            self._backdrop,
            self.placeholder_box,
            self.upload_icon_lbl,
            self.drop_text_main,
            self.drop_text_sub,
        ):
            clickable.bind("<Enter>", lambda _e: self._backdrop.set_hovered(True), add="+")
            clickable.bind("<Leave>", lambda _e: self._backdrop.set_hovered(False), add="+")
        for opener in (self.upload_icon_lbl, self.drop_text_main, self.drop_text_sub):
            opener.configure(cursor="hand2")
            opener.bind("<Button-1>", lambda _e: self._open_file_dialog(), add="+")

        # Görsel önizleme etiketi
        self.preview_image_lbl = ctk.CTkLabel(self.drop_frame, text="", fg_color="transparent")

        # Belge (PDF/DOCX/PPTX) yüklendiğinde gösterilen temiz özet kartı
        self._doc_icon = get_icon("file-text", size=28, color=ACCENT_SOFT_TEXT, stroke_width=1.8)
        self.doc_state_box = ctk.CTkFrame(self.drop_frame, fg_color="transparent")
        self.doc_icon_badge = ctk.CTkLabel(
            self.doc_state_box,
            text="",
            image=self._doc_icon,
            width=58,
            height=58,
            corner_radius=16,
            fg_color=ACCENT_SOFT_BG,
        )
        self.doc_icon_badge.pack(pady=(0, 12))
        self.doc_title_lbl = ctk.CTkLabel(
            self.doc_state_box,
            text="",
            font=ui_font(14, "bold"),
            text_color=TEXT_MAIN,
            wraplength=280,
            justify="center",
        )
        self.doc_title_lbl.pack(pady=(0, 6))
        self.doc_hint_lbl = ctk.CTkLabel(
            self.doc_state_box,
            text="",
            font=ui_font(12),
            text_color=TEXT_MUTED,
            wraplength=270,
            justify="center",
        )
        self.doc_hint_lbl.pack()

        # ── 3. Sayfa/Slayt Gezintisi ──
        self.pagination_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.pagination_frame.grid(row=2, column=0, padx=PADDING_CARD, pady=(0, 8), sticky="ew")
        self.pagination_frame.grid_columnconfigure(1, weight=1)

        self._prev_icon = get_icon("chevron-left", size=14, color=TEXT_MAIN)
        self._next_icon = get_icon("chevron-right", size=14, color=TEXT_MAIN)

        self.prev_page_btn = ctk.CTkButton(
            self.pagination_frame,
            text="Önceki",
            image=self._prev_icon,
            compound="left",
            width=86,
            height=30,
            font=ui_font(12),
            command=self._prev_page,
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            hover_color=SECONDARY_BTN_HOVER,
            text_color=TEXT_MAIN,
            corner_radius=8,
        )
        self.prev_page_btn.grid(row=0, column=0, padx=(0, 4))

        self.page_status_lbl = ctk.CTkLabel(
            self.pagination_frame,
            text="Sayfa 1 / 1",
            font=mono_font(12, "bold"),
            text_color=TEXT_MAIN,
        )
        self.page_status_lbl.grid(row=0, column=1)

        self.next_page_btn = ctk.CTkButton(
            self.pagination_frame,
            text="Sonraki",
            image=self._next_icon,
            compound="right",
            width=86,
            height=30,
            font=ui_font(12),
            command=self._next_page,
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            hover_color=SECONDARY_BTN_HOVER,
            text_color=TEXT_MAIN,
            corner_radius=8,
        )
        self.next_page_btn.grid(row=0, column=2, padx=(4, 0))
        self.pagination_frame.grid_remove()

        # ── 4. Ana Eylemler: Dosya Aç (Vurgu) & Yapıştır (İkincil) ──
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.grid(row=3, column=0, padx=PADDING_CARD, pady=(0, 10), sticky="ew")
        actions_frame.grid_columnconfigure((0, 1), weight=1)

        self._open_icon = get_icon("folder-open", size=16, color=ACCENT_TEXT, stroke_width=2.0)
        self._paste_icon = get_icon("clipboard-paste", size=16, color=TEXT_MAIN, stroke_width=1.9)

        self.file_btn = ctk.CTkButton(
            actions_frame,
            text=" Dosya aç",
            image=self._open_icon,
            compound="left",
            command=self._open_file_dialog,
            height=BTN_HEIGHT_MAIN,
            font=ui_font(13, "bold"),
            fg_color=ACCENT_COLOR,
            text_color=ACCENT_TEXT,
            hover_color=ACCENT_HOVER,
            corner_radius=RADIUS_BTN,
        )
        self.file_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.paste_btn = ctk.CTkButton(
            actions_frame,
            text=" Yapıştır",
            image=self._paste_icon,
            compound="left",
            command=self.paste_from_clipboard,
            height=BTN_HEIGHT_MAIN,
            font=ui_font(13, "semibold"),
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            text_color=TEXT_MAIN,
            hover_color=SECONDARY_BTN_HOVER,
            corner_radius=RADIUS_BTN,
        )
        self.paste_btn.grid(row=0, column=1, padx=(6, 0), sticky="ew")

        # ── 5. Görsel Yardımcı Araçları (Lucide ikonlu, çerçevesiz) ──
        tools_frame = ctk.CTkFrame(self, fg_color="transparent")
        tools_frame.grid(row=4, column=0, padx=PADDING_CARD, pady=(0, PADDING_CARD - 2), sticky="ew")
        tools_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self._rot_icon = get_icon("rotate-cw", size=14, color=TEXT_MUTED)
        self._crop_icon = get_icon("crop", size=14, color=TEXT_MUTED)
        self._trash_icon = get_icon("trash", size=14, color=TEXT_MUTED)

        self.rotate_btn = ctk.CTkButton(
            tools_frame,
            text=" 90° döndür",
            image=self._rot_icon,
            compound="left",
            command=self._rotate_current_image,
            height=30,
            font=ui_font(12),
            fg_color="transparent",
            hover_color=SECONDARY_BTN,
            text_color=TEXT_MUTED,
            corner_radius=8,
            state="disabled",
        )
        self.rotate_btn.grid(row=0, column=0, padx=2, sticky="ew")

        self.crop_btn = ctk.CTkButton(
            tools_frame,
            text=" Alan kırp",
            image=self._crop_icon,
            compound="left",
            command=self._open_crop_window,
            height=30,
            font=ui_font(12),
            fg_color="transparent",
            hover_color=SECONDARY_BTN,
            text_color=TEXT_MUTED,
            corner_radius=8,
            state="disabled",
        )
        self.crop_btn.grid(row=0, column=1, padx=2, sticky="ew")

        self.remove_btn = ctk.CTkButton(
            tools_frame,
            text=" Temizle",
            image=self._trash_icon,
            compound="left",
            command=self.clear_image,
            height=30,
            font=ui_font(12),
            fg_color="transparent",
            hover_color=SECONDARY_BTN,
            text_color=TEXT_MUTED,
            corner_radius=8,
            state="disabled",
        )
        self.remove_btn.grid(row=0, column=2, padx=2, sticky="ew")

    # ── Canlı OCR Tarama Animasyonu Kontrolü ─────────────────────

    def set_ocr_scanning(self, active: bool) -> None:
        """Gemini OCR çalışırken belge sahnesinde tarama ışınını başlatır/durdurur."""
        self._backdrop.set_scanning(active)
        if active:
            self.info_lbl.configure(
                text="Gemini okuyor…",
                fg_color=ACCENT_SOFT_BG,
                text_color=ACCENT_SOFT_TEXT,
            )
        elif self._current_image is not None:
            self.info_lbl.configure(
                text=get_image_info(self._current_image),
                fg_color=SECONDARY_BTN,
                text_color=TEXT_MUTED,
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
        self.info_lbl.configure(
            text="Yükleniyor…", fg_color=ACCENT_SOFT_BG, text_color=ACCENT_SOFT_TEXT
        )
        self.file_btn.configure(state="disabled")
        self.paste_btn.configure(state="disabled")
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
        self.file_btn.configure(state="normal")
        self.paste_btn.configure(state="normal")
        self._doc_pages = pages
        self._current_page_idx = 0

        if len(self._doc_pages) > 1:
            self.pagination_frame.grid()
            self._update_pagination_ui()
        else:
            self.pagination_frame.grid_remove()

        self._display_current_page(path)

        self.info_lbl.configure(
            text=f"{len(self._doc_pages)} Sayfa",
            fg_color=ACCENT_SOFT_BG,
            text_color=ACCENT_SOFT_TEXT,
        )
        self.remove_btn.configure(state="normal")
        self.rotate_btn.configure(state="disabled")
        self.crop_btn.configure(state="disabled")

    def _on_document_load_error(self, _err_text: str = "") -> None:
        self._is_loading_doc = False
        self._backdrop.set_scanning(False)
        self.file_btn.configure(state="normal")
        self.paste_btn.configure(state="normal")
        self.info_lbl.configure(text="Açılamadı", fg_color=SECONDARY_BTN, text_color=TEXT_MUTED)
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
            "Metin sağdaki stüdyoya aktarıldı.\nSesli dinleyebilir, özetleyebilir veya çevirebilirsiniz.",
        )
        self._current_image = None
        self._ctk_image = None

        if self._on_document_loaded:
            self._on_document_loaded(title, text)

    def _show_doc_state(self, title: str, hint: str) -> None:
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
            text=get_image_info(image), fg_color=SECONDARY_BTN, text_color=TEXT_MUTED
        )

        preview = resize_for_preview(image, max_width=360, max_height=380)
        self._ctk_image = ctk.CTkImage(
            light_image=preview,
            dark_image=preview,
            size=(preview.width, preview.height),
        )

        self.placeholder_box.grid_remove()
        self.doc_state_box.grid_remove()
        self.preview_image_lbl.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        self.preview_image_lbl.configure(image=self._ctk_image, text="")

        self.rotate_btn.configure(state="normal")
        self.crop_btn.configure(state="normal")
        self.remove_btn.configure(state="normal")

        if trigger_callback and self._on_image_loaded:
            self._on_image_loaded(image)

    def clear_image(self) -> None:
        self._current_image = None
        self._ctk_image = None
        self._doc_pages = []
        self._backdrop.set_scanning(False)
        self.pagination_frame.grid_remove()

        self.preview_image_lbl.grid_remove()
        self.doc_state_box.grid_remove()
        self.placeholder_box.grid(row=0, column=0, padx=18, pady=18)

        self.info_lbl.configure(
            text="Dosya bekleniyor", fg_color=SECONDARY_BTN, text_color=TEXT_MUTED
        )
        self.rotate_btn.configure(state="disabled")
        self.crop_btn.configure(state="disabled")
        self.remove_btn.configure(state="disabled")

    @property
    def current_image(self) -> Optional[Image.Image]:
        return self._current_image
