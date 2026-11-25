"""
OCR Servisi.
google-genai SDK (v1beta) ve otomatik yeniden deneme ile görselden metin çıkarır.
"""

from typing import Callable, Optional
from PIL import Image

from services.gemini_client import get_gemini_client, generate_with_retry


def get_client():
    """Geriye dönük uyumluluk için tekil GenAI istemcisini döndürür."""
    return get_gemini_client()


def extract_text_from_image(
    image: Image.Image,
    on_retry: Optional[Callable[[float, int], None]] = None,
) -> str:
    """Görseldeki tüm metni Gemini API (hız limiti yeniden denemeli) ile çıkarır."""
    if image.mode != "RGB":
        image = image.convert("RGB")

    max_dim = 2048
    if max(image.width, image.height) > max_dim:
        ratio = max_dim / max(image.width, image.height)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    prompt = (
        "Bu görseldeki tüm yazıları ve metinleri olduğu gibi, eksiksiz olarak oku ve çıkar. "
        "Yalnızca görselde okuduğun metni yaz. Hiçbir açıklama, selamlama veya yorum ekleme. "
        "Eğer görselde hiç metin yoksa sadece 'Görselde metin bulunamadı.' yaz."
    )

    return generate_with_retry(
        contents=[image, prompt],
        action_label="OCR (görsel okuma)",
        on_retry=on_retry,
    )
