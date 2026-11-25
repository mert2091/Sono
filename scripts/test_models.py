"""
Modelleri Tek Tek Test Eden ve Çalışanı Gösteren Script
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_api_key
from google import genai
from PIL import Image, ImageDraw

GEMINI_API_KEY = get_api_key()
if not GEMINI_API_KEY:
    print("HATA: GEMINI_API_KEY bulunamadı. Önce .env dosyasına veya uygulama içinden anahtarınızı girin.")
    sys.exit(1)

print("=" * 60)
print("ÇALIŞAN MODEL BULUNUYOR...")
print("=" * 60)

# Küçük test görseli
img = Image.new("RGB", (200, 60), color=(255, 255, 255))
d = ImageDraw.Draw(img)
d.text((10, 20), "DENEME 123", fill=(0, 0, 0))

client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={"api_version": "v1beta"},
)

# Test edilecek 3.x ve güncel modeller
models = [
    "gemini-3.8-flash",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
]

working_model = None

for m in models:
    print(f"\nModel deneniyor: {m} ...", end=" ")
    try:
        res = client.models.generate_content(
            model=m,
            contents=[img, "Bu görseldeki metni oku:"],
        )
        if res and res.text:
            print(f"BAŞARILI! Yanıt: {res.text.strip()}")
            working_model = m
            break
        else:
            print("Boş yanıt döndü.")
    except Exception as e:
        err_msg = str(e)
        if "404" in err_msg:
            print("404 (Model yok/erişilemiyor)")
        elif "429" in err_msg:
            print("429 (Kota aşımı)")
        else:
            print(f"HATA: {err_msg[:120]}")

print("\n" + "=" * 60)
if working_model:
    print(f"EN UYGUN ÇALIŞAN MODEL: {working_model}")
else:
    print("Modellerden hiçbiri doğrudan çalışmadı. Lütfen hata çıktılarını kontrol edin.")
print("=" * 60)
input("\nKapatmak için Enter'a basın...")
