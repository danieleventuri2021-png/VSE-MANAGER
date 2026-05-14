from pathlib import Path

import httpx
from openpyxl import Workbook


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000"
EXCEL_PATH = ROOT / "data" / "input" / "demo_vse.xlsx"
MTR_FOLDER = ROOT / "data" / "input" / "demo_mtr"


def reset_demo_files() -> None:
    EXCEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MTR_FOLDER.mkdir(parents=True, exist_ok=True)
    for path in MTR_FOLDER.glob("*"):
        if path.is_file():
            path.unlink()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "VSE"
    sheet.append(["Matricola", "Seriale", "Inventario", "Produttore", "Modello", "Descrizione", "Reparto", "Esito", "Data verifica"])
    sheet.append(["MAT-1001", "SN-A1001", "INV-001", "Acme Medical", "CARDIO-X1", "Monitor multiparametrico", "Cardiologia", "Conforme", "2026-05-14"])
    sheet.append(["MAT-2002", "SN-B2002", "INV-002", "BetaMed", "PUMP-22", "Pompa infusione", "Terapia Intensiva", "Conforme", "2026-05-14"])
    sheet.append(["MAT-3003", "SN-C3003", "INV-003", "GammaLab", "ECG-9", "Elettrocardiografo", "Ambulatorio", "Conforme", "2026-05-14"])
    workbook.save(EXCEL_PATH)

    (MTR_FOLDER / "MAT-1001_originale.mtr").write_text(
        """Rapporto prova sicurezza elettrica
Matricola: MAT-1001
Seriale: SN-A1001
Inventario: INV-001
Produttore: Acme Medical
Modello: CARDIO-X1
Descrizione: Monitor multiparametrico
Reparto: Cardiologia
Esito: Conforme

Continuita terra    0.08 ohm    PASS
Corrente dispersione    120 uA    PASS
""",
        encoding="utf-8",
    )
    (MTR_FOLDER / "MAT-2002_differenza.mtr").write_text(
        """Rapporto prova sicurezza elettrica
Matricola: MAT-2002
Seriale: SN-B2002
Inventario: INV-002
Produttore: BetaMed
Modello: PUMP-21
Descrizione: Pompa infusione
Reparto: Chirurgia
Esito: Conforme

Continuita terra    0.11 ohm    PASS
Corrente dispersione    95 uA    PASS
""",
        encoding="utf-8",
    )
    (MTR_FOLDER / "ORF-9999_orfano.mtr").write_text(
        """Rapporto prova sicurezza elettrica
Matricola: ORF-9999
Seriale: SN-Z9999
Inventario: INV-999
Produttore: DeltaCare
Modello: ORPHAN-1
Descrizione: Dispositivo non presente in Excel
Reparto: Magazzino
Esito: Conforme

Continuita terra    0.09 ohm    PASS
""",
        encoding="utf-8",
    )


def main() -> None:
    reset_demo_files()
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        health = client.get("/health")
        health.raise_for_status()

        job_response = client.post(
            "/api/jobs",
            json={
                "titolo": "Demo VSE fittizia",
                "cliente_nome": "Cliente Demo",
                "mtr_folder": str(MTR_FOLDER),
            },
        )
        job_response.raise_for_status()
        job = job_response.json()
        job_id = job["id"]

        with EXCEL_PATH.open("rb") as handle:
            excel_response = client.post(
                f"/api/jobs/{job_id}/excel",
                files={"file": (EXCEL_PATH.name, handle, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        excel_response.raise_for_status()

        mtr_response = client.post(f"/api/jobs/{job_id}/mtr-folder", json={"folder_path": str(MTR_FOLDER)})
        mtr_response.raise_for_status()

        analyze_response = client.post(f"/api/jobs/{job_id}/analyze")
        analyze_response.raise_for_status()
        analyzed_job = analyze_response.json()

        matches = client.get(f"/api/jobs/{job_id}/matches")
        matches.raise_for_status()
        anomalies = client.get(f"/api/jobs/{job_id}/anomalies")
        anomalies.raise_for_status()

        apply_response = client.post(f"/api/jobs/{job_id}/apply")
        apply_response.raise_for_status()
        applied = apply_response.json()

    print(f"job_id={job_id}")
    print(f"stato={analyzed_job['stato']}")
    print(f"summary={analyzed_job['summary']}")
    print("matches:")
    for item in matches.json():
        equipment = item["equipment"]
        mtr = item["mtr"]
        print(
            f"- {equipment.get('matricola')} -> "
            f"{mtr.get('nome_file') if mtr else 'NESSUN MTR'} "
            f"status={item['status']} score={item['score']}"
        )
    print("anomalies:")
    for item in anomalies.json():
        print(f"- {item['tipo']} [{item['severita']}]: {item['messaggio']}")
    print(f"backup_dir={applied['backup_dir']}")
    print(f"renamed={len(applied['renamed'])}")
    for item in applied["renamed"]:
        print(f"- {item['from']} -> {item['to']}")
    print(f"conflicts={len(applied['conflicts'])}")


if __name__ == "__main__":
    main()
