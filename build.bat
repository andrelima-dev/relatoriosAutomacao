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
echo Limpando build anterior...
if exist "build" rmdir /s /q "build"
if exist "dist\Gerador_OAB.exe" del /q "dist\Gerador_OAB.exe"

echo.
echo Gerando executavel (Gerador_OAB.spec)...
python -m PyInstaller --noconfirm Gerador_OAB.spec
if errorlevel 1 (
    echo [ERRO] Falha ao gerar executavel.
    pause
    exit /b 1
)

if not exist "dist\Gerador_OAB.exe" (
    echo [ERRO] dist\Gerador_OAB.exe nao foi gerado.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Concluido! Executavel em: dist\Gerador_OAB.exe
echo ========================================
pause
