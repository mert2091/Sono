"""
Sono Özgün Stüdyo Animasyon Motoru (`ui/animations.py`).

Tema duyarlı (Açık & Koyu), HiDPI uyumlu ve `reduced_motion` tercihine saygılı
60 FPS özel Tkinter Canvas animasyon bileşenleri:
- AcousticWaveformCanvas: Alt oynatıcıda canlı, hız ve ses seviyesine duyarlı akustik dalga formu
- StudioDropzoneBackdrop: Kesik çizgili belge alanı, hover akustik halkaları ve canlı OCR tarama ışını
- AcousticProgressRibbon: AI işlemleri (OCR, çeviri, özet, MP3) için akıcı ilerleme/parıltı şeridi
- LivePulseDot: 2.4 sn sakin canlı halka göstergesi (Gemini durumu / aktif ses)
- SlidingTabBar: 200 ms ease-out kayan gösterge çubuklu modern sekme şeridi
- animate_window_slide_in: Pano bildirimi için yumuşak giriş animasyonu
"""

from __future__ import annotations

import math
import time
import tkinter as tk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from ui.theme import (
    ACCENT_COLOR,
    ACCENT_GLOW,
    CARD_BG,
    CARD_BORDER,
    DASHED_BORDER,
    INNER_BG,
    PLAYER_BG,
    STOP_BTN_TEXT,
    SUCCESS_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
    WAVE_ACTIVE,
    WAVE_IDLE,
    WAVE_PEAK,
    ColorToken,
    hex_blend,
    is_reduced_motion,
    register_theme_listener,
    resolve_color,
    ui_font,
    unregister_theme_listener,
)


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _ease_in_out_sine(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


# ============================================================
# 1. CANLI AKUSTİK DALGA FORMU (ALT OYNATICI)
# ============================================================

class AcousticWaveformCanvas(tk.Canvas):
    """
    Sono'ya özgün 22 çubuklu akustik dalga formu görselleştiricisi.
    Oynatma hızı (0.5x-2.0x) ve ses seviyesine (0-100%) anlık tepki verir;
    boşta veya duraklatıldığında CPU harcamadan sakin duruşa geçer.
    """

    def __init__(
        self,
        master,
        width: int = 128,
        height: int = 34,
        bars: int = 20,
        bg_token: ColorToken = PLAYER_BG,
        on_click: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        self._bg_token = bg_token
        self._bars_count = bars
        self._on_click = on_click
        self._width_px = width
        self._height_px = height

        super().__init__(
            master,
            width=width,
            height=height,
            bg=resolve_color(bg_token),
            highlightthickness=0,
            bd=0,
            cursor="hand2" if on_click else "",
            **kwargs,
        )

        self._state = "idle"  # idle | playing | paused
        self._speed = 1.0
        self._volume = 1.0
        self._phase = 0.0
        self._last_ts = time.monotonic()
        self._after_id: Optional[str] = None
        self._heights: List[float] = [0.14] * bars
        self._line_ids: List[int] = []

        self._init_bars()
        if on_click:
            self.bind("<Button-1>", lambda _e: on_click())
        self.bind("<Destroy>", self._on_destroy, add="+")
        register_theme_listener(self._on_theme_change)
        self._redraw_bars()

    def _init_bars(self) -> None:
        self.delete("all")
        self._line_ids.clear()
        w = self._width_px
        h = self._height_px
        mid_y = h / 2.0
        pad_x = 6
        step = (w - 2 * pad_x) / max(1, self._bars_count - 1)
        bar_w = max(2.4, min(3.4, step * 0.48))
        idle_col = resolve_color(WAVE_IDLE)

        for i in range(self._bars_count):
            x = pad_x + i * step
            lid = self.create_line(
                x, mid_y - 2, x, mid_y + 2,
                fill=idle_col,
                width=bar_w,
                capstyle=tk.ROUND,
            )
            self._line_ids.append(lid)

    def set_state(self, state: str) -> None:
        """Durumu değiştir: 'idle' | 'playing' | 'paused'."""
        if state not in ("idle", "playing", "paused"):
            state = "idle"
        self._state = state
        self._last_ts = time.monotonic()
        if is_reduced_motion():
            self._apply_static_state()
            return
        self._ensure_loop()

    def set_playback_params(self, speed: Optional[float] = None, volume: Optional[float] = None) -> None:
        if speed is not None:
            self._speed = max(0.5, min(2.0, float(speed)))
        if volume is not None:
            self._volume = max(0.0, min(1.0, float(volume)))

    def _apply_static_state(self) -> None:
        self._stop_loop()
        for i in range(self._bars_count):
            env = math.sin(math.pi * (i + 0.5) / self._bars_count)
            if self._state == "playing":
                self._heights[i] = 0.22 + 0.52 * env * (0.4 + 0.6 * self._volume)
            elif self._state == "paused":
                self._heights[i] = 0.16 + 0.24 * env
            else:
                self._heights[i] = 0.12 + 0.08 * env
        self._redraw_bars()

    def _ensure_loop(self) -> None:
        if self._after_id is None:
            self._after_id = self.after(24, self._tick)

    def _stop_loop(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick(self) -> None:
        self._after_id = None
        if not self.winfo_exists():
            return
        if is_reduced_motion():
            self._apply_static_state()
            return

        now = time.monotonic()
        dt = min(0.06, max(0.008, now - self._last_ts))
        self._last_ts = now

        settled = True
        if self._state == "playing":
            self._phase += dt * (4.6 * self._speed)
            vol_gain = 0.18 + 0.82 * self._volume if self._volume > 0.01 else 0.08
            for i in range(self._bars_count):
                norm = (i + 0.5) / self._bars_count
                env = math.sin(math.pi * norm) ** 0.85
                w1 = math.sin(self._phase * 1.15 + i * 0.62)
                w2 = math.sin(self._phase * 2.05 - i * 0.91) * 0.52
                w3 = math.cos(self._phase * 0.72 + i * 1.33) * 0.34
                energy = (w1 + w2 + w3 + 1.86) / 3.72  # 0..1
                target = 0.12 + env * vol_gain * (0.20 + 0.76 * energy)
                self._heights[i] += (target - self._heights[i]) * min(1.0, dt * 16.0)
            settled = False
        else:
            for i in range(self._bars_count):
                env = math.sin(math.pi * (i + 0.5) / self._bars_count)
                target = (0.14 + 0.16 * env) if self._state == "paused" else (0.10 + 0.07 * env)
                diff = target - self._heights[i]
                if abs(diff) > 0.006:
                    self._heights[i] += diff * min(1.0, dt * 10.0)
                    settled = False
                else:
                    self._heights[i] = target

        self._redraw_bars()
        if not settled:
            self._after_id = self.after(24, self._tick)

    def _redraw_bars(self) -> None:
        h = self._height_px
        mid_y = h / 2.0
        max_half = (h - 8) / 2.0
        pad_x = 6
        step = (self._width_px - 2 * pad_x) / max(1, self._bars_count - 1)

        c_idle = resolve_color(WAVE_IDLE)
        c_act = resolve_color(WAVE_ACTIVE)
        c_peak = resolve_color(WAVE_PEAK)

        for i, lid in enumerate(self._line_ids):
            val = max(0.08, min(1.0, self._heights[i]))
            half = max(1.8, val * max_half)
            x = pad_x + i * step
            self.coords(lid, x, mid_y - half, x, mid_y + half)

            if self._state == "playing" and self._volume > 0.01:
                col = hex_blend(c_act, c_peak, max(0.0, (val - 0.55) / 0.45))
            elif self._state == "paused":
                col = hex_blend(c_idle, c_act, 0.45)
            else:
                col = c_idle
            self.itemconfigure(lid, fill=col)

    def _on_theme_change(self, _mode: str) -> None:
        if not self.winfo_exists():
            return
        self.configure(bg=resolve_color(self._bg_token))
        self._redraw_bars()

    def _on_destroy(self, _event=None) -> None:
        self._stop_loop()
        unregister_theme_listener(self._on_theme_change)


# ============================================================
# 2. BELGE BIRAKMA ARKA PLANI & CANLI OCR TARAMA IŞINI
# ============================================================

class StudioDropzoneBackdrop(tk.Canvas):
    """
    Belge alanının arkasında yuvarlatılmış kesik çerçeve, hover akustik halkaları
    ve Gemini OCR çalışırken akıcı bir tarama ışını (scan beam) çizer.
    """

    def __init__(self, master, bg_token: ColorToken = INNER_BG, **kwargs):
        self._bg_token = bg_token
        super().__init__(
            master,
            bg=resolve_color(bg_token),
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self._hovered = False
        self._scanning = False
        self._phase = 0.0
        self._last_ts = time.monotonic()
        self._after_id: Optional[str] = None

        self.bind("<Configure>", self._redraw_all)
        self.bind("<Destroy>", self._on_destroy, add="+")
        register_theme_listener(self._on_theme_change)

    def set_hovered(self, hovered: bool) -> None:
        if self._hovered == hovered:
            return
        self._hovered = hovered
        self._redraw_border()
        if hovered and not is_reduced_motion():
            self._last_ts = time.monotonic()
            self._ensure_loop()
        elif not self._scanning:
            self._redraw_effects()

    def set_scanning(self, active: bool) -> None:
        self._scanning = bool(active)
        self._phase = 0.0
        self._last_ts = time.monotonic()
        self._redraw_border()
        if self._scanning and not is_reduced_motion():
            self._ensure_loop()
        else:
            self.delete("scan")
            self._redraw_effects()

    def _ensure_loop(self) -> None:
        if self._after_id is None:
            self._after_id = self.after(24, self._tick)

    def _stop_loop(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick(self) -> None:
        self._after_id = None
        if not self.winfo_exists():
            return
        if is_reduced_motion() or (not self._hovered and not self._scanning):
            self.delete("scan")
            self.delete("halo")
            return

        now = time.monotonic()
        dt = min(0.06, max(0.01, now - self._last_ts))
        self._last_ts = now
        self._phase += dt
        self._redraw_effects()
        self._after_id = self.after(24, self._tick)

    def _redraw_all(self, _event=None) -> None:
        self._redraw_border()
        self._redraw_effects()

    def _redraw_border(self) -> None:
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 24 or h < 24:
            return
        self.delete("dash_border")
        pad = 3
        r = 12
        x1, y1, x2, y2 = pad, pad, w - pad, h - pad
        pts = [
            x1 + r, y1, x2 - r, y1,
            x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1,
            x1 + r, y1,
        ]
        if self._scanning or self._hovered:
            col = resolve_color(ACCENT_COLOR)
            dash = (8, 4) if self._scanning else (6, 4)
            width = 1.8
        else:
            col = resolve_color(DASHED_BORDER)
            dash = (6, 5)
            width = 1.4

        self.create_line(
            pts,
            smooth=True,
            fill=col,
            width=width,
            dash=dash,
            tags="dash_border",
        )

    def _redraw_effects(self) -> None:
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 40 or h < 40:
            return

        bg = resolve_color(self._bg_token)
        accent = resolve_color(ACCENT_COLOR)
        glow = resolve_color(ACCENT_GLOW)

        # 1) Sakin mimari akustik halkalar (boşta çok hafif, hover'da canlanan)
        self.delete("halo")
        cx, cy = w / 2.0, h * 0.40
        if self._hovered and not self._scanning and not is_reduced_motion():
            max_r = min(w, h) * 0.36
            for k in range(2):
                prog = (self._phase * 0.42 + k * 0.5) % 1.0
                rad = 30 + prog * max_r
                alpha = (1.0 - prog) * 0.32
                ring_col = hex_blend(bg, accent, alpha)
                self.create_oval(
                    cx - rad, cy - rad, cx + rad, cy + rad,
                    outline=ring_col,
                    width=1.4,
                    tags="halo",
                )
        elif not self._scanning:
            for rad, alpha in ((56, 0.11), (92, 0.06)):
                self.create_oval(
                    cx - rad, cy - rad, cx + rad, cy + rad,
                    outline=hex_blend(bg, accent, alpha),
                    width=1.0,
                    tags="halo",
                )

        # 2) Canlı Gemini OCR tarama ışını
        self.delete("scan")
        if self._scanning and not is_reduced_motion():
            cycle = (self._phase / 1.9) % 2.0
            t = cycle if cycle <= 1.0 else (2.0 - cycle)
            y = 14 + _ease_in_out_sine(t) * max(20, h - 28)
            direction = 1 if cycle <= 1.0 else -1

            # Yumuşak trailing glow şeritleri
            for step in range(1, 7):
                ty = y - direction * step * 5
                if 8 < ty < h - 8:
                    fade = max(0.0, (1.0 - step / 7.0) * 0.24)
                    self.create_line(
                        12, ty, w - 12, ty,
                        fill=hex_blend(bg, glow, fade),
                        width=4,
                        tags="scan",
                    )
            # Keskin ana tarama çizgisi
            self.create_line(
                10, y, w - 10, y,
                fill=accent,
                width=2,
                tags="scan",
            )

    def _on_theme_change(self, _mode: str) -> None:
        if not self.winfo_exists():
            return
        self.configure(bg=resolve_color(self._bg_token))
        self._redraw_all()

    def _on_destroy(self, _event=None) -> None:
        self._stop_loop()
        unregister_theme_listener(self._on_theme_change)


# ============================================================
# 3. AKUSTİK İLERLEME VE PARILTI ŞERİDİ (METİN STÜDYOSU)
# ============================================================

class AcousticProgressRibbon(tk.Canvas):
    """
    Metin Stüdyosu'nun üst kenarına entegre 3px'lik pürüzsüz etkinlik şeridi.
    0 < value < 1 iken akıcı teal shimmer koşar; 1.0'da emerald doluma geçer.
    """

    def __init__(self, master, bg_token: ColorToken = INNER_BG, height: int = 3, **kwargs):
        self._bg_token = bg_token
        super().__init__(
            master,
            height=height,
            bg=resolve_color(bg_token),
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self._value = 0.0
        self._phase = 0.0
        self._after_id: Optional[str] = None
        self._last_ts = time.monotonic()

        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Destroy>", self._on_destroy, add="+")
        register_theme_listener(self._on_theme_change)

    def set_progress(self, value: float) -> None:
        self._value = max(0.0, min(1.0, float(value)))
        self._last_ts = time.monotonic()
        if 0.0 < self._value < 1.0 and not is_reduced_motion():
            self._ensure_loop()
        else:
            self._stop_loop()
            self._draw()

    def _ensure_loop(self) -> None:
        if self._after_id is None:
            self._after_id = self.after(20, self._tick)

    def _stop_loop(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick(self) -> None:
        self._after_id = None
        if not self.winfo_exists():
            return
        if not (0.0 < self._value < 1.0) or is_reduced_motion():
            self._draw()
            return
        now = time.monotonic()
        dt = min(0.06, max(0.01, now - self._last_ts))
        self._last_ts = now
        self._phase = (self._phase + dt * 0.85) % 1.0
        self._draw()
        self._after_id = self.after(20, self._tick)

    def _draw(self) -> None:
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or self._value <= 0.0:
            return

        bg = resolve_color(self._bg_token)
        if self._value >= 1.0:
            self.create_rectangle(0, 0, w, h, fill=resolve_color(SUCCESS_COLOR), outline="")
            return

        if is_reduced_motion():
            self.create_rectangle(0, 0, int(w * self._value), h, fill=resolve_color(ACCENT_COLOR), outline="")
            return

        # Arka track
        accent = resolve_color(ACCENT_COLOR)
        glow = resolve_color(ACCENT_GLOW)
        self.create_rectangle(0, 0, w, h, fill=hex_blend(bg, accent, 0.14), outline="")

        # Kayan ışık şeridi
        seg_w = max(80, int(w * 0.28))
        pos = _ease_in_out_sine(self._phase) * (w + seg_w) - seg_w
        x1 = max(0, pos)
        x2 = min(w, pos + seg_w)
        if x2 > x1:
            self.create_rectangle(x1, 0, x2, h, fill=accent, outline="")
            cx = (x1 + x2) / 2.0
            core = seg_w * 0.28
            self.create_rectangle(
                max(x1, cx - core), 0, min(x2, cx + core), h,
                fill=glow, outline="",
            )

    def _on_theme_change(self, _mode: str) -> None:
        if not self.winfo_exists():
            return
        self.configure(bg=resolve_color(self._bg_token))
        self._draw()

    def _on_destroy(self, _event=None) -> None:
        self._stop_loop()
        unregister_theme_listener(self._on_theme_change)


# ============================================================
# 4. CANLI HALKA NOKTASI (2.4s GEMINI / DURUM GÖSTERGESİ)
# ============================================================

class LivePulseDot(tk.Canvas):
    """
    Sabit merkez noktası + 2.4 sn döngüde büyüyüp sönen canlı halka.
    `set_mode('ready' | 'busy' | 'error')` ile renk ve nabız hızını değiştirir.
    """

    def __init__(
        self,
        master,
        size: int = 16,
        bg_token: ColorToken = CARD_BG,
        on_click: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        self._size = size
        self._bg_token = bg_token
        self._mode = "ready"  # ready | busy | error
        self._phase = 0.0
        self._last_ts = time.monotonic()
        self._after_id: Optional[str] = None

        super().__init__(
            master,
            width=size,
            height=size,
            bg=resolve_color(bg_token),
            highlightthickness=0,
            bd=0,
            cursor="hand2" if on_click else "",
            **kwargs,
        )
        if on_click:
            self.bind("<Button-1>", lambda _e: on_click())
        self.bind("<Destroy>", self._on_destroy, add="+")
        register_theme_listener(self._on_theme_change)
        self._draw()
        self._start_or_stop()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._draw()
        self._start_or_stop()

    def set_bg_token(self, bg_token: ColorToken) -> None:
        self._bg_token = bg_token
        self.configure(bg=resolve_color(bg_token))
        self._draw()

    def _color_token(self) -> ColorToken:
        if self._mode == "error":
            return STOP_BTN_TEXT
        if self._mode == "busy":
            return ACCENT_COLOR
        return SUCCESS_COLOR

    def _start_or_stop(self) -> None:
        if is_reduced_motion():
            self._stop_loop()
            self._draw()
            return
        if self._after_id is None:
            self._last_ts = time.monotonic()
            self._after_id = self.after(36, self._tick)

    def _stop_loop(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick(self) -> None:
        self._after_id = None
        if not self.winfo_exists():
            return
        if is_reduced_motion():
            self._draw()
            return
        now = time.monotonic()
        dt = min(0.08, max(0.01, now - self._last_ts))
        self._last_ts = now
        period = 1.3 if self._mode == "busy" else 2.4
        self._phase = (self._phase + dt / period) % 1.0
        self._draw()
        self._after_id = self.after(36, self._tick)

    def _draw(self) -> None:
        self.delete("all")
        cx = cy = self._size / 2.0
        dot_col = resolve_color(self._color_token())
        bg = resolve_color(self._bg_token)

        if not is_reduced_motion():
            prog = _ease_out_cubic(self._phase)
            ring_r = 3.0 + prog * (self._size * 0.44 - 3.0)
            alpha = (1.0 - prog) * 0.65
            if alpha > 0.04:
                self.create_oval(
                    cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r,
                    outline=hex_blend(bg, dot_col, alpha),
                    width=1.4,
                )
        # Sabit merkez nokta
        r = 3.2
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=dot_col, outline="")

    def _on_theme_change(self, _mode: str) -> None:
        if not self.winfo_exists():
            return
        self.configure(bg=resolve_color(self._bg_token))
        self._draw()

    def _on_destroy(self, _event=None) -> None:
        self._stop_loop()
        unregister_theme_listener(self._on_theme_change)


# ============================================================
# 5. KAYAN GÖSTERGELİ SEKME ŞERİDİ (200ms EASE-OUT)
# ============================================================

class SlidingTabBar(ctk.CTkFrame):
    """
    Altında 200ms ease-out ile kayan Akustik Teal gösterge çubuğu taşıyan
    modern sekme şeridi (Metin | Çeviri | Özet | Soru-Cevap).
    """

    def __init__(
        self,
        master,
        tabs: List[str],
        on_change: Callable[[str], None],
        initial: Optional[str] = None,
        bg_token: ColorToken = CARD_BG,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._tabs = list(tabs)
        self._on_change = on_change
        self._bg_token = bg_token
        self._active = initial or (tabs[0] if tabs else "")
        self.buttons: Dict[str, ctk.CTkButton] = {}

        self._cur_x = 0.0
        self._cur_w = 0.0
        self._start_x = 0.0
        self._start_w = 0.0
        self._target_x = 0.0
        self._target_w = 0.0
        self._anim_start = 0.0
        self._anim_dur = 0.20
        self._after_id: Optional[str] = None

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")

        for name in self._tabs:
            is_act = name == self._active
            btn = ctk.CTkButton(
                row,
                text=name,
                width=max(74, len(name) * 8 + 26),
                height=32,
                font=ui_font(12, "semibold" if is_act else "normal"),
                fg_color="transparent",
                hover_color=("rgba_skip", "rgba_skip") if False else ("#EEF2F7", "#1D2431"),
                text_color=TEXT_MAIN if is_act else TEXT_MUTED,
                corner_radius=8,
                command=lambda n=name: self.select(n, notify=True),
            )
            btn.pack(side="left", padx=(0, 4))
            self.buttons[name] = btn

        self._track = tk.Canvas(
            self,
            height=3,
            bg=resolve_color(bg_token),
            highlightthickness=0,
            bd=0,
        )
        self._track.pack(fill="x", pady=(3, 0))
        self._track.bind("<Configure>", lambda _e: self._snap_to_active())
        self.bind("<Destroy>", self._on_destroy, add="+")
        register_theme_listener(self._on_theme_change)
        self.after(40, self._snap_to_active)

    def _btn_bounds(self, name: str) -> tuple[float, float]:
        btn = self.buttons.get(name)
        if not btn or not btn.winfo_exists():
            return (0.0, 0.0)
        x = float(btn.winfo_x())
        w = float(btn.winfo_width())
        inset = min(10.0, w * 0.16)
        return (x + inset, max(16.0, w - 2 * inset))

    def select(self, name: str, notify: bool = False) -> None:
        if name not in self.buttons:
            return
        changed = name != self._active
        self._active = name
        for k, btn in self.buttons.items():
            is_act = k == name
            btn.configure(
                text_color=TEXT_MAIN if is_act else TEXT_MUTED,
                font=ui_font(12, "semibold" if is_act else "normal"),
            )

        tx, tw = self._btn_bounds(name)
        if tw <= 0 or self._cur_w <= 0 or is_reduced_motion():
            self._cur_x, self._cur_w = tx, tw
            self._draw_indicator()
        else:
            self._start_x, self._start_w = self._cur_x, self._cur_w
            self._target_x, self._target_w = tx, tw
            self._anim_start = time.monotonic()
            self._start_anim()

        if notify and changed:
            self._on_change(name)

    def _snap_to_active(self) -> None:
        if not self.winfo_exists():
            return
        tx, tw = self._btn_bounds(self._active)
        if tw > 0:
            self._cur_x, self._cur_w = tx, tw
            self._draw_indicator()

    def _start_anim(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.after(14, self._tick_anim)

    def _tick_anim(self) -> None:
        self._after_id = None
        if not self.winfo_exists():
            return
        elapsed = time.monotonic() - self._anim_start
        p = _ease_out_cubic(elapsed / self._anim_dur)
        self._cur_x = self._start_x + (self._target_x - self._start_x) * p
        self._cur_w = self._start_w + (self._target_w - self._start_w) * p
        self._draw_indicator()
        if elapsed < self._anim_dur:
            self._after_id = self.after(14, self._tick_anim)

    def _draw_indicator(self) -> None:
        self._track.delete("all")
        w = self._track.winfo_width()
        if w <= 2:
            return
        # İnce taban çizgisi
        self._track.create_line(0, 2, w, 2, fill=resolve_color(CARD_BORDER), width=1)
        if self._cur_w > 2:
            self._track.create_line(
                self._cur_x, 1.5, self._cur_x + self._cur_w, 1.5,
                fill=resolve_color(ACCENT_COLOR),
                width=2.6,
                capstyle=tk.ROUND,
            )

    def _on_theme_change(self, _mode: str) -> None:
        if not self.winfo_exists():
            return
        self._track.configure(bg=resolve_color(self._bg_token))
        self._draw_indicator()

    def _on_destroy(self, _event=None) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        unregister_theme_listener(self._on_theme_change)


# ============================================================
# 6. PENCERE GİRİŞ ANİMASYONU (TOAST SLIDE-IN)
# ============================================================

def animate_window_slide_in(
    window: tk.Misc,
    width: int,
    height: int,
    target_x: int,
    target_y: int,
    offset_y: int = 22,
    duration_ms: int = 210,
) -> None:
    """Bildirim pencerelerini 210ms ease-out ile yumuşakça yerine kaydırır."""
    if is_reduced_motion():
        window.geometry(f"{width}x{height}+{target_x}+{target_y}")
        return

    start_y = target_y + offset_y
    t0 = time.monotonic()
    dur = max(0.08, duration_ms / 1000.0)
    window.geometry(f"{width}x{height}+{target_x}+{start_y}")

    def _step() -> None:
        if not window.winfo_exists():
            return
        p = _ease_out_cubic((time.monotonic() - t0) / dur)
        cy = int(round(start_y + (target_y - start_y) * p))
        try:
            window.geometry(f"{width}x{height}+{target_x}+{cy}")
        except Exception:
            return
        if p < 1.0:
            window.after(14, _step)

    window.after(12, _step)
