from pathlib import Path

import pandas as pd

from app.services.column_mapper import extract_row, map_columns


def import_excel(path: str | Path) -> tuple[list[dict], dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File Excel non trovato: {file_path}")
    df = pd.read_excel(file_path, dtype=str).fillna("")
    mapping = map_columns(df.columns)
    records: list[dict] = []
    for index, row in df.iterrows():
        raw = {str(k): (None if str(v).lower() == "nan" else str(v).strip()) for k, v in row.to_dict().items()}
        normalized = extract_row(raw, mapping)
        records.append({"row_index": int(index) + 2, "raw_data": {**raw, **normalized}, **normalized})
    return records, mapping
