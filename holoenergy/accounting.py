"""Tick-integrated energy attribution and explicit mission labels."""

import copy
import csv
from collections import deque
from pathlib import Path

from ._validation import ConfigurationError, number
from .provenance import write_json


class EnergyRuntime:
    """Public env.energy facade, separated from the numerical load models."""

    def __init__(self, owner):
        self.owner = owner
        self.episodes = []
        self.reset()

    def reset(self):
        self.phase = "unmarked"
        self.categories = {
            k: 0.0
            for k in (
                "propulsion",
                "sensors",
                "compute",
                "auxiliaries",
                "converters",
                "battery_losses",
            )
        }
        self.devices = {}
        self.phases = {}
        self.duration_s = 0.0
        self.history = deque()
        self.latest = None

    def set_component_state(self, name, state):
        self.owner.payload.set_state(name, state)

    def set_component_input(self, name, input_name=None, value=None, **inputs):
        self.owner.payload.set_input(name, input_name, value, **inputs)

    def set_environment(self, **values):
        self.owner.set_environment(**values)

    def mark_phase(self, name):
        if not isinstance(name, str) or not name.strip():
            raise ConfigurationError("Mission phase must be a nonempty string")
        self.phase = name

    def record(self, row):
        dt = row["dt_s"]
        powers = {
            "propulsion": row["power_propulsion_W"],
            "sensors": row["power_sensors_W"],
            "compute": row["power_compute_W"],
            "auxiliaries": row["power_auxiliary_W"],
            "converters": row["power_conversion_loss_W"],
            "battery_losses": row["power_battery_loss_W"],
        }
        for name, power in powers.items():
            self.categories[name] += power * dt / 3600
        device_powers = {**row["actuator_power_W"], **row["component_power_W"]}
        for name, power in device_powers.items():
            self.devices[name] = self.devices.get(name, 0) + power * dt / 3600
        phase = self.phases.setdefault(
            self.phase, {"duration_s": 0.0, "terminal_energy_Wh": 0.0, "battery_losses_Wh": 0.0}
        )
        phase["duration_s"] += dt
        phase["terminal_energy_Wh"] += row["power_total_W"] * dt / 3600
        phase["battery_losses_Wh"] += row["power_battery_loss_W"] * dt / 3600
        self.duration_s += dt
        self.history.append((row["time_s"], dt, row["power_total_W"]))
        # Retain a bounded time window for optional rolling endurance, independent of UI.
        while self.history and self.history[0][0] <= row["time_s"] - 60:
            self.history.popleft()
        row.update(
            mission_phase=self.phase,
            category_energy_Wh=dict(self.categories),
            component_energy_Wh={n: self.devices[n] for n in row["component_power_W"]},
            actuator_energy_Wh={n: self.devices[n] for n in row["actuator_power_W"]},
            phase_energy_Wh=copy.deepcopy(self.phases),
        )
        self.latest = row

    def endurance(self, window_s=60):
        window = number(window_s, "rolling endurance window_s", positive=True, maximum=60)
        if self.latest is None:
            return {"instantaneous_s": None, "rolling_average_s": None}
        remaining = self.latest["remaining_energy_Wh"] * 3600
        power = self.latest["power_total_W"]
        elapsed = self.latest["time_s"]
        samples = [
            (min(dt, max(0, t - (elapsed - window))), p)
            for t, dt, p in self.history
            if t > elapsed - window
        ]
        duration = sum(dt for dt, _ in samples)
        average = sum(dt * p for dt, p in samples) / duration if duration else 0
        return {
            "instantaneous_s": remaining / power if power > 0 else None,
            "rolling_average_s": remaining / average if average > 0 else None,
            "rolling_window_s": window,
            "observed_window_s": duration,
            "basis": "remaining OCV work upper bound / terminal power"
            if self.owner.config["fidelity_level"] == "L1"
            else "remaining ideal energy / terminal power",
            "interpretation": "instantaneous / rolling-average estimate; not a mission prediction",
        }

    def summary(self):
        terminal = sum(v for k, v in self.categories.items() if k != "battery_losses")
        total = terminal + self.categories["battery_losses"]
        return {
            "run_id": self.owner.logger.run_id,
            "episode": self.owner.episode,
            "duration_s": self.duration_s,
            "terminal_energy_Wh": terminal,
            "total_ocv_work_Wh": total,
            "category_energy_Wh": dict(self.categories),
            "category_percent_of_ocv_work": {
                k: 100 * v / total if total else 0 for k, v in self.categories.items()
            },
            "device_energy_Wh": dict(self.devices),
            "phases": copy.deepcopy(self.phases),
            "endurance_estimates": self.endurance(),
            "evidence_kind": "configured simulation; physical validation not implied",
        }

    def export_summary(self, path):
        path = Path(path)
        if path.suffix.lower() == ".csv":
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["group", "name", "energy_Wh"])
                for name, value in self.categories.items():
                    writer.writerow(["category", name, value])
                for name, value in self.devices.items():
                    writer.writerow(["device", name, value])
                for name, value in self.phases.items():
                    writer.writerow(["phase_terminal", name, value["terminal_energy_Wh"]])
        else:
            write_json(path, {**self.summary(), "previous_episodes": self.episodes})
        return path
