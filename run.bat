@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Follow the setup steps in README.md first.
    exit /b 1
)

".venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
endlocal
