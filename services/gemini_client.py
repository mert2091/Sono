"""
Sağlam Gemini API İstemcisi (Sono).
- Tek merkezden v1beta google-genai istemcisi sağlar.
- 429 (hız/kota limiti) ve 503 (sunucu yoğunluğu) hatalarında otomatik bekleyip yeniden dener.
- Tüm hataları logs/sono.log dosyasına yazar ve kullanıcıya anlaşılır Türkçe uyarı döndürür.
"""

import time
from typing import Any, Callable, Optional, Sequence, Tuple
from google import genai

import config
from services.logger_service import get_logger

logger = get_logger("gemini")

DEFAULT_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3.8-flash",
    "gemini-3.1-pro-preview",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
]

_client: Optional[genai.Client] = None
_client_key: str = ""


def _redact_secret(text: str, secret: str = "") -> str:
    """API anahtarının hata mesajlarına veya loglara sızmasını engeller."""
    out = str(text or "")
    for candidate in (secret, config.get_api_key()):
        if candidate and len(candidate) >= 6:
            out = out.replace(candidate, "[GİZLİ_ANAHTAR]")
    return out


def reset_gemini_client() -> None:
    """Önbellekteki GenAI istemcisini sıfırlar (yeni anahtar girildiğinde anında geçerli olur)."""
    global _client, _client_key
    _client = None
    _client_key = ""


def get_gemini_client() -> genai.Client:
    global _client, _client_key
    api_key = config.get_api_key()
    if not api_key:
        raise RuntimeError(
            "Gemini API anahtarı henüz girilmemiş. Ayarlar → Yapay Zeka ekranından anahtarınızı ekleyebilirsiniz."
        )
    if _client is None or _client_key != api_key:
        _client = genai.Client(
            api_key=api_key,
            http_options={"api_version": "v1beta"},
        )
        _client_key = api_key
    return _client


def validate_api_key(candidate_key: str) -> Tuple[bool, str]:
    """
    Verilen Gemini API anahtarını kaydetmeden önce hafif bir istek (models.list)
    ile doğrular. Anahtarı asla loglara veya hata mesajlarına yazmaz.
    """
    cleaned = (candidate_key or "").strip().strip('"').strip("'")
    if not cleaned or len(cleaned) < 10 or any(ch.isspace() for ch in cleaned):
        return False, "Lütfen geçerli bir Gemini API anahtarı girin."

    try:
        test_client = genai.Client(
            api_key=cleaned,
            http_options={"api_version": "v1beta"},
        )
        next(iter(test_client.models.list()), None)
        return True, "API anahtarı doğrulandı ve kaydedildi."
    except Exception as e:
        safe_err = _redact_secret(str(e), cleaned)
        logger.warning("API anahtarı doğrulama başarısız: %s", safe_err)
        low = safe_err.lower()
        if any(m in low for m in ("401", "403", "api_key", "api key", "unauthenticated", "permission", "invalid")):
            return False, "API anahtarı geçersiz veya yetkisiz. Lütfen anahtarınızı kontrol edip tekrar deneyin."
        if any(m in low for m in ("getaddrinfo", "connection", "connecterror", "network", "timeout", "dns", "unreachable")):
            return False, "İnternet bağlantısı kurulamadı. Bağlantınızı kontrol edip tekrar deneyin."
        if any(m in low for m in ("429", "503", "quota", "rate limit", "overloaded", "unavailable")):
            return False, "Gemini sunucuları şu an yoğun. Birkaç saniye sonra tekrar deneyin."
        return False, "API anahtarı doğrulanamadı. Anahtarınızı kontrol edip tekrar deneyin."


def is_rate_limit_or_transient(err: Exception) -> bool:
    msg = str(err).lower()
    markers = (
        "429",
        "resource_exhausted",
        "rate limit",
        "quota",
        "503",
        "unavailable",
        "overloaded",
        "capacity",
        "try again",
    )
    return any(m in msg for m in markers)


