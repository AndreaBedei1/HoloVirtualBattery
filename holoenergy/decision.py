"""Evidence-aware assessment of a mission energy requirement (review I-02).

A requirement such as "the mission must use at most E_max Wh" is assessed on three levels:

* the nominal estimate (the point values the run used);
* the interval the published evidence supports: ranges and bounds propagated by
  :func:`holoenergy.uncertainty.energy_intervals` on the bus side (each load divided by the
  efficiency of its rail), a published maximum counted as the upper side, and every
  contribution without a lower bound taken at zero (a power cannot be negative);
* the contributions the evidence leaves open: unconfigured loads, unmodelled or unverified
  conversion, components without a record. Any of these makes the upper side unknown.

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
RAILS = ("propulsion", "payload", "hotel")


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


def _intervals(report):
    intervals = _get(report, "intervals")
    if not intervals or "terminal_energy_Wh" not in intervals:
        raise ConfigurationError(
            "The report has no evidence intervals (EnergyReport intervals=True)"
        )
    return intervals


def _bus_energy(intervals):
    """'device.state' -> bus-side energy (device energy / rail efficiency)."""
    out = {}
    for key in ("contributions", "point_contributions", "open_contributions"):
        for row in intervals.get(key, []):
            out[f"{row['device']}.{row['state']}"] = row["energy_Wh"] * row.get("scale", 1.0)
    return out


def assess_energy_requirement(
    report,
    max_energy_wh,
    *,
    propulsion_factor_range=None,
    dynamics_source=None,
    assume_verified=(),
):
    """Assess ``terminal energy <= max_energy_wh`` for an :class:`EnergyReport` (or its dict).

    ``propulsion_factor_range`` = (low, high) scales the propulsion energy (bus side) to
    propagate physical-model evidence (``dynamics_source`` names it). ``assume_verified`` lists
    rails (``"payload"``, ``"hotel"``) whose conversion the caller treats as verified; this is
    an assumption and is recorded as such.
    """
    limit = number(max_energy_wh, "max_energy_wh", positive=True)
    intervals = _intervals(report)
    terminal = intervals["terminal_energy_Wh"]
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
    bus = _bus_energy(intervals)
    nominal = float(terminal["nominal"])
    # A contribution with no published lower bound can be as small as zero, together with the
    # conversion loss it causes (adversarial H1).
    low = float(terminal["low"]) - sum(bus.get(item, 0.0) for item in open_low)
    high = None if open_high else float(terminal["high"])
    propulsion = sum(
        r["energy_Wh"] * r.get("scale", 1.0) for r in intervals.get("point_contributions", [])
    )
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
    """key -> (energy, record, low_dev, high_dev, scale, rail); None marks an open side.

    Device-side bounds; ``scale`` converts to the bus side. Unknown contributions (unconfigured
    loads, unmodelled supply conversion) have unknown energy and never cancel (adversarial C3).
    """
    intervals = _intervals(report)
    out = {}
    for row in intervals.get("contributions", []):
        energy, ratio = row["energy_Wh"], row["ratio"]
        low = 0.0 if ratio is None or ratio[0] is None else energy * ratio[0]
        high = None if ratio is None or ratio[1] is None else energy * ratio[1]
        out[(row["device"], row["state"])] = (
            energy,
            row["record"],
            low,
            high,
            row.get("scale", 1.0),
            row.get("rail", "payload"),
        )
    for row in intervals.get("point_contributions", []):
        e = row["energy_Wh"]
        out[(row["device"], row["state"])] = (
            e,
            "point",
            e,
            e,
            row.get("scale", 1.0),
            row.get("rail", "propulsion"),
        )
    for row in intervals.get("open_contributions", []):
        out[(row["device"], row["state"])] = (
            row["energy_Wh"],
            None,
            0.0,
            None,
            row.get("scale", 1.0),
            row.get("rail", "payload"),
        )
    for item in intervals["terminal_energy_Wh"].get("unknown_contributions", []):
        if not item.startswith("conversion:"):
            out[(item, "unknown")] = (None, "unknown", 0.0, None, 1.0, "payload")
    return out


def _close(p, q, tolerance):
    if p is None or q is None:
        return p is q
    return abs(p - q) <= tolerance * max(abs(p), abs(q), 1.0)


def _same(xa, xb, tolerance):
    """Identical in both runs: same record, rail, energy, bounds and conversion scale."""
    if xa is None or xb is None or "unknown" in (xa[1], xb[1]):
        return False
    return (
        xa[1] == xb[1]
        and xa[5] == xb[5]
        and all(_close(xa[i], xb[i], tolerance) for i in (0, 2, 3, 4))
    )


def _rail_sums(contribs, keys):
    """Per rail: [bus-side low, bus-side high or None] over the differing contributions."""
    sums = {r: [0.0, 0.0] for r in RAILS}
    for key in keys:
        x = contribs.get(key)
        if x is None:
            continue
        rail = x[5] if x[5] in sums else "payload"
        sums[rail][0] += x[2] * x[4]
        sums[rail][1] = (
            None if sums[rail][1] is None or x[3] is None else sums[rail][1] + x[3] * x[4]
        )
    return sums


def _lower_supported(x_sums, y_sums, x_unverified, y_unverified):
    """Is X < Y for every admissible conversion scale? Returns (supported, delta_high at s=1).

    On a rail whose efficiency has no evidence the bus-side scale is unknown, s >= 1. If both
    configurations share that unverified rail, s is common: X - Y on that rail is s times the
    unit-scale difference, which must not be positive (adversarial C2). If only X's rail is
    unverified, X's contribution on it must be zero. If only Y's is, s = 1 is Y's worst case.
    """
    delta = 0.0
    for rail in RAILS:
        x_hi, y_lo = x_sums[rail][1], y_sums[rail][0]
        if x_hi is None:
            return False, None
        term = x_hi - y_lo
        if rail in x_unverified and rail in y_unverified and term > 1e-15:
            return False, None
        if rail in x_unverified and rail not in y_unverified and x_hi > 1e-15:
            return False, None
        delta += term
    return delta < 0.0, delta


def compare_energy(report_a, report_b, *, tolerance=1e-9):
    """Is the terminal energy of configuration A lower than that of B, given the evidence?

    Paired comparison on the same mission, on the bus side. A contribution identical in both
    runs (same device, state, record, energy, bounds and conversion scale) cancels. Every other
    contribution enters with its supported interval (no lower bound -> zero, no upper bound ->
    open). Rails without converter evidence are handled by :func:`_lower_supported`.
    """
    ca, cb = _contributions(report_a), _contributions(report_b)
    ia, ib = _intervals(report_a), _intervals(report_b)
    unverified_a = {r for r, ok in ia.get("rail_verified", {}).items() if not ok}
    unverified_b = {r for r, ok in ib.get("rail_verified", {}).items() if not ok}
    differing = tuple(
        key
        for key in sorted(set(ca) | set(cb), key=str)
        if not _same(ca.get(key), cb.get(key), tolerance)
    )
    sa, sb = _rail_sums(ca, differing), _rail_sums(cb, differing)
    a_lower, d_high = _lower_supported(sa, sb, unverified_a, unverified_b)
    b_lower, d_neg = _lower_supported(sb, sa, unverified_b, unverified_a)
    assumptions = []
    shared = sorted(unverified_a & unverified_b)
    if shared:
        assumptions.append(
            "rails without converter evidence in both runs (" + ", ".join(shared) + "): the same "
            "converter, with a load-independent efficiency, is assumed in both"
        )
    return EnergyComparison(
        nominal_a_Wh=float(ia["terminal_energy_Wh"]["nominal"]),
        nominal_b_Wh=float(ib["terminal_energy_Wh"]["nominal"]),
        difference_low_Wh=None if d_neg is None else -d_neg,
        difference_high_Wh=d_high,
        a_lower_supported=a_lower,
        b_lower_supported=b_lower,
        differing=differing,
        assumptions=tuple(assumptions),
    )
