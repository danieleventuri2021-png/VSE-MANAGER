from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from fpdf import FPDF


def generate_consip_pdf(data: dict[str, Any], edited: dict[str, Any], output_path: str | Path, header_image: str | None = None) -> None:
    pdf = ConsipVsePDF(data, edited, header_image)
    pdf.generate()
    pdf.output(str(output_path))


class ConsipVsePDF(FPDF):
    def __init__(self, data: dict[str, Any], edited: dict[str, Any], header_image: str | None):
        super().__init__("P", "mm", "A4")
        self.data = data
        self.ed = edited
        self.header_image = header_image
        self.set_auto_page_break(auto=False)
        self._font = "Helvetica"
        self._load_fonts()

    def _load_fonts(self) -> None:
        root = Path(__file__).resolve().parents[4]
        win_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        candidates = [
            (root / "data" / "fonts" / "calibri.ttf", root / "data" / "fonts" / "calibrib.ttf", root / "data" / "fonts" / "calibrii.ttf"),
            (win_fonts / "arialn.ttf", win_fonts / "arialnb.ttf", win_fonts / "arialni.ttf"),
            (win_fonts / "calibri.ttf", win_fonts / "calibrib.ttf", win_fonts / "calibrii.ttf"),
        ]
        for regular, bold, italic in candidates:
            if regular.exists():
                self.add_font("Consip", "", str(regular), uni=True)
                self.add_font("Consip", "B", str(bold if bold.exists() else regular), uni=True)
                self.add_font("Consip", "I", str(italic if italic.exists() else regular), uni=True)
                self._font = "Consip"
                return

    def generate(self) -> None:
        self.add_page()
        self._draw_page1()
        self.add_page()
        self._draw_page2()

    def footer(self) -> None:
        self.set_draw_color(130, 130, 130)
        self.line(22, 272, 188, 272)
        self.set_text_color(0)
        self.set_font(self._font, "", 9)
        self.set_xy(22, 274)
        self.cell(166, 4, "Meditech s.r.l., Via Lazzaretto, 12 - 21013 Gallarate - Italy", align="C")
        self.set_xy(22, 279)
        self.cell(166, 4, "C.F. e P.IVA 04155350871", align="C")
        self.set_xy(22, 284)
        self.cell(48, 4, "www.meditechsrl.it", align="C")
        self.set_xy(80, 284)
        self.cell(48, 4, "info@meditechsrl.it", align="C")
        self.set_xy(140, 284)
        self.cell(48, 4, "meditechsrl@pec.it", align="C")
        self.set_xy(22, 289)
        self.cell(132, 4, "Consip ID 2802 Modello di Verifica Sicurezza Elettrica Rev. 03 16/01/2026", align="C")
        self.set_xy(160, 289)
        self.cell(28, 4, f"Pag. {self.page_no()} di 2", align="R")

    def _header(self) -> float:
        img = self.header_image or _find_default_header()
        if img and Path(img).exists():
            self.image(img, x=20.1, y=12.5, w=169.8)
        else:
            self.set_font(self._font, "B", 18)
            self.text(25, 27, "Meditech")
            self.set_font(self._font, "", 9)
            self.text(118, 22, "Via Lazzaretto,12 - 21013 Gallarate -VA - ITALY")
            self.text(122, 31, "info@meditechsrl.it - meditechsrl@pec.it")
        return 43

    def _draw_page1(self) -> None:
        self._header()
        # Coordinates are taken from the CONSIP Word/PDF model, not from the legacy VSE layout.
        # The table body is 169.8 mm wide and starts at x ~= 20.2 mm.
        x = 20.2
        w = 169.8
        self.set_font(self._font, "", 16)
        self.cell_at(x, 43.5, w, 7, "MODELLO VERIFICA SICUREZZA ELETTRICA", align="C", size=16)
        self.cell_at(x, 62.5, w, 7, _lotto_title(self.ed), align="C", size=16)

        self._standards_box(x, 71.5, w)
        self._section_anagrafica(x, 109.0, w)
        self._section_dati_tecnici(x, 139.0, w)
        self._section_condizioni(x, 157.8, w)
        self._section_visivo(x, 196.8, w)

    def _draw_page2(self) -> None:
        self._header()
        x = 20.2
        w = 169.8
        self._instrumental_tests(x, 37.8, w)
        self._function_row(x, 191.3, w)
        self._final_section(x, 199.7, w)

    def cell_at(self, x: float, y: float, w: float, h: float, txt: str = "", border: int | str = 0, align: str = "L", style: str = "", size: float = 9, fill: bool = False) -> None:
        self.set_xy(x, y)
        self.set_font(self._font, style, size)
        self.cell(w, h, _clean(txt), border=border, align=align, fill=fill)

    def multicell_at(self, x: float, y: float, w: float, h: float, txt: str, style: str = "", size: float = 9, align: str = "L") -> None:
        self.set_xy(x, y)
        self.set_font(self._font, style, size)
        self.multi_cell(w, h, _clean(txt), border=0, align=align)

    def box(self, x: float, y: float, w: float, h: float, fill_gray: bool = False) -> None:
        self.set_draw_color(0)
        self.set_line_width(0.25)
        if fill_gray:
            self.set_fill_color(205, 205, 205)
            self.rect(x, y, w, h, "DF")
        else:
            self.rect(x, y, w, h)

    def checkbox(self, x: float, y: float, label: str, checked: bool, size: float = 9, bold: bool = False) -> None:
        self.rect(x, y - 2.4, 2.3, 2.3)
        if checked:
            self.set_font(self._font, "B", size)
            self.text(x + 0.35, y - 0.3, "X")
        self.set_font(self._font, "B" if bold else "", size)
        self.text(x + 3.1, y, _clean(label))

    def _standards_box(self, x: float, y: float, w: float) -> None:
        self.box(x, y, w, 33.5)
        third = w / 3
        self.line(x + third, y, x + third, y + 15.7)
        self.line(x + third * 2, y, x + third * 2, y + 15.7)
        self.line(x, y + 15.7, x + w, y + 15.7)
        self.multicell_at(x + 2, y + 0.8, third - 4, 3.5, "Norme Italiane:\nCEI 62-5; CEI 62-51\nCEI 62-148\nCEI 64-8 V710", size=8.1)
        self.multicell_at(x + third + 2, y + 0.8, third - 4, 3.5, "Norme Europee:\nEN 60601-1\nEN 62353\nEN 60364-6", size=8.1)
        self.multicell_at(x + third * 2 + 2, y + 0.8, third - 4, 3.5, "Norme Internazionali:\nIEC 60601-1\nIEC 62353\nIEC 60364-6", size=8.1)
        self.cell_at(x + 2, y + 17.1, w - 4, 4, "Strumenti utilizzati:", style="B", size=10)
        instr = self.data.get("instrument") or {}
        cal = _dmy(instr.get("calibrationDate") or instr.get("calibration_date") or "")
        self.cell_at(x + 2, y + 25, 54, 4, f"- Analizzatore: {instr.get('manufacturer') or 'FLUKE'}", size=9)
        self.cell_at(x + 59, y + 25, 38, 4, f"Mod. {instr.get('type') or 'ESA 615'}", size=9)
        self.cell_at(x + 96, y + 25, 38, 4, f"N. serie. {instr.get('serialNumber') or instr.get('serial_number') or ''}", size=9)
        self.cell_at(x + 134, y + 25, 30, 4, "Scad.", size=9)
        self.cell_at(x + 136, y + 30, 28, 4, cal, style="B", size=8, align="C")

    def _section_anagrafica(self, x: float, y: float, w: float) -> None:
        self.box(x, y, w, 27)
        self.line(x, y + 5, x + w, y + 5)
        self.cell_at(x + 2, y + 1, w - 4, 4, "Sezione Anagrafica", style="B", size=10)
        rows = [5, 10, 15, 23]
        for yy in rows:
            self.line(x, y + yy, x + w, y + yy)
        self.line(x + 113, y + 5, x + 113, y + 15)
        self.line(x + 57, y + 10, x + 57, y + 15)
        self.cell_at(x + 2, y + 6, 108, 4, f"N. Progressivo di Installazione: {self.ed.get('invGest', '')}", size=8.8)
        self.cell_at(x + 115, y + 6, 52, 4, f"Tipologia: {self.ed.get('tipologia', '')}", style="B", size=8.8)
        self.cell_at(x + 2, y + 11, 53, 4, f"Produttore: {self.ed.get('manufacturer', '')}", size=8.8)
        self.cell_at(x + 59, y + 11, 52, 4, f"Modello: {self.ed.get('model', '')}", size=8.8)
        self.cell_at(x + 115, y + 11, 52, 4, f"N. di Serie: {self.ed.get('serial', '')}", size=8.8)
        self.line(x + 70, y + 15, x + 70, y + 27)
        self.cell_at(x + 2, y + 16, 66, 4, f"Cliente: {self.ed.get('proprieta', '')}", size=8.8)
        self.multicell_at(x + 72, y + 16, 95, 4, f"Presidio: {self.ed.get('presidio', '')}", size=8.4)
        self.cell_at(x + 2, y + 24, 66, 3, f"Unita Operativa: {self.ed.get('reparto', '')}", size=8.8)
        self.cell_at(x + 72, y + 24, 95, 3, f"Locale: {self.ed.get('stanza', '')}", size=8.8)

    def _section_dati_tecnici(self, x: float, y: float, w: float) -> None:
        self.box(x, y, w, 18)
        for yy in (5, 9.7, 13.8):
            self.line(x, y + yy, x + w, y + yy)
        self.cell_at(x + 2, y + 1, w - 4, 4, "Dati Tecnici", style="B", size=10)
        self.cell_at(x + 2, y + 6, 52, 3.5, f"Alimentazione [V]: {self.ed.get('tensione', '')} V", size=8.5)
        self.cell_at(x + 56, y + 6, 56, 3.5, f"Potenza[W-VA]/Assorbimento[A]:{self.ed.get('potenza', '')}{self.ed.get('potenza_unit', '')}", size=8.5)
        self.cell_at(x + 114, y + 6, 15, 3.5, "Classe:", size=8.5)
        self.checkbox(x + 130, y + 8.6, "I", self.ed.get("classe") == "I", size=8.5)
        self.checkbox(x + 144, y + 8.6, "II", self.ed.get("classe") == "II", size=8.5)
        self.checkbox(x + 158, y + 8.6, "AI", self.ed.get("classe") == "AI", size=8.5)
        self.cell_at(x + 2, y + 10, 30, 3, "Parti Applicate:", size=8.5)
        for idx, label in enumerate(("0", "B", "BF", "CF")):
            self.checkbox(x + 34 + idx * 18, y + 12.6, label, (self.ed.get("apType") or "") == label, size=8.5)
        self.cell_at(x + 112, y + 10, 52, 3, f"Frequenze Prove [mesi]: {self.ed.get('periodicita', '')}", size=8.5)
        install = self.ed.get("installazione", "")
        self.cell_at(x + 2, y + 14.2, 42, 3, "Tipo di Installazione:", size=8.5)
        self.checkbox(x + 44, y + 16.9, "fissa", install == "Permanente", size=8.5)
        self.checkbox(x + 87, y + 16.9, "cavo separabile", True, size=8.5)
        self.checkbox(x + 130, y + 16.9, "cavo non separabile", False, size=8.5)

    def _section_condizioni(self, x: float, y: float, w: float) -> None:
        h = 35.7
        self.box(x, y, w, h)
        for yy in (4.8, 8.4, 12.2, 17.0, 23.7, 30.3):
            self.line(x, y + yy, x + w, y + yy)
        for xx in (47.2, 62.4, 76.5, 120.5, 144.6, 157.4):
            self.line(x + xx, y + 4.8, x + xx, y + 8.4)
            self.line(x + xx, y + 17.0, x + xx, y + h)
        self.cell_at(x + 2, y + 0.8, w - 4, 3.4, "Condizioni di Prova", style="B", size=9)
        self.cell_at(x + 2, y + 5.0, 46, 3.2, "Valori di Prima misura?", size=8)
        self.checkbox(x + 52, y + 7.6, "SI", True, size=8)
        self.checkbox(x + 66, y + 7.6, "NO", False, size=8)
        self.cell_at(x + 78, y + 5.0, 42, 3.2, "Norma di Riferimento:", size=8)
        self.checkbox(x + 125, y + 7.6, "62-5", False, size=8)
        self.checkbox(x + 151, y + 7.6, "62-148", True, size=8)
        self.cell_at(x + 78, y + 9.0, 86, 3.0, "Se 62-148, metodo di misura utilizzato:", size=8)
        self.checkbox(x + 82, y + 15.2, "Differenziale", False, size=8)
        self.checkbox(x + 116, y + 15.2, "Alternativo", False, size=8)
        self.checkbox(x + 151, y + 15.2, "Diretto", True, size=8)
        self.multicell_at(x + 2, y + 17.5, 44, 3.0, "Presenti fase di boot /\ncalibrazione motore?", size=8)
        self.checkbox(x + 50, y + 22.0, "SI", False, size=8)
        self.checkbox(x + 63, y + 22.0, "NO", True, size=8)
        self.cell_at(x + 78, y + 18.8, 66, 3.2, "Presenti cavi di terra supplementari?", size=8)
        self.checkbox(x + 146, y + 22.0, "SI", False, size=8)
        self.checkbox(x + 158, y + 22.0, "NO", True, size=8)
        self.multicell_at(x + 2, y + 24.2, 44, 3.0, "Classe alimentazione di\nsicurezza 64.8:", size=8)
        self.cell_at(x + 78, y + 25.4, 66, 3.2, "Presente trasformatore isolamento?", size=8)
        self.checkbox(x + 146, y + 28.6, "SI", False, size=8)
        self.checkbox(x + 158, y + 28.6, "NO", True, size=8)
        self.multicell_at(x + 2, y + 30.8, 44, 2.8, "Connessione diretta con nodo\ndel locale?", size=8)
        self.checkbox(x + 50, y + 35.0, "SI", False, size=8)
        self.checkbox(x + 63, y + 35.0, "NO", True, size=8)

    def _section_visivo(self, x: float, y: float, w: float) -> None:
        row_h = 5.08
        labels = [
            ("Verifica assenza malfunzionamenti", "vista_funzionamento"),
            ("Telaio/involucro", "vista_telaio"),
            ("Dispositivi di ancoraggio/maniglie", "vista_parti_mov"),
            ("Ruote/freni", "vista_ruote"),
            ("Spine/prese", "vista_spine"),
            ("Cavo di alimentazione", "vista_cavo"),
            ("Blocca cavo/Passacavo", "vista_passacavo"),
            ("Targa: completa e integra", "vista_targa"),
            ("Serigrafie dei dispositivi di\ncomando/spie", "vista_spie"),
            ("Tubazioni rigide e flessibili", "vista_tubazioni"),
            ("Manuale d'uso", "vista_doc"),
        ]
        h = 9.4 + row_h * len(labels)
        self.box(x, y, w, h)
        self.line(x, y + 4.8, x + w, y + 4.8)
        self.line(x, y + 9.4, x + w, y + 9.4)
        self.line(x + 54.9, y + 4.8, x + 54.9, y + h)
        self.line(x + 139.5, y + 4.8, x + 139.5, y + h)
        self.cell_at(x + 2, y + 0.8, w - 4, 3.5, "Controllo Visivo Iniziale", style="B", size=9)
        self.cell_at(x + 13, y + 5.4, 40, 3.5, "Voci di controllo:", style="B", size=8)
        self.cell_at(x + 89, y + 5.4, 35, 3.5, "Risultato", style="B", size=8)
        self.cell_at(x + 142, y + 5.4, 25, 3.5, "Note", style="B", size=8)
        yy = y + 9.4
        for label, key in labels:
            self.line(x, yy, x + w, yy)
            one_line_label = label.replace("\n", " ")
            self.cell_at(x + 1.5, yy + 0.8, 52, 3.0, one_line_label, size=7.2 if "Serigrafie" in one_line_label else 7.4)
            val = (self.ed.get(key) or "OK").upper()
            self.checkbox(x + 57.2, yy + 3.6, "ok", val == "OK", size=7.0)
            self.checkbox(x + 71.0, yy + 3.6, "non ok", val == "KO", size=7.0)
            self.checkbox(x + 91.0, yy + 3.6, "non verificabile", val == "NV", size=7.0)
            self.checkbox(x + 119.5, yy + 3.6, "non applicabile", val == "NA", size=7.0)
            yy += row_h

    def _instrumental_tests(self, x: float, y: float, w: float) -> None:
        c = [47.2, 14.9, 71.5, 36.2]
        h = 149.8
        self.box(x, y, w, h)
        for xx in (x + c[0], x + c[0] + c[1], x + c[0] + c[1] + c[2]):
            self.line(xx, y, xx, y + h)
        for yy in (4.8, 39.6, 48.2, 56.8, 65.5, 99.6, 135.8):
            self.line(x, y + yy, x + w, y + yy)
        for start, height in ((0, 4.8),):
            self.box(x, y + start, c[0], height, fill_gray=True)
            self.box(x + c[0], y + start, c[1], height, fill_gray=True)
            self.box(x + c[0] + c[1], y + start, c[2], height, fill_gray=True)
            self.box(x + c[0] + c[1] + c[2], y + start, c[3], height, fill_gray=True)
        self.cell_at(x + 4, y + 0.8, c[0] - 8, 3.5, "Prove Strumentali", style="B", size=8.8)
        self.cell_at(x + c[0] + 2, y + 0.8, c[1] - 4, 3.5, "Misura", size=8.3)
        self.cell_at(x + c[0] + c[1] + 19, y + 0.8, 34, 3.5, "Valori ammissibili", size=8.3)
        self.cell_at(x + c[0] + c[1] + c[2] + 14, y + 0.8, c[3] - 18, 3.5, "Esito", size=8.3)

        rows = [
            (4.8, 34.8, "Resistenza di Protezione\n[Ohm]", self._earth_value(), "Cavo non separabile / installazione fissa:\nR fra connettore di terra del cavo e parti metalliche accessibili <= 0.30Ohm\nCavo separabile:\nR cavo singolo <= 0.10Ohm\nR fra morsetto terra di protezione e parti metalliche accessibili <= 0.20Ohm\nR fra connettore di terra della spina e parti metalliche accessibili <= 0.30Ohm", "OK", False),
            (39.6, 8.6, "Resistenza di Isolamento Rete\n- Involucro [MOhm]", self._measure_value("Mains to Protective Earth"), "", "OK", True),
            (48.2, 8.6, "Resistenza di Isolamento Rete\n- PA [MOhm]", self._measure_value("Mains to Applied Parts"), "", "OK", True),
            (56.8, 8.7, "Resistenza di Isolamento PA -\nInvolucro [MOhm]", self._measure_value("Applied Parts to Non-Earth"), "", "OK", True),
        ]
        for yy, rh, label, measure, limits, outcome, gray_limits in rows:
            self.multicell_at(x + 2, y + yy + max(1.0, rh / 2 - 5), c[0] - 4, 3.2, label, size=7.8)
            self.cell_at(x + c[0] + 2, y + yy + rh / 2 - 1.8, c[1] - 4, 3.5, measure or "______", size=7.8, align="C")
            if gray_limits:
                self.box(x + c[0] + c[1], y + yy, c[2], rh, fill_gray=True)
            else:
                self.multicell_at(x + c[0] + c[1] + 1.5, y + yy + 1.0, c[2] - 3, 3.0, limits, style="B" if yy == 4.8 else "", size=6.8)
            ox = x + c[0] + c[1] + c[2] + 3
            self.checkbox(ox, y + yy + rh / 2, "OK", outcome == "OK", size=7.8)
            self.checkbox(ox + 10.5, y + yy + rh / 2, "NOK", outcome == "NOK", size=7.8)
            self.checkbox(ox + 25.0, y + yy + rh / 2, "NA", outcome == "NA", size=7.8)
        self._enclosure_limits_grid(x, y + 65.5, c)
        self._patient_limits_grid(x, y + 99.6, c)
        self._earth_leakage_grid(x, y + 135.8, c)

    def _leakage_common(self, x: float, y: float, c: list[float], label: str, measure: str, outcome: str, height: float) -> tuple[float, float, float]:
        vx = x + c[0] + c[1]
        vw = c[2]
        self.multicell_at(x + 2, y + height / 2 - 6, c[0] - 4, 4.0, label, size=8.2)
        self.cell_at(x + c[0] + 2, y + height / 2 - 1.8, c[1] - 4, 3.5, measure or "______", size=7.8, align="C")
        ox = x + c[0] + c[1] + c[2] + 3
        self.checkbox(ox, y + height / 2, "OK", outcome == "OK", size=7.8)
        self.checkbox(ox + 10.5, y + height / 2, "NOK", outcome == "NOK", size=7.8)
        self.checkbox(ox + 25.0, y + height / 2, "NA", outcome == "NA", size=7.8)
        return vx, vw, y

    def _enclosure_limits_grid(self, x: float, y: float, c: list[float]) -> None:
        vx, vw, _ = self._leakage_common(x, y, c, "Correnti di Dispersione\nnell'involucro [microA]", self._enclosure_leakage(), "OK", 34.1)
        label_w, class_w = 20.2, 12.6
        value_w = (vw - label_w - class_w) / 3
        for xx in (label_w, label_w + class_w, label_w + class_w + value_w, label_w + class_w + value_w * 2):
            self.line(vx + xx, y, vx + xx, y + 34.1)
        for yy in (8.5, 17.05, 25.55):
            self.line(vx + label_w, y + yy, vx + vw, y + yy)
        self.cell_at(vx + 2, y + 7.0, label_w - 4, 3, "Alternativo", size=6.8)
        self.cell_at(vx + 2, y + 23.8, label_w - 4, 3, "Diretto / Diff", style="B", size=6.8)
        self._limit_triplet(vx + label_w, y + 0.3, class_w, value_w, "I", ("B", "BF", "CF"), ("1000", "1000", "1000"))
        self._limit_triplet(vx + label_w, y + 8.85, class_w, value_w, "II", ("B", "BF", "CF"), ("500", "500", "500"))
        self._limit_triplet(vx + label_w, y + 17.4, class_w, value_w, "I", ("B", "BF", "CF"), ("500", "500", "500"), underline_last=True)
        self._limit_triplet(vx + label_w, y + 25.9, class_w, value_w, "II", ("B", "BF", "CF"), ("100", "100", "100"))

    def _patient_limits_grid(self, x: float, y: float, c: list[float]) -> None:
        vx, vw, _ = self._leakage_common(x, y, c, "Correnti di Dispersione nel\nPaziente [microA]", self._patient_leakage(), "OK", 36.2)
        label_w, class_w = 20.2, 12.6
        value_w = (vw - label_w - class_w) / 3
        self.box(vx + label_w + class_w, y, value_w, 36.2, fill_gray=True)
        for xx in (label_w, label_w + class_w, label_w + class_w + value_w, label_w + class_w + value_w * 2):
            self.line(vx + xx, y, vx + xx, y + 36.2)
        for yy in (9.05, 18.1, 27.15):
            self.line(vx + label_w, y + yy, vx + vw, y + yy)
        self.cell_at(vx + 2, y + 7.3, label_w - 4, 3, "Alternativo", size=6.8)
        self.cell_at(vx + 2, y + 25.2, label_w - 4, 3, "Diretto / Diff", style="B", size=6.8)
        self._limit_triplet(vx + label_w, y + 0.8, class_w, value_w, "I", ("", "BF", "CF"), ("", "5000", "50"))
        self._limit_triplet(vx + label_w, y + 9.85, class_w, value_w, "II", ("", "BF", "CF"), ("", "5000", "50"))
        self._limit_triplet(vx + label_w, y + 18.9, class_w, value_w, "I", ("", "BF", "CF"), ("", "5000", "50"), underline_last=True)
        self._limit_triplet(vx + label_w, y + 27.6, class_w, value_w, "II", ("", "BF", "CF"), ("", "5000", "50"))

    def _earth_leakage_grid(self, x: float, y: float, c: list[float]) -> None:
        vx = x + c[0] + c[1]
        vw = c[2]
        self.multicell_at(x + 2, y + 1.5, c[0] - 4, 4, "Corrente di Dispersione Verso\nTerra (Installazioni fisse)\n[microA]", size=8.2)
        self.cell_at(x + c[0] + 2, y + 2, c[1] - 4, 3.5, "nc/sfc", size=8, align="C")
        self.cell_at(x + c[0] + 4, y + 10.5, c[1] - 8, 3.5, "___/___", size=8, align="C")
        ox = x + c[0] + c[1] + c[2] + 3
        self.checkbox(ox, y + 8, "OK", False, size=7.8)
        self.checkbox(ox + 10.5, y + 8, "NOK", False, size=7.8)
        self.checkbox(ox + 25.0, y + 8, "NA", True, size=7.8)
        group = vw / 3
        for xx in (group, group * 2, group / 2, group + group / 2, group * 2 + group / 2):
            self.line(vx + xx, y + 4.6, vx + xx, y + 14)
        for yy in (4.6, 9.2):
            self.line(vx, y + yy, vx + vw, y + yy)
        for i, label in enumerate(("B", "BF", "CF")):
            self.cell_at(vx + i * group, y + 1.35, group, 3.0, label, size=6.4, align="C")
            self.cell_at(vx + i * group, y + 5.55, group / 2, 3.0, "nc", size=6.4, align="C")
            self.cell_at(vx + i * group + group / 2, y + 5.55, group / 2, 3.0, "sfc", size=6.4, align="C")
            self.cell_at(vx + i * group, y + 10.2, group / 2, 3.0, "5000", size=6.4, align="C")
            self.cell_at(vx + i * group + group / 2, y + 10.2, group / 2, 3.0, "10000", size=6.4, align="C")

    def _limit_triplet(self, x: float, y: float, class_w: float, value_w: float, class_label: str, headers: tuple[str, str, str], values: tuple[str, str, str], underline_last: bool = False) -> None:
        self.cell_at(x, y + 2.1, class_w, 3, class_label, size=7.2, align="C")
        for idx, header in enumerate(headers):
            style = "B" if underline_last and idx == 2 else ""
            self.cell_at(x + class_w + idx * value_w, y + 0.2, value_w, 3, header, style=style, size=7.2, align="C")
            self.cell_at(x + class_w + idx * value_w, y + 4.2, value_w, 3, values[idx], size=7.2, align="C")

    def _function_row(self, x: float, y: float, w: float) -> None:
        self.box(x, y, w, 6, fill_gray=True)
        self.cell_at(x + 2, y + 1, 92, 4, "Accensione e Verifica Generica di Funzionamento", size=9)
        self.checkbox(x + 105, y + 4, "OK", (self.ed.get("funz_accensione") or "OK") == "OK", size=9)
        self.checkbox(x + 126, y + 4, "NON OK", self.ed.get("funz_accensione") == "KO", size=9)
        self.checkbox(x + 154, y + 4, "NA", self.ed.get("funz_accensione") == "NA", size=9)

    def _final_section(self, x: float, y: float, w: float) -> None:
        h = 69
        self.box(x, y, w, h)
        self.line(x + 47, y, x + 47, y + h)
        self.line(x + 108, y + 42, x + 108, y + h)
        self.line(x, y + 7, x + 47, y + 7)
        self.cell_at(x + 7, y + 2, 34, 4, "VALUTAZIONE FINALE", style="I", size=9.5, align="C")
        passed = self.data.get("overallStatus") == "Passed"
        outcomes = [("CONFORME", passed), ("NON CONFORMITA'\nFORMALE", False), ("NON CONFORMITA'\nSOSTANZIALE", False), ("NON CONFORMITA' GRAVE", not passed)]
        yy = y + 12
        for label, checked in outcomes:
            self.checkbox(x + 2, yy, label, checked, size=8.8)
            yy += 9
        self.cell_at(x + 49, y + 2, 108, 4, "Provvedimenti suggeriti per l'adeguamento / note:", size=9)
        if self.ed.get("note"):
            self.multicell_at(x + 50, y + 8, 116, 4, self.ed.get("note", ""), size=8.5)
        self.line(x, y + 42, x + w, y + 42)
        self.cell_at(x + 8, y + 44, 32, 4, "DATA COMPILAZIONE", style="I", size=8.5, align="C")
        self.cell_at(x + 58, y + 44, 42, 4, "Nome e Firma Tecnico Esecutore:", style="I", size=8.5, align="C")
        self.cell_at(x + 116, y + 44, 44, 4, "Nome e Firma Responsabile Verifiche:", style="I", size=8.5, align="C")
        self.line(x, y + 49, x + w, y + 49)
        self.cell_at(x + 18, y + 51, 24, 4, _date_slashes(self.data.get("testDate") or ""), size=9)
        firma = self.ed.get("firma_path", "")
        if firma and Path(firma).exists():
            try:
                self.image(firma, x=x + 61, y=y + 49, h=7)
            except Exception:
                pass

    def _find_measure(self, *needles: str) -> dict[str, Any] | None:
        lowered = [needle.lower() for needle in needles]
        for item in self.data.get("measurements", []) or []:
            text = f"{item.get('description', '')} {item.get('parentType', {}).get('type', '')} {item.get('parentType', {}).get('param', '')}".lower()
            if all(needle in text for needle in lowered):
                return item
        return None

    def _measure_value(self, *needles: str) -> str:
        item = self._find_measure(*needles)
        return _format_measure(item)

    def _earth_value(self) -> str:
        return self._measure_value("Protective Earth")

    def _enclosure_leakage(self) -> str:
        return self._measure_value("Equipment Leakage") or self._measure_value("Touch Current") or self._measure_value("Open Earth")

    def _patient_leakage(self) -> str:
        return self._measure_value("Applied Part Leakage") or self._measure_value("Patient")


