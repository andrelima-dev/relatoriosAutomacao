"""Paleta e folha de estilo (QSS) da aplicação.

Tema único, construído sobre azul: fundo e cartões em azuis claros, cabeçalho
e log em azul escuro. O contraste vem da diferença de luminosidade entre essas
camadas, não de bordas fortes.
"""

import os

from core.utils import resource_path

CORES = {
    # camadas claras
    "bg": "#e7eef8",
    "superficie": "#ffffff",
    "superficie2": "#f1f6fd",
    "campo": "#ffffff",
    "borda": "#c6d8ef",
    "borda_forte": "#9db9dc",
    "aba_inativa": "#d8e5f6",
    # camadas escuras
    "escuro": "#0f2f5e",
    "escuro2": "#16406f",
    "log_bg": "#0d2748",
    "log_texto": "#d5e4f7",
    # legiveis sobre o fundo escuro do log
    "log_ok": "#6ee7a0",
    "log_erro": "#ff9a92",
    "log_info": "#8cc2ff",
    # texto
    "texto": "#10243d",
    "texto_dim": "#4f6885",
    "texto_claro": "#eaf2fd",
    # azuis de ação
    "acento": "#1565c0",
    "acento_hover": "#0f4f9e",
    "acento_forte": "#0d47a1",
    # semânticas (só no log e em avisos)
    "ok": "#1b7f4d",
    "erro": "#c62828",
    "aviso": "#a35c00",
}

