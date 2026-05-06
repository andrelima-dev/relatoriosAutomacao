@echo off
echo Instalando dependencias...
pip install -r requirements.txt

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

echo.
echo Concluido! Executavel em: dist\Gerador_OAB.exe
pause
