# Passo fisico di HoloOcean 2.3.0: clock client vs integrazione UE 5.3

Audit del 7 ottobre 2026. Domanda: a 20 Hz il clock della simulazione avanza di
0.05 s per tick, ma gravity e thruster dell'audit drag erano coerenti con un
passo di 1/30 s. Si tratta di un limite documentato di HoloOcean o di una
divergenza non documentata fra clock e fisica?

**Risultato in breve.** Il passo integrato dal solver è
`min(1/ticks_per_sec, MaxPhysicsDeltaTime)` con il default UE 5.3
`MaxPhysicsDeltaTime = 1/30 s` e substepping disattivato. Sopra i 30 Hz clock
client, DeltaTime del mondo e passo fisico coincidono; sotto i 30 Hz la fisica
integra solo 1/30 s per tick mentre clock, sensori e HoloEnergy avanzano di
1/tps. È un comportamento documentato di Unreal ma **non documentato né
intercettato da HoloOcean** (scenario B). Frequenza nativa raccomandata per
HoloEnergy: **100 Hz**. I numeri sono nelle sezioni 4–6 e nei file
[`sources/verified_backend/timestep_*`](../sources/verified_backend).

## 1. Catena del tempo (fonti primarie)

| Livello | Codice | Comportamento |
| --- | --- | --- |
| Client Python | `holoocean/environments.py` 2.3.0 | `state["t"] = num_ticks / ticks_per_sec`; default `ticks_per_sec = 30`; il timestamp è calcolato dal client, non letto dal motore |
| Server HoloOcean | `HolodeckWorldSettings.{h,cpp}`, `AdjustTPSCommand.cpp` | `FixupDeltaSeconds` restituisce `ConstantTimeDeltaBetweenTicks = 1/TicksPerSec` (float): DeltaTime del mondo fisso a 1/tps |
| Sensore | `DynamicsSensor.cpp` | accelerazione = Δv / DeltaTime del mondo |
| UE 5.3.2 | `PhysicsCore/Private/ChaosScene.cpp`, `FChaosScene::SetUpForFrame` | senza substepping `MDeltaTime = min(DeltaSeconds, MaxPhysicsDeltaTime)`; il tempo eccedente non viene accumulato |
| UE 5.3.2 | `Engine/Private/PhysicsEngine/PhysicsSettings.cpp` | default `MaxPhysicsDeltaTime = 1/30`, `bSubstepping = false`, `bTickPhysicsAsync = false`; non modificati da `BaseEngine.ini` né dal `DefaultEngine.ini` di HoloOcean (voci commentate) |
| UE 5.3.2 | `Chaos/PBDRigidsEvolutionGBF.h`, `Integrate` | `V += a·dt; V *= max(0, 1 − c·dt); X += V·dt` |

