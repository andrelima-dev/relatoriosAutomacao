import os
from datetime import date, datetime
from typing import Callable

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Border, Side, Alignment, numbers
from openpyxl.utils import get_column_letter

ABA_NOME = "Planilha1"

CATEGORIAS_ATIVAS = {"ADVOGADO", "SUPLEMENTAR"}
SITUACOES_ATIVAS = {
    "ATIVO COM IMPEDIMENTO",
    "ATIVO PLENO",
    "EXECUTADO",
    "SUSPENSO EM OUTRA SECCIONAL",
    "SUSPENSO POR PROCESSO",
}

_thin = Side(style="thin")
_border = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
_font_header = Font(name="Verdana", size=8, bold=True)
_font_data = Font(name="Verdana", size=8)


_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%Y/%m/%d",
)


def _parse_date(value: str):
    """Tenta converter string para datetime; retorna None se não conseguir."""
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def _is_date_col(col_name: str) -> bool:
    upper = col_name.strip().upper()
    return upper.startswith("DATA") or upper.endswith("_DATA") or "DATA_" in upper


def _escrever_planilha(ws, df: pd.DataFrame):
    date_cols = {i for i, c in enumerate(df.columns) if _is_date_col(c)}

    # Cabeçalhos
    for col_idx, col_name in enumerate(df.columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = _font_header
        cell.border = _border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Dados
    for row_idx, row in enumerate(df.itertuples(index=False), start=2):
        for col_idx, value in enumerate(row, start=1):
            if col_idx - 1 in date_cols:
                parsed = _parse_date(value)
                cell = ws.cell(row=row_idx, column=col_idx, value=parsed if parsed else value)
                if parsed:
                    cell.number_format = "DD/MM/YYYY"
            else:
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = _font_data
            cell.border = _border
            cell.alignment = Alignment(vertical="center")

    # Ajuste automático de largura de coluna (estimativa)
    for col_idx, col_name in enumerate(df.columns, start=1):
        col_letter = get_column_letter(col_idx)
        max_len = max(
            len(str(col_name)),
            *(len(str(v)) for v in df.iloc[:, col_idx - 1]),
            0,
        )
        ws.column_dimensions[col_letter].width = min(max_len + 2, 50)


def _nome_arquivo(sufixo: str) -> str:
    hoje = date.today().strftime("%d-%m-%Y")
    return f"RELATORIO CADASTRO ADVOGADOS GERAL{sufixo} {hoje}.xlsx"


def gerar_relatorios(
    df: pd.DataFrame,
    pasta_saida: str,
    log_cb: Callable[[str, str], None],
    gerar_geral: bool = True,
    gerar_ativos: bool = True,
) -> tuple[str | None, str | None]:
    """
    Gera os arquivos xlsx selecionados.
    Retorna (caminho_geral, caminho_ativos); None para os não gerados.
    """
    os.makedirs(pasta_saida, exist_ok=True)

    path_geral = None
    path_ativos = None

    # ── GERAL ────────────────────────────────────────────────────────────────
    if gerar_geral:
        log_cb("Gerando GERAL...", "info")
        path_geral = os.path.join(pasta_saida, _nome_arquivo(""))
        wb = Workbook()
        ws = wb.active
        ws.title = ABA_NOME
        _escrever_planilha(ws, df)
        wb.save(path_geral)
        log_cb(f"Gerando GERAL... ✔ ({len(df)} registros)", "ok")

    # ── GERAL ATIVOS ─────────────────────────────────────────────────────────
    if gerar_ativos:
        log_cb("Gerando GERAL ATIVOS...", "info")

        col_cat = _coluna(df, "CATEGORIA")
        col_sit = _coluna(df, "SITUACAO_INSCRICAO")

        if col_cat is None:
            raise ValueError("Coluna 'CATEGORIA' não encontrada no XML.")
        if col_sit is None:
            raise ValueError("Coluna 'SITUACAO_INSCRICAO' não encontrada no XML.")

        mask = (
            df[col_cat].str.strip().str.upper().isin(CATEGORIAS_ATIVAS)
            & df[col_sit].str.strip().str.upper().isin(SITUACOES_ATIVAS)
        )
        df_ativos = df[mask].reset_index(drop=True)

        path_ativos = os.path.join(pasta_saida, _nome_arquivo(" ATIVOS"))
        wb = Workbook()
        ws = wb.active
        ws.title = ABA_NOME
        _escrever_planilha(ws, df_ativos)
        wb.save(path_ativos)
        log_cb(f"Gerando GERAL ATIVOS... ✔ ({len(df_ativos)} registros)", "ok")

    return path_geral, path_ativos


def _coluna(df: pd.DataFrame, nome: str):
    """Busca coluna ignorando maiúsculas/minúsculas e espaços extras."""
    for c in df.columns:
        if c.strip().upper() == nome.upper():
            return c
    return None
