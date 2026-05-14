from pathlib import Path
import shutil
import uuid

from app.services.ansur_parser import parse_ansur_mtr
from app.services.ansur_template_detector import is_permanent_three_measure_template
from app.services.csv_parser import parse_esa615_csv
from app.services.measurement_indexer import build_measurement_index
from app.services.measurement_selector import find_worst_protective_earth
from app.services.pdf_generator import build_pdf_filename, generate_vse_pdf
from app.services.source_writer import save_to_source
from app.services.vse_defaults import ansur_defaults, merge_final_data


def workdir() -> Path:
    path = Path("C:/tmp") / f"vse-tests-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_permanent_three_measure_template_detection():
    measurements = [{"name": "Protective Earth Resistance", "value": "0.10 ohm"}, {"name": "Terra protezione 2", "value": "0.15 ohm"}, {"name": "PE resistance third", "value": "0.12 ohm"}]
    assert is_permanent_three_measure_template("Installazione permanente ESA615", measurements)


def test_permanent_template_defaults_select_worst_pe():
    parsed = {"ansur": {"is_permanent_three_measure_template": True, "electrical_class": ""}, "measurements": [{"name": "Protective Earth", "value": "0.10 ohm"}, {"name": "Protective Earth", "value": "0.31 ohm"}, {"name": "Terra", "value": "0.20 ohm"}]}
    defaults = ansur_defaults(parsed)
    assert defaults["classe_elettrica"] == "I"
    assert defaults["installazione"] == "Permanente"
    assert defaults["mobilita"] == "Fisso"
    assert defaults["resistenza_terra"] == "0.31 ohm"


def test_normal_template_defaults():
    parsed = {"ansur": {"electrical_class": "II", "applied_part_type": "BF", "is_permanent_three_measure_template": False}, "measurements": []}
    defaults = ansur_defaults(parsed)
    assert defaults["classe_elettrica"] == "II"
    assert defaults["installazione"] == "Non permanente"
    assert defaults["mobilita"] == "Trasportabile"


def test_measurement_index_and_worst_pe():
    measurements = [{"name": "Protective Earth Resistance", "value": "0.20 ohm", "unit": "ohm"}, {"name": "Continuita terra", "value": "0.44 ohm", "unit": "ohm"}]
    index = build_measurement_index(measurements)
    assert "protective" in index["by_name"]
    assert find_worst_protective_earth(measurements)["value"] == "0.44 ohm"


def test_parse_minimal_mtr_xml():
    tmp_path = workdir()
    path = tmp_path / "sample.mtr"
    path.write_text(
        """<?xml version="1.0"?>
<Ansur TemplateName="Installazione permanente">
  <Setup><DUT>
    <Item Name="Manufacturer" Value="Acme"/>
    <Item Name="Model" Value="X1"/>
    <Item Name="Serial Number" Value="SN1"/>
    <Item Name="Inventory" Value="INV1"/>
    <Item Name="Location" Value="Cardiologia"/>
  </DUT></Setup>
  <ResultItem Name="Protective Earth Resistance" Value="0.10" Unit="ohm" Result="PASS" ElementID="PE1"/>
  <ResultItem Name="Protective Earth Resistance 2" Value="0.20" Unit="ohm" Result="PASS" ElementID="PE2"/>
  <ResultItem Name="Protective Earth Resistance 3" Value="0.30" Unit="ohm" Result="PASS" ElementID="PE3"/>
</Ansur>""",
        encoding="utf-8",
    )
    parsed = parse_ansur_mtr(path)
    assert parsed["dut"]["manufacturer"] == "Acme"
    assert parsed["dut"]["serial_number"] == "SN1"
    assert parsed["ansur"]["is_permanent_three_measure_template"] is True
    assert len(parsed["measurements"]) == 3
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_parse_minimal_csv():
    tmp_path = workdir()
    path = tmp_path / "sample.csv"
    path.write_text("Produttore;Acme\nModello;X1\nMatricola;SN1\nTemplate;Installazione permanente\nProtective Earth;0.22 ohm;PASS\n", encoding="utf-8")
    parsed = parse_esa615_csv(path)
    assert parsed["dut"]["manufacturer"] == "Acme"
    assert parsed["dut"]["serial_number"] == "SN1"
    assert parsed["measurements"][0]["name"] == "Protective Earth"
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_merge_precedence_manual_over_defaults():
    final = merge_final_data(job_defaults_data={"tecnico": "Default", "tensione": "220"}, ansur_data={"tecnico": "Ansur"}, excel_data={"tecnico": "Excel"}, revised_data={"tecnico": "Manuale"}, locked_data={"tensione": "230"})
    assert final["tecnico"] == "Manuale"
    assert final["tensione"] == "230"


def test_pdf_filename_and_generation_without_header():
    tmp_path = workdir()
    name = build_pdf_filename({"tipologia": "Monitor", "matricola": "SN 1", "produttore": "Acme", "modello": "X1"})
    assert name == "Monitor-Acme-X1-SN_1.pdf"
    generated = generate_vse_pdf({"tipologia": "Monitor", "matricola": "SN1", "produttore": "Acme", "modello": "X1", "tecnico": "Mario"}, tmp_path)
    assert Path(generated["path"]).exists()
    assert Path(generated["path"]).read_bytes().startswith(b"%PDF")
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_source_writer_updates_safe_xml_fields_and_not_measurements():
    tmp_path = workdir()
    source = tmp_path / "source.mtr"
    source.write_text(
        """<?xml version="1.0"?><Root><Setup><DUT><Item Name="Manufacturer" Value="Old"/><Item Name="Model" Value="M1"/></DUT></Setup><Measurement Name="Protective Earth" Value="0.25" Unit="ohm"/></Root>""",
        encoding="utf-8",
    )
    result = save_to_source(source, {"produttore": "New"}, tmp_path / "backup")
    content = source.read_text(encoding="utf-8")
    assert "New" in content
    assert "0.25" in content
    assert "produttore" in result["changed"]
    shutil.rmtree(tmp_path, ignore_errors=True)
