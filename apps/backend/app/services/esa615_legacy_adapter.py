from pathlib import Path
import importlib.util
import tempfile
from datetime import datetime
from types import ModuleType
from typing import Any

from app.services.xml_cleaner import read_xml_document_text


_MODULE: ModuleType | None = None


def _legacy_module() -> ModuleType:
    global _MODULE
    if _MODULE is not None:
        return _MODULE
    root = Path(__file__).resolve().parents[4]
    source = root / "esa615_app_v2.py"
    if not source.exists():
        raise FileNotFoundError(f"File legacy non trovato: {source}")
    spec = importlib.util.spec_from_file_location("esa615_app_v2_legacy", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossibile caricare {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _MODULE = module
    return module


def parse_mtr_legacy(path: str | Path) -> dict[str, Any]:
    module = _legacy_module()
    try:
        return module.parse_mtr(str(path))
    except Exception:
        clean_text = read_xml_document_text(path)
        with tempfile.NamedTemporaryFile("w", suffix=Path(path).suffix or ".mtr", encoding="utf-8", delete=False) as handle:
            handle.write(clean_text)
            temp_path = Path(handle.name)
        try:
            parsed = module.parse_mtr(str(temp_path))
            parsed["sourceFile"] = Path(path).name
            parsed["sourceFilePath"] = str(path)
            return parsed
        finally:
            temp_path.unlink(missing_ok=True)


def parse_csv_legacy(path: str | Path) -> dict[str, Any]:
    return _legacy_module().parse_csv(str(path))


def generate_pdf_legacy(data: dict, edited: dict, output_path: str | Path, header_image: str | None = None) -> None:
    module = _legacy_module()
    old_header = getattr(module, "HEADER_IMAGE_OVERRIDE", None)
    module.HEADER_IMAGE_OVERRIDE = header_image or None
    try:
        module.generate_pdf(_normalize_legacy_pdf_dates(data), edited, str(output_path))
    finally:
        module.HEADER_IMAGE_OVERRIDE = old_header


def apply_template_defaults_legacy(data: dict, edited: dict) -> dict:
    return _legacy_module().apply_template_defaults(data, edited)


def normalize_classification_legacy(value: str | None) -> str:
    return _legacy_module().normalize_classification(value)


def default_class_legacy(data: dict) -> str:
    return _legacy_module().default_class(data)


def default_installation_legacy(data: dict) -> str:
    return _legacy_module().default_installation(data)


def default_mobility_legacy(data: dict) -> str:
    return _legacy_module().default_mobility(data)


def default_earth_res_pos_legacy(data: dict) -> str:
    return _legacy_module().default_earth_res_pos(data)


def is_permanent_three_measure_template_legacy(data_or_name: dict | str | None) -> bool:
    return _legacy_module().is_permanent_three_measure_template(data_or_name)


def sanitize_filename_legacy(value: str) -> str:
    return _legacy_module().sanitize_filename(value)


def earth_res_positions() -> list[str]:
    return list(_legacy_module().EARTH_RES_POSITIONS)


def _normalize_legacy_pdf_dates(data: dict) -> dict:
    result = dict(data)
    result["testDate"] = _italian_date(result.get("testDate"))
    instrument = dict(result.get("instrument") or {})
    instrument["calibrationDate"] = _italian_date(instrument.get("calibrationDate"))
    result["instrument"] = instrument
    return result


def _italian_date(value: object) -> str:
    text = str(value or "").strip()
    if not text or text == "-":
        return text
    text = text.replace("T", " ").split(" ", 1)[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(text[:10], fmt).date()
            return f"{parsed.day:02d}/{parsed.month:02d}/{parsed.year}"
        except ValueError:
            pass
    return text
