import os
import xml.etree.ElementTree as ET
import pandas as pd

NS = "urn:schemas-microsoft-com:office:spreadsheet"
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


def carregar_planilha(
    caminho: str,
    worksheet_idx: int = 0,
    progress_cb=None,
) -> tuple[list[str], pd.DataFrame]:
    """Carrega XML (Excel 2003) ou XLSX/XLSM, retornando (nomes_abas, DataFrame)."""
    ext = os.path.splitext(caminho)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        return _carregar_xlsx(caminho, worksheet_idx, progress_cb)
    return carregar_xml(caminho, worksheet_idx, progress_cb)


def _carregar_xlsx(
    caminho: str,
    worksheet_idx: int = 0,
    progress_cb=None,
) -> tuple[list[str], pd.DataFrame]:
    if progress_cb:
        progress_cb(5)
    try:
        xls = pd.ExcelFile(caminho)
    except Exception as exc:
        raise ValueError(f"Não foi possível abrir o Excel: {exc}")

    names = list(xls.sheet_names)
    if not names:
        raise ValueError("Nenhuma planilha encontrada no arquivo Excel.")

    idx = min(worksheet_idx, len(names) - 1)
    raw = xls.parse(names[idx], header=None, dtype=str).fillna("")
    if progress_cb:
        progress_cb(60)

    if len(raw) < 2:
        raise ValueError("A planilha não contém linhas de dados suficientes.")

    # Detecta a linha de cabeçalho (primeira com 2+ células preenchidas)
    header_row = 0
    for i in range(min(len(raw), 10)):
        preenchidas = (raw.iloc[i].astype(str).str.strip() != "").sum()
        if preenchidas >= 2:
            header_row = i
            break

    headers = [str(h).strip() for h in raw.iloc[header_row].tolist()]
    data = raw.iloc[header_row + 1:].copy()
    data.columns = headers
    # Descarta colunas sem nome
    data = data.loc[:, [bool(str(c).strip()) for c in data.columns]]
    for c in data.columns:
        data[c] = data[c].astype(str).str.strip()
    data = data.reset_index(drop=True)

    if progress_cb:
        progress_cb(100)
    return names, data


def carregar_xml(
    caminho: str,
    worksheet_idx: int = 0,
    progress_cb=None,
) -> tuple[list[str], pd.DataFrame]:
    """Parse único com ET.parse: confiável e com progresso no loop de dados."""
    try:
        tree = ET.parse(caminho)
    except ET.ParseError as exc:
        raise ValueError(f"XML malformado: {exc}")

    root = tree.getroot()
    worksheets = root.findall(".//ss:Worksheet", _ns)
    if not worksheets:
        raise ValueError("Nenhuma planilha (Worksheet) encontrada no XML.")

    names = [
        ws.get(f"{{{NS}}}Name") or f"Planilha{i + 1}"
        for i, ws in enumerate(worksheets)
    ]

    ws_idx = min(worksheet_idx, len(worksheets) - 1)
    table = worksheets[ws_idx].find("ss:Table", _ns)
    if table is None:
        raise ValueError("Elemento Table não encontrado na planilha.")

    rows = table.findall("ss:Row", _ns)
    if len(rows) < 2:
        raise ValueError("O XML não contém linhas de dados suficientes.")

    headers = _parse_row(rows[1])
    data_rows = rows[2:]
    total = max(len(data_rows), 1)
    records = []

    for i, row in enumerate(data_rows):
        values = _parse_row(row)
        if len(values) < len(headers):
            values += [""] * (len(headers) - len(values))
        elif len(values) > len(headers):
            values = values[: len(headers)]
        records.append(dict(zip(headers, values)))

        if progress_cb and i % 500 == 0:
            progress_cb(min(int(i / total * 100), 99))

    if progress_cb:
        progress_cb(100)

    return names, pd.DataFrame(records)
