"""
Çeviri Servisi.
google-genai SDK (v1beta) ve otomatik yeniden deneme ile metinleri çevirir.
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
    """Metnin dilini tespit edip seçilen hedef dile çevirir."""
    prompt = f"""Aşağıdaki metnin dilini tespit et ve {target_language} diline çevir.
Yanıtını tam olarak şu formatta ver (başka hiçbir şey ekleme):

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
