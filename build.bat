@echo off
echo ========================================
echo   Gerador de Relatorios OAB - Build
echo ========================================
echo.

REM Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo.
    echo Instale o Python 3.10+ em: https://www.python.org/downloads/
    echo Durante a instalacao, marque: "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do echo [OK] %%i encontrado.
echo.

echo Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo Gerando executavel...
python -m PyInstaller ^
    --onefile --windowed ^
    --name "Gerador_OAB" ^
    --add-data "assets;assets" ^
    --add-data "core;core" ^
    --hidden-import lxml.etree ^
    --hidden-import openpyxl ^
    --hidden-import pandas ^
    main.py

if errorlevel 1 (
    echo [ERRO] Falha ao gerar executavel.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Concluido! Executavel em: dist\Gerador_OAB.exe
echo ========================================
pause
