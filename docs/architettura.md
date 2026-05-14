# Architettura gestione-vse

La web app è divisa in due processi locali:

- backend FastAPI in `apps/backend`, porta predefinita `8000`;
- frontend React/Vite in `apps/frontend`, porta predefinita `5173`.

Il backend usa PostgreSQL locale con schema dedicato `gestione_vse`. All'avvio tenta di creare lo schema e le tabelle; in produzione operativa è preferibile usare Alembic con `alembic upgrade head`.

Flusso dati:

1. creazione lavoro VSE;
2. upload Excel e mapping colonne variabili;
3. scansione cartella MTR;
4. parsing dei campi base MTR;
5. matching esatto/fuzzy;
6. analisi differenze e anomalie;
7. backup;
8. aggiornamento e rinomina MTR.
