"""Diálogos da aplicação.

As listas usam QListWidget com itens marcáveis: a rolagem é virtualizada, então
não há limite prático de valores (a versão anterior renderizava no máximo 500
por vez) e a busca apenas esconde itens, preservando o que já estava marcado.
"""

from datetime import date, datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.utils import is_date_col

_FMTS_DATA_EXIBICAO = (
    ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y"),
    ("%Y-%m-%dT%H:%M:%S.%f", "%d/%m/%Y"),
    ("%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"),
    ("%Y-%m-%d", "%d/%m/%Y"),
)


def _fmt_valor(valor: str, e_data: bool) -> str:
    if not e_data:
        return valor
    for fmt_in, fmt_out in _FMTS_DATA_EXIBICAO:
        try:
            return datetime.strptime(valor, fmt_in).strftime(fmt_out)
        except ValueError:
            continue
    return valor


def _centralizar(dlg: QDialog, pai: QWidget | None):
    if pai is None:
        return
    geo = dlg.frameGeometry()
    geo.moveCenter(pai.frameGeometry().center())
    dlg.move(geo.topLeft())


class DialogoCarregando(QDialog):
    """Sobreposição modal sem bordas, exibida enquanto o arquivo é lido."""

    def __init__(self, pai: QWidget | None, mensagem: str = "Carregando..."):
        super().__init__(pai)
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setFixedWidth(340)

        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)

        caixa = QWidget(objectName="CaixaCarregando")
        externo.addWidget(caixa)

        col = QVBoxLayout(caixa)
        col.setContentsMargins(24, 22, 24, 22)
        col.setSpacing(10)

        self._lbl = QLabel(mensagem, alignment=Qt.AlignCenter)
        self._lbl.setStyleSheet("font-size: 14px; font-weight: 600;")
        col.addWidget(self._lbl)

        self._barra = QProgressBar(maximum=100, value=0)
        col.addWidget(self._barra)

        self._pct = QLabel("0%", objectName="Dica", alignment=Qt.AlignCenter)
        col.addWidget(self._pct)

    def definir_mensagem(self, msg: str):
        self._lbl.setText(msg)

    def definir_progresso(self, pct: int):
        self._barra.setValue(max(0, min(100, int(pct))))
        self._pct.setText(f"{int(pct)}%")


class DialogoListaMarcavel(QDialog):
    """Múltipla escolha com busca. Usado para subseções e valores de adimplência."""

    def __init__(self, pai, titulo: str, rotulo: str,
                 valores: list[str], selecionados: list[str]):
        super().__init__(pai)
        self.setWindowTitle(titulo)
        self.resize(430, 520)
        self._valores = list(valores)
        ja = {v.upper() for v in selecionados}

        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(10)

        acoes = QHBoxLayout()
        b_todas = QPushButton("Marcar todas")
        b_todas.clicked.connect(lambda: self._marcar_visiveis(True))
        b_limpar = QPushButton("Limpar")
        b_limpar.clicked.connect(lambda: self._marcar_visiveis(False))
        acoes.addWidget(b_todas)
        acoes.addWidget(b_limpar)
        acoes.addStretch(1)
        col.addLayout(acoes)

        self._busca = QLineEdit(placeholderText="Buscar...", clearButtonEnabled=True)
        self._busca.textChanged.connect(self._filtrar)
        col.addWidget(self._busca)

        col.addWidget(QLabel(rotulo, objectName="Dica"))

        self._lista = QListWidget()
        self._lista.setSelectionMode(QAbstractItemView.NoSelection)
        for v in self._valores:
            item = QListWidgetItem(v)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if v.upper() in ja else Qt.Unchecked)
            self._lista.addItem(item)
        self._lista.itemChanged.connect(self._atualizar_contador)
        col.addWidget(self._lista, 1)

        self._contador = QLabel(objectName="Dica")
        col.addWidget(self._contador)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Ok).setText("OK")
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        col.addWidget(botoes)

        self._atualizar_contador()
        _centralizar(self, pai)

    def _itens(self):
        return (self._lista.item(i) for i in range(self._lista.count()))

    def _filtrar(self, texto: str):
        alvo = texto.strip().lower()
        for item in self._itens():
            item.setHidden(bool(alvo) and alvo not in item.text().lower())
        self._atualizar_contador()

    def _marcar_visiveis(self, marcar: bool):
        estado = Qt.Checked if marcar else Qt.Unchecked
        for item in self._itens():
            if not item.isHidden():
                item.setCheckState(estado)

    def _atualizar_contador(self, *_):
        n = sum(1 for i in self._itens() if i.checkState() == Qt.Checked)
        visiveis = sum(1 for i in self._itens() if not i.isHidden())
        sufixo = "" if visiveis == len(self._valores) else f"  •  {visiveis} na busca"
        self._contador.setText(f"{n} de {len(self._valores)} marcados{sufixo}")

    def selecionados(self) -> list[str]:
        return [i.text() for i in self._itens() if i.checkState() == Qt.Checked]


