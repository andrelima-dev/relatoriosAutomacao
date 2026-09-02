"""Relatório executivo em PDF: capa, cards, gráficos de barras e adimplência."""

import os
from datetime import date, datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from core.utils import get_col, resource_path

# Paleta (validada em references/palette.md — categórica + status)
_AZUL = colors.HexColor("#1565C0")        # marca (cabeçalho)
_SERIE = colors.HexColor("#2a78d6")       # barras de magnitude (hue único)
_SERIE_CLARO = colors.HexColor("#cde2fb")
_VERDE = colors.HexColor("#0ca30c")       # status: adimplente
_VERMELHO = colors.HexColor("#d03b3b")    # status: inadimplente
_CINZA = colors.HexColor("#898781")       # não classificado / rótulos
_CINZA_CLARO = colors.HexColor("#F3F4F6")
_TEXTO = colors.HexColor("#111827")
_MUTED = colors.HexColor("#6B7280")

_LOGO = resource_path(os.path.join("assets", "logo.png"))

_MARGEM = 18 * mm
_LARGURA, _ALTURA = A4
_LARGURA_UTIL = _LARGURA - 2 * _MARGEM
_LINHA = 8 * mm  # altura de uma linha de gráfico de barras


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _elidir(texto: str, fonte: str, tamanho: float, largura_max: float) -> str:
    if stringWidth(texto, fonte, tamanho) <= largura_max:
        return texto
    while texto and stringWidth(texto + "…", fonte, tamanho) > largura_max:
        texto = texto[:-1]
    return texto + "…"


# ── Logo ─────────────────────────────────────────────────────────────────────

_logo_cache: object | None = None


def _logo_reader():
    """Logo recortada e reduzida a uma resolução de impressão.

    O PNG original tem ~2 MB; embutido cru ele domina o tamanho do PDF, então
    reduzimos a ~200 px de altura (bem acima dos 15 mm em que é desenhada)."""
    global _logo_cache
    if _logo_cache is not None:
        return _logo_cache or None
    if not os.path.isfile(_LOGO):
        _logo_cache = False
        return None
    try:
        from PIL import Image
        from reportlab.lib.utils import ImageReader

        img = Image.open(_LOGO).convert("RGBA")
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        img.thumbnail((600, 200), Image.LANCZOS)
        fundo = Image.new("RGB", img.size, (21, 101, 192))
        fundo.paste(img, mask=img.split()[3])
        _logo_cache = ImageReader(fundo)
        return _logo_cache
    except Exception:
        _logo_cache = False
        return None


def _desenhar_logo(c: canvas.Canvas, x: float, y: float, altura_max: float) -> float:
    img = _logo_reader()
    if img is None:
        return 0.0
    iw, ih = img.getSize()
    largura = altura_max * (iw / ih)
    c.drawImage(img, x, y, width=largura, height=altura_max)
    return largura


# ── Chrome (cabeçalho / rodapé) ──────────────────────────────────────────────

