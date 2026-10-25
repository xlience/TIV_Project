@echo off
cd /d "%~dp0"
rem Optional: build a single .exe (not tested; the PyInstaller build may need extra options for acevo-sdk)
python -m pip install pyinstaller
python -m pyinstaller --noconsole --onefile --name 3DOF_Motion app.py
echo Result: dist\3DOF_Motion.exe
pause
