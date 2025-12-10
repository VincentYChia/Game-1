@echo off
REM Game-1 Build Script for Windows
REM Packages the game into a standalone executable using PyInstaller

echo ======================================
echo   Game-1 Build Script
echo ======================================
echo.

REM Check if we're in the correct directory
if not exist main.py (
    echo Error: main.py not found. Please run this script from the Game-1-modular directory.
    exit /b 1
)

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo Done.
echo.

REM Build with PyInstaller
echo Building Game-1 with PyInstaller...
echo This may take 5-10 minutes...
echo.

pyinstaller Game1.spec

echo.
if exist dist\Game1 (
    echo ======================================
    echo   Build Complete!
    echo ======================================
    echo.
    echo Executable location: dist\Game1\Game1.exe
    echo.
    echo To test the game, run:
    echo   cd dist\Game1
    echo   Game1.exe
    echo.
    echo Note: Save files will be stored in:
    echo   %%APPDATA%%\Game1\saves\
) else (
    echo Build failed. Check the output above for errors.
    exit /b 1
)
