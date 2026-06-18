import os
import re
import zipfile
from datetime import date

_MESES_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

_DATE_PATTERN = re.compile(r"Data \d{1,2} de \w+ de \d{4}")


def _data_hoje_pt(d: date | None = None) -> str:
    d = d or date.today()
    return f"Data {d.day} de {_MESES_PT[d.month]} de {d.year}"


def atualizar_pbix(
    template_path: str,
    pasta_saida: str,
    nome_saida: str | None = None,
    data: date | None = None,
) -> str:
    """Copia o .pbix atualizando a data no título e salva com nome datado.

    Retorna o caminho do arquivo gerado.
    """
    d = data or date.today()
    nova_data_texto = _data_hoje_pt(d)

    if nome_saida is None:
        base = os.path.splitext(os.path.basename(template_path))[0]
        nome_saida = f"{d.strftime('%d-%m-%Y')} {base}.pbix"

    os.makedirs(pasta_saida, exist_ok=True)
    dest = os.path.join(pasta_saida, nome_saida)

    # Repack ZIP preservando todos os arquivos; só modifica Report/Layout
    with zipfile.ZipFile(template_path, "r") as zin, \
         zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data_bytes = zin.read(item.filename)
            if item.filename == "Report/Layout":
                data_bytes = _substituir_data_layout(data_bytes, nova_data_texto)
            zout.writestr(item, data_bytes)

    return dest


def _substituir_data_layout(raw: bytes, nova_data: str) -> bytes:
    try:
        text = raw.decode("utf-16-le")
    except UnicodeDecodeError:
        return raw

    novo_texto, n = _DATE_PATTERN.subn(nova_data, text)
    if n == 0:
        return raw
    return novo_texto.encode("utf-16-le")