def _find_default_header() -> str | None:
    root = Path(__file__).resolve().parents[4]
    for candidate in (root / "intestazione-consip-vse.png", root / "data" / "templates" / "intestazione-consip-vse.png"):
        if candidate.exists():
            return str(candidate)
    return None


def _lotto_title(ed: dict[str, Any]) -> str:
    tipologia = _norm(ed.get("tipologia"))
    modello = _norm(ed.get("model"))
    if tipologia == "DERMATOSCOPIO" and modello == "DE4100":
        return "LOTTO 1: APPARECCHIATURA: DERMATOSCOPIO"
    if tipologia == "ELETTROCARDIOGRAFO" and modello == "IMAC12PRO":
        return "LOTTO 3: APPARECCHIATURA: ECG EMERGENZE"
    if tipologia == "ELETTROCARDIOGRAFO" and modello == "IMAC120PRO":
        return "LOTTO 2: APPARECCHIATURA: ECG 12 DERIVAZIONI"
    if tipologia == "SPIROMETRO" and modello == "X2A":
        return "LOTTO 5: APPARECCHIATURA: SPIROMETRO"
    label = (ed.get("tipologia") or "APPARECCHIATURA").strip().upper()
    return f"APPARECCHIATURA: {label}"


def _norm(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _clean(value: object) -> str:
    return str(value or "").replace("°", "deg").replace("–", "-")


def _dmy(value: object) -> str:
    text = str(value or "").strip()
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
    if match and int(match.group(1)) <= 12:
        return f"{match.group(2)} / {match.group(1)} / {match.group(3)}"
    return text.replace("/", " / ")


def _date_slashes(value: object) -> str:
    text = _dmy(value)
    return text if text else " /      /"


def _format_measure(item: dict[str, Any] | None) -> str:
    if not item:
        return ""
    value = item.get("value")
    unit = item.get("unit")
    if value in (None, ""):
        return ""
    return f"{value} {unit or ''}".strip()


def _enclosure_limits() -> str:
    return "Alternativo\n I      B     BF    CF\n        1000  1000  1000\n II     B     BF    CF\n        500   500   500\nDiretto / Diff\n I      B     BF    CF\n        500   500   500\n II     B     BF    CF\n        100   100   100"


def _patient_limits() -> str:
    return "Alternativo\n I             BF    CF\n               5000  50\n II            BF    CF\n               5000  50\nDiretto / Diff\n I             BF    CF\n               5000  50\n II            BF    CF\n               5000  50"


def _enclosure_limits_compact() -> str:
    return (
        "Alternativo        I        B      BF      CF\n"
        "                         1000   1000   1000\n"
        "                   II       B      BF      CF\n"
        "                          500    500    500\n"
        "Diretto / Diff     I        B      BF      CF\n"
        "                          500    500    500\n"
        "                   II       B      BF      CF\n"
        "                          100    100    100"
    )


def _patient_limits_compact() -> str:
    return (
        "Alternativo        I              BF      CF\n"
        "                                      5000    50\n"
        "                   II             BF      CF\n"
        "                                      5000    50\n"
        "Diretto / Diff     I              BF      CF\n"
        "                                      5000    50\n"
        "                   II             BF      CF\n"
        "                                      5000    50"
    )


def _earth_leakage_limits_compact() -> str:
    return "nc/sfc        B              BF              CF\n              nc   sfc      nc   sfc      nc   sfc\n              5000 10000    5000 10000    5000 10000"
