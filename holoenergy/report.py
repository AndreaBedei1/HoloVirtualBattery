"""Provenance-aware mission energy reports and structured run comparison."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .provenance import write_json


def _sig(value, digits=3):
    """Format with limited significant digits (avoid false precision in text reports)."""
    if value is None:
        return "n/a"
    if value == 0:
        return "0"
    return f"{value:.{digits}g}"


@dataclass
class EnergyReport:
    run_id: str | None
    profile: dict
    duration_s: float
    terminal_energy_Wh: float
    total_ocv_work_Wh: float
    soc_initial: float | None
    soc_final: float | None
    peak_current_A: float | None
    minimum_voltage_V: float | None
    category_energy_Wh: dict
    device_energy_Wh: dict
    device_state_energy_Wh: dict
    phases: dict
    evidence: dict | None
    intervals: dict | None
    incomplete: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    @property
    def soc_loss(self):
        if self.soc_initial is None or self.soc_final is None:
            return None
        return self.soc_initial - self.soc_final

    @classmethod
    def from_runtime(cls, runtime, *, intervals=True):
        owner = runtime.owner
        summary = runtime.summary()
        evidence = summary.get("evidence")
        interval_data = None
        if intervals and getattr(owner, "evidence_map", None) is not None:
            from .uncertainty import energy_intervals

            interval_data = energy_intervals(summary, owner.evidence_map)
        metadata = owner.config.get("metadata", {})
        logger = getattr(owner, "logger", None)
        provenance = {}
        if logger is not None:
            meta = logger.metadata
            provenance = {
                k: meta.get(k)
                for k in (
                    "holoenergy_version",
                    "git",
                    "holoocean_version",
                    "resolved_config_sha256",
                    "random_seed",
                    "scenario",
                    "python_version",
                    "platform",
                )
                if k in meta
            }
        from .evidence import default_registry

        provenance["evidence_registry_version"] = default_registry().version
        provenance["actuation"] = owner.actuation.describe()
        provenance["fidelity_level"] = owner.config.get("fidelity_level")
        provenance["dt_s"] = owner.dt_s
        return cls(
            run_id=summary["run_id"],
            profile={
                "profile_id": metadata.get("profile_id"),
                "profile_version": metadata.get("profile_version"),
                "vehicle": owner.vehicle.name,
            },
            duration_s=summary["duration_s"],
            terminal_energy_Wh=summary["terminal_energy_Wh"],
            total_ocv_work_Wh=summary["total_ocv_work_Wh"],
            soc_initial=getattr(owner.battery, "initial_soc", None),
            soc_final=getattr(owner.battery, "soc", None),
            peak_current_A=runtime.peak_current_A,
            minimum_voltage_V=runtime.minimum_voltage_V,
            category_energy_Wh=summary["category_energy_Wh"],
            device_energy_Wh=summary["device_energy_Wh"],
            device_state_energy_Wh=summary["device_state_energy_Wh"],
            phases=summary["phases"],
            evidence=evidence,
            intervals=interval_data,
            incomplete=list((evidence or {}).get("unconfigured_components", [])),
            warnings=list(owner.warnings),
            provenance=provenance,
            notes=[
                "Simulation output; physical validation is not implied.",
                "Terminal energy = propulsion + sensors + compute + communications + "
                "auxiliaries + converter losses; total OCV work adds battery losses.",
            ],
        )

    def to_dict(self):
        result = asdict(self)
        result["soc_loss"] = self.soc_loss
        return result

    def write_json(self, path):
        write_json(path, self.to_dict())
        return Path(path)

    @classmethod
    def load(cls, path_or_dict):
        data = path_or_dict
        if not isinstance(data, dict):
            data = json.loads(Path(path_or_dict).read_text(encoding="utf-8"))
        data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**data)

    def text(self):
        lines = [
            f"Profile:                  {self.profile.get('profile_id') or self.profile.get('vehicle')}",
            f"Mission duration:         {_sig(self.duration_s, 4)} s",
            f"Energy consumed:          {_sig(self.terminal_energy_Wh)} Wh (terminal)",
            f"Total OCV work:           {_sig(self.total_ocv_work_Wh)} Wh (incl. battery losses)",
        ]
        if self.soc_loss is not None:
            lines.append(f"SOC loss:                 {_sig(100 * self.soc_loss)} %")
        lines.append(f"Peak pack current:        {_sig(self.peak_current_A)} A")
        lines.append("Energy breakdown:")
        for name, wh in self.category_energy_Wh.items():
            lines.append(f"  {name:<22}{_sig(wh)} Wh")
        if self.evidence:
            lines.append("Evidence (share of predicted energy by parameter grade):")
            for grade, share in self.evidence["share_percent"].items():
                lines.append(f"  Grade {grade}:                {_sig(share, 2)} %")
            lines.append(
                f"  from upper-bound values:  {_sig(self.evidence['upper_bound_share_percent'], 2)} %"
            )
        if self.intervals:
            t = self.intervals["terminal_energy_Wh"]
            low = "open" if t["open_low"] else _sig(t["low"])
            high = "open" if t["open_high"] else _sig(t["high"])
            lines.append(f"Estimated interval (terminal energy): [{low}, {high}] Wh")
            if t["open_low"] or t["open_high"]:
                lines.append(
                    "  open sides from: "
                    + ", ".join(sorted(set(t["open_low"]) | set(t["open_high"])))
                )
        if self.incomplete:
            lines.append(
                "INCOMPLETE configuration (excluded loads): "
                + ", ".join(u["component"] for u in self.incomplete)
            )
        lines.extend(self.notes)
        return "\n".join(lines)

    def __str__(self):
        return self.text()


_METRICS = ("duration_s", "terminal_energy_Wh", "total_ocv_work_Wh", "peak_current_A")


def compare_runs(*runs, labels=None):
    """Structured comparison of EnergyReports (objects, dicts or JSON paths).

    Returns absolute values, differences and ratios relative to the first run for the
    headline metrics, energy categories and evidence shares, plus the caveats that
    make two runs non-comparable (different durations, incomplete loads).
    """
    reports = [r if isinstance(r, EnergyReport) else EnergyReport.load(r) for r in runs]
    if len(reports) < 2:
        raise ValueError("compare_runs needs at least two runs")
    labels = labels or [
        r.profile.get("profile_id") or r.run_id or f"run{i}" for i, r in enumerate(reports)
    ]
    base = reports[0]

    def delta(a, b):
        if a is None or b is None:
            return {"value": b, "difference": None, "ratio": None}
        return {"value": b, "difference": b - a, "ratio": (b / a) if a else None}

    rows = []
    for label, report in zip(labels, reports, strict=True):
        entry = {"label": label}
        for metric in _METRICS:
            entry[metric] = delta(getattr(base, metric), getattr(report, metric))
        entry["soc_loss"] = delta(base.soc_loss, report.soc_loss)
        entry["category_energy_Wh"] = {
            k: delta(base.category_energy_Wh.get(k, 0.0), report.category_energy_Wh.get(k, 0.0))
            for k in sorted(set(base.category_energy_Wh) | set(report.category_energy_Wh))
        }
        entry["evidence_share_percent"] = copy.deepcopy(
            (report.evidence or {}).get("share_percent")
        )
        entry["incomplete"] = [u["component"] for u in report.incomplete]
        rows.append(entry)
    caveats = []
    durations = {round(r.duration_s, 6) for r in reports}
    if len(durations) > 1:
        caveats.append("runs have different durations: compare energy per time or per distance")
    if any(r.incomplete for r in reports):
        caveats.append("some runs exclude unconfigured loads; their energies are lower bounds")
    return {"baseline": labels[0], "runs": rows, "caveats": caveats}