class DialogoFiltroValores(QDialog):
    """Filtro de valores de uma coluna, no estilo do AutoFiltro do Excel.

    Resultado em `acao`: "aplicar" (usa `selecionados()`) ou "remover"."""

    def __init__(self, pai, col_nome: str, valores: list[str],
                 atual: list[str] | None):
        super().__init__(pai)
        self.setWindowTitle(f"Filtrar — {col_nome}")
        self.resize(400, 540)
        self._valores = list(valores)
        self._e_data = is_date_col(col_nome)
        self.acao = "aplicar"

        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(10)

        self._chk_todos = QCheckBox("(Selecionar tudo)")
        self._chk_todos.clicked.connect(self._alternar_todos)
        col.addWidget(self._chk_todos)

        linha = QHBoxLayout()
        self._busca = QLineEdit(placeholderText="Pesquisar...", clearButtonEnabled=True)
        self._busca.textChanged.connect(self._filtrar)
        linha.addWidget(self._busca, 1)
        b_somente = QPushButton("Somente estes")
        b_somente.setToolTip("Marca apenas os valores que aparecem na busca")
        b_somente.clicked.connect(self._somente_estes)
        linha.addWidget(b_somente)
        col.addLayout(linha)

        self._lista = QListWidget()
        self._lista.setSelectionMode(QAbstractItemView.NoSelection)
        marcado_inicial = None if atual is None else {v for v in atual}
        for v in self._valores:
            item = QListWidgetItem(_fmt_valor(v, self._e_data))
            item.setData(Qt.UserRole, v)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            ligado = marcado_inicial is None or v in marcado_inicial
            item.setCheckState(Qt.Checked if ligado else Qt.Unchecked)
            self._lista.addItem(item)
        self._lista.itemChanged.connect(self._atualizar_contador)
        col.addWidget(self._lista, 1)

        self._contador = QLabel(objectName="Dica")
        col.addWidget(self._contador)

        botoes = QHBoxLayout()
        b_remover = QPushButton("Remover filtro")
        b_remover.setToolTip("Volta a considerar todos os valores desta coluna")
        b_remover.clicked.connect(self._remover)
        botoes.addWidget(b_remover)
        botoes.addStretch(1)
        b_cancelar = QPushButton("Cancelar")
        b_cancelar.clicked.connect(self.reject)
        botoes.addWidget(b_cancelar)
        b_ok = QPushButton("OK", objectName="Sucesso")
        b_ok.setDefault(True)
        b_ok.clicked.connect(self._confirmar)
        botoes.addWidget(b_ok)
        col.addLayout(botoes)

        self._atualizar_contador()
        _centralizar(self, pai)

    def _itens(self):
        return (self._lista.item(i) for i in range(self._lista.count()))

    def _filtrar(self, texto: str):
        alvo = texto.strip().lower()
        for item in self._itens():
            item.setHidden(bool(alvo) and alvo not in item.text().lower())
        self._atualizar_contador()

    def _alternar_todos(self, marcado: bool):
        estado = Qt.Checked if marcado else Qt.Unchecked
        for item in self._itens():
            item.setCheckState(estado)

    def _somente_estes(self):
        for item in self._itens():
            item.setCheckState(Qt.Unchecked if item.isHidden() else Qt.Checked)

    def _atualizar_contador(self, *_):
        marcados = sum(1 for i in self._itens() if i.checkState() == Qt.Checked)
        total = len(self._valores)
        self._chk_todos.blockSignals(True)
        self._chk_todos.setChecked(bool(total) and marcados == total)
        self._chk_todos.blockSignals(False)
        visiveis = sum(1 for i in self._itens() if not i.isHidden())
        sufixo = "" if visiveis == total else f"  •  {visiveis} na busca"
        self._contador.setText(f"{marcados}/{total} selecionados{sufixo}")

    def _remover(self):
        self.acao = "remover"
        self.accept()

    def _confirmar(self):
        if not self.selecionados():
            QMessageBox.warning(
                self, "Filtro",
                "Selecione ao menos um valor — ou use “Remover filtro”.",
            )
            return
        self.acao = "aplicar"
        self.accept()

    def selecionados(self) -> list[str]:
        return [i.data(Qt.UserRole) for i in self._itens()
                if i.checkState() == Qt.Checked]

    def marcou_todos(self) -> bool:
        return len(self.selecionados()) == len(self._valores)


