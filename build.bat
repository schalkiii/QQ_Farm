@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   QQFarmBot EXE Build Script
echo ========================================
echo.

:: Clean old build
echo [1/3] Cleaning old build...
rmdir /s /q build 2>nul
rmdir /s /q dist\QQFarmBot 2>nul

:: Build
echo [2/3] Building QQFarmBot...
pyinstaller build.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

:: Verify
:: build.spec 为 onefile 模式（只有 EXE()，无 COLLECT()），产物是单个
:: dist\QQFarmBot.exe；templates/configs/icons 均已内嵌，不存在
:: dist\QQFarmBot\_internal\ 目录。此前按 onedir 路径校验导致误报失败。
echo.
echo [3/3] Verifying...
if not exist "dist\QQFarmBot.exe" (
    echo [ERROR] QQFarmBot.exe not found!
    pause
    exit /b 1
)

for %%A in (dist\QQFarmBot.exe) do echo EXE: %%~zA bytes
echo Mode: onefile - templates/configs/icons 已内嵌，运行时解压到临时目录

echo.
echo [OK] Build complete! Output: dist\QQFarmBot.exe
echo.
pause
