@echo off
chcp 65001 >nul
title Zapret2 TUI - Telegram Unblocker

:: Проверка прав администратора
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ============================================
    echo  Zapret2 TUI - Telegram Unblocker
    echo ============================================
    echo.
    echo [!] Требуется запуск от имени администратора!
    echo.
    echo Нажмите правой кнопкой на start.bat и выберите
    echo "Запуск от имени администратора"
    echo.
    pause
    exit /b 1
)

echo ============================================
echo  Zapret2 TUI - Telegram Unblocker
echo ============================================
echo.

:: Проверка наличия winws2.exe
if not exist "winws2.exe" (
    echo [!] winws2.exe не найден!
    echo.
    echo Скачайте winws2.exe из релизов zapret2:
    echo https://github.com/bol-van/zapret2/releases
    echo.
    echo и поместите его в эту директорию.
    echo.
    pause
    exit /b 1
)

:: Проверка наличия WinDivert64.dll
if not exist "WinDivert64.dll" (
    echo [!] WinDivert64.dll не найден!
    echo.
    echo Убедитесь что WinDivert64.dll находится
    echo в этой же директории что и winws2.exe
    echo.
    pause
    exit /b 1
)

:: Проверка Python
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Python не найден!
    echo.
    echo Установите Python 3.8+ с https://python.org
    echo.
    pause
    exit /b 1
)

:: Проверка зависимостей
echo [*] Проверка зависимостей...
python -c "import textual" >nul 2>&1
if %errorLevel% neq 0 (
    echo [*] Установка зависимостей...
    pip install -r requirements.txt
)

:: Создание директории lua если нет
if not exist "lua" mkdir lua

:: Запуск TUI
echo.
echo [*] Запуск Zapret2 TUI...
echo.
python zapret2_tui.py

pause
