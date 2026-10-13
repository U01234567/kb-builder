@echo off
rem start_kb-builder for Windows: double-click this file.
rem Finds Python 3.12 or newer, then runs scripts\start.py: updates, packages, and the review app.
cd /d "%~dp0"
for %%P in (py python) do (
    %%P -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>&1 && (%%P scripts\start.py & goto :end)
)
echo Python 3.12 or newer was not found. Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH"), then double-click this file again.
:end
pause
