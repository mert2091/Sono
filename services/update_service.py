"""
GitHub Releases Güncelleme Servisi (Sono).
Herkese açık GitHub deposunun Releases bölümünden API anahtarı gerekmeden
son sürümü denetler, sürüm notlarını alır ve güvenli bir güncelleyiciyle kurar.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from version import APP_VERSION

MAX_UPDATE_BYTES = 250 * 1024 * 1024  # 250 MB üst sınır
MAX_ZIP_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # 500 MB açılmış zip üst sınırı

_ALLOWED_GITHUB_HOSTS = {
    "github.com",
    "www.github.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-releases.githubusercontent.com",
    "codeload.github.com",
}


def is_safe_github_url(url: str) -> bool:
    """
    URL'nin yalnızca HTTPS ve izinli GitHub alan adlarından biri olduğunu doğrular.
    file://, http://, javascript: veya yetkisiz yönlendirmeleri engeller.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlparse(url.strip())
    except Exception:
        return False
    if parsed.scheme.lower() != "https":
        return False
    host = (parsed.hostname or "").lower()
    if host in _ALLOWED_GITHUB_HOSTS:
        return True
    if host.endswith(".githubusercontent.com"):
        return True
    return False


class _SafeGitHubRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Her HTTP yönlendirmesinde hedefin güvenli HTTPS GitHub/CDN adresi olduğunu doğrular."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        resolved = urllib.parse.urljoin(req.full_url, newurl)
        if not is_safe_github_url(resolved):
            raise urllib.error.URLError("Güvenli olmayan yönlendirme adresi engellendi.")
        return super().redirect_request(req, fp, code, msg, headers, resolved)


def _build_safe_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_SafeGitHubRedirectHandler())


def validate_zip_archive_safe(zip_path: str, target_dir: str) -> None:
    """
    ZIP arşivini Zip Slip (../ yol kaçışı) ve aşırı sıkıştırma (Zip Bomb)
    saldırılarına karşı açmadan önce doğrular.
    """
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("İndirilen güncelleme paketi geçerli bir ZIP arşivi değil.")

    abs_target = os.path.abspath(target_dir)
    total_size = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            member_name = info.filename
            if os.path.isabs(member_name) or member_name.startswith(("/", "\\")):
                raise ValueError("Güncelleme arşivinde güvensiz dosya yolu tespit edildi.")
            dest_member = os.path.abspath(os.path.join(abs_target, member_name))
            if os.path.commonpath([abs_target, dest_member]) != abs_target:
                raise ValueError("Güncelleme arşivinde klasör dışı yol (Zip Slip) engellendi.")
            total_size += max(0, info.file_size)
            if total_size > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise ValueError("Güncelleme arşivi izin verilen boyut sınırını aşıyor.")


@dataclass
class UpdateCheckResult:
    ok: bool
    update_available: bool = False
    current_version: str = APP_VERSION
    latest_version: str = ""
    release_notes: str = ""
    download_url: str = ""
    asset_name: str = ""
    release_page_url: str = ""
    error_message: str = ""


