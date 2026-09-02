"""Janela principal (PySide6).

O pacote `core` é agnóstico de interface — recebe DataFrames e callbacks —,
então toda a lógica de geração é reaproveitada sem alteração. O trabalho pesado
roda em QThreadPool e volta para a interface por sinais.
"""

import html
import os
import sys
import unicodedata
from datetime import datetime

from PySide6.QtCore import QDate, QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.csv_oabma import (
    ANOS_JOVEM_PADRAO,
    exportar_csv_oabma,
    mapear_para_oabma,
    periodo_jovem_padrao,
)
from core.gerador import (
    CATEGORIAS_ATIVAS,
    SITUACOES_ATIVAS,
    gerar_relatorios,
    gerar_relatorios_separados,
)
from core.leitor import carregar_planilha
from core.utils import get_col, is_date_col, resource_path
from ui.dialogos import (
    DialogoAdimplencia,
    DialogoCarregando,
    DialogoColunas,
    DialogoFiltrosAtivos,
    DialogoJovemAdvogado,
    DialogoListaMarcavel,
    DialogoMapeamentoCsv,
)
from ui.tema import paleta

_DATA_SENTINELA = QDate(1900, 1, 1)
_ALTURA_LOG = 68


class _Sinais(QObject):
    progresso = Signal(int)
    log = Signal(str, str)
    falhou = Signal(str)
    terminou = Signal(object)


class Tarefa(QRunnable):
    """Executa uma função em outra thread e devolve o resultado por sinal."""

    def __init__(self, fn):
        super().__init__()
        self.setAutoDelete(False)
        self._fn = fn
        self.sinais = _Sinais()

    def run(self):
        try:
            resultado = self._fn(self.sinais)
        except Exception as exc:
            self.sinais.falhou.emit(str(exc))
        else:
            self.sinais.terminou.emit(resultado)


