# HoloEnergy

Wrapper Python esterno per la simulazione energetica di ROV/AUV in HoloOcean.
Prima versione: BlueROV2 Heavy, otto thruster, batteria L0 oppure Rint L1,
temperatura dinamica, payload a stati, perdite dei convertitori, derating e log.

Il package non comunica con hardware reale. HoloOcean è una dipendenza opzionale
da installare secondo la sua documentazione ufficiale, insieme ai relativi mondi.
Le demo sintetiche si eseguono anche senza HoloOcean.

I limiti nominali Blue Robotics e i dati T200 provengono da fonti ufficiali.
OCV, resistenza del pacco, scambio termico, hotel load e curve in temperatura
necessitano di calibrazione. I valori dimostrativi sono marcati come placeholder:
questa versione non fornisce ancora una previsione validata dell'autonomia reale.

Vedi [fonti scientifiche](docs/scientific_sources.md),
[progetto](docs/holoenergy_design.md) e
[protocollo di validazione](docs/validation_protocol_bluerov2.md).

La .venv preparata qui usa Python 3.13.12. Dalla cartella del progetto:

    .venv\Scripts\python.exe -m pip install -e ".[dev]"
    .venv\Scripts\python.exe -m pytest -q
    .venv\Scripts\python.exe examples\bluerov2_energy_demo.py --backend synthetic
    .venv\Scripts\python.exe examples\bluerov2_sensor_payload_demo.py --backend synthetic

Per riprodurre l'ambiente da zero: uv sync --extra dev --locked.
I log sono in logs/, con sidecar per configurazione e provenienza.
Le demo abilitano il derating; il wrapper lo lascia disabilitato per default.

Per HoloOcean:

    & "C:\Users\Andrea\miniconda3\envs\holoocean_joystick\python.exe" examples\bluerov2_energy_demo.py --backend holoocean
    & "C:\Users\Andrea\miniconda3\envs\holoocean_joystick\python.exe" examples\bluerov2_sensor_payload_demo.py --backend holoocean

Su questa macchina HoloOcean 2.3.0 e il pacchetto Ocean sono presenti nell'ambiente
Conda holoocean_joystick (Python 3.10.20). La .venv di HoloEnergy non contiene
HoloOcean. Le demo usano per default configs/bluerov2_holoocean.json, con un solo
BlueROV2, scheme 0, PoseSensor, VelocitySensor e camera. Il sonar è un carico
elettrico modellato; questo scenario leggero non genera immagini sonar.
--show-viewport apre la finestra; --scenario permette un altro JSON nativo.

Le demo inizializzano il mondo con reset() prima degli step e rispettano i limiti
di forza pubblici del simulatore. Verifica esplicita del movimento con derating:

    & "C:\Users\Andrea\miniconda3\envs\holoocean_joystick\python.exe" examples\verify_holoocean_integration.py --backend holoocean --steps 60 --output-dir logs\holoocean

Vedi [verifiche](docs/verification.md) per risultati e limiti scientifici.

La v0.1 distingue esplicitamente L0 (energia ideale, tensione e temperatura di
riferimento costanti) da L1 (Rint elettro-termico). L2 resta futuro. Il supporto
generico R(SOC,T) accetta misure dell'utente; nessuna nuova curva è attribuita
alla batteria Blue Robotics.

Confronto con gli stessi comandi:

    .venv\Scripts\python.exe examples\compare_energy_models.py --backend synthetic --steps 300 --output-dir logs\comparison

Sono disponibili importazione delle mappe misurate, sensitivity/Monte Carlo con
incertezze esplicite, manifest di calibrazione/validazione separati e valutazione
dei log sincronizzati. Comandi e formati sono in
[strumenti sperimentali](docs/experimental_tooling.md):

    .venv\Scripts\python.exe -m holoenergy.analysis.cli --help

La provenienza comprende commit, versioni, scenario, profili/configurazione risolti,
seed, placeholder e hash dei dati. Il completamento dei comandi resta distinto
dal raggiungimento dell'obiettivo della missione, che richiede un criterio esplicito.

Stato delle evidenze:

- **VERIFIED SOFTWARE BEHAVIOUR**: test numerici e integrazione nativa HoloOcean.
- **DATASHEET-BASED PARAMETERS**: rating del pack, dati T200, massimi camera/Ping360.
- **PLACEHOLDER PARAMETERS**: OCV/R, mappe termiche, C_th/k, hotel e convertitori.
- **EXPERIMENTALLY CALIBRATED PARAMETERS**: nessuno sul BlueROV2 del progetto.
- **EXPERIMENTALLY VALIDATED RESULTS**: nessuna validazione fisica quantitativa.

Licenza MIT per codice e documentazione del progetto; [NOTICE](NOTICE) distingue
i diritti dei dati del produttore. [CITATION.cff](CITATION.cff) e
[CONTRIBUTING.md](CONTRIBUTING.md) definiscono citazione e rilascio. La CI verifica
Python 3.10–3.13 su Linux/Windows; i test Unreal/GPU restano manuali.
