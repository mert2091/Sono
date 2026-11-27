"""
Belge Okuma Servisi.
PDF, PowerPoint (PPTX), Word (DOCX) ve Metin (TXT) dosyalarını okur.
Sayfa veya slayt bazında ayrıştırma desteği sunar.
"""

import os
from typing import List, Dict, Any

MAX_DOCUMENT_BYTES = 80 * 1024 * 1024  # 80 MB güvenlik üst sınırı


def is_document_file(file_path: str) -> bool:
    """Dosyanın desteklenen bir ofis/belge formatı olup olmadığını denetler."""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in [".pdf", ".pptx", ".docx", ".txt"]


def load_document(file_path: str) -> List[Dict[str, Any]]:
    """
    Belgeyi yükler ve sayfa/slayt listesi döndürür.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError("Seçilen belge dosyası bulunamadı.")
    if os.path.getsize(file_path) > MAX_DOCUMENT_BYTES:
        raise ValueError("Belge boyutu izin verilen güvenlik sınırını (80 MB) aşıyor.")

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _load_pdf(file_path)
    elif ext == ".pptx":
        return _load_pptx(file_path)
    elif ext == ".docx":
        return _load_docx(file_path)
    elif ext == ".txt":
        return _load_txt(file_path)
    else:
        raise ValueError(f"Desteklenmeyen dosya biçimi: {ext}")


def _load_pdf(file_path: str) -> List[Dict[str, Any]]:
    """pypdf ile PDF metnini çıkarır; taranmış/görsel PDF ise otomatik Gemini OCR kullanır."""
    import pypdf
    from utils.text_utils import clean_text, smart_join_lines

    pages = []
    reader = pypdf.PdfReader(file_path)
    total = len(reader.pages)

    for i, page in enumerate(reader.pages):
        raw_text = page.extract_text() or ""
        text = smart_join_lines(raw_text)
        pages.append({
            "page_num": i + 1,
            "title": f"📄 Sayfa {i + 1} / {total}",
            "text": text,
        })

    # Eğer PDF taranmış/görsel tabanlıysa (seçilebilir metin yoksa) Gemini PDF OCR devreye girsin
    extracted_chars = sum(len(p["text"].strip()) for p in pages)
    if extracted_chars < 10:
        import config
        if not config.has_api_key():
            raise ValueError(
                "Bu PDF görsel/taranmış tabanlı görünüyor. Okumak için Ayarlar → Yapay Zeka ekranından Gemini API anahtarınızı girin."
            )
        from services.ocr_service import extract_text_from_pdf_bytes
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
        if len(pdf_bytes) > 20 * 1024 * 1024:
            raise ValueError("Görsel PDF boyutu Gemini OCR sınırı (20 MB) için çok büyük.")
        ocr_text = clean_text(extract_text_from_pdf_bytes(pdf_bytes))
        return [{
            "page_num": 1,
            "title": f"📄 PDF OCR ({total} sayfa)" if total > 1 else "📄 PDF OCR (1 sayfa)",
            "text": ocr_text,
        }]

    return pages


def _load_pptx(file_path: str) -> List[Dict[str, Any]]:
    """python-pptx ile PowerPoint sunumundaki slaytları okur."""
    from pptx import Presentation

    prs = Presentation(file_path)
    slides_data = []
    total = len(prs.slides)

    for i, slide in enumerate(prs.slides):
        slide_texts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                slide_texts.append(shape.text.strip())

        text = "\n\n".join(slide_texts).strip()
        slides_data.append({
            "page_num": i + 1,
            "title": f"📊 Slayt {i + 1} / {total}",
            "text": text if text else "(Bu slaytta metin kutusu bulunamadı)",
        })

    return slides_data


def _load_docx(file_path: str) -> List[Dict[str, Any]]:
    """python-docx ile Word belgesini okur."""
    import docx

    doc = docx.Document(file_path)
    full_text = []

    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())

    text = "\n\n".join(full_text)
    return [{
        "page_num": 1,
        "title": "📝 Word Belgesi",
        "text": text,
    }]


def _load_txt(file_path: str) -> List[Dict[str, Any]]:
    """Düz metin dosyasını okur."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    return [{
        "page_num": 1,
        "title": "📄 Metin Dosyası",
        "text": text.strip(),
    }]
