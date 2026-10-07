@echo off
setlocal
cd /d "%~dp0"

set "ISCC="
where ISCC.exe >nul 2>&1 && set "ISCC=ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo Inno Setup 6 was not found.
    echo Install it from https://jrsoftware.org/isinfo.php and run this script again.
    exit /b 1
)

set "BUILD_PYTHON=.build_venv\Scripts\python.exe"
if not exist "%BUILD_PYTHON%" (
    python -m venv .build_venv
    if errorlevel 1 goto :error
)

"%BUILD_PYTHON%" -m pip install -r requirements-build.txt
if errorlevel 1 goto :error

"%BUILD_PYTHON%" -m PyInstaller --noconfirm --clean --windowed --onedir --name PhotoTable --additional-hooks-dir "." --add-data "..\static:static" --distpath "dist" --workpath "build" --specpath "build" app.py
if errorlevel 1 goto :error

"%ISCC%" "PhotoTable_v.0.2.iss"
if errorlevel 1 goto :error

echo.
echo Installer created: dist\PhotoTable_v0.2_Setup.exe
exit /b 0

:error
echo.
echo Build failed. Review the error messages above.
exit /b 1
