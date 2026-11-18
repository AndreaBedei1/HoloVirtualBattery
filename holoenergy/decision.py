"""Evidence-aware assessment of a mission energy requirement (review I-02).

A requirement such as "the mission must use at most E_max Wh" is assessed on three levels:

* the nominal estimate (the point values the run used);
* the interval the published evidence supports: ranges and bounds propagated by
  :func:`holoenergy.uncertainty.energy_intervals`, a published maximum counted as the upper side,
  and every contribution without a lower bound taken at zero (a power cannot be negative);
* the contributions the evidence leaves open: unconfigured loads, unmodelled conversion,
  components without a record. Any of these makes the upper side unknown.

Verdicts are physical, not scores:

* ``SUPPORTED_PASS`` - the supported upper bound exists and is within the requirement;
* ``SUPPORTED_FAIL`` - the supported lower bound already exceeds it;
* ``INDETERMINATE`` - the evidence admits both outcomes (a decision cannot be certified).

Propulsion follows the simulator's dynamics and has no published uncertainty: it enters at its
nominal value unless ``propulsion_factor_range`` gives a defensible range (for example from
alternative published hydrodynamics), and the assessment states which treatment was used.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from ._validation import ConfigurationError, number

VERDICTS = ("SUPPORTED_PASS", "SUPPORTED_FAIL", "INDETERMINATE")


@dataclass(frozen=True)
class EnergyRequirementAssessment:
    requirement_Wh: float
    nominal_Wh: float
    supported_low_Wh: float
    supported_high_Wh: float | None
    nominal_pass: bool
    verdict: str
    open_low: tuple
    open_high: tuple
    unknown_contributions: tuple
    upper_bound_contribution_Wh: float
    dynamics: str
    assumptions: tuple = ()

    @property
    def evidence_supported_pass(self):
        return self.verdict == "SUPPORTED_PASS"

    @property
    def evidence_supported_fail(self):
        return self.verdict == "SUPPORTED_FAIL"

    @property
    def indeterminate(self):
        return self.verdict == "INDETERMINATE"

    def to_dict(self):
        result = asdict(self)
        for key in ("open_low", "open_high", "unknown_contributions", "assumptions"):
            result[key] = list(result[key])
        return result


def _get(report, key):
    return report[key] if isinstance(report, dict) else getattr(report, key)


def _state_energy(device_state_energy, item):
    device, _, state = item.rpartition(".")
    return float((device_state_energy.get(device) or {}).get(state, 0.0))


def assess_energy_requirement(
    report,
    max_energy_wh,
    *,
    propulsion_factor_range=None,
    dynamics_source=None,
    assume_verified=(),
):
    """Assess ``terminal energy <= max_energy_wh`` for an :class:`EnergyReport` (or its dict).

    ``propulsion_factor_range`` = (low, high) scales the propulsion energy to propagate
    physical-model evidence (``dynamics_source`` names it). ``assume_verified`` lists rails
    (``"payload"``, ``"hotel"``) whose conversion the caller treats as verified; this is an
    assumption and is recorded as such.
    """
    limit = number(max_energy_wh, "max_energy_wh", positive=True)
    intervals = _get(report, "intervals")
    if not intervals or "terminal_energy_Wh" not in intervals:
        raise ConfigurationError(
            "The report has no evidence intervals (EnergyReport intervals=True)"
        )
    terminal = intervals["terminal_energy_Wh"]
    device_state_energy = _get(report, "device_state_energy_Wh")
    evidence = _get(report, "evidence") or {}
    assumptions = []
    waived = {f"conversion:{rail}" for rail in assume_verified}
    if waived:
        assumptions.append(
            "conversion treated as verified for: " + ", ".join(sorted(assume_verified))
        )
    open_low = tuple(terminal.get("open_low", []))
    open_high = tuple(x for x in terminal.get("open_high", []) if x not in waived)
    unknown = tuple(x for x in terminal.get("unknown_contributions", []) if x not in waived)

    nominal = float(terminal["nominal"])
    low = float(terminal["low"])
    # A contribution with no published lower bound can be as small as zero.
    low -= sum(_state_energy(device_state_energy, item) for item in open_low)
    high = None if open_high else float(terminal["high"])

    propulsion = float((_get(report, "category_energy_Wh") or {}).get("propulsion", 0.0))
    if propulsion_factor_range is None:
        dynamics = "excluded: propulsion follows the simulator's dynamics"
    else:
        lo_f, hi_f = (
            number(v, "propulsion factor", positive=True) for v in propulsion_factor_range
        )
        if lo_f > hi_f:
            raise ConfigurationError("propulsion_factor_range must be (low, high)")
        low += (lo_f - 1.0) * propulsion
        if high is not None:
            high += (hi_f - 1.0) * propulsion
        dynamics = f"propulsion factor [{lo_f:g}, {hi_f:g}]" + (
            f" from {dynamics_source}" if dynamics_source else ""
        )
    low = max(low, 0.0)
    if low > limit:
        verdict = "SUPPORTED_FAIL"
    elif high is not None and high <= limit:
        verdict = "SUPPORTED_PASS"
    else:
        verdict = "INDETERMINATE"
    return EnergyRequirementAssessment(
        requirement_Wh=limit,
        nominal_Wh=nominal,
        supported_low_Wh=low,
        supported_high_Wh=high,
        nominal_pass=nominal <= limit,
        verdict=verdict,
        open_low=open_low,
        open_high=open_high,
        unknown_contributions=unknown,
        upper_bound_contribution_Wh=float(evidence.get("upper_bound_energy_Wh", 0.0)),
        dynamics=dynamics,
        assumptions=tuple(assumptions),
    )
