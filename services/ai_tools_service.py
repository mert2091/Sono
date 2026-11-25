"""
Akıllı AI Araçları Servisi.
Gemini 3.x ve otomatik yeniden deneme ile özet çıkarma, imla/OCR düzeltme ve belgeye soru sorma.
"""

from typing import Callable, Optional
from services.gemini_client import generate_with_retry


def summarize_text(
    text: str,
    on_retry: Optional[Callable[[float, int], None]] = None,
) -> str:
    """Metnin ana fikirlerini içeren 3-5 maddelik kısa ve öz bir özet çıkarır."""
    prompt = f"""Aşağıdaki metni dikkatle analiz et ve ana fikirlerini 3 ila 5 madde halinde özetle.
Özet Türkçe olsun. Her maddenin başına uygun bir emoji ekle.
Sonuna da 1 cümlelik genel bir 'Ana Sonuç' ekle.

Metin:
{text}"""

    return generate_with_retry(
        contents=prompt,
        action_label="Özet çıkarma",
        on_retry=on_retry,
    )


def fix_and_enhance_text(
    text: str,
    on_retry: Optional[Callable[[float, int], None]] = None,
) -> str:
    """OCR kaynaklı harf bozukluklarını, imla ve noktalama hatalarını düzeltir."""
    prompt = f"""Aşağıdaki metin OCR (görselden metin okuma) ile elde edilmiştir.
Lütfen bu metindeki OCR kaynaklı harf hatalarını, eksik/yanlış noktalamaları ve yazım yanlışlarını düzelt.
Metnin anlamını veya yapısını DEĞİŞTİRME, sadece imla ve akıcılığı düzelt.
Yalnızca düzeltilmiş metni yaz, başka hiçbir açıklama ekleme.

Metin:
{text}"""

    return generate_with_retry(
        contents=prompt,
        action_label="Metin düzeltme",
        on_retry=on_retry,
    )


def ask_document_question(
    document_text: str,
    question: str,
    on_retry: Optional[Callable[[float, int], None]] = None,
) -> str:
    """Belge metnine göre kullanıcının sorusunu yanıtlar."""
    prompt = f"""Aşağıda bir belgenin içeriği ve kullanıcı tarafından sorulan bir soru bulunmaktadır.
Lütfen yalnızca verilen belge içeriğindeki bilgilere dayanarak soruyu net, anlaşılır ve Türkçe olarak yanıtla.
Eğer belgede aranan cevap yoksa 'Bu bilgi belgede yer almamaktadır.' şeklinde belirt.

BELGE İÇERİĞİ:
{document_text}

KULLANICININ SORUSU:
{question}"""

    return generate_with_retry(
        contents=prompt,
        action_label="Belgeye soru sorma",
        on_retry=on_retry,
    )
