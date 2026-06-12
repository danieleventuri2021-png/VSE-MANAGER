#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESA615 - Generatore Schede Verifica Sicurezza Generale (Layout V2)
Genera PDF conformi al modulo VS Generale_Scheda (layout originale) da file .mtr e .csv
"""

import os
import sys
import xml.etree.ElementTree as ET
import re
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:  # Ambiente headless: GUI non disponibile, parsing e PDF funzionano comunque
    tk = ttk = filedialog = messagebox = None
from fpdf import FPDF


EARTH_RES_POSITIONS = [
    "Cavo non separabile - R connettore terra/parti accessibili (300 mOhm)",
    "Cavo non separabile - R cavo singolo (100 mOhm)",
    "Cavo separabile - R morsetto terra protezione/parti accessibili (200 mOhm)",
    "Cavo separabile - R connettore terra spina/parti accessibili (300 mOhm)",
    "Presa multipla - R connettore terra/parti conduttive accessibili (500 mOhm)",
]


def _first_existing_font(*paths):
    for path in paths:
        if path and os.path.exists(path):
            return path
    return None


def pdf_font_paths():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    bundled_fonts = os.path.join(root_dir, "data", "fonts")
    win_fonts = os.environ.get("WINDIR", r"C:\Windows")
    win_fonts = os.path.join(win_fonts, "Fonts")
    regular = _first_existing_font(
        os.path.join(bundled_fonts, "calibri.ttf"),
        os.path.join(win_fonts, "calibri.ttf"),
        "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    )
    bold = _first_existing_font(
        os.path.join(bundled_fonts, "calibrib.ttf"),
        os.path.join(win_fonts, "calibrib.ttf"),
        "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    )
    italic = _first_existing_font(
        os.path.join(bundled_fonts, "calibrii.ttf"),
        os.path.join(win_fonts, "calibrii.ttf"),
        "/usr/share/fonts/truetype/crosextra/Carlito-Italic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansOblique.ttf",
    )
    return regular, bold or regular, italic or regular


def normalize_classification(value):
    """Normalizza la classe elettrica letta da Ansur."""
    cls = (value or "").strip().upper().replace("CLASSE", "").replace("CLASS", "").strip()
    cls = cls.replace(".", "")
    mapping = {
        "1": "I",
        "I": "I",
        "2": "II",
        "II": "II",
        "IP": "AI",
        "AI": "AI",
    }
    return mapping.get(cls, cls)


def is_permanent_three_measure_template(data_or_name):
    """Riconosce i template Ansur per installazione permanente con tre misure PE."""
    if isinstance(data_or_name, dict):
        name = data_or_name.get("templateName", "")
    else:
        name = data_or_name or ""
    normalized = re.sub(r"\s+", " ", name).strip().lower()
    return "installazione permanente" in normalized and "3 misure" in normalized


def default_class(data):
    return normalize_classification(data.get("classification", "I")) or "I"


def default_installation(data):
    return "Permanente" if is_permanent_three_measure_template(data) else "Non permanente"


def default_mobility(data):
    return "Fisso" if is_permanent_three_measure_template(data) else "Trasportabile"


def default_earth_res_pos(data):
    if is_permanent_three_measure_template(data):
        return EARTH_RES_POSITIONS[0]
    return EARTH_RES_POSITIONS[3]


def apply_template_defaults(data, edited):
    """Applica le regole automatiche derivate dal template del file."""
    result = dict(edited)
    result["classe"] = normalize_classification(result.get("classe") or default_class(data)) or "I"
    if is_permanent_three_measure_template(data):
        result["classe"] = "I"
        result["installazione"] = "Permanente"
        result["mobilita"] = "Fisso"
        result["earthResPos"] = EARTH_RES_POSITIONS[0]
    return result


# ======================== PARSING ========================

def parse_mtr(filepath):
    """Parse un file .mtr (XML Ansur/ESA615)."""
    tree = ET.parse(filepath)
    root = tree.getroot()
    data = {"sourceFile": os.path.basename(filepath), "sourceFilePath": filepath}

    # DUT info
    for item in root.findall(".//Setup/DUT/Item"):
        name = item.get("Name", "")
        val = (item.text or "").strip()
        if name == "Serial Number":
            data["serialNumber"] = val
        elif name == "Equipment Number":
            data["equipmentNumber"] = val
        elif name == "Manufacturer":
            data["manufacturer"] = val
        elif name == "Model":
            data["model"] = val
        elif name == "Location":
            data["location"] = val
        elif name == "Other":
            data["other"] = val

    # Template name
    tmpl = root.find(".//Template")
    data["templateName"] = tmpl.get("Name", "") if tmpl is not None else ""

    # Classification from Comment
    comment_el = root.find(".//ResultData//Comment")
    comment = comment_el.text if comment_el is not None else ""
    m = re.search(r"Classification of Instrument\s*::\s*(\S+)", comment)
    if m:
        data["classification"] = normalize_classification(m.group(1))

    # AP type from template name
    tn = data["templateName"]
    if tn.endswith("-B"):
        data["apType"] = "B"
    elif "-BF" in tn:
        data["apType"] = "BF"
    elif "-CF" in tn:
        data["apType"] = "CF"

    # Test date
    date_el = root.find(".//Record/TestData/Date")
    if date_el is not None:
        data["testDate"] = f"{date_el.get('Day')}/{date_el.get('Month')}/{date_el.get('Year')}"

    # Overall status
    status_el = root.find(".//Record/TestData/Status")
    data["overallStatus"] = status_el.text if status_el is not None else ""

    # Test instrument
    mti = root.find(".//MTIData")
    if mti is not None:
        data["instrument"] = {
            "type": (mti.findtext("Type") or "").strip(),
            "serialNumber": (mti.findtext("SerialNumber") or "").strip(),
            "calibrationDate": (mti.findtext("CalibrationDate") or "").strip(),
        }

    # Build a map of ElementID -> test info from TemplateData
    te_info = {}
    for te in root.iter("TestElement"):
        eid = te.get("ID")
        info = te.find("Info")
        if eid and info is not None:
            ttype = (info.findtext("Type") or "").strip()
            param = (info.findtext("Parameter") or "").strip()
            te_info[eid] = {"type": ttype, "param": param}

    # Measurements from ResultData
    data["measurements"] = []
    for ri in root.iter("ResultItem"):
        meas = ri.find("Measurement")
        if meas is None:
            continue
        desc = (meas.findtext("Description") or "").strip()
        val = (meas.findtext("Value") or "").strip()
        unit = (meas.findtext("Unit") or "").strip()
        st = (meas.findtext("Status") or "").strip()
        if not desc or desc == "Operator ID":
            continue

        # Find parent test info
        eid = ri.get("ElementID", "")
        parent_type = te_info.get(eid, {"type": "", "param": ""})

        # Also look at parent ResultItem for context
        data["measurements"].append({
            "description": desc,
            "value": val,
            "unit": unit,
            "status": st,
            "parentType": parent_type,
        })

    # Tipologia from Other
    if not data.get("tipologia"):
        data["tipologia"] = data.get("other", "")
    data["isPermanentThreeMeasure"] = is_permanent_three_measure_template(data)

    return data


def parse_csv(filepath):
    """Parse un file .csv ESA615."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    data = {"sourceFile": os.path.basename(filepath), "sourceFilePath": filepath, "measurements": []}

    for line in lines:
        line = line.strip()
        if "Equipment Number" in line:
            m = re.search(r"Equipment Number\s*:,,(.+)", line)
            if m:
                data["equipmentNumber"] = m.group(1).strip()
        if "Calibration Tech" in line:
            m = re.search(r"Serial Number\s*:,,(.+)", line)
            if m:
                data["serialNumber"] = m.group(1).strip()
        if "Calibration Date" in line:
            m = re.search(r"Manufacturer\s*:,,(.+)", line)
            if m:
                data["manufacturer"] = m.group(1).strip()
            m2 = re.search(r"Calibration Date\s*:,,([^,]+)", line)
            if m2:
                data["calibrationDate"] = m2.group(1).strip()
        if "Firmware Version" in line:
            m = re.search(r"Model\s*:,,(.+)", line)
            if m:
                data["model"] = m.group(1).strip()
        if "Serial Number :" in line and "Location" in line:
            m = re.search(r"Location\s*:,,(.+)", line)
            if m:
                data["location"] = m.group(1).strip()
            m2 = re.search(r"Serial Number\s*:,,([^,]+)", line)
            if m2:
                data["instrumentSN"] = m2.group(1).strip()
        if "Date & Time" in line:
            m = re.search(r"Other\s*:,,(.+)", line)
            if m:
                data["other"] = m.group(1).strip()
            m2 = re.search(r"Date & Time\s*:,,([^,]+)", line)
            if m2:
                raw = m2.group(1).strip()
                parts = raw.split(" & ")
                if parts:
                    dp = parts[0].split("/")
                    if len(dp) == 3:
                        data["testDate"] = f"{dp[2]}/{dp[1]}/{dp[0]}"
        if "Template Name" in line:
            m = re.search(r"Template Name\s*:,,([^,]+)", line)
            if m:
                data["templateName"] = m.group(1).strip()
        if "Classification:" in line:
            m = re.search(r"Classification:\s*,,([^,]+)", line)
            if m:
                data["classification"] = normalize_classification(m.group(1).strip())
        if re.match(r"^Funz\.\d+,", line):
            parts = line.split(",")
            if len(parts) >= 2:
                data["apType"] = parts[1].strip()

    data["instrument"] = {
        "type": "ESA615",
        "serialNumber": data.get("instrumentSN", ""),
        "calibrationDate": data.get("calibrationDate", ""),
    }

    # Parse test results
    in_results = False
    current_group = ""
    for line in lines:
        line = line.strip()
        if "ESA615 Test Results" in line:
            in_results = True
            continue
        if not in_results:
            continue
        if "_________" in line:
            break
        if not line or "Test Name" in line:
            continue

        cols = line.split(",")
        first = cols[0].strip()

        # Find value pattern
        val_match = re.search(r"\s([\d.]+)\s+([a-zA-Z\u00B5%\/]+)", line)
        status_match = re.search(r",([PF])\s*$", line)

        if first:
            current_group = first
            if val_match:
                data["measurements"].append({
                    "description": first,
                    "value": val_match.group(1),
                    "unit": val_match.group(2),
                    "status": "Passed" if status_match and status_match.group(1) == "P" else "Failed",
                    "parentType": {"type": first, "param": ""},
                })
        elif val_match:
            desc = ""
            for c in cols[1:]:
                c = c.strip()
                if c and not re.match(r"^[\d.]+ ", c) and c not in ("-", "P", "F") and not re.match(r"^\d+$", c):
                    desc = c
                    break
            data["measurements"].append({
                "description": desc or current_group,
                "value": val_match.group(1),
                "unit": val_match.group(2),
                "status": "Passed" if status_match and status_match.group(1) == "P" else "Failed",
                "parentType": {"type": current_group, "param": desc},
            })

    all_passed = all(m["status"] == "Passed" for m in data["measurements"])
    data["overallStatus"] = "Passed" if all_passed else "Failed"
    data["tipologia"] = data.get("other", "")
    data["isPermanentThreeMeasure"] = is_permanent_three_measure_template(data)

    return data


