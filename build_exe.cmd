@echo off
echo Starting build process...

:: Check if python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not found in PATH.
    pause
    exit /b 1
)

:: Install PyInstaller if not present
echo Installing/Updating PyInstaller...
pip install pyinstaller

:: Clean previous build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: Run PyInstaller
echo Running PyInstaller...
pyinstaller mini-project-copyer.spec

if %errorlevel% neq 0 (
    echo Build failed!
    pause
    exit /b 1
)

echo Build completed successfully!
echo Executable is located in dist/mini-project-copyer.exe
pause
