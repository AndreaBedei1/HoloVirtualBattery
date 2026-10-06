# Report di consolidamento HoloEnergy v0.1

Data: 2026-10-06. Repository: AndreaBedei1/HoloVirtualBattery.
Le evidenze sono software/simulatore. Nessuna validazione fisica quantitativa è
stata eseguita sul BlueROV2 reale. Dettagli numerici e riproduzione sono in
[verification.md](verification.md); formati/API in
[experimental_tooling.md](experimental_tooling.md).

1. **Stato iniziale.** Checkout pulito d179584, branch locale/remoto
   feature/holoenergy-battery-model, origin configurato, main assente. Analizzati
   documenti, tutti i modelli/profili/configurazioni/esempi/test e storia recente
   prima di modificare i file. La suite iniziale aveva 62 test superati.

2. **Modifiche.** Consolidata l'architettura esistente esterna a HoloOcean:
   livelli espliciti, mappe misurate opzionali, dominio T200 rigoroso, brownout
   configurabile, provenienza e strumenti offline. Nessuna riscrittura del core,
   fork HoloOcean, nuova fisica del sonar o interfaccia verso hardware.

3. **File.** Modificati config/wrapper/logging e battery/thermal/payload/
   propulsion/power_manager; aggiunti provenance.py e holoenergy/analysis con
   metriche, replay, sensitivity, importazione, dataset, valutazione e CLI.
   Aggiunti compare_energy_models.py, archive_verification.py e quattro moduli
   di test; aggiornati demo/helper/importer T200 e relativo solo metadata.
   Aggiunti experimental_tooling.md, questo report, archivio delle verifiche,
   sette record di ricerca, LICENSE/NOTICE/CITATION.cff/CONTRIBUTING e CI.
   Aggiornati README, design, fonti, protocollo, verification, packaging.

4. **Problemi trovati.** Lookup di domanda fuori dominio silenziosamente saturo;
   supporto di forza non garantito nelle due tensioni adiacenti; radice termica
   soggetta a cancellazione per R piccolissima e calore entropico; radice Rint
   pubblica non fisica per potenza impossibile; limiti di calibrazione singleton
   ignorati; metadati incompleti per errori prima del primo campione e run senza
   file; Git di una wheel installata sotto un altro checkout attribuibile per
   errore al package; riferimenti Q/I importati non confrontati con il profilo.
   La distribuzione sorgente richiedeva inoltre conftest completo.

5. **Correzioni.** Consumo applicato limitato al dominio comune dei dataset,
   domanda satura marcata, radici stabili/errore esplicito, flag di dominio,
   hash codice e stato parziale degli errori, controllo reale della posizione
   del checkout e dei riferimenti Q/I. Test indipendenti dai dati fisici verificano
   ciascuna correzione; le aspettative fisiche precedenti restano superate.

6. **L0.** Bucket Wh, SOC energetico, tensione nominale costante, zero R/perdita
   interna, T fissa di riferimento senza feedback termico. Limiti applicativi
   espliciti e carichi/allocazione comuni. Ah×V nominali non sono Wh usabili misurati.

7. **L1.** Coulomb counting di riferimento, OCV(SOC,T), R, sag, limiti I/P/Q,
   cutoff latched, capacità accessibile e temperatura dinamica. Derating non
   lineare e perdite interne/converter separate. Nessuno stato RC aggiunto.

8. **R(SOC,T).** Supporto generico di griglia comune con ohm assoluti e
   interpolazione bilineare; non imposta monotonia in SOC. Fallback R(T) invariato.
   Nessuna curva nuova per Blue Robotics: servono misure DC del pack a SOC/T noti.

9. **Termica.** Un nodo C_th dT/dt=I²R−k(T−T_water), con entropy opzionale misurata.
   Soluzione esatta per ingressi costanti nel tick. C_th/k/onset non calibrati;
   cutoff 50 C dal guide, water/initial T ingressi di scenario. Due nodi differiti
   a evidenze di residui/time constants non descritti dal modello semplice.

10. **Thruster.** Workbook ufficiale originale, forward/reverse e dipendenza
    dalla tensione conservati. Nove correzioni di inviluppo e una discrepanza del
    workbook restano tracciate. Curve static/bollard: inflow, velocità del veicolo,
    interazione e installazione richiedono misure; nessun fattore arbitrario.

11. **Payload.** Hardware identificato distinto dal sensore simulato. OFF/IDLE/
    STARTING/ACTIVE/PINGING conservati; valori sconosciuti restano null/errori.
    Manual sempre disponibile; sensor_linked non implementato per assenza di
    contratto pubblico elettrico HoloOcean. Brownout discreto opzionale con soglie
    e ritardo utente, disabilitato nei profili forniti; non è un reboot esatto.

