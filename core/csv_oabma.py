"""Exportação no layout de importação do sistema OAB PREV.

O arquivo de origem (XML/Excel da OAB) não tem nomes de coluna fixos, então
cada um dos 20 campos do layout é resolvido por uma lista de candidatos e, se
necessário, por busca aproximada — mesma abordagem já usada na detecção de
subseção e de adimplência em app.py. Campos sem origem no arquivo saem vazios
e são reportados no log, em vez de receberem um valor inventado.
"""

import os
import re
from datetime import date
from typing import Callable

import pandas as pd

from core.gerador import (
    _parse_date,
    aplicar_filtro_data,
    filtrar_ativos,
    normalizar_filtros,
)

# Ordem e grafia exatas esperadas pelo importador da OAB PREV
COLUNAS_OABMA = [
    "nome", "registro", "categoria", "subsecao", "tipoInscricao",
    "cpf", "sexo", "adimplente", "logradouro", "bairro",
    "cidade", "uf", "cep", "dataCompromisso", "jovenAdvogado",
    "email", "telefone", "celular", "dataNascimento", "situacao",
]

# campo -> (candidatos exatos por ordem, termos aceitos por aproximação,
#           termos que desqualificam a coluna)
_ORIGENS: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "nome": (
        ("NOME", "NOME_ADVOGADO", "NM_ADVOGADO", "NOME_COMPLETO", "NOME_INSCRITO"),
        ("NOME",),
        ("SUBSEC", "SECCIONAL", "MAE", "PAI", "MUN", "CIDADE", "BAIRRO",
         "LOGR", "SOCIAL", "ARQUIV"),
    ),
    "registro": (
        ("INSCRICAO", "NUM_INSCRICAO", "NUMERO_INSCRICAO", "NUM_OAB",
         "REGISTRO", "NUM_REGISTRO", "MATRICULA"),
        ("INSCRICAO", "REGISTRO"),
        ("TIPO", "SITUAC", "DATA", "DT_", "CATEG", "SUBSEC"),
    ),
    "categoria": (
        ("CATEGORIA", "CATEGORIA_INSCRICAO", "DESC_CATEGORIA"),
        ("CATEG",),
        (),
    ),
    # Estes três a tela normalmente já detecta e passa prontos; a lista abaixo
    # é o retorno para quando a detecção não achou nada.
    "subsecao": (
        ("SUBSECAO", "SUBSEÇÃO", "SUB_SECAO", "SECCIONAL", "NM_SECCIONAL",
         "DESCRICAO_SECCIONAL", "NOME_SUBSECAO", "SUBSECAO_INSCRICAO"),
        ("SUBSEC", "SECCIONAL"),
        ("BAIRRO", "LOGR", "CEP", "FONE", "EMAIL", "CPF", "NASC", "SEXO",
         "SITUAC", "CATEG", "TITULO"),
    ),
    "cidade": (
        ("MUN_RES", "MUNICIPIO_RES", "MUNICIPIO", "MUNICÍPIO", "CIDADE",
         "MUN_COMARCA", "MUNICIPIO_COMARCA"),
        ("MUNIC", "CIDADE"),
        ("_COM", "COMERC", "NASC", "SUBSEC", "SECCIONAL"),
    ),
    "adimplente": (
        ("SIT_FIN_ATUAL", "SITUACAO_FIN_ATUAL", "SIT_FIN", "ADIMPLENCIA",
         "ADIMPLÊNCIA", "SITUACAO_FINANCEIRA", "SITUACAO_FINANCEIRA_INSCRICAO",
         "SIT_FINANCEIRA", "ANUIDADE", "STATUS_FINANCEIRO"),
        # "FIN" sozinho casaria com DEFINITIVO (TIPO_INSCRICAO)
        ("ADIMPL", "FINANC", "ANUIDADE", "SIT_FIN", "FIN_ATUAL", "SITUACAO_FIN"),
        (),
    ),
    "tipoInscricao": (
        ("TIPO_INSCRICAO", "TIPOINSCRICAO", "TIPO_INSC", "TIPO"),
        ("TIPO_INSC", "TIPOINSC"),
        ("SITUAC", "DATA", "DT_"),
    ),
    "cpf": (
        ("CPF", "NUM_CPF", "CPF_CNPJ", "NR_CPF"),
        ("CPF",),
        (),
    ),
    "sexo": (
        ("SEXO", "GENERO", "SEXO_INSCRITO"),
        ("SEXO", "GENERO"),
        (),
    ),
    "logradouro": (
        ("LOGRADOURO", "END_RES", "ENDERECO_RES", "LOGR_RES", "ENDERECO",
         "LOGRADOURO_RES"),
        ("LOGR", "ENDERECO"),
        ("_COM", "COMERC", "NUM", "COMPL", "CEP", "BAIRRO"),
    ),
    "bairro": (
        ("BAIRRO", "BAIRRO_RES", "NM_BAIRRO"),
        ("BAIRRO",),
        ("_COM", "COMERC"),
    ),
    "uf": (
        ("UF_RES", "UF", "ESTADO", "SIGLA_UF", "UF_ENDERECO"),
        ("UF", "ESTADO"),
        ("SUBSEC", "SECCIONAL", "_COM", "COMERC", "NASC"),
    ),
    "cep": (
        ("CEP", "CEP_RES", "NUM_CEP"),
        ("CEP",),
        ("_COM", "COMERC"),
    ),
    "dataCompromisso": (
        ("DATA_COMPROMISSO", "DT_COMPROMISSO", "COMPROMISSO",
         "DATA_INSCRICAO", "DT_INSCRICAO"),
        ("COMPROMISSO",),
        ("NASC",),
    ),
    "jovenAdvogado": (
        ("JOVEM_ADVOGADO", "JOVENADVOGADO", "JOVEN_ADVOGADO", "JOVEM"),
        ("JOVEM", "JOVEN"),
        (),
    ),
    "email": (
        ("EMAIL", "E_MAIL", "EMAIL_RES", "ENDERECO_EMAIL"),
        ("EMAIL", "E_MAIL"),
        ("_COM", "COMERC"),
    ),
    "telefone": (
        ("TELEFONE", "FONE_RES", "TELEFONE_RES", "TEL_RES", "FONE"),
        ("FONE", "TELEFONE"),
        ("CEL",),
    ),
    "celular": (
        ("CELULAR", "FONE_CEL", "TEL_CEL", "CEL"),
        ("CEL",),
        (),
    ),
    "dataNascimento": (
        ("DATA_NASCIMENTO", "DT_NASCIMENTO", "NASCIMENTO", "DT_NASC",
         "DATA_NASC"),
        ("NASC",),
        (),
    ),
    "situacao": (
        ("SITUACAO_INSCRICAO", "SITUACAO", "SIT_INSCRICAO", "DESC_SITUACAO"),
        ("SITUAC",),
        ("FINANC", "ADIMPL", "ANUIDADE"),
    ),
}

