"""
Sono Ayarlar Paneli (SettingsPanel).
- Sol ada menü (Lucide ikonlu 6 bölüm + Stüdyoya dön kısayolu)
- Genel sekmesinde görsel önizlemeli Koyu Stüdyo / Açık Stüdyo tema kartları
- Kısayollar ve Özellikler (monospace tuş kapakları + 'Animasyonları azalt' anahtarı)
- Yapay Zeka (maskeli API anahtarı girişi + göster/gizle + canlı doğrulama)
- Güncellemeler & Hakkında (tam çift temalı tokenlar)
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
from tkinter import filedialog
from typing import Callable, Optional
import customtkinter as ctk

import config
from services.gemini_client import reset_gemini_client, validate_api_key
from services.settings_service import (
    SHORTCUT_META,
    SettingsService,
    format_keys_for_display,
)
from ui.icons import get_icon
from ui.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    ACCENT_SOFT_BG,
    ACCENT_SOFT_BORDER,
    ACCENT_SOFT_TEXT,
    ACCENT_TEXT,
    CARD_BG,
    CARD_BORDER,
    INNER_BG,
    ISLAND_ACTIVE_BG,
    PADDING_CARD,
    PRIMARY_BTN_BG,
    PRIMARY_BTN_HOVER,
    PRIMARY_BTN_TEXT,
    RADIUS_BTN,
    RADIUS_CARD,
    SECONDARY_BTN,
    SECONDARY_BTN_BORDER,
    SECONDARY_BTN_HOVER,
    STATUS_PILL_BG,
    STOP_BTN_BG,
    STOP_BTN_TEXT,
    SUCCESS_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
    display_font,
    mono_font,
    ui_font,
)

MODIFIER_KEYSYMS = {
    "Control_L",
    "Control_R",
    "Shift_L",
    "Shift_R",
    "Alt_L",
    "Alt_R",
    "Super_L",
    "Super_R",
    "Meta_L",
    "Meta_R",
    "Win_L",
    "Win_R",
    "Caps_Lock",
    "Num_Lock",
    "Scroll_Lock",
    "ISO_Level3_Shift",
    "Mode_switch",
    "Menu",
    "App",
}
_MODIFIER_VK_CODES = {
    0x10, 0x11, 0x12, 0x13, 0x14,
    0x5B, 0x5C, 0x5D,
    0x90, 0x91,
    0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5,
}
_WIN_SPECIAL_VK_MAP = {
    0x20: "Space",
    0x0D: "Enter",
    0x09: "Tab",
    0x08: "BackSpace",
    0x2E: "Delete",
    0x2D: "Insert",
    0x24: "Home",
    0x23: "End",
    0x21: "PageUp",
    0x22: "PageDown",
    0x25: "Left",
    0x26: "Up",
    0x27: "Right",
    0x28: "Down",
}
_KEYSYM_FALLBACK_MAP = {
    "space": "Space",
    "Return": "Enter",
    "KP_Enter": "Enter",
    "Left": "Left",
    "Right": "Right",
    "Up": "Up",
    "Down": "Down",
    "Tab": "Tab",
    "BackSpace": "BackSpace",
    "Delete": "Delete",
    "Insert": "Insert",
    "Home": "Home",
    "End": "End",
    "Prior": "PageUp",
    "Page_Up": "PageUp",
    "PageUp": "PageUp",
    "Next": "PageDown",
    "Page_Down": "PageDown",
    "PageDown": "PageDown",
}
for _fn in range(1, 13):
    _KEYSYM_FALLBACK_MAP[f"F{_fn}"] = f"F{_fn}"

GLOBAL_SHORTCUT_IDS = {"capture_screen", "toggle_window"}


class SettingsPanel(ctk.CTkFrame):
    """Tüm ayarları yöneten çift temalı ada-kartlı Ayarlar görünümü."""

    def __init__(
        self,
        master,
        settings: SettingsService,
        on_back_to_studio: Callable[[], None],
        on_shortcuts_changed: Optional[Callable[[], None]] = None,
        on_feature_changed: Optional[Callable[[str, bool], None]] = None,
        on_theme_changed: Optional[Callable[[str], None]] = None,
        on_check_updates: Optional[Callable[[], None]] = None,
        on_install_update: Optional[Callable[[], None]] = None,
        on_api_key_updated: Optional[Callable[[bool], None]] = None,
        on_recording_state_changed: Optional[Callable[[bool], None]] = None,
        current_version: str = "v1.0.0",
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.settings = settings
        self._on_back = on_back_to_studio
        self._on_shortcuts_changed = on_shortcuts_changed
        self._on_feature_changed = on_feature_changed
        self._on_theme_changed = on_theme_changed
        self._on_check_updates = on_check_updates
        self._on_install_update = on_install_update
        self._on_api_key_updated = on_api_key_updated
        self._on_recording_state_changed = on_recording_state_changed
        self._current_version = current_version
        self._api_key_visible = False
        self._api_key_testing = False

        self._recording_action: Optional[str] = None
        self._key_bind_id: Optional[str] = None
        self._active_tab = "shortcuts_features"

        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._nav_icons_idle: dict[str, ctk.CTkImage] = {}
        self._nav_icons_act: dict[str, ctk.CTkImage] = {}
        self._tab_frames: dict[str, ctk.CTkFrame] = {}
        self._shortcut_rows: dict[str, dict] = {}
        self._feature_switches: dict[str, ctk.CTkSwitch] = {}
        self._theme_cards: dict[str, dict] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # ── Sol Ada Menü + Stüdyoya Dön ──
        left_holder = ctk.CTkFrame(self, fg_color="transparent", width=232)
        left_holder.grid(row=0, column=0, sticky="nw", padx=(0, 16))
        left_holder.grid_propagate(False)

        left_island = ctk.CTkFrame(
            left_holder,
            corner_radius=RADIUS_CARD,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        left_island.pack(fill="x")

        nav_items = [
            ("general", "Genel ve görünüm", "sliders-horizontal"),
            ("shortcuts_features", "Kısayollar ve özellikler", "keyboard"),
            ("audio", "Ses ve okuma", "headphones"),
            ("ai", "Yapay zeka (API)", "key-round"),
            ("updates", "Güncellemeler", "refresh-cw"),
            ("about", "Hakkında", "info"),
        ]
        for idx, (key, label, icon_name) in enumerate(nav_items):
            ic_idle = get_icon(icon_name, size=15, color=TEXT_MUTED, stroke_width=1.5)
            ic_act = get_icon(icon_name, size=15, color=TEXT_MAIN, stroke_width=1.8)
            self._nav_icons_idle[key] = ic_idle
            self._nav_icons_act[key] = ic_act

            btn = ctk.CTkButton(
                left_island,
                text=f" {label}",
                image=ic_idle,
                compound="left",
                height=36,
                anchor="w",
                font=ui_font(12),
                fg_color="transparent",
                hover_color=SECONDARY_BTN,
                text_color=TEXT_MUTED,
                corner_radius=8,
                command=lambda k=key: self.select_tab(k),
            )
            pad_top = 8 if idx == 0 else 2
            pad_bot = 8 if idx == len(nav_items) - 1 else 2
            btn.pack(fill="x", padx=8, pady=(pad_top, pad_bot))
            self._nav_buttons[key] = btn

        self._ic_back = get_icon("arrow-left", size=14, color=TEXT_MAIN, stroke_width=1.5)
        back_btn = ctk.CTkButton(
            left_holder,
            text=" Stüdyoya dön",
            image=self._ic_back,
            compound="left",
            height=36,
            font=ui_font(12, "semibold"),
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
            text_color=TEXT_MAIN,
            hover_color=SECONDARY_BTN_HOVER,
            corner_radius=8,
            command=self._handle_back,
        )
        back_btn.pack(fill="x", pady=(12, 0))

        # ── Sağ Kaydırılabilir İçerik Alanı ──
        self.right_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=SECONDARY_BTN,
            scrollbar_button_hover_color=SECONDARY_BTN_HOVER,
        )
        self.right_scroll.grid(row=0, column=1, sticky="nsew")
        self.right_scroll.grid_columnconfigure(0, weight=1)

        self._build_shortcuts_and_features_tab()
        self._build_general_tab()
        self._build_audio_tab()
        self._build_ai_tab()
        self._build_updates_tab()
        self._build_about_tab()

        self.select_tab("shortcuts_features")

    # ── Sekme 1: Kısayollar ve Özellikler ────────────────────────

    def _build_shortcuts_and_features_tab(self) -> None:
        tab = ctk.CTkFrame(self.right_scroll, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        # 1) Klavye Kısayolları
        sc_card = ctk.CTkFrame(
            tab,
            corner_radius=RADIUS_CARD,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        sc_card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        sc_card.grid_columnconfigure(0, weight=1)

        sc_hdr = ctk.CTkFrame(sc_card, fg_color="transparent")
        sc_hdr.grid(row=0, column=0, sticky="ew", padx=PADDING_CARD, pady=(PADDING_CARD, 12))
        sc_hdr.grid_columnconfigure(0, weight=1)

        sc_title_box = ctk.CTkFrame(sc_hdr, fg_color="transparent")
        sc_title_box.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            sc_title_box,
            text="Klavye kısayolları",
            font=ui_font(14, "semibold"),
            text_color=TEXT_MAIN,
        ).pack(anchor="w")
        ctk.CTkLabel(
            sc_title_box,
            text="İstediğin kısayolu değiştir ya da hepsini tek anahtarla kapat",
            font=ui_font(12),
            text_color=TEXT_MUTED,
        ).pack(anchor="w")

        sc_ctrl = ctk.CTkFrame(sc_hdr, fg_color="transparent")
        sc_ctrl.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            sc_ctrl,
            text="Kısayolları kullan",
            font=ui_font(12),
            text_color=TEXT_MUTED,
        ).pack(side="left", padx=(0, 8))

        self.master_sc_switch = ctk.CTkSwitch(
            sc_ctrl,
            text="",
            width=42,
            progress_color=ACCENT_COLOR,
            button_color=("#FFFFFF", "#F8FAFC"),
            fg_color=SECONDARY_BTN_BORDER,
            command=self._on_master_shortcut_toggle,
        )
        if self.settings.is_shortcuts_enabled():
            self.master_sc_switch.select()
        self.master_sc_switch.pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            sc_ctrl,
            text="Varsayılana dön",
            height=32,
            font=ui_font(12, "semibold"),
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            text_color=TEXT_MAIN,
            hover_color=SECONDARY_BTN_HOVER,
            corner_radius=8,
            command=self._reset_shortcuts,
        ).pack(side="left")

        self.conflict_banner = ctk.CTkLabel(
            sc_card,
            text="",
            font=ui_font(12, "semibold"),
            text_color=STOP_BTN_TEXT,
            fg_color=STOP_BTN_BG,
            corner_radius=8,
            padx=12,
            pady=6,
            anchor="w",
        )

        self.sc_rows_container = ctk.CTkFrame(sc_card, fg_color="transparent")
        self.sc_rows_container.grid(row=2, column=0, sticky="ew", padx=PADDING_CARD, pady=(0, 12))
        self.sc_rows_container.grid_columnconfigure(0, weight=1)

        self._render_shortcut_rows()

        # 2) Özellikler
        feat_card = ctk.CTkFrame(
            tab,
            corner_radius=RADIUS_CARD,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        feat_card.grid(row=1, column=0, sticky="ew")
        feat_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            feat_card,
            text="Özellikler ve erişilebilirlik",
            font=ui_font(14, "semibold"),
            text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", padx=PADDING_CARD, pady=(PADDING_CARD, 8))

        features_spec = [
            ("highlight_sentence", "Okunan kelimeyi vurgula", "3 katmanlı takip ile metin kendiliğinden kayar"),
            ("resume_last_position", "Kaldığı yerden devam", "Kitaplıktaki belgeler son paragraftan sürdürülür"),
            ("clipboard_monitor", "Pano izleme", 'Metin kopyalayınca "Okuyayım mı?" bildirimi açılır'),
            ("minimize_to_tray", "Sistem tepsisine küçült", "Pencere kapatıldığında arka planda hazır kalır"),
            ("start_with_windows", "Windows ile başlat", "Bilgisayar açıldığında Sono otomatik başlar"),
            ("reduced_motion", "Animasyonları azalt", "Dalga formu, tarama çizgisi ve geçiş hareketlerini durağanlaştırır"),
        ]

        for idx, (fkey, ftitle, fdesc) in enumerate(features_spec):
            if idx > 0:
                sep = ctk.CTkFrame(feat_card, height=1, fg_color=CARD_BORDER)
                sep.grid(row=idx * 2, column=0, sticky="ew", padx=PADDING_CARD)

            row = ctk.CTkFrame(feat_card, fg_color="transparent")
            row.grid(
                row=idx * 2 + 1,
                column=0,
                sticky="ew",
                padx=PADDING_CARD,
                pady=(10, 14 if idx == len(features_spec) - 1 else 10),
            )
            row.grid_columnconfigure(0, weight=1)

            lbl_box = ctk.CTkFrame(row, fg_color="transparent")
            lbl_box.grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(
                lbl_box,
                text=ftitle,
                font=ui_font(13, "semibold"),
                text_color=TEXT_MAIN,
            ).pack(anchor="w")
            ctk.CTkLabel(
                lbl_box,
                text=fdesc,
                font=ui_font(11),
                text_color=TEXT_MUTED,
            ).pack(anchor="w")

            sw = ctk.CTkSwitch(
                row,
                text="",
                width=42,
                progress_color=ACCENT_COLOR,
                button_color=("#FFFFFF", "#F8FAFC"),
                fg_color=SECONDARY_BTN_BORDER,
                command=lambda k=fkey: self._on_feature_toggle(k),
            )
            if self.settings.get_feature(fkey):
                sw.select()
            sw.grid(row=0, column=1, sticky="e", padx=(10, 0))
            self._feature_switches[fkey] = sw

        self._tab_frames["shortcuts_features"] = tab

    # ── Kısayol Satırlarını Çizme ────────────────────────────────

    def _render_shortcut_rows(self) -> None:
        for w in self.sc_rows_container.winfo_children():
            w.destroy()
        self._shortcut_rows.clear()

        master_on = self.settings.is_shortcuts_enabled()
        actions = list(SHORTCUT_META.keys())

        for idx, action_id in enumerate(actions):
            meta = SHORTCUT_META[action_id]
            cfg = self.settings.get_shortcut(action_id)
            keys = cfg.get("keys", "")
            enabled = bool(cfg.get("enabled", False))
            is_recording = self._recording_action == action_id

            if idx > 0:
                sep = ctk.CTkFrame(self.sc_rows_container, height=1, fg_color=CARD_BORDER)
                sep.grid(row=idx * 2 - 1, column=0, sticky="ew")

            row = ctk.CTkFrame(self.sc_rows_container, fg_color="transparent")
            row.grid(row=idx * 2, column=0, sticky="ew", pady=10)
            row.grid_columnconfigure(0, weight=1)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.grid(row=0, column=0, sticky="w")

            ctk.CTkLabel(
                info,
                text=meta["title"],
                font=ui_font(13, "semibold"),
                text_color=TEXT_MAIN if master_on else TEXT_MUTED,
            ).pack(anchor="w")

            desc_text = "Yeni tuş kombinasyonuna bas, iptal için Esc." if is_recording else meta["desc"]
            ctk.CTkLabel(
                info,
                text=desc_text,
                font=ui_font(11),
                text_color=ACCENT_SOFT_TEXT if is_recording else TEXT_MUTED,
            ).pack(anchor="w")

            right = ctk.CTkFrame(row, fg_color="transparent")
            right.grid(row=0, column=1, sticky="e")

            if is_recording:
                ctk.CTkLabel(
                    right,
                    text="Tuşlara bas…",
                    font=mono_font(11, "bold"),
                    text_color=ACCENT_SOFT_TEXT,
                    fg_color=ACCENT_SOFT_BG,
                    corner_radius=8,
                    padx=12,
                    pady=6,
                ).pack(side="left", padx=(0, 8))

                ctk.CTkButton(
                    right,
                    text="İptal",
                    width=64,
                    height=32,
                    font=ui_font(12),
                    fg_color=SECONDARY_BTN,
                    border_width=1,
                    border_color=SECONDARY_BTN_BORDER,
                    text_color=TEXT_MAIN,
                    hover_color=SECONDARY_BTN_HOVER,
                    corner_radius=9,
                    command=self._cancel_recording,
                ).pack(side="left", padx=(0, 12))
            else:
                parts = format_keys_for_display(keys)
                if parts:
                    for p_idx, part in enumerate(parts):
                        if p_idx > 0 and keys != "Left/Right":
                            ctk.CTkLabel(
                                right, text="+", font=mono_font(11), text_color=TEXT_MUTED
                            ).pack(side="left", padx=2)
                        cap_box = ctk.CTkFrame(
                            right,
                            fg_color=INNER_BG,
                            border_width=1,
                            border_color=CARD_BORDER,
                            corner_radius=7,
                        )
                        cap_box.pack(side="left", padx=2)
                        ctk.CTkLabel(
                            cap_box,
                            text=part,
                            font=mono_font(11, "bold"),
                            text_color=TEXT_MAIN if (master_on and enabled) else TEXT_MUTED,
                            padx=8,
                            pady=3,
                        ).pack()
                else:
                    ctk.CTkLabel(
                        right,
                        text="Atanmadı",
                        font=ui_font(12),
                        text_color=TEXT_MUTED,
                    ).pack(side="left", padx=(0, 8))

                ctk.CTkButton(
                    right,
                    text="Değiştir" if keys else "Ata",
                    width=72 if keys else 52,
                    height=32,
                    font=ui_font(12),
                    fg_color=SECONDARY_BTN,
                    border_width=1,
                    border_color=SECONDARY_BTN_BORDER,
                    text_color=TEXT_MAIN,
                    hover_color=SECONDARY_BTN_HOVER,
                    corner_radius=8,
                    state="normal" if master_on else "disabled",
                    command=lambda aid=action_id: self._start_recording(aid),
                ).pack(side="left", padx=(8, 12))

            sw = ctk.CTkSwitch(
                right,
                text="",
                width=42,
                progress_color=ACCENT_COLOR,
                button_color=("#FFFFFF", "#F8FAFC"),
                fg_color=SECONDARY_BTN_BORDER,
                state="normal" if master_on else "disabled",
                command=lambda aid=action_id: self._on_single_shortcut_toggle(aid),
            )
            if enabled:
                sw.select()
            sw.pack(side="left")
            self._shortcut_rows[action_id] = {"switch": sw}

    @property
    def is_recording(self) -> bool:
        return self._recording_action is not None

    def _start_recording(self, action_id: str) -> None:
        self._cancel_recording()
        self._hide_conflict()
        self._recording_action = action_id
        self._render_shortcut_rows()

        if self._on_recording_state_changed:
            self._on_recording_state_changed(True)

        top = self.winfo_toplevel()
        try:
            top.focus_set()
        except Exception:
            pass
        self._key_bind_id = top.bind("<KeyPress>", self._on_key_captured, add="+")

    def _cancel_recording(self) -> None:
        if self._key_bind_id is not None:
            try:
                self.winfo_toplevel().unbind("<KeyPress>", self._key_bind_id)
            except Exception:
                pass
            self._key_bind_id = None
        if self._recording_action is not None:
            self._recording_action = None
            self._render_shortcut_rows()
            if self._on_recording_state_changed:
                self._on_recording_state_changed(False)

    @staticmethod
    def _extract_modifiers(event) -> list[str]:
        """Windows Tkinter'da 0x0008 NumLock'tur; Alt yalnızca 0x20000 bitinden okunur."""
        state = getattr(event, "state", 0) or 0
        mods: list[str] = []
        if state & 0x0004:
            mods.append("Ctrl")
        if state & 0x0001:
            mods.append("Shift")
        if sys.platform == "win32":
            if state & 0x20000:
                mods.append("Alt")
        else:
            if state & 0x20000 or state & 0x0008:
                mods.append("Alt")
        return mods

    @staticmethod
    def _extract_main_key(event) -> Optional[str]:
        """Windows'ta Türkçe/Shift düzen farklarından bağımsız Win32 VK koduyla tuş çözer."""
        if sys.platform == "win32":
            keycode = getattr(event, "keycode", 0) or 0
            if 0x41 <= keycode <= 0x5A:
                return chr(keycode)
            if 0x30 <= keycode <= 0x39:
                return chr(keycode)
            if 0x60 <= keycode <= 0x69:
                return str(keycode - 0x60)
            if 0x70 <= keycode <= 0x7B:
                return f"F{keycode - 0x6F}"
            if keycode in _WIN_SPECIAL_VK_MAP:
                return _WIN_SPECIAL_VK_MAP[keycode]

        keysym = getattr(event, "keysym", "") or ""
        if keysym in _KEYSYM_FALLBACK_MAP:
            return _KEYSYM_FALLBACK_MAP[keysym]
        if len(keysym) == 1 and keysym.isascii() and keysym.isalnum():
            return keysym.upper()
        return None

    def _on_key_captured(self, event) -> str:
        if self._recording_action is None:
            return ""
        keysym = getattr(event, "keysym", "") or ""
        keycode = getattr(event, "keycode", 0) or 0
        if keysym == "Escape" or (sys.platform == "win32" and keycode == 0x1B):
            self._cancel_recording()
            return "break"
        if keysym in MODIFIER_KEYSYMS or (sys.platform == "win32" and keycode in _MODIFIER_VK_CODES):
            return "break"

        mods = self._extract_modifiers(event)
        main_key = self._extract_main_key(event)
        if not main_key:
            self._show_conflict(
                "Bu tuş kısayol olarak desteklenmiyor. Harf, rakam, yön veya F1–F12 tuşlarından birini seçin."
            )
            return "break"

        action_id = self._recording_action
        is_fn_key = main_key.startswith("F") and main_key[1:].isdigit()
        if action_id in GLOBAL_SHORTCUT_IDS and not mods and not is_fn_key:
            self._show_conflict(
                "Genel kısayollar diğer uygulamalarda çakışmaması için Ctrl, Alt veya Shift ile birlikte (ya da tek başına F1–F12) atanmalıdır."
            )
            return "break"

        combo = "+".join(mods + [main_key]) if mods else main_key

        conflict_title = self.settings.find_shortcut_conflict(action_id, combo)
        if conflict_title:
            self._show_conflict(
                f"'{combo}' zaten '{conflict_title}' kısayolunda kullanılıyor. Başka bir tuş seçin."
            )
            return "break"

        self.settings.set_shortcut_keys(action_id, combo)
        self._hide_conflict()
        self._cancel_recording()
        if self._on_shortcuts_changed:
            self._on_shortcuts_changed()
        return "break"

    def _show_conflict(self, msg: str) -> None:
        self.conflict_banner.configure(text=msg)
        self.conflict_banner.grid(row=1, column=0, sticky="ew", padx=PADDING_CARD, pady=(0, 8))

    def _hide_conflict(self) -> None:
        self.conflict_banner.grid_forget()

    def _on_master_shortcut_toggle(self) -> None:
        self._cancel_recording()
        enabled = bool(self.master_sc_switch.get())
        self.settings.set_shortcuts_enabled(enabled)
        self._render_shortcut_rows()
        if self._on_shortcuts_changed:
            self._on_shortcuts_changed()

    def _on_single_shortcut_toggle(self, action_id: str) -> None:
        sw = self._shortcut_rows[action_id]["switch"]
        self.settings.set_shortcut_enabled(action_id, bool(sw.get()))
        if self._on_shortcuts_changed:
            self._on_shortcuts_changed()

    def _reset_shortcuts(self) -> None:
        self._cancel_recording()
        self._hide_conflict()
        self.settings.reset_shortcuts()
        self.master_sc_switch.select()
        self._render_shortcut_rows()
        if self._on_shortcuts_changed:
            self._on_shortcuts_changed()

    # ── Sekme 2: Genel ve Görünüm (Görsel Tema Kartları) ─────────

    def _build_general_tab(self) -> None:
        tab = ctk.CTkFrame(self.right_scroll, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(
            tab, corner_radius=RADIUS_CARD, fg_color=CARD_BG, border_width=1, border_color=CARD_BORDER
        )
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text="Görünüm ve stüdyo teması", font=ui_font(14, "semibold"), text_color=TEXT_MAIN
        ).grid(row=0, column=0, sticky="w", padx=PADDING_CARD, pady=(PADDING_CARD, 4))
        ctk.CTkLabel(
            card,
            text="Sistem (Windows), Koyu veya Açık temasını seç — seçimin kalıcı kaydedilir",
            font=ui_font(12),
            text_color=TEXT_MUTED,
        ).grid(row=1, column=0, sticky="w", padx=PADDING_CARD, pady=(0, 12))

        # Üç görsel önizleme kartı: Sistem (Windows) + Koyu + Açık
        theme_grid = ctk.CTkFrame(card, fg_color="transparent")
        theme_grid.grid(row=2, column=0, sticky="ew", padx=PADDING_CARD, pady=(0, 16))
        theme_grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="tcard")

        self._make_theme_preview_card(
            theme_grid,
            col=0,
            mode="system",
            title="Sistem · Windows",
            subtitle="Windows temasını otomatik izler",
            bg_hex="#1E1F23",
            rail_hex="#141417",
            card_hex="#2A2B30",
            accent_hex="#8AA2FF",
            line_hex="#4A4D57",
        )
        self._make_theme_preview_card(
            theme_grid,
            col=1,
            mode="dark",
            title="Koyu · Grafit",
            subtitle="Düşük ışıkta rahat odak",
            bg_hex="#141415",
            rail_hex="#0F0F10",
            card_hex="#19191B",
            accent_hex="#8AA2FF",
            line_hex="#2F2F34",
        )
        self._make_theme_preview_card(
            theme_grid,
            col=2,
            mode="light",
            title="Açık · Kağıt",
            subtitle="Gündüz okuma netliği",
            bg_hex="#F7F4EE",
            rail_hex="#F1EDE5",
            card_hex="#FDFBF7",
            accent_hex="#3D5BD9",
            line_hex="#CFC8BC",
        )

        cur_mode = self.settings.get_general("theme", "system")
        self.sync_theme_selection(cur_mode)

        sep = ctk.CTkFrame(card, height=1, fg_color=CARD_BORDER)
        sep.grid(row=3, column=0, sticky="ew", padx=PADDING_CARD, pady=(0, 6))

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.grid(row=4, column=0, sticky="ew", padx=PADDING_CARD, pady=(10, PADDING_CARD))
        row2.grid_columnconfigure(0, weight=1)

        dir_box = ctk.CTkFrame(row2, fg_color="transparent")
        dir_box.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            dir_box,
            text="Varsayılan dışa aktarma klasörü",
            font=ui_font(13, "semibold"),
            text_color=TEXT_MAIN,
        ).pack(anchor="w")
        cur_dir = self.settings.get_general("export_dir", "") or "Her seferinde sor"
        self.export_dir_lbl = ctk.CTkLabel(
            dir_box, text=cur_dir, font=mono_font(11), text_color=TEXT_MUTED
        )
        self.export_dir_lbl.pack(anchor="w", pady=(2, 0))

        self._ic_folder = get_icon("folder-open", size=14, color=TEXT_MAIN, stroke_width=1.5)
        ctk.CTkButton(
            row2,
            text=" Klasör seç…",
            image=self._ic_folder,
            compound="left",
            height=32,
            font=ui_font(12, "semibold"),
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            text_color=TEXT_MAIN,
            hover_color=SECONDARY_BTN_HOVER,
            corner_radius=8,
            command=self._choose_export_dir,
        ).grid(row=0, column=1, sticky="e")

        self._tab_frames["general"] = tab

    def _make_theme_preview_card(
        self,
        parent,
        col: int,
        mode: str,
        title: str,
        subtitle: str,
        bg_hex: str,
        rail_hex: str,
        card_hex: str,
        accent_hex: str,
        line_hex: str,
    ) -> None:
        outer = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color=INNER_BG,
            border_width=2,
            border_color=CARD_BORDER,
            cursor="hand2",
        )
        outer.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0 if col == 2 else 6))

        # Mini pencere önizlemesi
        preview = ctk.CTkFrame(
            outer, height=88, corner_radius=8, fg_color=bg_hex, border_width=1, border_color=line_hex
        )
        preview.pack(fill="x", padx=12, pady=(12, 8))
        preview.pack_propagate(False)

        mini_rail = ctk.CTkFrame(preview, width=20, fg_color=rail_hex, corner_radius=4)
        mini_rail.pack(side="left", fill="y", padx=(4, 6), pady=4)
        ctk.CTkFrame(mini_rail, width=8, height=8, corner_radius=4, fg_color=accent_hex).pack(pady=(8, 0))
        ctk.CTkFrame(mini_rail, width=8, height=3, corner_radius=2, fg_color=line_hex).pack(pady=(6, 0))
        ctk.CTkFrame(mini_rail, width=8, height=3, corner_radius=2, fg_color=line_hex).pack(pady=(4, 0))

        mini_body = ctk.CTkFrame(preview, fg_color="transparent")
        mini_body.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=6)

        mini_bar = ctk.CTkFrame(
            mini_body, height=14, fg_color=card_hex, corner_radius=4, border_width=1, border_color=line_hex
        )
        mini_bar.pack(side="bottom", fill="x", pady=(4, 0))
        mini_bar.pack_propagate(False)
        ctk.CTkFrame(mini_bar, width=8, height=8, corner_radius=4, fg_color=accent_hex).pack(side="left", padx=(4, 4), pady=2)
        ctk.CTkFrame(mini_bar, height=3, corner_radius=2, fg_color=line_hex).pack(side="left", fill="x", expand=True, padx=(2, 8), pady=5)

        mini_cards = ctk.CTkFrame(mini_body, fg_color="transparent")
        mini_cards.pack(side="top", fill="both", expand=True)
        c1 = ctk.CTkFrame(mini_cards, fg_color=card_hex, corner_radius=6, border_width=1, border_color=line_hex)
        c1.pack(side="left", fill="both", expand=True, padx=(0, 4))
        c2 = ctk.CTkFrame(mini_cards, fg_color=card_hex, corner_radius=6, border_width=1, border_color=line_hex)
        c2.pack(side="left", fill="both", expand=True, padx=(4, 0))
        ctk.CTkFrame(c2, height=5, width=48, corner_radius=3, fg_color=accent_hex).pack(anchor="w", padx=8, pady=(8, 4))
        ctk.CTkFrame(c2, height=4, width=72, corner_radius=2, fg_color=line_hex).pack(anchor="w", padx=8, pady=(0, 3))
        ctk.CTkFrame(c2, height=4, width=54, corner_radius=2, fg_color=line_hex).pack(anchor="w", padx=8)

        # Başlık satırı + Aktif göstergesi
        meta = ctk.CTkFrame(outer, fg_color="transparent")
        meta.pack(fill="x", padx=12, pady=(0, 12))
        meta.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(meta, text=title, font=ui_font(13, "semibold"), text_color=TEXT_MAIN).grid(
            row=0, column=0, sticky="w"
        )
        badge = ctk.CTkLabel(
            meta,
            text="Aktif",
            font=mono_font(10, "bold"),
            text_color=ACCENT_SOFT_TEXT,
            fg_color="transparent",
            padx=0,
            pady=0,
        )
        badge.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(meta, text=subtitle, font=ui_font(11), text_color=TEXT_MUTED).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 0)
        )

        def _pick(_e=None) -> None:
            self.settings.set_general("theme", mode)
            self.sync_theme_selection(mode)
            if self._on_theme_changed:
                self._on_theme_changed(mode)

        for w in (outer, preview, mini_rail, mini_body, mini_cards, c1, c2, mini_bar, meta):
            w.bind("<Button-1>", _pick, add="+")
        for child in meta.winfo_children():
            child.bind("<Button-1>", _pick, add="+")

        self._theme_cards[mode] = {"frame": outer, "badge": badge}

    def sync_theme_selection(self, mode: str) -> None:
        m_low = str(mode).lower()
        mode = m_low if m_low in ("system", "light", "dark") else "system"
        for m, refs in self._theme_cards.items():
            if m == mode:
                refs["frame"].configure(border_color=ACCENT_COLOR)
                refs["badge"].grid()
            else:
                refs["frame"].configure(border_color=CARD_BORDER)
                refs["badge"].grid_remove()

    # ── Sekme 3: Ses ve Okuma ────────────────────────────────────

    def _build_audio_tab(self) -> None:
        tab = ctk.CTkFrame(self.right_scroll, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        card = ctk.CTkFrame(
            tab, corner_radius=RADIUS_CARD, fg_color=CARD_BG, border_width=1, border_color=CARD_BORDER
        )
        card.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            card, text="Ses motoru ve okuma", font=ui_font(14, "semibold"), text_color=TEXT_MAIN
        ).pack(anchor="w", padx=PADDING_CARD, pady=(PADDING_CARD, 8))
        ctk.CTkLabel(
            card,
            text="Ses motoru: Microsoft Edge-TTS (doğal çok dilli nöral sesler).\n"
            "Hız (0.5x–2.0x), ses seviyesi ve ses seçimi alt stüdyo konsolundan anlık değiştirilebilir.\n"
            "Canlı kelime takibi ve kaldığı yerden devam anahtarları 'Kısayollar ve özellikler' bölümündedir.",
            font=ui_font(12),
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=640,
        ).pack(anchor="w", padx=PADDING_CARD, pady=(0, PADDING_CARD))
        self._tab_frames["audio"] = tab

    # ── Sekme 4: Yapay Zeka (API Anahtarı) ───────────────────────

    def _build_ai_tab(self) -> None:
        tab = ctk.CTkFrame(self.right_scroll, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        card = ctk.CTkFrame(
            tab, corner_radius=RADIUS_CARD, fg_color=CARD_BG, border_width=1, border_color=CARD_BORDER
        )
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text="Yapay zeka (Gemini API anahtarı)", font=ui_font(14, "semibold"), text_color=TEXT_MAIN
        ).grid(row=0, column=0, sticky="w", padx=PADDING_CARD, pady=(PADDING_CARD, 8))

        has_key = config.has_api_key()
        self.ai_status_lbl = ctk.CTkLabel(
            card,
            text="Gemini API anahtarı kayıtlı ve hazır" if has_key else "Devam etmek için Gemini API anahtarınızı girin",
            font=ui_font(12, "semibold"),
            text_color=SUCCESS_COLOR if has_key else STOP_BTN_TEXT,
        )
        self.ai_status_lbl.grid(row=1, column=0, sticky="w", padx=PADDING_CARD, pady=(0, 12))

        key_row = ctk.CTkFrame(card, fg_color="transparent")
        key_row.grid(row=2, column=0, sticky="ew", padx=PADDING_CARD, pady=(0, 8))
        key_row.grid_columnconfigure(0, weight=1)

        self.api_key_entry = ctk.CTkEntry(
            key_row,
            placeholder_text="Gemini API anahtarı",
            show="•",
            height=36,
            font=mono_font(12),
            fg_color=INNER_BG,
            border_color=CARD_BORDER,
            text_color=TEXT_MAIN,
            placeholder_text_color=TEXT_MUTED,
            corner_radius=RADIUS_BTN,
        )
        if has_key:
            self.api_key_entry.insert(0, config.get_api_key())
        self.api_key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self._ic_eye = get_icon("eye", size=15, color=TEXT_MAIN, stroke_width=1.5)
        self._ic_eye_off = get_icon("eye-off", size=15, color=TEXT_MAIN, stroke_width=1.5)

        self.api_key_toggle_btn = ctk.CTkButton(
            key_row,
            text="",
            image=self._ic_eye,
            width=36,
            height=36,
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            hover_color=SECONDARY_BTN_HOVER,
            corner_radius=RADIUS_BTN,
            command=self._toggle_api_key_visibility,
        )
        self.api_key_toggle_btn.grid(row=0, column=1, padx=(0, 8))

        self.api_key_save_btn = ctk.CTkButton(
            key_row,
            text="Doğrula ve kaydet",
            width=144,
            height=36,
            font=ui_font(12, "semibold"),
            fg_color=PRIMARY_BTN_BG,
            text_color=PRIMARY_BTN_TEXT,
            hover_color=PRIMARY_BTN_HOVER,
            corner_radius=RADIUS_BTN,
            command=self._handle_save_api_key,
        )
        self.api_key_save_btn.grid(row=0, column=2)

        help_row = ctk.CTkFrame(card, fg_color="transparent")
        help_row.grid(row=3, column=0, sticky="ew", padx=PADDING_CARD, pady=(0, 12))
        help_row.grid_columnconfigure(0, weight=1)

        self.api_key_feedback_lbl = ctk.CTkLabel(
            help_row,
            text="Anahtar yalnızca bilgisayarınızdaki .env dosyasına kaydedilir, üçüncü taraflarla paylaşılmaz.",
            font=ui_font(11),
            text_color=TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=480,
        )
        self.api_key_feedback_lbl.grid(row=0, column=0, sticky="w")

        self._ic_ext = get_icon("external-link", size=13, color=ACCENT_SOFT_TEXT)
        ctk.CTkButton(
            help_row,
            text="Anahtar al ",
            image=self._ic_ext,
            compound="right",
            height=28,
            width=96,
            font=ui_font(11, "semibold"),
            fg_color="transparent",
            hover_color=SECONDARY_BTN,
            text_color=ACCENT_SOFT_TEXT,
            corner_radius=8,
            command=lambda: webbrowser.open("https://aistudio.google.com/app/apikey"),
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            card,
            text="Desteklenen biçimler\n"
            "· Görseller (OCR): PNG, JPG, JPEG, WEBP, BMP\n"
            "· Belgeler: PDF, PPTX, DOCX, TXT\n"
            "· Dışa aktarma: TXT, Word (.docx), PDF, Markdown (.md), MP3",
            font=ui_font(12),
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=640,
        ).grid(row=4, column=0, sticky="w", padx=PADDING_CARD, pady=(4, 14))

        ctk.CTkButton(
            card,
            text="Hata kaydını (logs/sono.log) aç",
            height=32,
            font=ui_font(12),
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            text_color=TEXT_MAIN,
            hover_color=SECONDARY_BTN_HOVER,
            corner_radius=8,
            command=self._open_log_file,
        ).grid(row=5, column=0, sticky="w", padx=PADDING_CARD, pady=(0, PADDING_CARD))

        self._tab_frames["ai"] = tab

    def _toggle_api_key_visibility(self) -> None:
        self._api_key_visible = not self._api_key_visible
        self.api_key_entry.configure(show="" if self._api_key_visible else "•")
        self.api_key_toggle_btn.configure(image=self._ic_eye_off if self._api_key_visible else self._ic_eye)

    def _handle_save_api_key(self) -> None:
        if self._api_key_testing:
            return
        candidate = self.api_key_entry.get().strip()
        if not candidate:
            self.api_key_feedback_lbl.configure(
                text="Lütfen önce Gemini API anahtarınızı yapıştırın.",
                text_color=STOP_BTN_TEXT,
            )
            return

        self._api_key_testing = True
        self.api_key_save_btn.configure(state="disabled", text="Doğrulanıyor…")
        self.api_key_feedback_lbl.configure(
            text="Anahtar Gemini ile doğrulanıyor, lütfen bekleyin…",
            text_color=ACCENT_SOFT_TEXT,
        )

        def task() -> None:
            ok, msg = validate_api_key(candidate)
            if ok:
                try:
                    config.save_api_key(candidate)
                    reset_gemini_client()
                except Exception:
                    ok = False
                    msg = "Anahtar doğrulandı ancak .env dosyasına kaydedilemedi. Klasör yazma iznini kontrol edin."

            def apply_ui() -> None:
                self._api_key_testing = False
                self.api_key_save_btn.configure(state="normal", text="Doğrula ve kaydet")
                if ok:
                    self.ai_status_lbl.configure(
                        text="Gemini API anahtarı kayıtlı ve hazır.",
                        text_color=SUCCESS_COLOR,
                    )
                    self.api_key_feedback_lbl.configure(text=msg, text_color=SUCCESS_COLOR)
                    if self._on_api_key_updated:
                        self._on_api_key_updated(True)
                else:
                    self.api_key_feedback_lbl.configure(text=msg, text_color=STOP_BTN_TEXT)
                    if not config.has_api_key():
                        self.ai_status_lbl.configure(
                            text="Devam etmek için Gemini API anahtarınızı girin.",
                            text_color=STOP_BTN_TEXT,
                        )
                        if self._on_api_key_updated:
                            self._on_api_key_updated(False)

            self.after(0, apply_ui)

        threading.Thread(target=task, daemon=True).start()

    # ── Sekme 5: Güncellemeler ───────────────────────────────────

    def _create_updates_card(self, parent) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            corner_radius=RADIUS_CARD,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        card.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=PADDING_CARD, pady=(PADDING_CARD, 12))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr,
            text="Güncellemeler",
            font=ui_font(14, "semibold"),
            text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w")

        self.upd_badge_lbl = ctk.CTkLabel(
            hdr,
            text="Denetlenmedi",
            font=mono_font(11),
            text_color=TEXT_MUTED,
            fg_color="transparent",
            padx=0,
            pady=2,
        )
        self.upd_badge_lbl.grid(row=0, column=1, sticky="e")

        ver_row = ctk.CTkFrame(card, fg_color="transparent")
        ver_row.grid(row=1, column=0, sticky="ew", padx=PADDING_CARD, pady=(0, 12))

        cur_box = ctk.CTkFrame(ver_row, fg_color="transparent")
        cur_box.pack(side="left", padx=(0, 28))
        ctk.CTkLabel(cur_box, text="Yüklü sürüm", font=ui_font(11), text_color=TEXT_MUTED).pack(anchor="w")
        self.cur_ver_lbl = ctk.CTkLabel(
            cur_box, text=self._current_version, font=mono_font(15, "bold"), text_color=TEXT_MAIN
        )
        self.cur_ver_lbl.pack(anchor="w")

        lat_box = ctk.CTkFrame(ver_row, fg_color="transparent")
        lat_box.pack(side="left")
        ctk.CTkLabel(lat_box, text="Son sürüm", font=ui_font(11), text_color=TEXT_MUTED).pack(anchor="w")
        self.latest_ver_lbl = ctk.CTkLabel(
            lat_box, text="—", font=mono_font(15, "bold"), text_color=SUCCESS_COLOR
        )
        self.latest_ver_lbl.pack(anchor="w")

        ctk.CTkLabel(
            card, text="GitHub deposu", font=ui_font(11, "semibold"), text_color=TEXT_MUTED
        ).grid(row=2, column=0, sticky="w", padx=PADDING_CARD, pady=(0, 4))

        self.repo_entry = ctk.CTkEntry(
            card,
            placeholder_text="github.com/kullanici-adi/sono",
            height=36,
            font=mono_font(12),
            fg_color=INNER_BG,
            border_color=CARD_BORDER,
            text_color=TEXT_MAIN,
            placeholder_text_color=TEXT_MUTED,
            corner_radius=RADIUS_BTN,
        )
        saved_repo = self.settings.get_update_setting("github_repo", "")
        if saved_repo:
            self.repo_entry.insert(0, saved_repo)
        self.repo_entry.bind("<FocusOut>", lambda _e: self._save_repo_entry())
        self.repo_entry.bind("<Return>", lambda _e: self._save_repo_entry())
        self.repo_entry.grid(row=3, column=0, sticky="ew", padx=PADDING_CARD, pady=(0, 12))

        notes_box = ctk.CTkFrame(
            card, corner_radius=12, fg_color=INNER_BG, border_width=1, border_color=CARD_BORDER
        )
        notes_box.grid(row=4, column=0, sticky="ew", padx=PADDING_CARD, pady=(0, 12))
        ctk.CTkLabel(
            notes_box, text="Sürüm notları", font=ui_font(12, "semibold"), text_color=TEXT_MAIN
        ).pack(anchor="w", padx=12, pady=(10, 2))
        self.release_notes_lbl = ctk.CTkLabel(
            notes_box,
            text="GitHub deposunu girip 'Güncellemeleri denetle' düğmesine bastığında sürüm açıklaması burada görünür.",
            font=ui_font(12),
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=600,
            anchor="w",
        )
        self.release_notes_lbl.pack(anchor="w", padx=12, pady=(0, 10))

        auto_row = ctk.CTkFrame(card, fg_color="transparent")
        auto_row.grid(row=5, column=0, sticky="ew", padx=PADDING_CARD, pady=(0, 12))
        auto_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            auto_row, text="Açılışta otomatik denetle", font=ui_font(12), text_color=TEXT_MAIN
        ).grid(row=0, column=0, sticky="w")
        self.auto_upd_switch = ctk.CTkSwitch(
            auto_row,
            text="",
            width=42,
            progress_color=ACCENT_COLOR,
            button_color=("#FFFFFF", "#F8FAFC"),
            fg_color=SECONDARY_BTN_BORDER,
            command=self._on_auto_update_toggle,
        )
        if self.settings.get_update_setting("auto_check", True):
            self.auto_upd_switch.select()
        self.auto_upd_switch.grid(row=0, column=1, sticky="e")

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=6, column=0, sticky="ew", padx=PADDING_CARD, pady=(0, 8))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        self._ic_refresh = get_icon("refresh-cw", size=14, color=TEXT_MAIN, stroke_width=1.5)
        self._ic_dl = get_icon("download", size=14, color=PRIMARY_BTN_TEXT, stroke_width=1.5)
        self._ic_dl_idle = get_icon("download", size=14, color=TEXT_MUTED, stroke_width=1.5)

        self.btn_check_upd = ctk.CTkButton(
            btn_row,
            text=" Güncellemeleri denetle",
            image=self._ic_refresh,
            compound="left",
            height=40,
            font=ui_font(12, "semibold"),
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            text_color=TEXT_MAIN,
            hover_color=SECONDARY_BTN_HOVER,
            corner_radius=RADIUS_BTN,
            command=self._handle_check_updates,
        )
        self.btn_check_upd.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.btn_install_upd = ctk.CTkButton(
            btn_row,
            text=" İndir ve kur",
            image=self._ic_dl_idle,
            compound="left",
            height=40,
            font=ui_font(12, "semibold"),
            fg_color=SECONDARY_BTN,
            border_width=1,
            border_color=SECONDARY_BTN_BORDER,
            text_color=TEXT_MUTED,
            hover_color=SECONDARY_BTN_HOVER,
            corner_radius=RADIUS_BTN,
            state="disabled",
            command=self._handle_install_update,
        )
        self.btn_install_upd.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ctk.CTkLabel(
            card,
            text="Kurulumdan sonra uygulama kendini yeniden başlatır",
            font=ui_font(11),
            text_color=TEXT_MUTED,
        ).grid(row=7, column=0, sticky="w", padx=PADDING_CARD, pady=(0, PADDING_CARD))

        return card

    def _build_updates_tab(self) -> None:
        tab = ctk.CTkFrame(self.right_scroll, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        upd_card = self._create_updates_card(tab)
        upd_card.grid(row=0, column=0, sticky="ew")
        self._tab_frames["updates"] = tab

    # ── Sekme 6: Hakkında ────────────────────────────────────────

    def _build_about_tab(self) -> None:
        tab = ctk.CTkFrame(self.right_scroll, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        card = ctk.CTkFrame(
            tab, corner_radius=RADIUS_CARD, fg_color=CARD_BG, border_width=1, border_color=CARD_BORDER
        )
        card.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            card, text="Sono", font=display_font(20, "semibold"), text_color=TEXT_MAIN
        ).pack(anchor="w", padx=PADDING_CARD, pady=(PADDING_CARD, 4))
        ctk.CTkLabel(
            card,
            text="Belge okuma ve ses stüdyosu",
            font=ui_font(13),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=PADDING_CARD, pady=(0, 12))
        ctk.CTkLabel(
            card,
            text=f"Sürüm: {self._current_version}\n"
            "OCR & Çeviri: Google Gemini\n"
            "Seslendirme: Microsoft Edge-TTS\n"
            "İkonlar: Lucide Icons (MIT)\n"
            "Verilerin cihazında kalır · Açık Kaynak (MIT)",
            font=mono_font(12),
            text_color=TEXT_MUTED,
            justify="left",
        ).pack(anchor="w", padx=PADDING_CARD, pady=(0, PADDING_CARD))
        self._tab_frames["about"] = tab

    # ── Olaylar ──────────────────────────────────────────────────

    def select_tab(self, tab_key: str) -> None:
        self._cancel_recording()
        if tab_key not in self._tab_frames:
            tab_key = "shortcuts_features"
        self._active_tab = tab_key

        for f in self._tab_frames.values():
            f.grid_forget()
        self._tab_frames[tab_key].grid(row=0, column=0, sticky="nsew")

        for k, btn in self._nav_buttons.items():
            if k == tab_key:
                btn.configure(
                    image=self._nav_icons_act[k],
                    fg_color=ISLAND_ACTIVE_BG,
                    text_color=TEXT_MAIN,
                    font=ui_font(12, "semibold"),
                )
            else:
                btn.configure(
                    image=self._nav_icons_idle[k],
                    fg_color="transparent",
                    text_color=TEXT_MUTED,
                    font=ui_font(12),
                )

    def _on_feature_toggle(self, key: str) -> None:
        val = bool(self._feature_switches[key].get())
        self.settings.set_feature(key, val)
        if self._on_feature_changed:
            self._on_feature_changed(key, val)

    def _on_auto_update_toggle(self) -> None:
        self.settings.set_update_setting("auto_check", bool(self.auto_upd_switch.get()))

    def _save_repo_entry(self) -> None:
        repo = self.repo_entry.get().strip()
        self.settings.set_update_setting("github_repo", repo)

    def set_update_checking(self) -> None:
        self.upd_badge_lbl.configure(
            text="Denetleniyor…", text_color=ACCENT_SOFT_TEXT, fg_color="transparent"
        )
        self.btn_check_upd.configure(state="disabled", text=" Denetleniyor…")
        self.btn_install_upd.configure(
            state="disabled",
            image=self._ic_dl_idle,
            fg_color=SECONDARY_BTN,
            border_width=1,
            text_color=TEXT_MUTED,
        )

    def apply_update_result(self, result) -> None:
        self.btn_check_upd.configure(state="normal", text=" Güncellemeleri denetle")
        if not result.ok:
            self.upd_badge_lbl.configure(text="Hata", text_color=STOP_BTN_TEXT, fg_color="transparent")
            self.latest_ver_lbl.configure(text="—", text_color=TEXT_MUTED)
            self.release_notes_lbl.configure(text=result.error_message)
            self.btn_install_upd.configure(
                state="disabled",
                image=self._ic_dl_idle,
                fg_color=SECONDARY_BTN,
                border_width=1,
                text_color=TEXT_MUTED,
            )
            return

        self.latest_ver_lbl.configure(
            text=result.latest_version or self._current_version,
            text_color=SUCCESS_COLOR,
        )
        notes = result.release_notes or "Sürüm notu bulunmuyor."
        if len(notes) > 420:
            notes = notes[:420].rstrip() + "…"
        self.release_notes_lbl.configure(text=notes)

        if result.update_available:
            self.upd_badge_lbl.configure(
                text="Yeni sürüm var", text_color=ACCENT_SOFT_TEXT, fg_color="transparent"
            )
            self.btn_install_upd.configure(
                state="normal",
                text=" İndir ve kur",
                image=self._ic_dl,
                fg_color=PRIMARY_BTN_BG,
                border_width=0,
                text_color=PRIMARY_BTN_TEXT,
                hover_color=PRIMARY_BTN_HOVER,
            )
        else:
            self.upd_badge_lbl.configure(
                text="Güncel", text_color=SUCCESS_COLOR, fg_color="transparent"
            )
            self.btn_install_upd.configure(
                state="disabled",
                text=" İndir ve kur",
                image=self._ic_dl_idle,
                fg_color=SECONDARY_BTN,
                border_width=1,
                text_color=TEXT_MUTED,
            )

    def set_download_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.btn_install_upd.configure(state="disabled", text=f" İndiriliyor %{pct}…")
        else:
            kb = downloaded // 1024
            self.btn_install_upd.configure(state="disabled", text=f" İndiriliyor ({kb} KB)…")

    def set_download_error(self, message: str) -> None:
        self.upd_badge_lbl.configure(
            text="İndirme hatası", text_color=STOP_BTN_TEXT, fg_color="transparent"
        )
        self.release_notes_lbl.configure(text=message)
        self.btn_install_upd.configure(state="normal", text=" İndir ve kur")

    def _handle_check_updates(self) -> None:
        self._save_repo_entry()
        if self._on_check_updates:
            self._on_check_updates()

    def _handle_install_update(self) -> None:
        if self._on_install_update:
            self._on_install_update()

    def _choose_export_dir(self) -> None:
        folder = filedialog.askdirectory(title="Varsayılan dışa aktarma klasörünü seç")
        if folder:
            self.settings.set_general("export_dir", folder)
            self.export_dir_lbl.configure(text=folder)

    def _open_log_file(self) -> None:
        from services.logger_service import get_log_file_path, setup_logging

        setup_logging()
        log_path = get_log_file_path()
        if not os.path.exists(log_path):
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("Sono hata kaydı başlatıldı.\n")
        try:
            os.startfile(log_path)
        except Exception:
            pass

    def _handle_back(self) -> None:
        self._cancel_recording()
        self._save_repo_entry()
        self._on_back()
