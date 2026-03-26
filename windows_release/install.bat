@echo off
chcp 65001 >nul
title Zapret2 TUI - Установка

:: Проверка прав администратора
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ============================================
    echo  Zapret2 TUI - Установка
    echo ============================================
    echo.
    echo [!] ТРЕБУЮТСЯ ПРАВА АДМИНИСТРАТОРА!
    echo.
    echo Нажмите правой кнопкой на install.bat
    echo и выберите "Запуск от имени администратора"
    echo.
    pause
    exit /b 1
)

echo ============================================
echo  Zapret2 TUI - Установка
echo ============================================
echo.

:: Переход в директорию скрипта
cd /d "%~dp0"

:: Проверка Python
echo [*] Проверка Python...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Python не найден!
    echo.
    echo Скачайте с: https://www.python.org/downloads/
    echo При установке отметьте: Add Python to PATH
    echo.
    pause
    exit /b 1
)
python --version
echo     OK
echo.

:: Установка зависимостей
echo [*] Установка Python зависимостей...
pip install -r requirements.txt --quiet --disable-pip-version-check
if %errorLevel% neq 0 (
    echo [!] Ошибка установки зависимостей
    echo     Попробуйте вручную: pip install -r requirements.txt
) else (
    echo     OK
)
echo.

:: Скачивание WinDivert
echo [*] Скачивание WinDivert...
set "WINDIVERT_URL=https://github.com/basil00/Divert/releases/download/v2.2.2/WinDivert-2.2.2-W.zip"
set "WINDIVERT_ZIP=%TEMP%\WinDivert.zip"
set "WINDIVERT_TEMP=%TEMP%\WinDivert"

:: Используем certutil для скачивания (более надежный)
certutil -urlcache -split -f "%WINDIVERT_URL%" "%WINDIVERT_ZIP%" >nul 2>&1
if exist "%WINDIVERT_ZIP%" (
    echo     WinDivert загружен
    
    :: Распаковка
    if not exist "%WINDIVERT_TEMP%" mkdir "%WINDIVERT_TEMP%"
    powershell -Command "Expand-Archive -Path '%WINDIVERT_ZIP%' -DestinationPath '%WINDIVERT_TEMP%' -Force" 2>nul
    
    if exist "%WINDIVERT_TEMP%\WinDivert-2.2.2-W\x64\WinDivert64.dll" (
        copy /y "%WINDIVERT_TEMP%\WinDivert-2.2.2-W\x64\WinDivert64.dll" "." >nul
        copy /y "%WINDIVERT_TEMP%\WinDivert-2.2.2-W\x64\WinDivert64.sys" "." >nul
        echo     WinDivert установлен!
    ) else (
        echo [!] Ошибка распаковки WinDivert
    )
    
    :: Очистка
    del /f /q "%WINDIVERT_ZIP%" 2>nul
    rmdir /s /q "%WINDIVERT_TEMP%" 2>nul
) else (
    echo [!] Не удалось скачать WinDivert
    echo.
    echo     Скачайте вручную:
    echo     %WINDIVERT_URL%
    echo.
    echo     Распакуйте и скопируйте:
    echo     - WinDivert64.dll
    echo     - WinDivert64.sys
)
echo.

:: Скачивание winws2
echo [*] Скачивание winws2...
set "ZAPRET2_API=https://api.github.com/repos/bol-van/zapret2/releases/latest"

:: Получаем последнюю версию
for /f "delims=" %%i in ('powershell -Command "(Invoke-RestMethod '%ZAPRET2_API%').tag_name" 2^>nul') do set "VERSION=%%i"

if defined VERSION (
    echo     Найдена версия: %VERSION%
    
    :: Формируем URL для скачивания
    set "WINWS2_URL=https://github.com/bol-van/zapret2/archive/refs/tags/%VERSION%.zip"
    set "WINWS2_ZIP=%TEMP%\zapret2.zip"
    set "WINWS2_TEMP=%TEMP%\zapret2"
    
    certutil -urlcache -split -f "%WINWS2_URL%" "%WINWS2_ZIP%" >nul 2>&1
    
    if exist "%WINWS2_ZIP%" (
        echo     zapret2 загружен
        
        if not exist "%WINWS2_TEMP%" mkdir "%WINWS2_TEMP%"
        powershell -Command "Expand-Archive -Path '%WINWS2_ZIP%' -DestinationPath '%WINWS2_TEMP%' -Force" 2>nul
        
        :: Ищем winws2.exe
        for /f "delims=" %%f in ('dir /s /b "%WINWS2_TEMP%\*\binaries\*\winws2.exe" 2^>nul') do (
            copy /y "%%f" "." >nul
            echo     winws2.exe установлен!
            goto :winws2_done
        )
        
        :winws2_done
        
        del /f /q "%WINWS2_ZIP%" 2>nul
        rmdir /s /q "%WINWS2_TEMP%" 2>nul
    )
) else (
    echo [!] Не удалось получить информацию о релизе
    echo.
    echo     Скачайте вручную:
    echo     https://github.com/bol-van/zapret2/releases
)
echo.

:: Проверка файлов
echo [*] Проверка установленных файлов...
set "ALL_PRESENT=1"

for %%f in (winws2.exe WinDivert64.dll WinDivert64.sys) do (
    if exist "%%f" (
        echo     [OK] %%f
    ) else (
        echo     [!] %%f - ОТСУТСТВУЕТ
        set "ALL_PRESENT=0"
    )
)
echo.

if "%ALL_PRESENT%"=="1" (
    echo Все файлы на месте!
    echo.
    echo ============================================
    echo  Запуск Zapret2 TUI...
    echo ============================================
    echo.
    python zapret2_tui.py
) else (
    echo.
    echo [!] Некоторые файлы отсутствуют!
    echo     Скачайте их вручную (см. выше)
    echo.
    pause
)
