import pandas as pd


def is_date_col(col_name: str) -> bool:
    upper = col_name.strip().upper()
    return upper.startswith("DATA") or upper.endswith("_DATA") or "DATA_" in upper


def get_col(df: pd.DataFrame, nome: str) -> str | None:
    for c in df.columns:
        if c.strip().upper() == nome.upper():
            return c
    return None
