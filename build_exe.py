"""
PyInstaller ile Tek Dosya Sono.exe Üretici.
CustomTkinter, tkinterdnd2, pystray, PIL, edge_tts, docx/pptx ve assets/ varlıklarını
toplayıp tek bir bağımsız Windows çalıştırılabilir dosyası (dist/Sono.exe) derler.
Not: .env, settings.json ve history.db kesinlikle .exe içine gömülmez.
"""

import importlib.metadata
import os
import subprocess
import sys

from version import APP_NAME, APP_VERSION


def _has_dist(pkg_name: str) -> bool:
    try:
        importlib.metadata.distribution(pkg_name)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def _find_icon_path() -> str:
    """Güncel Sono simge (.ico) dosyasını assets/ içinden bulur."""
    for candidate in ("sono.ico", "ses-studyosu.ico"):
        path = os.path.join("assets", candidate)
        if os.path.exists(path):
            return path
    return ""


def build() -> int:
    print("=" * 60)
    print(f"{APP_NAME} v{APP_VERSION} - Tek Dosya (.exe) Derleme Başlatılıyor")
    print("=" * 60)

    ico_path = _find_icon_path()
    if ico_path:
        print(f"Simge dosyası: {ico_path}")
    else:
        print("Uyarı: assets/ altında .ico simge dosyası bulunamadı.")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        f"--name={APP_NAME}",
        "--collect-data=customtkinter",
        "--collect-data=tkinterdnd2",
        "--collect-binaries=tkinterdnd2",
        "--collect-data=certifi",
        "--collect-data=docx",
        "--collect-data=pptx",
        "--collect-data=edge_tts",
        "--hidden-import=pystray._win32",
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=edge_tts",
        "--hidden-import=aiohttp",
        "--hidden-import=pygame",
        "--hidden-import=google.genai",
        "--hidden-import=dotenv",
        "--hidden-import=pypdf",
        "--hidden-import=docx",
        "--hidden-import=pptx",
    ]
    for pkg in ("requests", "pypdf", "google-genai", "edge-tts"):
        if _has_dist(pkg):
            cmd.append(f"--copy-metadata={pkg}")

    if ico_path:
        cmd.append(f"--icon={ico_path}")
    if os.path.isdir("assets"):
        cmd.append("--add-data=assets;assets/")

    cmd.append("main.py")

    print("\nKomut çalıştırılıyor:\n", " ".join(cmd), "\n")
    ret = subprocess.call(cmd)

    exe_out = os.path.join("dist", f"{APP_NAME}.exe")
    if ret == 0 and os.path.exists(exe_out):
        size_mb = os.path.getsize(exe_out) / (1024 * 1024)
        print("\n" + "=" * 60)
        print(f"DERLEME BAŞARIYLA TAMAMLANDI! ({size_mb:.1f} MB)")
        print(f"Çıktı dosyası: {exe_out}")
        print("=" * 60)
    else:
        print("\nDerleme sırasında bir hata oluştu.")
    return ret


if __name__ == "__main__":
    raise SystemExit(build())
