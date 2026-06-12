# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`gestione-vse` is a local web app for managing VSE/MTR electrical-safety verification jobs. A technician imports an Excel inventory, scans a folder of instrument output files (MTR/CSV/DTA from Fluke ESA615 / Ansur), the backend matches instrument files to inventory rows, surfaces differences/anomalies, lets the user review each measurement record, and generates per-device PDF reports. Verified data is consolidated into a persistent per-client equipment registry with next-verification dates exportable as `.ics`.

The codebase, domain language, DB columns, and user-facing strings are in **Italian** — keep new identifiers and messages consistent with the surrounding Italian naming (e.g. `LavoroVse` = job, `Apparecchiatura` = equipment row, `VerificaVse` = verification, `FileMtr` = parsed instrument file, `RegistroApparecchiatura` = registry entry).

## Architecture

Two local processes (see `docs/architettura.md`):

- **Backend** — FastAPI in `apps/backend`, default port `8000`. PostgreSQL with a dedicated schema `gestione_vse` (search_path set per-connection in `app/db/session.py`). At startup `main.py` runs `ensure_schema()` + `Base.metadata.create_all()` + `ensure_default_admin()`; Alembic is the source of truth for production schema.
- **Frontend** — React + Vite + TypeScript + Tailwind in `apps/frontend`, default port `5173`. Page-per-route under `src/pages/`, shared axios client in `src/api/client.ts` (Bearer token from `localStorage`, base URL proxied to backend).

### Backend layering
- `app/api/routes.py` — nearly all endpoints live here (one large router + a separate `auth_router`). `router` is mounted with a global `Depends(get_current_user)`; `auth_router` (login) is open. Most routes resolve a job via `_job_or_404(db, job_id, current_user)` which enforces per-user ownership (`owner_user_id`).
- `app/services/` — all domain logic. Routes orchestrate; services do the work. Key services:
  - `mtr_parser.py` — entry point `parse_mtr_file()` / `scan_mtr_folder()`. Dispatches by extension/content to the parsers below and normalizes everything into a common dict shape (`normalized` with `dut`/`ansur`/`test`/`instrument`/`measurements`, plus a flat legacy view via `_legacy_from_normalized`).
  - Parsers: `dta_parser.py` (binary `.dta`), `ansur_parser.py` + `esa615_legacy_adapter.py` (XML MTR), `csv_parser.py` (ESA615 CSV). Parsing tries a primary parser then merges a fallback parser's fields (`_merge_*_parses`).
  - `matcher.py` — `match_records()`: exact serial/inventory match → fuzzy (rapidfuzz, with a pure-Python fallback if rapidfuzz is missing). Score ≥90 = `certo`, ≥55 = `da_controllare`, else `mancante`. Unmatched instrument files are `mtr_orfano`.
  - `difference_analyzer.py`, `anomaly_service.py` — diff Excel vs parsed file, record anomalies.
  - `excel_importer.py` + `column_mapper.py` — import inventory, map variable column headers.
  - `vse_defaults.py`, `session_defaults_service.py` — per-job common values (technician, voltage, periodicity, etc.) and applying them to verifications. Manual per-record edits always win over defaults.
  - `pdf_generator.py` / `consip_pdf_generator.py` / `bulk_pdf_service.py` — PDF generation (`standard` and CONSIP templates/headers). Also `font_manager.py`, `signature_service.py`, `measurement_indexer.py`, `measurement_selector.py`, `measurement_deduplication_service.py`.
  - `equipment_registry_service.py` — `sync_job_registry()` consolidates verified data per client; `build_registry_ics()` exports the calendar.
  - `mtr_writer.py` / `source_writer.py` / `backup_service.py` / `file_renamer.py` — the **apply** step. Source instrument files are only mutated on explicit apply, always after a backup, and only safe identifier fields are written — never measurement values.
- `app/models/entities.py` — single-file SQLAlchemy model. All tables carry `{"schema": SCHEMA}`. Rich JSONB columns store per-record state (`dati_ansur_json`, `dati_excel_json`, `dati_revisionati_json`, `dati_finali_pdf_json`, `campi_bloccati_json`, `measurement_index_json`).

### Job workflow
A job has a `workflow_mode` stored in `summary["workflow_mode"]` (`full` or `simple`); `_job_workflow_mode()` in routes.py branches on it (simple jobs skip Excel). Typical full flow: create job → upload Excel → set MTR folder → `analyze` (parse + match + diff + anomalies) → review per file → set defaults → generate PDFs → sync registry → export `.ics`.

## Commands

All commands run from PowerShell (Windows is the primary dev target).

### Backend (`apps/backend`)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head          # apply migrations
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pytest                        # run all tests
pytest tests/test_matcher.py  # single file
pytest tests/test_matcher.py::test_name   # single test
```
Migrations live in `apps/backend/alembic/versions/` (`0001`…`0005`). Create a new one with `alembic revision -m "..."` and edit it (do not rely solely on `create_all`).

### Frontend (`apps/frontend`)
```powershell
npm install
npm run dev      # vite dev server
npm run build    # tsc -b && vite build
```

### Full stack / launchers
```powershell
.\scripts\start_all.ps1                                  # migrate + backend + frontend + open browser
.\scripts\start_all.ps1 -BackendPort 8001 -FrontendPort 5174
.\scripts\start_backend.ps1 / .\scripts\start_frontend.ps1
python scripts/check_ports.py                            # verify 8000/5173 free
```
`AVVIA_VSE_MANAGER.bat` (and `AVVIA_SERVER_LAN.bat`, `AVVIA_PC_AZIENDALE.bat`) are double-click entry points wrapping the PowerShell scripts. Logs go to `logs/`.

### Raspberry / Linux deploy
`scripts/raspberry_install.sh` (first install: nginx on :80 + systemd `vse-manager-backend`), `scripts/raspberry_deploy.sh` (update: git pull + deps + frontend build + migrate + restart).

## Configuration

Backend config is `pydantic-settings` in `app/core/config.py`, loaded from `apps/backend/.env` (committed working `.env`; `.env.example` has a generic password). Key vars: `DATABASE_URL` (default `postgresql://postgres:Daniele@localhost:5432/postgres`), `DB_SCHEMA`, `AUTH_SECRET_KEY`, `ADMIN_USERNAME`/`ADMIN_PASSWORD`, and the data dirs `DATA_ROOT`/`INPUT_DIR`/`OUTPUT_DIR`/`BACKUP_DIR`/`TEMPLATE_DIR` (default under `data/`). PDF header images are looked up in `data/templates/` (`meditech-vse.png`, `intestazione-consip-vse.png`); if absent, PDFs fall back to a text header.

## Conventions & invariants

- **Never modify measurement values in source instrument files.** The save-source/apply paths only touch identifier fields and always create a backup first.
- New parsers must return the normalized shape consumed by `_legacy_from_normalized` / `_merge_*_parses` in `mtr_parser.py` so matching, diffing, and PDF generation keep working.
- Per-record manual edits and locked fields (`campi_bloccati_json`) take precedence over job-level defaults; preserve that precedence when changing the defaults logic.
- New tables/columns belong in `entities.py` **and** a new Alembic migration, always under the `gestione_vse` schema.
- Endpoints that operate on a job should go through `_job_or_404` to keep per-user ownership enforcement intact.