_TOKENS_INADIMPLENTE = ("INADIMPL", "ATRASO", "DEVEDOR", "DEBITO", "DÉBITO",
                        "PENDENTE", "VENCID")
_TOKENS_ADIMPLENTE = ("ADIMPL", "REGULAR", "QUITE", "EM DIA", "QUITADO", "PAGO")
_TOKENS_SIM = ("SIM", "S", "TRUE", "1", "X", "VERDADEIRO")

# Jovem advogado: recorte por data de compromisso. O padrão são os últimos
# 5 anos contados do ano corrente (em 2026, de 01/01/2021 a 31/12/2026).
ANOS_JOVEM_PADRAO = 5


def periodo_jovem_padrao(anos: int = ANOS_JOVEM_PADRAO) -> tuple[date, date]:
    """De 1º de janeiro de (ano atual - anos) até o fim do ano atual."""
    ano = date.today().year
    return date(ano - anos, 1, 1), date(ano, 12, 31)


def achar_coluna(df: pd.DataFrame, exatos: tuple[str, ...],
                 contem: tuple[str, ...] = (),
                 evitar: tuple[str, ...] = ()) -> str | None:
    """Resolve uma coluna: primeiro por nome exato, depois por aproximação,
    pulando as que contenham termos desqualificantes.

    Também usada pela exportação Jusbrasil (core/csv_jusbrasil.py)."""
    cols_upper = {str(c).strip().upper(): c for c in df.columns}

    for nome in exatos:
        if nome in cols_upper:
            return cols_upper[nome]

    for upper, original in cols_upper.items():
        if any(e in upper for e in evitar):
            continue
        if any(t in upper for t in contem):
            return original
    return None


