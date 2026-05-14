@echo off
title DotCode — AI Agent
chcp 65001 >nul

:: =========================
:: Auto-detect AGENT_DIR
:: =========================
set AGENT_DIR=%~dp0
set AGENT_DIR=%AGENT_DIR:~0,-1%
set CONFIG_FILE=%AGENT_DIR%\.aider.conf.yml

:: =========================
:: Ép OPENAI_API_KEY từ DEEPSEEK_API_KEY
:: =========================
set OPENAI_API_KEY=%DEEPSEEK_API_KEY%

if "%OPENAI_API_KEY%"=="" (
    echo [ERROR] Khong tim thay DEEPSEEK_API_KEY.
    echo         Chay install.bat de huong dan setup.
    pause
    exit /b 1
)

:: =========================
:: Workspace hiện tại
:: =========================
for %%I in (.) do set CURRENT_FOLDER=%%~nxI
echo [INFO] Agent dir : %AGENT_DIR%
echo [INFO] Project   : %CURRENT_FOLDER%

:: Tạo thư mục Aider nếu chưa có
if not exist "Aider" (
    mkdir "Aider"
    echo [INFO] Created Aider\ folder.
)

:: Cleanup __pycache__
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul

:: =========================
:: Launch Aider
:: =========================
set PYTHONUTF8=1

aider ^
  --config "%CONFIG_FILE%" ^
  --read "%AGENT_DIR%\agent\rules.md" ^
  --read "%AGENT_DIR%\agent\rules.d\async.md" ^
  --read "%AGENT_DIR%\agent\rules.d\database.md" ^
  --read "%AGENT_DIR%\agent\rules.d\security.md" ^
  --read "%AGENT_DIR%\agent\rules.d\heavy_feature.md" ^
  --read "%AGENT_DIR%\agent\rules.d\dangerous_ops.md" ^
  --read "%AGENT_DIR%\agent\rules.d\patch_isolation.md" ^
  --input-history-file "Aider\.aider.input.history-%CURRENT_FOLDER%" ^
  --chat-history-file "Aider\.aider.chat.history-%CURRENT_FOLDER%.md"

pause