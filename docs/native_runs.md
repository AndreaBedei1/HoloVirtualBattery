# Native HoloOcean and DESERT runs

How the native results in [`experiments/results/native`](../experiments/results/native) were
produced, and how to reproduce them without disturbing other simulations on the same
machine.

## 1. Verified backend (required for quantitative runs)

1. Build separate packages with the drag-units patch and an unpatched control
   ([holoocean_patched_build.md](holoocean_patched_build.md), `--engine-kind launcher`).
2. Verify at 100 Hz before any experiment:

   ```powershell
   $py = 'F:/Andrea/HoloWithDesertCommunications/.venv/Scripts/python.exe'   # HoloOcean 2.3.0 env
   $after = 'C:/HOB/packages/patched-after/Ocean/Windows/Holodeck/Binaries/Win64/Holodeck.exe'
   & $py tools/check_holoocean_backend.py --binary $after --source-dir C:/HOB/src/after --ticks-per-sec 100 --output experiments/results/native/backend/check_patched_after.json
   ```

   Required: `PASS`, observed/expected drag 1.000000 (current and still water), physics/client
   step ratio 1.000000. The campaign scripts refuse a package without a build manifest
   that records the patch, and a source tree without the unit conversion.
3. Use 100 Hz (`DT = 0.01`). 20 Hz is never used for quantitative results
   ([holoocean_timestep_report.md](holoocean_timestep_report.md)).

## 2. Running next to other HoloOcean instances

HoloOcean 2.3 on Windows opens no TCP port for its client channel: each process is
identified by a UUID that names its shared-memory blocks and semaphores. The rules used:

* inspect running `Holodeck.exe` processes first (other projects on this machine run
  their own packages from `F:/Andrea/holoocean_patched_root*`; they are never touched);
* every process HoloEnergy starts gets a fresh `uuid4` (`tools/holoocean_backend.make_env`)
  and runs from its own package directory (`C:/HOB/packages/...`), so logs and `Saved/`
  state are never shared with another installation;
* at most two HoloEnergy instances at a time (the campaign is split into two processes
  with disjoint `--runs`); every process is closed in a `finally` block;
* the installed package (`%LOCALAPPDATA%/holoocean/2.3.0`) is not launched by the
  campaign, so its logs are never written.

Wall-clock speed depends on machine load (real-time factor 0.3-0.5 with six concurrent
instances); the physics is synchronous and fixed-step, so results do not depend on it.

## 3. DESERT engine

`holo_desert` would start (or reuse) its Compose service `holo-desert` on port 5555 when
no healthy engine answers. To never recreate another user's container, HoloEnergy runs
its own engine container on a non-default port and always passes `manage_engine=False`:

```bash
docker run -d --name holoenergy-desert-5571 --label owner=holoenergy-campaign --init --cpus=2 --memory=2g -p 127.0.0.1:5571:5555 holo-desert-engine:4.0.0-v2
```

The image `holo-desert-engine:4.0.0-v2` is the engine that `holo_desert` builds from
`uwsignet/desert:4.0.0` (`holo-desert engine up` in HoloWithDesertCommunications, or the
Dockerfile in `src/holo_desert/resources/docker`). The engine fingerprint reported by the
container must equal the package's (here `755d96a2c67be143`):

```powershell
& $py -c "from holo_desert.desert_adapter.backend import DESERTAdapter as D; from holo_desert.resources.docker.stack_builder import engine_fingerprint as f; print(D(port=5571).health_info()['engine_fingerprint'], f())"
```
Stop and remove only this container afterwards (`docker rm -f holoenergy-desert-5571`).

```powershell
& $py tools/check_desert_noninterference.py --mode native --port 5571 --output experiments/results/native/desert/noninterference_native.json
& $py experiments/run_comm_matrix.py --port 5571
```

## 4. Campaign commands

Interpreters: `$py` (the HoloOcean 2.3.0 environment, which also has `holo_desert`) for every
native and DESERT command; `uv run python` (the locked HoloEnergy environment) for the offline
campaign and the analysis; any Python with matplotlib for the figures. To reproduce without
overwriting committed results, pass a scratch location: `--output-dir` (native campaign,
figures), `--full-trace-dir`, `--output` (DESERT scripts, offline campaign), `--native-dir` /
`--tables-dir` (analysis).

```powershell
& $py experiments/run_native_campaign.py --binary $after --source-dir C:/HOB/src/after --list
& $py experiments/run_native_campaign.py --binary $after --source-dir C:/HOB/src/after --runs N1_layouts
& $py experiments/run_native_campaign.py --binary $after --source-dir C:/HOB/src/after --runs N2_orientation N3_heave N4_mission N5_suites N6_battery
& $py experiments/run_crosslayer.py --binary $after --port 5571
python experiments/analyze_native_campaign.py
python experiments/make_paper_figures.py
```

Full per-tick traces are written to `logs/native_campaign/` (not committed; SHA256 in each
summary); 0.1 s traces are committed next to the summaries.

## 5. Reproducibility record (per run)

Each `*.summary.json` stores: HoloEnergy version and git state; backend identity
(executable/PDB SHA256, package config SHA256, build manifest with HoloOcean commit
`49e70552`, patch SHA256 `00f1b303…`, toolchain); the source parameters actually used for
the chain closure; physics rate; instance isolation; scenario; controller gains (user
policy, not calibrated); evidence registry version and size; the run specification
(layout, mapping, current, plan, suite, battery changes); random seed (none: the plan and
controller are deterministic). DESERT outputs store the `holo_desert` version, the engine
port, the scenario (including its RNG `seed`) and the traffic definition; the engine image
digest is `sha256:dce313c4…` (`holo-desert-engine:4.0.0-v2`, base `uwsignet/desert:4.0.0`).
