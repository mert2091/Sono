@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo ============================================================
echo Sono Kurulum Sihirbazi (Setup.exe) Olusturuluyor
echo ============================================================

if not exist "dist\Sono.exe" (
    echo dist\Sono.exe bulunamadi, once EXE derleniyor...
    python build_exe.py
    if errorlevel 1 (
        echo EXE derleme basarisiz oldu.
        exit /b 1
    )
)

set "ISCC_EXE="
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if "%ISCC_EXE%"=="" (
    where iscc >nul 2>&1
    if not errorlevel 1 set "ISCC_EXE=iscc"
)

if "%ISCC_EXE%"=="" (
    echo HATA: Inno Setup 6 ^(ISCC.exe^) bulunamadi.
    echo Kurmak icin: winget install JRSoftware.InnoSetup
    exit /b 1
)

for /f "delims=" %%v in ('python -c "from version import APP_VERSION; print(APP_VERSION)"') do set "APP_VER=%%v"
if "%APP_VER%"=="" set "APP_VER=1.0.0"

echo Derlenen surum: %APP_VER%
"%ISCC_EXE%" /DMyAppVersion=%APP_VER% Sono.iss
if errorlevel 1 (
    echo Yukleyici derlenirken hata olustu.
    exit /b 1
)

echo.
echo Basarili! Cikti: dist\SonoSetup-%APP_VER%.exe
