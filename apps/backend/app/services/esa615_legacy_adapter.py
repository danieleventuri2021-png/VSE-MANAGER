from pathlib import Path
import importlib.util
from types import ModuleType
from typing import Any


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
    return _legacy_module().parse_mtr(str(path))


def parse_csv_legacy(path: str | Path) -> dict[str, Any]:
    return _legacy_module().parse_csv(str(path))


def generate_pdf_legacy(data: dict, edited: dict, output_path: str | Path, header_image: str | None = None) -> None:
    module = _legacy_module()
    old_header = getattr(module, "HEADER_IMAGE_OVERRIDE", None)
    module.HEADER_IMAGE_OVERRIDE = header_image or None
    try:
        module.generate_pdf(data, edited, str(output_path))
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
