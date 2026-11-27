"""
Çeviri Servisi.
google-genai SDK (v1beta) ve otomatik yeniden deneme ile metinleri anlam kayması olmadan çevirir.
"""

from typing import Callable, Optional
from services.gemini_client import get_gemini_client, generate_with_retry


def get_client():
    return get_gemini_client()


def detect_and_translate(
    text: str,
    target_language: str = "Türkçe",
    on_retry: Optional[Callable[[float, int], None]] = None,
) -> dict:
    """Metnin dilini otomatik tespit edip seçilen hedef dile anlam bütünlüğünü koruyarak çevirir."""
    prompt = f"""Aşağıdaki metnin kaynak dilini otomatik tespit et ve {target_language} diline çevir.

Çeviri Kuralları:
- Kelime kelime mekanik çeviri yapma; bağlamı, deyimleri, teknik terimleri ve anlatım tonunu koruyarak doğal, akıcı ve anlam kayması olmayan bir {target_language} metin üret.
- Orijinal paragraf yapısını, madde işaretlerini ve sayısal verileri aynen koru; cümle ekleme veya çıkarma yapma.
- Kaynak metin zaten {target_language} dilindeyse metni bozmadan olduğu gibi koru.

Yanıtını tam olarak şu formatta ver (başka hiçbir açıklama ekleme):

KAYNAK_DİL: [dil adı Türkçe olarak]
---
[{target_language} çeviri metni]

Metin:
{text}"""

    result = generate_with_retry(
        contents=prompt,
        action_label="Çeviri",
        on_retry=on_retry,
    )

    if "---" in result:
        parts = result.split("---", 1)
        source_lang = parts[0].replace("KAYNAK_DİL:", "").strip()
        translation = parts[1].strip()
    else:
        source_lang = "Bilinmiyor"
        translation = result

    return {
        "source_language": source_lang,
        "translation": translation,
        "target_language": target_language,
    }
