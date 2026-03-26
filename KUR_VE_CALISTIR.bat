@echo off
setlocal enabledelayedexpansion
title Accurace Parser Kurulum

cd /d "%~dp0"
set KLASOR=%~dp0

echo.
echo  ================================================
echo   Accurace Kosu Parser - Otomatik Kurulum
echo  ================================================
echo.
echo  Klasor: %KLASOR%
echo.

if exist "main.py" goto :python_ara
echo  HATA: main.py bulunamadi!
echo  Bu BAT ile main.py ayni klasorde olmali.
pause
exit /b 1

:python_ara
echo  OK: main.py bulundu.
echo.

set PYTHON_CMD=

python --version >nul 2>&1
if not errorlevel 1 set PYTHON_CMD=python
if not "!PYTHON_CMD!"=="" goto :python_found

py --version >nul 2>&1
if not errorlevel 1 set PYTHON_CMD=py
if not "!PYTHON_CMD!"=="" goto :python_found

for %%V in (313 312 311 310 39) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        goto :python_found
    )
    if exist "C:\Python%%V\python.exe" (
        set "PYTHON_CMD=C:\Python%%V\python.exe"
        goto :python_found
    )
)

for /f "delims=" %%i in ('where python 2^>nul') do (
    set "PYTHON_CMD=%%i"
    goto :python_found
)

echo  Python bulunamadi. Indiriliyor...
set PYTHON_INSTALLER=%TEMP%\python_installer.exe
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe' -OutFile '%PYTHON_INSTALLER%'"
if exist "%PYTHON_INSTALLER%" (
    "%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1
    del "%PYTHON_INSTALLER%" >nul 2>&1
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;!PATH!"
    python --version >nul 2>&1
    if not errorlevel 1 set PYTHON_CMD=python
)
if "!PYTHON_CMD!"=="" (
    echo  Python kurulamadi. python.org/downloads adresinden kurun.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

:python_found
echo  OK: Python bulundu.
"!PYTHON_CMD!" --version
echo.

echo  Paketler kuruluyor, bekleyin...
"!PYTHON_CMD!" -m pip install --upgrade pip --quiet
"!PYTHON_CMD!" -m pip install pdf2image pandas openpyxl pillow pytesseract --quiet
if errorlevel 1 (
    echo  HATA: Paket kurulumu basarisiz. Interneti kontrol edin.
    pause
    exit /b 1
)
echo  OK: Paketler hazir.
echo.

where pdftoppm >nul 2>&1
if not errorlevel 1 (
    echo  OK: Poppler zaten kurulu.
    goto :launch
)

if exist "poppler\bin\pdftoppm.exe" (
    set "POPPLER_BIN=%KLASOR%poppler\bin"
    goto :setpath
)

echo  Poppler indiriliyor...
set POPPLER_ZIP=%TEMP%\poppler.zip
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip' -OutFile '%POPPLER_ZIP%'"
if exist "%POPPLER_ZIP%" (
    powershell -Command "Expand-Archive -Path '%POPPLER_ZIP%' -DestinationPath '%KLASOR%poppler' -Force"
    del "%POPPLER_ZIP%" >nul 2>&1
    for /r "%KLASOR%poppler" %%F in (pdftoppm.exe) do set "POPPLER_BIN=%%~dpF"
)
if "!POPPLER_BIN!"=="" (
    echo  Poppler kurulamadi, atlaniyor.
    goto :launch
)

:setpath
set "PATH=!POPPLER_BIN!;!PATH!"
setx PATH "!POPPLER_BIN!;%PATH%" >nul 2>&1
echo  OK: Poppler hazir.
echo.

:launch
echo  ================================================
echo   Kurulum tamamlandi! Uygulama aciliyor...
echo  ================================================
echo.
"!PYTHON_CMD!" "main.py"
pause