def parse_github_repo(raw: str) -> Optional[Tuple[str, str]]:
    """
    'github.com/user/repo', 'https://github.com/user/repo.git' veya 'user/repo'
    biçimlerinden (owner, repo) çiftini çıkarır.
    """
    if not raw:
        return None
    text = raw.strip().strip("/")
    text = re.sub(r"^https?://", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^www\.", "", text, flags=re.IGNORECASE)
    if text.lower().startswith("github.com/"):
        text = text[len("github.com/"):]
    if text.lower().endswith(".git"):
        text = text[:-4]
    parts = [p for p in text.split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if not re.match(r"^[A-Za-z0-9_.-]+$", owner) or not re.match(r"^[A-Za-z0-9_.-]+$", repo):
        return None
    return owner, repo


def parse_version_tuple(ver: str) -> Tuple[int, ...]:
    """'v1.2.3' veya '1.2.3' dizesini karşılaştırılabilir tam sayı demetine çevirir."""
    cleaned = ver.strip().lstrip("vV")
    nums = re.findall(r"\d+", cleaned)
    if not nums:
        return (0,)
    return tuple(int(n) for n in nums[:4])


def is_newer_version(latest: str, current: str = APP_VERSION) -> bool:
    a = parse_version_tuple(latest)
    b = parse_version_tuple(current)
    max_len = max(len(a), len(b))
    a_pad = a + (0,) * (max_len - len(a))
    b_pad = b + (0,) * (max_len - len(b))
    return a_pad > b_pad


def check_for_updates(repo_input: str, current_version: str = APP_VERSION, timeout: int = 10) -> UpdateCheckResult:
    """Herkese açık GitHub Releases API'sinden son sürümü denetler."""
    parsed = parse_github_repo(repo_input)
    if not parsed:
        return UpdateCheckResult(
            ok=False,
            current_version=current_version,
            error_message="Geçerli bir GitHub depo adresi girin (ör. github.com/kullanici/sono).",
        )

    owner, repo = parsed
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    req = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Sono-Updater/{current_version}",
        },
    )

    try:
        opener = _build_safe_opener()
        with opener.open(req, timeout=timeout) as resp:
            payload = json.loads(resp.read(2 * 1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return UpdateCheckResult(
                ok=False,
                current_version=current_version,
                error_message="Depo bulunamadı ya da bu depoda henüz yayınlanmış bir sürüm (Release) yok.",
            )
        if e.code == 403:
            return UpdateCheckResult(
                ok=False,
                current_version=current_version,
                error_message="GitHub API istek sınırına ulaşıldı. Lütfen birkaç dakika sonra tekrar deneyin.",
            )
        return UpdateCheckResult(
            ok=False,
            current_version=current_version,
            error_message=f"GitHub sunucusundan hata döndü (HTTP {e.code}).",
        )
    except urllib.error.URLError:
        return UpdateCheckResult(
            ok=False,
            current_version=current_version,
            error_message="İnternet bağlantısı yok veya GitHub'a ulaşılamıyor.",
        )
    except Exception:
        return UpdateCheckResult(
            ok=False,
            current_version=current_version,
            error_message="Güncelleme denetlenirken beklenmeyen bir hata oluştu.",
        )

    tag = (payload.get("tag_name") or payload.get("name") or "").strip()
    notes = (payload.get("body") or "Bu sürüm için açıklama girilmemiş.").strip()
    fallback_page = f"https://github.com/{owner}/{repo}/releases"
    raw_html_url = payload.get("html_url") or fallback_page
    html_url = raw_html_url if is_safe_github_url(raw_html_url) else fallback_page

    # İndirilebilir varlık seçimi: öncelik .exe, ardından .zip (yalnızca güvenli HTTPS GitHub URL'leri)
    assets = payload.get("assets") or []
    download_url = ""
    asset_name = ""
    for ext in (".exe", ".zip"):
        for asset in assets:
            name = asset.get("name") or ""
            cand_url = asset.get("browser_download_url") or ""
            if name.lower().endswith(ext) and is_safe_github_url(cand_url):
                download_url = cand_url
                asset_name = name
                break
        if download_url:
            break

    newer = is_newer_version(tag, current_version) if tag else False
    return UpdateCheckResult(
        ok=True,
        update_available=newer,
        current_version=current_version,
        latest_version=tag if tag.startswith("v") else (f"v{tag}" if tag else ""),
        release_notes=notes,
        download_url=download_url,
        asset_name=asset_name,
        release_page_url=html_url,
    )


def download_update_file(
    download_url: str,
    asset_name: str,
    on_progress: Optional[Callable[[int, int], None]] = None,
    timeout: int = 30,
) -> str:
    """
    Güncelleme dosyasını güvenli HTTPS GitHub adresinden izole geçici klasöre indirir,
    boyut ve dosya biçimi (PE/ZIP) doğrulaması yapar.
    """
    if not download_url or not is_safe_github_url(download_url):
        raise ValueError("Güvenli olmayan veya geçersiz güncelleme bağlantısı engellendi.")

    ext = ".zip" if (asset_name or "").lower().endswith(".zip") else ".exe"
    tmp_dir = tempfile.mkdtemp(prefix="sono_update_")
    dest_path = os.path.join(tmp_dir, f"sono_update{ext}")

    req = urllib.request.Request(
        download_url,
        headers={"User-Agent": f"Sono-Updater/{APP_VERSION}"},
    )
    opener = _build_safe_opener()
    try:
        with opener.open(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            if total > MAX_UPDATE_BYTES:
                raise ValueError("Güncelleme dosyası izin verilen maksimum boyutu aşıyor.")

            downloaded = 0
            chunk_size = 65536
            with open(dest_path, "wb") as out:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > MAX_UPDATE_BYTES:
                        raise ValueError("Güncelleme dosyası izin verilen maksimum boyutu aşıyor.")
                    out.write(chunk)
                    if on_progress:
                        on_progress(downloaded, total)

        if ext == ".exe":
            with open(dest_path, "rb") as f:
                magic = f.read(2)
            if magic != b"MZ":
                raise ValueError("İndirilen dosya geçerli bir Windows çalıştırılabilir dosyası (.exe) değil.")
    except Exception:
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass
        raise

    return dest_path


def launch_updater_and_exit(downloaded_file: str) -> None:
    """
    Küçük bir Windows güncelleyici (.bat, ASCII+CRLF) oluşturup başlatır.
    Tüm yollar ortam değişkenleri üzerinden geçirilerek komut enjeksiyonu engellenir;
    ZIP paketleri açılmadan önce Zip Slip denetiminden geçirilir.
    """
    pid = os.getpid()
    is_frozen = getattr(sys, "frozen", False)
    abs_download = os.path.abspath(downloaded_file)
    tmp_dir = os.path.dirname(abs_download)
    bat_path = os.path.join(tmp_dir, "sono_apply_update.bat")

    if is_frozen:
        target_exe = os.path.abspath(sys.executable)
        target_dir = os.path.dirname(target_exe)
        relaunch_cmd = 'start "" "%SONO_TARGET_EXE%"'
    else:
        target_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        target_exe = os.path.join(target_dir, "Sono.exe")
        relaunch_cmd = 'start "" "%SONO_PY%" "%SONO_MAIN%"'

    if abs_download.lower().endswith(".zip"):
        validate_zip_archive_safe(abs_download, target_dir)
        copy_block = (
            'powershell -NoProfile -Command '
            '"Expand-Archive -LiteralPath $env:SONO_SRC -DestinationPath $env:SONO_TARGET_DIR -Force"\r\n'
        )
    else:
        copy_block = 'copy /Y "%SONO_SRC%" "%SONO_TARGET_EXE%" >nul\r\n'

    env = os.environ.copy()
    env["SONO_SRC"] = abs_download
    env["SONO_TARGET_EXE"] = target_exe
    env["SONO_TARGET_DIR"] = target_dir
    if not is_frozen:
        env["SONO_PY"] = sys.executable
        env["SONO_MAIN"] = os.path.join(target_dir, "main.py")

    bat_content = (
        "@echo off\r\n"
        "setlocal DisableDelayedExpansion\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        ":waitloop\r\n"
        f'tasklist /FI "PID eq {pid}" 2>nul | find /I "{pid}" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "  timeout /t 1 /nobreak >nul\r\n"
        "  goto waitloop\r\n"
        ")\r\n"
        f"{copy_block}"
        f"{relaunch_cmd}\r\n"
        'del /f /q "%SONO_SRC%" >nul 2>&1\r\n'
        'del /f /q "%~f0" >nul 2>&1\r\n'
    )

    with open(bat_path, "w", encoding="ascii", errors="ignore", newline="") as f:
        f.write(bat_content)

    creationflags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
    subprocess.Popen(["cmd", "/c", bat_path], env=env, creationflags=creationflags)
