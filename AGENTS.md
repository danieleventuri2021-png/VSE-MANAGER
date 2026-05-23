# Repository Guidelines

## Project Structure & Module Organization

This repository contains a local VSE/MTR management app with a FastAPI backend and a React/Vite frontend.

- `apps/backend/app/`: API routes, models, services, database setup, and configuration.
- `apps/backend/tests/`: pytest test suite for backend services and health checks.
- `apps/backend/alembic/`: database migrations.
- `apps/frontend/src/`: React application source, split into `pages/`, `components/`, `api/`, and `lib/`.
- `data/`: runtime input, output, backup, and PDF template folders.
- `docs/`: workflow and architecture notes.
- `scripts/`: local helper scripts for startup and demo flows.

## Build, Test, and Development Commands

Run frontend commands from `apps/frontend`:

- `npm run dev -- --host 127.0.0.1 --port 5173`: start the Vite dev server.
- `npm run build`: type-check and build the frontend.
- `npm run preview`: preview the production frontend build.

Run backend commands from `apps/backend` or repo root as noted:

- `py -3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8000`: start the backend from `apps/backend`.
- `py -3.13 -m pytest apps\backend\tests`: run backend tests from repo root.
- `alembic upgrade head`: apply database migrations from `apps/backend`.

## Coding Style & Naming Conventions

Use TypeScript with React function components and hooks. Keep reusable UI in `components/`, page-level behavior in `pages/`, API wrappers in `api/client.ts`, and pure helpers in `lib/`. Prefer clear Italian UI labels to match the current app.

Backend code uses Python type hints, service-oriented modules, and FastAPI route functions. Keep business logic in `app/services/` and route handlers thin. Use snake_case for Python names and PascalCase for React components.

## Testing Guidelines

Backend tests use `pytest`; test files follow `test_*.py` naming. Add or update focused tests when changing parsing, matching, registry sync, PDF generation, or API behavior. Frontend currently relies on TypeScript build checks; run `npm run build` before handing off UI changes.

## Commit & Pull Request Guidelines

There is no existing commit history, so use concise imperative commit messages, for example `Add registry anomaly cleanup` or `Format VSE dates in Italian`. Pull requests should include a short summary, commands run, database migration notes if applicable, and screenshots for visible UI changes.

## Security & Configuration Tips

Do not commit generated PDFs, backups, local database dumps, or machine-specific paths from `data/`. Keep credentials and local overrides in environment files outside versioned code. Treat folder deletion features conservatively; avoid recursive deletion unless explicitly requested and reviewed.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
