"""
Görsel yardımcı araçları.
Panodan görsel alma, boyutlandırma, döndürme ve format dönüştürme.
"""

import io
from PIL import Image, ImageGrab, ImageEnhance


def grab_clipboard_image() -> Image.Image | None:
    """
    Windows panosundan (clipboard) görsel yakalar.

    Returns:
        PIL Image nesnesi veya görsel yoksa None
    """
    try:
        content = ImageGrab.grabclipboard()
        if isinstance(content, Image.Image):
            return content
        if isinstance(content, list) and content:
            path = content[0]
            if isinstance(path, str):
                with Image.open(path) as img:
                    img.load()
                    return img.copy()
        return None
    except Exception:
        return None


def resize_for_preview(
    image: Image.Image,
    max_width: int = 380,
    max_height: int = 380,
) -> Image.Image:
    """
    Görseli önizleme alanına sığacak şekilde küçültür.
    Orijinal en-boy oranını korur.

    Args:
        image: Orijinal görsel
        max_width: Maksimum genişlik (piksel)
        max_height: Maksimum yükseklik (piksel)

    Returns:
        Yeniden boyutlandırılmış görsel
    """
    ratio = min(max_width / max(image.width, 1), max_height / max(image.height, 1))
    if ratio < 1:
        new_size = (max(int(image.width * ratio), 1), max(int(image.height * ratio), 1))
        return image.resize(new_size, Image.LANCZOS)
    return image.copy()


def rotate_image(image: Image.Image, degrees: int = 90) -> Image.Image:
    """
    Görseli saat yönünde belirtilen derece kadar döndürür.
    Varsayılan 90 derecedir.
    """
    # PIL rotate saat yönünün tersinedir, saat yönü için -degrees
    return image.rotate(-degrees, expand=True)


def get_image_info(image: Image.Image) -> str:
    """Görsel hakkında kısa bilgi döndürür (Örn: '1920x1080 px • RGB')."""
    return f"{image.width}x{image.height} px • {image.mode}"
