import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from core.utils import resource_path
from ui.tema import folha_de_estilo, paleta

_LARGURA, _ALTURA = 420, 220


def _criar_splash(cores) -> QSplashScreen:
    """Tela de abertura desenhada à mão — some assim que a janela abre."""
    pix = QPixmap(_LARGURA, _ALTURA)
    pix.fill(QColor(cores["superficie"]))

    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    p.fillRect(0, _ALTURA - 4, _LARGURA, 4, QColor(cores["acento"]))
    p.setPen(QColor(cores["borda_forte"]))
    p.drawRect(0, 0, _LARGURA - 1, _ALTURA - 1)

    logo = resource_path(os.path.join("assets", "logo.png"))
    y_texto = 96
    if os.path.exists(logo):
        img = QPixmap(logo)
        if not img.isNull():
            img = img.scaledToHeight(70, Qt.SmoothTransformation)
            p.drawPixmap((_LARGURA - img.width()) // 2, 30, img)
            y_texto = 124

    p.setPen(QColor(cores["texto"]))
    p.setFont(QFont("Segoe UI", 15, QFont.Bold))
    p.drawText(0, y_texto, _LARGURA, 30, Qt.AlignCenter,
               "Gerador de Relatórios OAB")

    p.setPen(QColor(cores["texto_dim"]))
    p.setFont(QFont("Segoe UI", 9))
    p.drawText(0, y_texto + 30, _LARGURA, 24, Qt.AlignCenter, "Carregando...")

    p.setPen(QColor(cores["borda_forte"]))
    p.setFont(QFont("Segoe UI", 8))
    p.drawText(0, _ALTURA - 30, _LARGURA - 14, 20,
               Qt.AlignRight | Qt.AlignVCenter, "created by andrelima-dev")
    p.end()

    return QSplashScreen(pix, Qt.WindowStaysOnTopHint)


if __name__ == "__main__":
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Gerador de Relatórios OAB")
    cores = paleta()
    qt_app.setStyleSheet(folha_de_estilo())

    splash = _criar_splash(cores)
    splash.show()
    qt_app.processEvents()

    from app import App  # import pesado (pandas, openpyxl) acontece aqui

    janela = App()
    janela.show()
    splash.finish(janela)

    sys.exit(qt_app.exec())