# ======================== SAVING ========================

def save_mtr(filepath, edited):
    """Salva le modifiche nel file .mtr (XML)."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    field_map = {
        "Serial Number": "serial",
        "Equipment Number": "invGest",
        "Manufacturer": "manufacturer",
        "Model": "model",
        "Location": "presidio",
        "Other": "tipologia",
    }

    for item in root.findall(".//Setup/DUT/Item"):
        name = item.get("Name", "")
        if name in field_map:
            val = edited.get(field_map[name], "")
            item.text = val

    tree.write(filepath, encoding="utf-8", xml_declaration=True)


def save_csv(filepath, edited):
    """Salva le modifiche nel file .csv."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    # Mappa: campo CSV (lato destro della riga) -> chiave edited
    right_fields = {
        "Equipment Number": "invGest",
        "Serial Number": "serial",
        "Manufacturer": "manufacturer",
        "Model": "model",
        "Location": "presidio",
        "Other": "tipologia",
    }

    new_lines = []
    for line in lines:
        new_line = line
        for csv_field, edit_key in right_fields.items():
            # I campi DUT sono sulla parte destra delle righe, formato: "FieldName :,,value"
            pattern = rf"({csv_field}\s*:,,)([^\r\n]*)"
            # Conta quante volte appare nella riga - aggiorna solo l'ultima occorrenza (lato DUT)
            matches = list(re.finditer(pattern, new_line))
            if matches:
                # L'ultimo match e' quello del blocco DUT (colonne a destra)
                m = matches[-1]
                val = edited.get(edit_key, "")
                new_line = new_line[:m.start(2)] + val + new_line[m.end(2):]
        new_lines.append(new_line)

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


# ======================== PDF GENERATION ========================

