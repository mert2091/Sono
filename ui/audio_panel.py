"""
Sono Hi-Fi Alt Stüdyo Oynatıcı Konsolu (AudioPanel).
- Lucide vektör transport düğmeleri (Önceki · Oynat/Duraklat · Sonraki · Durdur)
- Canlı, hız ve ses seviyesine duyarlı 20 çubuklu Akustik Dalga Formu (AcousticWaveformCanvas)
- Tabular Cascadia Mono süre sayaçları ve akıcı ilerleme çubuğu
- Uyku zamanlayıcısı rozeti, hız/ses kontrolleri ve çift temalı ses seçici
"""

from __future__ import annotations

import customtkinter as ctk

from services.tts_service import TTSService
from ui.animations import AcousticWaveformCanvas
from ui.icons import get_icon
from ui.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    ACCENT_SOFT_BG,
    ACCENT_SOFT_TEXT,
    ACCENT_TEXT,
    CARD_BG,
    PADDING_CARD,
    PLAYER_BG,
    PLAYER_BORDER,
    RADIUS_BTN,
    RADIUS_CARD,
    SECONDARY_BTN,
    SECONDARY_BTN_BORDER,
    SECONDARY_BTN_HOVER,
    SLIDER_TRACK,
    STATUS_PILL_BG,
    STOP_BTN_BG,
    STOP_BTN_BORDER,
    STOP_BTN_HOVER,
    STOP_BTN_TEXT,
    SUCCESS_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
    mono_font,
    ui_font,
)


