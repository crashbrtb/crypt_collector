@echo off
cd /d "%~dp0"
if exist "%~dp0python\pythonw.exe" (
    start "" "%~dp0python\pythonw.exe" "%~dp0docrypt.py"
) else (
    start "" pythonw "%~dp0docrypt.py"
)
exit
