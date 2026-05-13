@echo off
title Agent_Code — Installer
chcp 65001 >nul

echo ============================================
echo   Agent_Code — Setup
echo ============================================
echo.

:: Detect chính xác thư mục chứa install.bat
set AGENT_DIR=%~dp0
set AGENT_DIR=%AGENT_DIR:~0,-1%

echo [INFO] Agent directory: %AGENT_DIR%
echo.

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
    pip install aider-chat
    if errorlevel 1 (
        echo [ERROR] Aider install failed.
        echo         Thu chay thu cong: pip install aider-chat
        pause
        exit /b 1
    )
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
:: STEP 4 — Thêm Agent_Code vào PATH
:: =========================
echo [4/4] Adding Agent_Code to PATH...

:: Kiểm tra đã có trong PATH chưa
echo %PATH% | findstr /i /c:"%AGENT_DIR%" >nul
if not errorlevel 1 (
    echo [OK] Already in PATH. Skipping.
) else (
    setx PATH "%PATH%;%AGENT_DIR%"
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
echo   Restart terminal, sau do go "AI" o bat ky
echo   thu muc nao de bat dau.
echo.
pause
