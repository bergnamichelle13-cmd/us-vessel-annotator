# Pubblicazione su Streamlit Community Cloud

1. Crea un repository GitHub (preferibilmente privato) chiamato `us-vessel-annotator`.
2. Carica nella radice del repository `app.py`, `requirements.txt`, `packages.txt`, `.streamlit/config.toml`.
3. Accedi a https://share.streamlit.io/ con GitHub.
4. Crea una nuova app, seleziona il repository e il branch `main`, e imposta il file principale su `app.py`.
5. Scegli il sottodominio disponibile e premi Deploy.

## Dati medici
Non caricare video di pazienti identificabili su un servizio cloud pubblico senza autorizzazione istituzionale, valutazione privacy e accordi adeguati. L'app mantiene i dati nella sessione del server e non implementa autenticazione, audit o archiviazione clinica sicura. Scarica il file ZIP prima di chiudere la sessione.

## Limiti
Il campionamento è uniforme per indice del frame, non per distanza spaziale della sonda. Il componente `streamlit-drawable-canvas` potrebbe richiedere aggiornamenti di compatibilità su versioni recenti di Streamlit.
