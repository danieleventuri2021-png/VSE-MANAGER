# Installazione Windows 11 VSE-MANAGER

Questo pacchetto prepara il progetto nella cartella aziendale:

```text
C:\Users\Daniele\Nextcloud\MEDITECH\VSE-MANAGER
```

## Cosa fa l'installer

- verifica Python 3.12+;
- verifica Node.js/npm;
- verifica PostgreSQL come servizio Windows;
- se richiesto, prova a installare i prerequisiti con `winget`;
- crea le cartelle `data/input`, `data/output`, `data/backup`, `data/templates` e `logs`;
- crea o aggiorna `apps/backend/.env`;
- crea la virtualenv backend e installa `requirements.txt`;
- installa le dipendenze frontend con `npm install`;
- applica le migration Alembic su PostgreSQL;
- esegue una build frontend di controllo.

Il database puo' essere vuoto: le tabelle vengono create dalle migration nello schema `gestione_vse`.

## Procedura sul PC aziendale

1. Copia o estrai il pacchetto in:

```text
C:\Users\Daniele\Nextcloud\MEDITECH\VSE-MANAGER
```

2. Fai doppio click su:

```text
INSTALLA_PC_AZIENDALE.bat
```

3. Se PostgreSQL e' gia' installato con password diversa da `Daniele`, avvia invece PowerShell nella cartella del progetto ed esegui:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\windows\install_vse_manager.ps1 -PostgresPassword "PASSWORD_REALE" -ForceEnv
```

4. A installazione completata avvia il sistema con:

```text
AVVIA_PC_AZIENDALE.bat
```

L'app si apre su:

```text
http://127.0.0.1:5173
```

Credenziali iniziali:

```text
admin / admin
```

## Creazione dello zip dal PC di sviluppo

Dal repository sorgente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\windows\build_package.ps1
```

Lo zip viene creato in `C:\tmp` ed esclude cartelle generate come `.git`, `node_modules`, `.venv`, `logs`, cache e file `.env`.

## Note operative

- Per installare prerequisiti con `winget` serve Internet.
- Dopo l'installazione il programma puo' avviarsi senza Internet.
- PostgreSQL deve accettare la connessione indicata in `apps/backend/.env`.
- Se cambiano porte o password, rilancia `install_vse_manager.ps1` con i parametri corretti.
