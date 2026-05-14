# Workflow VSE/MTR

## Valori globali del lavoro e valori specifici MTR

I valori globali del lavoro sono i default usati quando un singolo MTR non ha un valore revisionato. Comprendono tecnico, firma, proprieta, periodicita, tensione, frequenza, protezione, template PDF e intestazione PDF.

I valori specifici del singolo MTR sono salvati sulla verifica collegata al file MTR. Possono includere dati identificativi, note, controlli visivi/funzionali, installazione, mobilita, classe elettrica, parte applicata, CIVAB/CND e override delle misure selezionate.

La priorita di merge e:

1. campi bloccati manualmente sul singolo MTR;
2. dati revisionati manualmente sul singolo MTR;
3. dati Excel associati;
4. dati letti dal MTR/Ansur;
5. default del lavoro;
6. default generali di sistema.

## Tecnico, firma e proprieta

Tecnico, firma e proprieta non sono piu variabili di memoria della GUI. Sono persistiti come default del lavoro e, se serve, anche come valori specifici della singola verifica.

La revisione MTR permette tre comportamenti:

- applicare i valori solo al file corrente salvando la revisione;
- salvarli come default del lavoro dalla pagina Impostazioni lavoro;
- applicarli a tutti gli MTR non bloccati con `POST /api/jobs/{job_id}/apply-defaults`.

## Genera PDF Singolo

La generazione singola usa il file MTR selezionato, i dati revisionati per quel file e i default del lavoro solo dove il campo e vuoto. Il risultato viene salvato in `data/output/job_{id}` e registrato in `pdf_generati`.

## Genera Tutti I PDF

La generazione massiva scorre tutti i file MTR del lavoro, applica i default comuni, applica le regole Ansur del singolo template, rispetta i campi bloccati e produce un report con totale, generati, errori, saltati e anomalie.

## Scrittura Nel Sorgente

`POST /api/files/{file_mtr_id}/save-source` modifica solo campi identificativi sicuri:

- produttore;
- modello;
- matricola/seriale;
- inventario;
- descrizione;
- location/reparto se presente.

Prima della modifica viene creato un backup. Le misure tecniche e la struttura tecnica Ansur non vengono modificate. Dopo la scrittura il sorgente viene riletto.

I campi extra come note, CIVAB, controlli, tecnico, firma, proprieta, periodicita e blocchi manuali restano nel database.

## Template Ansur Permanente Tre Misure

Il template viene riconosciuto quando il nome richiama installazione permanente e sono presenti almeno tre misure di terra/protective earth. In questo caso vengono applicati:

- classe elettrica `I`;
- installazione `Permanente`;
- mobilita `Fisso`;
- posizione terra per installazione permanente;
- resistenza terra come misura PE peggiore, cioe il valore maggiore.

## Selezione Misure

Le misure vengono indicizzate per nome, descrizione, parametro, condizione, esito, unita, `ElementID` e `TestElement`. I selector supportano varianti italiane e inglesi per protective earth, leakage, applied part leakage e isolamento.

## Archivio Apparecchiature

Dopo analisi/revisione/PDF, il lavoro puo essere sincronizzato nell'archivio apparecchiature. La sincronizzazione usa i dati finali PDF e crea o aggiorna una scheda per cliente e identificativo apparecchiatura.

L'identificativo viene scelto in ordine da matricola/seriale, inventario gestionale, inventario MTR. Se manca, la riga viene saltata e indicata nel report.

La prossima verifica viene calcolata aggiungendo la periodicita in mesi alla data dell'ultima verifica. Se la periodicita non e presente sul singolo MTR, viene usato il default del lavoro.

`GET /api/registry/calendar.ics` produce un calendario importabile in Google Calendar. Ogni evento contiene cliente, tipologia, marca, modello, matricola e ubicazione.