class AudioPanel(ctk.CTkFrame):
    """Hi-Fi Stüdyo Medya Oynatıcı Konsolu."""

    SPEED_OPTIONS: list[tuple[str, float]] = [
        ("0.5x", 0.5),
        ("0.75x", 0.75),
        ("1.0x", 1.0),
        ("1.25x", 1.25),
        ("1.5x", 1.5),
        ("1.75x", 1.75),
        ("2.0x", 2.0),
    ]

    def __init__(self, master, tts_service: TTSService, on_stop=None, settings=None, **kwargs):
        super().__init__(
            master,
            corner_radius=RADIUS_CARD,
            fg_color=PLAYER_BG,
            border_width=1,
            border_color=PLAYER_BORDER,
            **kwargs,
        )
        self.tts = tts_service
        self._on_stop_cb = on_stop
        self.settings = settings
        self._is_seeking = False
        self._total_est_sec = 0
        self._last_nonzero_vol = 100
        self._vol_save_after = None
        self._speed_map = dict(self.SPEED_OPTIONS)

        # Çift temalı Lucide ikonları
        self._ic_prev = get_icon("skip-back", size=16, color=TEXT_MAIN)
        self._ic_next = get_icon("skip-forward", size=16, color=TEXT_MAIN)
        self._ic_pause = get_icon("pause", size=18, color=ACCENT_TEXT, stroke_width=2.2, filled=True)
        self._ic_play = get_icon("play", size=18, color=ACCENT_TEXT, stroke_width=2.2, filled=True)
        self._ic_stop = get_icon("square", size=13, color=STOP_BTN_TEXT, stroke_width=2.0, filled=True)
        self._vol_icon_on = get_icon("volume-2", size=16, color=TEXT_MAIN)
        self._vol_icon_mute = get_icon("volume-x", size=16, color=STOP_BTN_TEXT)
        self._ic_sleep = get_icon("moon-star", size=13, color=SUCCESS_COLOR)
        self._ic_sleep_wait = get_icon("moon-star", size=13, color=ACCENT_SOFT_TEXT)

        self._setup_ui()
        self._restore_saved_settings()

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(2, weight=1)  # Orta ilerleme çubuğu esnesin

        # ── 1. Sol: Transport Düğmeleri ──
        controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        controls_frame.grid(row=0, column=0, padx=(PADDING_CARD, 10), pady=12, sticky="w")

        self.prev_btn = ctk.CTkButton(
            controls_frame,
            text="",
            image=self._ic_prev,
            width=34,
            height=34,
            command=self._prev_paragraph,
            state="disabled",
            fg_color="transparent",
            hover_color=SECONDARY_BTN,
            corner_radius=17,
        )
        self.prev_btn.pack(side="left", padx=(0, 4))

        self.pause_btn = ctk.CTkButton(
            controls_frame,
            text="",
            image=self._ic_play,
            width=46,
            height=46,
            command=self._toggle_pause,
            state="disabled",
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            corner_radius=23,
        )
        self.pause_btn.pack(side="left", padx=4)

        self.next_btn = ctk.CTkButton(
            controls_frame,
            text="",
            image=self._ic_next,
            width=34,
            height=34,
            command=self._next_paragraph,
            state="disabled",
            fg_color="transparent",
            hover_color=SECONDARY_BTN,
            corner_radius=17,
        )
        self.next_btn.pack(side="left", padx=(4, 8))

        self.stop_btn = ctk.CTkButton(
            controls_frame,
            text="",
            image=self._ic_stop,
            width=34,
            height=34,
            command=self._stop,
            state="disabled",
            fg_color=STOP_BTN_BG,
            border_width=1,
            border_color=STOP_BTN_BORDER,
            hover_color=STOP_BTN_HOVER,
            corner_radius=10,
        )
        self.stop_btn.pack(side="left")

        # ── 2. Sono İmza Akustik Dalga Formu ──
        self.waveform = AcousticWaveformCanvas(
            self,
            width=108,
            height=34,
            bars=18,
            bg_token=PLAYER_BG,
            on_click=self._on_waveform_click,
        )
        self.waveform.grid(row=0, column=1, padx=(4, 8), pady=12, sticky="w")

        # ── 3. Orta: Tabular Süre ve İlerleme Kaydırıcısı ──
        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.grid(row=0, column=2, padx=8, pady=12, sticky="ew")
        center_frame.grid_columnconfigure(1, weight=1)

        self.cur_time_lbl = ctk.CTkLabel(
            center_frame,
            text="0:00",
            font=mono_font(11),
            text_color=TEXT_MUTED,
            width=38,
        )
        self.cur_time_lbl.grid(row=0, column=0, padx=(0, 8))

        self.track_slider = ctk.CTkSlider(
            center_frame,
            from_=0,
            to=100,
            number_of_steps=200,
            progress_color=ACCENT_COLOR,
            button_color=TEXT_MAIN,
            button_hover_color=ACCENT_HOVER,
            button_length=0,
            button_corner_radius=8,
            fg_color=SLIDER_TRACK,
            height=15,
            command=self._on_track_drag,
        )
        self.track_slider.set(0)
        self.track_slider.bind("<ButtonPress-1>", self._on_track_press)
        self.track_slider.bind("<ButtonRelease-1>", self._on_track_release)
        self.track_slider.grid(row=0, column=1, sticky="ew")

        self.total_time_lbl = ctk.CTkLabel(
            center_frame,
            text="0:00",
            font=mono_font(11),
            text_color=TEXT_MUTED,
            width=38,
        )
        self.total_time_lbl.grid(row=0, column=2, padx=(8, 0))

        # ── 4. Sağ: Uyku Rozeti, Hız, Ses Seviyesi, Ses Seçici ──
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.grid(row=0, column=3, padx=(10, PADDING_CARD), pady=12, sticky="e")

        self.sleep_pill = ctk.CTkLabel(
            right_frame,
            text="",
            image=self._ic_sleep,
            compound="left",
            font=mono_font(11, "bold"),
            text_color=SUCCESS_COLOR,
            fg_color=STATUS_PILL_BG,
            corner_radius=9,
            padx=9,
            pady=4,
        )

        # Hız Seçici (Tek tıkla açılan hız kutusu)
        self._speed_lbl = ctk.CTkLabel(
            right_frame, text="Hız", font=ui_font(11), text_color=TEXT_MUTED
        )
        self._speed_lbl.pack(side="left", padx=(0, 6))

        self.speed_dropdown = ctk.CTkOptionMenu(
            right_frame,
            values=[label for label, _ in self.SPEED_OPTIONS],
            command=self._on_speed_change,
            width=86,
            height=34,
            font=mono_font(12, "bold"),
            fg_color=SECONDARY_BTN,
            button_color=SECONDARY_BTN_BORDER,
            button_hover_color=SECONDARY_BTN_HOVER,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SECONDARY_BTN,
            dropdown_text_color=TEXT_MAIN,
            text_color=TEXT_MAIN,
            corner_radius=RADIUS_BTN,
        )
        self.speed_dropdown.set("1.0x")
        self.speed_dropdown.pack(side="left", padx=(0, 10))

        # Ses / Sessize Al
        self.mute_btn = ctk.CTkButton(
            right_frame,
            text="",
            image=self._vol_icon_on,
            width=30,
            height=30,
            fg_color="transparent",
            hover_color=SECONDARY_BTN,
            corner_radius=8,
            command=self._toggle_mute,
        )
        self.mute_btn.pack(side="left", padx=(0, 3))

        self.vol_slider = ctk.CTkSlider(
            right_frame,
            from_=0,
            to=100,
            number_of_steps=20,
            width=66,
            progress_color=ACCENT_COLOR,
            button_color=TEXT_MAIN,
            button_hover_color=ACCENT_HOVER,
            button_length=0,
            button_corner_radius=7,
            fg_color=SLIDER_TRACK,
            command=self._on_volume_change,
            height=13,
        )
        self.vol_slider.set(100)
        self.vol_slider.bind("<ButtonRelease-1>", self._on_volume_release)
        self.vol_slider.pack(side="left", padx=(0, 12))

        # Ses Seçici
        self.voice_map = {
            "TR  Emel · Kadın": "tr-TR-EmelNeural",
            "TR  Ahmet · Erkek": "tr-TR-AhmetNeural",
            "EN  Jenny · Kadın": "en-US-JennyNeural",
            "EN  Guy · Erkek": "en-US-GuyNeural",
            "DE  Katja · Kadın": "de-DE-KatjaNeural",
            "FR  Denise · Kadın": "fr-FR-DeniseNeural",
            "ES  Elvira · Kadın": "es-ES-ElviraNeural",
        }

        self.voice_dropdown = ctk.CTkOptionMenu(
            right_frame,
            values=list(self.voice_map.keys()),
            command=self._on_voice_change,
            width=162,
            height=34,
            font=ui_font(12),
            fg_color=SECONDARY_BTN,
            button_color=SECONDARY_BTN_BORDER,
            button_hover_color=SECONDARY_BTN_HOVER,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SECONDARY_BTN,
            dropdown_text_color=TEXT_MAIN,
            text_color=TEXT_MAIN,
            corner_radius=RADIUS_BTN,
        )
        self.voice_dropdown.set("TR  Emel · Kadın")
        self.voice_dropdown.pack(side="left")

    # ── Kontrol Aksiyonları ────────────────────────────────────────

    def _on_waveform_click(self) -> None:
        if self.tts.is_playing or self.tts.is_paused:
            self._toggle_pause()

    def _toggle_pause(self) -> None:
        if self.tts.is_paused:
            self.tts.resume()
            self.pause_btn.configure(image=self._ic_pause)
            self.waveform.set_state("playing")
        else:
            self.tts.pause()
            self.pause_btn.configure(image=self._ic_play)
            self.waveform.set_state("paused")

    def _stop(self) -> None:
        self.tts.stop()
        self.pause_btn.configure(image=self._ic_play, state="disabled")
        self.stop_btn.configure(state="disabled")
        self.prev_btn.configure(state="disabled")
        self.next_btn.configure(state="disabled")
        self.track_slider.set(0)
        self.cur_time_lbl.configure(text="0:00")
        self.total_time_lbl.configure(text="0:00")
        self.waveform.set_state("idle")
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
        speed_f = self._speed_map.get(speed_label, 1.0)
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

    def _on_track_press(self, _event=None) -> None:
        self._is_seeking = True

    def _on_track_drag(self, value: float) -> None:
        if self._total_est_sec > 0:
            preview_sec = int((float(value) / 100.0) * self._total_est_sec)
            m, s = divmod(preview_sec, 60)
            self.cur_time_lbl.configure(text=f"{m}:{s:02d}")

    def _on_track_release(self, _event=None) -> None:
        self._is_seeking = False
        if self.tts.total_paragraphs > 0:
            ratio = float(self.track_slider.get()) / 100.0
            self.tts.seek_to_ratio(ratio)

    # ── Dışarıdan UI Güncellemeleri ───────────────────────────────

    def set_sleep_badge(self, text: str = "", active: bool = False) -> None:
        clean = (text or "").replace("🌙", "").strip()
        if not clean:
            self.sleep_pill.pack_forget()
            return
        self.sleep_pill.configure(
            text=f" {clean}",
            image=self._ic_sleep if active else self._ic_sleep_wait,
            text_color=SUCCESS_COLOR if active else ACCENT_SOFT_TEXT,
            fg_color=STATUS_PILL_BG if active else ACCENT_SOFT_BG,
        )
        self.sleep_pill.pack(side="left", padx=(0, 10), before=self._speed_lbl)

    def update_time(self, elapsed_sec: int, total_sec: int, pct: float) -> None:
        self._total_est_sec = max(1, int(total_sec))
        t_min, t_s = divmod(self._total_est_sec, 60)
        self.total_time_lbl.configure(text=f"{t_min}:{t_s:02d}")
        if not self._is_seeking:
            self.track_slider.set(max(0.0, min(100.0, float(pct))))
            c_min, c_s = divmod(max(0, int(elapsed_sec)), 60)
            self.cur_time_lbl.configure(text=f"{c_min}:{c_s:02d}")

    def update_progress(self, current: int, total: int) -> None:
        if not self._is_seeking and total > 0:
            pct = (current / total) * 100.0
            self.track_slider.set(pct)

        self.pause_btn.configure(image=self._ic_pause, state="normal")
        self.stop_btn.configure(state="normal")
        self.prev_btn.configure(state="normal" if current > 0 else "disabled")
        self.next_btn.configure(state="normal" if current < total - 1 else "disabled")
        self.waveform.set_state("paused" if self.tts.is_paused else "playing")

    def on_playback_complete(self) -> None:
        self.pause_btn.configure(image=self._ic_play, state="disabled")
        self.stop_btn.configure(state="disabled")
        self.prev_btn.configure(state="disabled")
        self.next_btn.configure(state="disabled")
        self.track_slider.set(100)
        self.waveform.set_state("idle")
