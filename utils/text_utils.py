"""
Metin yardımcı araçları.
Uzun metinleri paragraflara bölme, akıllı satır birleştirme, TTS normalizasyonu ve istatistik hesaplama.
"""

import math
import re


_LIST_OR_HEADING_RE = re.compile(
    r"^\s*(?:[-*•▪◦]|\d+[.)]|[A-Za-z][.)]|#+)\s+"
)


def smart_join_lines(text: str) -> str:
    """
    PDF ve OCR çıktılarındaki kırık satır sonlarını akıllıca birleştirir:
    - Çift satır sonlarını (paragraf boşlukları) korur.
    - Satır sonundaki tireyle bölünmüş kelimeleri ('bilgi-\\nsayar') birleştirir.
    - Liste maddeleri ve başlıklar dışındaki cümle ortası kırık satırları tek boşlukla birleştirir.
    """
    if not text:
        return ""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n[ \t]*\n+", normalized.strip())
    joined_blocks: list[str] = []

    for block in blocks:
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in block.split("\n")]
        lines = [ln for ln in lines if ln]
        if not lines:
            continue

        out_lines: list[str] = [lines[0]]
        for ln in lines[1:]:
            prev = out_lines[-1]
            # Liste veya markdown başlığı yeni satırda kalsın
            if _LIST_OR_HEADING_RE.match(ln) or _LIST_OR_HEADING_RE.match(prev):
                out_lines.append(ln)
                continue

            # Tire ile bölünmüş kelimeyi birleştir (ör. "uygu-\nlama" -> "uygulama")
            if (
                prev.endswith("-")
                and len(prev) >= 2
                and prev[-2].isalpha()
                and ln[0].islower()
            ):
                out_lines[-1] = prev[:-1] + ln
                continue

            # Önceki satır kesin cümle sonu ile bitiyorsa ve sonraki satır kısa başlık/etiket gibiyse
            # yine tek boşlukla aynı paragrafta akıcı tutmak TTS duraklamasını önler.
            out_lines[-1] = f"{prev} {ln}"

        joined_blocks.append("\n".join(out_lines))

    return "\n\n".join(joined_blocks).strip()


def split_paragraphs_with_spans(
    text: str, base_offset: int = 0, max_length: int = 500
) -> list[tuple[str, int, int]]:
    """
    Metni paragraflara böler ve her parçanın orijinal metindeki
    kesin (abs_start, abs_end) karakter aralığını döndürür.
    Garanti: text[abs_start - base_offset : abs_end - base_offset] == parca_metni.
    """
    if not text or not text.strip():
        return []

    spans: list[tuple[str, int, int]] = []

    raw_ranges: list[tuple[int, int]] = []
    # Her paragraf ayırıcısı arasındaki blokları al
    pos = 0
    for m in re.finditer(r"\n[ \t]*\n+", text):
        if m.start() > pos:
            raw_ranges.append((pos, m.start()))
        pos = m.end()
    if pos < len(text):
        raw_ranges.append((pos, len(text)))

    for b_start, b_end in raw_ranges:
        # Baş/son boşlukları kırp ama kesin indeksleri koru
        while b_start < b_end and text[b_start].isspace():
            b_start += 1
        while b_end > b_start and text[b_end - 1].isspace():
            b_end -= 1
        if b_start >= b_end:
            continue

        if b_end - b_start <= max_length:
            spans.append((text[b_start:b_end], base_offset + b_start, base_offset + b_end))
            continue

        # Uzun paragrafı cümle sınırlarından böl (dilim indekslerini bozmadan)
        sub = text[b_start:b_end]
        sent_bounds: list[tuple[int, int]] = []
        s_pos = 0
        for m in re.finditer(r"(?<=[.!?…])\s+", sub):
            if m.start() > s_pos:
                sent_bounds.append((s_pos, m.start()))
            s_pos = m.end()
        if s_pos < len(sub):
            sent_bounds.append((s_pos, len(sub)))

        chunk_start: int | None = None
        chunk_end: int = 0
        for s_start, s_end in sent_bounds:
            if chunk_start is None:
                chunk_start, chunk_end = s_start, s_end
                if chunk_end - chunk_start > max_length:
                    spans.append(
                        (
                            sub[chunk_start:chunk_end],
                            base_offset + b_start + chunk_start,
                            base_offset + b_start + chunk_end,
                        )
                    )
                    chunk_start = None
                continue

            if s_end - chunk_start > max_length:
                spans.append(
                    (
                        sub[chunk_start:chunk_end],
                        base_offset + b_start + chunk_start,
                        base_offset + b_start + chunk_end,
                    )
                )
                chunk_start, chunk_end = s_start, s_end
                if chunk_end - chunk_start > max_length:
                    spans.append(
                        (
                            sub[chunk_start:chunk_end],
                            base_offset + b_start + chunk_start,
                            base_offset + b_start + chunk_end,
                        )
                    )
                    chunk_start = None
            else:
                chunk_end = s_end

        if chunk_start is not None and chunk_end > chunk_start:
            spans.append(
                (
                    sub[chunk_start:chunk_end],
                    base_offset + b_start + chunk_start,
                    base_offset + b_start + chunk_end,
                )
            )

    if not spans:
        stripped = text.strip()
        s_idx = text.find(stripped)
        if s_idx == -1:
            s_idx = 0
        return [(stripped, base_offset + s_idx, base_offset + s_idx + len(stripped))]
    return spans