def _cabecalho(c: canvas.Canvas, titulo: str, subtitulo: str) -> float:
    c.setFillColor(_AZUL)
    c.rect(0, _ALTURA - 32 * mm, _LARGURA, 32 * mm, stroke=0, fill=1)

    largura_logo = _desenhar_logo(c, _MARGEM, _ALTURA - 24 * mm, 15 * mm)
    x_texto = _MARGEM + (largura_logo + 6 * mm if largura_logo else 0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(x_texto, _ALTURA - 16 * mm,
                 _elidir(titulo, "Helvetica-Bold", 15, _LARGURA - x_texto - _MARGEM))
    c.setFont("Helvetica", 8.5)
    c.drawString(x_texto, _ALTURA - 22 * mm, subtitulo)
    return _ALTURA - 44 * mm


def _rodape(c: canvas.Canvas):
    c.setStrokeColor(_CINZA_CLARO)
    c.setLineWidth(0.8)
    c.line(_MARGEM, 14 * mm, _LARGURA - _MARGEM, 14 * mm)
    c.setFillColor(_CINZA)
    c.setFont("Helvetica", 7)
    c.drawString(_MARGEM, 9 * mm, "Gerador de Relatórios OAB")
    c.drawRightString(_LARGURA - _MARGEM, 9 * mm,
                      datetime.now().strftime("Emitido em %d/%m/%Y às %H:%M"))


class _Pagina:
    """Cursor de escrita com quebra de página automática."""

    def __init__(self, c: canvas.Canvas, titulo: str):
        self.c = c
        self.titulo = titulo
        self.y = _cabecalho(c, titulo, date.today().strftime("Relatório gerado em %d/%m/%Y"))

    def espaco(self, altura: float):
        if self.y - altura < 22 * mm:
            _rodape(self.c)
            self.c.showPage()
            self.y = _cabecalho(self.c, self.titulo, "continuação")

    def titulo_secao(self, texto: str):
        self.espaco(16 * mm)
        self.c.setFillColor(_TEXTO)
        self.c.setFont("Helvetica-Bold", 11)
        self.c.drawString(_MARGEM, self.y, texto)
        self.y -= 7 * mm


# ── Cards ────────────────────────────────────────────────────────────────────

def _cards(c: canvas.Canvas, y: float, itens: list[tuple[str, str, bool]]) -> float:
    gap = 4 * mm
    w = (_LARGURA_UTIL - gap * (len(itens) - 1)) / len(itens)
    h = 22 * mm
    for i, (valor, rotulo, destaque) in enumerate(itens):
        x = _MARGEM + i * (w + gap)
        c.setFillColor(_SERIE_CLARO if destaque else _CINZA_CLARO)
        c.roundRect(x, y - h, w, h, 3 * mm, stroke=0, fill=1)

        c.setFillColor(_AZUL if destaque else _TEXTO)
        tam = 20
        while stringWidth(valor, "Helvetica-Bold", tam) > w - 8 * mm and tam > 9:
            tam -= 1
        c.setFont("Helvetica-Bold", tam)
        c.drawCentredString(x + w / 2, y - h + 10 * mm, valor)

        c.setFillColor(_MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(x + w / 2, y - h + 4 * mm,
                            _elidir(rotulo, "Helvetica", 7.5, w - 4 * mm))
    return y - h - 10 * mm


# ── Gráfico de barras horizontais (magnitude) ────────────────────────────────

def _bar_chart(pg: _Pagina, linhas: list[tuple[str, int]], total: int,
               tem_agregado: bool = False):
    """Barras horizontais proporcionais ao maior valor da série.

    Rótulo à esquerda, barra ao centro, quantidade + % à direita. A linha
    agregada ('Outros'), quando houver, fica em cinza e fora da escala."""
    c = pg.c
    escalaveis = linhas[:-1] if (tem_agregado and len(linhas) > 1) else linhas
    maior = max((q for _, q in escalaveis), default=0)

    lbl_w = 46 * mm
    val_x = _MARGEM + _LARGURA_UTIL - 22 * mm   # quantidade (bold)
    pct_x = _MARGEM + _LARGURA_UTIL              # percentual
    barra_x = _MARGEM + lbl_w
    barra_w_max = val_x - barra_x - 13 * mm

    for i, (rotulo, qtd) in enumerate(linhas):
        pg.espaco(_LINHA)
        y = pg.y
        agregada = tem_agregado and i == len(linhas) - 1

        c.setFillColor(_TEXTO)
        c.setFont("Helvetica", 8.5)
        c.drawString(_MARGEM, y, _elidir(rotulo, "Helvetica", 8.5, lbl_w - 3 * mm))

        if maior:
            w = max(barra_w_max * min(qtd / maior, 1.0), 0.8 * mm)
            c.setFillColor(_CINZA_CLARO if agregada else _SERIE)
            c.roundRect(barra_x, y - 1.2 * mm, w, 4.6 * mm, 1.2 * mm, stroke=0, fill=1)

        pct = (qtd / total * 100) if total else 0.0
        c.setFillColor(_TEXTO)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawRightString(val_x, y, _fmt_int(qtd))
        c.setFillColor(_MUTED)
        c.setFont("Helvetica", 8)
        c.drawRightString(pct_x, y, f"{pct:.1f}%")
        pg.y -= _LINHA

    pg.y -= 3 * mm


# ── Adimplência (meter) ──────────────────────────────────────────────────────

def _chip(c: canvas.Canvas, x: float, y: float, cor, texto: str) -> float:
    c.setFillColor(cor)
    c.roundRect(x, y - 0.3 * mm, 3 * mm, 3 * mm, 0.6 * mm, stroke=0, fill=1)
    c.setFillColor(_MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(x + 4.2 * mm, y, texto)
    return x + 4.2 * mm + stringWidth(texto, "Helvetica", 8) + 7 * mm


def _meter(pg: _Pagina, n_adim: int, n_inad: int, n_outro: int):
    c = pg.c
    total = n_adim + n_inad + n_outro
    base = n_adim + n_inad
    pct_adim = (n_adim / base * 100) if base else 0.0

    pg.espaco(28 * mm)
    y = pg.y

    # Headline
    c.setFillColor(_VERDE)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(_MARGEM, y - 7 * mm, f"{pct_adim:.1f}%")
    c.setFillColor(_MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(_MARGEM + stringWidth(f'{pct_adim:.1f}%', 'Helvetica-Bold', 22) + 4 * mm,
                 y - 6 * mm, "adimplentes")

    # Barra proporcional (meter), com 1.4mm de folga entre segmentos
    by = y - 16 * mm
    h = 8 * mm
    gap = 1.4 * mm
    segmentos = [(n_adim, _VERDE), (n_inad, _VERMELHO)]
    if n_outro:
        segmentos.append((n_outro, _CINZA))
    x = _MARGEM
    for val, cor in segmentos:
        seg_w = (_LARGURA_UTIL * val / total) if total else 0
        if seg_w <= 0:
            continue
        c.setFillColor(cor)
        c.rect(x, by, max(seg_w - gap, 0.5 * mm), h, stroke=0, fill=1)
        # rótulo dentro do segmento, se couber
        rot = f"{_fmt_int(val)} ({val / total * 100:.0f}%)" if total else ""
        if stringWidth(rot, "Helvetica-Bold", 8) < seg_w - 4 * mm:
            c.setFillColorRGB(1, 1, 1)
            c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(x + seg_w / 2, by + h / 2 - 1.1 * mm, rot)
        x += seg_w

    # Legenda
    ly = by - 6 * mm
    x = _chip(c, _MARGEM, ly, _VERDE, f"Adimplentes  {_fmt_int(n_adim)}")
    x = _chip(c, x, ly, _VERMELHO, f"Inadimplentes  {_fmt_int(n_inad)}")
    if n_outro:
        _chip(c, x, ly, _CINZA, f"Não classificados  {_fmt_int(n_outro)}")
    pg.y = ly - 8 * mm


# ── Agregações ───────────────────────────────────────────────────────────────

def _contagem(df: pd.DataFrame, nome_col: str,
              limite: int = 12) -> tuple[list[tuple[str, int]], bool]:
    col = get_col(df, nome_col)
    if col is None or df.empty:
        return [], False
    serie = df[col].astype(str).str.strip().replace("", "(não informado)")
    contagem = serie.value_counts()
    principais = [(str(k), int(v)) for k, v in contagem.head(limite).items()]
    resto = int(contagem.iloc[limite:].sum())
    if resto:
        principais.append((f"Outros ({len(contagem) - limite})", resto))
        return principais, True
    return principais, False


def _n_distintos(df: pd.DataFrame, nome_col: str) -> int:
    col = get_col(df, nome_col)
    if col is None or df.empty:
        return 0
    return int(df[col].astype(str).str.strip().replace("", "(não informado)").nunique())


def _classificar_adimplencia(df, cfg) -> tuple[int, int, int] | None:
    col = get_col(df, cfg["col"])
    if col is None:
        return None
    serie = df[col].astype(str).str.strip().str.upper()
    adim = {str(v).strip().upper() for v in cfg.get("adimplente", [])}
    inad = {str(v).strip().upper() for v in cfg.get("inadimplente", [])}
    n_adim = int(serie.isin(adim).sum())
    n_inad = int(serie.isin(inad).sum())
    return n_adim, n_inad, len(serie) - n_adim - n_inad


# ── Documento ────────────────────────────────────────────────────────────────

def gerar_pdf(df: pd.DataFrame, caminho: str, titulo: str,
              filtros: list[str] | None = None, adimplencia: dict | None = None) -> str:
    c = canvas.Canvas(caminho, pagesize=A4, pageCompression=1)
    c.setTitle(titulo)
    total = len(df)
    pg = _Pagina(c, titulo)

    col_sub = "UF" if get_col(df, "UF") is not None else "SUBSECAO"
    pg.y = _cards(c, pg.y, [
        (_fmt_int(total), "TOTAL DE REGISTROS", True),
        (_fmt_int(_n_distintos(df, "CATEGORIA")), "CATEGORIAS", False),
        (_fmt_int(_n_distintos(df, "SITUACAO_INSCRICAO")), "SITUAÇÕES", False),
        (_fmt_int(_n_distintos(df, col_sub)), "SUBSEÇÕES", False),
    ])

    if filtros:
        pg.titulo_secao("Filtros aplicados")
        c.setFillColor(_MUTED)
        c.setFont("Helvetica", 8)
        for f in filtros:
            pg.espaco(5 * mm)
            c.setFillColor(_MUTED)
            c.setFont("Helvetica", 8)
            c.drawString(_MARGEM + 2 * mm, pg.y,
                         _elidir(f"• {f}", "Helvetica", 8, _LARGURA_UTIL - 4 * mm))
            pg.y -= 4.6 * mm
        pg.y -= 5 * mm

    # Adimplência primeiro — é o recorte que o usuário configurou explicitamente
    if adimplencia:
        cls = _classificar_adimplencia(df, adimplencia)
        if cls and (cls[0] or cls[1]):
            pg.titulo_secao("Adimplência")
            _meter(pg, *cls)

    for titulo_tab, nome_col, lim in (
        ("Distribuição por categoria", "CATEGORIA", 12),
        ("Distribuição por situação de inscrição", "SITUACAO_INSCRICAO", 12),
        ("Maiores subseções", col_sub, 10),
    ):
        linhas, agregou = _contagem(df, nome_col, lim)
        if not linhas:
            continue
        pg.titulo_secao(titulo_tab)
        _bar_chart(pg, linhas, total, agregou)

    if total == 0:
        c.setFillColor(_MUTED)
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(_MARGEM, pg.y, "Nenhum registro corresponde aos filtros selecionados.")

    _rodape(c)
    c.save()
    return caminho


def salvar_pdf(df: pd.DataFrame, pasta_saida: str, nome_base: str, sufixo: str,
               titulo: str, filtros: list[str] | None, log_cb,
               adimplencia: dict | None = None) -> str:
    """Salva o PDF; se o arquivo estiver aberto, usa um nome alternativo."""
    os.makedirs(pasta_saida, exist_ok=True)
    hoje = date.today().strftime("%d-%m-%Y")
    base = os.path.join(pasta_saida, f"{nome_base}{sufixo} {hoje}")

    try:
        return gerar_pdf(df, f"{base}.pdf", titulo, filtros, adimplencia)
    except PermissionError:
        for i in range(2, 100):
            try:
                path = gerar_pdf(df, f"{base} ({i}).pdf", titulo, filtros, adimplencia)
                log_cb(f"PDF já aberto — salvo como '{os.path.basename(path)}'.", "info")
                return path
            except PermissionError:
                continue
        raise PermissionError(
            f"Não foi possível salvar o PDF '{os.path.basename(base)}.pdf'. "
            f"Feche o arquivo e gere novamente."
        )
