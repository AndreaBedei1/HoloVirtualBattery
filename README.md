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
