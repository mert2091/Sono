"""
TTS (Metin-Ses) Servisi.
Edge-TTS ile metin → ses dönüşümü ve pygame ile oynatma.
Ses seviyesi, hız, ses seçimi, paragraf atlama, kelime senkronizasyonu,
sonraki paragraf ön-hazırlığı (prefetch) ve MP3 dışa aktarma destekler.
"""

import asyncio
from bisect import bisect_right
import os
import re
import shutil
import tempfile
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Optional

import edge_tts
import pygame

from utils.text_utils import clean_text, normalize_for_tts_with_map


_EDGE_STRIP_PUNCT_RE = re.compile(r"^[^\w]+|[^\w]+$", re.UNICODE)


class TTSService:
    """Gelişmiş Metin-Ses dönüştürme ve oynatma servisi."""

    # Kullanılabilir sesler
    VOICES = {
        "🇹🇷 Emel (Türkçe Kadın)": "tr-TR-EmelNeural",
        "🇹🇷 Ahmet (Türkçe Erkek)": "tr-TR-AhmetNeural",
        "🇺🇸 Jenny (İngilizce Kadın)": "en-US-JennyNeural",
        "🇺🇸 Guy (İngilizce Erkek)": "en-US-GuyNeural",
        "🇩🇪 Katja (Almanca)": "de-DE-KatjaNeural",
        "🇫🇷 Denise (Fransızca)": "fr-FR-DeniseNeural",
        "🇪🇸 Elvira (İspanyolca)": "es-ES-ElviraNeural",
    }

    def __init__(self, temp_dir: Optional[str] = None):
        if temp_dir:
            self.temp_dir = temp_dir
            self._owns_temp_dir = False
            os.makedirs(self.temp_dir, exist_ok=True)
        else:
            self.temp_dir = tempfile.mkdtemp(prefix="sono_tts_")
            self._owns_temp_dir = True

        try:
            pygame.mixer.init()
        except pygame.error as e:
            print(f"Ses sistemi başlatılamadı: {e}")

        # Durum değişkenleri
        self._is_paused = False
        self._is_playing = False
        self._current_paragraph = 0
        self._paragraphs: list[str] = []
        self._volume = 1.0

        # Ayarlar
        self._voice = "tr-TR-EmelNeural"
        self._rate = "+0%"

        # Thread ve oturum kontrolü
        self._state_lock = threading.Lock()
        self._session_id = 0
        self._stop_event = threading.Event()
        self._skip_event = threading.Event()
        self._playback_thread: Optional[threading.Thread] = None
        self._pending_seek_index: Optional[int] = None
        self._prefetch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sono-tts-prefetch")

        # Callback'ler
        self._on_paragraph_change: Optional[Callable[[int], None]] = None
        self._on_word_change: Optional[Callable[[int, int, int], None]] = None
        self._on_time_tick: Optional[Callable[[int, int, float], None]] = None
        self._on_playback_complete: Optional[Callable[[], None]] = None

    # ── Ayar metotları ──────────────────────────────────────────────

    def set_voice(self, voice_display_name: str) -> None:
        """Ses tipini değiştir."""
        self._voice = self.VOICES.get(voice_display_name, "tr-TR-EmelNeural")

    def set_rate(self, rate_percent: int) -> None:
        """Okuma hızını ayarla (-50 ile +100 arası)."""
        if rate_percent >= 0:
            self._rate = f"+{rate_percent}%"
        else:
            self._rate = f"{rate_percent}%"

    def set_volume(self, volume: float) -> None:
        """Ses seviyesini ayarla (0.0 ile 1.0 arası)."""
        self._volume = max(0.0, min(1.0, volume))
        try:
            pygame.mixer.music.set_volume(self._volume)
        except Exception:
            pass

    # ── Ses üretimi ─────────────────────────────────────────────────

    async def _generate_audio(
        self, text: str, output_path: str, voice: Optional[str] = None, rate: Optional[str] = None
    ) -> None:
        """Edge-TTS ile metni ses dosyasına dönüştür."""
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice or self._voice,
            rate=rate or self._rate,
        )
        await communicate.save(output_path)

    def _generate_audio_sync(self, text: str, output_path: str) -> None:
        """Edge-TTS'i senkron çalıştır."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._generate_audio(text, output_path))
        finally:
            loop.close()

    @staticmethod
    def _map_word_boundaries_to_para(
        orig_para: str,
        tts_text: str,
        idx_map: list[int],
        raw_boundaries: list[tuple[int, str]],
    ) -> list[tuple[int, int, int]]:
        """
        Edge-TTS WordBoundary olaylarını kelime-sınırı bazlı eşleştirerek
        orijinal paragraftaki kesin (ms, baslangic, bitis) aralıklarına dönüştürür.
        Kısa kelimelerin başka kelimelerin içine kaymasını engeller.
        """
        if not tts_text or not idx_map or not raw_boundaries:
            return []

        tokens: list[tuple[int, int, str]] = []
        for m in re.finditer(r"\S+", tts_text):
            raw_tok = m.group(0)
            cleaned_tok = _EDGE_STRIP_PUNCT_RE.sub("", raw_tok).lower()
            tokens.append((m.start(), m.end(), cleaned_tok or raw_tok.lower()))

        if not tokens:
            return []

        timings: list[tuple[int, int, int]] = []
        tok_idx = 0
        sub_cursor = 0  # Tire/kesme ile bölünmüş tek bir token içinde alt imleç
        n_tokens = len(tokens)

        for offset_ms, w_raw in raw_boundaries:
            w_clean = _EDGE_STRIP_PUNCT_RE.sub("", (w_raw or "").strip()).lower()
            if not w_clean:
                continue

            matched_tts_start: Optional[int] = None
            matched_tts_end: Optional[int] = None

            # 1) Mevcut bölünmüş token içinde devam kontrolü (ör. "e-posta" -> "e", "posta")
            if tok_idx < n_tokens and sub_cursor > 0:
                t_start, t_end, _ = tokens[tok_idx]
                t_slice = tts_text[t_start:t_end].lower()
                sub_pos = t_slice.find(w_clean, sub_cursor)
                if sub_pos != -1:
                    matched_tts_start = t_start + sub_pos
                    matched_tts_end = matched_tts_start + len(w_clean)
                    if sub_pos + len(w_clean) >= len(t_slice) - 1:
                        tok_idx += 1
                        sub_cursor = 0
                    else:
                        sub_cursor = sub_pos + len(w_clean)

            # 2) İleri bakış penceresi içinde tam kelime eşleştirme
            if matched_tts_start is None:
                lookahead_end = min(n_tokens, tok_idx + 8)
                found_j: Optional[int] = None

                for j in range(tok_idx, lookahead_end):
                    _, _, t_clean = tokens[j]
                    if t_clean == w_clean:
                        found_j = j
                        break

                if found_j is not None:
                    matched_tts_start, matched_tts_end, _ = tokens[found_j]
                    tok_idx = found_j + 1
                    sub_cursor = 0
                else:
                    # 3) Tire/kesme işaretiyle bölünen kelime başı kontrolü
                    for j in range(tok_idx, min(n_tokens, tok_idx + 4)):
                        t_start, t_end, _ = tokens[j]
                        t_slice = tts_text[t_start:t_end].lower()
                        if (
                            len(w_clean) >= 2 or "-" in t_slice or "'" in t_slice or "’" in t_slice
                        ):
                            sub_pos = t_slice.find(w_clean)
                            if sub_pos != -1 and (
                                sub_pos == 0 or not t_slice[sub_pos - 1].isalnum()
                            ):
                                matched_tts_start = t_start + sub_pos
                                matched_tts_end = matched_tts_start + len(w_clean)
                                tok_idx = j
                                if sub_pos + len(w_clean) >= len(t_slice) - 1:
                                    tok_idx = j + 1
                                    sub_cursor = 0
                                else:
                                    sub_cursor = sub_pos + len(w_clean)
                                break

            if matched_tts_start is None or matched_tts_end is None:
                continue

            tts_s = max(0, min(matched_tts_start, len(idx_map) - 1))
            tts_e = max(tts_s + 1, min(matched_tts_end, len(idx_map)))
            orig_s = idx_map[tts_s]
            orig_e = idx_map[tts_e - 1] + 1
            orig_e = max(orig_s + 1, min(orig_e, len(orig_para)))
            timings.append((offset_ms, orig_s, orig_e))

        return timings

    async def _generate_audio_with_word_timings(
        self,
        orig_para: str,
        output_path: str,
        voice: str,
        rate: str,
    ) -> list[tuple[int, int, int]]:
        """
        Edge-TTS ile ses üretirken WordBoundary zaman damgalarını
        (başlangıç_ms, kelime_başlangıç_ofseti, kelime_bitiş_ofseti) olarak toplar.
        """
        tts_text, idx_map = normalize_for_tts_with_map(orig_para)
        if not tts_text:
            tts_text = orig_para.strip()
            idx_map = list(range(len(orig_para)))

        communicate = edge_tts.Communicate(
            text=tts_text,
            voice=voice,
            rate=rate,
            boundary="WordBoundary",
        )
        raw_boundaries: list[tuple[int, str]] = []
        with open(output_path, "wb") as out_f:
            async for chunk in communicate.stream():
                ctype = chunk.get("type")
                if ctype == "audio":
                    out_f.write(chunk["data"])
                elif ctype == "WordBoundary":
                    offset_ms = int(chunk.get("offset", 0) // 10_000)
                    w_text = (chunk.get("text") or "").strip()
                    if w_text:
                        raw_boundaries.append((offset_ms, w_text))

        return self._map_word_boundaries_to_para(
            orig_para, tts_text, idx_map, raw_boundaries
        )

    def _generate_audio_with_word_timings_sync(
        self,
        orig_para: str,
        output_path: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
    ) -> tuple[list[tuple[int, int, int]], float]:
        use_voice = voice or self._voice
        use_rate = rate or self._rate
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            timings = loop.run_until_complete(
                self._generate_audio_with_word_timings(
                    orig_para, output_path, use_voice, use_rate
                )
            )
        finally:
            loop.close()

        measured_sec = 0.0
        try:
            measured_sec = float(pygame.mixer.Sound(output_path).get_length())
        except Exception:
            pass
        return timings, measured_sec

    @staticmethod
    def _build_estimated_word_timings(
        paragraph: str, total_ms: int
    ) -> list[tuple[int, int, int]]:
        """WordBoundary gelmezse her kelime için (başlangıç_ms, start, end) üretir."""
        matches = list(re.finditer(r"\S+", paragraph))
        if not matches:
            return []
        total_chars = sum(max(len(m.group(0)), 1) for m in matches)
        result: list[tuple[int, int, int]] = []
        acc = 0
        for m in matches:
            start_ms = int((acc / max(total_chars, 1)) * max(total_ms, 1))
            result.append((start_ms, m.start(), m.end()))
            acc += max(len(m.group(0)), 1)
        return result

    def export_to_mp3(self, text: str, output_path: str) -> None:
        """Metnin tamamını akıllı satır birleştirmesiyle tek bir MP3 dosyası olarak kaydeder."""
        prepared = clean_text(text) or text
        self._generate_audio_sync(prepared, output_path)

    # ── Oynatma kontrolü ───────────────────────────────────────────

    def play_paragraphs(
        self,
        paragraphs: list[str],
        start_index: int = 0,
        on_paragraph_change: Optional[Callable[[int], None]] = None,
        on_word_change: Optional[Callable[[int, int, int], None]] = None,
        on_time_tick: Optional[Callable[[int, int, float], None]] = None,
        on_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        """Paragrafları sırayla sesli okur."""
        self.stop()

        with self._state_lock:
            self._session_id += 1
            session_id = self._session_id
            self._paragraphs = list(paragraphs)
            self._current_paragraph = max(0, min(start_index, len(paragraphs) - 1))
            self._pending_seek_index = None
            self._stop_event.clear()
            self._skip_event.clear()
            self._on_paragraph_change = on_paragraph_change
            self._on_word_change = on_word_change
            self._on_time_tick = on_time_tick
            self._on_playback_complete = on_complete

        self._playback_thread = threading.Thread(
            target=self._playback_loop, args=(session_id,), daemon=True
        )
        self._playback_thread.start()

    def seek_to_ratio(self, ratio: float) -> None:
        """0.0 ile 1.0 arasındaki konuma karşılık gelen paragrafa atlar."""
        if not self._paragraphs:
            return
        clamped = max(0.0, min(0.999, float(ratio)))
        target_idx = int(clamped * len(self._paragraphs))
        target_idx = max(0, min(target_idx, len(self._paragraphs) - 1))
        with self._state_lock:
            self._pending_seek_index = target_idx
            self._is_paused = False
        self._skip_event.set()

    @staticmethod
    def _estimate_para_seconds(text: str) -> float:
        words = max(1, len(text.split()))
        return max(2.0, words / 2.35)  # ~140 kelime/dk

    def _start_prefetch(
        self, session_id: int, para_idx: int, para_text: str, voice: str, rate: str
    ) -> tuple[int, str, str, Future]:
        audio_path = os.path.join(
            self.temp_dir, f"s{session_id}_para_{para_idx}.mp3"
        )
        fut = self._prefetch_executor.submit(
            self._generate_audio_with_word_timings_sync,
            para_text,
            audio_path,
            voice,
            rate,
        )
        return para_idx, voice, rate, fut

    def _playback_loop(self, session_id: int) -> None:
        """
        Paragrafları sırayla oynatan, sonraki paragrafı arka planda önceden hazırlayan
        ve kelime + canlı süre senkronizasyonu yapan ana döngü.
        """
        para_durations = [self._estimate_para_seconds(p) for p in self._paragraphs]
        total_est_sec = max(1.0, sum(para_durations))
        prefetched: Optional[tuple[int, str, str, Future]] = None

        while 0 <= self._current_paragraph < len(self._paragraphs):
            if self._stop_event.is_set() or session_id != self._session_id:
                break

            idx = self._current_paragraph
            para = self._paragraphs[idx]
            audio_path = os.path.join(
                self.temp_dir, f"s{session_id}_para_{idx}.mp3"
            )
            cur_voice = self._voice
            cur_rate = self._rate

            try:
                if self._on_paragraph_change and not self._stop_event.is_set():
                    self._on_paragraph_change(idx)

                # Önceden hazırlanmış (prefetch) ses eşleşiyorsa beklemeden kullan
                timings: Optional[list[tuple[int, int, int]]] = None
                measured_sec = 0.0
                if prefetched is not None:
                    pf_idx, pf_voice, pf_rate, pf_fut = prefetched
                    prefetched = None
                    if pf_idx == idx and pf_voice == cur_voice and pf_rate == cur_rate:
                        try:
                            timings, measured_sec = pf_fut.result()
                        except Exception:
                            timings = None

                if timings is None:
                    timings, measured_sec = self._generate_audio_with_word_timings_sync(
                        para, audio_path, cur_voice, cur_rate
                    )

                if self._stop_event.is_set() or session_id != self._session_id:
                    break
                if self._skip_event.is_set():
                    self._skip_event.clear()
                    with self._state_lock:
                        target = self._pending_seek_index
                        self._pending_seek_index = None
                    self._current_paragraph = target if target is not None else idx + 1
                    continue

                # Gerçek ses süresini ölçüp toplam tahmini güncelle
                actual_para_sec = para_durations[idx]
                if measured_sec > 0.2:
                    actual_para_sec = measured_sec
                    para_durations[idx] = measured_sec
                    total_est_sec = max(1.0, sum(para_durations))

                # Eğer Edge-TTS WordBoundary vermediyse tahmini kelime çizelgesi kur
                if not timings:
                    timings = self._build_estimated_word_timings(
                        para, int(actual_para_sec * 1000)
                    )

                # Sonraki paragrafı oynatma sırasında arka planda önceden hazırla (duraklamasız geçiş)
                next_idx = idx + 1
                if (
                    next_idx < len(self._paragraphs)
                    and not self._stop_event.is_set()
                    and session_id == self._session_id
                ):
                    prefetched = self._start_prefetch(
                        session_id,
                        next_idx,
                        self._paragraphs[next_idx],
                        self._voice,
                        self._rate,
                    )

                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.set_volume(self._volume)
                pygame.mixer.music.play()
                self._is_playing = True

                base_elapsed = sum(para_durations[:idx])
                timing_ms_list = [t[0] for t in timings]
                last_word_idx = -1
                if timings and self._on_word_change and not self._stop_event.is_set():
                    last_word_idx = 0
                    _, w_s, w_e = timings[0]
                    self._on_word_change(idx, w_s, w_e)

                skipped = False
                # Oynatılırken bekle, güncel kelimeyi ve gerçek süreyi takip et
                while pygame.mixer.music.get_busy() or self._is_paused:
                    if self._stop_event.is_set() or session_id != self._session_id:
                        pygame.mixer.music.stop()
                        self._is_playing = False
                        return
                    if self._skip_event.is_set():
                        self._skip_event.clear()
                        pygame.mixer.music.stop()
                        skipped = True
                        break

                    if not self._is_paused:
                        pos_ms = pygame.mixer.music.get_pos()
                        if pos_ms >= 0:
                            cur_sec = min(total_est_sec, base_elapsed + (pos_ms / 1000.0))
                            pct = min(100.0, (cur_sec / total_est_sec) * 100.0)
                            if self._on_time_tick:
                                self._on_time_tick(int(cur_sec), int(total_est_sec), pct)

                            if timings and self._on_word_change:
                                # Hafif +35ms algısal senkronizasyon ile akıcı kelime vurgusu
                                active_idx = max(
                                    0, bisect_right(timing_ms_list, pos_ms + 35) - 1
                                )
                                if active_idx != last_word_idx:
                                    last_word_idx = active_idx
                                    _, w_s, w_e = timings[active_idx]
                                    self._on_word_change(idx, w_s, w_e)

                    pygame.time.wait(30)

                self._is_playing = False
                if skipped:
                    with self._state_lock:
                        target = self._pending_seek_index
                        self._pending_seek_index = None
                    self._current_paragraph = target if target is not None else idx + 1
                else:
                    self._current_paragraph = idx + 1

            except Exception as e:
                print(f"TTS hatası (paragraf {idx}): {e}")
                self._current_paragraph = idx + 1

        self._is_playing = False
        if (
            self._on_playback_complete
            and not self._stop_event.is_set()
            and session_id == self._session_id
        ):
            self._on_playback_complete()

    def pause(self) -> None:
        """Oynatmayı duraklat."""
        if self._is_playing and not self._is_paused:
            pygame.mixer.music.pause()
            self._is_paused = True

    def resume(self) -> None:
        """Duraklatılmış oynatmaya devam et."""
        if self._is_paused:
            pygame.mixer.music.unpause()
            self._is_paused = False

    def stop(self) -> None:
        """Oynatmayı tamamen durdur."""
        with self._state_lock:
            self._session_id += 1
            self._pending_seek_index = None
        self._stop_event.set()
        self._skip_event.set()
        self._is_paused = False
        self._is_playing = False

        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception:
            pass

        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=2)

        self._cleanup_temp()

    def shutdown(self) -> None:
        """Uygulama kapanırken oynatmayı durdurur, prefetch havuzunu ve mixer'ı kapatır."""
        self.stop()
        try:
            self._prefetch_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
        except Exception:
            pass
        if getattr(self, "_owns_temp_dir", False):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def next_paragraph(self) -> None:
        """Sonraki paragrafa atla."""
        if (self._is_playing or self._is_paused) and self._current_paragraph < len(self._paragraphs) - 1:
            with self._state_lock:
                self._pending_seek_index = self._current_paragraph + 1
                self._is_paused = False
            self._skip_event.set()

    def previous_paragraph(self) -> None:
        """Önceki paragrafa dön."""
        if (self._is_playing or self._is_paused) and self._paragraphs:
            with self._state_lock:
                self._pending_seek_index = max(0, self._current_paragraph - 1)
                self._is_paused = False
            self._skip_event.set()

    def _cleanup_temp(self) -> None:
        """Geçici ses dosyalarını temizle."""
        try:
            for filename in os.listdir(self.temp_dir):
                if (filename.startswith("para_") or filename.startswith("s")) and filename.endswith(".mp3"):
                    filepath = os.path.join(self.temp_dir, filename)
                    try:
                        os.remove(filepath)
                    except OSError:
                        pass
        except FileNotFoundError:
            pass

    # ── Durum bilgileri ──────────────────────────────────────────

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def current_paragraph(self) -> int:
        return self._current_paragraph

    @property
    def total_paragraphs(self) -> int:
        return len(self._paragraphs)