class DialogoColunas(QDialog):
    """Escolha de colunas com filtro de valores por coluna.

    Escreve os filtros direto em `filtros` (mesmo contrato da versão anterior)."""

    def __init__(self, pai, titulo: str, colunas: list[str],
                 selecionadas: list[str], filtros: dict[str, list[str]],
                 valores_da_coluna):
        super().__init__(pai)
        self.setWindowTitle(titulo)
        self.resize(560, 580)
        self._colunas = list(colunas)
        self._filtros = filtros
        self._valores_da_coluna = valores_da_coluna
        ja = set(selecionadas)

        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(10)

        acoes = QHBoxLayout()
        b_todas = QPushButton("Marcar todas")
        b_todas.clicked.connect(lambda: self._marcar_visiveis(True))
        b_limpar = QPushButton("Limpar")
        b_limpar.clicked.connect(lambda: self._marcar_visiveis(False))
        acoes.addWidget(b_todas)
        acoes.addWidget(b_limpar)
        acoes.addStretch(1)
        self._b_filtrar = QPushButton("▼ Filtrar valores...")
        self._b_filtrar.setToolTip(
            "Restringe os valores da coluna destacada (duplo clique também abre)")
        self._b_filtrar.clicked.connect(self._filtrar_atual)
        acoes.addWidget(self._b_filtrar)
        col.addLayout(acoes)

        self._busca = QLineEdit(placeholderText="Buscar coluna...",
                                clearButtonEnabled=True)
        self._busca.textChanged.connect(self._filtrar_lista)
        col.addWidget(self._busca)

        self._arvore = QTreeWidget()
        self._arvore.setHeaderLabels(["Coluna", "Filtro de valores"])
        self._arvore.setRootIsDecorated(False)
        self._arvore.setAlternatingRowColors(False)
        cab = self._arvore.header()
        cab.setStretchLastSection(False)
        cab.setSectionResizeMode(0, cab.ResizeMode.Stretch)
        # Sem isto a coluna do filtro é espremida e o texto sai cortado
        cab.setSectionResizeMode(1, cab.ResizeMode.ResizeToContents)
        self._arvore.itemDoubleClicked.connect(lambda *_: self._filtrar_atual())
        for c in self._colunas:
            item = QTreeWidgetItem([c, ""])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked if c in ja else Qt.Unchecked)
            self._arvore.addTopLevelItem(item)
            self._atualizar_rotulo_filtro(item)
        col.addWidget(self._arvore, 1)

        dica = QLabel(
            "Marque as colunas que devem sair no relatório. Para restringir os "
            "valores de uma coluna, destaque-a e clique em “Filtrar valores...”.",
            objectName="Dica", wordWrap=True,
        )
        col.addWidget(dica)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Ok).setText("OK")
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        col.addWidget(botoes)

        _centralizar(self, pai)

    def _itens(self):
        return (self._arvore.topLevelItem(i)
                for i in range(self._arvore.topLevelItemCount()))

    def _filtrar_lista(self, texto: str):
        alvo = texto.strip().lower()
        for item in self._itens():
            item.setHidden(bool(alvo) and alvo not in item.text(0).lower())

    def _marcar_visiveis(self, marcar: bool):
        estado = Qt.Checked if marcar else Qt.Unchecked
        for item in self._itens():
            if not item.isHidden():
                item.setCheckState(0, estado)

    def _atualizar_rotulo_filtro(self, item: QTreeWidgetItem):
        vals = self._filtros.get(item.text(0))
        if not vals:
            item.setText(1, "todos os valores")
            item.setForeground(1, Qt.gray)
        elif len(vals) <= 2:
            item.setText(1, "● " + ", ".join(vals))
        else:
            item.setText(1, f"● {len(vals)} valores")

    def _filtrar_atual(self):
        item = self._arvore.currentItem()
        if item is None:
            QMessageBox.information(
                self, "Filtrar valores",
                "Destaque uma coluna na lista para filtrar os valores dela.")
            return
        col_nome = item.text(0)
        valores = self._valores_da_coluna(col_nome)
        if not valores:
            QMessageBox.information(
                self, "Filtrar valores",
                f"A coluna “{col_nome}” não possui valores para filtrar.")
            return

        dlg = DialogoFiltroValores(self, col_nome, valores,
                                   self._filtros.get(col_nome))
        if dlg.exec() != QDialog.Accepted:
            return
        if dlg.acao == "remover" or dlg.marcou_todos():
            self._filtros.pop(col_nome, None)
        else:
            self._filtros[col_nome] = dlg.selecionados()
        self._atualizar_rotulo_filtro(item)

    def selecionadas(self) -> list[str]:
        return [i.text(0) for i in self._itens() if i.checkState(0) == Qt.Checked]


