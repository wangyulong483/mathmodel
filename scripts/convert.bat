@echo off
setlocal
REM Compatibility wrapper. The canonical build entry is Python.
cd /d "%~dp0.."
python scripts\build_paper.py %*
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
