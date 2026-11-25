"""
Sono
====
Görsel ve belgelerden metin çıkarıp çeviren, özetleyen ve sesli okuyan masaüstü uygulaması.

Kullanım:
    python main.py

Gereksinimler:
    pip install -r requirements.txt

Konfigürasyon:
    .env dosyasına GEMINI_API_KEY=... yazın
"""

import sys
import os

# PyInstaller --windowed (.exe) modunda sys.stdout / sys.stderr None olur;
# CustomTkinter ve diğer kütüphanelerin stderr.write() çağrılarının çökmesini önle.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Windows yüksek çözünürlüklü ekranlarda (HiDPI) yazıların bulanıklaşmasını önle
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# Proje kök dizinini Python yoluna ekle (her yerden çalıştırılabilmesi için)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """Uygulamayı başlat."""
    from services.logger_service import setup_logging, get_logger
    setup_logging()
    logger = get_logger("main")
    logger.info("Sono başlatılıyor...")

    def _excepthook(exc_type, exc_value, exc_tb):
        logger.exception("Yakalanmayan uygulama hatası", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook

    try:
        # Konfigürasyon modülünü yükle (.env yoksa uygulama içi giriş ekranı açılır)
        import config  # noqa: F401
    except Exception as e:
        logger.error("Konfigürasyon yükleme hatası: %s", e)

    try:
        # Uygulamayı başlat
        from ui.app import App

        app = App()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        logger.exception("Uygulama başlatma hatası: %s", e)
        print("\n" + "=" * 60)
        print("UYGULAMA BAŞLATILIRKEN BİR HATA OLUŞTU:")
        print("=" * 60)
        print(err_msg)
        print("=" * 60)
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Uygulama Hatası", f"Bir hata oluştu:\n\n{e}\n\nDetaylar konsolda gösterildi.")
        except Exception:
            pass
        if not getattr(sys, "frozen", False) and sys.stdin:
            input("\nPencereyi kapatmak için Enter tuşuna basın...")
        sys.exit(1)


if __name__ == "__main__":
    main()
