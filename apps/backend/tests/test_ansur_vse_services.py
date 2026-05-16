from pathlib import Path
import shutil
import uuid

from app.services.ansur_parser import parse_ansur_mtr
from app.services.ansur_template_detector import is_permanent_three_measure_template
from app.services.csv_parser import parse_esa615_csv
from app.services.measurement_indexer import build_measurement_index
from app.services.measurement_selector import find_worst_protective_earth
from app.services.mtr_parser import parse_mtr_file
from app.services.pdf_generator import build_pdf_filename, generate_vse_pdf
from app.services.source_writer import save_to_source
from app.services.vse_defaults import ansur_defaults, merge_final_data, source_data


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


def test_malformed_xml_mtr_falls_back_to_text_parse():
    tmp_path = workdir()
    path = tmp_path / "broken.mtr"
    path.write_text(
        """<?xml version="1.0"?>
<Ansur>
Manufacturer: Acme
Model: X1
Serial Number: SN1
\x01
</Ansur>""",
        encoding="utf-8",
    )
    parsed = parse_mtr_file(path)
    assert parsed["nome_file"] == "broken.mtr"
    assert parsed["produttore"] == "Acme"
    assert parsed["matricola"] == "SN1"
    assert parsed["normalized"]["source_type"] == "mtr"
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_xml_mtr_with_trailing_update_text_keeps_measurements():
    tmp_path = workdir()
    path = tmp_path / "trailing.mtr"
    path.write_text(
        """<?xml version="1.0"?>
<Ansur TemplateName="IEC62353-Diretto Classe1-BF">
  <Setup><DUT><Item Name="Manufacturer">Acme</Item><Item Name="Serial Number">SN1</Item></DUT></Setup>
  <ResultItem ElementID="PE1"><Measurement><Description>Protective Earth Resistance</Description><Value>0.10</Value><Unit>ohm</Unit><Status>Passed</Status></Measurement></ResultItem>
</Ansur>

# Aggiornamento gestione-vse
id: 129
""",
        encoding="utf-8",
    )
    parsed = parse_mtr_file(path)
    assert parsed["produttore"] == "Acme"
    assert parsed["matricola"] == "SN1"
    assert len(parsed["normalized"]["measurements"]) == 1
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


def test_parse_esa615_csv_report_format():
    tmp_path = workdir()
    path = tmp_path / "sample_esa615.csv"
    path.write_text(
        """,,,,,,,Date :15/05/2026
Test Setup
,,,,,DUT Information
Operator ID :,,,,,Equipment Number :,,08
Calibration Tech :,,SLT,,,Serial Number :,,02311023
Calibration Date :,,10/17/2025,,,Manufacturer :,,GOLDEN STAR
Firmware Version :,,3.01.03,,,Model :,,ENDOR PLUS
Serial Number :,,7013015,,,Location :,,FT IVAN ROSI
Date & Time :,,2026/05/15 & 09:06,,,Other :,,TECAR TERAPIA
Template Name :,,IEC62353-Diretto Classe1-BF,,,Standard :,,IEC62353-Direct
Classification:,,I
AP Name,AP Type,AP Num
Funz.1,BF,1
ESA615 Test Results
Test Name,,,,,Value,High Limits,Low Limits,Status
Protective Earth Resistance,,,,,0.087 Ohm,0.3,-,P
Equipment Current,,,,,0.1 A,-,-,P
""",
        encoding="utf-8",
    )
    parsed = parse_mtr_file(path)
    instrument = parsed["normalized"]["instrument"]
    assert parsed["normalized"]["source_type"] == "csv"
    assert parsed["matricola"] == "02311023"
    assert parsed["inventario"] == "08"
    assert parsed["produttore"] == "GOLDEN STAR"
    assert parsed["modello"] == "ENDOR PLUS"
    assert parsed["descrizione"] == "TECAR TERAPIA"
    assert parsed["reparto"] in (None, "")
    assert parsed["stanza"] == "FT IVAN ROSI"
    assert parsed["template_ansur"] == "IEC62353-Diretto Classe1-BF"
    assert (instrument.get("serialNumber") or instrument.get("serial_number")) == "7013015"
    assert (instrument.get("calibrationDate") or instrument.get("calibration_date")) == "10/17/2025"
    assert len(parsed["normalized"]["measurements"]) == 2
    assert parsed["normalized"]["measurements"][0]["result"] in {"PASS", "P"}
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


