@echo off
setlocal

:: Activate venv
if exist .venv (
  call .venv\Scripts\activate
) else (
  python -m venv .venv
  call .venv\Scripts\activate
)

python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install pyinstaller

:: Use --collect-all/--add-data to avoid missing package metadata
pyinstaller --noconfirm --onefile ^
  --add-data "thresholds.json;." ^
  --add-data "data;data" ^
  --add-data "logo.jpg;." ^
  --collect-all streamlit ^
  --name "DGA-Assistant" run_app.py

echo Build finished. EXE should be in dist\DGA-Assistant.exe
pause
