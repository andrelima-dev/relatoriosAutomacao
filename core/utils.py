import os
import sys

import pandas as pd


def resource_path(relative: str) -> str:
    """Caminho de um asset embutido, tanto em dev quanto no .exe do PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, relative)


def is_date_col(col_name: str) -> bool:
    upper = col_name.strip().upper()
    return upper.startswith("DATA") or upper.endswith("_DATA") or "DATA_" in upper


def get_col(df: pd.DataFrame, nome: str) -> str | None:
    for c in df.columns:
        if c.strip().upper() == nome.upper():
            return c
    return None
