# Generic marine energy framework

Schema version 1. Il core tratta un agente e un pack a scarica unidirezionale.
Le configurazioni originali di v0.1.0 continuano a funzionare. Le nuove chiavi
`vehicle`, `actuators`, `components`, `environment`, `telemetry` e `payload`
aggiungono genericità senza sostituire i modelli numerici consolidati.

## Ownership e contratto con HoloOcean

| Quantità / funzione | Responsabile | Scambio con HoloEnergy |
| --- | --- | --- |
| Massa, volume, centri, drag, added mass | Asset/scenario/backend dinamico | Descrizione o adapter esplicito |
| Corrente, moto, collisioni, sensori | HoloOcean | API pubblica ambiente e osservazioni |
| Controller / allocazione geometrica | Applicazione utente | Vettore di sforzi diretti |
| Curve elettriche, carichi, batteria, calore | HoloEnergy | Stato `Energy` |
| Limiti elettrici | HoloEnergy | Sforzi ridotti inviati al backend |

Il `control_contract` dichiara `action_units`, `thruster_count`, `dt_s` e, quando
applicabili, `agent_name`, `agent_type`, `control_scheme`. Gli ultimi campi sono
confrontati se richiesti dal profilo. Il nome storico `thruster_count` rimane per
compatibilità e descrive la lunghezza del vettore diretto. Il wrapper verifica
anche i limiti pubblici di `action_space` quando presenti.

`force_N` indica sforzi firmati in newton. `normalized_command` indica il
comando normalizzato delle tabelle, non una forza o un'accelerazione. Il backend
deve interpretare la stessa unità; un controller Fossen/high-level che accetta
velocità o accelerazioni non può essere passato direttamente. Un adapter deve
esporre gli sforzi fisici e reinserire le limitazioni nella dinamica.

`apply_derating_to_actions: true` richiede un contratto e invia azioni limitate.
Il default false mantiene la modalità accounting: `dynamics_energy_consistent`
segnala quando gli sforzi sono stati applicati coerentemente con i limiti.
`ticks=N` esegue N tick fisici, non un unico aggiornamento energetico lungo N dt.
Potenza del risultato aggregato è una media temporale; SOC, cumulative Wh, stati
e osservazioni sono quelli finali. I log conservano ogni tick.

## VehicleProfile e payload fisico

```yaml
vehicle:
  name: CustomROV
  kind: ROV
  dynamics_source: user-configured backend
  dynamics_mode: descriptive
  mass_kg: 20
  volume_m3: 0.020
  center_of_mass_m: [0, 0, 0]
  center_of_buoyancy_m: [0, 0, 0.02]
  dimensions_m: [0.6, 0.4, 0.3]
  drag: {coefficient: 0.8, reference_area_m2: 0.15}
  payload:
    - name: scientific_equipment
      mass_kg: 5
      displaced_volume_m3: 0.005
      position_m: [0.1, 0, 0]
  actuator_layout:
    - {id: actuator_1, position_m: [0, 0, 0], direction: [1, 0, 0]}
  metadata:
    status: USER-SUPPLIED
    source: demonstration values; not identified dynamics
```

Posizioni/centri sono nel frame body definito dal backend; unità SI e convenzione
assi vanno dichiarate nei metadata. `direction` è un vettore unitario. Il layout
è descrittivo: non viene usato per inventare un'allocazione geometrica.
`payload` può essere una mappa, una lista, oppure la chiave root equivalente.
Servono insieme massa, volume spostato e `position_m`. La densità del payload è
una quantità derivabile da massa/volume; il framework non presume neutralità.
Il numero 5 kg non attiva alcun carico elettrico o thrust automatico.

In `descriptive` questi valori vengono registrati, con status e warning che
esplicitano che non sono applicati. Per usarli nella fisica:

```python
class MyDynamicsAdapter:
    def configure_vehicle(self, profile):
        # Applicare al proprio backend massa, volume, centri e payload.
        # Questa funzione deve avere una implementazione verificata per quel backend.
        ...

    def set_environment(self, values):
        ...
```

Selezionare `dynamics_mode: adapter` e passare `dynamics_adapter=...` al wrapper.
Un adapter mancante viene rifiutato. Anche reset richiama configure_vehicle.
Non è fornito un adapter universale Unreal perché la API pubblica HoloOcean
avverte che cambiare le proprietà Python non cambia l'asset C++.
Per aggiungere added mass/drag più complessi usare la configurazione nativa del
modello dinamico; non sono reinterpretati nel core elettrico.

