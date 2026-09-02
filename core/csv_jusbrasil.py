"""Exportação no layout de importação do Jusbrasil.

São 6 colunas, com cabeçalho acentuado e em maiúsculas/minúsculas exatas —
o importador casa pelo texto do cabeçalho, então ele não pode ser normalizado.
Diferente do layout OAB PREV, aqui o CPF vai **com máscara** (000.000.000-00).

A resolução de colunas de origem é a mesma usada na exportação OAB PREV
(`achar_coluna`), já que o arquivo de origem é o mesmo.
"""

import os
from datetime import date
from typing import Callable

import pandas as pd

from core.csv_oabma import _data, _digitos, _texto, achar_coluna
from core.gerador import aplicar_filtro_data, filtrar_ativos, normalizar_filtros

# Ordem e grafia exatas do modelo do Jusbrasil
COLUNAS_JUSBRASIL = [
    "Nome completo",
    "E-mail",
    "CPF",
    "Data de nascimento",
    "Nº da OAB",
    "Data de inscrição na OAB",
]

# campo -> (candidatos exatos por ordem, termos aceitos por aproximação,
#           termos que desqualificam a coluna)
_ORIGENS: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "Nome completo": (
        ("NOME", "NOME_ADVOGADO", "NM_ADVOGADO", "NOME_COMPLETO", "NOME_INSCRITO"),
        ("NOME",),
        ("SUBSEC", "SECCIONAL", "MAE", "PAI", "MUN", "CIDADE", "BAIRRO",
         "LOGR", "SOCIAL", "ARQUIV"),
    ),
    "E-mail": (
        ("EMAIL", "E_MAIL", "EMAIL_RES", "ENDERECO_EMAIL"),
        ("EMAIL", "E_MAIL"),
        ("_COM", "COMERC"),
    ),
    "CPF": (
        ("CPF", "NUM_CPF", "CPF_CNPJ", "NR_CPF"),
        ("CPF",),
        (),
    ),
    "Data de nascimento": (
        ("DATA_NASCIMENTO", "DT_NASCIMENTO", "NASCIMENTO", "DT_NASC",
         "DATA_NASC"),
        ("NASC",),
        (),
    ),
    "Nº da OAB": (
        ("INSCRICAO", "NUM_INSCRICAO", "NUMERO_INSCRICAO", "NUM_OAB",
         "REGISTRO", "NUM_REGISTRO", "MATRICULA"),
        ("INSCRICAO", "REGISTRO"),
        ("TIPO", "SITUAC", "DATA", "DT_", "CATEG", "SUBSEC"),
    ),
    "Data de inscrição na OAB": (
        ("DATA_INSCRICAO", "DT_INSCRICAO", "DATA_COMPROMISSO",
         "DT_COMPROMISSO", "COMPROMISSO"),
        ("COMPROMISSO", "INSCRICAO"),
        ("NASC", "TIPO", "SITUAC", "NUM", "CATEG"),
    ),
}


def _cpf_mascarado(v) -> str:
    """000.000.000-00. Sem 11 dígitos, devolve o que houver — melhor entregar
    o dado cru do que uma máscara inventada."""
    d = _digitos(v, 11)
    if len(d) != 11:
        return d
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


_NORMALIZADORES: dict[str, Callable[[object], str]] = {
    "CPF": _cpf_mascarado,
    "Data de nascimento": _data,
    "Nº da OAB": lambda v: _digitos(v),
    "Data de inscrição na OAB": _data,
}


def mapear_para_jusbrasil(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[tuple[str, str | None]]]:
    """Converte o df de origem no layout do Jusbrasil.

    Devolve (df_no_layout, mapeamento), onde mapeamento lista cada campo e a
    coluna de origem usada (None quando o campo não pôde ser preenchido).
    """
    saida = pd.DataFrame(index=df.index)
    mapeamento: list[tuple[str, str | None]] = []

    for campo in COLUNAS_JUSBRASIL:
        col = achar_coluna(df, *_ORIGENS[campo])
        if col is None:
            saida[campo] = ""
            mapeamento.append((campo, None))
            continue
        norm = _NORMALIZADORES.get(campo, _texto)
        saida[campo] = df[col].map(norm)
        mapeamento.append((campo, col))

    return saida[COLUNAS_JUSBRASIL], mapeamento


def _nome_csv(nome_base: str) -> str:
    hoje = date.today().strftime("%d-%m-%Y")
    return f"{nome_base} JUSBRASIL {hoje}.csv"


def _salvar_csv(df: pd.DataFrame, path: str,
                log_cb: Callable[[str, str], None]) -> str:
    """Salva o CSV; se o arquivo estiver aberto/bloqueado, usa nome alternativo
    em vez de quebrar a geração (mesma política dos .xlsx)."""
    def escrever(destino: str):
        df.to_csv(destino, index=False, sep=",", encoding="utf-8",
                  lineterminator="\n")

    try:
        escrever(path)
        return path
    except PermissionError:
        base, ext = os.path.splitext(path)
        for i in range(2, 100):
            alt = f"{base} ({i}){ext}"
            try:
                escrever(alt)
                log_cb(
                    f"'{os.path.basename(path)}' estava aberto — salvo como "
                    f"'{os.path.basename(alt)}'.",
                    "info",
                )
                return alt
            except PermissionError:
                continue
        raise PermissionError(
            f"Não foi possível salvar '{os.path.basename(path)}'. "
            f"Feche o arquivo e gere novamente."
        )


def exportar_csv_jusbrasil(
    df: pd.DataFrame,
    pasta_saida: str,
    log_cb: Callable[[str, str], None],
    base: str = "ativos",
    categorias_filtro: set[str] | None = None,
    situacoes_filtro: set[str] | None = None,
    data_col: str | None = None,
    data_inicio=None,
    data_fim=None,
    nome_base: str = "RELATORIO CADASTRO ADVOGADOS GERAL",
    progress_cb: Callable[[int], None] | None = None,
) -> str:
    """Gera o CSV no layout do Jusbrasil e devolve o caminho salvo."""
    os.makedirs(pasta_saida, exist_ok=True)
    if progress_cb:
        progress_cb(5)

    log_cb("Gerando CSV de importação (Jusbrasil)...", "info")

    df_base = aplicar_filtro_data(df, data_col, data_inicio, data_fim)
    if base == "ativos":
        cats, sits = normalizar_filtros(categorias_filtro, situacoes_filtro)
        df_base = filtrar_ativos(df_base, cats, sits, obrigatorio=True)
    if progress_cb:
        progress_cb(30)

    df_csv, mapeamento = mapear_para_jusbrasil(df_base)
    if progress_cb:
        progress_cb(70)

    usados = [f"{campo} ← {col}" for campo, col in mapeamento if col]
    vazios = [campo for campo, col in mapeamento if not col]
    log_cb(f"Mapeamento: {'; '.join(usados)}", "normal")
    if vazios:
        log_cb(
            f"Sem origem no arquivo, saíram em branco: {', '.join(vazios)}. "
            f"Preencha no CSV antes de importar, se o Jusbrasil exigir.",
            "erro",
        )

    path = _salvar_csv(df_csv, os.path.join(pasta_saida, _nome_csv(nome_base)),
                       log_cb)
    log_cb(
        f"Gerando CSV de importação (Jusbrasil)... ✔ ({len(df_csv)} registros, "
        f"{len(COLUNAS_JUSBRASIL)} colunas)",
        "ok",
    )
    if progress_cb:
        progress_cb(100)
    return path
