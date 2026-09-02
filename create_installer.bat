@echo off
echo ========================================
echo   Gerador de Relatorios OAB - Installer
echo ========================================
echo.

REM Caminhos comuns do Inno Setup
set ISCC=""
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe"       set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"

if %ISCC%=="" (
    echo [ERRO] Inno Setup nao encontrado!
    echo.
    echo Baixe e instale gratuitamente em: https://jrsoftware.org/isdl.php
    echo Depois execute este script novamente.
    echo.
    pause
    exit /b 1
)

if not exist "dist\Gerador_OAB.exe" (
    echo [ERRO] dist\Gerador_OAB.exe nao encontrado.
    echo Execute build.bat primeiro para gerar o executavel.
    echo.
    pause
    exit /b 1
)

REM As imagens do assistente sao geradas a partir do logo
if not exist "assets\wizard.bmp" (
    echo Gerando imagens do assistente...
    python gerar_imagens_instalador.py
    if errorlevel 1 (
        echo [ERRO] Falha ao gerar as imagens do assistente.
        pause
        exit /b 1
    )
)

echo Compilando installer...
%ISCC% installer.iss

if errorlevel 1 (
    echo [ERRO] Falha ao compilar o installer.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Concluido! Installer em: installer_output\Gerador_OAB_Setup.exe
echo ========================================
echo.
echo Envie esse unico arquivo para o outro usuario.
echo Ele detecta e remove a versao anterior automaticamente.
echo.
pause