def _achar_col(df: pd.DataFrame, campo: str) -> str | None:
    return achar_coluna(df, *_ORIGENS[campo])


def _texto(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _digitos(v, tamanho: int | None = None) -> str:
    d = re.sub(r"\D", "", _texto(v))
    if tamanho and 0 < len(d) < tamanho:
        d = d.zfill(tamanho)
    return d


def _data(v) -> str:
    dt = _parse_date(_texto(v))
    return dt.strftime("%d/%m/%Y") if dt else ""


def _sexo(v) -> str:
    u = _texto(v).upper()
    if u.startswith("M"):
        return "M"
    if u.startswith("F"):
        return "F"
    return ""


def _sim_nao(v) -> str:
    u = _texto(v).upper()
    if not u:
        return ""
    return "sim" if u in _TOKENS_SIM or u.startswith("SIM") else "nao"


def _fazer_adimplente(adimp: set[str], inad: set[str]) -> Callable[[object], str]:
    """Classificador de adimplência: usa os valores já classificados na tela e,
    fora deles, recai nos termos usuais da coluna financeira."""
    def classificar(v) -> str:
        u = _texto(v).upper()
        if not u:
            return ""
        if u in adimp:
            return "sim"
        if u in inad:
            return "nao"
        if any(t in u for t in _TOKENS_INADIMPLENTE):
            return "nao"
        if any(t in u for t in _TOKENS_ADIMPLENTE):
            return "sim"
        return ""
    return classificar


def _fazer_jovem(desde: date | None, ate: date | None) -> Callable[[object], str]:
    """Jovem advogado = compromisso dentro do período. Data ilegível fica
    em branco, para não afirmar "nao" sem base."""
    def classificar(v) -> str:
        dt = _parse_date(_texto(v))
        if dt is None:
            return ""
        d = dt.date()
        if (desde and d < desde) or (ate and d > ate):
            return "nao"
        return "sim"
    return classificar


_NORMALIZADORES: dict[str, Callable[[object], str]] = {
    "registro": lambda v: _digitos(v),
    "cpf": lambda v: _digitos(v, 11),
    "cep": lambda v: _digitos(v, 8),
    "telefone": lambda v: _digitos(v),
    "celular": lambda v: _digitos(v),
    "sexo": _sexo,
    "dataCompromisso": _data,
    "dataNascimento": _data,
    "jovenAdvogado": _sim_nao,
}


def mapear_para_oabma(
    df: pd.DataFrame,
    col_subsecao: str | None = None,
    col_cidade: str | None = None,
    col_adimplencia: str | None = None,
    valores_adimplente: list[str] | None = None,
    valores_inadimplente: list[str] | None = None,
    jovem_desde: date | None = None,
    jovem_ate: date | None = None,
) -> tuple[pd.DataFrame, list[tuple[str, str | None]]]:
    """Converte o df de origem no layout OAB PREV.

    Devolve (df_no_layout, mapeamento), onde mapeamento lista cada campo e a
    origem usada (None quando o campo não pôde ser preenchido).
    """
    # Colunas que a tela já detecta são passadas prontas; o resto é procurado
    fixas = {
        "subsecao": col_subsecao,
        "cidade": col_cidade,
        "adimplente": col_adimplencia,
    }

    if jovem_desde is None and jovem_ate is None:
        jovem_desde, jovem_ate = periodo_jovem_padrao()
    col_compromisso = _achar_col(df, "dataCompromisso")
    classificar_jovem = _fazer_jovem(jovem_desde, jovem_ate)

    adimp = {str(v).strip().upper() for v in (valores_adimplente or [])}
    inad = {str(v).strip().upper() for v in (valores_inadimplente or [])}
    classificar_adimplente = _fazer_adimplente(adimp, inad)

    saida = pd.DataFrame(index=df.index)
    mapeamento: list[tuple[str, str | None]] = []

    for campo in COLUNAS_OABMA:
        # Jovem advogado é calculado do compromisso, não copiado de uma coluna
        if campo == "jovenAdvogado":
            if col_compromisso is None:
                saida[campo] = ""
                mapeamento.append((campo, None))
            else:
                saida[campo] = df[col_compromisso].map(classificar_jovem)
                mapeamento.append((campo, "calculado de %s  (compromisso de %s a %s)"
                                   % (col_compromisso,
                                      jovem_desde.strftime("%d/%m/%Y"),
                                      jovem_ate.strftime("%d/%m/%Y"))))
            continue

        col = fixas.get(campo) or _achar_col(df, campo)
        if col is not None and col not in df.columns:
            col = None

        if col is None:
            saida[campo] = ""
            mapeamento.append((campo, None))
            continue

        if campo == "adimplente":
            norm = classificar_adimplente
        else:
            norm = _NORMALIZADORES.get(campo, _texto)
        saida[campo] = df[col].map(norm)
        mapeamento.append((campo, col))

    return saida[COLUNAS_OABMA], mapeamento


def _nome_csv(nome_base: str) -> str:
    hoje = date.today().strftime("%d-%m-%Y")
    return f"{nome_base} IMPORTACAO OAB PREV {hoje}.csv"


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


def exportar_csv_oabma(
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
    col_subsecao: str | None = None,
    col_cidade: str | None = None,
    col_adimplencia: str | None = None,
    valores_adimplente: list[str] | None = None,
    valores_inadimplente: list[str] | None = None,
    jovem_desde: date | None = None,
    jovem_ate: date | None = None,
    progress_cb: Callable[[int], None] | None = None,
) -> str:
    """Gera o CSV no layout de importação da OAB PREV e devolve o caminho salvo."""
    os.makedirs(pasta_saida, exist_ok=True)
    if progress_cb:
        progress_cb(5)

    log_cb("Gerando CSV de importação (OAB PREV)...", "info")

    df_base = aplicar_filtro_data(df, data_col, data_inicio, data_fim)
    if base == "ativos":
        cats, sits = normalizar_filtros(categorias_filtro, situacoes_filtro)
        df_base = filtrar_ativos(df_base, cats, sits, obrigatorio=True)
    if progress_cb:
        progress_cb(30)

    df_csv, mapeamento = mapear_para_oabma(
        df_base, col_subsecao, col_cidade, col_adimplencia,
        valores_adimplente, valores_inadimplente, jovem_desde, jovem_ate,
    )
    if progress_cb:
        progress_cb(70)

    usados = [f"{campo} ← {col}" for campo, col in mapeamento if col]
    vazios = [campo for campo, col in mapeamento if not col]
    log_cb(f"Mapeamento: {'; '.join(usados)}", "normal")
    if vazios:
        log_cb(
            f"Sem origem no arquivo, saíram em branco: {', '.join(vazios)}. "
            f"Preencha no CSV antes de importar, se o sistema exigir.",
            "erro",
        )

    path = _salvar_csv(df_csv, os.path.join(pasta_saida, _nome_csv(nome_base)), log_cb)
    log_cb(
        f"Gerando CSV de importação (OAB PREV)... ✔ ({len(df_csv)} registros, "
        f"{len(COLUNAS_OABMA)} colunas)",
        "ok",
    )
    if progress_cb:
        progress_cb(100)
    return path