def test_dut_items_map_to_inventory_tipologia_and_stanza():
    tmp_path = workdir()
    source = tmp_path / "dut.mtr"
    source.write_text(
        """<?xml version="1.0"?>
<Root><DUT>
  <Item Name="Serial Number" Ord="1" Caption="Serial Number" Required="True" Key="True">200002621</Item>
  <Item Name="Equipment Number" Ord="2" Caption="Appliance Code">19</Item>
  <Item Name="Manufacturer" Ord="3" Caption="Manufacturer">CHINESPORT SPA</Item>
  <Item Name="Model" Ord="4" Caption="Model">LS382B6WF</Item>
  <Item Name="Location" Ord="5" Caption="Location">STANZA 1</Item>
  <Item Name="Other" Ord="6" Caption="Other">LETTO ELETTRICO</Item>
</DUT></Root>""",
        encoding="utf-8",
    )
    parsed = parse_mtr_file(source)
    final_source = source_data(parsed["normalized"])
    assert parsed["matricola"] == "200002621"
    assert parsed["inventario"] == "19"
    assert parsed["descrizione"] == "LETTO ELETTRICO"
    assert final_source["stanza"] == "STANZA 1"
    assert final_source["presidio"] == ""
    assert final_source["reparto"] == ""
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_final_pdf_data_does_not_promote_mtr_location_to_presidio_or_reparto():
    job = type("Job", (), {"tecnico_default": "", "firma_default_path": "", "proprieta_default": "", "periodicita_default": "12", "tensione_default": "220", "frequenza_default": "50", "protezione_default": "", "template_pdf": "standard", "intestazione_pdf": "standard"})()
    file_mtr = type(
        "FileMtrObj",
        (),
        {
            "produttore": "CHINESPORT SPA",
            "modello": "LS382B6WF",
            "matricola": "200002621",
            "seriale": "200002621",
            "inventario": "19",
            "descrizione": "LETTO ELETTRICO",
            "reparto": "NO NAME",
            "template_ansur": "",
            "nome_file": "sample.mtr",
            "path_corrente": "sample.mtr",
            "parsed_data": {},
            "parsed_json": {
                "dut": {
                    "manufacturer": "CHINESPORT SPA",
                    "model": "LS382B6WF",
                    "serial_number": "200002621",
                    "inventory": "19",
                    "description": "LETTO ELETTRICO",
                    "location": "NO NAME",
                },
                "ansur": {},
                "test": {},
                "instrument": {},
                "measurements": [],
            },
        },
    )()
    verification = type("Verification", (), {"dati_excel_json": {}, "dati_revisionati_json": {}, "campi_bloccati_json": {}})()
    from app.services.bulk_pdf_service import build_final_pdf_data

    final = build_final_pdf_data(job, file_mtr, verification)
    assert final["stanza"] == "NO NAME"
    assert final["presidio"] == ""
    assert final["reparto"] == ""


def test_source_writer_updates_dut_items_without_mapping_reparto_to_location():
    tmp_path = workdir()
    source = tmp_path / "source.mtr"
    source.write_text(
        """<?xml version="1.0"?>
<Root><DUT>
  <Item Name="Equipment Number" Ord="2" Caption="Appliance Code">200002621</Item>
  <Item Name="Location" Ord="5" Caption="Location">NO NAME</Item>
  <Item Name="Other" Ord="6" Caption="Other">LETTO ELETTRICO</Item>
</DUT></Root>""",
        encoding="utf-8",
    )
    result = save_to_source(source, {"inventario": "19", "descrizione": "LETTINO", "stanza": "STANZA 1", "reparto": "FISIOTERAPIA"}, tmp_path / "backup")
    content = source.read_text(encoding="utf-8")
    assert {"inventario", "descrizione", "stanza"}.issubset(set(result["changed"]))
    assert "FISIOTERAPIA" not in content
    assert "<Item Name=\"Equipment Number\" Ord=\"2\" Caption=\"Appliance Code\">19</Item>" in content
    assert "<Item Name=\"Location\" Ord=\"5\" Caption=\"Location\">STANZA 1</Item>" in content
    assert "<Item Name=\"Other\" Ord=\"6\" Caption=\"Other\">LETTINO</Item>" in content
    shutil.rmtree(tmp_path, ignore_errors=True)