class DialogoFiltrosAtivos(QDialog):
    """Categorias e situações que compõem o recorte de 'ativos'."""

    def __init__(self, pai, categorias: list[str], situacoes: list[str],
                 cats_marcadas: set[str], sits_marcadas: set[str]):
        super().__init__(pai)
        self.setWindowTitle("Filtros — Geral Ativos")
        self.resize(430, 560)

        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(10)

        col.addWidget(QLabel(
            "Só entram no recorte de “ativos” os registros cuja categoria E "
            "situação estejam marcadas abaixo.",
            objectName="Dica", wordWrap=True))

        area = QScrollArea(widgetResizable=True)
        interno = QWidget()
        vint = QVBoxLayout(interno)
        vint.setContentsMargins(0, 0, 8, 0)

        self._cats = self._bloco(vint, "Categorias a incluir", categorias, cats_marcadas)
        self._sits = self._bloco(vint, "Situações a incluir", situacoes, sits_marcadas)
        vint.addStretch(1)
        area.setWidget(interno)
        col.addWidget(area, 1)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Ok).setText("OK")
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        col.addWidget(botoes)

        _centralizar(self, pai)

    @staticmethod
    def _bloco(layout, titulo, valores, marcados) -> dict[str, QCheckBox]:
        caixas: dict[str, QCheckBox] = {}
        if not valores:
            return caixas
        grupo = QGroupBox(titulo)
        vg = QVBoxLayout(grupo)
        vg.setSpacing(4)
        for v in valores:
            chk = QCheckBox(v)
            chk.setChecked(v in marcados)
            vg.addWidget(chk)
            caixas[v] = chk
        layout.addWidget(grupo)
        return caixas

    def categorias(self) -> set[str]:
        return {c for c, chk in self._cats.items() if chk.isChecked()}

    def situacoes(self) -> set[str]:
        return {s for s, chk in self._sits.items() if chk.isChecked()}