12. **Sensitivity/uncertainty.** Runner separato, parametri scalari selezionati
    dall'utente, perturbazioni o valori espliciti, Monte Carlo uniform/normal/
    choice con seed e indipendenza dichiarati. Nessuna incertezza BlueROV2 assunta.
    Tutti i draw, inclusi quelli invalidi, restano nei risultati CSV/JSON.

13. **Dati reali.** Import di mappe identificate OCV/R e Q/I senza imputazione;
    log sincronizzati con mapping colonne; metriche elettriche, termiche, Wh/SOC,
    eventi, riserva e missione. Mancanti restano null. Manifest hash/ID/gruppi
    distinguono identificazione, model selection e final validation. Il tool non
    rende indipendente un dataset falsamente dichiarato e non calibra da solo.

14. **Provenienza.** UUID/UTC, commit e dirty status o assenza esplicita Git,
    versioni, hash codice, scenario, configurazione/profili risolti e hash,
    input/output, seed, placeholder e status dichiarati. Replay conserva anche
    comandi e hash. I sidecar sono necessari per ricostruire le run.

15. **Test.** 106 superati su Python 3.13.12 e nell'archivio sorgente estratto;
    105 superati/1 skip appropriato su Python 3.10.20 con HoloOcean. Ruff lint e
    format passano. Import T200 riproducibile; wheel/sdist costruiti e wheel
    verificata in isolamento con sola PyYAML. CI remota: **8 job superati** su
    Linux/Windows × Python 3.10/3.11/3.12/3.13, per il commit 70f584f.
    [Run GitHub Actions](https://github.com/AndreaBedei1/HoloVirtualBattery/actions/runs/37451876879).

16. **HoloOcean nativo.** Ambiente esistente 2.3.0, nessuna reinstallazione/core
    modificato. Initialization/reset/zero/direct movement/accounting/derating/
    limite potenza/payload/chiusura verificati. Con cap di test 8 A: surge 2,473942 m
    vs 4,674221 m; azioni 9,812758 vs 20 N, confrontate con argomenti dello step
    nativo. L0/L1 su 300 comandi: 0,895634/0,879417 Wh. Sonar OFF/ACTIVE:
    0,860258/0,879417 Wh. Nessun criterio di goal: mission completion null.

17. **Placeholder.** OCV demo, R=0,04 ohm, identità in temperatura, C_th=1200 J/K,
    k=2 W/K, onset 40 C, hotel 15 W, efficienze payload/hotel 0,9. Massimi camera
    1,1 W/Ping360 5 W sono upper bound da datasheet, non medie misurate.

18. **Limiti aperti.** Rint/quasi-statico, capacità accessibile come convenzione
    da calibrare, T media del pack, coefficienti medi dei convertitori, effetto
    della discretizzazione sul cutoff, assenza di polarization/inflow/hot-cell/
    reboot esatto. Monte Carlo indipendente senza copertura adattativa. Nessun
    claim di accuracy fisica, sicurezza termica o autonomia reale.

19. **Misure necessarie.** V/I calibrati, OCV rilassata e resistenza DC pack con
    protocollo a SOC/T multipli, Q accessibile senza duplicare sag, limiti continui,
    calore/scambio dell'enclosure, carichi di stato/rail e boot, converter losses,
    mounted thrust/PWM/force, movimenti hover/surge/sway/yaw/verticale e missioni
    indipendenti. Identificare DVL/sonar diversi prima di assegnare consumi.

20. **Commit creati.** e649c1d (livelli/mappe/policy/provenienza), da7c6fb (tooling),
    03adda7 (dominio/azioni native), cae8ad7 (riferimenti import), 40da419 (CI/release),
    6fe86ea (fonti/workflow), 69023f0 (sdist), ffe417b (errori/finalizzazione),
    db660a7 (provenienza del codice), fb0d9a5 (test senza Git), 70f584f (archivio).
    Il commit del report finale è successivo; nessuna storia riscritta.

21. **Push.** feature/scientific-consolidation pubblicato su origin al commit
    70f584f con permessi verificati; nessun force push. Il branch originario e
    tutti i suoi commit sono conservati. La pubblicazione finale usa main come
    stabile e feature/scientific-consolidation come branch di sviluppo, entrambi
    con la storia completa. Non viene aggiornato forzatamente alcun ref.

22. **Versione/tag.** Metadata coerenti 0.1.0, licenza MIT con NOTICE separato per
    materiali terzi. Release v0.1.0 preparata sul commit di questo report da
    checkout pulito verificato; il tag annotato è creato nella pubblicazione
    finale. Ref/hash/esito definitivo sono verificati nella consegna. Il numero
    di release non costituisce validazione sperimentale.