def _titulo(texto: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet("font-weight: 600;")
    return lbl


def _dica(texto: str) -> QLabel:
    lbl = QLabel(texto, objectName="Dica", wordWrap=True)
    return lbl


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerador de Relatórios OAB")
        self.setAcceptDrops(True)
        self.setMinimumSize(860, 560)

        ico = resource_path(os.path.join("assets", "logo.ico"))
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))

        self._df = None
        self._caminho = ""
        self._ws_names: list[str] = []
        self._tarefas: set[Tarefa] = set()
        self._dlg_carregando: DialogoCarregando | None = None

        self._uf_col: str | None = None
        self._valores_uf: list[str] = []
        self._comarca_col: str | None = None
        self._valores_comarca: list[str] = []

        self._cats_selecionadas: set[str] = set(CATEGORIAS_ATIVAS)
        self._sits_selecionadas: set[str] = set(SITUACOES_ATIVAS)
        self._cats_disponiveis: list[str] = []
        self._sits_disponiveis: list[str] = []
        self._filtros_customizados = False

        self._cols_disponiveis: list[str] = []
        self._colunas_personalizado: list[str] = []
        self._filtros_coluna_personalizado: dict[str, list[str]] = {}

        self._sep_subsecoes: list[str] = []
        self._sep_colunas: list[str] = []
        self._filtros_coluna_sep: dict[str, list[str]] = {}
        self._sep_adim_col = ""
        self._sep_val_adimplente: list[str] = []
        self._sep_val_inadimplente: list[str] = []

        self._date_cols: list[str] = []

        # Jovem advogado no CSV: recorte por data de compromisso
        self._jovem_personalizado = False
        self._jovem_anos = ANOS_JOVEM_PADRAO
        self._jovem_desde, self._jovem_ate = periodo_jovem_padrao()

        self._linhas_log: list[tuple[str, str]] = []

        self._construir_ui()
        self._atualizar_botoes()
        self._dimensionar()

    def _dimensionar(self):
        """Ajusta ao conteúdo, sem estourar a área útil da tela.

        O QScrollArea não propaga a altura do conteúdo, então sizeHint() da
        janela ignoraria o corpo — as três faixas são somadas na mão."""
        tela = QGuiApplication.primaryScreen().availableGeometry()
        corpo = self._corpo_w.sizeHint()
        alvo_altura = (self._cab.sizeHint().height() + corpo.height()
                       + self._rod.sizeHint().height() + 8)
        largura = max(min(corpo.width() + 40, tela.width() - 80), 900)
        altura = max(min(alvo_altura, tela.height() - 90), 600)
        self.resize(largura, altura)
        quadro = self.frameGeometry()
        quadro.moveCenter(tela.center())
        if quadro.top() < tela.top():
            quadro.moveTop(tela.top())
        self.move(quadro.topLeft())

    # ── Construção da interface ──────────────────────────────────────────────

    def _construir_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self._cab = self._cabecalho()
        raiz.addWidget(self._cab)

        area = QScrollArea(widgetResizable=True)
        self._corpo_w = QWidget()
        corpo = QVBoxLayout(self._corpo_w)
        corpo.setContentsMargins(16, 12, 16, 12)
        corpo.setSpacing(11)
        corpo.addWidget(self._bloco_arquivo())
        corpo.addWidget(self._bloco_relatorios())
        corpo.addWidget(self._bloco_data())
        corpo.addStretch(1)
        area.setWidget(self._corpo_w)
        raiz.addWidget(area, 1)

        self._rod = self._rodape()
        raiz.addWidget(self._rod)

    def _cabecalho(self) -> QWidget:
        cab = QFrame(objectName="Cabecalho")
        lin = QHBoxLayout(cab)
        lin.setContentsMargins(20, 14, 20, 14)

        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(QLabel("Gerador de Relatórios OAB", objectName="TituloApp"))
        textos.addWidget(QLabel(
            "Selecione o arquivo, escolha o que gerar e clique em Gerar.",
            objectName="SubtituloApp"))
        lin.addLayout(textos)
        lin.addStretch(1)

        logo = resource_path(os.path.join("assets", "logo.png"))
        if os.path.exists(logo):
            pix = QPixmap(logo)
            if not pix.isNull():
                lbl = QLabel()
                lbl.setPixmap(pix.scaledToHeight(46, Qt.SmoothTransformation))
                lin.addWidget(lbl)
        return cab

    def _bloco_arquivo(self) -> QWidget:
        grupo = QGroupBox("1 · Arquivo de origem")
        col = QVBoxLayout(grupo)
        col.setSpacing(9)

        # QFormLayout mantém os rótulos alinhados entre si
        form = QFormLayout()
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self._ed_arquivo = QLineEdit(readOnly=True,
                                     placeholderText="Nenhum arquivo selecionado — "
                                                     "clique ao lado ou arraste aqui")
        self._ed_arquivo.setProperty("somenteLeitura", "true")
        b = QPushButton("Selecionar arquivo...")
        b.clicked.connect(self._selecionar_arquivo)
        form.addRow("Arquivo:", self._com_botao(self._ed_arquivo, b))

        self._cmb_planilha = QComboBox()
        self._cmb_planilha.currentIndexChanged.connect(self._ao_trocar_planilha)
        form.addRow("Planilha:", self._cmb_planilha)
        self._linha_planilha = form.rowCount() - 1
        form.setRowVisible(self._linha_planilha, False)

        self._ed_saida = QLineEdit(placeholderText="Pasta de destino dos relatórios")
        b2 = QPushButton("Alterar...")
        b2.clicked.connect(self._selecionar_pasta)
        form.addRow("Salvar em:", self._com_botao(self._ed_saida, b2))

        self._ed_nome = QLineEdit("RELATORIO CADASTRO ADVOGADOS GERAL")
        form.addRow("Nome base:", self._ed_nome)
        self._form_arquivo = form
        col.addLayout(form)

        self._lbl_preview = QLabel("Nenhum arquivo selecionado.", objectName="Preview")
        col.addWidget(self._lbl_preview)
        return grupo

    @staticmethod
    def _com_botao(campo: QWidget, botao: QWidget) -> QWidget:
        caixa = QWidget()
        lin = QHBoxLayout(caixa)
        lin.setContentsMargins(0, 0, 0, 0)
        lin.setSpacing(8)
        lin.addWidget(campo, 1)
        lin.addWidget(botao)
        return caixa

    def _bloco_relatorios(self) -> QWidget:
        grupo = QGroupBox("2 · O que gerar")
        col = QVBoxLayout(grupo)

        self._abas = QTabWidget()
        self._abas.addTab(self._aba_prontos(), "Relatórios prontos")
        self._abas.addTab(self._aba_personalizado(), "Personalizado")
        self._abas.addTab(self._aba_subsecao(), "Por subseção")
        self._abas.addTab(self._aba_csv(), "CSV OAB-MA")
        # O painel acompanha a altura da aba atual. Sem isto o QTabWidget
        # reserva a altura da maior aba e sobra um vazio nas demais.
        self._abas.currentChanged.connect(self._ajustar_altura_aba)
        self._ajustar_altura_aba(0)
        col.addWidget(self._abas)
        return grupo

    def _ajustar_altura_aba(self, atual: int):
        """Fixa o painel na altura da aba atual.

        Só marcar as outras páginas como Ignored não basta: o QTabWidget mantém
        o sizeHint da maior página, sobrando um vazio nas abas curtas."""
        for i in range(self._abas.count()):
            self._abas.widget(i).setSizePolicy(
                QSizePolicy.Preferred,
                QSizePolicy.Preferred if i == atual else QSizePolicy.Ignored)
        pagina = self._abas.widget(atual)
        pagina.adjustSize()
        self._abas.setFixedHeight(
            pagina.sizeHint().height()
            + self._abas.tabBar().sizeHint().height() + 18)

    def _aba_prontos(self) -> QWidget:
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(14, 14, 14, 14)
        col.setSpacing(8)

        self._chk_geral = QCheckBox("Geral — todos os registros do arquivo")
        self._chk_geral.setChecked(True)
        self._chk_geral.toggled.connect(self._atualizar_botoes)
        col.addWidget(self._chk_geral)

        lin = QHBoxLayout()
        self._chk_ativos = QCheckBox("Apenas ativos — só advogados em situação regular")
        self._chk_ativos.setChecked(True)
        self._chk_ativos.toggled.connect(self._atualizar_botoes)
        lin.addWidget(self._chk_ativos)
        self._btn_filtros = QPushButton("Filtros...")
        self._btn_filtros.setEnabled(False)
        self._btn_filtros.clicked.connect(self._abrir_filtros_ativos)
        lin.addWidget(self._btn_filtros)
        lin.addStretch(1)
        col.addLayout(lin)

        self._chk_estagiarios = QCheckBox("+ Incluir estagiários no filtro de ativos")
        self._chk_estagiarios.setEnabled(False)
        self._chk_estagiarios.toggled.connect(self._ao_alternar_estagiarios)
        col.addWidget(self._chk_estagiarios)

        self._lbl_estagiarios = _dica("")
        col.addWidget(self._lbl_estagiarios)

        col.addWidget(_dica(
            "Sai com todas as colunas. Para escolher colunas ou filtrar valores, "
            "use a aba Personalizado."))

        self._btn_prontos = QPushButton("▶  Gerar relatórios prontos",
                                        objectName="Acao")
        self._btn_prontos.setEnabled(False)
        self._btn_prontos.clicked.connect(self._gerar_prontos)
        col.addWidget(self._btn_prontos, 0, Qt.AlignLeft)
        col.addStretch(1)
        return w

    def _aba_personalizado(self) -> QWidget:
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(14, 14, 14, 14)
        col.setSpacing(8)

        lin = QHBoxLayout()
        self._btn_colunas = QPushButton("Selecionar colunas...")
        self._btn_colunas.setEnabled(False)
        self._btn_colunas.clicked.connect(self._abrir_seletor_colunas)
        lin.addWidget(self._btn_colunas)
        lin.addStretch(1)
        col.addLayout(lin)

        self._lbl_colunas = _dica("Nenhuma coluna selecionada")
        col.addWidget(self._lbl_colunas)

        lin2 = QHBoxLayout()
        lin2.addWidget(QLabel("Base:"))
        self._rb_pers_ativos = QRadioButton("Apenas ativos")
        self._rb_pers_ativos.setChecked(True)
        self._rb_pers_ativos.setEnabled(False)
        self._rb_pers_ativos.toggled.connect(self._ao_trocar_base_personalizado)
        self._rb_pers_todos = QRadioButton("Todos")
        self._rb_pers_todos.setEnabled(False)
        lin2.addWidget(self._rb_pers_ativos)
        lin2.addWidget(self._rb_pers_todos)
        lin2.addStretch(1)
        col.addLayout(lin2)

        self._chk_estagiarios_pers = QCheckBox("+ Incluir estagiários no filtro de ativos")
        self._chk_estagiarios_pers.setEnabled(False)
        self._chk_estagiarios_pers.toggled.connect(self._ao_alternar_estagiarios_pers)
        col.addWidget(self._chk_estagiarios_pers)

        self._lbl_estagiarios_pers = _dica("")
        col.addWidget(self._lbl_estagiarios_pers)

        col.addWidget(_dica(
            "Para filtrar valores: em “Selecionar colunas...”, destaque a coluna "
            "e use “Filtrar valores...”."))

        self._btn_pers = QPushButton("▶  Gerar relatório personalizado",
                                     objectName="Acao")
        self._btn_pers.setEnabled(False)
        self._btn_pers.clicked.connect(self._gerar_personalizado)
        col.addWidget(self._btn_pers, 0, Qt.AlignLeft)
        col.addStretch(1)
        return w

    def _aba_subsecao(self) -> QWidget:
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(14, 14, 14, 14)
        col.setSpacing(8)

        lin = QHBoxLayout()
        self._btn_sep_subsecoes = QPushButton("Selecionar subseções...")
        self._btn_sep_subsecoes.setEnabled(False)
        self._btn_sep_subsecoes.clicked.connect(self._abrir_seletor_subsecoes)
        lin.addWidget(self._btn_sep_subsecoes)
        self._btn_sep_colunas = QPushButton("Selecionar colunas...")
        self._btn_sep_colunas.setEnabled(False)
        self._btn_sep_colunas.clicked.connect(self._abrir_seletor_colunas_sep)
        lin.addWidget(self._btn_sep_colunas)
        lin.addStretch(1)
        col.addLayout(lin)

        self._lbl_sep_sub = _dica("Nenhuma subseção selecionada")
        self._lbl_sep_col = _dica("Todas as colunas")
        col.addWidget(self._lbl_sep_sub)
        col.addWidget(self._lbl_sep_col)

        lin2 = QHBoxLayout()
        self._chk_sep_adim = QCheckBox(
            "Separar cada subseção em adimplentes × inadimplentes")
        self._chk_sep_adim.setEnabled(False)
        self._chk_sep_adim.toggled.connect(self._ao_alternar_separar_adim)
        lin2.addWidget(self._chk_sep_adim)
        self._btn_sep_adim = QPushButton("Adimplência...")
        self._btn_sep_adim.clicked.connect(self._abrir_config_adimplencia)
        self._btn_sep_adim.hide()
        lin2.addWidget(self._btn_sep_adim)
        lin2.addStretch(1)
        col.addLayout(lin2)

        self._lbl_sep_adim = _dica("Adimplência não configurada")
        col.addWidget(self._lbl_sep_adim)

        lin3 = QHBoxLayout()
        lin3.addWidget(QLabel("Base:"))
        self._rb_sep_ativos = QRadioButton("Apenas ativos")
        self._rb_sep_ativos.setEnabled(False)
        self._rb_sep_todos = QRadioButton("Todos")
        self._rb_sep_todos.setChecked(True)
        self._rb_sep_todos.setEnabled(False)
        lin3.addWidget(self._rb_sep_ativos)
        lin3.addWidget(self._rb_sep_todos)
        lin3.addStretch(1)
        col.addLayout(lin3)

        col.addWidget(_dica(
            "1 arquivo por subseção. Sem seleção, gera todas."))

        self._btn_separados = QPushButton("▶  Gerar relatórios separados",
                                          objectName="Acao")
        self._btn_separados.setEnabled(False)
        self._btn_separados.clicked.connect(self._gerar_separados_click)
        col.addWidget(self._btn_separados, 0, Qt.AlignLeft)
        col.addStretch(1)
        return w

    def _aba_csv(self) -> QWidget:
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(14, 14, 14, 14)
        col.setSpacing(8)

        lin = QHBoxLayout()
        self._btn_csv_mapa = QPushButton("Ver mapeamento...")
        self._btn_csv_mapa.setEnabled(False)
        self._btn_csv_mapa.clicked.connect(self._abrir_mapeamento_csv)
        lin.addWidget(self._btn_csv_mapa)
        lin.addStretch(1)
        col.addLayout(lin)

        lin2 = QHBoxLayout()
        lin2.addWidget(QLabel("Base:"))
        self._rb_csv_ativos = QRadioButton("Apenas ativos")
        self._rb_csv_ativos.setChecked(True)
        self._rb_csv_ativos.setEnabled(False)
        self._rb_csv_todos = QRadioButton("Todos")
        self._rb_csv_todos.setEnabled(False)
        lin2.addWidget(self._rb_csv_ativos)
        lin2.addWidget(self._rb_csv_todos)
        lin2.addStretch(1)
        col.addLayout(lin2)

        lin3 = QHBoxLayout()
        self._btn_csv_jovem = QPushButton("Jovem advogado...")
        self._btn_csv_jovem.setToolTip(
            "Período de compromisso que conta como jovem advogado")
        self._btn_csv_jovem.setEnabled(False)
        self._btn_csv_jovem.clicked.connect(self._abrir_config_jovem)
        lin3.addWidget(self._btn_csv_jovem)
        lin3.addStretch(1)
        col.addLayout(lin3)

        self._lbl_csv_adim = _dica("")
        self._lbl_csv_jovem = _dica("")
        col.addWidget(self._lbl_csv_adim)
        col.addWidget(self._lbl_csv_jovem)

        col.addWidget(_dica(
            "CSV com as 20 colunas do layout de importação. O mapeamento das "
            "colunas é automático — confira antes de importar."))

        self._btn_csv = QPushButton("▶  Gerar CSV de importação", objectName="Acao")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._gerar_csv)
        col.addWidget(self._btn_csv, 0, Qt.AlignLeft)
        col.addStretch(1)
        return w

    def _bloco_data(self) -> QWidget:
        grupo = QGroupBox("Filtro de data  ·  aplica-se a todos os relatórios")
        col = QVBoxLayout(grupo)
        col.setSpacing(8)

        lin = QHBoxLayout()
        self._chk_data = QCheckBox("Ativar filtro de data")
        self._chk_data.setEnabled(False)
        self._chk_data.toggled.connect(self._alternar_filtro_data)
        lin.addWidget(self._chk_data)
        lin.addSpacing(14)

        lin.addWidget(QLabel("Coluna:"))
        self._cmb_data = QComboBox()
        self._cmb_data.setEnabled(False)
        self._cmb_data.setMinimumWidth(200)
        lin.addWidget(self._cmb_data)

        lin.addSpacing(12)
        lin.addWidget(QLabel("De:"))
        self._data_de = self._campo_data()
        lin.addWidget(self._data_de)
        lin.addWidget(QLabel("Até:"))
        self._data_ate = self._campo_data()
        lin.addWidget(self._data_ate)
        lin.addStretch(1)
        col.addLayout(lin)

        col.addWidget(_dica(
            "Deixe em “— sem limite —” para filtrar só por um lado."))
        return grupo

    @staticmethod
    def _campo_data() -> QDateEdit:
        ed = QDateEdit()
        ed.setEnabled(False)
        ed.setCalendarPopup(True)
        ed.setDisplayFormat("dd/MM/yyyy")
        ed.setMinimumDate(_DATA_SENTINELA)
        ed.setSpecialValueText("— sem limite —")
        ed.setDate(_DATA_SENTINELA)
        return ed

    def _rodape(self) -> QWidget:
        rod = QFrame(objectName="Rodape")
        col = QVBoxLayout(rod)
        col.setContentsMargins(18, 10, 18, 12)
        col.setSpacing(7)

        topo = QHBoxLayout()
        self._lbl_status = QLabel(objectName="Status")
        topo.addWidget(self._lbl_status)
        topo.addStretch(1)
        self._btn_log = QPushButton("Ocultar log", objectName="Link")
        self._btn_log.clicked.connect(self._alternar_log)
        topo.addWidget(self._btn_log)
        col.addLayout(topo)

        self._barra = QProgressBar(maximum=100, value=0, textVisible=False)
        col.addWidget(self._barra)

        self._log = QPlainTextEdit(objectName="Log", readOnly=True)
        self._log.setFixedHeight(_ALTURA_LOG)
        self._log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        col.addWidget(self._log)

        credito = QLabel("created by andrelima-dev", objectName="Credito")
        credito.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        col.addWidget(credito)
        return rod

    def _alternar_log(self):
        mostrando = not self._log.isVisible()
        self._log.setVisible(mostrando)
        self._btn_log.setText("Ocultar log" if mostrando else "Mostrar log")
        if self.isMaximized() or self.isFullScreen():
            return
        # Sem encolher a janela junto, o espaco liberado viraria um vazio
        delta = _ALTURA_LOG + self._rod.layout().spacing()
        self.resize(self.width(),
                    max(self.height() + (delta if mostrando else -delta),
                        self.minimumHeight()))

    # ── Arrastar e soltar ────────────────────────────────────────────────────

    def dragEnterEvent(self, evento):
        urls = evento.mimeData().urls()
        if urls and urls[0].toLocalFile().lower().endswith(
                (".xml", ".xlsx", ".xlsm", ".xls")):
            evento.acceptProposedAction()

    def dropEvent(self, evento):
        urls = evento.mimeData().urls()
        if urls:
            self._carregar(urls[0].toLocalFile())

    # ── Carregamento do arquivo ──────────────────────────────────────────────

    def _selecionar_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo (XML ou Excel)", "",
            "Planilhas (*.xml *.xlsx *.xlsm);;XML (*.xml);;"
            "Excel (*.xlsx *.xlsm);;Todos os arquivos (*)",
        )
        if caminho:
            self._carregar(caminho)

    def _selecionar_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar pasta de saída")
        if pasta:
            self._ed_saida.setText(pasta)

    def _mostrar_carregando(self, msg: str):
        if self._dlg_carregando is None:
            self._dlg_carregando = DialogoCarregando(self, msg)
            self._dlg_carregando.show()
        else:
            self._dlg_carregando.definir_mensagem(msg)

    def _esconder_carregando(self):
        if self._dlg_carregando is not None:
            self._dlg_carregando.close()
            self._dlg_carregando = None

    def _iniciar(self, fn, ao_terminar, ao_falhar):
        # A Tarefa precisa continuar referenciada enquanto roda: se o coletor a
        # levar, o _Sinais morre junto e a thread quebra ao emitir progresso.
        tarefa = Tarefa(fn)
        self._tarefas.add(tarefa)
        soltar = lambda *_: self._tarefas.discard(tarefa)  # noqa: E731
        tarefa.sinais.terminou.connect(ao_terminar)
        tarefa.sinais.falhou.connect(ao_falhar)
        tarefa.sinais.terminou.connect(soltar)
        tarefa.sinais.falhou.connect(soltar)
        QThreadPool.globalInstance().start(tarefa)
        return tarefa

    def showEvent(self, evento):
        super().showEvent(evento)
        # Só depois do primeiro layout real a página tem tamanho definitivo
        self._ajustar_altura_aba(self._abas.currentIndex())

    def closeEvent(self, evento):
        # Fechar com tarefa em voo destruiria os sinais que ela ainda usa
        pool = QThreadPool.globalInstance()
        if pool.activeThreadCount():
            pool.waitForDone(5000)
        super().closeEvent(evento)

    def _carregar(self, caminho: str, ws_idx: int = 0, trocando_planilha: bool = False):
        self._caminho = caminho
        self._df = None
        self._log_limpar()
        self._lbl_preview.setText("Carregando...")
        self._mostrar_carregando(
            "Carregando planilha..." if trocando_planilha else "Carregando arquivo...")

        def _trabalho(sinais):
            return carregar_planilha(caminho, ws_idx,
                                     progress_cb=sinais.progresso.emit)

        tarefa = self._iniciar(
            _trabalho,
            lambda r: self._ao_carregar_ok(caminho, r, trocando_planilha),
            self._ao_carregar_erro,
        )
        tarefa.sinais.progresso.connect(self._progresso_carregando)

    def _progresso_carregando(self, pct: int):
        if self._dlg_carregando is not None:
            self._dlg_carregando.definir_progresso(pct)

    def _ao_carregar_erro(self, msg: str):
        self._esconder_carregando()
        self._lbl_preview.setText("Erro ao carregar.")
        self._log_append(f"Erro: {msg}", "erro")
        QMessageBox.critical(self, "Arquivo inválido", msg)

    def _ao_carregar_ok(self, caminho, resultado, trocando_planilha: bool):
        nomes, df = resultado
        self._esconder_carregando()
        self._ed_arquivo.setText(caminho)
        if not self._ed_saida.text().strip():
            self._ed_saida.setText(os.path.dirname(caminho))

        if not trocando_planilha:
            self._ws_names = nomes
            self._cmb_planilha.blockSignals(True)
            self._cmb_planilha.clear()
            self._cmb_planilha.addItems(nomes)
            self._cmb_planilha.blockSignals(False)
            self._form_arquivo.setRowVisible(self._linha_planilha,
                                             len(nomes) > 1)

        self._df = df
        self._apos_carregar(df)

    def _ao_trocar_planilha(self, idx: int):
        if idx < 0 or not self._caminho:
            return
        self._carregar(self._caminho, idx, trocando_planilha=True)

    # ── Após carregar ────────────────────────────────────────────────────────

    def _apos_carregar(self, df):
        total = len(df)
        col_cat = get_col(df, "CATEGORIA")
        col_sit = get_col(df, "SITUACAO_INSCRICAO")

        if col_cat and col_sit:
            mask = (
                df[col_cat].str.strip().str.upper().isin(
                    {c.upper() for c in CATEGORIAS_ATIVAS})
                & df[col_sit].str.strip().str.upper().isin(
                    {s.upper() for s in SITUACOES_ATIVAS})
            )
            self._lbl_preview.setText(
                f"{total} registros carregados   ·   Ativos: {int(mask.sum())}   ·   "
                f"{len(df.columns)} colunas")
        else:
            self._lbl_preview.setText(
                f"{total} registros carregados   ·   {len(df.columns)} colunas")

        self._log_append(f"{total} registros carregados", "ok")

        self._cats_disponiveis = (
            sorted(df[col_cat].str.strip().str.upper().dropna().unique().tolist())
            if col_cat else [])
        self._sits_disponiveis = (
            sorted(df[col_sit].str.strip().str.upper().dropna().unique().tolist())
            if col_sit else [])

        self._btn_filtros.setEnabled(bool(col_cat or col_sit))
        self._chk_estagiarios.setEnabled(bool(col_cat))
        self._chk_estagiarios_pers.setEnabled(
            bool(col_cat) and self._rb_pers_ativos.isChecked())
        self._ao_alternar_estagiarios()

        self._cols_disponiveis = list(df.columns)
        self._colunas_personalizado = []
        self._filtros_coluna_personalizado = {}
        self._lbl_colunas.setText("Nenhuma coluna selecionada")

        for w in (self._btn_colunas, self._rb_pers_ativos, self._rb_pers_todos,
                  self._btn_sep_subsecoes, self._btn_sep_colunas,
                  self._chk_sep_adim, self._rb_sep_ativos, self._rb_sep_todos,
                  self._btn_csv_mapa, self._rb_csv_ativos, self._rb_csv_todos,
                  self._btn_csv_jovem):
            w.setEnabled(True)

        self._sep_subsecoes = []
        self._sep_colunas = []
        self._filtros_coluna_sep = {}
        self._sep_adim_col = self._detectar_col_adimplencia(df) or ""
        if self._sep_adim_col:
            self._sep_val_adimplente, self._sep_val_inadimplente = (
                self._classificar_adimplencia(
                    self._valores_da_coluna(self._sep_adim_col)))
        else:
            self._sep_val_adimplente, self._sep_val_inadimplente = [], []

        self._uf_col = self._detectar_col_subsecao(df)
        if self._uf_col:
            self._valores_uf = self._valores_da_coluna(self._uf_col)
            self._log_append(
                f"Subseção → coluna '{self._uf_col}'  "
                f"(ex: {', '.join(self._valores_uf[:5])}...)", "info")
        else:
            self._valores_uf = []
            self._log_append("Coluna de subseção não detectada no arquivo.", "normal")

        self._comarca_col = self._detectar_col_comarca(df)
        if self._comarca_col:
            self._valores_comarca = self._valores_da_coluna(self._comarca_col)
            self._log_append(
                f"Município → coluna '{self._comarca_col}'  "
                f"(ex: {', '.join(self._valores_comarca[:5])}...)", "info")
        else:
            self._valores_comarca = []

        self._atualizar_lbls_sep()
        self._atualizar_lbls_csv()

        self._date_cols = [c for c in df.columns if is_date_col(c)]
        self._cmb_data.clear()
        self._cmb_data.addItems(self._date_cols)
        self._chk_data.setEnabled(bool(self._date_cols))
        if not self._date_cols:
            self._chk_data.setChecked(False)
        self._alternar_filtro_data()

        self._atualizar_botoes()

    # ── Detecção de colunas ──────────────────────────────────────────────────

    @staticmethod
    def _detectar_col_subsecao(df):
        def pular(col: str) -> bool:
            u = col.strip().upper()
            partes = {"BAIRRO", "LOGR", "CEP", "COMP", "EXIBE", "DT_", "DATA_",
                      "FONE", "EMAIL", "CPF", "RG", "NASC", "SEXO", "NUM_",
                      "SITUAC", "CATEG", "INSCR", "TITULO"}
            if any(p in u for p in partes):
                return True
            if u.endswith(("_RES", "_COM", "_END", "_OAB")):
                return True
            if u.startswith(("MUN_", "END_", "UF_", "NOME_")):
                return True
            return False

        exatos = {"SUBSECAO", "SUBSEÇÃO", "SUB_SECAO", "SECCIONAL",
                  "NM_SECCIONAL", "DESCRICAO_SECCIONAL", "NOME_SUBSECAO",
                  "SUBSEÇÃO_INSCRICAO", "SUBSECAO_INSCRICAO"}
        for col in df.columns:
            if col.strip().upper() in exatos:
                return col

        for col in df.columns:
            if pular(col):
                continue
            u = col.strip().upper()
            if "SUBSEC" in u or "SECCIONAL" in u:
                return col

        melhor, melhor_score = None, -1
        for col in df.columns:
            if pular(col):
                continue
            vals = [str(v).strip() for v in df[col].dropna().unique() if str(v).strip()]
            n = len(vals)
            if n < 5 or n > 45:
                continue
            media = sum(len(v) for v in vals[:30]) / min(len(vals), 30)
            if media <= 3:
                continue
            score = media * 2 + (50 - n)
            if score > melhor_score:
                melhor_score, melhor = score, col
        return melhor

    @staticmethod
    def _detectar_col_comarca(df):
        prioridade = ["MUN_RES", "MUNICIPIO_RES", "MUNICIPIO", "MUNICÍPIO",
                      "CIDADE", "MUN_COMARCA", "MUNICIPIO_COMARCA"]
        cols = {c.strip().upper(): c for c in df.columns}
        for nome in prioridade:
            if nome in cols:
                return cols[nome]
        for col in df.columns:
            u = col.strip().upper()
            if u.startswith("MUN_") or "MUNIC" in u:
                return col
        return None

    @staticmethod
    def _detectar_col_adimplencia(df) -> str | None:
        prioridade = ["SIT_FIN_ATUAL", "SITUACAO_FIN_ATUAL", "SIT_FIN",
                      "ADIMPLENCIA", "ADIMPLÊNCIA", "SITUACAO_FINANCEIRA",
                      "SITUACAO_FINANCEIRA_INSCRICAO", "SIT_FINANCEIRA",
                      "ANUIDADE", "STATUS_FINANCEIRO"]
        cols = {c.strip().upper(): c for c in df.columns}
        for nome in prioridade:
            if nome in cols:
                return cols[nome]
        # "FIN" sozinho casaria com DEFINITIVO (TIPO_INSCRICAO)
        termos = ("ADIMPL", "FINANC", "ANUIDADE", "SIT_FIN", "FIN_ATUAL",
                  "SITUACAO_FIN")
        for col in df.columns:
            u = col.strip().upper()
            if any(t in u for t in termos):
                return col
        return None

    @staticmethod
    def _classificar_adimplencia(valores: list[str]) -> tuple[list[str], list[str]]:
        adimp, inad = [], []
        for v in valores:
            u = v.strip().upper()
            if any(t in u for t in ("INADIMPL", "ATRASO", "DEVEDOR", "DEBITO",
                                    "DÉBITO", "PENDENTE", "VENCID")):
                inad.append(v)
            elif any(t in u for t in ("ADIMPL", "REGULAR", "QUITE", "EM DIA",
                                      "QUITADO", "PAGO")):
                adimp.append(v)
        return adimp, inad

    def _valores_da_coluna(self, col_nome: str) -> list[str]:
        if self._df is None or not col_nome:
            return []
        col = get_col(self._df, col_nome) or col_nome
        if col not in self._df.columns:
            return []
        return sorted(
            str(v).strip() for v in self._df[col].dropna().unique() if str(v).strip())

    # ── Estagiários ──────────────────────────────────────────────────────────

    def _cats_estagiarios(self) -> set[str]:
        return {
            c for c in self._cats_disponiveis
            if unicodedata.normalize("NFKD", str(c))
            .encode("ascii", "ignore").decode().strip().upper().startswith("ESTAGI")
        }

    def _cats_efetivas(self) -> set[str] | None:
        base = set(self._cats_selecionadas) if self._filtros_customizados else None
        if not self._chk_estagiarios.isChecked():
            return base
        extras = self._cats_estagiarios()
        if not extras:
            return base
        return (set(CATEGORIAS_ATIVAS) if base is None else base) | extras

    def _ao_alternar_estagiarios(self, *_):
        # As duas caixas refletem o mesmo recorte de "ativos"
        marcado = self._chk_estagiarios.isChecked()
        if self._chk_estagiarios_pers.isChecked() != marcado:
            self._chk_estagiarios_pers.blockSignals(True)
            self._chk_estagiarios_pers.setChecked(marcado)
            self._chk_estagiarios_pers.blockSignals(False)

        if not marcado:
            texto = ""
        elif extras := self._cats_estagiarios():
            texto = "Somando: " + ", ".join(sorted(extras))
        else:
            texto = ("Nenhuma categoria de estagiário encontrada na coluna CATEGORIA "
                     "deste arquivo — nada será somado.")
        self._lbl_estagiarios.setText(texto)
        self._lbl_estagiarios_pers.setText(
            texto if self._rb_pers_ativos.isChecked() else "")

    def _ao_alternar_estagiarios_pers(self, marcado: bool):
        if self._chk_estagiarios.isChecked() != marcado:
            self._chk_estagiarios.setChecked(marcado)
        else:
            self._ao_alternar_estagiarios()

    def _ao_trocar_base_personalizado(self, *_):
        ativos = self._rb_pers_ativos.isChecked()
        self._chk_estagiarios_pers.setEnabled(
            ativos and self._df is not None and bool(self._cats_disponiveis))
        self._ao_alternar_estagiarios()

    # ── Diálogos ─────────────────────────────────────────────────────────────

    def _abrir_filtros_ativos(self):
        if not self._cats_disponiveis and not self._sits_disponiveis:
            return
        sits_marcadas = (self._sits_selecionadas if self._filtros_customizados
                         else {s for s in self._sits_disponiveis
                               if s in SITUACOES_ATIVAS})
        dlg = DialogoFiltrosAtivos(
            self, self._cats_disponiveis, self._sits_disponiveis,
            self._cats_selecionadas, sits_marcadas)
        if dlg.exec() == QDialog.Accepted:
            self._cats_selecionadas = dlg.categorias()
            self._sits_selecionadas = dlg.situacoes()
            self._filtros_customizados = True
            self._log_append(
                f"Filtros de ativos: {len(self._cats_selecionadas)} categoria(s), "
                f"{len(self._sits_selecionadas)} situação(ões)", "info")

    def _abrir_seletor_colunas(self):
        dlg = DialogoColunas(
            self, "Selecionar colunas — Relatório personalizado",
            self._cols_disponiveis, self._colunas_personalizado,
            self._filtros_coluna_personalizado, self._valores_da_coluna)
        if dlg.exec() != QDialog.Accepted:
            return
        self._colunas_personalizado = dlg.selecionadas()
        self._filtros_coluna_personalizado = {
            c: v for c, v in self._filtros_coluna_personalizado.items()
            if c in self._colunas_personalizado
        }
        self._lbl_colunas.setText(self._descrever_colunas(
            self._colunas_personalizado, self._filtros_coluna_personalizado))
        self._atualizar_botoes()

    def _abrir_seletor_colunas_sep(self):
        dlg = DialogoColunas(
            self, "Selecionar colunas — Relatórios separados",
            self._cols_disponiveis, self._sep_colunas,
            self._filtros_coluna_sep, self._valores_da_coluna)
        if dlg.exec() != QDialog.Accepted:
            return
        self._sep_colunas = dlg.selecionadas()
        # Filtros valem mesmo sem a coluna estar na saída — só descarta os vazios
        self._filtros_coluna_sep = {c: v for c, v in self._filtros_coluna_sep.items() if v}
        self._atualizar_lbls_sep()

    def _abrir_seletor_subsecoes(self):
        if not self._uf_col or not self._valores_uf:
            QMessageBox.warning(
                self, "Relatórios separados",
                "Coluna de subseção não detectada no arquivo. Não é possível "
                "separar por subseção.")
            return
        dlg = DialogoListaMarcavel(
            self, "Selecionar subseções — Relatórios separados",
            f"Subseções disponíveis ({self._uf_col})",
            self._valores_uf, self._sep_subsecoes)
        if dlg.exec() == QDialog.Accepted:
            self._sep_subsecoes = dlg.selecionados()
            self._atualizar_lbls_sep()

    def _ao_alternar_separar_adim(self, ligado: bool):
        self._btn_sep_adim.setVisible(ligado)
        self._atualizar_lbls_sep()
        if ligado and self._df is not None and not self._sep_adim_col:
            self._abrir_config_adimplencia()

    def _abrir_config_adimplencia(self):
        if self._df is None:
            return
        dlg = DialogoAdimplencia(
            self, self._cols_disponiveis, self._sep_adim_col,
            self._valores_da_coluna, self._classificar_adimplencia,
            self._sep_val_adimplente, self._sep_val_inadimplente)
        if dlg.exec() == QDialog.Accepted:
            (self._sep_adim_col, self._sep_val_adimplente,
             self._sep_val_inadimplente) = dlg.resultado()
            self._atualizar_lbls_sep()
            self._atualizar_lbls_csv()

    def _abrir_mapeamento_csv(self):
        if self._df is None:
            return
        _, mapa = mapear_para_oabma(
            self._df,
            col_subsecao=self._uf_col,
            col_cidade=self._comarca_col,
            col_adimplencia=self._sep_adim_col or None,
            valores_adimplente=self._sep_val_adimplente,
            valores_inadimplente=self._sep_val_inadimplente,
            jovem_desde=self._jovem_desde,
            jovem_ate=self._jovem_ate,
        )
        DialogoMapeamentoCsv(self, mapa).exec()

    # ── Rótulos ──────────────────────────────────────────────────────────────

    @staticmethod
    def _descrever_colunas(selecionadas: list[str],
                           filtros: dict[str, list[str]]) -> str:
        if filtros:
            partes = [f"{c}={'/'.join(v)}" if len(v) <= 2 else f"{c}=({len(v)})"
                      for c, v in filtros.items()]
            sufixo = "  •  Filtros: " + ", ".join(partes)
        else:
            sufixo = ""
        n = len(selecionadas)
        if n == 0:
            return "Nenhuma coluna selecionada"
        if n <= 4:
            return f"{n} colunas: {', '.join(selecionadas)}{sufixo}"
        return f"{n} colunas selecionadas ({', '.join(selecionadas[:3])}...){sufixo}"

    @staticmethod
    def _fmt_lista(vals: list[str], vazio: str) -> str:
        n = len(vals)
        if n == 0:
            return vazio
        if n <= 4:
            return ", ".join(vals)
        return f"{n} selecionados ({', '.join(vals[:3])}...)"

    def _atualizar_lbls_csv(self):
        if not self._sep_adim_col:
            self._lbl_csv_adim.setText(
                "Adimplência: nenhuma coluna reconhecida neste arquivo — o "
                "campo “adimplente” sairá em branco.")
        else:
            self._lbl_csv_adim.setText(
                f"Adimplência: {self._sep_adim_col}  •  adimplente = "
                f"{self._fmt_lista(self._sep_val_adimplente, '—')}  •  inadimplente = "
                f"{self._fmt_lista(self._sep_val_inadimplente, '—')}")

        origem = ("personalizado" if self._jovem_personalizado
                  else f"padrão, últimos {self._jovem_anos} anos")
        self._lbl_csv_jovem.setText(
            f"Jovem advogado ({origem}): compromisso de "
            f"{self._jovem_desde.strftime('%d/%m/%Y')} a "
            f"{self._jovem_ate.strftime('%d/%m/%Y')}")

    def _abrir_config_jovem(self):
        dlg = DialogoJovemAdvogado(
            self, self._jovem_anos, self._jovem_desde, self._jovem_ate,
            self._jovem_personalizado, periodo_jovem_padrao)
        if dlg.exec() == QDialog.Accepted:
            (self._jovem_personalizado, self._jovem_anos,
             self._jovem_desde, self._jovem_ate) = dlg.resultado()
            self._atualizar_lbls_csv()

    def _atualizar_lbls_sep(self):
        total = len(self._valores_uf)
        n_sub = len(self._sep_subsecoes)
        if n_sub == 0:
            self._lbl_sep_sub.setText(
                f"Nenhuma subseção selecionada — serão geradas todas ({total})"
                if total else "Nenhuma subseção selecionada")
        else:
            self._lbl_sep_sub.setText(
                f"{n_sub} de {total} subseções: "
                f"{self._fmt_lista(self._sep_subsecoes, '')}")

        n_col = len(self._sep_colunas)
        texto = ("Todas as colunas" if n_col == 0
                 else f"{n_col} colunas: {self._fmt_lista(self._sep_colunas, '')}")
        if self._filtros_coluna_sep:
            partes = [f"{c}={'/'.join(v)}" if len(v) <= 2 else f"{c}=({len(v)})"
                      for c, v in self._filtros_coluna_sep.items()]
            texto += "  •  Filtros: " + ", ".join(partes)
        self._lbl_sep_col.setText(texto)

        if not self._chk_sep_adim.isChecked():
            self._lbl_sep_adim.setText(
                "Sem separação por adimplência — 1 arquivo por subseção, tudo junto")
        elif not self._sep_adim_col:
            self._lbl_sep_adim.setText(
                "Adimplência: coluna não definida — clique “Adimplência...”")
        else:
            self._lbl_sep_adim.setText(
                f"Adimplência: {self._sep_adim_col}  •  adimplente = "
                f"{self._fmt_lista(self._sep_val_adimplente, '—')}  •  inadimplente = "
                f"{self._fmt_lista(self._sep_val_inadimplente, '—')}")

    def _alternar_filtro_data(self, *_):
        ativo = self._chk_data.isChecked() and bool(self._date_cols)
        self._cmb_data.setEnabled(ativo)
        self._data_de.setEnabled(ativo)
        self._data_ate.setEnabled(ativo)
        if not ativo:
            self._data_de.setDate(_DATA_SENTINELA)
            self._data_ate.setDate(_DATA_SENTINELA)

    def _atualizar_botoes(self, *_):
        """Cada aba tem sua própria ação; libera só as que dá para executar."""
        tem = self._df is not None
        self._btn_prontos.setEnabled(
            tem and (self._chk_geral.isChecked() or self._chk_ativos.isChecked()))
        self._btn_pers.setEnabled(tem and bool(self._colunas_personalizado))
        self._btn_csv.setEnabled(tem)
        self._btn_separados.setEnabled(tem and bool(self._uf_col))

        if not tem:
            self._lbl_status.setText("Selecione um arquivo para começar.")
        else:
            self._lbl_status.setText(
                "Pronto — cada aba gera o seu próprio arquivo.")

    # ── Datas ────────────────────────────────────────────────────────────────

    def _intervalo_datas(self):
        if not (self._chk_data.isChecked() and self._date_cols):
            return None, None, None
        de = self._data_de.date()
        ate = self._data_ate.date()
        inicio = None if de == _DATA_SENTINELA else datetime(
            de.year(), de.month(), de.day())
        fim = None if ate == _DATA_SENTINELA else datetime(
            ate.year(), ate.month(), ate.day())
        return self._cmb_data.currentText(), inicio, fim

    # ── Geração ──────────────────────────────────────────────────────────────

    def _base_parametros(self) -> dict | None:
        """Parâmetros comuns a todas as ações. None (com log) se faltar algo."""
        if self._df is None:
            self._log_append("Selecione um arquivo válido antes de gerar.", "erro")
            return None
        pasta = self._ed_saida.text().strip()
        if not pasta:
            self._log_append("Informe a pasta de saída.", "erro")
            return None
        data_col, data_inicio, data_fim = self._intervalo_datas()
        return {
            "df": self._df.copy(),
            "pasta": pasta,
            "data_col": data_col,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "nome_base": (self._ed_nome.text().strip()
                          or "RELATORIO CADASTRO ADVOGADOS GERAL"),
            "cats": self._cats_efetivas(),
            "sits": (set(self._sits_selecionadas)
                     if self._filtros_customizados else None),
        }

    def _acoes(self) -> tuple:
        return (self._btn_prontos, self._btn_pers, self._btn_csv,
                self._btn_separados)

    def _ocupado(self, ocupado: bool, botao=None, rotulo: str = ""):
        for b in self._acoes():
            b.setEnabled(not ocupado)
        if ocupado:
            self._lbl_status.setText("Gerando...")
            if botao is not None:
                self._rotulo_original = (botao, botao.text())
                botao.setText("Processando...")
        else:
            anterior = getattr(self, "_rotulo_original", None)
            if anterior:
                anterior[0].setText(anterior[1])
                self._rotulo_original = None
            self._atualizar_botoes()

    def _executar(self, botao, trabalho):
        """Roda a geração em outra thread, cuidando de estado e progresso."""
        self._ocupado(True, botao)
        self._barra.setValue(0)
        self._log_limpar()
        tarefa = self._iniciar(trabalho, self._ao_concluir, self._ao_falhar)
        tarefa.sinais.progresso.connect(self._barra.setValue)
        tarefa.sinais.log.connect(self._log_append)

    def _ao_concluir(self, pasta):
        self._barra.setValue(100)
        self._log_append(f"Concluído! Arquivos salvos em: {pasta}", "ok")
        self._ocupado(False)
        self._lbl_status.setText(f"Concluído — arquivos em {pasta}")
        self._abrir_pasta(pasta)

    def _ao_falhar(self, msg: str):
        self._log_append(f"Erro: {msg}", "erro")
        self._ocupado(False)
        self._lbl_status.setText("Falhou — veja o log.")

    # ── Ação 1: relatórios prontos ───────────────────────────────────────────

    def _gerar_prontos(self):
        p = self._base_parametros()
        if p is None:
            return
        geral = self._chk_geral.isChecked()
        ativos = self._chk_ativos.isChecked()
        if not (geral or ativos):
            self._log_append("Marque “Geral” e/ou “Apenas ativos”.", "erro")
            return

        def _trabalho(sinais):
            gerar_relatorios(
                p["df"], p["pasta"],
                lambda m, t="normal": sinais.log.emit(m, t),
                gerar_geral=geral,
                gerar_ativos=ativos,
                categorias_filtro=p["cats"],
                situacoes_filtro=p["sits"],
                data_col=p["data_col"],
                data_inicio=p["data_inicio"],
                data_fim=p["data_fim"],
                nome_base=p["nome_base"],
                progress_cb=sinais.progresso.emit,
                gerar_personalizado=False,
            )
            return p["pasta"]

        self._executar(self._btn_prontos, _trabalho)

    # ── Ação 2: relatório personalizado ──────────────────────────────────────

    def _gerar_personalizado(self):
        p = self._base_parametros()
        if p is None:
            return
        if not self._colunas_personalizado:
            self._log_append(
                "Clique em “Selecionar colunas...” e escolha ao menos uma coluna.",
                "erro")
            return
        colunas = list(self._colunas_personalizado)
        filtros = {c: list(v) for c, v in self._filtros_coluna_personalizado.items()
                   if c in colunas and v} or None
        base = "ativos" if self._rb_pers_ativos.isChecked() else "geral"

        def _trabalho(sinais):
            gerar_relatorios(
                p["df"], p["pasta"],
                lambda m, t="normal": sinais.log.emit(m, t),
                gerar_geral=False,
                gerar_ativos=False,
                categorias_filtro=p["cats"],
                situacoes_filtro=p["sits"],
                data_col=p["data_col"],
                data_inicio=p["data_inicio"],
                data_fim=p["data_fim"],
                nome_base=p["nome_base"],
                progress_cb=sinais.progresso.emit,
                gerar_personalizado=True,
                colunas_personalizado=colunas,
                filtros_valores_personalizado=filtros,
                personalizado_base=base,
            )
            return p["pasta"]

        self._executar(self._btn_pers, _trabalho)

    # ── Ação 3: CSV de importação ────────────────────────────────────────────

    def _gerar_csv(self):
        p = self._base_parametros()
        if p is None:
            return
        base = "ativos" if self._rb_csv_ativos.isChecked() else "geral"
        col_sub, col_cid = self._uf_col, self._comarca_col
        col_adim = self._sep_adim_col or None
        adim = list(self._sep_val_adimplente)
        inad = list(self._sep_val_inadimplente)
        jovem_de, jovem_ate = self._jovem_desde, self._jovem_ate

        def _trabalho(sinais):
            exportar_csv_oabma(
                p["df"], p["pasta"],
                lambda m, t="normal": sinais.log.emit(m, t),
                base=base,
                categorias_filtro=p["cats"],
                situacoes_filtro=p["sits"],
                data_col=p["data_col"],
                data_inicio=p["data_inicio"],
                data_fim=p["data_fim"],
                nome_base=p["nome_base"],
                col_subsecao=col_sub,
                col_cidade=col_cid,
                col_adimplencia=col_adim,
                valores_adimplente=adim,
                valores_inadimplente=inad,
                jovem_desde=jovem_de,
                jovem_ate=jovem_ate,
                progress_cb=sinais.progresso.emit,
            )
            return p["pasta"]

        self._executar(self._btn_csv, _trabalho)

    # ── Ação 4: relatórios separados por subseção ────────────────────────────

    def _gerar_separados_click(self):
        if self._df is None:
            return
        if not self._uf_col or not self._valores_uf:
            QMessageBox.warning(
                self, "Relatórios separados",
                "Coluna de subseção não detectada no arquivo. Não é possível "
                "separar por subseção.")
            return
        if self._chk_sep_adim.isChecked():
            if not self._sep_adim_col:
                QMessageBox.warning(
                    self, "Relatórios separados",
                    "Clique em “Adimplência...” e escolha a coluna — ou desmarque "
                    "“Separar cada subseção em adimplentes × inadimplentes”.")
                return
            if not self._sep_val_adimplente:
                QMessageBox.warning(self, "Relatórios separados",
                                    "Defina os valores de ADIMPLENTE.")
                return
            if not self._sep_val_inadimplente:
                QMessageBox.warning(self, "Relatórios separados",
                                    "Defina os valores de INADIMPLENTE.")
                return

        pasta = self._ed_saida.text().strip()
        if not pasta:
            self._log_append("Informe a pasta de saída antes de gerar.", "erro")
            return

        subsecoes = self._sep_subsecoes or list(self._valores_uf)
        separar = self._chk_sep_adim.isChecked()
        data_col, data_inicio, data_fim = self._intervalo_datas()
        args = dict(
            subsecao_col=self._uf_col,
            subsecoes=subsecoes,
            adimplencia_col=self._sep_adim_col if separar else None,
            valores_adimplente=list(self._sep_val_adimplente) if separar else None,
            valores_inadimplente=list(self._sep_val_inadimplente) if separar else None,
            colunas=list(self._sep_colunas) or None,
            filtros_coluna={c: list(v) for c, v in self._filtros_coluna_sep.items()
                            if v} or None,
            base="ativos" if self._rb_sep_ativos.isChecked() else "geral",
            categorias_filtro=self._cats_efetivas(),
            situacoes_filtro=(set(self._sits_selecionadas)
                              if self._filtros_customizados else None),
            data_col=data_col,
            data_inicio=data_inicio,
            data_fim=data_fim,
            nome_base=(self._ed_nome.text().strip()
                       or "RELATORIO CADASTRO ADVOGADOS GERAL"),
        )
        df = self._df.copy()

        self._ocupado(True, self._btn_separados)
        self._barra.setValue(0)
        self._log_limpar()
        self._log_append(
            f"Gerando relatórios separados: {len(subsecoes)} subseção(ões) × 2 = "
            f"{len(subsecoes) * 2} arquivos" if separar else
            f"Gerando relatórios separados: {len(subsecoes)} arquivo(s), "
            f"1 por subseção", "info")

        def _trabalho(sinais):
            gerar_relatorios_separados(
                df, pasta, lambda m, t="normal": sinais.log.emit(m, t),
                progress_cb=sinais.progresso.emit, **args)
            return pasta

        tarefa = self._iniciar(_trabalho, self._ao_concluir, self._ao_falhar)
        tarefa.sinais.progresso.connect(self._barra.setValue)
        tarefa.sinais.log.connect(self._log_append)

    # ── Log ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _cor_log(tag: str) -> str:
        p = paleta()
        return {"ok": p["log_ok"], "erro": p["log_erro"],
                "info": p["log_info"]}.get(tag, p["log_texto"])

    def _log_limpar(self):
        self._linhas_log.clear()
        self._log.clear()

    def _log_append(self, texto: str, tag: str = "normal"):
        self._linhas_log.append((texto, tag))
        self._escrever_linha(texto, tag)

    def _escrever_linha(self, texto: str, tag: str):
        self._log.appendHtml(
            f'<span style="color:{self._cor_log(tag)}">{html.escape(texto)}</span>')
        barra = self._log.verticalScrollBar()
        barra.setValue(barra.maximum())



    @staticmethod
    def _abrir_pasta(pasta: str):
        try:
            if sys.platform == "win32":
                os.startfile(pasta)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", pasta])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", pasta])
        except Exception:
            pass
