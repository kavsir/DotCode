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
:: TIER 1 — Always load (core only, <80 lines total)
::   rules-core.md        : principles, triage, behavior, architect, safety
::   system-map-core.md   : module map, active goal, constants
::   sandbox.md           : shell command safety (always active)
::
:: TIER 2 — JIT load (agent uses /add on trigger, not preloaded)
::   rules.d/python.md    : trigger = .py file detected
::   rules.d/javascript.md: trigger = .js/.mjs file detected
::   rules.d/async.md     : trigger = async def / await detected
::   rules.d/database.md  : trigger = SQL / ORM detected
::   rules.d/security.md  : trigger = auth / secrets detected
::   rules.d/heavy_feature.md  : trigger = diff >300 lines or >=3 files
::   rules.d/dangerous_ops.md  : trigger = production / destructive DB
::   rules.d/patch_isolation.md: trigger = 2+ verbs fix/refactor/add/update/rename
::   rules.d/grill.md     : trigger = @grill
::   rules.d/caveman.md   : trigger = @caveman
::   rules.d/diagnose.md  : trigger = @diagnose or multi-file error
::
:: TIER 3 — On demand (user or agent requests explicitly)
::   lesson-log.md        : load on @diagnose or repeat error
::   changelog.md         : load when history needed
::   rules-extended.md    : load when sections 5-10 needed

set PYTHONUTF8=1

aider ^
  --config "%CONFIG_FILE%" ^
  --read "%AGENT_DIR%\agent\rules-core.md" ^
  --read "%AGENT_DIR%\agent\system-map-core.md" ^
  --read "%AGENT_DIR%\agent\rules.d\sandbox.md" ^
  --input-history-file "Aider\.aider.input.history-%CURRENT_FOLDER%" ^
  --chat-history-file "Aider\.aider.chat.history-%CURRENT_FOLDER%.md"
pause