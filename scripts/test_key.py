"""
API Anahtarı ve Model Teşhis Aracı.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_api_key
from google import genai

GEMINI_API_KEY = get_api_key()
if not GEMINI_API_KEY:
    print("HATA: GEMINI_API_KEY bulunamadı. Önce .env dosyasına veya uygulama içinden anahtarınızı girin.")
    sys.exit(1)

print("=" * 60)
print("GEMINI API VE MODEL TESTİ")
print("=" * 60)
print(f"API Anahtarı (ilk 10 karakter): {GEMINI_API_KEY[:10]}...")
print("\n1. v1beta ile modeller listeleniyor...")

client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={"api_version": "v1beta"},
)

found_models = []
try:
    for model in client.models.list():
        name = model.name or ""
        actions = getattr(model, "supported_actions", []) or []
        found_models.append((name, actions))
        print(f"  - {name} (İşlemler: {', '.join(actions) if actions else 'Belirtilmemiş'})")
except Exception as e:
    print(f"  [HATA] v1beta ile listeleme başarısız: {e}")

if not found_models:
    print("\n2. v1 ile modeller listeleniyor...")
    client_v1 = genai.Client(api_key=GEMINI_API_KEY)
    try:
        for model in client_v1.models.list():
            name = model.name or ""
            actions = getattr(model, "supported_actions", []) or []
            found_models.append((name, actions))
            print(f"  - {name}")
    except Exception as e:
        print(f"  [HATA] v1 ile listeleme de başarısız: {e}")

print("=" * 60)
if found_models:
    print(f"Toplam {len(found_models)} adet model bulundu!")
else:
    print("HİÇBİR MODEL BULUNAMADI!")
    print("Bu anahtar Gemini modellerine erişim iznine sahip olmayabilir.")
print("=" * 60)
input("\nKapatmak için Enter'a basın...")