def is_fatal_auth_or_network_error(err: Exception) -> bool:
    """
    401/403 (geçersiz anahtar/yetki) veya bağlantı/ağ yok hatalarında
    diğer modelleri boşuna denememek için erken çıkış kararı verir.
    """
    if is_rate_limit_or_transient(err):
        return False
    msg = str(err).lower()
    fatal_markers = (
        "401",
        "403",
        "api_key",
        "api key",
        "unauthenticated",
        "permission_denied",
        "permission denied",
        "getaddrinfo",
        "connection",
        "connecterror",
        "network",
        "name or service not known",
        "nodename nor servname",
        "unreachable",
        "failed to establish",
        "dns",
    )
    return any(m in msg for m in fatal_markers)


def format_friendly_gemini_error(err: Exception, action_label: str = "İşlem") -> str:
    msg = str(err).lower()
    if "429" in msg or "resource_exhausted" in msg or "quota" in msg or "rate limit" in msg:
        return (
            f"{action_label} sırasında Gemini API kullanım sınırına ulaşıldı. "
            "Lütfen birkaç saniye bekleyip tekrar deneyin."
        )
    if "503" in msg or "unavailable" in msg or "capacity" in msg or "overloaded" in msg:
        return (
            f"Gemini sunucuları şu an yoğun ({action_label}). "
            "Birkaç saniye sonra tekrar deneyin."
        )
    if "401" in msg or "403" in msg or "api_key" in msg or "permission" in msg or "invalid" in msg:
        return (
            "Gemini API anahtarı geçersiz veya yetkisiz görünüyor. "
            "Lütfen .env dosyasındaki GEMINI_API_KEY değerini kontrol edin."
        )
    if "getaddrinfo" in msg or "connection" in msg or "timeout" in msg or "network" in msg:
        return (
            f"İnternet bağlantısı yok veya Gemini sunucusuna ulaşılamıyor ({action_label})."
        )
    return f"{action_label} başarısız oldu. Ayrıntılar logs/sono.log dosyasına kaydedildi."


def generate_with_retry(
    contents: Any,
    models: Optional[Sequence[str]] = None,
    action_label: str = "Yapay zeka işlemi",
    retry_delays: Sequence[float] = (2.0, 5.0),
    on_retry: Optional[Callable[[float, int], None]] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> str:
    """
    Model listesini dener; 429/503 hız limiti veya yoğunlukta üstel bekleme ile
    yeniden dener. Başarısız olursa anlaşılır Türkçe RuntimeError fırlatır.
    """
    client = get_gemini_client()
    model_list = list(models or DEFAULT_MODELS)
    last_err: Optional[Exception] = None

    for attempt in range(len(retry_delays) + 1):
        saw_transient = False
        for model_name in model_list:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                last_err = e
                safe_err = _redact_secret(str(e))
                logger.warning("Model %s hatası (%s): %s", model_name, action_label, safe_err)
                if is_fatal_auth_or_network_error(e):
                    logger.error(
                        "%s kalıcı kimlik/ağ hatası nedeniyle durduruldu: %s",
                        action_label,
                        safe_err,
                    )
                    raise RuntimeError(format_friendly_gemini_error(e, action_label)) from e
                if is_rate_limit_or_transient(e):
                    saw_transient = True
                continue

        if saw_transient and attempt < len(retry_delays):
            wait_s = retry_delays[attempt]
            logger.info(
                "Gemini hız limiti/yoğunluk algılandı (%s). %.1f sn beklenip yeniden deneniyor (deneme %d).",
                action_label,
                wait_s,
                attempt + 1,
            )
            if on_retry:
                try:
                    on_retry(wait_s, attempt + 1)
                except Exception:
                    pass
            sleep_fn(wait_s)
        else:
            break

    if last_err is not None:
        logger.error("%s tüm modellerde başarısız oldu. Son hata: %s", action_label, _redact_secret(str(last_err)))
        raise RuntimeError(format_friendly_gemini_error(last_err, action_label))

    raise RuntimeError(f"{action_label} sırasında boş yanıt alındı.")