class DialogoAdimplencia(QDialog):
    """Coluna de adimplência e quais valores dela contam como adimplente."""

    def __init__(self, pai, colunas: list[str], col_atual: str,
                 valores_da_coluna, classificar,
                 adimplentes: list[str], inadimplentes: list[str]):
        super().__init__(pai)
        self.setWindowTitle("Adimplência — Relatórios Separados")
        self.resize(520, 300)
        self._valores_da_coluna = valores_da_coluna
        self._classificar = classificar
        self._adimplentes = list(adimplentes)
        self._inadimplentes = list(inadimplentes)

        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(10)

        col.addWidget(QLabel(
            "Defina qual coluna indica adimplência e quais valores dela contam "
            "como adimplente ou inadimplente.",
            objectName="Dica", wordWrap=True))

        linha = QHBoxLayout()
        linha.addWidget(QLabel("Coluna:"))
        self._combo = QComboBox()
        self._combo.addItems(colunas)
        if col_atual in colunas:
            self._combo.setCurrentText(col_atual)
        self._combo.currentTextChanged.connect(self._ao_trocar_coluna)
        linha.addWidget(self._combo, 1)
        col.addLayout(linha)

        self._lbl_adim = QLabel(objectName="Dica", wordWrap=True)
        self._lbl_inad = QLabel(objectName="Dica", wordWrap=True)

        for texto, slot, lbl in (
            ("Adimplente =", self._sel_adimplente, self._lbl_adim),
            ("Inadimplente =", self._sel_inadimplente, self._lbl_inad),
        ):
            l = QHBoxLayout()
            b = QPushButton(texto)
            b.setFixedWidth(130)
            b.clicked.connect(slot)
            l.addWidget(b)
            l.addWidget(lbl, 1)
            col.addLayout(l)

        col.addWidget(QLabel(
            "Ao escolher a coluna, o app já separa os valores automaticamente — "
            "confira e ajuste se preciso.",
            objectName="Dica", wordWrap=True))
        col.addStretch(1)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Ok).setText("OK")
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        col.addWidget(botoes)

        self._atualizar_rotulos()
        _centralizar(self, pai)

    @staticmethod
    def _fmt(vals: list[str]) -> str:
        if not vals:
            return "Nenhum selecionado"
        if len(vals) <= 4:
            return ", ".join(vals)
        return f"{len(vals)} selecionados ({', '.join(vals[:3])}...)"

    def _atualizar_rotulos(self):
        self._lbl_adim.setText(self._fmt(self._adimplentes))
        self._lbl_inad.setText(self._fmt(self._inadimplentes))

    def _ao_trocar_coluna(self, col: str):
        adimp, inad = self._classificar(self._valores_da_coluna(col))
        self._adimplentes, self._inadimplentes = adimp, inad
        self._atualizar_rotulos()

    def _escolher(self, titulo: str, rotulo: str, atual: list[str]) -> list[str] | None:
        vals = self._valores_da_coluna(self._combo.currentText())
        if not vals:
            QMessageBox.information(self, titulo, "Não há valores para selecionar.")
            return None
        dlg = DialogoListaMarcavel(self, titulo, rotulo, vals, atual)
        return dlg.selecionados() if dlg.exec() == QDialog.Accepted else None

    def _sel_adimplente(self):
        r = self._escolher("Valores = Adimplente",
                           "Marque os valores que significam ADIMPLENTE",
                           self._adimplentes)
        if r is not None:
            self._adimplentes = r
            self._atualizar_rotulos()

    def _sel_inadimplente(self):
        r = self._escolher("Valores = Inadimplente",
                           "Marque os valores que significam INADIMPLENTE",
                           self._inadimplentes)
        if r is not None:
            self._inadimplentes = r
            self._atualizar_rotulos()

    def resultado(self) -> tuple[str, list[str], list[str]]:
        return self._combo.currentText(), self._adimplentes, self._inadimplentes


class DialogoMapeamentoCsv(QDialog):
    """Mostra qual coluna do arquivo alimenta cada campo do CSV.

    Serve aos dois layouts (OAB PREV e Jusbrasil); o nome vem no título.
    """

    def __init__(self, pai, mapeamento: list[tuple[str, str | None]],
                 layout: str = "OAB PREV"):
        super().__init__(pai)
        self.setWindowTitle(f"Mapeamento — CSV de importação {layout}")
        self.resize(500, 600)

        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(10)

        col.addWidget(QLabel(
            "Cada campo do CSV e a coluna do arquivo que vai preenchê-lo.",
            objectName="Dica", wordWrap=True))

        arvore = QTreeWidget()
        arvore.setHeaderLabels(["Campo do CSV", "Coluna de origem"])
        arvore.setRootIsDecorated(False)
        arvore.header().setSectionResizeMode(0, arvore.header().ResizeMode.ResizeToContents)
        arvore.header().setStretchLastSection(True)
        for campo, origem in mapeamento:
            item = QTreeWidgetItem([campo, origem or "sem origem — sairá em branco"])
            if not origem:
                item.setForeground(1, Qt.red)
            arvore.addTopLevelItem(item)
        col.addWidget(arvore, 1)

        faltando = [c for c, o in mapeamento if not o]
        if faltando:
            col.addWidget(QLabel(
                f"{len(faltando)} campo(s) sem origem no arquivo. Preencha no CSV "
                f"antes de importar, se o sistema exigir.",
                objectName="Aviso", wordWrap=True))

        botoes = QDialogButtonBox(QDialogButtonBox.Close)
        botoes.button(QDialogButtonBox.Close).setText("Fechar")
        botoes.rejected.connect(self.reject)
        botoes.accepted.connect(self.accept)
        col.addWidget(botoes)

        _centralizar(self, pai)


