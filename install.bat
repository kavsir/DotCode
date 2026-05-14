@echo off
title DotCode — Installer
chcp 65001 >nul

echo ============================================
echo   DotCode — Setup
echo ============================================
echo.

:: Detect chính xác thư mục chứa install.bat
set AGENT_DIR=%~dp0
set AGENT_DIR=%AGENT_DIR:~0,-1%

echo [INFO] Agent directory: %AGENT_DIR%
echo.

:: =========================
:: Reload PATH từ registry — không cần restart terminal
:: =========================
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set PATH=%%B;%PATH%
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set PATH=%%B;%PATH%

:: =========================
:: STEP 1 — Kiểm tra Python
:: =========================
echo [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo         Tai tai: https://www.python.org/downloads/
    echo         Yeu cau: Python 3.11 tro len
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] Python %PY_VER% found.
echo.

:: =========================
:: STEP 2 — Kiểm tra & cài Aider
:: =========================
echo [2/4] Checking Aider...
aider --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Aider not found. Installing...
    python -m pip install aider-chat
    if errorlevel 1 (
        echo [ERROR] Aider install failed.
        echo         Thu chay thu cong: python -m pip install aider-chat
        pause
        exit /b 1
    )
    :: Reload PATH từ registry sau khi cài để nhận aider ngay
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set PATH=%%B;%PATH%
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set PATH=%%B;%PATH%
    echo [OK] Aider installed.
) else (
    for /f "tokens=*" %%v in ('aider --version 2^>^&1') do set AIDER_VER=%%v
    echo [OK] Aider %AIDER_VER% found.
)
echo.

:: =========================
:: STEP 3 — Kiểm tra DEEPSEEK_API_KEY
:: =========================
echo [3/4] Checking DEEPSEEK_API_KEY...

:: Reload KEY từ registry nếu terminal chưa nhận
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v DEEPSEEK_API_KEY 2^>nul') do set DEEPSEEK_API_KEY=%%B

if "%DEEPSEEK_API_KEY%"=="" (
    echo [ERROR] DEEPSEEK_API_KEY not found.
    echo.
    echo         Lay API key tai: https://platform.deepseek.com/api_keys
    echo         Sau do chay lenh sau trong terminal:
    echo.
    echo             setx DEEPSEEK_API_KEY sk-xxxxxxxxxxxxxxxx
    echo.
    echo         Sau khi set xong, chay lai install.bat
    pause
    exit /b 1
)
echo [OK] DEEPSEEK_API_KEY found.
echo.

:: =========================
:: STEP 4 — Thêm DotCode vào PATH
:: =========================
echo [4/4] Adding DotCode to PATH...

:: Đọc PATH hiện tại từ registry
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set CURRENT_USER_PATH=%%B

:: Kiểm tra đã có chưa
echo %CURRENT_USER_PATH% | findstr /i /c:"%AGENT_DIR%" >nul
if not errorlevel 1 (
    echo [OK] Already in PATH. Skipping.
) else (
    :: Dùng reg add thay setx — tránh giới hạn 1024 ký tự
    reg add "HKCU\Environment" /v PATH /t REG_EXPAND_SZ /d "%CURRENT_USER_PATH%;%AGENT_DIR%" /f >nul
    set PATH=%PATH%;%AGENT_DIR%
    echo [OK] Added to PATH: %AGENT_DIR%
)
echo.

:: =========================
:: DONE
:: =========================
echo ============================================
echo   Setup complete!
echo ============================================
echo.
echo   Go "AI" o bat ky thu muc nao de bat dau.
echo   (Khong can restart terminal)
echo.
pause