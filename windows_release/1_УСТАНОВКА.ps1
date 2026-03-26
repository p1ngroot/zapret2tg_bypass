# Zapret2 TUI - Автоматическая установка зависимостей
# Запускать от имени Администратора!

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Zapret2 TUI - Установка зависимостей" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"

# Проверка прав администратора
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).`
    IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[!] ОШИБКА: Запустите от имени Администратора!" -ForegroundColor Red
    Write-Host "    Правая кнопка на файле -> Запуск от имени администратора" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "[*] Проверка прав администратора... OK" -ForegroundColor Green
Write-Host ""

# Переход в директорию скрипта
Set-Location -Path $PSScriptRoot

# Проверка Python
Write-Host "[*] Проверка Python..." -ForegroundColor Cyan
try {
    $pythonVersion = python --version 2>&1
    Write-Host "    $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[!] Python не найден!" -ForegroundColor Red
    Write-Host "    Скачайте с: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "    При установке отметьте: Add Python to PATH" -ForegroundColor Yellow
    pause
    exit 1
}
Write-Host ""

# Установка Python зависимостей
Write-Host "[*] Установка Python зависимостей..." -ForegroundColor Cyan
try {
    pip install -r requirements.txt --quiet
    Write-Host "    Зависимости установлены!" -ForegroundColor Green
} catch {
    Write-Host "[!] Ошибка установки зависимостей" -ForegroundColor Red
    Write-Host "    Попробуйте вручную: pip install -r requirements.txt" -ForegroundColor Yellow
}
Write-Host ""

# Скачивание WinDivert
Write-Host "[*] Скачивание WinDivert..." -ForegroundColor Cyan
$windivertUrl = "https://github.com/basil00/Divert/releases/download/v2.2.2/WinDivert-2.2.2-W.zip"
$windivertZip = "$env:TEMP\WinDivert.zip"
$windivertTemp = "$env:TEMP\WinDivert"

try {
    # Используем Invoke-WebRequest с правильным User-Agent
    $headers = @{
        "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    Invoke-WebRequest -Uri $windivertUrl -OutFile $windivertZip -Headers $headers -UseBasicParsing
    
    # Распаковка
    if (Test-Path $windivertZip) {
        if (-not (Test-Path $windivertTemp)) {
            New-Item -ItemType Directory -Path $windivertTemp | Out-Null
        }
        
        Expand-Archive -Path $windivertZip -DestinationPath $windivertTemp -Force
        
        # Копирование файлов
        Copy-Item "$windivertTemp\WinDivert-2.2.2-W\x64\WinDivert64.dll" -Destination "." -Force
        Copy-Item "$windivertTemp\WinDivert-2.2.2-W\x64\WinDivert64.sys" -Destination "." -Force
        
        Write-Host "    WinDivert установлен!" -ForegroundColor Green
    }
} catch {
    Write-Host "[!] Не удалось скачать WinDivert автоматически" -ForegroundColor Red
    Write-Host ""
    Write-Host "    Скачайте вручную с:" -ForegroundColor Yellow
    Write-Host "    https://github.com/basil00/Divert/releases/download/v2.2.2/WinDivert-2.2.2-W.zip" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "    Распакуйте и скопируйте в эту папку:" -ForegroundColor Yellow
    Write-Host "    - WinDivert64.dll" -ForegroundColor Cyan
    Write-Host "    - WinDivert64.sys" -ForegroundColor Cyan
    Write-Host ""
}

# Очистка временных файлов
if (Test-Path $windivertZip) { Remove-Item $windivertZip -Force }
if (Test-Path $windivertTemp) { Remove-Item $windivertTemp -Recurse -Force }

Write-Host ""

# Скачивание winws2 из релизов zapret2
Write-Host "[*] Скачивание winws2..." -ForegroundColor Cyan
$zapret2ReleasesUrl = "https://api.github.com/repos/bol-van/zapret2/releases/latest"

try {
    $release = Invoke-RestMethod -Uri $zapret2ReleasesUrl -Headers $headers
    
    # Ищем файл с winws2
    $winws2Asset = $release.assets | Where-Object { $_.name -like "*win*" -and $_.name -like "*.zip" } | Select-Object -First 1
    
    if ($winws2Asset) {
        Write-Host "    Найдено: $($winws2Asset.name)" -ForegroundColor Green
        
        $winws2Zip = "$env:TEMP\winws2.zip"
        $winws2Temp = "$env:TEMP\winws2"
        
        Invoke-WebRequest -Uri $winws2Asset.browser_download_url -OutFile $winws2Zip -Headers $headers -UseBasicParsing
        
        if (Test-Path $winws2Zip) {
            if (-not (Test-Path $winws2Temp)) {
                New-Item -ItemType Directory -Path $winws2Temp | Out-Null
            }
            
            Expand-Archive -Path $winws2Zip -DestinationPath $winws2Temp -Force
            
            # Копирование winws2.exe
            $winws2Exe = Get-ChildItem -Path $winws2Temp -Recurse -Filter "winws2.exe" | Select-Object -First 1
            if ($winws2Exe) {
                Copy-Item $winws2Exe.FullName -Destination "." -Force
                Write-Host "    winws2.exe установлен!" -ForegroundColor Green
            }
        }
    } else {
        Write-Host "[!] Не найден winws2 в релизах" -ForegroundColor Red
    }
} catch {
    Write-Host "[!] Не удалось скачать winws2 автоматически" -ForegroundColor Red
    Write-Host ""
    Write-Host "    Скачайте вручную с:" -ForegroundColor Yellow
    Write-Host "    https://github.com/bol-van/zapret2/releases" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "    Распакуйте и скопируйте в эту папку:" -ForegroundColor Yellow
    Write-Host "    - winws2.exe" -ForegroundColor Cyan
    Write-Host ""
}

# Очистка временных файлов
if (Test-Path $winws2Zip) { Remove-Item $winws2Zip -Force }
if (Test-Path $winws2Temp) { Remove-Item $winws2Temp -Recurse -Force }

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Установка завершена!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Проверка наличия всех файлов
Write-Host "[*] Проверка файлов..." -ForegroundColor Cyan

$requiredFiles = @("winws2.exe", "WinDivert64.dll", "WinDivert64.sys", "zapret2_tui.py", "start.bat")
$allPresent = $true

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "    [OK] $file" -ForegroundColor Green
    } else {
        Write-Host "    [!] $file - ОТСУТСТВУЕТ" -ForegroundColor Red
        $allPresent = $false
    }
}

Write-Host ""

if ($allPresent) {
    Write-Host "Все файлы на месте!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Запуск Zapret2 TUI..." -ForegroundColor Cyan
    Write-Host ""
    
    # Запуск TUI
    python zapret2_tui.py
} else {
    Write-Host ""
    Write-Host "Некоторые файлы отсутствуют!" -ForegroundColor Red
    Write-Host "Скачайте их вручную (см. сообщения выше)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Нажмите любую клавишу для выхода..." -ForegroundColor Gray
    pause
}
