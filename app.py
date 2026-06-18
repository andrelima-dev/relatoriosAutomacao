import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from core.gerador import CATEGORIAS_ATIVAS, SITUACOES_ATIVAS, gerar_relatorios
from core.leitor import carregar_planilha
from core.utils import get_col, is_date_col

_DATE_PARSE_FMTS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d")

# Cores de log e elementos não cobertos pelo tema
_LOG = {
    "bg":   "#1e2d3d",
    "fg":   "#d4dce6",
    "ok":   "#56d364",
    "err":  "#f85149",
    "info": "#58a6ff",
    "dim":  "#8b949e",
}


def _resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


class App(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly", title="Gerador de Relatórios OAB")
        self.resizable(False, False)

        self._df = None
        self._xml_path = tk.StringVar()
        self._out_path = tk.StringVar()
        self._count_var = tk.StringVar(value="Nenhum arquivo selecionado.")
        self._nome_base = tk.StringVar(value="RELATORIO CADASTRO ADVOGADOS GERAL")
        self._chk_geral = tk.BooleanVar(value=True)
        self._chk_ativos = tk.BooleanVar(value=True)
        self._chk_por_uf = tk.BooleanVar(value=False)

        self._ws_names: list[str] = []
        self._ws_var = tk.StringVar()

        self._uf_col: str | None = None
        self._valores_uf: list[str] = []
        self._ufs_selecionadas: list[str] = []
        self._ufs_personalizado: list[str] = []
        self._lbl_uf_var = tk.StringVar(value="Nenhuma selecionada")
        self._lbl_uf_pers_var = tk.StringVar(value="Nenhuma selecionada")

        self._comarca_col: str | None = None
        self._valores_comarca: list[str] = []
        self._comarcas_selecionadas: list[str] = []
        self._lbl_comarca_var = tk.StringVar(value="Nenhuma selecionada")
        self._chk_por_comarca = tk.BooleanVar(value=False)

        self._date_cols: list[str] = []
        self._data_col_var = tk.StringVar()
        self._data_inicio_var = tk.StringVar()
        self._data_fim_var = tk.StringVar()
        self._chk_filtro_data = tk.BooleanVar(value=False)

        self._cats_selecionadas: set[str] = set(CATEGORIAS_ATIVAS)
        self._sits_selecionadas: set[str] = set(SITUACOES_ATIVAS)
        self._cats_disponiveis: list[str] = []
        self._sits_disponiveis: list[str] = []
        self._filtros_customizados: bool = False

        # Relatório personalizado
        self._chk_personalizado = tk.BooleanVar(value=False)
        self._base_personalizado = tk.StringVar(value="ativos")  # "ativos" | "geral"
        self._colunas_personalizado: list[str] = []
        self._cols_disponiveis: list[str] = []
        self._lbl_colunas_var = tk.StringVar(value="Nenhuma coluna selecionada")
        # col_nome -> lista de valores permitidos (ausente = sem filtro / todos)
        self._filtros_coluna_personalizado: dict[str, list[str]] = {}
        self._chk_uf_personalizado = tk.BooleanVar(value=False)

        self._logo_img = None
        self._dlg_loading: tk.Toplevel | None = None
        self._build_ui()
        self._center()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 12, "pady": 4}

        # Configura fonte padrão dos widgets ttk
        style = ttk.Style.instance
        style.configure(".", font=("Segoe UI", 9))
        style.configure("TLabelframe.Label", font=("Segoe UI", 9, "bold"))
        style.configure("TButton", font=("Segoe UI", 9))
        style.configure("TCheckbutton", font=("Segoe UI", 9))
        # ── 1+2. Arquivo & Saída (unificado) ─────────────────────────────
        frm1 = ttk.LabelFrame(self, text="Configuração")
        frm1.pack(fill="x", **pad)

        ttk.Label(frm1, text="Arquivo:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(frm1, textvariable=self._xml_path, width=44, state="readonly").grid(
            row=0, column=1, padx=4, pady=3, sticky="ew"
        )
        ttk.Button(frm1, text="Selecionar arquivo", command=self._selecionar_xml).grid(
            row=0, column=2, padx=6, pady=3
        )

        self._lbl_ws = ttk.Label(frm1, text="Planilha:")
        self._cmb_ws = ttk.Combobox(frm1, textvariable=self._ws_var, state="readonly", width=34)
        self._cmb_ws.bind("<<ComboboxSelected>>", self._on_ws_change)

        ttk.Label(frm1, text="Salvar em:").grid(row=2, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(frm1, textvariable=self._out_path, width=44).grid(
            row=2, column=1, padx=4, pady=3, sticky="ew"
        )
        ttk.Button(frm1, text="Alterar", command=self._selecionar_pasta).grid(
            row=2, column=2, padx=6, pady=3
        )

        ttk.Label(frm1, text="Nome base:").grid(row=3, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(frm1, textvariable=self._nome_base, width=44).grid(
            row=3, column=1, padx=4, pady=3, sticky="ew"
        )

        # ── 3. Preview inline ─────────────────────────────────────────────
        frm3 = ttk.LabelFrame(self, text="Preview")
        frm3.pack(fill="x", **pad)
        ttk.Label(frm3, textvariable=self._count_var,
                  bootstyle="info", font=("Segoe UI", 9, "bold")).pack(
            anchor="w", padx=10, pady=5
        )

        # ── 4. Relatórios prontos ─────────────────────────────────────────
        frm4 = ttk.LabelFrame(self, text="1 · Relatórios prontos  (arquivo único, todas as colunas)")
        frm4.pack(fill="x", **pad)

        ttk.Checkbutton(
            frm4, text="Geral  —  todos os registros do arquivo",
            variable=self._chk_geral, command=self._validar_selecao,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(4, 2))

        ttk.Checkbutton(
            frm4, text="Apenas ativos  —  só advogados em situação regular",
            variable=self._chk_ativos, command=self._validar_selecao,
        ).grid(row=1, column=0, sticky="w", padx=8, pady=2)
        self._btn_filtros = ttk.Button(
            frm4, text="Filtros...", command=self._abrir_filtros_ativos, width=9,
        )
        self._btn_filtros.grid(row=1, column=1, padx=4, pady=2, sticky="w")
        self._btn_filtros.config(state="disabled")

        ttk.Label(
            frm4,
            text="ℹ  Gera o arquivo com TODAS as colunas. Para escolher colunas "
                 "específicas ou filtrar valores (seccional, município...), "
                 "use o nº 2 abaixo.",
            bootstyle="secondary", font=("Segoe UI", 8),
            wraplength=560, justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=10, pady=(2, 6))

        # ── 5. Relatório personalizado ────────────────────────────────────
        frm5 = ttk.LabelFrame(
            self, text="2 · Relatório personalizado  (escolha colunas, filtros e divisão)"
        )
        frm5.pack(fill="x", **pad)

        self._chk_personalizado_btn = ttk.Checkbutton(
            frm5, text="Gerar relatório personalizado",
            variable=self._chk_personalizado, command=self._validar_selecao,
            state="disabled",
        )
        self._chk_personalizado_btn.grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))

        self._btn_colunas = ttk.Button(
            frm5, text="Selecionar Colunas...",
            command=self._abrir_seletor_colunas, state="disabled",
        )
        self._btn_colunas.grid(row=0, column=1, padx=6, pady=(6, 2), sticky="w")

        ttk.Label(
            frm5, textvariable=self._lbl_colunas_var,
            bootstyle="secondary", font=("Segoe UI", 8),
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=28, pady=(0, 2))

        # Base (ativos x todos)
        frm_base = ttk.Frame(frm5)
        frm_base.grid(row=2, column=0, columnspan=3, sticky="w", padx=28, pady=(0, 2))
        ttk.Label(frm_base, text="Base:").pack(side="left", padx=(0, 6))
        self._rb_base_ativos = ttk.Radiobutton(
            frm_base, text="Apenas ativos", value="ativos",
            variable=self._base_personalizado, state="disabled",
        )
        self._rb_base_ativos.pack(side="left", padx=(0, 12))
        self._rb_base_geral = ttk.Radiobutton(
            frm_base, text="Todos", value="geral",
            variable=self._base_personalizado, state="disabled",
        )
        self._rb_base_geral.pack(side="left")

        ttk.Label(
            frm5,
            text="ℹ  Para filtrar (seccional, município, situação...): clique "
                 "“Selecionar Colunas...” e use o botão ▼ ao lado de cada coluna.",
            bootstyle="secondary", font=("Segoe UI", 8),
            wraplength=560, justify="left",
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=10, pady=(2, 6))

        # ── 6. Filtro de Data ─────────────────────────────────────────────
        frm_data = ttk.LabelFrame(self, text="Filtro de Data  (aplica-se a todos os relatórios)")
        frm_data.pack(fill="x", **pad)

        self._chk_filtro_data_btn = ttk.Checkbutton(
            frm_data, text="Ativar filtro de data",
            variable=self._chk_filtro_data, command=self._toggle_filtro_data,
            state="disabled",
        )
        self._chk_filtro_data_btn.grid(row=0, column=0, columnspan=6, sticky="w", padx=6, pady=(4, 2))

        ttk.Label(frm_data, text="Coluna:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self._cmb_data_col = ttk.Combobox(
            frm_data, textvariable=self._data_col_var, state="disabled", width=22,
        )
        self._cmb_data_col.grid(row=1, column=1, padx=4, pady=4, sticky="w")

        ttk.Label(frm_data, text="De:").grid(row=1, column=2, sticky="w", padx=(14, 2), pady=4)
        self._ent_data_inicio = ttk.Entry(frm_data, textvariable=self._data_inicio_var, width=12, state="disabled")
        self._ent_data_inicio.grid(row=1, column=3, padx=2, pady=4)
        ttk.Label(frm_data, text="Até:").grid(row=1, column=4, sticky="w", padx=(10, 2), pady=4)
        self._ent_data_fim = ttk.Entry(frm_data, textvariable=self._data_fim_var, width=12, state="disabled")
        self._ent_data_fim.grid(row=1, column=5, padx=2, pady=4)
        ttk.Label(
            frm_data, text="formato: dd/mm/aaaa",
            bootstyle="secondary", font=("Segoe UI", 7),
        ).grid(row=2, column=1, columnspan=5, sticky="w", padx=4, pady=(0, 3))

        # ── 7. Barra de progresso ─────────────────────────────────────────
        frm_prog = ttk.Frame(self)
        frm_prog.pack(fill="x", padx=12, pady=(2, 0))
        self._progress = ttk.Progressbar(
            frm_prog, mode="determinate", maximum=100, bootstyle="info-striped",
        )
        self._progress.pack(fill="x")

        # ── 8. Botão Gerar ────────────────────────────────────────────────
        frm_btn = ttk.Frame(self)
        frm_btn.pack(fill="x", padx=12, pady=6)
        style = ttk.Style.instance
        style.configure("Gerar.success.TButton",
                        font=("Segoe UI", 11, "bold"), padding=(20, 10))
        self._btn_gerar = ttk.Button(
            frm_btn,
            text="▶   Gerar Relatórios",
            command=self._gerar,
            style="Gerar.success.TButton",
            cursor="hand2",
        )
        self._btn_gerar.pack(fill="x")

        # ── 9. Log ────────────────────────────────────────────────────────
        frm_log = ttk.LabelFrame(self, text="Log")
        frm_log.pack(fill="both", expand=True, padx=12, pady=5)
        self._log = ScrolledText(
            frm_log, height=8, state="disabled",
            font=("Consolas", 9), wrap="word",
            bg=_LOG["bg"], fg=_LOG["fg"],
            insertbackground=_LOG["fg"],
            relief="flat", bd=0,
        )
        self._log.pack(fill="both", expand=True, padx=4, pady=4)
        self._log.tag_config("ok",     foreground=_LOG["ok"])
        self._log.tag_config("erro",   foreground=_LOG["err"])
        self._log.tag_config("info",   foreground=_LOG["info"])
        self._log.tag_config("normal", foreground=_LOG["fg"])

        self.geometry("680x820")

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    # ── Tela de carregamento ──────────────────────────────────────────────────

    def _mostrar_carregando(self, msg: str = "Carregando..."):
        if self._dlg_loading:
            return
        s = ttk.Style.instance
        bg     = s.colors.bg
        surface = s.colors.selectbg
        fg     = s.colors.fg
        accent = s.colors.info

        dlg = tk.Toplevel(self)
        dlg.overrideredirect(True)
        dlg.configure(bg=accent)
        dlg.attributes("-topmost", True)

        borda = tk.Frame(dlg, bg=accent, padx=1, pady=1)
        borda.pack(fill="both", expand=True)
        body = tk.Frame(borda, bg=bg)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="⏳", font=("Segoe UI Emoji", 20), bg=bg).pack(pady=(16, 2))

        self._loading_msg_var = tk.StringVar(value=msg)
        tk.Label(
            body, textvariable=self._loading_msg_var,
            font=("Segoe UI", 9, "bold"), fg=accent, bg=bg,
        ).pack(padx=32, pady=(0, 6))

        self._loading_pb = ttk.Progressbar(
            body, mode="determinate", maximum=100, length=240, bootstyle="info-striped",
        )
        self._loading_pb.pack(padx=24, pady=(0, 4))

        self._loading_pct_var = tk.StringVar(value="0%")
        tk.Label(
            body, textvariable=self._loading_pct_var,
            font=("Segoe UI", 8), fg=fg, bg=bg,
        ).pack(pady=(0, 16))

        dlg.update_idletasks()
        w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.update()
        self._dlg_loading = dlg

    def _set_loading_progress(self, pct: int):
        if self._dlg_loading and hasattr(self, "_loading_pb"):
            self._loading_pb["value"] = pct
            self._loading_pct_var.set(f"{pct}%")
            self._dlg_loading.update_idletasks()

    def _atualizar_carregando(self, msg: str):
        if hasattr(self, "_loading_msg_var") and self._loading_msg_var:
            self._loading_msg_var.set(msg)

    def _esconder_carregando(self):
        if self._dlg_loading:
            try:
                self._dlg_loading.destroy()
            except Exception:
                pass
            self._dlg_loading = None

    # ── Selecionar XML ────────────────────────────────────────────────────────

    def _selecionar_xml(self):
        path = filedialog.askopenfilename(
            title="Selecionar arquivo (XML ou Excel)",
            filetypes=[
                ("Planilhas (XML/Excel)", "*.xml *.xlsx *.xlsm"),
                ("Arquivos XML", "*.xml"),
                ("Arquivos Excel", "*.xlsx *.xlsm"),
                ("Todos", "*.*"),
            ],
        )
        if not path:
            return

        self._mostrar_carregando("Carregando arquivo...")
        self._count_var.set("Carregando...")
        self._log_clear()
        self._df = None

        def _task():
            def progress(pct: int):
                self.after(0, lambda p=pct: self._set_loading_progress(p))
            try:
                nomes, df = carregar_planilha(path, progress_cb=progress)
                self.after(0, lambda: self._apos_carregar_xml(path, nomes, df))
            except Exception as exc:
                self.after(0, self._esconder_carregando)
                self.after(0, lambda: messagebox.showerror("Arquivo inválido", str(exc)))
                self.after(0, lambda: self._count_var.set("Erro ao carregar."))

        threading.Thread(target=_task, daemon=True).start()

    def _apos_carregar_xml(self, path: str, nomes: list[str], df):
        self._xml_path.set(path)
        if not self._out_path.get():
            self._out_path.set(os.path.dirname(path))

        self._ws_names = nomes
        self._ws_var.set(nomes[0])

        if len(nomes) > 1:
            self._cmb_ws["values"] = nomes
            self._lbl_ws.grid(row=1, column=0, sticky="w", padx=6, pady=3)
            self._cmb_ws.grid(row=1, column=1, columnspan=2, padx=4, pady=3, sticky="w")
        else:
            self._lbl_ws.grid_remove()
            self._cmb_ws.grid_remove()

        self._df = df
        self._esconder_carregando()
        self._apos_carregar(df)

    def _on_ws_change(self, _event=None):
        path = self._xml_path.get()
        if not path:
            return
        ws_idx = (
            self._ws_names.index(self._ws_var.get())
            if self._ws_var.get() in self._ws_names
            else 0
        )
        self._mostrar_carregando("Carregando planilha...")
        self._count_var.set("Carregando...")
        self._log_clear()
        self._df = None

        def _task():
            try:
                _, df = carregar_planilha(path, ws_idx)
                self.after(0, self._esconder_carregando)
                self.after(0, lambda: self._apos_ws_change(df))
            except Exception as exc:
                self.after(0, self._esconder_carregando)
                self.after(0, lambda: self._log_append(f"Erro: {exc}", "erro"))

        threading.Thread(target=_task, daemon=True).start()

    def _apos_ws_change(self, df):
        self._df = df
        self._apos_carregar(df)

    def _apos_carregar(self, df):
        total = len(df)

        col_cat = get_col(df, "CATEGORIA")
        col_sit = get_col(df, "SITUACAO_INSCRICAO")
        if col_cat and col_sit:
            mask = (
                df[col_cat].str.strip().str.upper().isin({c.upper() for c in CATEGORIAS_ATIVAS})
                & df[col_sit].str.strip().str.upper().isin({s.upper() for s in SITUACOES_ATIVAS})
            )
            ativos = int(mask.sum())
            self._count_var.set(f"{total} registros carregados  |  Ativos: {ativos}")
        else:
            self._count_var.set(f"{total} registros carregados")

        self._log_append(f"{total} registros carregados", "ok")

        if col_cat:
            self._cats_disponiveis = sorted(
                df[col_cat].str.strip().str.upper().dropna().unique().tolist()
            )
        if col_sit:
            self._sits_disponiveis = sorted(
                df[col_sit].str.strip().str.upper().dropna().unique().tolist()
            )

        self._btn_filtros.config(
            state="normal" if (col_cat or col_sit) else "disabled"
        )

        # Colunas disponíveis para o relatório personalizado
        self._cols_disponiveis = list(df.columns)
        self._colunas_personalizado = []
        self._filtros_coluna_personalizado = {}
        self._lbl_colunas_var.set("Nenhuma coluna selecionada")
        self._chk_personalizado_btn.config(state="normal")
        self._btn_colunas.config(state="normal")
        self._rb_base_ativos.config(state="normal")
        self._rb_base_geral.config(state="normal")

        # Detecção automática da coluna de seccional
        self._uf_col = self._detectar_col_subsecao(df)
        if self._uf_col:
            primeiros = sorted(
                str(v).strip() for v in df[self._uf_col].dropna().unique() if str(v).strip()
            )[:5]
            self._log_append(
                f"Seccional → coluna '{self._uf_col}'  "
                f"(ex: {', '.join(primeiros)}...)",
                "info",
            )
            self._popular_valores_uf(df, self._uf_col)
        else:
            self._log_append("Coluna de seccional não detectada no arquivo.", "normal")
            self._ufs_selecionadas = []
            self._lbl_uf_var.set("Nenhuma selecionada")
            self._ufs_personalizado = []
            self._lbl_uf_pers_var.set("Nenhuma selecionada")

        # Detecção automática da coluna de município
        self._comarca_col = self._detectar_col_comarca(df)
        if self._comarca_col:
            primeiros_c = sorted(
                str(v).strip() for v in df[self._comarca_col].dropna().unique() if str(v).strip()
            )[:5]
            self._log_append(
                f"Município → coluna '{self._comarca_col}'  "
                f"(ex: {', '.join(primeiros_c)}...)",
                "info",
            )
            self._popular_valores_comarca(df, self._comarca_col)
        else:
            self._comarcas_selecionadas = []
            self._lbl_comarca_var.set("Nenhuma selecionada")

        # Detectar colunas de data
        self._date_cols = [c for c in df.columns if is_date_col(c)]
        if self._date_cols:
            self._cmb_data_col["values"] = self._date_cols
            self._data_col_var.set(self._date_cols[0])
            self._chk_filtro_data_btn.config(state="normal")
        else:
            self._chk_filtro_data.set(False)
            self._chk_filtro_data_btn.config(state="disabled")
        self._toggle_filtro_data()

    @staticmethod
    def _detectar_col_subsecao(df):
        def skip(col: str) -> bool:
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
            if skip(col):
                continue
            u = col.strip().upper()
            if "SUBSEC" in u or "SECCIONAL" in u:
                return col

        best_col, best_score = None, -1
        for col in df.columns:
            if skip(col):
                continue
            vals = [str(v).strip() for v in df[col].dropna().unique() if str(v).strip()]
            n = len(vals)
            if n < 5 or n > 45:
                continue
            avg_len = sum(len(v) for v in vals[:30]) / min(len(vals), 30)
            if avg_len <= 3:
                continue
            score = avg_len * 2 + (50 - n)
            if score > best_score:
                best_score = score
                best_col = col

        return best_col

    def _popular_valores_uf(self, df, col_nome: str):
        col = get_col(df, col_nome) or col_nome
        if col not in df.columns:
            return
        self._valores_uf = sorted(
            str(v).strip() for v in df[col].dropna().unique() if str(v).strip()
        )
        self._ufs_selecionadas = []
        self._ufs_personalizado = []
        self._lbl_uf_var.set("Nenhuma selecionada")
        self._lbl_uf_pers_var.set("Nenhuma selecionada")

    @staticmethod
    def _detectar_col_comarca(df):
        # Prioridade: MUN_RES, depois variações comuns
        prioridade = ["MUN_RES", "MUNICIPIO_RES", "MUNICIPIO", "MUNICÍPIO",
                      "CIDADE", "MUN_COMARCA", "MUNICIPIO_COMARCA"]
        cols_upper = {c.strip().upper(): c for c in df.columns}
        for nome in prioridade:
            if nome in cols_upper:
                return cols_upper[nome]

        for col in df.columns:
            u = col.strip().upper()
            if u.startswith("MUN_") or "MUNIC" in u:
                return col

        return None

    def _popular_valores_comarca(self, df, col_nome: str):
        col = get_col(df, col_nome) or col_nome
        if col not in df.columns:
            return
        self._valores_comarca = sorted(
            str(v).strip() for v in df[col].dropna().unique() if str(v).strip()
        )
        self._comarcas_selecionadas = []
        self._lbl_comarca_var.set("Nenhuma selecionada")

    # ── Toggle filtro de data ─────────────────────────────────────────────────

    def _toggle_filtro_data(self):
        ativo = self._chk_filtro_data.get() and bool(self._date_cols)
        state_cmb = "readonly" if ativo else "disabled"
        state_ent = "normal" if ativo else "disabled"
        self._cmb_data_col.config(state=state_cmb)
        self._ent_data_inicio.config(state=state_ent)
        self._ent_data_fim.config(state=state_ent)
        if not ativo:
            self._data_inicio_var.set("")
            self._data_fim_var.set("")

    # ── Selecionar pasta ──────────────────────────────────────────────────────

    def _selecionar_pasta(self):
        pasta = filedialog.askdirectory(title="Selecionar pasta de saída")
        if pasta:
            self._out_path.set(pasta)

    # ── Validação ─────────────────────────────────────────────────────────────

    def _validar_selecao(self):
        personalizado_ok = (
            self._chk_personalizado.get() and bool(self._colunas_personalizado)
        )
        nenhum = (
            not self._chk_geral.get()
            and not self._chk_ativos.get()
            and not personalizado_ok
        )
        self._btn_gerar.config(state="disabled" if nenhum else "normal")

    # ── Diálogo de seleção de seccionais ─────────────────────────────────────

    @staticmethod
    def _fmt_ufs(ufs: list[str]) -> str:
        if not ufs:
            return "Nenhuma selecionada"
        if len(ufs) <= 2:
            return ", ".join(ufs)
        return f"{len(ufs)} selecionadas"

    def _abrir_seletor_seccionais(self, target: str):
        if target == "comarca":
            valores = self._valores_comarca
            atual = self._comarcas_selecionadas
            titulo = "Selecionar Municípios"
            rotulo = "Municípios disponíveis"
        else:
            valores = self._valores_uf
            atual = self._ufs_selecionadas if target == "principal" else self._ufs_personalizado
            titulo = "Selecionar Seccionais"
            rotulo = "Seccionais disponíveis"

        if not valores:
            return

        dlg = tk.Toplevel(self)
        dlg.title(titulo)
        dlg.resizable(False, True)
        dlg.grab_set()

        uf_vars: dict[str, tk.BooleanVar] = {}

        frm_topo = ttk.Frame(dlg)
        frm_topo.pack(fill="x", padx=12, pady=(10, 4))

        # Pré-cria todos os BooleanVars para preservar estado durante a busca
        for uf in valores:
            uf_vars[uf] = tk.BooleanVar(value=uf in atual)

        def _sel_todas():
            for v in uf_vars.values():
                v.set(True)

        def _limpar():
            for v in uf_vars.values():
                v.set(False)

        ttk.Button(frm_topo, text="Selecionar Todas", command=_sel_todas, width=16).pack(side="left", padx=(0, 6))
        ttk.Button(frm_topo, text="Limpar", command=_limpar, width=10).pack(side="left")

        # Campo de busca com botão
        frm_busca = ttk.Frame(dlg)
        frm_busca.pack(fill="x", padx=12, pady=(0, 4))
        ttk.Label(frm_busca, text="Buscar:").pack(side="left", padx=(0, 4))
        busca_var = tk.StringVar()
        ent_busca = ttk.Entry(frm_busca, textvariable=busca_var, width=24)
        ent_busca.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ent_busca.focus_set()

        frm_lista = ttk.LabelFrame(dlg, text=rotulo)
        frm_lista.pack(fill="both", expand=True, padx=12, pady=4)

        canvas = tk.Canvas(frm_lista, width=300, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frm_lista, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _refresh_lista(_=None):
            for w in inner.winfo_children():
                w.destroy()
            filtro = busca_var.get().strip().lower()
            for uf in valores:
                if filtro and filtro not in uf.lower():
                    continue
                ttk.Checkbutton(inner, text=uf, variable=uf_vars[uf]).pack(anchor="w", padx=8, pady=1)
            inner.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(0)

        ttk.Button(frm_busca, text="Buscar", command=_refresh_lista, width=8).pack(side="left")
        ent_busca.bind("<Return>", _refresh_lista)

        _refresh_lista()

        def _on_configure(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())

        inner.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_configure)

        def _scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _scroll)

        canvas.config(height=min(max(len(valores) * 24, 80), 400))

        frm_btn = ttk.Frame(dlg)
        frm_btn.pack(padx=12, pady=10)

        def _ok():
            canvas.unbind_all("<MouseWheel>")
            selecionadas = [uf for uf in valores if uf_vars[uf].get()]
            if target == "principal":
                self._ufs_selecionadas = selecionadas
                self._lbl_uf_var.set(self._fmt_ufs(selecionadas))
            elif target == "comarca":
                self._comarcas_selecionadas = selecionadas
                self._lbl_comarca_var.set(self._fmt_ufs(selecionadas))
            else:
                self._ufs_personalizado = selecionadas
                self._lbl_uf_pers_var.set(self._fmt_ufs(selecionadas))
            self._validar_selecao()
            dlg.destroy()

        def _cancelar():
            canvas.unbind_all("<MouseWheel>")
            dlg.destroy()

        ttk.Button(frm_btn, text="OK", command=_ok, width=10).pack(side="left", padx=6)
        ttk.Button(frm_btn, text="Cancelar", command=_cancelar, width=10).pack(side="left", padx=6)

        dlg.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dlg.winfo_reqwidth()) // 2
        y = self.winfo_y() + (self.winfo_height() - dlg.winfo_reqheight()) // 2
        dlg.geometry(f"+{x}+{y}")

    # ── Diálogo de filtros de Ativos ──────────────────────────────────────────

    def _abrir_filtros_ativos(self):
        if not self._cats_disponiveis and not self._sits_disponiveis:
            return

        dlg = tk.Toplevel(self)
        dlg.title("Filtros — Geral Ativos")
        dlg.resizable(False, False)
        dlg.grab_set()

        cat_vars: dict[str, tk.BooleanVar] = {}
        sit_vars: dict[str, tk.BooleanVar] = {}

        if self._cats_disponiveis:
            frm_cat = ttk.LabelFrame(dlg, text="Categorias a incluir")
            frm_cat.pack(fill="x", padx=12, pady=(10, 4))
            for cat in self._cats_disponiveis:
                var = tk.BooleanVar(value=cat in self._cats_selecionadas)
                cat_vars[cat] = var
                ttk.Checkbutton(frm_cat, text=cat, variable=var).pack(anchor="w", padx=8, pady=1)

        if self._sits_disponiveis:
            frm_sit = ttk.LabelFrame(dlg, text="Situações a incluir")
            frm_sit.pack(fill="x", padx=12, pady=4)
            for sit in self._sits_disponiveis:
                padrao = sit in SITUACOES_ATIVAS
                customizado = sit in self._sits_selecionadas
                marcado = customizado if self._filtros_customizados else padrao
                var = tk.BooleanVar(value=marcado)
                sit_vars[sit] = var
                ttk.Checkbutton(frm_sit, text=sit, variable=var).pack(anchor="w", padx=8, pady=1)

        frm_btn = ttk.Frame(dlg)
        frm_btn.pack(padx=12, pady=10)

        def _ok():
            self._cats_selecionadas = {c for c, v in cat_vars.items() if v.get()}
            self._sits_selecionadas = {s for s, v in sit_vars.items() if v.get()}
            self._filtros_customizados = True
            dlg.destroy()

        ttk.Button(frm_btn, text="OK", command=_ok, width=10).pack(side="left", padx=6)
        ttk.Button(frm_btn, text="Cancelar", command=dlg.destroy, width=10).pack(side="left", padx=6)

        dlg.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dlg.winfo_reqwidth()) // 2
        y = self.winfo_y() + (self.winfo_height() - dlg.winfo_reqheight()) // 2
        dlg.geometry(f"+{x}+{y}")

    # ── Diálogo de seleção de colunas ─────────────────────────────────────────

    def _abrir_seletor_colunas(self):
        if not self._cols_disponiveis:
            return

        dlg = tk.Toplevel(self)
        dlg.title("Selecionar Colunas — Relatório Personalizado")
        dlg.resizable(False, True)
        dlg.grab_set()

        # Botões de ação rápida
        frm_topo = ttk.Frame(dlg)
        frm_topo.pack(fill="x", padx=12, pady=(10, 4))

        col_vars: dict[str, tk.BooleanVar] = {}

        def _sel_todos():
            for v in col_vars.values():
                v.set(True)

        def _limpar():
            for v in col_vars.values():
                v.set(False)

        ttk.Button(frm_topo, text="Selecionar Todas", command=_sel_todos, width=16).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(frm_topo, text="Limpar", command=_limpar, width=10).pack(side="left")

        # Lista de colunas com scroll
        frm_lista = ttk.LabelFrame(dlg, text="Colunas disponíveis")
        frm_lista.pack(fill="both", expand=True, padx=12, pady=4)

        canvas = tk.Canvas(frm_lista, width=340, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frm_lista, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        filtro_btns: dict[str, ttk.Button] = {}

        def _atualizar_btn_filtro(col: str):
            btn = filtro_btns.get(col)
            if not btn:
                return
            ativo = bool(self._filtros_coluna_personalizado.get(col))
            btn.config(
                text="▼ Filtrado" if ativo else "▼ Filtrar",
                bootstyle="info" if ativo else "secondary-outline",
            )

        for col in self._cols_disponiveis:
            already = col in self._colunas_personalizado
            var = tk.BooleanVar(value=already)
            col_vars[col] = var

            row = ttk.Frame(inner)
            row.pack(fill="x", anchor="w", padx=8, pady=1)
            ttk.Checkbutton(row, text=col, variable=var).pack(side="left", anchor="w")
            btn_f = ttk.Button(
                row, text="▼ Filtrar", width=11,
                command=lambda c=col: self._abrir_filtro_valores(
                    c, lambda c2=col: _atualizar_btn_filtro(c2)
                ),
            )
            btn_f.pack(side="right", padx=(6, 0))
            filtro_btns[col] = btn_f
            _atualizar_btn_filtro(col)

        def _on_configure(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())

        inner.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_configure)

        # Scroll com roda do mouse
        def _scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _scroll)

        # Limitar altura do canvas
        n = len(self._cols_disponiveis)
        canvas_h = min(max(n * 24, 80), 400)
        canvas.config(height=canvas_h)

        # Botões OK / Cancelar
        frm_btn = ttk.Frame(dlg)
        frm_btn.pack(padx=12, pady=10)

        def _ok():
            canvas.unbind_all("<MouseWheel>")
            selecionadas = [c for c in self._cols_disponiveis if col_vars[c].get()]
            self._colunas_personalizado = selecionadas
            # Descarta filtros de colunas que deixaram de estar selecionadas
            self._filtros_coluna_personalizado = {
                c: v for c, v in self._filtros_coluna_personalizado.items()
                if c in selecionadas
            }
            n_sel = len(selecionadas)
            if self._filtros_coluna_personalizado:
                partes = []
                for c, v in self._filtros_coluna_personalizado.items():
                    partes.append(
                        f"{c}={'/'.join(v)}" if len(v) <= 2 else f"{c}=({len(v)})"
                    )
                sufixo_filtro = "  •  Filtros: " + ", ".join(partes)
            else:
                sufixo_filtro = ""
            if n_sel == 0:
                self._lbl_colunas_var.set("Nenhuma coluna selecionada")
            elif n_sel <= 4:
                self._lbl_colunas_var.set(f"{n_sel} colunas: {', '.join(selecionadas)}{sufixo_filtro}")
            else:
                preview = ", ".join(selecionadas[:3])
                self._lbl_colunas_var.set(f"{n_sel} colunas selecionadas ({preview}...){sufixo_filtro}")
            self._validar_selecao()
            dlg.destroy()

        def _cancelar():
            canvas.unbind_all("<MouseWheel>")
            dlg.destroy()

        ttk.Button(frm_btn, text="OK", command=_ok, width=10).pack(side="left", padx=6)
        ttk.Button(frm_btn, text="Cancelar", command=_cancelar, width=10).pack(side="left", padx=6)

        dlg.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dlg.winfo_reqwidth()) // 2
        y = self.winfo_y() + (self.winfo_height() - dlg.winfo_reqheight()) // 2
        dlg.geometry(f"+{x}+{y}")

    # ── Filtro de valores por coluna (estilo AutoFiltro do Excel) ─────────────

    def _abrir_filtro_valores(self, col_nome: str, on_close=None):
        if self._df is None:
            return
        col_real = get_col(self._df, col_nome) or col_nome
        if col_real not in self._df.columns:
            return

        valores = sorted(
            str(v).strip() for v in self._df[col_real].dropna().unique() if str(v).strip()
        )
        if not valores:
            messagebox.showinfo(
                "Filtro", f"A coluna '{col_nome}' não possui valores para filtrar."
            )
            return

        atual = self._filtros_coluna_personalizado.get(col_nome)  # None = todos

        # Estado leve (dict de bool) — suporta colunas com milhares de valores
        # distintos sem criar um widget por valor.
        estado: dict[str, bool] = {
            v: (atual is None) or (v in atual) for v in valores
        }
        MAX_RENDER = 500

        # Formata datas de colunas de data para exibição (DD/MM/AAAA)
        _is_date = is_date_col(col_nome)
        _DATE_DISPLAY_FMTS = [
            ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y"),
            ("%Y-%m-%dT%H:%M:%S.%f", "%d/%m/%Y"),
            ("%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"),
            ("%Y-%m-%d", "%d/%m/%Y"),
        ]

        def _fmt_val(v: str) -> str:
            if not _is_date:
                return v
            for fmt_in, fmt_out in _DATE_DISPLAY_FMTS:
                try:
                    return datetime.strptime(v, fmt_in).strftime(fmt_out)
                except ValueError:
                    continue
            return v

        dlg = tk.Toplevel(self)
        dlg.title(f"Filtrar — {col_nome}")
        dlg.resizable(False, True)
        dlg.grab_set()

        busca_var = tk.StringVar()
        info_var = tk.StringVar()
        todos_var = tk.BooleanVar(value=all(estado.values()))

        def _matches() -> list[str]:
            filtro = busca_var.get().strip().lower()
            if not filtro:
                return valores
            return [v for v in valores if filtro in v.lower() or filtro in _fmt_val(v).lower()]

        # (Selecionar Tudo) — marca/desmarca TODOS os valores (estilo Excel)
        frm_topo = ttk.Frame(dlg)
        frm_topo.pack(fill="x", padx=14, pady=(10, 2))

        def _toggle_todos():
            val = todos_var.get()
            for v in valores:
                estado[v] = val
            _refresh_lista()

        chk_todos = ttk.Checkbutton(
            frm_topo, text="(Selecionar Tudo)", variable=todos_var,
            command=_toggle_todos,
        )
        chk_todos.pack(side="left", anchor="w")

        # Busca + "Somente estes" (filtra só os resultados da busca)
        frm_busca = ttk.Frame(dlg)
        frm_busca.pack(fill="x", padx=12, pady=(4, 2))
        ttk.Label(frm_busca, text="Pesquisar:").pack(side="left", padx=(0, 4))
        ent_busca = ttk.Entry(frm_busca, textvariable=busca_var)
        ent_busca.pack(side="left", fill="x", expand=True)
        ent_busca.focus_set()

        def _somente_estes():
            sel = set(_matches())
            for v in valores:
                estado[v] = v in sel
            _refresh_lista()

        ttk.Button(
            frm_busca, text="Somente estes", command=_somente_estes, width=14,
            bootstyle="info-outline",
        ).pack(side="left", padx=(6, 0))

        ttk.Label(
            dlg, textvariable=info_var, bootstyle="secondary", font=("Segoe UI", 8),
        ).pack(fill="x", padx=14, pady=(0, 2))

        frm_lista = ttk.LabelFrame(dlg, text="Valores")
        frm_lista.pack(fill="both", expand=True, padx=12, pady=4)

        canvas = tk.Canvas(frm_lista, width=280, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frm_lista, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        # Mantém referências aos BooleanVars renderizados (apenas os visíveis)
        render_vars: dict[str, tk.BooleanVar] = {}

        def _refresh_lista(_=None):
            for w in inner.winfo_children():
                w.destroy()
            render_vars.clear()
            matches = _matches()
            mostrados = matches[:MAX_RENDER]
            for v in mostrados:
                bv = tk.BooleanVar(value=estado[v])
                render_vars[v] = bv

                def _on_toggle(vv=v, b=bv):
                    estado[vv] = b.get()

                ttk.Checkbutton(
                    inner, text=_fmt_val(v), variable=bv, command=_on_toggle,
                ).pack(anchor="w", padx=8, pady=1)

            sel_total = sum(1 for v in valores if estado[v])
            buscando = bool(busca_var.get().strip())
            todos_var.set(bool(valores) and all(estado[v] for v in valores))
            chk_todos.config(
                text="(Selecionar Tudo)"
                if not buscando
                else f"(Selecionar Tudo)    ·    {len(matches)} na busca"
            )
            if len(matches) > MAX_RENDER:
                info_var.set(
                    f"{sel_total}/{len(valores)} selecionados  •  "
                    f"mostrando {MAX_RENDER} de {len(matches)} — refine a busca"
                )
            else:
                info_var.set(f"{sel_total}/{len(valores)} selecionados")

            inner.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(0)

        # Debounce da busca para não re-renderizar a cada tecla
        _busca_after: dict[str, str | None] = {"id": None}

        def _on_busca(_=None):
            if _busca_after["id"]:
                self.after_cancel(_busca_after["id"])
            _busca_after["id"] = self.after(250, _refresh_lista)

        ent_busca.bind("<KeyRelease>", _on_busca)
        _refresh_lista()

        def _on_configure(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())

        inner.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_configure)

        def _scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _scroll)

        canvas.config(height=min(max(len(valores) * 24, 80), 360))

        frm_btn = ttk.Frame(dlg)
        frm_btn.pack(padx=12, pady=10)

        def _ok():
            canvas.unbind_all("<MouseWheel>")
            sel = [v for v in valores if estado[v]]
            if not sel:
                messagebox.showwarning(
                    "Filtro", "Selecione ao menos um valor (ou use 'Remover filtro')."
                )
                canvas.bind_all("<MouseWheel>", _scroll)
                return
            if len(sel) == len(valores):
                self._filtros_coluna_personalizado.pop(col_nome, None)  # sem filtro
            else:
                self._filtros_coluna_personalizado[col_nome] = sel
            if on_close:
                on_close()
            dlg.destroy()

        def _limpar_filtro():
            canvas.unbind_all("<MouseWheel>")
            self._filtros_coluna_personalizado.pop(col_nome, None)
            if on_close:
                on_close()
            dlg.destroy()

        def _cancelar():
            canvas.unbind_all("<MouseWheel>")
            dlg.destroy()

        ttk.Button(frm_btn, text="OK", command=_ok, width=10).pack(side="left", padx=4)
        ttk.Button(frm_btn, text="Remover filtro", command=_limpar_filtro, width=14).pack(side="left", padx=4)
        ttk.Button(frm_btn, text="Cancelar", command=_cancelar, width=10).pack(side="left", padx=4)

        dlg.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dlg.winfo_reqwidth()) // 2
        y = self.winfo_y() + (self.winfo_height() - dlg.winfo_reqheight()) // 2
        dlg.geometry(f"+{x}+{y}")

    # ── Gerar ─────────────────────────────────────────────────────────────────

    def _gerar(self):
        if self._df is None:
            self._log_append("Selecione um arquivo válido antes de gerar.", "erro")
            return
        pasta = self._out_path.get().strip()
        if not pasta:
            self._log_append("Informe a pasta de saída.", "erro")
            return

        personalizado_ok = self._chk_personalizado.get() and bool(self._colunas_personalizado)
        if self._chk_personalizado.get() and not self._colunas_personalizado:
            self._log_append(
                "Relatório personalizado: clique 'Selecionar Colunas...' e escolha "
                "ao menos uma coluna.", "erro")
            return
        if not self._chk_geral.get() and not self._chk_ativos.get() and not personalizado_ok:
            self._log_append("Selecione ao menos um relatório para gerar.", "erro")
            return

        filtro_data_ativo = self._chk_filtro_data.get() and bool(self._date_cols)
        data_inicio = self._parse_data_ui(self._data_inicio_var.get()) if filtro_data_ativo else None
        data_fim = self._parse_data_ui(self._data_fim_var.get()) if filtro_data_ativo else None
        if filtro_data_ativo and self._data_inicio_var.get().strip() and data_inicio is None:
            self._log_append("Data inicial inválida. Use o formato dd/mm/aaaa.", "erro")
            return
        if filtro_data_ativo and self._data_fim_var.get().strip() and data_fim is None:
            self._log_append("Data final inválida. Use o formato dd/mm/aaaa.", "erro")
            return

        geral        = self._chk_geral.get()
        ativos       = self._chk_ativos.get()
        data_col = self._data_col_var.get() if filtro_data_ativo else None
        nome_base = self._nome_base.get().strip() or "RELATORIO CADASTRO ADVOGADOS GERAL"
        cats = set(self._cats_selecionadas) if self._filtros_customizados else None
        sits = set(self._sits_selecionadas) if self._filtros_customizados else None

        self._btn_gerar.config(state="disabled", text="Processando...")
        self._progress["value"] = 0
        self._log_clear()

        df = self._df.copy()
        colunas_pers = list(self._colunas_personalizado) if personalizado_ok else None
        base_pers = self._base_personalizado.get()
        filtros_valores_pers = (
            {c: list(v) for c, v in self._filtros_coluna_personalizado.items()
             if c in self._colunas_personalizado and v}
            if personalizado_ok else None
        )

        def _processar():
            def progress(pct: int):
                self.after(0, lambda p=pct: self._progress.config(value=p))

            def log(msg, tag="normal"):
                self.after(0, lambda m=msg, t=tag: self._log_append(m, t))

            try:
                gerar_relatorios(
                    df, pasta, log,
                    gerar_geral=geral,
                    gerar_ativos=ativos,
                    categorias_filtro=cats,
                    situacoes_filtro=sits,
                    data_col=data_col,
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                    nome_base=nome_base,
                    progress_cb=progress,
                    gerar_personalizado=personalizado_ok,
                    colunas_personalizado=colunas_pers,
                    filtros_valores_personalizado=filtros_valores_pers,
                    personalizado_base=base_pers,
                )
                self.after(0, lambda: self._log_append(
                    f"Concluído! Arquivos salvos em: {pasta}", "ok"
                ))
                self.after(0, lambda: self._abrir_pasta(pasta))
            except Exception as exc:
                self.after(0, lambda: self._log_append(f"Erro: {exc}", "erro"))
            finally:
                self.after(0, lambda: self._btn_gerar.config(
                    state="normal", text="▶   Gerar Relatórios"
                ))

        threading.Thread(target=_processar, daemon=True).start()

    @staticmethod
    def _parse_data_ui(s: str) -> datetime | None:
        s = s.strip()
        if not s:
            return None
        for fmt in _DATE_PARSE_FMTS:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log_clear(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    def _log_append(self, texto: str, tag: str = "normal"):
        self._log.config(state="normal")
        self._log.insert("end", texto + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

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
