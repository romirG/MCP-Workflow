@echo off
setlocal
echo ============================================
echo  MCP Workflow Proxy -- Setup (Windows)
echo ============================================
echo.

set SCRIPT_DIR=%~dp0

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ and add it to PATH.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment...
python -m venv "%SCRIPT_DIR%venv"
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/3] Installing dependencies...
"%SCRIPT_DIR%venv\Scripts\pip.exe" install -r "%SCRIPT_DIR%requirements.txt" --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo [3/3] Generating Claude Desktop config snippet...
"%SCRIPT_DIR%venv\Scripts\python.exe" "%SCRIPT_DIR%generate_config.py"

echo.
echo ============================================
echo  Done! Follow the steps above to finish.
echo ============================================
pause
