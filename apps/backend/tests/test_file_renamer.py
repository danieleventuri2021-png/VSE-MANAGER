from pathlib import Path
from unittest.mock import patch

from app.services.file_renamer import build_mtr_filename, unique_path


def test_build_mtr_filename_sanitizes_fields():
    filename = build_mtr_filename({"matricola": "AB/12", "produttore": "ACME Spa", "modello": "X 1", "reparto": "Sala 1"})
    assert filename == "AB_12-ACME_Spa-X_1-Sala_1.MTR"


def test_unique_path_adds_progressive_suffix():
    def fake_exists(path: Path) -> bool:
        return path.name == "A.MTR"

    with patch.object(Path, "exists", fake_exists):
        assert unique_path("C:/nonexistent", "A.MTR").name == "A_01.MTR"