class SchedaPDF(FPDF):
    """PDF che riproduce il modulo VS Generale_Scheda (3 pagine)."""

    def __init__(self, data, edited):
        super().__init__("P", "mm", "A4")
        self.data = data
        self.ed = edited
        self.set_auto_page_break(auto=False)
        regular, bold, italic = pdf_font_paths()
        if regular:
            self.add_font("Calibri", "", regular, uni=True)
            self.add_font("Calibri", "B", bold, uni=True)
            self.add_font("Calibri", "I", italic, uni=True)

    def footer(self):
        self.set_y(285)
        self.set_font("Calibri", "", 10)
        self.set_text_color(100)
        self.cell(0, 4, "Meditech S.r.l.", align="L")
        self.set_x(80)
        self.cell(50, 4, "VSS.GEN Rev03 del 01/07/2019", align="C")
        self.set_x(160)
        self.cell(35, 4, f"Pag. {self.page_no()} a {{nb}}", align="R")

    def draw_checkbox(self, x, y, checked, label):
        self.set_draw_color(100)
        self.rect(x, y, 3, 3)
        if checked:
            self.set_font("Calibri", "B", 10)
            self.text(x + 0.5, y + 2.5, "X")
        self.set_font("Calibri", "", 10)
        self.text(x + 4.5, y + 2.3, label)

    def draw_box(self, x, y, w=3, h=3):
        self.set_draw_color(100)
        self.rect(x, y, w, h)

    def gray_bg(self, x, y, w, h):
        """Disegna sfondo grigio chiaro."""
        self.set_fill_color(230, 230, 230)
        self.rect(x, y, w, h, "F")

    def cell_bordered(self, x, y, w, h, txt="", align="L", font_style="", font_size=10):
        self.set_draw_color(150)
        self.rect(x, y, w, h)
        self.set_font("Calibri", font_style, font_size)
        self.set_xy(x + 1.5, y)
        self.cell(w - 3, h, txt, align=align)

    def find_meas(self, desc_part):
        for m in self.data.get("measurements", []):
            if desc_part in m.get("description", ""):
                return m
        return None

    def find_measurements(self, desc_part):
        return [
            m for m in self.data.get("measurements", [])
            if desc_part in m.get("description", "")
        ]

    def earth_measure_sort_value(self, measurement):
        try:
            value = float(measurement.get("value") or 0)
        except (TypeError, ValueError):
            return None
        unit = (measurement.get("unit") or "").strip().lower()
        if unit in ("mohm", "mohms"):
            return value / 1000
        return value

    def find_earth_resistance(self):
        earth_measurements = self.find_measurements("Protective Earth Resistance")
        if not earth_measurements:
            return None
        if not is_permanent_three_measure_template(self.data):
            return earth_measurements[0]

        with_values = []
        for measurement in earth_measurements:
            sort_value = self.earth_measure_sort_value(measurement)
            if sort_value is not None:
                with_values.append((sort_value, measurement))
        if not with_values:
            return earth_measurements[0]
        return max(with_values, key=lambda item: item[0])[1]

    def find_meas_by_parent(self, parent_type, param_part):
        for m in self.data.get("measurements", []):
            pt = m.get("parentType", {})
            if parent_type in pt.get("type", ""):
                if param_part in pt.get("param", "") or param_part in m.get("description", ""):
                    return m
        return None

    def generate(self):
        self.alias_nb_pages()
        self.add_page()
        self.draw_page1()
        self.add_page()
        self.draw_page2()
        self.add_page()
        self.draw_page3()

    def draw_page1(self):
        ML = 15
        PW = 180
        W = 210
        y = 15

        # Header da immagine
        header_img = globals().get("HEADER_IMAGE_OVERRIDE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "meditech-vse.png")
        if os.path.isfile(header_img):
            self.image(header_img, x=ML, y=y, w=PW)
            y += 20
        else:
            # Fallback testo se immagine non trovata
            self.set_draw_color(0)
            self.rect(ML, y, PW, 16)
            self.set_font("Calibri", "B", 10)
            self.set_text_color(200, 0, 0)
            self.text(ML + 2, y + 5, "Meditech")
            self.set_text_color(0)
            self.set_font("Calibri", "B", 10)
            self.text(52, y + 3, "Scheda di Verifica di Sicurezza Generale")
            self.set_font("Calibri", "B", 10)
            self.text(50, y + 10, "APPARECCHIATURA ELETTROMEDICALE")
            self.set_font("Calibri", "", 10)
            self.text(W - 35, y, "Riferimento")
            self.text(W - 35, y + 4, "Protocollo")
            self.set_font("Calibri", "B", 10)
            self.text(W - 35, y + 8, "VSP.GEN")
            y += 20

        # DATI IDENTIFICATIVI
        y += 4
        self.set_font("Calibri", "B", 10)
        self.set_text_color(0)
        self.text(ML, y, "DATI IDENTIFICATIVI DELL'APPARECCHIATURA")
        y += 3

        ed = self.ed
        id_rows = [
            [("Tipologia Apparecchio", ed["tipologia"], PW * 0.7), ("Codice CIVAB", ed["civab"], PW * 0.3)],
            [("Produttore", ed["manufacturer"], PW * 0.5), ("Modello", ed["model"], PW * 0.5)],
            [("Matricola", ed["serial"], PW * 0.5), ("Proprieta'", ed["proprieta"], PW * 0.5)],
            [("N. Inventario Gestionale", ed["invGest"], PW * 0.5), ("N. Inventario Ente", ed["invEnte"], PW * 0.5)],
            [("Presidio", ed["presidio"], PW * 0.35), ("Reparto", ed["reparto"], PW * 0.35), ("Stanza", ed["stanza"], PW * 0.3)],
            [("Periodicita'", ed["periodicita"], PW)],
        ]

        lbl_h = 5  # altezza fascia grigia etichetta
        rh = 12
        for row in id_rows:
            x = ML
            for label, value, w in row:
                self.set_draw_color(150)
                self.rect(x, y, w, rh)
                self.gray_bg(x + 0.3, y + 0.3, w - 0.6, lbl_h)
                self.set_font("Calibri", "B", 10)
                self.set_text_color(0)
                self.text(x + 2, y + 4, label)
                self.set_font("Calibri", "", 10)
                self.set_text_color(0)
                self.text(x + 2, y + 10, value or "")
                x += w
            y += rh
        y += 4

        # DATI TECNICI
        self.set_font("Calibri", "B", 10)
        self.text(ML, y, "DATI TECNICI")
        y += 3

        techH = 26
        self.set_draw_color(150)
        self.rect(ML, y, PW, techH)
        c1, c2, c3, c4 = PW * 0.22, PW * 0.25, PW * 0.25, PW * 0.28
        self.line(ML + c1, y, ML + c1, y + techH)
        self.line(ML + c1 + c2, y, ML + c1 + c2, y + techH)
        self.line(ML + c1 + c2 + c3, y, ML + c1 + c2 + c3, y + techH)

        # Sfondo grigio per intestazioni colonne
        self.gray_bg(ML + 0.3, y + 0.3, c1 - 0.3, 5)
        self.gray_bg(ML + c1 + 0.3, y + 0.3, c2 - 0.6, 5)
        self.gray_bg(ML + c1 + c2 + 0.3, y + 0.3, c3 - 0.6, 5)
        self.gray_bg(ML + c1 + c2 + c3 + 0.3, y + 0.3, c4 - 0.3, 5)
        self.set_font("Calibri", "B", 10)
        self.set_text_color(0)
        self.text(ML + 2, y + 4, "Tipo installazione")
        self.text(ML + c1 + 2, y + 4, "Mobilita'")
        self.text(ML + c1 + c2 + c3 / 2 - 4, y + 4, "Classe")
        self.text(ML + c1 + c2 + c3 + c4 / 2 - 10, y + 4, "Parti applicate")

        inst = ed.get("installazione", "Non permanente")
        mob = ed.get("mobilita", "Trasportabile")
        self.set_font("Calibri", "", 10)
        self.draw_checkbox(ML + 3, y + 7, inst == "Permanente", "Permanente")
        self.draw_checkbox(ML + 3, y + 13, inst == "Non permanente", "Non permanente")
        self.draw_checkbox(ML + c1 + 3, y + 7, mob == "Fisso", "Fisso")
        self.draw_checkbox(ML + c1 + 3, y + 13, mob == "Spostabile", "Spostabile")
        self.draw_checkbox(ML + c1 + 3, y + 19, mob == "Trasportabile", "Trasportabile")
        self.draw_checkbox(ML + c1 + c2 * 0.55, y + 7, mob == "Portatile", "Portatile")
        self.draw_checkbox(ML + c1 + c2 * 0.55, y + 13, mob == "Stazionario", "Stazionario")

        cx = ML + c1 + c2 + 5
        self.draw_checkbox(cx, y + 7, ed["classe"] == "I", "I")
        self.draw_checkbox(cx, y + 13, ed["classe"] == "II", "II")
        self.draw_checkbox(cx, y + 19, ed["classe"] == "AI", "AI")

        ax = ML + c1 + c2 + c3 + 5
        self.draw_checkbox(ax, y + 7, ed["apType"] == "B", "B")
        self.draw_checkbox(ax, y + 13, ed["apType"] == "BF", "BF")
        self.draw_checkbox(ax, y + 19, ed["apType"] == "CF", "CF")
        y += techH + 2

        # Dati di targa
        tensione = ed.get("tensione", "220")
        frequenza = ed.get("frequenza", "50")
        potenza = ed.get("potenza", "")
        potenza_unit = ed.get("potenza_unit", "W")
        self.rect(ML, y, PW, 10)
        self.gray_bg(ML + 0.3, y + 0.3, PW - 0.6, 4.5)
        self.set_font("Calibri", "B", 10)
        self.set_text_color(0)
        self.text(ML + 2, y + 4, "Dati di targa")
        self.set_font("Calibri", "", 10)
        pot_txt = f"Tensione di alimentazione: {tensione} [V]     Frequenza: {frequenza} [Hz]     Potenza: "
        if potenza:
            pot_txt += f"{potenza} "
        # Evidenzia solo l'unita' selezionata se c'e' un valore
        for u in ["W", "A", "VA"]:
            if potenza and potenza_unit == u:
                pot_txt += f"[{u}] "
            else:
                pot_txt += f"  {u}   "
            if u != "VA":
                pot_txt += "/ "
        self.text(ML + 2, y + 8, pot_txt)
        y += 12

        # Protezione
        prot = ed.get("protezione", "Trasformatore di isolamento")
        fus_conf = ed.get("fusibili_conformita", "")
        dati_targa_fus = ed.get("dati_targa_fusibili", "")
        val_nom = ed.get("valore_nominale", "")
        prot_altro = ed.get("protezione_altro", "")
        prot_h = 42
        self.rect(ML, y, PW, prot_h)
        self.gray_bg(ML + 0.3, y + 0.3, PW - 0.6, 4.5)
        self.set_font("Calibri", "B", 10)
        self.set_text_color(0)
        self.text(ML + 2, y + 4, "Protezione")
        self.set_font("Calibri", "", 10)
        self.draw_checkbox(ML + 3, y + 7, prot == "Magnetotermico", "Magnetotermico")
        self.draw_checkbox(ML + PW * 0.35, y + 7, prot == "Magnetotermico Differenziale", "Magnetotermico Differenziale")
        self.draw_checkbox(ML + 3, y + 13, prot == "Termico", "Termico")
        self.draw_checkbox(ML + PW * 0.35, y + 13, prot == "Trasformatore di isolamento", "Trasformatore di isolamento")
        # Fusibili con sotto-opzioni
        self.draw_checkbox(ML + 3, y + 19, prot == "Fusibili", "Fusibili")
        self.draw_checkbox(ML + 30, y + 19, fus_conf == "conformi", "conformi ai dati di targa")
        self.draw_checkbox(ML + 30, y + 24, fus_conf == "non conformi", "non conformi ai dati di targa")
        self.draw_checkbox(ML + 30, y + 29, fus_conf == "senza dati", "Senza dati di targa")
        # Dati di Targa e Valore nominale
        self.set_font("Calibri", "", 10)
        rx = ML + PW * 0.55
        self.text(rx, y + 22, f"Dati di Targa: {dati_targa_fus or '___________________'}")
        self.text(rx, y + 28, f"Valore nominale dispositivo installato: {val_nom or '_____________'}")
        # Altro
        self.draw_checkbox(ML + 3, y + 35, prot == "Altro", "")
        self.set_font("Calibri", "", 10)
        self.text(ML + 7, y + 37.5, f"Altro {prot_altro or '________________________________'}")
        y += prot_h + 4

        # ESAME A VISTA
        self.set_font("Calibri", "B", 10)
        self.text(ML, y, "ESAME A VISTA")
        y += 2

        vista_keys = ["vista_targa", "vista_telaio", "vista_parti_mov", "vista_cavo",
                      "vista_passacavo", "vista_spie", "vista_parti_appl", "vista_doc"]
        vista_labels = [
            "Integrita' targa ed etichetta e presenza istruzioni necessarie per un corretto utilizzo",
            "Integrita' telaio, involucro e componenti esterne",
            "Integrita' delle parti in movimento, parti e superfici pericolose",
            "Controllo cavo/spina di alimentazione",
            "Verifica blocca cavo/passacavo",
            "Verifica integrita' spie/interruttori",
            "Controllo integrita' parti applicate, accessori e connettori",
            "Controllo della documentazione d'uso",
        ]

        vw = PW - 30
        self.set_draw_color(150)
        self.rect(ML, y, vw, 6)
        self.rect(ML + vw, y, 10, 6)
        self.rect(ML + vw + 10, y, 10, 6)
        self.rect(ML + vw + 20, y, 10, 6)
        self.gray_bg(ML + 0.3, y + 0.3, vw - 0.6, 5.4)
        self.gray_bg(ML + vw + 0.3, y + 0.3, 9.4, 5.4)
        self.gray_bg(ML + vw + 10.3, y + 0.3, 9.4, 5.4)
        self.gray_bg(ML + vw + 20.3, y + 0.3, 9.4, 5.4)
        self.set_font("Calibri", "B", 10)
        self.set_text_color(0)
        self.text(ML + 2, y + 4, "Descrizione attivita'")
        self.text(ML + vw + 2.5, y + 4, "OK")
        self.text(ML + vw + 12.5, y + 4, "KO")
        self.text(ML + vw + 22.5, y + 4, "NA")
        y += 6

        self.set_font("Calibri", "", 10)
        cw_vista = 10  # larghezza colonne OK/KO/NA
        ch_vista = 6   # altezza riga
        for i, label in enumerate(vista_labels):
            val = ed.get(vista_keys[i], "OK")
            self.rect(ML, y, vw, ch_vista)
            self.text(ML + 2, y + 4, label)
            for ci, (col_label, col_x) in enumerate([(("OK"), ML + vw), (("KO"), ML + vw + 10), (("NA"), ML + vw + 20)]):
                self.rect(col_x, y, cw_vista, ch_vista)
                bx = col_x + cw_vista / 2 - 1.5
                by = y + ch_vista / 2 - 1.5
                self.draw_box(bx, by)
                if val == col_label:
                    self.set_font("Calibri", "B", 10)
                    self.text(bx + 0.5, by + 2.5, "X")
                    self.set_font("Calibri", "", 10)
            y += ch_vista

    def draw_page2(self):
        ML = 15
        PW = 180
        y = 15

        self.set_font("Calibri", "B", 10)
        self.set_text_color(0)
        self.text(ML, y, "MISURE ELETTRICHE")
        y += 4

        # Resistenza di terra
        earth = self.find_earth_resistance()
        cw = [PW * 0.23, PW * 0.35, PW * 0.18, PW * 0.12, PW * 0.04, PW * 0.04, PW * 0.04]
        headers = ["Resistenza di terra\ndi protezione", "Punti di misurazione\nresistenza", "Misura", "Valori limiti\n(mOhm)", "OK", "KO", "NA"]
        x = ML
        for i, h in enumerate(headers):
            self.set_draw_color(150)
            self.rect(x, y, cw[i], 10)
            self.gray_bg(x + 0.3, y + 0.3, cw[i] - 0.6, 9.4)
            self.set_font("Calibri", "B", 10)
            self.set_text_color(0)
            # multiline header
            for li, part in enumerate(h.split("\n")):
                self.text(x + 1.5, y + 4 + li * 3, part)
            x += cw[i]
        y += 10

        earth_rows = [
            ("CAVO NON SEPARABILE/\nISTALLAZIONE FISSA", "R tra connettore di terra del cavo e  parti\nmetalliche accessibili", "300", 12),
            ("", "R cavo singolo", "100", 7),
            ("CAVO SEPARABILE", "R tra morsetto di terra di protezione e\nparti metalliche accessibili", "200", 12),
            ("", "R tra connettore di terra dela spina e parti\naccessibili", "300", 10),
            ("CON PRESA MULTIPLA\n(SISTEMA EM)", "R tra il connettore di terra di protezione\ndell'alimentazione principale della presa\nmultipla e tutte le parti conduttive\naccessibili", "500", 16),
        ]

        # Posizione resistenza di terra: indice riga nel modulo
        # 0=Cavo non separabile (300), 1=Cavo singolo (100),
        # 2=Morsetto terra (200), 3=Connettore spina (300), 4=Presa multipla (500)
        if is_permanent_three_measure_template(self.data):
            earth_row_idx = 0
        else:
            earth_pos_val = self.ed.get("earthResPos", EARTH_RES_POSITIONS[3])
            if earth_pos_val in EARTH_RES_POSITIONS:
                earth_row_idx = EARTH_RES_POSITIONS.index(earth_pos_val)
            else:
                try:
                    earth_row_idx = int(earth_pos_val)
                except (ValueError, TypeError):
                    earth_row_idx = 3

        # Converti valore da Ohm a mOhm per il modulo
        earth_mohm = ""
        if earth:
            try:
                val_f = float(earth["value"])
                if earth["unit"] == "Ohm":
                    earth_mohm = f"{val_f * 1000:.0f} mOhm"
                else:
                    earth_mohm = f"{earth['value']} {earth['unit']}"
            except ValueError:
                earth_mohm = f"{earth['value']} {earth['unit']}"

        self.set_font("Calibri", "", 10)
        for ri, (cat, desc, limit, rh) in enumerate(earth_rows):
            x = ML
            for ci in range(len(cw)):
                self.rect(x, y, cw[ci], rh)
                if ci == 0 and cat:
                    for li, part in enumerate(cat.split("\n")):
                        self.text(x + 1.5, y + 3.5 + li * 3, part)
                if ci == 1:
                    for li, part in enumerate(desc.split("\n")):
                        self.text(x + 1.5, y + 3.5 + li * 3, part)
                if ci == 3:
                    self.text(x + cw[ci] / 2 - 2, y + rh / 2 + 1, limit)
                if ci == 2 and earth and ri == earth_row_idx and self.ed["classe"] == "I":
                    self.text(x + 2, y + rh / 2 + 1, earth_mohm)
                if ci >= 4:
                    self.draw_box(x + cw[ci] / 2 - 1.5, y + rh / 2 - 1.5)
                if ci == 4 and earth and earth["status"] == "Passed" and ri == earth_row_idx and self.ed["classe"] == "I":
                    self.set_font("Calibri", "B", 10)
                    self.text(x + cw[ci] / 2 - 1, y + rh / 2 + 1, "X")
                    self.set_font("Calibri", "", 10)
                x += cw[ci]
            y += rh
        y += 3

        # Correnti di dispersione
        lk = [PW * 0.22, PW * 0.27, PW * 0.18, PW * 0.06, PW * 0.06, PW * 0.06, PW * 0.05, PW * 0.05, PW * 0.05]
        self.set_font("Calibri", "B", 10)

        # Header row 1
        x = ML
        self.rect(x, y, lk[0], 14)
        self.gray_bg(x + 0.3, y + 0.3, lk[0] - 0.6, 13.4)
        self.text(x + 1, y + 6, "Correnti di")
        self.text(x + 1, y + 9, "dispersione")
        x += lk[0]
        self.rect(x, y, lk[1], 14)
        self.gray_bg(x + 0.3, y + 0.3, lk[1] - 0.6, 13.4)
        self.text(x + 2, y + 8, "Metodo di misura")
        x += lk[1]
        self.rect(x, y, lk[2], 14)
        self.gray_bg(x + 0.3, y + 0.3, lk[2] - 0.6, 13.4)
        self.text(x + 2, y + 8, "Misura")
        x += lk[2]
        paW = lk[3] + lk[4] + lk[5]
        self.rect(x, y, paW, 8)
        self.gray_bg(x + 0.3, y + 0.3, paW - 0.6, 7.4)
        self.text(x + 2, y + 4, "Valori ammissibili")
        self.text(x + 2, y + 7, "P.A. (uA)")
        x += paW
        self.rect(x, y, lk[6], 14)
        self.gray_bg(x + 0.3, y + 0.3, lk[6] - 0.6, 13.4)
        self.text(x + 2, y + 8, "OK")
        x += lk[6]
        self.rect(x, y, lk[7], 14)
        self.gray_bg(x + 0.3, y + 0.3, lk[7] - 0.6, 13.4)
        self.text(x + 2, y + 8, "KO")
        x += lk[7]
        self.rect(x, y, lk[8], 14)
        self.gray_bg(x + 0.3, y + 0.3, lk[8] - 0.6, 13.4)
        self.text(x + 2, y + 8, "NA")
        y += 8

        # Sub header B BF CF
        x = ML + lk[0] + lk[1] + lk[2]
        self.rect(x, y, lk[3], 6)
        self.gray_bg(x + 0.3, y + 0.3, lk[3] - 0.6, 5.4)
        self.text(x + lk[3] / 2 - 1, y + 4, "B")
        x += lk[3]
        self.rect(x, y, lk[4], 6)
        self.gray_bg(x + 0.3, y + 0.3, lk[4] - 0.6, 5.4)
        self.text(x + lk[4] / 2 - 2, y + 4, "BF")
        x += lk[4]
        self.rect(x, y, lk[5], 6)
        self.gray_bg(x + 0.3, y + 0.3, lk[5] - 0.6, 5.4)
        self.text(x + lk[5] / 2 - 2, y + 4, "CF")
        y += 6

        oe = self.find_meas("Open Earth")
        oer = self.find_meas("Open Earth-Reversed Mains")
        ap_nc = self.find_meas_by_parent("Direct Applied Part Leakage", "Normal Condition")
        is_direct = "Diretto" in self.data.get("templateName", "")
        h = 7

        # APPARECCHIO
        self.rect(ML, y, lk[0], h * 5)
        self.set_font("Calibri", "B", 10)
        self.text(ML + 1, y + 8, "APPARECCHIO")
        self.set_font("Calibri", "", 10)
        self.text(ML + 1, y + 12, "(non applicabile a EM")
        self.text(ML + 1, y + 15, "con sorgente elettrica")
        self.text(ML + 1, y + 18, "interna)")
        self.set_font("Calibri", "", 10)

        def worst(a, b):
            if not a:
                return ""
            v = float(a["value"]) if a["value"] else 0
            if b and b["value"]:
                v = max(v, float(b["value"]))
            return f"{v} {a['unit']}"

        eq1 = worst(oe, oer) if self.ed["classe"] == "I" else ""
        eq2 = worst(oe, oer) if self.ed["classe"] == "II" else ""

        # DIRETTO
        x = ML + lk[0]
        self.set_font("Calibri", "B", 10)
        self.rect(x, y, PW - lk[0], h)
        self.text(x + 2, y + 5, "DIRETTO/DIFFERENZIALE")
        y += h
        self.set_font("Calibri", "", 10)

        self._leak_row(ML, y, lk, PW, "Apparecchi Classe I", eq1 if is_direct else "", "500", "500", "500",
                       is_direct and self.ed["classe"] == "I" and oe and oe["status"] == "Passed", h)
        y += h
        self._leak_row(ML, y, lk, PW, "Apparecchio Classe II", eq2 if is_direct else "", "100", "100", "100",
                       is_direct and self.ed["classe"] == "II" and oe and oe["status"] == "Passed", h)
        y += h

        # ALTERNATIVO
        x = ML + lk[0]
        self.set_font("Calibri", "B", 10)
        self.rect(x, y, PW - lk[0], h)
        self.text(x + 2, y + 5, "ALTERNATIVO")
        y += h
        self.set_font("Calibri", "", 10)

        self._leak_row(ML, y, lk, PW, "Apparecchi Classe I", eq1 if not is_direct else "", "1000", "1000", "1000", False, h)
        y += h
        self._leak_row(ML, y, lk, PW, "Apparecchio Classe II", eq2 if not is_direct else "", "500", "500", "500", False, h)
        y += h

        # PARTE APPLICATA
        self.set_font("Calibri", "B", 10)
        self.rect(ML, y, lk[0], h * 4)
        self.text(ML + 1, y + 8, "PARTE APPLICATA")
        self.set_font("Calibri", "", 10)

        x = ML + lk[0]
        self.set_font("Calibri", "B", 10)
        self.rect(x, y, PW - lk[0], h)
        self.text(x + 2, y + 5, "DIRETTO")
        y += h
        self.set_font("Calibri", "", 10)

        ap_val = f"{ap_nc['value']} {ap_nc['unit']}" if ap_nc else ""
        self._leak_row(ML, y, lk, PW, "Apparecchi Classe I, II, A.I.", ap_val if is_direct else "", "--", "5000", "50",
                       is_direct and ap_nc and ap_nc["status"] == "Passed", h)
        y += h

        x = ML + lk[0]
        self.set_font("Calibri", "B", 10)
        self.rect(x, y, PW - lk[0], h)
        self.text(x + 2, y + 5, "ALTERNATIVO")
        y += h
        self.set_font("Calibri", "", 10)

        self._leak_row(ML, y, lk, PW, "Apparecchi Classe I, II, A.I.", ap_val if not is_direct else "", "--", "5000", "50", False, h)
        y += h + 3

        # Resistenza di isolamento
        self.set_font("Calibri", "B", 10)
        ic = [PW * 0.475, PW * 0.375, PW * 0.05, PW * 0.05, PW * 0.05]
        for i, hdr in enumerate(["Resistenza di isolamento", "Misura", "OK", "KO", "NA"]):
            ix = ML + sum(ic[:i])
            self.rect(ix, y, ic[i], 7)
            self.gray_bg(ix + 0.3, y + 0.3, ic[i] - 0.6, 6.4)
            self.text(ix + 2, y + 5, hdr)
        y += 7
        self.set_font("Calibri", "", 10)

        ins_pe = self.find_meas("Mains to Protective Earth")
        ins_ap = self.find_meas("Mains to Applied Parts")
        ins_ne = self.find_meas("Applied Parts to Non-Earth")

        for label, meas in [("RETE - INVOLUCRO", ins_pe or ins_ap), ("INVOLUCRO - PARTE APPLICATA", ins_ne)]:
            x = ML
            self.rect(x, y, ic[0], 7)
            self.text(x + 2, y + 5, label)
            x += ic[0]
            self.rect(x, y, ic[1], 7)
            if meas:
                self.text(x + 2, y + 5, f"{meas['value']} {meas['unit']}")
            x += ic[1]
            self.rect(x, y, ic[2], 7)
            self.draw_box(x + ic[2] / 2 - 1.5, y + 2)
            if meas and meas["status"] == "Passed":
                self.set_font("Calibri", "B", 10)
                self.text(x + ic[2] / 2 - 1, y + 4.5, "X")
                self.set_font("Calibri", "", 10)
            x += ic[2]
            self.rect(x, y, ic[3], 7)
            self.draw_box(x + ic[3] / 2 - 1.5, y + 2)
            x += ic[3]
            self.rect(x, y, ic[4], 7)
            self.draw_box(x + ic[4] / 2 - 1.5, y + 2)
            y += 7

        y += 3

        # PROVE DI FUNZIONALITA'
        self.set_font("Calibri", "B", 10)
        self.text(ML, y, "PROVE DI FUNZIONALITA'")
        y += 2

        fc = [PW - 30, 10, 10, 10]
        self.set_font("Calibri", "B", 10)
        x = ML
        for i, hdr in enumerate(["Descrizione attivita'", "OK", "KO", "NA"]):
            self.rect(x, y, fc[i], 7)
            self.gray_bg(x + 0.3, y + 0.3, fc[i] - 0.6, 6.4)
            self.text(x + 2, y + 5, hdr)
            x += fc[i]
        y += 7

        self.set_font("Calibri", "", 10)
        funz_acc = self.ed.get("funz_accensione", "")
        x = ML
        self.rect(x, y, fc[0], 7)
        self.text(x + 2, y + 5, "Accensione e verifica generica di funzionamento")
        for ci, col_val in enumerate(["OK", "KO", "NA"]):
            x += fc[ci]
            cw_f = fc[ci + 1]
            self.rect(x, y, cw_f, 7)
            bx = x + cw_f / 2 - 1.5
            by = y + 2
            self.draw_box(bx, by)
            if funz_acc == col_val:
                self.set_font("Calibri", "B", 10)
                self.text(bx + 0.5, by + 2.5, "X")
                self.set_font("Calibri", "", 10)
        y += 7

        funz_pp = self.ed.get("funz_prova_part", "")
        codice_prot = self.ed.get("funz_codice_prot", "")
        normativa = self.ed.get("funz_normativa", "")
        self.rect(ML, y, fc[0], 7)
        self.text(ML + 2, y + 5, "Prova particolare")
        for ci, col_val in enumerate(["OK", "KO", "NA"]):
            cx = ML + fc[0] + ci * fc[ci + 1]
            cw_f = fc[ci + 1]
            self.rect(cx, y, cw_f, 7)
            bx = cx + cw_f / 2 - 1.5
            by = y + 2
            self.draw_box(bx, by)
            if funz_pp == col_val:
                self.set_font("Calibri", "B", 10)
                self.text(bx + 0.5, by + 2.5, "X")
                self.set_font("Calibri", "", 10)
        y += 7

        self.rect(ML, y, PW, 7)
        codice_txt = codice_prot if codice_prot else "________________"
        norm_txt = normativa if normativa else "_____________"
        self.text(ML + 2, y + 5, f"Codice Protocollo: {codice_txt}    Normativa di riferimento: {norm_txt}")
        y += 10

        self.set_font("Calibri", "", 7)
        self.text(ML, y, "OK = OPERAZIONE ESEGUITA CON ESITO POSITIVO")
        self.text(ML, y + 3.5, "KO = OPERAZIONE ESEGUITA CON ESITO NEGATIVO (INDICARE I MOTIVI NELLE NOTE)")
        self.text(ML, y + 7, "NA = OPERAZIONE NON APPLICABILE / NON PERTINENTE")

    def _leak_row(self, ML, y, lk, PW, label, measure, limB, limBF, limCF, ok, h):
        x = ML + lk[0]
        self.rect(x, y, lk[1], h)
        self.text(x + 2, y + h / 2 + 1, label)
        x += lk[1]
        self.rect(x, y, lk[2], h)
        if measure:
            self.text(x + 2, y + h / 2 + 1, measure)
        x += lk[2]
        self.rect(x, y, lk[3], h)
        self.text(x + lk[3] / 2 - 2, y + h / 2 + 1, limB)
        x += lk[3]
        self.rect(x, y, lk[4], h)
        self.text(x + lk[4] / 2 - 2, y + h / 2 + 1, limBF)
        x += lk[4]
        self.rect(x, y, lk[5], h)
        self.text(x + lk[5] / 2 - 2, y + h / 2 + 1, limCF)
        x += lk[5]
        self.rect(x, y, lk[6], h)
        self.draw_box(x + lk[6] / 2 - 1.5, y + h / 2 - 1.5)
        if ok:
            self.set_font("Calibri", "B", 10)
            self.text(x + lk[6] / 2 - 1, y + h / 2 + 1, "X")
            self.set_font("Calibri", "", 10)
        x += lk[6]
        self.rect(x, y, lk[7], h)
        self.draw_box(x + lk[7] / 2 - 1.5, y + h / 2 - 1.5)
        x += lk[7]
        self.rect(x, y, lk[8], h)
        self.draw_box(x + lk[8] / 2 - 1.5, y + h / 2 - 1.5)

    def draw_page3(self):
        ML = 15
        PW = 180
        W = 210
        y = 15

        self.set_font("Calibri", "B", 10)
        self.set_text_color(0)
        self.text(ML, y, "STRUMENTI DI VERIFICA UTILIZZATI")
        y += 2

        sc = [PW * 0.2] * 5
        headers = ["Strumento", "Produttore", "Modello", "Matricola", "Data ultima taratura"]
        x = ML
        self.set_font("Calibri", "B", 10)
        self.set_text_color(0)
        for i in range(5):
            self.rect(x, y, sc[i], 7)
            self.gray_bg(x + 0.3, y + 0.3, sc[i] - 0.6, 6.4)
            self.text(x + 2, y + 5, headers[i])
            x += sc[i]
        y += 7

        instr = self.data.get("instrument", {})
        cal_date = convert_date_to_dmy(instr.get("calibrationDate", ""))
        vals = [instr.get("type", "ESA615"), "Fluke Biomedical", instr.get("type", "ESA615"),
                instr.get("serialNumber", ""), cal_date]
        self.set_font("Calibri", "", 10)
        x = ML
        for i in range(5):
            self.rect(x, y, sc[i], 7)
            self.text(x + 2, y + 5, vals[i])
            x += sc[i]
        y += 7

        # Empty row
        x = ML
        for i in range(5):
            self.rect(x, y, sc[i], 7)
            x += sc[i]
        y += 12

        # NOTE
        self.set_font("Calibri", "B", 10)
        self.text(ML, y, "NOTE")
        y += 2
        self.rect(ML, y, PW, 55)

        note_text = self.ed.get("note", "")
        if note_text:
            self.set_font("Calibri", "", 10)
            ny = y + 5
            for line in note_text.split("\n"):
                if ny >= y + 52:
                    break
                self.text(ML + 3, ny, line)
                ny += 4
        y += 59

        # ESITO
        self.set_font("Calibri", "B", 10)
        self.text(ML, y, "ESITO")
        y += 2
        self.rect(ML, y, PW, 10)
        is_passed = self.data.get("overallStatus") == "Passed"
        self.set_font("Calibri", "", 10)
        self.draw_checkbox(ML + 5, y + 5, is_passed, "Positivo")
        self.draw_checkbox(ML + 45, y + 5, not is_passed, "Negativo")
        self.draw_checkbox(ML + 85, y + 5, False, "Apparecchiatura da revisionare/ necessita manutenzione")
        y += 18

        # Data e Firma
        self.set_font("Calibri", "B", 10)
        self.text(ML, y, "Data")
        self.text(W - 75, y, "Nome e Firma Tecnico Esecutore")
        y += 4

        # Immagine firma
        firma_path = self.ed.get("firma_path", "")
        firma_x = W - 75
        firma_y = y
        if firma_path and os.path.isfile(firma_path):
            try:
                self.image(firma_path, x=firma_x, y=firma_y, h=15)
            except Exception:
                pass  # se l'immagine non e' supportata, salta
        firma_y += 16

        # Prima linea firma
        self.line(firma_x, firma_y, W - ML, firma_y)

        # Nome in stampatello sotto la prima linea
        tecnico = self.ed.get("tecnico", "")
        if tecnico:
            self.set_font("Calibri", "B", 10)
            self.text(firma_x, firma_y + 4, tecnico.upper())

        # Seconda linea firma
        firma_y += 8
        self.line(firma_x, firma_y, W - ML, firma_y)

        # Data
        self.set_font("Calibri", "", 10)
        td = self.data.get("testDate", "")
        if td:
            parts = td.split("/")
            if len(parts) == 3:
                self.text(ML, y + 6, f"{parts[0]} / {parts[1]} / {parts[2]}")
        else:
            self.text(ML, y + 6, "___ /___ /_____")


def generate_pdf(data, edited, output_path):
    """Genera un singolo PDF."""
    edited = apply_template_defaults(data, edited)
    pdf = SchedaPDF(data, edited)
    pdf.generate()
    pdf.output(output_path)


def convert_date_to_dmy(date_str):
    """Converte data da mm/dd/yyyy a dd/mm/yyyy."""
    if not date_str:
        return date_str
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", date_str.strip())
    if m:
        mm, dd, yyyy = m.group(1), m.group(2), m.group(3)
        # Se il mese e' > 12 probabilmente e' gia' dd/mm/yyyy
        if int(mm) > 12:
            return date_str
        return f"{dd}/{mm}/{yyyy}"
    return date_str


def sanitize_filename(s):
    s = re.sub(r"[^a-zA-Z0-9_\-. ]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s[:50] if s else "unknown"


# ======================== GUI ========================

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("ESA615 - Generatore Schede VS Generale (V2)")
        self.root.geometry("1050x700")
        self.root.minsize(800, 500)

        self.parsed_files = []
        self.output_dir = ""
        self._last_firma_path = ""
        self._last_tecnico = ""
        self._last_proprieta = ""
        self._firma_tk_image = None  # keep reference to prevent GC

        self._build_ui()

    def _build_ui(self):
        # Top bar
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Button(top, text="Carica file .mtr/.csv", command=self.load_files).pack(side="left", padx=(0, 5))
        ttk.Button(top, text="Carica cartella", command=self.load_folder).pack(side="left", padx=(0, 5))
        ttk.Button(top, text="Genera tutti i PDF", command=self.generate_all).pack(side="left", padx=(0, 5))
        ttk.Button(top, text="Cancella tutto", command=self.clear_all).pack(side="left", padx=(0, 5))

        self.status_var = tk.StringVar(value="Nessun file caricato")
        ttk.Label(top, textvariable=self.status_var).pack(side="right", padx=(8, 0))
        self.pdf_progress_var = tk.DoubleVar(value=0)
        self.pdf_progress = ttk.Progressbar(
            top,
            variable=self.pdf_progress_var,
            maximum=100,
            mode="determinate",
            length=190,
        )
        self.pdf_progress.pack(side="right", padx=(8, 0))

        # Main area: list + detail
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Left: file list
        left = ttk.LabelFrame(paned, text="File caricati", padding=5)
        paned.add(left, weight=1)

        self.file_listbox = tk.Listbox(left, font=("Segoe UI", 9))
        self.file_listbox.pack(fill="both", expand=True)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_select)

        # Right: detail/edit
        right = ttk.LabelFrame(paned, text="Dettaglio e modifica", padding=5)
        paned.add(right, weight=2)

        canvas = tk.Canvas(right)
        scrollbar = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        self.detail_frame = ttk.Frame(canvas)

        self.detail_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.detail_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.fields = {}

    def _set_pdf_progress(self, current, total, message=None):
        total = max(int(total or 1), 1)
        current = max(0, min(int(current), total))
        self.pdf_progress.configure(maximum=total)
        self.pdf_progress_var.set(current)
        if message is not None:
            self.status_var.set(message)
        self.root.update_idletasks()

    def _browse_firma(self):
        path = filedialog.askopenfilename(
            title="Seleziona immagine firma",
            filetypes=[("Immagini", "*.png *.jpg *.jpeg *.bmp *.gif"), ("Tutti i file", "*.*")]
        )
        if path:
            self.firma_path_var.set(path)
            self._last_firma_path = path
            self._update_firma_preview()

    def _clear_firma(self):
        self.firma_path_var.set("")
        self._last_firma_path = ""
        self._update_firma_preview()

    def _update_firma_preview(self):
        path = self.firma_path_var.get() if hasattr(self, 'firma_path_var') else ""
        if not hasattr(self, 'firma_preview_label'):
            return
        if path and os.path.isfile(path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(path)
                # Resize for preview: max 200x60
                img.thumbnail((200, 60))
                self._firma_tk_image = ImageTk.PhotoImage(img)
                self.firma_preview_label.configure(image=self._firma_tk_image, text="")
            except ImportError:
                self.firma_preview_label.configure(image="", text=f"  (anteprima non disponibile - installa Pillow)")
            except Exception:
                self.firma_preview_label.configure(image="", text=f"  (errore caricamento immagine)")
        else:
            self._firma_tk_image = None
            self.firma_preview_label.configure(image="", text="  Nessuna firma caricata" if not path else "")

    def load_files(self):
        paths = filedialog.askopenfilenames(
            title="Seleziona file .mtr o .csv",
            filetypes=[("File ESA615", "*.mtr *.csv"), ("Tutti i file", "*.*")]
        )
        if paths:
            self._parse_and_add(paths)

    def load_folder(self):
        folder = filedialog.askdirectory(title="Seleziona cartella con file .mtr/.csv")
        if folder:
            paths = []
            for f in os.listdir(folder):
                if f.lower().endswith((".mtr", ".csv")):
                    paths.append(os.path.join(folder, f))
            if paths:
                self._parse_and_add(paths)
            else:
                messagebox.showinfo("Info", "Nessun file .mtr o .csv trovato nella cartella.")

    def _parse_and_add(self, paths):
        existing_bases = {os.path.splitext(d["sourceFile"])[0] for d in self.parsed_files}
        added = 0
        for p in paths:
            base = os.path.splitext(os.path.basename(p))[0]
            if base in existing_bases:
                continue
            try:
                if p.lower().endswith(".mtr"):
                    data = parse_mtr(p)
                else:
                    data = parse_csv(p)
                self.parsed_files.append(data)
                existing_bases.add(base)
                added += 1
            except Exception as e:
                print(f"Errore parsing {p}: {e}")

        self._refresh_list()
        self.status_var.set(f"{len(self.parsed_files)} file caricati ({added} nuovi)")

    def _refresh_list(self):
        self.file_listbox.delete(0, tk.END)
        for d in self.parsed_files:
            mfg = (d.get("manufacturer") or "").upper()
            mod = (d.get("model") or "").upper()
            sn = d.get("serialNumber") or d.get("equipmentNumber") or ""
            status = "OK" if d.get("overallStatus") == "Passed" else "KO"
            self.file_listbox.insert(tk.END, f"[{status}] {mfg} {mod} ({sn}) - {d['sourceFile']}")

    def on_select(self, event):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self._show_detail(idx)

    def _show_detail(self, idx):
        # Save tecnico name before clearing (persist across selections)
        if "proprieta" in self.fields:
            self._last_proprieta = self.fields["proprieta"].get()
        if "tecnico" in self.fields:
            self._last_tecnico = self.fields["tecnico"].get()
        if hasattr(self, 'firma_path_var'):
            self._last_firma_path = self.firma_path_var.get()

        # Clear
        for w in self.detail_frame.winfo_children():
            w.destroy()
        self.fields = {}

        data = self.parsed_files[idx]
        saved = apply_template_defaults(data, data.get("_edited", {}))

        def add_field(parent, label, key, default=""):
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=label, width=22, anchor="e").pack(side="left")
            val = saved.get(key, default)
            var = tk.StringVar(value=val)
            ttk.Entry(row, textvariable=var, width=40).pack(side="left", padx=(5, 0), fill="x", expand=True)
            self.fields[key] = var

        def add_combo(parent, label, key, values, default=""):
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=label, width=22, anchor="e").pack(side="left")
            val = saved.get(key, default)
            var = tk.StringVar(value=val)
            cb = ttk.Combobox(row, textvariable=var, values=values, state="readonly", width=10)
            cb.pack(side="left", padx=(5, 0))
            self.fields[key] = var

        cls = default_class(data)

        ttk.Label(self.detail_frame, text="DATI IDENTIFICATIVI", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(5, 5))
        add_field(self.detail_frame, "Tipologia Apparecchio:", "tipologia", data.get("tipologia") or data.get("other", ""))
        add_field(self.detail_frame, "Produttore:", "manufacturer", data.get("manufacturer", ""))
        add_field(self.detail_frame, "Modello:", "model", data.get("model", ""))
        add_field(self.detail_frame, "Matricola:", "serial", data.get("serialNumber") or data.get("equipmentNumber", ""))
        add_field(self.detail_frame, "Codice CIVAB:", "civab", "")
        add_field(self.detail_frame, "Proprieta':", "proprieta", self._last_proprieta)
        add_field(self.detail_frame, "N. Inv. Gestionale:", "invGest", data.get("equipmentNumber", ""))
        add_field(self.detail_frame, "N. Inv. Ente:", "invEnte", "")
        add_field(self.detail_frame, "Presidio:", "presidio", data.get("location", ""))
        add_field(self.detail_frame, "Reparto:", "reparto", "")
        add_field(self.detail_frame, "Stanza:", "stanza", "")
        add_combo(self.detail_frame, "Periodicita':", "periodicita", ["12 mesi", "24 mesi"], "12 mesi")
        add_combo(self.detail_frame, "Classe:", "classe", ["I", "II", "AI"], cls)
        add_combo(self.detail_frame, "Parti Applicate:", "apType", ["B", "BF", "CF"], data.get("apType", "B"))

        ttk.Label(self.detail_frame, text="DATI TECNICI", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        add_combo(self.detail_frame, "Tipo installazione:", "installazione",
                  ["Permanente", "Non permanente"], default_installation(data))
        add_combo(self.detail_frame, "Mobilita':", "mobilita",
                  ["Fisso", "Spostabile", "Trasportabile", "Portatile", "Stazionario"], default_mobility(data))
        add_field(self.detail_frame, "Tensione [V]:", "tensione", "220")
        add_field(self.detail_frame, "Frequenza [Hz]:", "frequenza", "50")
        pot_row = ttk.Frame(self.detail_frame)
        pot_row.pack(fill="x", pady=1)
        ttk.Label(pot_row, text="Potenza:", width=22, anchor="e").pack(side="left")
        pot_var = tk.StringVar(value=saved.get("potenza", ""))
        ttk.Entry(pot_row, textvariable=pot_var, width=15).pack(side="left", padx=(5, 0))
        self.fields["potenza"] = pot_var
        pot_unit_var = tk.StringVar(value=saved.get("potenza_unit", "W"))
        ttk.Combobox(pot_row, textvariable=pot_unit_var, values=["W", "A", "VA"], state="readonly", width=5).pack(side="left", padx=(5, 0))
        self.fields["potenza_unit"] = pot_unit_var
        add_combo(self.detail_frame, "Protezione:", "protezione",
                  ["Magnetotermico", "Magnetotermico Differenziale", "Termico",
                   "Trasformatore di isolamento", "Fusibili", "Altro"],
                  "Trasformatore di isolamento")
        add_combo(self.detail_frame, "Fusibili conformita':", "fusibili_conformita",
                  ["", "conformi", "non conformi", "senza dati"], "")
        add_field(self.detail_frame, "Dati di Targa fusibili:", "dati_targa_fusibili", "")
        add_field(self.detail_frame, "Valore nom. dispositivo:", "valore_nominale", "")
        add_field(self.detail_frame, "Protezione Altro:", "protezione_altro", "")

        ttk.Label(self.detail_frame, text="ESAME A VISTA", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        vista_items = [
            ("Integrita' targa/etichetta:", "vista_targa"),
            ("Integrita' telaio/involucro:", "vista_telaio"),
            ("Parti in movimento:", "vista_parti_mov"),
            ("Cavo/spina alimentazione:", "vista_cavo"),
            ("Blocca cavo/passacavo:", "vista_passacavo"),
            ("Spie/interruttori:", "vista_spie"),
            ("Parti applicate/accessori:", "vista_parti_appl"),
            ("Documentazione d'uso:", "vista_doc"),
        ]
        for label, key in vista_items:
            add_combo(self.detail_frame, label, key, ["OK", "KO", "NA"], "OK")

        ttk.Label(self.detail_frame, text="TECNICO ESECUTORE", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        add_field(self.detail_frame, "Nome e Cognome:", "tecnico", self._last_tecnico)

        # Firma immagine
        firma_row = ttk.Frame(self.detail_frame)
        firma_row.pack(fill="x", pady=1)
        ttk.Label(firma_row, text="Immagine firma:", width=22, anchor="e").pack(side="left")
        self.firma_path_var = tk.StringVar(value=saved.get("firma_path", self._last_firma_path))
        ttk.Entry(firma_row, textvariable=self.firma_path_var, width=30, state="readonly").pack(side="left", padx=(5, 0), fill="x", expand=True)
        ttk.Button(firma_row, text="Sfoglia...", command=self._browse_firma).pack(side="left", padx=(5, 0))
        ttk.Button(firma_row, text="Rimuovi", command=self._clear_firma).pack(side="left", padx=(2, 0))

        # Anteprima firma
        self.firma_preview_label = ttk.Label(self.detail_frame)
        self.firma_preview_label.pack(anchor="w", pady=(2, 5))
        self._update_firma_preview()

        self.fields["firma_path"] = self.firma_path_var

        ttk.Label(self.detail_frame, text="OPZIONI MISURE", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        row = ttk.Frame(self.detail_frame)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text="Posiz. Res. Terra:", width=22, anchor="e").pack(side="left")
        earth_var = tk.StringVar(value=saved.get("earthResPos", default_earth_res_pos(data)))
        earth_cb = ttk.Combobox(row, textvariable=earth_var, values=EARTH_RES_POSITIONS, state="readonly", width=70)
        earth_cb.pack(side="left", padx=(5, 0), fill="x", expand=True)
        self.fields["earthResPos"] = earth_var

        ttk.Label(self.detail_frame, text="PROVE DI FUNZIONALITA'", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        add_combo(self.detail_frame, "Accensione/funzionamento:", "funz_accensione", ["", "OK", "KO", "NA"], "")
        add_field(self.detail_frame, "Codice Protocollo:", "funz_codice_prot", "")
        add_field(self.detail_frame, "Normativa di riferimento:", "funz_normativa", "")
        add_combo(self.detail_frame, "Prova particolare:", "funz_prova_part", ["", "OK", "KO", "NA"], "")

        ttk.Label(self.detail_frame, text="NOTE", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        note_var = tk.StringVar(value=saved.get("note", ""))
        note_text = tk.Text(self.detail_frame, height=4, width=60, font=("Segoe UI", 9))
        note_text.insert("1.0", saved.get("note", ""))
        note_text.pack(fill="x", pady=(0, 5))
        self.fields["note"] = note_text

        # Results table
        ttk.Label(self.detail_frame, text="RISULTATI TEST", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))

        cols = ("Test", "Valore", "Unita'", "Esito")
        tree = ttk.Treeview(self.detail_frame, columns=cols, show="headings", height=min(12, len(data.get("measurements", []))))
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=120 if c == "Test" else 70)
        for m in data.get("measurements", []):
            tag = "pass" if m["status"] == "Passed" else "fail"
            tree.insert("", "end", values=(m["description"], m["value"], m["unit"], "OK" if m["status"] == "Passed" else "KO"), tags=(tag,))
        tree.tag_configure("pass", foreground="green")
        tree.tag_configure("fail", foreground="red")
        tree.pack(fill="x", pady=5)

        # Buttons
        btn_frame = ttk.Frame(self.detail_frame)
        btn_frame.pack(fill="x", pady=10)
        ttk.Button(btn_frame, text="Salva modifiche", command=lambda: self.save_to_source(idx)).pack(side="left", padx=(0, 5))
        ttk.Button(btn_frame, text="Genera PDF per questo file", command=lambda: self.generate_one(idx)).pack(side="left", padx=(0, 5))
        ttk.Button(btn_frame, text="Rimuovi", command=lambda: self.remove_file(idx)).pack(side="left")

    def save_to_source(self, idx):
        if not self.fields:
            messagebox.showwarning("Attenzione", "Seleziona un file dalla lista.")
            return

        data = self.parsed_files[idx]
        edited = apply_template_defaults(data, self._get_edited())
        self._last_proprieta = edited.get("proprieta", "")
        filepath = data.get("sourceFilePath", "")

        if not filepath or not os.path.isfile(filepath):
            messagebox.showerror("Errore", f"File sorgente non trovato:\n{filepath}")
            return

        try:
            if filepath.lower().endswith(".mtr"):
                save_mtr(filepath, edited)
            else:
                save_csv(filepath, edited)

            # Re-parse per aggiornare i dati in memoria
            if filepath.lower().endswith(".mtr"):
                new_data = parse_mtr(filepath)
            else:
                new_data = parse_csv(filepath)
            # Preserva i campi editati che non esistono nel file sorgente
            new_data["_edited"] = edited
            self.parsed_files[idx] = new_data
            self._refresh_list()
            self._show_detail(idx)
            self.file_listbox.selection_set(idx)

            messagebox.showinfo("Successo", f"Modifiche salvate in:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nel salvataggio:\n{e}")

    def _get_edited(self):
        result = {}
        for k, v in self.fields.items():
            if isinstance(v, tk.Text):
                result[k] = v.get("1.0", "end-1c")
            else:
                result[k] = v.get()
        return result

    def _ask_output_dir(self):
        d = filedialog.askdirectory(title="Seleziona cartella di destinazione per i PDF")
        return d

    def generate_one(self, idx):
        if not self.fields:
            messagebox.showwarning("Attenzione", "Seleziona un file dalla lista.")
            return

        out_dir = self._ask_output_dir()
        if not out_dir:
            return

        data = self.parsed_files[idx]
        edited = apply_template_defaults(data, self._get_edited())
        self._last_proprieta = edited.get("proprieta", "")

        tip = sanitize_filename(edited.get("tipologia", "") or "apparecchio")
        mfg = sanitize_filename(edited.get("manufacturer", "") or "produttore")
        mod = sanitize_filename(edited.get("model", "") or "modello")
        ser = sanitize_filename(edited.get("serial", "") or "matricola")
        filename = f"{tip}-{mfg}-{mod}-{ser}.pdf"
        out_path = os.path.join(out_dir, filename)

        try:
            self._set_pdf_progress(0, 1, f"Generazione PDF: {data['sourceFile']}")
            generate_pdf(data, edited, out_path)
            self._set_pdf_progress(1, 1, "PDF generato")
            messagebox.showinfo("Successo", f"PDF generato:\n{out_path}")
        except Exception as e:
            self._set_pdf_progress(0, 1, "Errore nella generazione PDF")
            messagebox.showerror("Errore", f"Errore nella generazione:\n{e}")

    def generate_all(self):
        if not self.parsed_files:
            messagebox.showwarning("Attenzione", "Nessun file caricato.")
            return

        # Aggiorna tecnico/firma dal file correntemente selezionato
        if "proprieta" in self.fields:
            self._last_proprieta = self.fields["proprieta"].get()
        if "tecnico" in self.fields:
            self._last_tecnico = self.fields["tecnico"].get()
        if hasattr(self, 'firma_path_var'):
            self._last_firma_path = self.firma_path_var.get()

        out_dir = self._ask_output_dir()
        if not out_dir:
            return

        ok_count = 0
        errors = []
        total_files = len(self.parsed_files)
        self._set_pdf_progress(0, total_files, f"Generazione PDF 0/{total_files}")
        for i, data in enumerate(self.parsed_files):
            self._set_pdf_progress(
                i,
                total_files,
                f"Generazione PDF {i + 1}/{total_files}: {data['sourceFile']}",
            )
            # Build edited data from parsed values (defaults)
            cls = default_class(data)
            edited = {
                "tipologia": data.get("tipologia") or data.get("other", ""),
                "manufacturer": data.get("manufacturer", ""),
                "model": data.get("model", ""),
                "serial": data.get("serialNumber") or data.get("equipmentNumber", ""),
                "civab": "",
                "proprieta": self._last_proprieta,
                "invGest": data.get("equipmentNumber", ""),
                "invEnte": "",
                "presidio": data.get("location", ""),
                "reparto": "",
                "stanza": "",
                "periodicita": "12 mesi",
                "classe": cls,
                "apType": data.get("apType", "B"),
                "installazione": default_installation(data),
                "mobilita": default_mobility(data),
                "tensione": "220",
                "frequenza": "50",
                "potenza": "",
                "potenza_unit": "W",
                "protezione": "Trasformatore di isolamento",
                "fusibili_conformita": "", "dati_targa_fusibili": "",
                "valore_nominale": "", "protezione_altro": "",
                "vista_targa": "OK", "vista_telaio": "OK", "vista_parti_mov": "OK",
                "vista_cavo": "OK", "vista_passacavo": "OK", "vista_spie": "OK",
                "vista_parti_appl": "OK", "vista_doc": "OK",
                "tecnico": self._last_tecnico,
                "firma_path": self._last_firma_path,
                "earthResPos": default_earth_res_pos(data),
                "funz_accensione": "", "funz_prova_part": "",
                "funz_codice_prot": "", "funz_normativa": "",
                "note": "",
            }

            # Se il file ha valori salvati, sovrascrivili ai default
            if "_edited" in data:
                edited.update(data["_edited"])
            edited = apply_template_defaults(data, edited)

            # If this is the currently selected file, use edited fields
            sel = self.file_listbox.curselection()
            if sel and sel[0] == i and self.fields:
                edited = apply_template_defaults(data, self._get_edited())

            tip = sanitize_filename(edited.get("tipologia", "") or "apparecchio")
            mfg = sanitize_filename(edited.get("manufacturer", "") or "produttore")
            mod = sanitize_filename(edited.get("model", "") or "modello")
            ser = sanitize_filename(edited.get("serial", "") or "matricola")
            filename = f"{tip}-{mfg}-{mod}-{ser}.pdf"
            out_path = os.path.join(out_dir, filename)

            try:
                generate_pdf(data, edited, out_path)
                ok_count += 1
            except Exception as e:
                errors.append(f"{data['sourceFile']}: {e}")
            finally:
                self._set_pdf_progress(
                    i + 1,
                    total_files,
                    f"Generazione PDF {i + 1}/{total_files} completata",
                )

        msg = f"{ok_count}/{len(self.parsed_files)} PDF generati in:\n{out_dir}"
        if errors:
            msg += f"\n\nErrori:\n" + "\n".join(errors)
            self.status_var.set(f"Generazione completata con errori: {ok_count}/{total_files}")
        else:
            self.status_var.set(f"Generazione completata: {ok_count}/{total_files} PDF")
        messagebox.showinfo("Risultato", msg)

    def remove_file(self, idx):
        self.parsed_files.pop(idx)
        self._refresh_list()
        for w in self.detail_frame.winfo_children():
            w.destroy()
        self.fields = {}
        self.status_var.set(f"{len(self.parsed_files)} file caricati")

    def clear_all(self):
        self.parsed_files = []
        self._refresh_list()
        for w in self.detail_frame.winfo_children():
            w.destroy()
        self.fields = {}
        self._set_pdf_progress(0, 1)
        self.status_var.set("Nessun file caricato")


# ======================== TEST ========================

def run_test():
    """Testa il parsing e la generazione PDF con i file nella cartella corrente."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    test_dir = os.path.join(base_dir, "test_output_v2")
    os.makedirs(test_dir, exist_ok=True)

    files = [f for f in os.listdir(base_dir) if f.lower().endswith((".mtr", ".csv"))]
    if not files:
        print("Nessun file .mtr/.csv trovato per il test.")
        return

    ok = 0
    for f in files:
        fp = os.path.join(base_dir, f)
        try:
            if f.lower().endswith(".mtr"):
                data = parse_mtr(fp)
            else:
                data = parse_csv(fp)

            cls = default_class(data)
            edited = {
                "tipologia": data.get("tipologia") or data.get("other", ""),
                "manufacturer": data.get("manufacturer", ""),
                "model": data.get("model", ""),
                "serial": data.get("serialNumber") or data.get("equipmentNumber", ""),
                "civab": "", "proprieta": self._last_proprieta, "invGest": data.get("equipmentNumber", ""),
                "invEnte": "", "presidio": data.get("location", ""),
                "reparto": "", "stanza": "", "periodicita": "12 mesi",
                "classe": cls, "apType": data.get("apType", "B"),
                "installazione": default_installation(data), "mobilita": default_mobility(data),
                "tensione": "220", "frequenza": "50", "potenza": "", "potenza_unit": "W",
                "protezione": "Trasformatore di isolamento",
                "fusibili_conformita": "", "dati_targa_fusibili": "",
                "valore_nominale": "", "protezione_altro": "",
                "vista_targa": "OK", "vista_telaio": "OK", "vista_parti_mov": "OK",
                "vista_cavo": "OK", "vista_passacavo": "OK", "vista_spie": "OK",
                "vista_parti_appl": "OK", "vista_doc": "OK",
                "tecnico": "VENTURI DANIELE",
                "firma_path": os.path.join(base_dir, "test_firma.png"),
                "earthResPos": default_earth_res_pos(data),
                "funz_accensione": "", "funz_prova_part": "",
                "funz_codice_prot": "", "funz_normativa": "",
                "note": "",
            }

            edited = apply_template_defaults(data, edited)

            tip = sanitize_filename(edited["tipologia"] or "apparecchio")
            mfg = sanitize_filename(edited["manufacturer"] or "produttore")
            mod = sanitize_filename(edited["model"] or "modello")
            ser = sanitize_filename(edited["serial"] or "matricola")
            filename = f"{tip}-{mfg}-{mod}-{ser}.pdf"
            out_path = os.path.join(test_dir, filename)
            generate_pdf(data, edited, out_path)

            sz = os.path.getsize(out_path)
            print(f"  OK: {f} -> {filename} ({sz} bytes)")
            print(f"      Produttore={data.get('manufacturer')}, Modello={data.get('model')}, Matricola={edited['serial']}")
            print(f"      Classe={cls}, AP={data.get('apType')}, Esito={data.get('overallStatus')}")
            print(f"      Misure: {len(data.get('measurements', []))}")
            ok += 1
        except Exception as e:
            print(f"  ERRORE: {f} -> {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{ok}/{len(files)} file elaborati con successo. PDF in: {test_dir}")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_test()
    else:
        root = tk.Tk()
        app = App(root)
        root.mainloop()