class DialogoJovemAdvogado(QDialog):
    """Período de compromisso que define quem é jovem advogado.

    Padrão: últimos N anos contados do ano corrente. Personalizado: intervalo
    de datas escolhido à mão."""

    def __init__(self, pai, anos: int, desde, ate, personalizado: bool,
                 padrao_para_anos):
        super().__init__(pai)
        self.setWindowTitle("Jovem advogado — CSV de importação")
        self.resize(520, 300)
        self._padrao_para_anos = padrao_para_anos

        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(10)

        col.addWidget(QLabel(
            "O campo “jovenAdvogado” do CSV é calculado pela data de "
            "compromisso: fica “sim” quando o compromisso cai no período "
            "abaixo, e “nao” fora dele.",
            objectName="Dica", wordWrap=True))

        self._rb_padrao = QRadioButton("Padrão — últimos")
        self._rb_padrao.toggled.connect(self._alternar)
        lin = QHBoxLayout()
        lin.addWidget(self._rb_padrao)
        self._spin = QSpinBox(minimum=1, maximum=50, value=anos, suffix=" anos")
        self._spin.valueChanged.connect(self._atualizar_previa)
        lin.addWidget(self._spin)
        lin.addStretch(1)
        col.addLayout(lin)

        self._previa = QLabel(objectName="Dica")
        col.addWidget(self._previa)

        self._rb_custom = QRadioButton("Período personalizado")
        col.addWidget(self._rb_custom)

        lin2 = QHBoxLayout()
        lin2.addSpacing(24)
        lin2.addWidget(QLabel("De:"))
        self._de = QDateEdit(calendarPopup=True)
        self._de.setDisplayFormat("dd/MM/yyyy")
        self._de.setDate(QDate(desde.year, desde.month, desde.day))
        lin2.addWidget(self._de)
        lin2.addWidget(QLabel("Até:"))
        self._ate = QDateEdit(calendarPopup=True)
        self._ate.setDisplayFormat("dd/MM/yyyy")
        self._ate.setDate(QDate(ate.year, ate.month, ate.day))
        lin2.addWidget(self._ate)
        lin2.addStretch(1)
        col.addLayout(lin2)
        col.addStretch(1)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Ok).setText("OK")
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self._confirmar)
        botoes.rejected.connect(self.reject)
        col.addWidget(botoes)

        (self._rb_custom if personalizado else self._rb_padrao).setChecked(True)
        self._alternar()
        _centralizar(self, pai)

    def _alternar(self, *_):
        padrao = self._rb_padrao.isChecked()
        self._spin.setEnabled(padrao)
        self._de.setEnabled(not padrao)
        self._ate.setEnabled(not padrao)
        self._atualizar_previa()

    def _atualizar_previa(self, *_):
        d, a = self._padrao_para_anos(self._spin.value())
        self._previa.setText(
            "        de %s até %s" % (d.strftime("%d/%m/%Y"),
                                      a.strftime("%d/%m/%Y")))
        if self._rb_padrao.isChecked():
            self._de.setDate(QDate(d.year, d.month, d.day))
            self._ate.setDate(QDate(a.year, a.month, a.day))

    def _confirmar(self):
        if self._de.date() > self._ate.date():
            QMessageBox.warning(self, "Jovem advogado",
                                "A data inicial não pode ser depois da final.")
            return
        self.accept()

    def resultado(self):
        """(personalizado, anos, desde, ate) — datas como date do Python."""
        d, a = self._de.date(), self._ate.date()
        return (self._rb_custom.isChecked(), self._spin.value(),
                date(d.year(), d.month(), d.day()),
                date(a.year(), a.month(), a.day()))