QSS = """
QWidget {{
    background: {bg};
    color: {texto};
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 13px;
}}

QToolTip {{
    background: {escuro};
    color: {texto_claro};
    border: none;
    padding: 5px 8px;
}}

/* ── Cabeçalho escuro ────────────────────────────────────────── */
#Cabecalho {{ background: {escuro}; }}
#TituloApp {{ font-size: 18px; font-weight: 600; color: {texto_claro}; }}
#SubtituloApp {{ font-size: 12px; color: #a9c4e6; }}

/* ── Cartões ─────────────────────────────────────────────────── */
QGroupBox {{
    background: {superficie};
    border: 1px solid {borda};
    border-radius: 8px;
    margin-top: 16px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 1px;
    padding: 1px 7px;
    color: {acento_forte};
}}

QLabel {{ background: transparent; }}
#Dica {{ color: {texto_dim}; font-size: 12px; }}
#Aviso {{ color: {aviso}; font-size: 12px; }}
#Status {{ color: {texto_dim}; font-size: 12px; }}
#Credito {{ color: {borda_forte}; font-size: 11px; }}
#Preview {{ color: {acento_forte}; font-size: 13px; font-weight: 600; }}

/* ── Campos ──────────────────────────────────────────────────── */
QLineEdit, QComboBox, QDateEdit, QPlainTextEdit {{
    background: {campo};
    border: 1px solid {borda_forte};
    border-radius: 6px;
    padding: 6px 9px;
    color: {texto};
    selection-background-color: {acento};
    selection-color: #ffffff;
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
    border: 2px solid {acento};
    padding: 5px 8px;
}}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{
    background: {superficie2};
    color: {texto_dim};
    border-color: {borda};
}}
QLineEdit[somenteLeitura="true"] {{ background: {superficie2}; color: {texto_dim}; }}

/* A seta vem de um PNG: o truque de triângulo por bordas não funciona em
   subcontrole (vira um quadrado) e estilizar ::drop-down sem imagem faz o Qt
   parar de desenhar a seta nativa. */
QComboBox::drop-down, QDateEdit::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow, QDateEdit::down-arrow {{
    image: url({seta});
    width: 12px;
    height: 12px;
    margin-right: 7px;
}}
QComboBox::down-arrow:disabled, QDateEdit::down-arrow:disabled {{
    image: url({seta_off});
}}
QComboBox QAbstractItemView {{
    background: {campo};
    color: {texto};
    border: 1px solid {borda_forte};
    selection-background-color: {acento};
    selection-color: #ffffff;
    outline: none;
}}
QCalendarWidget QWidget {{ background: {superficie}; color: {texto}; }}
QCalendarWidget QAbstractItemView {{
    background: {campo};
    color: {texto};
    selection-background-color: {acento};
    selection-color: #ffffff;
}}

/* ── Botões ──────────────────────────────────────────────────── */
QPushButton {{
    background: {superficie2};
    border: 1px solid {borda_forte};
    border-radius: 6px;
    padding: 7px 14px;
    color: {acento_forte};
}}
QPushButton:hover {{ background: {aba_inativa}; border-color: {acento}; }}
QPushButton:pressed {{ background: {borda}; }}
QPushButton:disabled {{
    background: {superficie2};
    color: #9bacc2;
    border-color: {borda};
}}

/* Ação principal de cada aba */
QPushButton#Acao {{
    background: {acento};
    border: none;
    color: #ffffff;
    font-weight: 600;
    font-size: 14px;
    padding: 10px 22px;
    border-radius: 6px;
}}
QPushButton#Acao:hover {{ background: {acento_hover}; }}
QPushButton#Acao:pressed {{ background: {acento_forte}; }}
QPushButton#Acao:disabled {{ background: {aba_inativa}; color: #93a8c2; }}

QPushButton#Link {{
    background: transparent;
    border: none;
    color: {acento};
    padding: 3px 6px;
}}
QPushButton#Link:hover {{ text-decoration: underline; }}

/* ── Marcadores ──────────────────────────────────────────────── */
QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 17px;
    height: 17px;
    border: 1px solid {borda_forte};
    background: {campo};
}}
QCheckBox::indicator {{ border-radius: 4px; }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {acento}; }}
QCheckBox::indicator:checked {{
    background: {acento};
    border-color: {acento};
    image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png);
}}
/* Anel + ponto: uma borda grossa achataria o arredondamento */
QRadioButton::indicator:checked {{
    border: 1px solid {acento};
    border-radius: 9px;
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                stop:0 {acento}, stop:0.5 {acento},
                stop:0.55 {campo}, stop:1 {campo});
}}
QCheckBox:disabled, QRadioButton:disabled {{ color: {texto_dim}; }}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background: {superficie2};
    border-color: {borda};
}}

/* ── Abas ────────────────────────────────────────────────────── */
QTabWidget::pane {{
    background: {superficie2};
    border: 1px solid {borda};
    border-radius: 8px;
    top: -1px;
}}
QTabBar::tab {{
    background: {aba_inativa};
    color: {texto_dim};
    border: 1px solid {borda};
    border-bottom: none;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    padding: 8px 15px;
    margin-right: 3px;
}}
QTabBar::tab:hover {{ background: {borda}; color: {texto}; }}
QTabBar::tab:selected {{
    background: {superficie2};
    color: {acento_forte};
    font-weight: 600;
}}

/* ── Listas ──────────────────────────────────────────────────── */
QListWidget, QTreeWidget {{
    background: {campo};
    border: 1px solid {borda_forte};
    border-radius: 6px;
    outline: none;
}}
QListWidget::item, QTreeWidget::item {{ padding: 5px 4px; }}
QListWidget::item:hover, QTreeWidget::item:hover {{ background: {superficie2}; }}
QListWidget::item:selected, QTreeWidget::item:selected {{
    background: {acento};
    color: #ffffff;
}}
QHeaderView::section {{
    background: {aba_inativa};
    color: {acento_forte};
    border: none;
    border-bottom: 1px solid {borda};
    padding: 6px;
    font-weight: 600;
}}

/* ── Rolagem ─────────────────────────────────────────────────── */
QScrollArea {{ border: none; background: {bg}; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {borda_forte};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {acento}; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; }}
QScrollBar::handle:horizontal {{
    background: {borda_forte};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ── Progresso ───────────────────────────────────────────────── */
QProgressBar {{
    background: {aba_inativa};
    border: none;
    border-radius: 5px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {acento}; border-radius: 4px; }}

/* ── Log escuro ──────────────────────────────────────────────── */
#Log {{
    background: {log_bg};
    color: {log_texto};
    border: none;
    border-radius: 6px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    padding: 4px;
}}

/* ── Rodapé ──────────────────────────────────────────────────── */
#Rodape {{
    background: {superficie};
    border-top: 1px solid {borda};
}}

/* ── Diálogo de carregamento ─────────────────────────────────── */
#CaixaCarregando {{
    background: {superficie};
    border: 2px solid {acento};
    border-radius: 10px;
}}
"""


def paleta() -> dict:
    return CORES


def folha_de_estilo() -> str:
    # O QSS precisa de caminho absoluto com barras normais, inclusive no .exe
    def caminho(nome: str) -> str:
        return resource_path(os.path.join("assets", nome)).replace("\\", "/")

    return QSS.format(seta=caminho("seta_baixo.png"),
                      seta_off=caminho("seta_baixo_off.png"), **CORES)