def split_into_paragraphs(text: str, max_length: int = 500) -> list[str]:
    """
    Metni paragraflara böler. TTS için her paragraf ayrı ses dosyasına dönüştürülür.
    """
    return [chunk for chunk, _, _ in split_paragraphs_with_spans(text, 0, max_length)]


def normalize_for_tts_with_map(para: str) -> tuple[str, list[int]]:
    """
    Paragraf içindeki kırık satır sonlarını ve fazla boşlukları Edge-TTS'in
    yapay duraklama yapmaması için tek boşluğa indirger; aynı anda her karakterin
    orijinal paragraftaki indeksini tutan eşleme dizisini döndürür.
    """
    if not para:
        return "", []

    out_chars: list[str] = []
    idx_map: list[int] = []
    n = len(para)
    i = 0

    while i < n:
        ch = para[i]
        # Tire + satır sonu birleşimi: "kelime-\ndevam" -> "kelimedevam"
        if (
            ch == "-"
            and i > 0
            and para[i - 1].isalpha()
            and i + 1 < n
            and para[i + 1] in "\r\n"
        ):
            j = i + 1
            while j < n and para[j] in " \t\r\n":
                j += 1
            if j < n and para[j].islower():
                i = j
                continue

        if ch.isspace():
            if out_chars and out_chars[-1] != " ":
                out_chars.append(" ")
                idx_map.append(i)
            i += 1
            continue

        out_chars.append(ch)
        idx_map.append(i)
        i += 1

    if out_chars and out_chars[-1] == " ":
        out_chars.pop()
        idx_map.pop()

    return "".join(out_chars), idx_map


def split_into_sentences(text: str) -> list[str]:
    """Bir paragrafı okuma vurgulaması için cümlelere böler."""
    if not text or not text.strip():
        return []
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text.strip())
    sentences = [p.strip() for p in parts if p and p.strip()]
    return sentences if sentences else [text.strip()]


def clean_text(text: str) -> str:
    """OCR ve belge çıktısındaki gereksiz boşlukları ve kırık satırları akıllıca temizler."""
    cleaned = smart_join_lines(text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def get_text_stats(text: str) -> dict:
    """
    Metin istatistiklerini hesaplar:
    - Kelime sayısı
    - Karakter sayısı (boşluklu ve boşluksuz)
    - Tahmini okuma süresi (dakika)
    - Paragraf sayısı
    """
    if not text or not text.strip():
        return {
            "words": 0,
            "chars": 0,
            "paragraphs": 0,
            "reading_time_str": "0 dk",
        }

    stripped = text.strip()
    words = len(stripped.split())
    chars = len(stripped)
    paragraphs = len([p for p in stripped.split("\n\n") if p.strip()]) or 1

    # Ortalama konuşma hızı: 140 kelime/dk
    minutes = max(1, math.ceil(words / 140)) if words > 0 else 0
    reading_time_str = f"~{minutes} dk" if words > 0 else "0 dk"

    return {
        "words": words,
        "chars": chars,
        "paragraphs": paragraphs,
        "reading_time_str": reading_time_str,
    }