## Attuatori

`actuators` è una lista di profili oppure gruppi con `count`; `id` opzionale
genera ID univoci per il gruppo. Tutti condividono `action_units`, coerente con
il backend. Il resolver produce il contratto `propulsion` storico per conservare
compatibilità. Non c'è alcuna assunzione su otto unità o modello T200.

```yaml
actuators:
  - {id: main, count: 2, model: custom_lookup, profile: main_motor.yaml}
  - {id: trim, count: 4, model: custom_lookup, profile: trim_motor.yaml}
```

Formato command–force–power, per ogni tensione e direzione:

```yaml
model: custom_lookup
voltage_tables:
  - voltage_V: 24
    forward:
      - {command: 0, force_N: 0, power_W: 0}
      - {command: 1, force_N: 30, power_W: 150}
    reverse:
      - {command: 0, force_N: 0, power_W: 0}
      - {command: 1, force_N: 20, power_W: 120}
```

Una singola tensione ha dominio esattamente a quella tensione. Servono più
tabelle per un pack variabile. Curve monotone, origine zero, dati finiti e
potenze non negative sono obbligatori. L'interpolazione è lineare in ciascuna
tabella e tra tensioni. Non si estrapola oltre la massima forza; la tensione
fuori dominio attiva le restrizioni esistenti, senza inventare una curva nuova.
Per modelli eterogenei il dominio utilizzabile è l'intersezione dei domini.
La tensione nominale del pack deve rientrarvi già alla costruzione.

`force_power_tables` usa `forward: [[force_N, power_W], ...]`, con reverse
separato. Non consente normalized_command. La coordinata normalizzata interna
serve solo a riutilizzare l'interpolatore: non rappresenta PWM misurato.

`ActuatorEnergyModel.power(action, voltage, units)` è il confine elettrico
generale. Il distributore propulsivo diretto richiede inoltre
`DirectEffortActuatorModel`: `min_voltage`, `max_voltage`, `tables`,
`max_force(voltage, direction)` e `force(command, voltage)`. Registrare una factory
Python con `register_actuator_model`; YAML non importa/esegue codice.
Una factory parametrica deve fornire dominio e provenienza delle equazioni.
Il core non propone una legge forza–potenza universale.

## Componenti elettrici

`ElectricalComponent` accetta `name` univoco, `model/type: generic_load`,
`category: sensors|compute|auxiliaries`, stati uppercase e potenza W.
`active_W` è una scorciatoia per ACTIVE; non usarla insieme a states.ACTIVE.
Default iniziale ACTIVE se esiste, altrimenti OFF. OFF mancante è derivato a
zero per rail gating; gli altri stati devono essere dichiarati dall'utente.
OFF esplicito può rappresentare standby non nullo. STARTING con
`startup_duration_s` richiede STARTING e ACTIVE ed integra esattamente i confini
temporali. I componenti legacy continuano a usare startup/ping/brownout originali.

`power_model: {type: lookup, input: ..., initial_value: ..., points: ...}`
interpola una curva operativa fornita, in ACTIVE per default oppure nella lista
`states` esplicita. Input e unità sono dichiarati dal profilo; valori fuori
dominio vengono rifiutati. Aggiornare con
`env.energy.set_component_input(name, input_name, value)` oppure keyword.
Un componente non può cambiare a uno stato non configurato.
La compatibilità `env.set_payload_state` rimane disponibile.

Il carico hotel storico viene attribuito ad auxiliaries con i suoi nomi e
`hotel_constant`. Nelle nuove configurazioni generic, hotel omesso significa
zero derivato: tutti i consumi devono essere nei componenti. Gli ID di attuatori,
componenti e hotel non possono collidere. Le efficienze dei convertitori seguono
le tre categorie legacy propulsion/payload/hotel; payload comprende le nuove
categorie e l'attribuzione delle perdite resta separata.

## Batteria, temperatura e autonomia

L0: energia ideale a tensione costante, capacità Wh, SOC e almeno un limite
di corrente/potenza. Nessuna generazione termica; la temperatura di riferimento
resta costante, mentre water_temperature_C viene registrata.

