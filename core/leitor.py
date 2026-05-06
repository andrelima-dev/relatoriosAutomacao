import xml.etree.ElementTree as ET
import pandas as pd

NS = "urn:schemas-microsoft-com:office:spreadsheet"
SS = f"{{{NS}}}ss"

_ns = {
    "ss": NS,
    "o":  "urn:schemas-microsoft-com:office:office",
    "x":  "urn:schemas-microsoft-com:office:excel",
    "html": "http://www.w3.org/TR/REC-html40",
}


def _cell_value(cell_el):
    data = cell_el.find("ss:Data", _ns)
    if data is None:
        return ""
    return (data.text or "").strip()


def _parse_row(row_el):
    return [_cell_value(c) for c in row_el.findall("ss:Cell", _ns)]


def ler_xml(caminho: str) -> pd.DataFrame:
    tree = ET.parse(caminho)
    root = tree.getroot()

    worksheet = root.find(".//ss:Worksheet", _ns)
    if worksheet is None:
        raise ValueError("Nenhuma planilha (Worksheet) encontrada no XML.")

    table = worksheet.find("ss:Table", _ns)
    if table is None:
        raise ValueError("Elemento Table não encontrado na planilha.")

    rows = table.findall("ss:Row", _ns)
    if len(rows) < 2:
        raise ValueError("O XML não contém linhas de dados suficientes.")

    # Linha 1 → título (ignorar), linha 2 → cabeçalhos, linha 3+ → dados
    headers = _parse_row(rows[1])

    records = []
    for row in rows[2:]:
        values = _parse_row(row)
        # Garantir que o número de colunas bate com os cabeçalhos
        if len(values) < len(headers):
            values += [""] * (len(headers) - len(values))
        elif len(values) > len(headers):
            values = values[: len(headers)]
        records.append(dict(zip(headers, values)))

    return pd.DataFrame(records)
