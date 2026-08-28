@echo off
cd /d "%~dp0"
if exist "%~dp0python\pythonw.exe" (
    start "" "%~dp0python\pythonw.exe" "%~dp0launcher.py"
) else (
    start "" pythonw "%~dp0launcher.py"
)
exit
