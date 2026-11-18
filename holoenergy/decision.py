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


@dataclass(frozen=True)
class EnergyComparison:
    nominal_a_Wh: float
    nominal_b_Wh: float
    difference_low_Wh: float | None
    difference_high_Wh: float | None
    a_lower_supported: bool
    b_lower_supported: bool
    differing: tuple
    assumptions: tuple

    @property
    def verdict(self):
        if self.a_lower_supported:
            return "A_LOWER_SUPPORTED"
        if self.b_lower_supported:
            return "B_LOWER_SUPPORTED"
        return "RANKING_NOT_SUPPORTED"

    def to_dict(self):
        result = asdict(self)
        result["verdict"] = self.verdict
        result["differing"] = [list(x) for x in self.differing]
        result["assumptions"] = list(self.assumptions)
        return result


def _contributions(report):
    """(device, state) -> (energy_Wh, record, low_Wh, high_Wh); None marks an open side."""
    terminal = _get(report, "intervals")["terminal_energy_Wh"]
    intervals = _get(report, "intervals")
    out = {}
    for row in intervals.get("contributions", []):
        energy, ratio = row["energy_Wh"], row["ratio"]
        low = 0.0 if ratio is None or ratio[0] is None else energy * ratio[0]
        high = None if ratio is None or ratio[1] is None else energy * ratio[1]
        out[(row["device"], row["state"])] = (energy, row["record"], low, high)
    for row in intervals.get("point_contributions", []):
        energy = row["energy_Wh"]
        out[(row["device"], row["state"])] = (energy, "point", energy, energy)
    for row in intervals.get("open_contributions", []):
        out[(row["device"], row["state"])] = (row["energy_Wh"], None, 0.0, None)
    for item in terminal.get("unknown_contributions", []):
        if not item.startswith("conversion:"):
            out[(item, "unknown")] = (0.0, None, 0.0, None)
    return out


def compare_energy(report_a, report_b, *, tolerance=1e-9):
    """Is the terminal energy of configuration A lower than that of B, given the evidence?

    Paired comparison on the same mission: a contribution identical in both runs (same device
    and state, same record, same energy) cancels. A rail without converter evidence present in
    both runs is assumed to have the same, load-independent efficiency, which scales both
    sides and preserves the sign of the difference; this assumption is recorded. Every other
    contribution enters with its supported interval (no lower bound -> zero, no upper bound ->
    open). A is supported as lower only if A's supported upper sum is below B's lower sum.
    """
    ca, cb = _contributions(report_a), _contributions(report_b)
    ua = set(_get(report_a, "intervals")["terminal_energy_Wh"].get("unknown_contributions", []))
    ub = set(_get(report_b, "intervals")["terminal_energy_Wh"].get("unknown_contributions", []))
    assumptions = []
    for rail in sorted(x for x in ua | ub if x.startswith("conversion:")):
        if rail in ua and rail in ub:
            assumptions.append(f"{rail}: same load-independent efficiency in both configurations")
        else:
            owner = ca if rail in ua else cb
            owner[(rail, "unknown")] = (0.0, None, 0.0, None)
    sums = {"a": [0.0, 0.0], "b": [0.0, 0.0]}
    differing = []
    for key in sorted(set(ca) | set(cb), key=str):
        xa, xb = ca.get(key), cb.get(key)
        if xa and xb and xa[1] == xb[1] and abs(xa[0] - xb[0]) <= tolerance * max(abs(xa[0]), 1.0):
            continue
        differing.append(key)
        for side, x in (("a", xa), ("b", xb)):
            if x is None:
                continue
            sums[side][0] += x[2]
            sums[side][1] = None if sums[side][1] is None or x[3] is None else sums[side][1] + x[3]
    a_low, a_high = sums["a"]
    b_low, b_high = sums["b"]
    return EnergyComparison(
        nominal_a_Wh=float(_get(report_a, "intervals")["terminal_energy_Wh"]["nominal"]),
        nominal_b_Wh=float(_get(report_b, "intervals")["terminal_energy_Wh"]["nominal"]),
        difference_low_Wh=None if b_high is None else a_low - b_high,
        difference_high_Wh=None if a_high is None else a_high - b_low,
        a_lower_supported=a_high is not None and a_high < b_low,
        b_lower_supported=b_high is not None and b_high < a_low,
        differing=tuple(differing),
        assumptions=tuple(assumptions),
    )
