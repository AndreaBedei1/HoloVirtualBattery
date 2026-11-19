# Baseline UI audit (dashboard at abdf077)

Rendered with synthetic telemetry (`examples/realtime_energy_demo.py --backend synthetic`) and
inspected in a browser on 2026-11-19, before any change. Screenshots: `screenshots/baseline/`
(`live_*.jpg` from the browser pane, `live_home_<width>.png` full-page from `tools/ui_audit.py`).
Measurements: `screenshots/baseline/audit.json`.

## What exists

One page (`holoenergy/dashboard/index.html`, 21.8 kB, inline CSS/JS) that shows a single live run:
ten KPI tiles, an attribution table, a motion/effort panel, four history charts, actuator and
component tables, actuation, communications, evidence and a "Compare runs" list of saved reports.
There is no robot, mission, hardware or evidence workflow. The page cannot configure anything.

## Measured defects

| Check | 320 px | 390 px | 768 px | 1440 px |
| --- | --- | --- | --- | --- |
| Horizontal page overflow | 250 px | 180 px | 0 | 0 |
| Elements clipped beyond the viewport | 18 | 18 | 0 | 0 |
| Text below 12 px | ≥ 25 | ≥ 25 | ≥ 25 | ≥ 25 |
| Inputs without an accessible name | 1 (`select#window`) | 1 | 1 | 1 |

The overflow at phone widths comes from the scientific-warnings table (four columns with long effect
text). All KPI labels and card captions are 11 px.

## Observed defects (from the screenshots)

1. **Wrong scope.** The page is a run monitor only; the brief's Robot, Mission, Hardware and
   Evidence workflows do not exist.
2. **Endurance shown.** "Endurance estimates 22.7 / 20.6 min" is displayed although the claim matrix
   forbids any endurance figure. It is an instantaneous extrapolation but it reads as a prediction.
3. **Uniform tiles.** Ten tiles of the same size and weight; SOC, power and voltage have no priority
   over water temperature or episode number.
4. **Explanatory copy in the primary view.** Captions such as the endurance note and the
   attribution footnote sit under cards; at 390 px they push the content down by about a screen.
5. **Generic dark navy and teal theme**, borders on every container, uniform 8 px radii.
6. **Status mixed with warnings.** Battery-state chips (NORMAL, LOW SOC, …) appear as a row of
   identical pills; only colour marks the active one.
7. **Empty values.** In energy-only mode, linear speed, angular speed and depth show "— m/s" and
   take a full panel.
8. **Redundant actuator table.** Eight rows with Command and Applied columns that are equal unless
   derating is active.
9. **Header wraps to three lines at 320 px** ("HoloEnergy / Mission / monitor").
10. **Warnings table not responsive** (the overflow above); there is no card layout for phones.
11. **No progressive disclosure.** Evidence, allocation, communications and comparison are all open
    at once, so the page is about six screens tall at 1440 px.
12. **Charts have no text alternative** and use colour alone to tell series apart.

## Consequence for the redesign

The redesign replaces the single monitor with an application organised as Overview, Robot,
Mission, Run, Results, Compare, Hardware and Evidence. Every number is served by the Python API
(`holoenergy.dashboard.server`), so the browser holds no scientific model.