L1: pack Rint con OCV, R, capacità Ah e thermal one-node. Le mappe in temperatura
e SOC sono quelle documentate in [scientific_sources.md](scientific_sources.md).
Calore irreversibile I²R e termine entropico solo se fornito. La temperatura
dell'acqua varia a runtime senza cambiare direttamente SOC o aggiungere energia.
`environment.water_temperature_C` e il vecchio campo thermal devono essere
coerenti; dichiarazioni contrastanti sono rifiutate.

`chemistry` e `cells` descrivono un pack. Non derivano OCV/R/capacità da un nome
chimico, non scalano automaticamente dati cella e non simulano celle individuali.
Si può quindi usare qualsiasi pack misurato senza conoscere le singole celle.

`remaining_energy_Wh` L0 = SOC × capacity_Wh. L1 integra esattamente a tratti
OCV sulla carica accessibile sopra la coda indisponibile in temperatura:
Q_ref × integral(U_ocv(s,T), s_unavailable..SOC). È un limite superiore di lavoro
OCV alla temperatura corrente, senza sag/cutoff futuro. Le stime istantanea e
rolling dividono questa energia per potenza terminale osservata; possono essere
ottimistiche. Potenza zero dà null, non infinito. `env.energy.endurance(window_s)`
accetta finestre positive fino a 60 s; default 60 s, riporta la durata osservata.

## Ambiente e osservazioni

`set_environment` valida prima tutte le modifiche. Temperatura acqua °C,
`current_velocity_m_s` vettore 3 SI, `water_density_kg_m3` positivo e
`current_mode: descriptive|native|adapter` sono espliciti. Descriptive registra
soltanto; native usa il metodo pubblico `set_ocean_currents(agent_name, vector)`.
La modalità native richiede agent_name e rifiuta un contratto Fossen dichiarato.
Non supporta cambiamento della densità. Adapter richiede set_environment(values).
Passare da ambiente applicato a descriptive viene rifiutato per evitare di
nascondere una modifica fisica ancora attiva. Reset ripristina l'ambiente iniziale.

L'osservazione `VehicleState` esplicita usa linear_speed_m_s, angular_speed_rad_s,
acceleration_m_s2, depth_m. In alternativa sono letti VelocitySensor, PoseSensor e
DynamicsSensor documentati, NWU/SI. Canali assenti restano null, senza velocità
inventata. `actuators` riporta comando originale, sforzo inviato, forza stimata
dalla curva e potenza. È un valore sottoposto al backend, non una misura di
thrust effettivo dell'elica né di saturazioni private successive del motore.

Le correnti di HoloOcean nativo e quelle Fossen hanno contratti differenti.
L'ispezione del sorgente 2.3 trova densità 997 kg/m³ costante e una possibile
conversione mancante newton→centinewton nel drag, mentre gravità/buoyancy la
applicano. Non è stato modificato il motore; servono test dimensionali della
build esatta prima di usare il test correnti per conclusioni quantitative reali.
Vedi il registro scientifico e `sources/generic_native_source_inspection.json`.

## Accounting, log e replay

Ogni tick integra W × dt / 3600 per categoria e per dispositivo. Bilancio:
terminal = propulsion + sensors + compute + auxiliaries + converters;
OCV work = terminal + battery_losses. `mark_phase(name)` marca i tick successivi;
ripetere un nome accumula nella stessa fase. Summary include durata, Wh e perdite
per fase, percentuali rispetto a OCV work e stime endurance. Reset conserva il
summary dell'episodio precedente e azzera quello corrente.

Chiusura genera `.summary.json` e `.summary.csv` se logging abilitato; una
eccezione registra stato partial e chiude comunque logger/telemetria/backend.
La telemetria è separata dall'accounting: pacchetti persi non perdono energia
nei log o summary. Eventi reset/fine missione indicano il ciclo di vita UI.

Il CSV missione conserva time_s tick-start, action JSON, sensor_states legacy,
water_temperature_C, phase, component_states JSON, component_inputs JSON.
Replay energetico non determina posizione, successo missione o corrente fisica.
La suite di sensitivity, calibrazione e validazione separata rimane invariata.

## Estensioni future

Il pack è isolato dai carichi e il distributore separato dai modelli: un futuro
manager multi-bus potrà usare più istanze batteria e instradare carichi/attuatori.
L'attuale summary single-pack non aggrega reti/pacchi e non dichiara multi-battery
già implementato. Lo stesso confine permette planner/replay futuri, con criteri
di completamento espliciti. Aging, BMS, PDE, CFD e coordinamento multi-agent
rimangono fuori dallo scope.
