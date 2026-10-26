@echo off
cd /d "%~dp0"
pythonw gui.py
if errorlevel 1 (
    python gui.py
    pause
)
