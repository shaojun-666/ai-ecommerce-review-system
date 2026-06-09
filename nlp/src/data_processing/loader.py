"""Multi-format data loader for review datasets."""
import pandas as pd
from typing import Optional


def load_csv(path: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, **kwargs)


def load_excel(path: str, **kwargs) -> pd.DataFrame:
    return pd.read_excel(path, **kwargs)


def load_json(path: str, **kwargs) -> pd.DataFrame:
    return pd.read_json(path, **kwargs)


def load_text(path: str, delimiter: str = "\t", **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, delimiter=delimiter, **kwargs)


def load_dataset(path: str, format: Optional[str] = None, **kwargs) -> pd.DataFrame:
    """Auto-detect format and load dataset."""
    if format:
        loaders = {"csv": load_csv, "excel": load_excel, "json": load_json, "tsv": load_text}
        return loaders[format](path, **kwargs)

    ext = str(path).rsplit(".", 1)[-1].lower()
    format_map = {"csv": load_csv, "xlsx": load_excel, "xls": load_excel, "json": load_json, "tsv": load_text}
    loader = format_map.get(ext, load_csv)
    return loader(path, **kwargs)
