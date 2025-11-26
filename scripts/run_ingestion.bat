@echo off
REM Run project knowledge ingestion with proper UTF-8 encoding
cd /d "%~dp0\.."
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONLEGACYWINDOWSFSENCODING=0
"%~dp0\..\venv-memory\Scripts\python.exe" scripts/ingest_project_knowledge.py
pause
