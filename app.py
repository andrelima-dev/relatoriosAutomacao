import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from core.leitor import ler_xml
from core.gerador import gerar_relatorios


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gerador de Relatórios OAB")
        self.resizable(False, False)
        self._df = None
        self._xml_path = tk.StringVar()
        self._out_path = tk.StringVar()
        self._count_var = tk.StringVar(value="Nenhum arquivo selecionado.")
        self._chk_geral = tk.BooleanVar(value=True)
        self._chk_ativos = tk.BooleanVar(value=True)
        self._build_ui()
        self._center()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        # ── Seção 1 – Arquivo ─────────────────────────────────────────────
        frm1 = ttk.LabelFrame(self, text="Arquivo")
        frm1.pack(fill="x", **pad)

        ttk.Label(frm1, text="Arquivo XML:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frm1, textvariable=self._xml_path, width=52, state="readonly").grid(
            row=0, column=1, padx=4, pady=4
        )
        ttk.Button(frm1, text="Selecionar XML", command=self._selecionar_xml).grid(
            row=0, column=2, padx=6, pady=4
        )

        # ── Seção 2 – Pasta de saída ──────────────────────────────────────
        frm2 = ttk.LabelFrame(self, text="Pasta de saída")
        frm2.pack(fill="x", **pad)

        ttk.Label(frm2, text="Salvar em:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frm2, textvariable=self._out_path, width=52).grid(
            row=0, column=1, padx=4, pady=4
        )
        ttk.Button(frm2, text="Alterar", command=self._selecionar_pasta).grid(
            row=0, column=2, padx=6, pady=4
        )

        # ── Seção 3 – Preview ─────────────────────────────────────────────
        frm3 = ttk.LabelFrame(self, text="Preview")
        frm3.pack(fill="x", **pad)
        ttk.Label(frm3, textvariable=self._count_var, foreground="#444").pack(
            anchor="w", padx=8, pady=6
        )

        # ── Seção 4 – Relatórios ──────────────────────────────────────────
        frm4 = ttk.LabelFrame(self, text="Relatórios a gerar")
        frm4.pack(fill="x", **pad)

        ttk.Checkbutton(
            frm4, text="Geral (todos os registros)", variable=self._chk_geral,
            command=self._validar_selecao,
        ).pack(anchor="w", padx=8, pady=2)
        ttk.Checkbutton(
            frm4, text="Geral Ativos (apenas advogados ativos)", variable=self._chk_ativos,
            command=self._validar_selecao,
        ).pack(anchor="w", padx=8, pady=2)

        # ── Seção 5 – Ação ────────────────────────────────────────────────
        frm5 = ttk.Frame(self)
        frm5.pack(fill="x", padx=12, pady=4)

        self._btn_gerar = tk.Button(
            frm5,
            text="Gerar Relatórios",
            command=self._gerar,
            bg="#1565C0",
            fg="white",
            activebackground="#0D47A1",
            activeforeground="white",
            font=("Verdana", 11, "bold"),
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
        )
        self._btn_gerar.pack(fill="x")

        # ── Seção 6 – Log ─────────────────────────────────────────────────
        frm5 = ttk.LabelFrame(self, text="Log")
        frm5.pack(fill="both", expand=True, **pad)

        self._log = ScrolledText(
            frm5,
            height=10,
            state="disabled",
            font=("Verdana", 8),
            wrap="word",
            bg="#FAFAFA",
        )
        self._log.pack(fill="both", expand=True, padx=4, pady=4)

        # Tags de cor no log
        self._log.tag_config("ok",    foreground="#2E7D32")
        self._log.tag_config("erro",  foreground="#C62828")
        self._log.tag_config("info",  foreground="#1565C0")
        self._log.tag_config("normal", foreground="#222222")

        self.geometry("620x580")

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _selecionar_xml(self):
        path = filedialog.askopenfilename(
            title="Selecionar arquivo XML",
            filetypes=[("Arquivos XML", "*.xml"), ("Todos", "*.*")],
        )
        if not path:
            return

        self._xml_path.set(path)
        pasta = os.path.dirname(path)
        if not self._out_path.get():
            self._out_path.set(pasta)

        self._count_var.set("Carregando...")
        self._log_clear()
        self._log_append("Lendo XML...", "info")

        def _carregar():
            try:
                df = ler_xml(path)
                self._df = df
                msg = f"{len(df)} registros carregados"
                self.after(0, lambda: self._count_var.set(msg))
                self.after(0, lambda: self._log_append(msg, "ok"))
            except Exception as exc:
                self._df = None
                err = f"Erro ao ler XML: {exc}"
                self.after(0, lambda: self._count_var.set("Erro ao carregar."))
                self.after(0, lambda: self._log_append(err, "erro"))

        threading.Thread(target=_carregar, daemon=True).start()

    def _selecionar_pasta(self):
        pasta = filedialog.askdirectory(title="Selecionar pasta de saída")
        if pasta:
            self._out_path.set(pasta)

    def _validar_selecao(self):
        nenhum = not self._chk_geral.get() and not self._chk_ativos.get()
        self._btn_gerar.config(state="disabled" if nenhum else "normal")

    def _gerar(self):
        if self._df is None:
            self._log_append("Selecione um arquivo XML válido antes de gerar.", "erro")
            return
        pasta = self._out_path.get().strip()
        if not pasta:
            self._log_append("Informe a pasta de saída.", "erro")
            return
        if not self._chk_geral.get() and not self._chk_ativos.get():
            self._log_append("Selecione ao menos um relatório para gerar.", "erro")
            return

        geral = self._chk_geral.get()
        ativos = self._chk_ativos.get()

        self._btn_gerar.config(state="disabled", text="Processando...")
        self._log_clear()

        def _processar():
            try:
                def log(msg, tag="normal"):
                    self.after(0, lambda m=msg, t=tag: self._log_append(m, t))

                gerar_relatorios(self._df, pasta, log, gerar_geral=geral, gerar_ativos=ativos)
                self.after(
                    0,
                    lambda: self._log_append(
                        f"Concluído! Arquivos salvos em: {pasta}", "ok"
                    ),
                )
                self.after(0, lambda: self._abrir_pasta(pasta))
            except Exception as exc:
                self.after(0, lambda: self._log_append(f"Erro: {exc}", "erro"))
            finally:
                self.after(
                    0,
                    lambda: self._btn_gerar.config(state="normal", text="Gerar Relatórios"),
                )

        threading.Thread(target=_processar, daemon=True).start()

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
