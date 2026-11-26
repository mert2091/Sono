"""
Sono Tasarım Sistemi — Çift Temalı (Açık / Koyu) Renk, Tipografi ve Hareket Tokenları.

İki stüdyo teması:
- Koyu ("Koyu · Grafit"): Nötr grafit yüzeyler + Sıcak Amber vurgu
- Açık ("Açık · Kağıt"): Sıcak kağıt yüzeyler + Derin Amber vurgu

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


def display_font(size: int = 20, weight: str = "semibold") -> ctk.CTkFont:
    _resolve_system_fonts()
    if weight == "semibold":
        return ctk.CTkFont(family=FONT_FAMILY_SEMIBOLD, size=size, weight="normal")
    w = "bold" if weight == "bold" else "normal"
    return ctk.CTkFont(family=FONT_DISPLAY, size=size, weight=w)


def mono_font(size: int = 12, weight: str = "normal") -> ctk.CTkFont:
    _resolve_system_fonts()
    return ctk.CTkFont(family=FONT_MONO, size=size, weight=weight)


# ============================================================
# ÇİFT TEMALI RENK PALETİ — (LIGHT, DARK)
# ============================================================

# Kabuk ve Yüzey Katmanları (Açık · Kağıt / Koyu · Grafit)
RAIL_BG: ColorToken = ("#EFECE6", "#0F0F10")
RAIL_BORDER: ColorToken = ("#E2DDD4", "#242427")
RAIL_ITEM_HOVER: ColorToken = ("#E6E1D8", "#1A1A1D")
RAIL_ITEM_ACTIVE: ColorToken = ("#FDFBF7", "#222225")

BG_COLOR: ColorToken = ("#F7F4EE", "#141415")
HEADER_BG: ColorToken = ("#F7F4EE", "#141415")
CARD_BG: ColorToken = ("#FDFBF7", "#19191B")
CARD_BG_ELEVATED: ColorToken = ("#F4F0E8", "#202023")
CARD_BORDER: ColorToken = ("#E5E0D7", "#27272A")
CARD_HOVER_BORDER: ColorToken = ("#D2CBC0", "#38383D")
INNER_BG: ColorToken = ("#F6F3EC", "#131315")
DIVIDER_COLOR: ColorToken = ("#E5E0D7", "#242427")

# Birincil Eylem Düğmesi (Koyu temada kırık beyaz, açık temada mürekkep)
PRIMARY_BTN_BG: ColorToken = ("#1C1917", "#EDEDED")
PRIMARY_BTN_TEXT: ColorToken = ("#FDFBF7", "#141415")
PRIMARY_BTN_HOVER: ColorToken = ("#292524", "#FFFFFF")

# İkincil Kontrol Yüzeyleri
SECONDARY_BTN: ColorToken = ("#EFECE6", "#222225")
SECONDARY_BTN_BORDER: ColorToken = ("#DCD6CC", "#2F2F34")
SECONDARY_BTN_HOVER: ColorToken = ("#E5E0D7", "#2B2B30")

DASHED_BORDER: ColorToken = ("#CFC8BC", "#323238")

# Metin Hiyerarşisi (WCAG AA/AAA >= 4.5:1)
TEXT_MAIN: ColorToken = ("#1C1917", "#EDEDED")
TEXT_MUTED: ColorToken = ("#57534E", "#A1A1A6")
TEXT_SUBTLE: ColorToken = ("#78716C", "#78787F")

# Sono İmza Vurgu Rengi: Sıcak Stüdyo Amber
ACCENT_COLOR: ColorToken = ("#B45309", "#E59A3C")
ACCENT_TEXT: ColorToken = ("#FFFFFF", "#141415")
ACCENT_HOVER: ColorToken = ("#92400E", "#F0AA4E")
ACCENT_SOFT_BG: ColorToken = ("#F5ECE0", "#261F17")
ACCENT_SOFT_BORDER: ColorToken = ("#E6D1B8", "#3D3020")
ACCENT_SOFT_TEXT: ColorToken = ("#9A470A", "#E59A3C")
ACCENT_GLOW: ColorToken = ("#D97706", "#F2B866")

# Durum ve Bildirim Renkleri
SUCCESS_COLOR: ColorToken = ("#15803D", "#4CC38A")
STATUS_PILL_BG: ColorToken = SECONDARY_BTN
STATUS_PILL_BORDER: ColorToken = CARD_BORDER
STATUS_PILL_HOVER: ColorToken = SECONDARY_BTN_HOVER

WARN_COLOR: ColorToken = ("#B45309", "#E5A03C")
WARN_BG: ColorToken = ("#FBF4E8", "#262015")
WARN_BORDER: ColorToken = ("#EBD5B3", "#403420")

# Durdur / Tehlike Düğmesi
STOP_BTN_TEXT: ColorToken = ("#B91C1C", "#E5484D")
STOP_BTN_BG: ColorToken = ("#FDF2F2", "#261719")
STOP_BTN_BORDER: ColorToken = ("#F2D2D2", "#422226")
STOP_BTN_HOVER: ColorToken = ("#F9E2E2", "#331D20")

# Navigasyon & Araç Düğme Uyumluluk Tokenları
NAV_PILL_BG: ColorToken = CARD_BG
NAV_PILL_ACTIVE_BG: ColorToken = RAIL_ITEM_ACTIVE
NAV_PILL_ACTIVE_BORDER: ColorToken = CARD_BORDER
NAV_TEXT_IDLE: ColorToken = TEXT_MUTED

AI_BTN_BG: ColorToken = SECONDARY_BTN
AI_BTN_BORDER: ColorToken = SECONDARY_BTN_BORDER
AI_BTN_TEXT: ColorToken = TEXT_MAIN
AI_BTN_HOVER: ColorToken = SECONDARY_BTN_HOVER

# Alt Stüdyo Oynatıcı & Akustik Dalga Formu
PLAYER_BG: ColorToken = ("#FDFBF7", "#19191B")
PLAYER_BORDER: ColorToken = ("#E5E0D7", "#27272A")
WAVE_IDLE: ColorToken = ("#D6D0C4", "#2E2E32")
WAVE_ACTIVE: ColorToken = ("#B45309", "#E59A3C")
WAVE_PEAK: ColorToken = ("#92400E", "#F5C47C")
SLIDER_TRACK: ColorToken = ("#E2DDD4", "#2B2B30")

# 3-Katmanlı Okuma Vurgusu
HL_DONE_FG: ColorToken = ("#1C1917", "#EDEDED")
HL_ACTIVE_BG: ColorToken = ("#F4E3C9", "#332615")
HL_ACTIVE_FG: ColorToken = ("#78350F", "#FCE7C8")
HL_UNREAD_FG: ColorToken = ("#A8A29E", "#6B6B72")

# Ayarlar Yan Menü Aktif Yüzeyi
ISLAND_ACTIVE_BG: ColorToken = ("#EFECE6", "#222225")

# ============================================================
# ÖLÇÜLER (GEOMETRY & 4px SPACING RHYTHM)
# ============================================================
RADIUS_CARD = 12
RADIUS_INNER = 8
RADIUS_BTN = 8
RADIUS_PILL = 8

BTN_HEIGHT_MAIN = 40
BTN_HEIGHT_SM = 32

SPACING_CARD = 16
PADDING_CARD = 16
RAIL_WIDTH = 72


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
