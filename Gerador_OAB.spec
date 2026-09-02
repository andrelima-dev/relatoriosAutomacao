# -*- mode: python ; coding: utf-8 -*-

# Módulos Qt que a aplicação não usa. Sem estes excludes o PySide6 arrasta
# WebEngine, Quick/QML, 3D e multimídia, quase triplicando o executável.
_QT_NAO_USADOS = [
    'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineQuick', 'PySide6.QtWebView',
    'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DAnimation',
    'PySide6.Qt3DExtras', 'PySide6.Qt3DInput', 'PySide6.Qt3DLogic',
    'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtGraphs',
    'PySide6.QtGraphsWidgets',
    'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQuickWidgets',
    'PySide6.QtQuickControls2', 'PySide6.QtQml', 'PySide6.QtQmlModels',
    'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
    'PySide6.QtSpatialAudio',
    'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtPositioning',
    'PySide6.QtLocation', 'PySide6.QtSerialPort', 'PySide6.QtSerialBus',
    'PySide6.QtSensors', 'PySide6.QtWebSockets', 'PySide6.QtWebChannel',
    'PySide6.QtHttpServer', 'PySide6.QtNetworkAuth',
    'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtHelp', 'PySide6.QtDesigner',
    'PySide6.QtUiTools', 'PySide6.QtScxml', 'PySide6.QtStateMachine',
    'PySide6.QtRemoteObjects', 'PySide6.QtTextToSpeech',
    'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtSvgWidgets',
    'PySide6.QtConcurrent', 'PySide6.QtDBus',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/logo.png', 'assets'), ('assets/logo.ico', 'assets'),
           ('assets/seta_baixo.png', 'assets'),
           ('assets/seta_baixo_off.png', 'assets')],
    hiddenimports=['lxml.etree', 'openpyxl', 'pandas'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'ttkbootstrap', 'matplotlib', 'IPython',
              'notebook', 'jinja2'] + _QT_NAO_USADOS,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Gerador_OAB',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/logo.ico',
)
