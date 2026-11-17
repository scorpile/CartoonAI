@echo off
cd /d "%~dp0"
python -m celstudio serve --open
if errorlevel 1 pause
