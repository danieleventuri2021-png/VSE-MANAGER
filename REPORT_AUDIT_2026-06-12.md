# Report audit VSE-MANAGER — 12/06/2026

## Riepilogo

Audit completo del progetto: test automatici, scanner di sicurezza, revisione manuale del codice. I fix a basso rischio sono stati applicati sul branch git `audit/fix-sicuri-20260612` (commit `ac54e48`); il branch `dta-parser-sync` e le tue modifiche in corso ai launcher non sono stati toccati. Copia di sicurezza pre-audit: `data/backup/copia_pre_audit_20260612.zip`.

**Risultati test**: pytest backend 40/40 passati (prima dei fix: 35/40), `npm run build` frontend OK senza errori TypeScript, `npm audit` 0 vulnerabilita, `pip-audit` nessuna CVE nota, `bandit` solo rilievi di livello basso.

## ⚠ Azione manuale richiesta subito

1. Il file `.git\index.lock` e rimasto bloccato (limite dell'ambiente di lavoro). Prima di usare git, eliminalo da PowerShell:
   `del C:\CODEX\VSE-MANAGER\.git\index.lock`
2. Riavvia il backend per caricare la nuova `AUTH_SECRET_KEY` (gli utenti dovranno rifare il login una volta).
3. Se l'utente admin ha ancora password `admin`, cambiala dalla pagina utenti.

## Fix applicati (branch `audit/fix-sicuri-20260612`)

1. **Path traversal nell'upload Excel** (`routes.py`): il nome file caricato non era sanitizzato; un nome come `..\..\file.xlsx` poteva scrivere fuori dalla cartella di input. Ora viene usato solo il nome base del file.
2. **Chiave segreta dei token di default** (`config.py` aveva `cambia-questa-chiave-vse-manager`): con la chiave nota, chiunque in LAN poteva forgiare token di accesso validi senza password. Ho generato una `AUTH_SECRET_KEY` casuale in `apps/backend/.env` (file non versionato) e aggiunto un warning all'avvio in `main.py` se restano i default di chiave o password admin.
3. **Corruzione file con valori contenenti backslash** (`source_writer.py`): `re.sub` interpretava `\` e `\g` nei valori inseriti dall'utente durante il salvataggio nei sorgenti MTR/CSV/DTA, con rischio di scrivere valori corrotti. Ora il valore viene inserito letteralmente.
4. **Parsing bloccato su server senza interfaccia grafica** (`esa615_app_v2.py`): l'import di `tkinter` a livello di modulo faceva fallire parsing MTR/CSV e generazione PDF su ambienti headless — incluso il deploy Raspberry, dove `python3-tk` spesso manca. L'import ora e opzionale (la GUI Windows resta invariata). Questo fix da solo ha risolto i 5 test che fallivano.
5. **Dipendenze frontend tutte a `latest`** (`package.json`): build non riproducibile e rischio di rotture improvvise a ogni `npm install` (es. un futuro React 20). Versioni fissate a quelle gia in uso nel tuo `package-lock.json`, quindi nessun cambiamento di comportamento.

## Vulnerabilita e rischi segnalati (non corretti, da valutare)

- **Endpoint `/system/folders`**: qualunque utente autenticato puo sfogliare, creare e rinominare cartelle su tutto il filesystem del server (tutti i drive). Per uso personale in locale va bene; se esponi in LAN con piu utenti, conviene limitare la navigazione a una radice configurata (es. `DATA_ROOT`).
- **`output_dir` libero nella generazione PDF massiva**: un utente autenticato puo far scrivere i PDF in qualunque cartella del server. Stesso discorso: accettabile in locale, da limitare in LAN.
- **Nessun rate-limiting sul login**: con esposizione LAN un attaccante puo provare password all'infinito. Miglioria suggerita: blocco temporaneo dopo N tentativi falliti.
- **Password minima 6 caratteri** e password DB locale debole nel `.env`: alza i requisiti se passi all'uso multi-utente.
- **Token salvato in `localStorage`**: vulnerabile in caso di XSS. Non ho trovato `dangerouslySetInnerHTML` ne altri sink XSS nel frontend, quindi il rischio attuale e basso.
- **Parsing XML con `xml.etree`** (rilievo bandit B314): per file provenienti da terzi conviene la libreria `defusedxml` (cambio di una riga negli import dei parser).
- **`_save_dta` tratta i `.dta` come testo UTF-8 con `errors="ignore"`**: se un `.dta` contiene byte non-UTF-8, la riscrittura li perde silenziosamente. Il backup automatico pre-scrittura mitiga, ma il salvataggio su `.dta` andrebbe riscritto in modalita binaria. Non l'ho toccato perche richiede test con file reali.

## Migliorie funzionali e operative suggerite

- **Matcher greedy**: `match_records` assegna i file in ordine di riga Excel; in caso di punteggi simili l'ordine puo rubare il match migliore a una riga successiva. Un'assegnazione globale (es. algoritmo ungherese su rapidfuzz) darebbe abbinamenti piu stabili.
- **Avvio "produzione"**: `AVVIA_VSE_MANAGER.bat` usa il dev server di Vite. In locale va benissimo; per l'uso in LAN (`AVVIA_SERVER_LAN.bat`) sarebbe piu robusto servire la build statica (`npm run build` + serve `dist/`), come gia fa il deploy Raspberry con nginx.
- **Requirements non pinnati**: `requirements.txt` senza versioni; consiglio di fissarle (`pip freeze`) come fatto per il frontend. Inoltre `fpdf` 1.x non e piu mantenuta: valutare migrazione a `fpdf2` (API quasi compatibile).
- **API deprecate**: `datetime.utcnow()` (5 occorrenze) e `@app.on_event("startup")` sono deprecati in Python/FastAPI recenti; migrare a `datetime.now(timezone.utc)` e agli handler `lifespan` prima o poi.
- **Fine riga CRLF/LF**: molti file risultano "modificati" in git solo per i fine riga (tutti i file in `DATI-TEST` e vari `.py`). Un file `.gitattributes` con `* text=auto` eliminerebbe questo rumore.
- **Pulizia**: in `data/backup` c'e un file vuoto residuo `copia_pre_audit_20260612_1805.zip` da cancellare; ci sono anche centinaia di cartelle `source_write_*` accumulate — utile una pulizia periodica automatica dei backup piu vecchi di N giorni.

## Cosa fare per integrare i fix

```powershell
del C:\CODEX\VSE-MANAGER\.git\index.lock
git log --oneline -1 audit/fix-sicuri-20260612   # verifica il commit ac54e48
# quando vuoi integrare nel tuo branch di lavoro:
git checkout dta-parser-sync
git merge audit/fix-sicuri-20260612
```

Dopo il merge: riavvia con `AVVIA_VSE_MANAGER.bat` e rifai il login.

---

# Addendum 12/06/2026 — Ridondanze e migliorie del flusso operativo

## Passaggi ridondanti per l'operatore

1. **"Salva default lavoro" + "Applica a tutti" sono due click separati**, ma il backend supporta gia entrambe le cose in una chiamata sola (`apply-defaults` accetta `save_as_job_default: true`, la UI non lo usa). Un solo bottone "Salva e applica a tutti" elimina un passaggio a ogni lavoro.
2. **"Analizza" va premuto a mano** dopo aver caricato Excel e file MTR. L'analisi e ricalcolabile senza effetti collaterali: si puo lanciare automaticamente appena entrambi gli input sono presenti.
3. **La sincronizzazione del Registro e manuale** (pagina Registro → "Sincronizza"): facile da dimenticare. Potrebbe partire da sola dopo "Genera tutti i PDF", che e di fatto la fine del lavoro.
4. **"Salva nel sorgente" e per singolo file**: se correggi i campi identificativi su molti file servono molti click. Utile un "salva nel sorgente tutti i revisionati".
5. **Ricaricare i file MTR cancella e ricrea tutto** (`_replace_mtr_files` elimina tutti i FileMtr del lavoro, e con loro le revisioni gia fatte). Aggiungere un file a lavoro avviato fa perdere il lavoro di revisione: serve un avviso in UI o un upload incrementale.

## Ridondanze nel codice (prestazioni su lavori grandi)

1. **`build_final_pdf_data` viene ricalcolato ovunque**: a ogni apertura del dettaglio revisione (e l'endpoint GET lo salva pure nel DB con commit — una GET non dovrebbe scrivere), per ogni file in apply-defaults, in generazione PDF, in sync registro, e nella pagina Abbinamenti per ogni riga. In piu `_registry_candidate_for_match` esegue per OGNI riga una query su tutto l'archivio del cliente con scoring: la pagina Abbinamenti costa O(righe × archivio). Soluzione: caricare i candidati archivio una volta per lavoro e riusarli.
2. **La risposta di `/matches` trasporta payload enormi**: per ogni riga viene serializzato l'intero `parsed_data` + `parsed_json` + `measurement_index` del file. Basterebbe una versione ridotta per la tabella.
3. **N+1 query in `analyze` e `/matches`**: `eq.verifiche` e `row.matched_file_mtr` sono lazy-load per riga; con `selectinload` si riducono centinaia di query a 2-3.
4. **`get_review_list` crea le verifiche mancanti a ogni GET** (un INSERT+flush per file al primo caricamento): meglio crearle una volta sola dentro `analyze`.
5. **Un backup-cartella per ogni click "Salva nel sorgente"**: in `data/backup` ci sono gia centinaia di cartelle `source_write_*`. Raggruppare i backup per giorno/lavoro e aggiungere pulizia automatica (>30 giorni).
6. **Timeout frontend**: il client axios ha timeout 15 s di default; `analyze` su lavori grandi puo superarlo (upload e PDF hanno gia l'override a 300 s, analyze no) → la UI mostra errore mentre il backend in realta finisce. Aggiungere l'override anche ad `analyzeJob`.
7. **Matcher greedy**: l'abbinamento procede riga per riga e una riga puo "rubare" il file migliore di una successiva. Con un'assegnazione globale sui punteggi gli abbinamenti diventano stabili e piu accurati.

## Priorita suggerita

Primi tre interventi per rapporto beneficio/sforzo: (1) bottone unico "Salva e applica a tutti" + auto-analyze, (2) timeout su analyze + payload ridotto di /matches, (3) avviso o upload incrementale sul ricaricamento MTR.
