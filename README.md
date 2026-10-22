# US Vessel Annotator

Prototipo locale Streamlit per annotare frame ecografici. Classi PNG: 0 sfondo, 1 vena, 2 arteria.

## Installazione

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Su Windows usare `.venv\\Scripts\\activate`.

## Workflow

1. Carica video MP4/AVI/MOV/MKV.
2. Scegli il numero di frame equidistanti e il frame da annotare.
3. Seleziona vena, arteria o gomma; disegna sul canvas e premi **Applica tratto**.
4. Usa undo/redo, zoom e navigazione tra frame.
5. Premi **Prepara esportazione ZIP** e scarica il dataset.

Il file ZIP include `images/`, `masks/` e `metadata.json` con frame index e timestamp stimato da FPS. I PNG sono esportati alla risoluzione originale del video. Ogni pixel della maschera contiene un ID di classe, non un colore RGB.

## Limitazioni

- La persistenza è nella sessione Streamlit; scarica il file ZIP prima di chiudere la sessione.
- I video vengono decodificati con OpenCV; alcuni codec richiedono conversione preliminare.
- Il campionamento è per indice frame, non per distanza fisica della sonda.
- Non è prevista autenticazione, audit trail, validazione clinica o gestione certificata dei dati paziente. Usare video anonimizzati e solo in ambiente locale protetto.
- Il componente canvas è una dipendenza di terze parti; verificare la compatibilità con la versione Streamlit installata.
