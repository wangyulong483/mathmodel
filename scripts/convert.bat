@echo off
REM ================================================
REM   数学建模论文 Markdown → Word 转换工具
REM   Pandoc + reference.docx → paper.docx
REM   从项目根目录运行: scripts\convert.bat
REM ================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%\.."

REM Detect Pandoc path
set "PANDOC="
if exist "%LOCALAPPDATA%\Pandoc\pandoc.exe" (
    set "PANDOC=%LOCALAPPDATA%\Pandoc\pandoc.exe"
) else if exist "%LOCALAPPDATA%\Microsoft\WinGet\Packages\JohnMacFarlane.Pandoc_Microsoft.Winget.Source_8wekyb3d8bbwe\pandoc-*\pandoc.exe" (
    for /d %%d in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\JohnMacFarlane.Pandoc_Microsoft.Winget.Source_8wekyb3d8bbwe\pandoc-*") do (
        if exist "%%d\pandoc.exe" set "PANDOC=%%d\pandoc.exe"
    )
) else (
    where pandoc >nul 2>&1
    if %ERRORLEVEL% EQU 0 set "PANDOC=pandoc"
)

if "%PANDOC%"=="" (
    echo [ERROR] Pandoc not found. Install: winget install JohnMacFarlane.Pandoc
    pause
    exit /b 1
)

echo ================================================
echo   Math Paper Generator
echo ================================================
echo.
echo [1/2] Pandoc: output\paper.md → output\paper.docx
echo.

REM v2.0: removed -s flag (conflicts with --reference-doc structure)
"%PANDOC%" output\paper.md -o output\paper.docx --reference-doc=templates\reference.docx --mathml --syntax-highlighting=pygments

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Pandoc conversion failed.
    pause
    exit /b 1
)

echo [2/2] Post-processing: tables, page numbers, styles ...
cd scripts
python postprocess_appendix.py
cd ..

echo ================================================
echo   [DONE] output\paper.docx generated.
echo ================================================
echo   Tables: 100% width, 3-line borders
echo   Page numbers: footer center, decimal
echo.
pause
