"""
Dışa Aktarma ve Hızlı Dil Algılama Servisi (Sono).
Çeviri ve belgeleri Word (.docx), PDF (.pdf) ve Markdown (.md) olarak kaydeder;
metin dilini API gerektirmeden anlık olarak tahmin eder.
"""

import os
import re
from typing import List
from PIL import Image, ImageDraw, ImageFont
from docx import Document


def detect_language_local(text: str) -> str:
    """Metnin dilini hızlı yerel kurallarla otomatik algılar."""
    if not text or len(text.strip()) < 4:
        return "Bilinmiyor"

    sample = text[:1200]
    if re.search(r"[\u3040-\u30ff\u4e00-\u9faf]", sample):
        return "Japonca"
    if re.search(r"[\u0600-\u06ff]", sample):
        return "Arapça"
    if re.search(r"[\u0400-\u04ff]", sample):
        return "Rusça"

    lower = sample.lower()
    words = set(re.findall(r"[a-zçğıöşüäöüßàâéèêëîïôùûçñáíóú]+", lower))

    tr_chars = sum(lower.count(c) for c in "çğıöşü")
    tr_words = len(words & {"ve", "bir", "bu", "için", "ile", "olarak", "daha", "çok", "olan", "gibi", "ama", "veya"})
    en_words = len(words & {"the", "and", "is", "are", "for", "with", "that", "this", "from", "have", "you", "not"})
    de_words = len(words & {"der", "die", "das", "und", "ist", "mit", "für", "nicht", "ein", "eine", "auf", "von"})
    fr_words = len(words & {"le", "la", "les", "des", "et", "est", "pour", "dans", "une", "que", "pas", "avec"})
    es_words = len(words & {"el", "la", "los", "las", "de", "que", "en", "para", "con", "por", "una", "como"})
    it_words = len(words & {"il", "lo", "gli", "che", "per", "con", "una", "sono", "della", "anche", "come"})

    scores = {
        "Türkçe": tr_words * 2 + (3 if tr_chars >= 2 else 0),
        "İngilizce": en_words * 2,
        "Almanca": de_words * 2 + (2 if "ß" in lower else 0),
        "Fransızca": fr_words * 2,
        "İspanyolca": es_words * 2 + (2 if "ñ" in lower else 0),
        "İtalyanca": it_words * 2,
    }
    best_lang, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_lang if best_score >= 2 else "Otomatik"


def export_to_markdown(
    output_path: str,
    translated_text: str,
    original_text: str = "",
    source_lang: str = "",
    target_lang: str = "",
) -> None:
    """Çeviriyi (ve varsa orijinal metni) Markdown (.md) olarak kaydeder."""
    lines = ["# Sono Çeviri Çıktısı", ""]
    if source_lang or target_lang:
        lines.append(f"**Dil:** {source_lang or 'Otomatik'} → {target_lang or 'Hedef Dil'}")
        lines.append("")
    lines.append("## Çeviri")
    lines.append("")
    lines.append(translated_text.strip())
    if original_text and original_text.strip() and original_text.strip() != translated_text.strip():
        lines.extend(["", "---", "", "## Orijinal Metin", "", original_text.strip()])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def export_to_docx(
    output_path: str,
    translated_text: str,
    original_text: str = "",
    source_lang: str = "",
    target_lang: str = "",
) -> None:
    """Çeviriyi Word (.docx) belgesi olarak kaydeder."""
    doc = Document()
    doc.add_heading("Sono Çeviri Çıktısı", level=1)
    if source_lang or target_lang:
        p = doc.add_paragraph()
        run = p.add_run(f"Dil: {source_lang or 'Otomatik'} → {target_lang or 'Hedef Dil'}")
        run.italic = True

    doc.add_heading("Çeviri", level=2)
    for para in translated_text.strip().split("\n\n"):
        if para.strip():
            doc.add_paragraph(para.strip())

    if original_text and original_text.strip() and original_text.strip() != translated_text.strip():
        doc.add_heading("Orijinal Metin", level=2)
        for para in original_text.strip().split("\n\n"):
            if para.strip():
                doc.add_paragraph(para.strip())

    doc.save(output_path)


def _load_unicode_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    candidates = (
        ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf"]
        if bold
        else ["segoeui.ttf", "arial.ttf", "calibri.ttf"]
    )
    for name in candidates:
        path = os.path.join(win_fonts, name)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _wrap_line(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> List[str]:
    if not text:
        return [""]
    words = text.split(" ")
    lines: List[str] = []
    cur = ""
    for w in words:
        candidate = f"{cur} {w}".strip() if cur else w
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if (bbox[2] - bbox[0]) <= max_width or not cur:
            cur = candidate
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def export_to_pdf(
    output_path: str,
    translated_text: str,
    original_text: str = "",
    source_lang: str = "",
    target_lang: str = "",
) -> None:
    """
    Türkçe Unicode destekli çok sayfalı A4 PDF üretir (Pillow + Windows Segoe UI).
    """
    page_w, page_h = 1240, 1754  # A4 @ 150 DPI
    margin_x, margin_y = 90, 95
    max_w = page_w - 2 * margin_x

    font_h1 = _load_unicode_font(34, bold=True)
    font_h2 = _load_unicode_font(24, bold=True)
    font_meta = _load_unicode_font(18, bold=False)
    font_body = _load_unicode_font(20, bold=False)

    blocks: List[tuple[str, object, tuple[int, int, int], int]] = [
        ("Sono Çeviri Çıktısı", font_h1, (15, 23, 42), 16),
    ]
    if source_lang or target_lang:
        blocks.append((f"Dil: {source_lang or 'Otomatik'} → {target_lang or 'Hedef Dil'}", font_meta, (100, 116, 139), 22))

    blocks.append(("Çeviri", font_h2, (30, 58, 138), 10))
    for raw_line in translated_text.strip().splitlines():
        blocks.append((raw_line, font_body, (20, 24, 32), 8))

    if original_text and original_text.strip() and original_text.strip() != translated_text.strip():
        blocks.append(("", font_body, (20, 24, 32), 18))
        blocks.append(("Orijinal Metin", font_h2, (30, 58, 138), 10))
        for raw_line in original_text.strip().splitlines():
            blocks.append((raw_line, font_body, (55, 65, 81), 8))

    pages: List[Image.Image] = []
    cur_img = Image.new("RGB", (page_w, page_h), (255, 255, 255))
    draw = ImageDraw.Draw(cur_img)
    y = margin_y

    for text, font, color, extra_gap in blocks:
        wrapped = _wrap_line(draw, text, font, max_w)
        line_h = int((draw.textbbox((0, 0), "Ag", font=font)[3]) + 10)
        for wl in wrapped:
            if y + line_h > page_h - margin_y:
                pages.append(cur_img)
                cur_img = Image.new("RGB", (page_w, page_h), (255, 255, 255))
                draw = ImageDraw.Draw(cur_img)
                y = margin_y
            draw.text((margin_x, y), wl, fill=color, font=font)
            y += line_h
        y += extra_gap

    pages.append(cur_img)
    pages[0].save(output_path, "PDF", resolution=150.0, save_all=True, append_images=pages[1:])
