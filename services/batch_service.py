"""
Toplu İşleme Servisi (Sono).
Birden fazla belge (PDF, PPTX, DOCX, TXT) ve görseli (PNG, JPG, WEBP) sırayla
metne çevirir veya tek bir MP3 ses dosyasında birleştirir.
"""

import os
import tempfile
from typing import Callable, List, Optional, Tuple
from PIL import Image

from services.document_service import is_document_file, load_document
from services.ocr_service import extract_text_from_image
from services.tts_service import TTSService
from utils.text_utils import clean_text, split_into_paragraphs


def extract_text_from_any_file(path: str) -> str:
    """Tek bir belge veya görsel dosyasından temiz metin çıkarır."""
    if is_document_file(path):
        pages = load_document(path)
        joined = "\n\n".join(p.get("text", "").strip() for p in pages if p.get("text", "").strip())
        return clean_text(joined)

    if os.path.getsize(path) > 50 * 1024 * 1024:
        raise ValueError("Görsel dosyası izin verilen 50 MB güvenlik sınırını aşıyor.")
    try:
        with Image.open(path) as img:
            img.load()
            image = img.convert("RGB") if img.mode != "RGB" else img.copy()
    except Image.DecompressionBombError as e:
        raise ValueError("Görsel çözünürlüğü güvenlik sınırını aşıyor.") from e
    raw = extract_text_from_image(image)
    return clean_text(raw)


def process_files_to_combined_text(
    file_paths: List[str],
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[str, List[str]]:
    """
    Seçilen dosyaları sırayla okuyup başlıklandırılmış tek bir metinde birleştirir.
    Dönüş: (birleşik_metin, hatalı_dosya_listesi)
    """
    sections: List[str] = []
    errors: List[str] = []
    total = len(file_paths)

    for idx, path in enumerate(file_paths, start=1):
        fname = os.path.basename(path)
        if on_progress:
            on_progress(idx, total, fname)
        try:
            text = extract_text_from_any_file(path)
            if text:
                sections.append(f"--- {fname} ---\n\n{text}")
        except Exception as e:
            errors.append(f"{fname}: {e}")

    return "\n\n\n".join(sections), errors


def export_combined_text_to_single_mp3(
    tts_service: TTSService,
    combined_text: str,
    output_path: str,
    on_chunk_progress: Optional[Callable[[int, int], None]] = None,
) -> None:
    """
    Uzun birleşik metni güvenli parçalara bölerek Edge-TTS ile sentezler ve
    tek bir MP3 dosyasında birleştirir.
    """
    chunks = split_into_paragraphs(combined_text, max_length=1200)
    if not chunks:
        raise ValueError("Birleştirilecek metin bulunamadı.")

    tmp_dir = tempfile.mkdtemp(prefix="sono_batch_mp3_")
    part_files: List[str] = []
    try:
        total = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            if on_chunk_progress:
                on_chunk_progress(idx, total)
            part_path = os.path.join(tmp_dir, f"part_{idx:04d}.mp3")
            tts_service.export_to_mp3(chunk, part_path)
            part_files.append(part_path)

        with open(output_path, "wb") as out_f:
            for pf in part_files:
                with open(pf, "rb") as in_f:
                    out_f.write(in_f.read())
    finally:
        for pf in part_files:
            try:
                os.remove(pf)
            except OSError:
                pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass
