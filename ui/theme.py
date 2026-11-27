"""
Sono Tasarım Sistemi — Referans Stüdyo (sono-studio) Çift Temalı Renk ve Tipografi Tokenları.

İki stüdyo teması:
- Koyu ("Koyu · Grafit"): #0F0F10 / #141415 / #19191B + Mavi vurgu (#8AA2FF)
- Açık ("Açık · Kağıt"): #F1EDE5 / #F7F4EE / #FDFBF7 + Mavi vurgu (#3D5BD9) + belirgin çizgiler
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple, Union
import customtkinter as ctk

ColorToken = Union[str, Tuple[str, str]]

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

# Kabuk ve Yüzey Katmanları (Açık · Kağıt belirgin çizgili / Koyu · Grafit)
RAIL_BG: ColorToken = ("#F1EDE5", "#0F0F10")
RAIL_BORDER: ColorToken = ("#CFC8BC", "#242427")
RAIL_ITEM_HOVER: ColorToken = ("#E5DFD3", "#1A1A1D")
RAIL_ITEM_ACTIVE: ColorToken = ("#E9E3D7", "#232325")

BG_COLOR: ColorToken = ("#F7F4EE", "#141415")
HEADER_BG: ColorToken = ("#F7F4EE", "#141415")
CARD_BG: ColorToken = ("#FDFBF7", "#19191B")
CARD_BG_ELEVATED: ColorToken = ("#EFE9DF", "#232325")
CARD_BORDER: ColorToken = ("#D2CBC0", "#27272A")
CARD_HOVER_BORDER: ColorToken = ("#B8B0A4", "#38383D")
INNER_BG: ColorToken = ("#F7F4EE", "#141415")
DIVIDER_COLOR: ColorToken = ("#D2CBC0", "#242427")

# Birincil Eylem Düğmesi
PRIMARY_BTN_BG: ColorToken = ("#1F1B16", "#EDEDED")
PRIMARY_BTN_TEXT: ColorToken = ("#FDFBF7", "#141415")
PRIMARY_BTN_HOVER: ColorToken = ("#332D26", "#FFFFFF")

# İkincil Kontrol Yüzeyleri
SECONDARY_BTN: ColorToken = ("#EFE9DF", "#232325")
SECONDARY_BTN_BORDER: ColorToken = ("#C4BDB1", "#2F2F34")
SECONDARY_BTN_HOVER: ColorToken = ("#E3DDD1", "#2C2C30")

DASHED_BORDER: ColorToken = ("#BEB6A9", "#323238")

# Metin Hiyerarşisi
TEXT_MAIN: ColorToken = ("#1F1B16", "#EDEDED")
TEXT_MUTED: ColorToken = ("#5E554A", "#A1A1A6")
TEXT_SUBTLE: ColorToken = ("#7B7266", "#85858B")

# Referans Vurgu Rengi: Stüdyo Mavi (#3D5BD9 / #8AA2FF)
ACCENT_COLOR: ColorToken = ("#3D5BD9", "#8AA2FF")
ACCENT_TEXT: ColorToken = ("#FFFFFF", "#0F1220")
ACCENT_HOVER: ColorToken = ("#2F4BC4", "#A3B6FF")
ACCENT_SOFT_BG: ColorToken = ("#E6E9F6", "#222531")
ACCENT_SOFT_BORDER: ColorToken = ("#C5CEF0", "#39446B")
ACCENT_SOFT_TEXT: ColorToken = ("#3D5BD9", "#8AA2FF")
ACCENT_GLOW: ColorToken = ("#5B76E5", "#A8BBFF")

# Durum ve Bildirim Renkleri
SUCCESS_COLOR: ColorToken = ("#16A34A", "#4CC38A")
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

NAV_PILL_BG: ColorToken = CARD_BG
NAV_PILL_ACTIVE_BG: ColorToken = RAIL_ITEM_ACTIVE
NAV_PILL_ACTIVE_BORDER: ColorToken = CARD_BORDER
NAV_TEXT_IDLE: ColorToken = TEXT_MUTED

AI_BTN_BG: ColorToken = SECONDARY_BTN
AI_BTN_BORDER: ColorToken = SECONDARY_BTN_BORDER
AI_BTN_TEXT: ColorToken = TEXT_MAIN
AI_BTN_HOVER: ColorToken = SECONDARY_BTN_HOVER

# Alt Stüdyo Oynatıcı & İlerleme Çubuğu
PLAYER_BG: ColorToken = ("#FDFBF7", "#0F0F10")
PLAYER_BORDER: ColorToken = ("#D2CBC0", "#27272A")
WAVE_IDLE: ColorToken = ("#CFC8BC", "#2E2E32")
WAVE_ACTIVE: ColorToken = ("#3D5BD9", "#8AA2FF")
WAVE_PEAK: ColorToken = ("#2F4BC4", "#B3C3FF")
SLIDER_TRACK: ColorToken = ("#CEC7BA", "#2B2B30")

# 3-Katmanlı Okuma Vurgusu
HL_DONE_FG: ColorToken = ("#1F1B16", "#EDEDED")
HL_ACTIVE_BG: ColorToken = ("#E2E7FA", "#232942")
HL_ACTIVE_FG: ColorToken = ("#1E3A8A", "#C7D2FE")
HL_UNREAD_FG: ColorToken = ("#9C9488", "#787880")

ISLAND_ACTIVE_BG: ColorToken = ("#E9E3D7", "#232325")

RADIUS_CARD = 12
RADIUS_INNER = 8
RADIUS_BTN = 8
RADIUS_PILL = 8

BTN_HEIGHT_MAIN = 38
BTN_HEIGHT_SM = 32

SPACING_CARD = 16
PADDING_CARD = 16
RAIL_WIDTH = 256

_theme_listeners: list[Callable[[str], None]] = []
_reduced_motion: bool = False


def get_theme_mode() -> str:
    try:
        return "light" if ctk.get_appearance_mode().lower() == "light" else "dark"
    except Exception:
        return "dark"


def is_light_mode() -> bool:
    return get_theme_mode() == "light"


def resolve_color(token: ColorToken, mode: Optional[str] = None) -> str:
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
