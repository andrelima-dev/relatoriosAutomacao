@echo off
echo Gerando executavel...

"%APPDATA%\Python\Python313\Scripts\pyinstaller.exe" ^
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
