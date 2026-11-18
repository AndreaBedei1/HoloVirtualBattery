# Public measured-energy datasets for underwater vehicle missions

Search date: 2026-11-18. Scope: public datasets with measured electrical power/energy (battery V, I, or Wh) of an ROV/AUV during a mission, with speed/trajectory.

## Verified candidates

### 1. Co-Design of Marine Energy Converters for AUV Docking and Recharging, Year 3 (OpenEI MHKDR)
- Authors: G. Hollinger, R. Vivekanandan, B. Robertson, C. Rusch (Univ. of Washington), D. Okushemiya, J. Lou. Project lead C. Schmaus. DOE award EE0009449.
- Year: 2025 (data dated 24 Jul 2025; updated 22 May 2026). DOI: none listed; URL https://mhkdr.openei.org/submissions/646
- Vehicle: BlueROV2 software referenced; docking tests with an AUV; pressure data recorded on an ROV.
- Measured electrical power/energy: NOT stated on the landing page. No battery, voltage, current, or Wh variables are described. "vehicle data" from docking runs is described only generically. Keywords include "power" and "vehicle telemetry" (from search snippet, not on fetched page).
- Sampling: not stated. Conditions: O.H. Hinsdale Wave Research Laboratory, varying wave conditions.
- Files: AUV Pressure Data.zip (24.33 MB, ROS 2 bag); Hinsdale Videos 2024.zip (3.05 GB); Vehicle Docking Data.zip (15.36 GB, ROS bags). Total 18.44 GB.
- License: CC BY 4.0. Download links present. Code: github.com/Robotic-Decision-Making-Lab/underwater_docking.
- Assessment: the only openly downloadable ROS-bag dataset with BlueROV2 operation found. Whether the bags contain battery topics is UNVERIFIED and would need inspection of the bag contents (not downloaded).

### 2. Low-cost energy measurement and estimation for AUVs (De Carolis, Lane, Brown; OCEANS 2014 Taipei)
- DOI: 10.1109/OCEANS-TAIPEI.2014.6964490. Landing page: https://researchportal.hw.ac.uk/en/publications/low-cost-energy-measurement-and-estimation-for-autonomous-underwa/
- Vehicle: Nessie VII AUV.
- Measurement vs computed: the paper proposes a low-cost measurement method plus a linear model that estimates energy along a trajectory, trained by calibration. The landing page does not state whether the reference is electrical sensing. Treat as measurement-plus-model; no dataset released.
- Assessment: method reference, not a public dataset.

### 3. MBARI Bluefin AUV battery log, 2003 (bluefinBattlog.nc, dods.mbari.org/opendap/data/auvctd/2003/2003206/2003.206.02/)
- Source of evidence: search snippet only. The .info, .dmr.html pages returned Anubis bot-block (HTTP-level access denied), so the landing page was NOT verified.
- Snippet reports nominal voltage, nominal current, and max cell voltage for three battery packs, logged over a mission. Vehicle: MBARI Bluefin AUV (large survey AUV, not BlueROV2-class).
- Assessment: plausibly measured electrical data, but speed/trajectory linkage, sampling, and license unverified. Needs manual check in a browser.

## Checked and rejected
- VT thesis on AUV energy monitoring (vtechworks, bitstream 82795550-...): PDF returned as compressed binary; content not readable. Unverified; no dataset evident.
- Rutgers data review (smart_battery_voltage, mV / mA fields): catalogue entry of a vehicle data stream, no mission dataset confirmed.
- ALFA Seabotix vLBV300 station-keeping and shared-autonomy datasets (OpenEI/data.gov): tethered ROV navigation/manipulation; no energy fields seen in snippets.
- Data.gov catalog record for the co-design project (catalog.data.gov/...2d566): returned 404 on fetch.
- IEEE DataPort WPT-AUV dataset: charging hardware, not consumption.
- AURORA AUV dataset (Sapienza, 2022): navigation/sonar/camera, no power fields.
- Patent on ROV energy management (USPTO 11837907): not a dataset; notes peak power up to 10x average, no data.
- Tethys LRAUV shore.log files (WHOI): diagnostics and fault logs; no state-of-charge or energy totals in excerpts.
- Zenodo: no AUV/ROV battery dataset surfaced; the two Zenodo hits were stationary lead-acid banks and EV data.

## Searches with no suitable hit
BlueROV2 battery/power logs; REMUS power logs; Iver energy data; hotel-load measurements; ArduSub dataflash battery datasets; generic "ROV energy Wh" queries. None returned a public measured-energy mission dataset for a BlueROV2-class vehicle.

## Bottom line
No public, verified measured-electrical-energy dataset for a BlueROV2-class mission found. Best lead: dataset 1 (OpenEI 646), contingent on inspecting its ROS bags for battery topics (e.g., voltage/current messages). Dataset 3 is the only measured AUV battery record surfaced, but unverified and from a non-BlueROV2 vehicle.
