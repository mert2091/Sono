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



def _notify_existing_instance() -> bool:
    """Halihazirda acik bir Sono ornegi varsa onu one getirir ve True doner."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        mutex = ctypes.windll.kernel32.CreateMutexW(
            None, False, "Local\\Sono_SingleInstance_Mutex_v1"
        )
        last_err = ctypes.windll.kernel32.GetLastError()
        globals()["_SONO_INSTANCE_MUTEX"] = mutex
        if last_err == 183:  # ERROR_ALREADY_EXISTS
            import socket
            from utils.paths import DATA_DIR
            port_file = DATA_DIR / "instance.port"
            if port_file.exists():
                try:
                    port = int(port_file.read_text(encoding="utf-8").strip())
                    with socket.create_connection(("127.0.0.1", port), timeout=1.5) as s:
                        s.sendall(b"SHOW\n")
                except Exception:
                    pass
            return True
    except Exception:
        pass
    return False


def _start_instance_listener(app) -> None:
    """Ikinci bir Sono acilmaya calisildiginda mevcut pencereyi one getiren yerel dinleyici."""
    import socket
    import threading
    from utils.paths import DATA_DIR

    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(5)
        port = srv.getsockname()[1]
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        port_file = DATA_DIR / "instance.port"
        port_file.write_text(str(port), encoding="utf-8")

        def _serve():
            while True:
                try:
                    conn, _ = srv.accept()
                    with conn:
                        data = conn.recv(64)
                        if b"SHOW" in data:
                            app.after(0, app._restore_from_tray)
                except OSError:
                    break
                except Exception:
                    pass

        threading.Thread(target=_serve, daemon=True).start()
        app._instance_server = srv
    except Exception:
        pass


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

        if _notify_existing_instance():
            logger.info("Sono zaten acik; mevcut pencere one getirildi.")
            return
        app = App()
        _start_instance_listener(app)
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
