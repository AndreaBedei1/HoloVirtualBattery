"""Explicit command, electrical and mission outcomes; never infer a vehicle goal."""

from math import sqrt

from .._validation import ConfigurationError, number


def errors(predicted, measured):
    if not predicted or len(predicted) != len(measured):
        raise ConfigurationError("Error metrics require equal nonempty paired samples")
    differences = [
        number(a, "prediction") - number(b, "measurement")
        for a, b in zip(predicted, measured, strict=True)
    ]
    return {
        "mae": sum(abs(x) for x in differences) / len(differences),
        "rmse": sqrt(sum(x * x for x in differences) / len(differences)),
        "max_abs_error": max(abs(x) for x in differences),
        "n": len(differences),
    }


def first_event(rows, predicate):
    return next((r["time_s"] for r in rows if predicate(r)), None)


def summarize(
    rows,
    *,
    command_sequence_completed=True,
    mission_completed=None,
    completion_time_s=None,
    reserve_soc=None,
):
    if not rows:
        raise ConfigurationError("Cannot summarize an empty run")
    if mission_completed not in (None, True, False):
        raise ConfigurationError("mission_completed must be boolean or null")
    if completion_time_s is not None:
        number(completion_time_s, "completion_time_s", minimum=0)
    if reserve_soc is not None:
        reserve_soc = number(reserve_soc, "reserve_soc", minimum=0, maximum=1)

    def integrate(key):
        return sum(r[key] * r["dt_s"] / 3600 for r in rows)

    def derated(row):
        return (any(row["requested_action"]) and row["derating_factor"] < 1 - 1e-9) or (
            row["auxiliary_service_factor"] < 1 - 1e-9
        )

    flags = [derated(row) for row in rows]
    events = sum(on and (i == 0 or not flags[i - 1]) for i, on in enumerate(flags))
    cutoff_time = first_event(rows, lambda r: r["battery_state"] == "CUTOFF")
    violations = [] if reserve_soc is None else [r for r in rows if r["soc"] < reserve_soc]
    return {
        "terminal_energy_Wh": integrate("power_total_W"),
        "final_soc": rows[-1]["soc"],
        "minimum_voltage_V": min(r.get("minimum_voltage_V", r["voltage_V"]) for r in rows),
        "peak_current_A": max(r.get("peak_current_A", r["current_A"]) for r in rows),
        "peak_temperature_C": max(r.get("peak_temperature_C", r["temperature_C"]) for r in rows),
        "propulsion_energy_Wh": integrate("power_propulsion_W"),
        "payload_energy_Wh": integrate("power_payload_W"),
        "hotel_energy_Wh": integrate("power_hotel_W"),
        "conversion_loss_Wh": integrate("power_conversion_loss_W"),
        "battery_internal_loss_Wh": integrate("power_battery_loss_W"),
        "unmet_energy_Wh": integrate("unmet_power_W"),
        "peak_unmet_power_W": max(r["unmet_power_W"] for r in rows),
        "unmet_power_is_capped": any(r.get("requested_power_is_capped", False) for r in rows),
        "derating_events": events,
        "derating_duration_s": sum(r["dt_s"] for r, on in zip(rows, flags, strict=True) if on),
        "first_derating_time_s": next(
            (r["time_s"] for r, on in zip(rows, flags, strict=True) if on), None
        ),
        "time_to_cutoff_s": cutoff_time,
        "cutoff_events": int(cutoff_time is not None),
        "command_sequence_completed": command_sequence_completed,
        "mission_completed": mission_completed,
        "mission_completion_time_s": completion_time_s,
        "simulated_duration_s": sum(r["dt_s"] for r in rows),
        "power_feasible": cutoff_time is None and integrate("unmet_power_W") < 1e-9,
        "dynamics_energy_consistent": all(r["dynamics_energy_consistent"] for r in rows),
        "reserve_soc": reserve_soc,
        "reserve_violation_samples": None if reserve_soc is None else len(violations),
        "reserve_violation_duration_s": None
        if reserve_soc is None
        else sum(r["dt_s"] for r in violations),
    }
