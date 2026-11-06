"""Propagate published parameter ranges to mission energy (deterministic interval analysis).

State loads draw constant power while in a state, so their energy scales exactly with
the power value: ``E_state = P_state * t_state``.  A published range [P_min, P_max] for
the power that produced ``E_state`` therefore gives the exact energy interval for the
recorded state durations.  An upper-bound-only value leaves the lower side *open*
(reported as such, not filled with an invented minimum).  Battery resistive losses are
scaled with the resistance range at fixed current, a first-order approximation that
ignores the small feedback of resistance on current.  Dynamics are not re-simulated:
these intervals are valid for the recorded actuator efforts and state timelines.
"""

from __future__ import annotations

from .evidence import default_registry


def _ratio_interval(record, used_value):
    """(low_ratio, high_ratio) relative to the value used; None = open side."""
    if used_value is None or used_value == 0:
        return None
    lo = record.si("value_min")
    hi = record.si("value_max")
    if record.bound == "upper_bound":
        hi = hi if hi is not None else record.si("value")
    if record.bound == "lower_bound":
        lo = lo if lo is not None else record.si("value")
    if lo is None and hi is None:
        return (1.0, 1.0) if record.bound in ("exact", "measured_mean") else None
    return (None if lo is None else lo / used_value, None if hi is None else hi / used_value)


def energy_intervals(summary, evidence_map, registry=None, used_values=None):
    """Interval of terminal and total energy from evidence ranges.

    ``used_values`` maps (device, state) -> value (SI) actually used by the model; by
    default it is read from the component evidence records (``use: value``).
    """
    registry = registry or default_registry()
    device_states = summary["device_state_energy_Wh"]
    nominal_terminal = summary["terminal_energy_Wh"]
    nominal_total = summary["total_ocv_work_Wh"]
    low_delta = high_delta = 0.0
    open_low, open_high, rows = [], [], []
    for device, states in device_states.items():
        for state, wh in states.items():
            if wh == 0:
                continue
            record_id = evidence_map.records.get(device, {}).get(state)
            if record_id is None:
                if device not in evidence_map.actuators:
                    open_low.append(f"{device}.{state}")
                    open_high.append(f"{device}.{state}")
                continue
            record = registry.get(record_id)
            used = (used_values or {}).get((device, state))
            if used is None:
                used = record.si("value")
                if used is None:
                    used = record.si("value_max")
            ratio = _ratio_interval(record, used)
            rows.append(
                {
                    "device": device,
                    "state": state,
                    "energy_Wh": wh,
                    "record": record_id,
                    "ratio": ratio,
                }
            )
            if ratio is None:
                open_low.append(f"{device}.{state}")
                open_high.append(f"{device}.{state}")
                continue
            lo, hi = ratio
            if lo is None:
                open_low.append(f"{device}.{state}")
            else:
                low_delta += wh * (lo - 1)
            if hi is None:
                open_high.append(f"{device}.{state}")
            else:
                high_delta += wh * (hi - 1)
    battery = {"record": evidence_map.battery_loss_record, "interval_Wh": None}
    loss = summary["category_energy_Wh"].get("battery_losses", 0.0)
    if evidence_map.battery_loss_record and loss:
        record = registry.get(evidence_map.battery_loss_record)
        ratio = _ratio_interval(record, record.si("value"))
        if ratio is not None:
            lo = None if ratio[0] is None else loss * ratio[0]
            hi = None if ratio[1] is None else loss * ratio[1]
            battery["interval_Wh"] = [lo, hi]
            battery["open_upper"] = record.bound == "lower_bound"
            battery["note"] = "first-order: resistive loss scaled with resistance at fixed current"
    return {
        "method": __doc__.strip().splitlines()[0],
        "terminal_energy_Wh": {
            "nominal": nominal_terminal,
            "low": nominal_terminal + low_delta,
            "high": nominal_terminal + high_delta,
            "open_low": sorted(set(open_low)),
            "open_high": sorted(set(open_high)),
        },
        "total_ocv_work_Wh_nominal": nominal_total,
        "battery_losses": battery,
        "contributions": rows,
        "excluded": (
            "propulsion (manufacturer curve without published measurement uncertainty) and "
            "dynamics (simulator-owned); unconfigured loads are absent, not bounded"
        ),
    }
