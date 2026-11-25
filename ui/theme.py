"""
Sono Tasarım Sistemi — Çift Temalı (Açık / Koyu) Renk, Tipografi ve Hareket Tokenları.

İki özgün stüdyo teması:
- Koyu Stüdyo ("Obsidian Console"): Derin arduvaz yüzeyler + Akustik Teal vurgu
- Açık Stüdyo ("Atelier Paper"): Serin mimari kağıt yüzeyler + Derin Stüdyo Teal vurgu

Tüm renk tokenları CustomTkinter'ın yerel (light_hex, dark_hex) ikilileridir;
raw tk.Canvas ve tk.Text bileşenleri için `resolve_color()` ve `register_theme_listener()`
ile anlık, titremesiz tema geçişi sağlanır.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple, Union
import customtkinter as ctk

ColorToken = Union[str, Tuple[str, str]]

# ============================================================
# TİPOGRAFİ (FONT)
# ============================================================
FONT_FAMILY = "Segoe UI Variable Text"
FONT_FAMILY_SEMIBOLD = "Segoe UI Variable Text Semibold"
FONT_DISPLAY = "Segoe UI Variable Display"
FONT_MONO = "Cascadia Mono"

_FONTS_RESOLVED = False


def _resolve_system_fonts() -> None:
    """Windows 11 Variable fontlarını, yoksa Segoe UI / Consolas yedeklerini seçer."""
    global FONT_FAMILY, FONT_FAMILY_SEMIBOLD, FONT_DISPLAY, FONT_MONO, _FONTS_RESOLVED
    if _FONTS_RESOLVED:
        return
    try:
        import tkinter.font as tkfont
        fams = set(tkfont.families())
        if "Segoe UI Variable Text" not in fams:
            FONT_FAMILY = "Segoe UI"
            FONT_FAMILY_SEMIBOLD = "Segoe UI Semibold" if "Segoe UI Semibold" in fams else "Segoe UI"
        elif "Segoe UI Variable Text Semibold" not in fams:
            FONT_FAMILY_SEMIBOLD = "Segoe UI Variable Text"

        if "Segoe UI Variable Display" not in fams:
            FONT_DISPLAY = FONT_FAMILY

        if "Cascadia Mono" not in fams:
            FONT_MONO = "Consolas" if "Consolas" in fams else "Courier New"
        _FONTS_RESOLVED = True
    except Exception:
        FONT_FAMILY = "Segoe UI"
        FONT_FAMILY_SEMIBOLD = "Segoe UI"
        FONT_DISPLAY = "Segoe UI"
        FONT_MONO = "Consolas"


def apply_default_font() -> None:
    """CustomTkinter genel varsayılan font ailesini ayarlar."""
    try:
        if "CTkFont" in ctk.ThemeManager.theme:
            ctk.ThemeManager.theme["CTkFont"]["family"] = "Segoe UI"
            ctk.ThemeManager.theme["CTkFont"]["size"] = 13
    except Exception:
        pass


def ui_font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    _resolve_system_fonts()
    fam = FONT_FAMILY_SEMIBOLD if weight == "semibold" else FONT_FAMILY
    w = "bold" if weight == "bold" else "normal"
    return ctk.CTkFont(family=fam, size=size, weight=w)


def display_font(size: int = 20, weight: str = "bold") -> ctk.CTkFont:
    _resolve_system_fonts()
    return ctk.CTkFont(family=FONT_DISPLAY, size=size, weight=weight)


def mono_font(size: int = 12, weight: str = "normal") -> ctk.CTkFont:
    _resolve_system_fonts()
    return ctk.CTkFont(family=FONT_MONO, size=size, weight=weight)


# ============================================================
# ÇİFT TEMALI RENK PALETİ — (LIGHT, DARK)
# ============================================================

# Kabuk ve Yüzey Katmanları
RAIL_BG: ColorToken = ("#EAEFF5", "#0B0E13")
RAIL_BORDER: ColorToken = ("#D7E0EB", "#1B222E")
RAIL_ITEM_HOVER: ColorToken = ("#DDE5EF", "#161C27")
RAIL_ITEM_ACTIVE: ColorToken = ("#FFFFFF", "#172329")

BG_COLOR: ColorToken = ("#F3F6FA", "#10141B")
HEADER_BG: ColorToken = ("#F3F6FA", "#10141B")
CARD_BG: ColorToken = ("#FFFFFF", "#161B24")
CARD_BG_ELEVATED: ColorToken = ("#FFFFFF", "#1B222D")
CARD_BORDER: ColorToken = ("#DCE3EC", "#232C3A")
CARD_HOVER_BORDER: ColorToken = ("#BCC8D8", "#334155")
INNER_BG: ColorToken = ("#F7F9FC", "#0E1219")
DIVIDER_COLOR: ColorToken = ("#DFE6EF", "#1D2430")

# İkincil Kontrol Yüzeyleri
SECONDARY_BTN: ColorToken = ("#EEF2F7", "#1D2431")
SECONDARY_BTN_BORDER: ColorToken = ("#CFD8E3", "#2D3648")
SECONDARY_BTN_HOVER: ColorToken = ("#E2E8F0", "#263042")

DASHED_BORDER: ColorToken = ("#B4C2D4", "#334155")

# Metin Hiyerarşisi (WCAG AA/AAA >= 4.5:1)
TEXT_MAIN: ColorToken = ("#0F172A", "#F1F5F9")
TEXT_MUTED: ColorToken = ("#475569", "#94A3B8")
TEXT_SUBTLE: ColorToken = ("#64748B", "#7B8BA3")

# Sono İmza Vurgu Rengi: Akustik Teal
ACCENT_COLOR: ColorToken = ("#0F766E", "#2DD4BF")
ACCENT_TEXT: ColorToken = ("#FFFFFF", "#042F2E")
ACCENT_HOVER: ColorToken = ("#115E59", "#14B8A6")
ACCENT_SOFT_BG: ColorToken = ("#E6F6F4", "#10282A")
ACCENT_SOFT_BORDER: ColorToken = ("#9CDCD5", "#1F4B4F")
ACCENT_SOFT_TEXT: ColorToken = ("#0F766E", "#5EEAD4")
ACCENT_GLOW: ColorToken = ("#14B8A6", "#5EEAD4")

# Durum ve Bildirim Renkleri
SUCCESS_COLOR: ColorToken = ("#047857", "#34D399")
STATUS_PILL_BG: ColorToken = ("#ECFDF5", "#0E241E")
STATUS_PILL_BORDER: ColorToken = ("#A7F3D0", "#1B4739")
STATUS_PILL_HOVER: ColorToken = ("#D1FAE5", "#14332A")

WARN_COLOR: ColorToken = ("#B45309", "#FBBF24")
WARN_BG: ColorToken = ("#FFFBEB", "#29200F")
WARN_BORDER: ColorToken = ("#FDE68A", "#523E19")

# Durdur / Tehlike Düğmesi (Signal Coral)
STOP_BTN_TEXT: ColorToken = ("#BE123C", "#FB7185")
STOP_BTN_BG: ColorToken = ("#FFF1F2", "#2B141B")
STOP_BTN_BORDER: ColorToken = ("#FECDD3", "#522230")
STOP_BTN_HOVER: ColorToken = ("#FFE4E6", "#3B1B24")

# Navigasyon & AI Düğme Uyumluluk Tokenları
NAV_PILL_BG: ColorToken = ("#FFFFFF", "#161B24")
NAV_PILL_ACTIVE_BG: ColorToken = ("#E6F6F4", "#11282A")
NAV_PILL_ACTIVE_BORDER: ColorToken = ("#0F766E", "#2DD4BF")
NAV_TEXT_IDLE: ColorToken = ("#475569", "#94A3B8")

AI_BTN_BG: ColorToken = ACCENT_SOFT_BG
AI_BTN_BORDER: ColorToken = ACCENT_SOFT_BORDER
AI_BTN_TEXT: ColorToken = ACCENT_SOFT_TEXT
AI_BTN_HOVER: ColorToken = ("#D4F0EC", "#163538")

# Alt Stüdyo Oynatıcı & Akustik Dalga Formu
PLAYER_BG: ColorToken = ("#FFFFFF", "#141922")
PLAYER_BORDER: ColorToken = ("#D3DCE8", "#242D3D")
WAVE_IDLE: ColorToken = ("#CBD5E1", "#263142")
WAVE_ACTIVE: ColorToken = ("#0D9488", "#2DD4BF")
WAVE_PEAK: ColorToken = ("#0F766E", "#99F6E4")
SLIDER_TRACK: ColorToken = ("#DCE3EC", "#263042")

# Monkeytype 3-Katmanlı Okuma Vurgusu
HL_DONE_FG: ColorToken = ("#0F172A", "#F1F5F9")
HL_ACTIVE_BG: ColorToken = ("#CCFBF1", "#134E4A")
HL_ACTIVE_FG: ColorToken = ("#115E59", "#F0FDFA")
HL_UNREAD_FG: ColorToken = ("#94A3B8", "#64748B")

# Ayarlar Yan Menü Aktif Yüzeyi
ISLAND_ACTIVE_BG: ColorToken = ("#E6F6F4", "#13292C")

# ============================================================
# ÖLÇÜLER (GEOMETRY & 4/8px SPACING RHYTHM)
# ============================================================
RADIUS_CARD = 16
RADIUS_INNER = 12
RADIUS_BTN = 10
RADIUS_PILL = 16

BTN_HEIGHT_MAIN = 44
BTN_HEIGHT_SM = 32

SPACING_CARD = 16
PADDING_CARD = 18
RAIL_WIDTH = 78


# ============================================================
# CANLI TEMA YÖNETİMİ VE RENK ÇÖZÜMLEME
# ============================================================
_theme_listeners: list[Callable[[str], None]] = []
_reduced_motion: bool = False


def get_theme_mode() -> str:
    """Aktif temayı 'light' veya 'dark' olarak döndürür."""
    try:
        return "light" if ctk.get_appearance_mode().lower() == "light" else "dark"
    except Exception:
        return "dark"


def is_light_mode() -> bool:
    return get_theme_mode() == "light"


def resolve_color(token: ColorToken, mode: Optional[str] = None) -> str:
    """(light, dark) ikilisini aktif tema için tek hex renge çözümler."""
    if isinstance(token, tuple) and len(token) >= 2:
        m = (mode or get_theme_mode()).lower()
        return token[0] if m == "light" else token[1]
    return str(token)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, int(r))):02X}{max(0, min(255, int(g))):02X}{max(0, min(255, int(b))):02X}"


def hex_blend(c1: str, c2: str, t: float) -> str:
    """İki hex rengi 0..1 oranında pürüzsüz karıştırır."""
    t = max(0.0, min(1.0, float(t)))
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    return rgb_to_hex(
        round(r1 + (r2 - r1) * t),
        round(g1 + (g2 - g1) * t),
        round(b1 + (b2 - b1) * t),
    )


def register_theme_listener(callback: Callable[[str], None]) -> None:
    if callback not in _theme_listeners:
        _theme_listeners.append(callback)


def unregister_theme_listener(callback: Callable[[str], None]) -> None:
    try:
        _theme_listeners.remove(callback)
    except ValueError:
        pass


def notify_theme_changed(mode: str) -> None:
    """Tema değiştiğinde tüm özel Canvas / tk.Text dinleyicilerini günceller."""
    dead: list[Callable[[str], None]] = []
    for cb in list(_theme_listeners):
        try:
            cb(mode)
        except Exception:
            dead.append(cb)
    for cb in dead:
        unregister_theme_listener(cb)


def is_reduced_motion() -> bool:
    return _reduced_motion


def set_reduced_motion(enabled: bool) -> None:
    global _reduced_motion
    _reduced_motion = bool(enabled)
