"""
Sono Alt Stüdyo Oynatıcı Konsolu (AudioPanel) ve Paragraf İlerleme Çubuğu (SegmentedParagraphTrack).
- Paragraf kelime sayısına orantılı segmentli ilerleme çubuğu (SegmentedParagraphTrack)
- Vektör transport düğmeleri (Önceki · Oynat/Duraklat · Sonraki)
- Tabular Cascadia Mono süre sayaçları
- Uyku zamanlayıcısı rozeti, hız ve ses seçici hapları (pill)
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from services.tts_service import TTSService
from ui.animations import AcousticWaveformCanvas
from ui.icons import get_icon
from ui.theme import (
    ACCENT_COLOR,
    ACCENT_SOFT_TEXT,
    CARD_BG,
    CARD_BORDER,
    DIVIDER_COLOR,
    PLAYER_BG,
    PRIMARY_BTN_BG,
    PRIMARY_BTN_HOVER,
    PRIMARY_BTN_TEXT,
    SECONDARY_BTN,
    SLIDER_TRACK,
    STOP_BTN_TEXT,
    TEXT_MAIN,
    TEXT_MUTED,
    TEXT_SUBTLE,
    mono_font,
    register_theme_listener,
    resolve_color,
    ui_font,
    unregister_theme_listener,
)


class SegmentedParagraphTrack(tk.Canvas):
    """Paragraf kelime sayısına göre bölünmüş yatay ilerleme çubuğu."""

    _BAR_HEIGHT = 4.0
    _GAP = 3.0
    _PAD_X = 9.0
    _KNOB_RADIUS = 6.0
    _KNOB_HALO = 3.0

    def __init__(
        self,
        master,
        on_click: Optional[Callable[[int], None]] = None,
        height: int = 32,
        **kwargs,
    ):
        super().__init__(
            master,
            height=height,
            bg=resolve_color(PLAYER_BG),
            highlightthickness=0,
            bd=0,
            cursor="hand2" if on_click else "",
            **kwargs,
        )
        self._on_click = on_click
        self._height = float(height)
        self._word_counts: list[int] = []
        self._current_index: int = -1
        self._fraction: float = 0.0
        self._bar_ranges: list[tuple[float, float]] = []

        self.bind("<Configure>", lambda _e: self._redraw(), add="+")
        self.bind("<Button-1>", self._handle_click)
        self.bind("<Destroy>", self._on_destroy, add="+")
        register_theme_listener(self._on_theme_change)
        self._redraw()

    def set_segments(self, word_counts: list[int]) -> None:
        self._word_counts = [max(1, int(wc)) for wc in word_counts]
        self._current_index = -1
        self._fraction = 0.0
        self._redraw()

    def set_current(self, index: int, fraction: float) -> None:
        self._current_index = int(index)
        self._fraction = max(0.0, min(1.0, float(fraction)))
        self._redraw()

    def reset(self) -> None:
        self._current_index = -1
        self._fraction = 0.0
        self._redraw()

    def _on_theme_change(self, _mode: str) -> None:
        try:
            if not self.winfo_exists():
                unregister_theme_listener(self._on_theme_change)
                return
            self.configure(bg=resolve_color(PLAYER_BG))
            self._redraw()
        except Exception:
            unregister_theme_listener(self._on_theme_change)

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            unregister_theme_listener(self._on_theme_change)

    def _handle_click(self, event) -> None:
        if not self._bar_ranges or not self._on_click:
            return
        x = float(event.x)
        for idx, (x0, x1) in enumerate(self._bar_ranges):
            if x0 <= x <= x1:
                self._on_click(idx)
                return

        def _dist(i: int) -> float:
            x0, x1 = self._bar_ranges[i]
            if x0 <= x <= x1:
                return 0.0
            return min(abs(x - x0), abs(x - x1))

        nearest_idx = min(range(len(self._bar_ranges)), key=_dist)
        self._on_click(nearest_idx)

    def _draw_pill_bar(self, x0: float, x1: float, cy: float, color: str) -> None:
        bw = x1 - x0
        if bw <= 0.5:
            return
        if bw >= self._BAR_HEIGHT:
            r = self._BAR_HEIGHT / 2.0
            self.create_line(
                x0 + r,
                cy,
                x1 - r,
                cy,
                fill=color,
                width=self._BAR_HEIGHT,
                capstyle=tk.ROUND,
            )
        else:
            half_h = self._BAR_HEIGHT / 2.0
            self.create_rectangle(
                x0,
                cy - half_h,
                x1,
                cy + half_h,
                fill=color,
                outline="",
            )

    def _redraw(self) -> None:
        if not self.winfo_exists():
            return
        self.delete("all")
        self._bar_ranges.clear()

        w = float(self.winfo_width())
        h = float(self.winfo_height())
        if w <= 2:
            w = 200.0
        if h <= 2:
            h = self._height

        cy = h / 2.0
        pad_x = self._PAD_X if w > self._PAD_X * 4 else 2.0
        avail_w = max(4.0, w - 2.0 * pad_x)

        player_bg = resolve_color(PLAYER_BG)
        track_col = resolve_color(SLIDER_TRACK)
        done_col = resolve_color(TEXT_SUBTLE)
        accent_col = resolve_color(ACCENT_COLOR)
        knob_col = resolve_color(TEXT_MAIN)

        n = len(self._word_counts)
        if n == 0:
            self._draw_pill_bar(pad_x, pad_x + avail_w, cy, track_col)
            return

        total_gap_space = (n - 1) * self._GAP
        if total_gap_space >= avail_w - n:
            gap = max(0.0, (avail_w - n) / max(1, n - 1)) if n > 1 else 0.0
        else:
            gap = self._GAP

        bars_total_w = max(float(n), avail_w - (n - 1) * gap)
        total_weight = float(sum(self._word_counts))

        knob_pos_x: Optional[float] = None
        cursor_x = pad_x
        right_limit = pad_x + avail_w

        for i, wc in enumerate(self._word_counts):
            if i == n - 1:
                x0 = cursor_x
                x1 = max(x0 + 1.0, right_limit)
            else:
                bar_w = bars_total_w * (wc / total_weight)
                x0 = cursor_x
                x1 = x0 + max(1.0, bar_w)
                cursor_x = x1 + gap

            self._bar_ranges.append((x0, x1))

            if i < self._current_index:
                self._draw_pill_bar(x0, x1, cy, done_col)
            elif i == self._current_index:
                self._draw_pill_bar(x0, x1, cy, track_col)
                fill_x = x0 + (x1 - x0) * self._fraction
                if self._fraction > 0.0:
                    self._draw_pill_bar(x0, fill_x, cy, accent_col)
                knob_pos_x = fill_x
            else:
                self._draw_pill_bar(x0, x1, cy, track_col)

        if knob_pos_x is not None:
            outer_r = self._KNOB_RADIUS + self._KNOB_HALO
            self.create_oval(
                knob_pos_x - outer_r,
                cy - outer_r,
                knob_pos_x + outer_r,
                cy + outer_r,
                fill=player_bg,
                outline="",
            )
            r = self._KNOB_RADIUS
            self.create_oval(
                knob_pos_x - r,
                cy - r,
                knob_pos_x + r,
                cy + r,
                fill=knob_col,
                outline="",
            )


class AudioPanel(ctk.CTkFrame):
    """Hi-Fi Stüdyo Alt Medya Oynatıcı Konsolu."""

    SPEED_OPTIONS: list[tuple[str, float]] = [
        ("0.5×", 0.5),
        ("0.75×", 0.75),
        ("1.0×", 1.0),
        ("1.25×", 1.25),
        ("1.5×", 1.5),
        ("1.75×", 1.75),
        ("2.0×", 2.0),
    ]

    def __init__(
        self,
        master,
        tts_service: TTSService,
        on_stop=None,
        on_play_request=None,
        on_seek_paragraph=None,
        settings=None,
        **kwargs,
    ):
        super().__init__(
            master,
            corner_radius=0,
            fg_color=PLAYER_BG,
            border_width=0,
            height=80,
            **kwargs,
        )
        self.tts = tts_service
        self._on_stop_cb = on_stop
        self._on_play_request_cb = on_play_request
        self._on_seek_paragraph_cb = on_seek_paragraph
        self._has_text = False
        self.settings = settings
        self._is_seeking = False
        self._total_est_sec = 0
        self._last_nonzero_vol = 100
        self._vol_save_after = None
        self._current_para_index = -1
        self._speed_map = dict(self.SPEED_OPTIONS)

        # Çift temalı Lucide ikonları
        self._ic_prev = get_icon("skip-back", size=16, color=TEXT_MUTED, stroke_width=1.5)
        self._ic_next = get_icon("skip-forward", size=16, color=TEXT_MUTED, stroke_width=1.5)
        self._ic_pause = get_icon("pause", size=18, color=PRIMARY_BTN_TEXT, stroke_width=1.5, filled=True)
        self._ic_play = get_icon("play", size=18, color=PRIMARY_BTN_TEXT, stroke_width=1.5, filled=True)
        self._ic_stop = get_icon("square", size=13, color=STOP_BTN_TEXT, stroke_width=1.5, filled=True)
        self._vol_icon_on = get_icon("volume-2", size=16, color=TEXT_MUTED, stroke_width=1.5)
        self._vol_icon_mute = get_icon("volume-x", size=16, color=STOP_BTN_TEXT, stroke_width=1.5)
        self._ic_sleep = get_icon("moon-star", size=13, color=ACCENT_SOFT_TEXT, stroke_width=1.5)
        self._ic_sleep_wait = get_icon("moon-star", size=13, color=TEXT_MUTED, stroke_width=1.5)

        self._setup_ui()
        self._restore_saved_settings()

    def _setup_ui(self) -> None:
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 1px üst ayırıcı çizgi
        self._top_divider = ctk.CTkFrame(
            self,
            height=1,
            corner_radius=0,
            border_width=0,
            fg_color=DIVIDER_COLOR,
        )
        self._top_divider.grid(row=0, column=0, sticky="ew")

        # Ana oynatıcı satırı (CSS .player: padding 0 32px, gap 20px)
        player_row = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        player_row.grid(row=1, column=0, padx=32, sticky="nsew")
        player_row.grid_rowconfigure(0, weight=1)
        player_row.grid_columnconfigure(2, weight=1)

        # ── 1. Sol: Transport Düğmeleri (.ctl) ──
        controls_frame = ctk.CTkFrame(player_row, fg_color="transparent")
        controls_frame.grid(row=0, column=0, padx=(0, 20), sticky="w")

        self.prev_btn = ctk.CTkButton(
            controls_frame,
            text="",
            image=self._ic_prev,
            width=32,
            height=32,
            command=self._prev_paragraph,
            state="disabled",
            fg_color="transparent",
            hover_color=SECONDARY_BTN,
            corner_radius=8,
        )
        self.prev_btn.pack(side="left", padx=(0, 6))

        self.pause_btn = ctk.CTkButton(
            controls_frame,
            text="",
            image=self._ic_play,
            width=44,
            height=44,
            command=self._toggle_pause,
            state="disabled",
            fg_color=PRIMARY_BTN_BG,
            hover_color=PRIMARY_BTN_HOVER,
            corner_radius=22,
        )
        self.pause_btn.pack(side="left", padx=(0, 6))

        self.next_btn = ctk.CTkButton(
            controls_frame,
            text="",
            image=self._ic_next,
            width=32,
            height=32,
            command=self._next_paragraph,
            state="disabled",
            fg_color="transparent",
            hover_color=SECONDARY_BTN,
            corner_radius=8,
        )
        self.next_btn.pack(side="left")

        # ── 2. Geçen Süre (.time.mono) ──
        self.cur_time_lbl = ctk.CTkLabel(
            player_row,
            text="0:00",
            font=mono_font(12),
            text_color=TEXT_SUBTLE,
            width=44,
            anchor="w",
        )
        self.cur_time_lbl.grid(row=0, column=1, padx=(0, 20), sticky="w")

        # ── 3. Segmentli Paragraf İlerleme Çubuğu (.track) ──
        self.track = SegmentedParagraphTrack(
            player_row,
            on_click=self._on_track_segment_click,
            height=32,
        )
        self.track.grid(row=0, column=2, padx=(0, 20), sticky="ew")

        # ── 4. Toplam Süre (.time.r.mono) ──
        self.total_time_lbl = ctk.CTkLabel(
            player_row,
            text="0:00",
            font=mono_font(12),
            text_color=TEXT_SUBTLE,
            width=44,
            anchor="e",
        )
        self.total_time_lbl.grid(row=0, column=3, padx=(0, 20), sticky="e")

        # ── 5. Sağ: Uyku Rozeti, Hız Hapı, Ses/Sessize Al + Ses Seçici Hapı ──
        right_frame = ctk.CTkFrame(player_row, fg_color="transparent")
        right_frame.grid(row=0, column=4, sticky="e")

        self.sleep_pill = ctk.CTkLabel(
            right_frame,
            text="",
            image=self._ic_sleep,
            compound="left",
            font=mono_font(11),
            text_color=TEXT_MUTED,
            fg_color="transparent",
            padx=4,
            pady=2,
        )

        # Hız Hapı (.pill.mono)
        self._speed_pill = ctk.CTkFrame(
            right_frame,
            height=32,
            corner_radius=8,
            border_width=1,
            border_color=CARD_BORDER,
            fg_color=PLAYER_BG,
        )
        self._speed_pill.pack(side="left", padx=(0, 12))

        self.speed_dropdown = ctk.CTkOptionMenu(
            self._speed_pill,
            values=[label for label, _ in self.SPEED_OPTIONS],
            command=self._on_speed_change,
            width=74,
            height=28,
            font=mono_font(12),
            fg_color=PLAYER_BG,
            button_color=PLAYER_BG,
            button_hover_color=SECONDARY_BTN,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SECONDARY_BTN,
            dropdown_text_color=TEXT_MAIN,
            text_color=TEXT_MAIN,
            corner_radius=6,
            dynamic_resizing=False,
        )
        self.speed_dropdown.set("1.0×")
        self.speed_dropdown.pack(padx=2, pady=2)

        # Ses Seçici + Sessize Al Hapı (.pill)
        self.voice_map = {
            "TR  Emel · Kadın": "tr-TR-EmelNeural",
            "TR  Ahmet · Erkek": "tr-TR-AhmetNeural",
            "EN  Jenny · Kadın": "en-US-JennyNeural",
            "EN  Guy · Erkek": "en-US-GuyNeural",
            "DE  Katja · Kadın": "de-DE-KatjaNeural",
            "FR  Denise · Kadın": "fr-FR-DeniseNeural",
            "ES  Elvira · Kadın": "es-ES-ElviraNeural",
        }

        self._voice_pill = ctk.CTkFrame(
            right_frame,
            height=32,
            corner_radius=8,
            border_width=1,
            border_color=CARD_BORDER,
            fg_color=PLAYER_BG,
        )
        self._voice_pill.pack(side="left")

        self.mute_btn = ctk.CTkButton(
            self._voice_pill,
            text="",
            image=self._vol_icon_on,
            width=28,
            height=28,
            fg_color="transparent",
            hover_color=SECONDARY_BTN,
            corner_radius=6,
            command=self._toggle_mute,
        )
        self.mute_btn.pack(side="left", padx=(3, 0), pady=2)

        self.voice_dropdown = ctk.CTkOptionMenu(
            self._voice_pill,
            values=list(self.voice_map.keys()),
            command=self._on_voice_change,
            width=152,
            height=28,
            font=ui_font(12),
            fg_color=PLAYER_BG,
            button_color=PLAYER_BG,
            button_hover_color=SECONDARY_BTN,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SECONDARY_BTN,
            dropdown_text_color=TEXT_MAIN,
            text_color=TEXT_MAIN,
            corner_radius=6,
            dynamic_resizing=False,
        )
        self.voice_dropdown.set("TR  Emel · Kadın")
        self.voice_dropdown.pack(side="left", padx=(0, 2), pady=2)

        # ── Geriye Uyumluluk İçin Gizli (Gridlenmemiş) Bileşenler ──
        self.stop_btn = ctk.CTkButton(
            self,
            text="",
            image=self._ic_stop,
            width=1,
            height=1,
            command=self._stop,
            state="disabled",
            fg_color="transparent",
        )
        self.waveform = AcousticWaveformCanvas(
            self,
            width=1,
            height=1,
            bars=4,
            bg_token=PLAYER_BG,
        )
        self.track_slider = ctk.CTkSlider(
            self,
            from_=0,
            to=100,
            width=1,
            height=1,
        )
        self.track_slider.set(0)
        self.vol_slider = ctk.CTkSlider(
            self,
            from_=0,
            to=100,
            width=1,
            height=1,
            command=self._on_volume_change,
        )
        self.vol_slider.set(100)

    # ── Kontrol Aksiyonları ────────────────────────────────────────

    def _on_track_segment_click(self, index: int) -> None:
        if self._on_seek_paragraph_cb:
            self._on_seek_paragraph_cb(index)

    def set_segments(self, word_counts: list[int]) -> None:
        self._current_para_index = -1
        self.track.set_segments(word_counts)

    def set_para_fraction(self, fraction: float) -> None:
        if self._current_para_index >= 0:
            self.track.set_current(self._current_para_index, fraction)

    def set_has_text(self, has_text: bool) -> None:
        self._has_text = bool(has_text)
        if not (self.tts.is_playing or self.tts.is_paused):
            self.pause_btn.configure(
                image=self._ic_play,
                state="normal" if self._has_text else "disabled",
            )

    def _toggle_pause(self) -> None:
        if not (self.tts.is_playing or self.tts.is_paused):
            if self._on_play_request_cb:
                self._on_play_request_cb()
            return
        if self.tts.is_paused:
            self.tts.resume()
            self.pause_btn.configure(image=self._ic_pause)
        else:
            self.tts.pause()
            self.pause_btn.configure(image=self._ic_play)

    def _stop(self) -> None:
        self.tts.stop()
        self.pause_btn.configure(image=self._ic_play, state="normal" if self._has_text else "disabled")
        self.stop_btn.configure(state="disabled")
        self.prev_btn.configure(state="disabled")
        self.next_btn.configure(state="disabled")
        self._current_para_index = -1
        self.track.reset()
        self.track_slider.set(0)
        self.cur_time_lbl.configure(text="0:00")
        self.total_time_lbl.configure(text="0:00")
        if self._on_stop_cb:
            self._on_stop_cb()

    def _prev_paragraph(self) -> None:
        self.tts.previous_paragraph()

    def _next_paragraph(self) -> None:
        self.tts.next_paragraph()

    def _speed_to_label(self, speed_f: float) -> str:
        closest_label, _ = min(
            self.SPEED_OPTIONS, key=lambda item: abs(item[1] - speed_f)
        )
        return closest_label

    def _restore_saved_settings(self) -> None:
        if not self.settings:
            return

        # 1) Kayıtlı ses
        saved_voice = self.settings.get_audio("voice", "tr-TR-EmelNeural")
        display_voice = next(
            (disp for disp, raw in self.voice_map.items() if raw == saved_voice),
            None,
        )
        if display_voice is None and saved_voice in self.voice_map:
            display_voice = saved_voice
            saved_voice = self.voice_map[display_voice]
        if display_voice:
            self.voice_dropdown.set(display_voice)
            self.tts._voice = saved_voice

        # 2) Kayıtlı hız
        try:
            saved_speed = float(self.settings.get_audio("speed", 1.0))
        except (TypeError, ValueError):
            saved_speed = 1.0
        speed_label = self._speed_to_label(saved_speed)
        speed_val = self._speed_map[speed_label]
        self.speed_dropdown.set(speed_label)
        self.waveform.set_playback_params(speed=speed_val)
        self.tts.set_rate(int(round((speed_val - 1.0) * 100)))

        # 3) Kayıtlı ses seviyesi
        try:
            saved_vol = int(round(float(self.settings.get_audio("volume", 100))))
        except (TypeError, ValueError):
            saved_vol = 100
        saved_vol = max(0, min(100, saved_vol))
        if saved_vol > 0:
            self._last_nonzero_vol = saved_vol
        self.vol_slider.set(saved_vol)
        self.mute_btn.configure(
            image=self._vol_icon_on if saved_vol > 0 else self._vol_icon_mute
        )
        self.waveform.set_playback_params(volume=saved_vol / 100.0)
        self.tts.set_volume(saved_vol / 100.0)

    def _on_speed_change(self, speed_label: str) -> None:
        speed_f = self._speed_map.get(speed_label)
        if speed_f is None:
            try:
                speed_f = float(speed_label.replace("×", "").replace("x", "").strip())
            except (TypeError, ValueError):
                speed_f = 1.0
        self.waveform.set_playback_params(speed=speed_f)
        self.tts.set_rate(int(round((speed_f - 1.0) * 100)))
        if self.settings:
            self.settings.set_audio("speed", speed_f)

    def _toggle_mute(self) -> None:
        cur = int(round(self.vol_slider.get()))
        if cur > 0:
            self._last_nonzero_vol = cur
            self.vol_slider.set(0)
            self._on_volume_change(0)
            self._save_volume_now(0)
        else:
            restore = self._last_nonzero_vol if self._last_nonzero_vol > 0 else 100
            self.vol_slider.set(restore)
            self._on_volume_change(restore)
            self._save_volume_now(restore)

    def _save_volume_now(self, vol: int) -> None:
        if self._vol_save_after is not None:
            try:
                self.after_cancel(self._vol_save_after)
            except Exception:
                pass
            self._vol_save_after = None
        if self.settings:
            self.settings.set_audio("volume", max(0, min(100, int(vol))))

    def _on_volume_release(self, _event=None) -> None:
        self._save_volume_now(int(round(self.vol_slider.get())))

    def _on_volume_change(self, value: float) -> None:
        vol = int(round(value))
        if vol > 0:
            self._last_nonzero_vol = vol
            self.mute_btn.configure(image=self._vol_icon_on)
        else:
            self.mute_btn.configure(image=self._vol_icon_mute)
        self.waveform.set_playback_params(volume=vol / 100.0)
        self.tts.set_volume(vol / 100.0)
        if self.settings:
            if self._vol_save_after is not None:
                try:
                    self.after_cancel(self._vol_save_after)
                except Exception:
                    pass
            self._vol_save_after = self.after(
                250, lambda v=vol: self._save_volume_now(v)
            )

    def _on_voice_change(self, voice_display: str) -> None:
        raw_voice = self.voice_map.get(voice_display, "tr-TR-EmelNeural")
        self.tts._voice = raw_voice
        if self.settings:
            self.settings.set_audio("voice", raw_voice)

    # ── Dışarıdan UI Güncellemeleri ───────────────────────────────

    def set_sleep_badge(self, text: str = "", active: bool = False) -> None:
        clean = (text or "").replace("🌙", "").strip()
        if not clean:
            self.sleep_pill.pack_forget()
            return
        self.sleep_pill.configure(
            text=f" {clean}",
            image=self._ic_sleep if active else self._ic_sleep_wait,
            text_color=ACCENT_SOFT_TEXT if active else TEXT_MUTED,
            fg_color="transparent",
        )
        self.sleep_pill.pack(side="left", padx=(0, 12), before=self._speed_pill)

    def update_time(self, elapsed_sec: int, total_sec: int, pct: float) -> None:
        total_s = max(0, int(total_sec))
        self._total_est_sec = max(1, total_s)
        t_min, t_s = divmod(total_s, 60)
        self.total_time_lbl.configure(text=f"{t_min}:{t_s:02d}")
        c_min, c_s = divmod(max(0, int(elapsed_sec)), 60)
        self.cur_time_lbl.configure(text=f"{c_min}:{c_s:02d}")

    def update_progress(self, current: int, total: int) -> None:
        self._current_para_index = int(current)
        self.track.set_current(current, 0.0)
        self.pause_btn.configure(
            image=self._ic_play if self.tts.is_paused else self._ic_pause,
            state="normal",
        )
        self.stop_btn.configure(state="normal")
        self.prev_btn.configure(state="normal" if current > 0 else "disabled")
        self.next_btn.configure(state="normal" if current < total - 1 else "disabled")

    def on_playback_complete(self) -> None:
        self.pause_btn.configure(
            image=self._ic_play,
            state="normal" if self._has_text else "disabled",
        )
        self.stop_btn.configure(state="disabled")
        self.prev_btn.configure(state="disabled")
        self.next_btn.configure(state="disabled")
        self._current_para_index = len(self.track._word_counts)
        self.track.set_current(len(self.track._word_counts), 0.0)