Predizione senza fitting: `dt_fisico = min(f32(1/tps), f32(1/30))`.
La documentazione ufficiale di HoloOcean 2.3.0
([scenarios](https://byu-holoocean.github.io/holoocean-docs/v2.3.0/usage/scenarios.html))
descrive `ticks_per_sec` come numero di tick per secondo di simulazione, da tenere
sopra le frequenze dei sensori, default 30; non indica un minimo né il limite del
passo fisico.

## 2. Metodo

`tools/audit_holoocean_timestep.py`, solo nativo (nessun import HoloEnergy, nessun
controller), BlueROV2 in `SimpleUnderwater`, avvio identico per tutte le build.
Per ogni frequenza 20, 30, 40, 60, 100, 200 Hz, tre ripetizioni, 12 passi per caso:

| Stimatore | Caso | Indipendenza |
| --- | --- | --- |
| Gravity | caduta in aria da z = 20 m | ricorsione `v[n+1] = (v[n] − g·dt)(1 − c·dt)` per qualunque `v[n]` |
| Spinta nota | 10 N netti lungo X in acqua, primo passo da fermo | `v1 = (F/m)·dt·(1 − c·dt)`; drag nullo da fermo |
| Damping | moto orizzontale a 1 m/s in aria | `dt = (1 − v[n+1]/v[n]) / c`: indipendente da massa e forze |
| Cinematica | stessi moti lungo X | `dt = (x[n+1] − x[n]) / v[n+1]`: indipendente da massa, forze e damping |
| DeltaTime del mondo | tutti | `Δv / a_sensore` |

`g = 9.8 m/s²` (gravity del mondo verificata dall'audit drag), `m = 11.5 kg`,
`c = 1 s⁻¹` dal sorgente. Il passo efficace è la media dei tre stimatori dinamici;
quello cinematico è un controllo indipendente. Criterio di coerenza
`|dt_fisico / dt_client − 1| < 1e−4`, ampio rispetto alla precisione float32 dei
sensori ma severo rispetto a qualunque divergenza reale.

Con `--drag-stability` si aggiunge una decelerazione in acqua ferma da 2.5 m/s,
confrontata con la soluzione continua esatta di `m dv/dt = −K v|v| − c m v`
(`K = ρ·Cd·A/2` per la scala effettiva della build): misura l'errore del passo
esplicito quando il drag è corretto.

## 3. Risultati: passo integrato per frequenza

Identici sulle tre build (ufficiale, controllo con raw bit-identico, patchata):
la patch del drag non tocca il passo temporale. Valori della build ufficiale,
media su 3 ripetizioni ([report](../sources/verified_backend/timestep_original/report.json)):

| tps | dt client s | DeltaTime mondo s | dt gravity s | dt spinta s | dt damping s | dt cinematico s | dt fisico / client | Esito |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 20 | 0.050000 | 0.050000001 | 0.0333333373 | 0.0333333337 | 0.0333333340 | 0.0333333350 | **0.6666667** | divergente |
| 30 | 0.033333 | 0.033333335 | 0.0333333373 | 0.0333333337 | 0.0333333340 | 0.0333333350 | 1.0000001 | coerente |
| 40 | 0.025000 | 0.024999999 | 0.0249999999 | 0.0249999997 | 0.0250000018 | 0.0250000002 | 1.0000000 | coerente |
| 60 | 0.016667 | 0.016666667 | 0.0166666684 | 0.0166666669 | 0.0166666633 | 0.0166666675 | 1.0000000 | coerente |
| 100 | 0.010000 | 0.010000000 | 0.0100000004 | 0.0099999994 | 0.0100000000 | 0.0099999997 | 1.0000000 | coerente |
| 200 | 0.005000 | 0.005000000 | 0.0050000002 | 0.0050000000 | 0.0050000013 | 0.0049999998 | 1.0000001 | coerente |

Quattro stimatori indipendenti (dinamici e cinematico) concordano entro ~1·10⁻⁸
relativo; lo scarto dalla predizione `min(f32(1/tps), f32(1/30))` è ≤ 1.7·10⁻⁷.
A 20 Hz il DeltaTime del mondo (sensori, controller nativi) è 0.05 s mentre la
fisica integra 1/30 s: tutti gli effetti di forza per secondo di clock risultano
scalati di 2/3, come già osservato nell'audit drag (spinta 10 N → m·a 6.4444 N,
gravità −6.3156 m/s², stessi numeri predetti con dt = 1/30). A 30 Hz il passo
coincide esattamente col cap (1/30 in float, stesso valore della costante UE).

## 4. Il passo con il drag corretto: decelerazione in acqua ferma

Caso aggiuntivo: veicolo impostato a 2.5 m/s, corrente nulla; il primo tick dopo
l'impostazione è già un passo di drag. Build patchata:

| tps | K·v₀·dt/m | v dopo 1 passo misurata | Eulero esplicito predetto | Soluzione continua | Errore 1° passo | max \|misurato − continuo\| |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20, 30 | 1.300 | −0.726 (inversione) | −0.726 | 1.061 | −168% | 1.79 m/s |
| 40 | 0.975 | 0.060 | 0.060 | 1.242 | −95% | 1.18 m/s |
| 60 | 0.650 | 0.860 | 0.860 | 1.495 | −42% | 0.63 m/s |
| 100 | 0.390 | 1.509 | 1.509 | 1.783 | −15% | 0.27 m/s |
| 200 | 0.195 | 2.002 | 2.002 | 2.082 | −3.9% | 0.10 m/s |

Il backend integra esattamente la propria equazione con Eulero esplicito
(|misurato − predizione| ≤ 1·10⁻⁷ m/s a tutte le frequenze): non è un difetto di
implementazione. È però un limite numerico che con il drag 100 volte troppo debole
era invisibile: con `K/m = 15.6 m⁻¹` (BlueROV2 di HoloOcean) l'accuratezza dei
transitori dipende da `K·|v_rel|·dt/m`. Per le velocità relative di questo lavoro
(≤ 0.8 m/s) il prodotto vale ≤ 0.125 a 100 Hz e ≤ 0.062 a 200 Hz. Nota di
revisione: la prima versione del riepilogo partiva dallo stato dopo il priming;
l'analisi è stata corretta e ricalcolata dai raw archiviati (invariati), il report
iniziale è conservato (`report_initial_analysis.json`).
## 5. Bug o limite documentato?

* **Unreal Engine**: comportamento documentato e voluto. Senza substepping il passo
  è limitato a `MaxPhysicsDeltaTime` (default 1/30 s) per evitare instabilità con
  frame lunghi; il tempo eccedente si perde.
* **HoloOcean**: il limite non è documentato (la pagina degli scenari 2.3.0 indica
  solo il default 30 e il vincolo rispetto ai sensori), non è intercettato
  (`SetTPS`/`-TicksPerSec` accettano qualunque valore positivo) e il clock Python
  continua a contare 1/tps. Il risultato è una divergenza silenziosa fra clock della
  simulazione e tempo fisico integrato sotto i 30 Hz: **scenario B**. Non è lo stesso
  difetto del drag e va proposto come nota separata.

Possibili correzioni upstream, non applicate qui: documentare `ticks_per_sec >= 30`;
oppure impostare `MaxPhysicsDeltaTime >= 1/tps` (o abilitare il substepping) quando
si cambia il tick rate; oppure rifiutare/avvisare per tps < 30.

## 6. Frequenza nativa raccomandata per HoloEnergy

**100 Hz** (`dt = 0.01 s`), perché:

1. il passo fisico coincide con il clock (verificato) e quindi
   `dt energia = dt client = dt fisico`;
2. è la frequenza di riferimento della campagna drag (60/100/200 Hz tutte verificate);
3. con il drag corretto il passo esplicito conta: per il BlueROV2
   (`K/m = 15.6 m⁻¹`) il prodotto `K·|v|·dt/m` vale 0.16 a 1 m/s e la velocità
   relativa che si inverte in un passo è 6.4 m/s a 100 Hz contro 1.9 m/s a 30 Hz;
4. costo moderato: 200 Hz dimezza ancora l'errore di passo ma raddoppia i tick.

30–60 Hz restano corretti per il clock; 200 Hz è consigliabile per manovre a
velocità relative elevate. Gli esempi nativi di HoloEnergy rifiutano un passo
energetico più lungo di 1/30 s prima di avviare il simulatore.

Controllo di convergenza (build patchata, stesso controller): dimezzando il passo
a 200 Hz l'energia propulsiva cambia di +0.01% nello station keeping a 0.5 m/s
(3.11578 contro 3.11547 Wh) e di −0.04% nella missione a 0.2 m/s (1.48985 contro
1.49038 Wh): per queste grandezze 100 Hz è convergente.

## 7. Effetti sull'accoppiamento energetico

HoloEnergy integra la potenza su `dt_s` del proprio profilo. Con il backend nativo
il passo energetico deve coincidere con il passo fisico integrato: a 20 Hz
l'energia sarebbe integrata su 0.05 s per tick mentre il veicolo si muove per
1/30 s, gonfiando di 1.5 volte l'energia per secondo di moto simulato rispetto
alla dinamica. Gli esempi nativi ora usano 100 Hz di default e rifiutano
`dt_s > 1/30 s` prima di avviare il simulatore (`examples/_common.py`, test in
`tests/test_examples.py`). Gli esperimenti energetici di questo lavoro sono tutti a
100 Hz, con un raffinamento a 200 Hz come controllo numerico; la chiusura tick per
tick della catena forza → sforzo → potenza in anello chiuso a 100 Hz è nel
[report del backend verificato](verified_backend_report.md) (§24).

## 8. Riproduzione

```powershell
$py = 'C:/Users/Andrea/miniconda3/envs/holoocean_joystick/python.exe'
& $py tools/audit_holoocean_timestep.py --source-dir <HoloOcean v2.3.0 checkout> --drag-stability --output-dir logs/timestep_original
& $py tools/audit_holoocean_timestep.py --source-dir <patched checkout> --binary <patched Holodeck.exe> --drag-stability --output-dir logs/timestep_patched
# rianalisi deterministica dai raw archiviati, senza simulatore né sorgente HoloOcean,
# su una copia (il report viene riscritto, l'analisi iniziale resta in report_initial_analysis.json):
Copy-Item -Recurse sources/verified_backend/timestep_patched $env:TEMP/timestep_patched
& $py -c "import gzip,shutil,sys; shutil.copyfileobj(gzip.open(sys.argv[1]), open(sys.argv[2], 'wb'))" $env:TEMP/timestep_patched/raw.jsonl.gz $env:TEMP/timestep_patched/raw.jsonl
& $py tools/audit_holoocean_timestep.py --output-dir $env:TEMP/timestep_patched --reanalyze
```

La rianalisi dall'archivio riproduce gli stessi verdetti e gli stessi valori (entro
l'ultimo bit fra versioni di Python diverse); è verificata da
`tests/test_timestep_audit.py` a ogni esecuzione della CI.

Archivio: [`sources/verified_backend/timestep_*`](../sources/verified_backend) (report
corrente, report iniziale, raw JSONL compresso, scenari, hash).
