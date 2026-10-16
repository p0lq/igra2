@echo off
rem Сборка игры в папку dist\Granica99 (Granica99.exe + _internal)
chcp 65001 >nul
if not exist .venv (
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)
.venv\Scripts\pyinstaller --noconfirm --onedir --windowed --name Granica99 --add-data "data;data" main.py
echo.
echo Готово: dist\Granica99\Granica99.exe
pause
