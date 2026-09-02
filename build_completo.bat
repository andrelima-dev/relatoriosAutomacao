@echo off
REM Gera o executavel e o instalador em um passo so.
REM Resultado final: installer_output\Gerador_OAB_Setup.exe

echo ############################################
echo #  Gerador de Relatorios OAB - Build total #
echo ############################################
echo.

call build.bat
if errorlevel 1 exit /b 1

call create_installer.bat
if errorlevel 1 exit /b 1
