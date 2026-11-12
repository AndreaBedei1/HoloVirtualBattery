"""Explicit unit handling for configurable physical and electrical parameters.

Internally HoloEnergy uses SI base or SI-derived units: W, J (reported as Wh),
V, A, N, m, s, m/s, ohm, Hz, bit/s.  Temperatures are carried in degrees Celsius
by the battery/thermal models; conversions to and from kelvin are explicit.

Ambiguous spellings are rejected on purpose: ``C`` could mean coulomb or degree
Celsius, so neither is accepted for temperature; ``dB re 1 uPa`` (acoustic source
level) and ``dBm`` (radio-frequency power) are *not* convertible to electrical
input power because their relation to supply power is hardware specific.
"""

from dataclasses import dataclass
from math import isfinite, log10

from ._validation import ConfigurationError

# kind -> unit -> factor to the SI unit of that kind (affine kinds handled separately)
_LINEAR = {
    "power": {"W": 1.0, "mW": 1e-3, "uW": 1e-6, "µW": 1e-6, "kW": 1e3},
    "energy": {"J": 1.0, "kJ": 1e3, "Wh": 3600.0, "mWh": 3.6, "kWh": 3.6e6},
    "voltage": {"V": 1.0, "mV": 1e-3, "kV": 1e3},
    "current": {"A": 1.0, "mA": 1e-3, "uA": 1e-6, "µA": 1e-6},
    "charge": {"Ah": 3600.0, "mAh": 3.6, "As": 1.0, "coulomb": 1.0},
    "force": {"N": 1.0, "kN": 1e3, "kgf": 9.80665, "lbf": 4.4482216152605},
    "length": {"m": 1.0, "cm": 1e-2, "mm": 1e-3, "km": 1e3},
    "area": {"m2": 1.0, "cm2": 1e-4},
    "volume": {"m3": 1.0, "L": 1e-3},
    "mass": {"kg": 1.0, "g": 1e-3},
    "time": {"s": 1.0, "ms": 1e-3, "us": 1e-6, "min": 60.0, "h": 3600.0, "day": 86400.0},
    "speed": {"m/s": 1.0, "km/h": 1 / 3.6, "kn": 1852 / 3600},
    "angular_speed": {"rad/s": 1.0, "rpm": 2 * 3.141592653589793 / 60},
    "resistance": {"ohm": 1.0, "Ω": 1.0, "mohm": 1e-3, "mΩ": 1e-3},
    "frequency": {"Hz": 1.0, "kHz": 1e3, "MHz": 1e6},
    "bitrate": {"bit/s": 1.0, "bps": 1.0, "kbit/s": 1e3, "kbps": 1e3, "Mbit/s": 1e6},
    "data": {"bit": 1.0, "byte": 8.0, "B": 8.0, "kB": 8e3},
    "thermal_capacity": {"J/K": 1.0, "J/degC": 1.0},
    "thermal_conductance": {"W/K": 1.0, "W/degC": 1.0},
    "dimensionless": {"1": 1.0, "fraction": 1.0, "%": 0.01},
    "angle": {"rad": 1.0, "deg": 3.141592653589793 / 180},
    "pressure": {"Pa": 1.0, "kPa": 1e3, "MPa": 1e6, "bar": 1e5},
    "density": {"kg/m3": 1.0},
    # Rate constants (e.g. a linear damping coefficient per unit mass), not frequencies.
    "rate": {"1/s": 1.0},
}
_SI = {
    "power": "W",
    "energy": "J",
    "voltage": "V",
    "current": "A",
    "charge": "As",
    "force": "N",
    "length": "m",
    "area": "m2",
    "volume": "m3",
    "mass": "kg",
    "time": "s",
    "speed": "m/s",
    "angular_speed": "rad/s",
    "resistance": "ohm",
    "frequency": "Hz",
    "rate": "1/s",
    "bitrate": "bit/s",
    "data": "bit",
    "thermal_capacity": "J/K",
    "thermal_conductance": "W/K",
    "dimensionless": "1",
    "angle": "rad",
    "pressure": "Pa",
    "density": "kg/m3",
    "temperature": "K",
}
_TEMPERATURE = {"K": 0.0, "degC": 273.15, "°C": 273.15}
# Logarithmic or non-electrical levels: recorded, never silently converted to watts.
_LEVELS = {
    "dB re 1 uPa": "acoustic_source_level",
    "dB re 1 µPa": "acoustic_source_level",
    "dB re 1 uPa @ 1 m": "acoustic_source_level",
    "dBm": "rf_power_level",
    "dB": "ratio_level",
}


def unit_kind(unit):
    """Return the quantity kind of a unit string or raise for unknown spellings."""
    if not isinstance(unit, str) or not unit.strip():
        raise ConfigurationError("Unit must be a nonempty string")
    if unit in _TEMPERATURE:
        return "temperature"
    if unit in _LEVELS:
        return _LEVELS[unit]
    for kind, table in _LINEAR.items():
        if unit in table:
            return kind
    if unit == "C":
        raise ConfigurationError("Ambiguous unit 'C': use 'degC' for temperature or 'As'/'coulomb'")
    raise ConfigurationError(f"Unknown unit {unit!r}")


def to_si(value, unit, kind=None):
    """Convert ``value`` in ``unit`` to the SI unit of its kind (temperature -> K)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ConfigurationError("Quantity value must be a finite number")
    found = unit_kind(unit)
    if kind is not None and found != kind:
        raise ConfigurationError(f"Unit {unit!r} is {found}, expected {kind}")
    if found == "temperature":
        return float(value) + _TEMPERATURE[unit]
    if found in _LEVELS.values():
        raise ConfigurationError(
            f"{unit!r} is a {found}; it has no hardware-independent electrical-power equivalent"
        )
    return float(value) * _LINEAR[found][unit]


def convert(value, from_unit, to_unit):
    kind = unit_kind(from_unit)
    if unit_kind(to_unit) != kind:
        raise ConfigurationError(f"Cannot convert {from_unit} to {to_unit}")
    si = to_si(value, from_unit)
    if kind == "temperature":
        return si - _TEMPERATURE[to_unit]
    return si / _LINEAR[kind][to_unit]


def celsius_to_kelvin(value_C):
    return to_si(value_C, "degC")


def kelvin_to_celsius(value_K):
    return convert(value_K, "K", "degC")


def dbm_to_watt(value_dBm):
    """Radiated/RF power level to watts of RF power (not electrical supply power)."""
    if isinstance(value_dBm, bool) or not isinstance(value_dBm, (int, float)):
        raise ConfigurationError("dBm value must be a number")
    return 10 ** ((float(value_dBm) - 30) / 10)


def watt_to_dbm(value_W):
    if value_W <= 0:
        raise ConfigurationError("RF power must be > 0 W to express in dBm")
    return 10 * log10(value_W) + 30


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str

    def __post_init__(self):
        unit_kind(self.unit)
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ConfigurationError("Quantity value must be a number")

    @property
    def kind(self):
        return unit_kind(self.unit)

    @property
    def si(self):
        return to_si(self.value, self.unit)

    def to(self, unit):
        return Quantity(convert(self.value, self.unit, unit), unit)

    @classmethod
    def parse(cls, text):
        """Parse ``"15 W"``-style strings; the unit is everything after the number."""
        if not isinstance(text, str):
            raise ConfigurationError("Quantity text must be a string such as '15 W'")
        head, _, tail = text.strip().partition(" ")
        try:
            number = float(head)
        except ValueError as exc:
            raise ConfigurationError(f"Cannot parse quantity {text!r}") from exc
        return cls(number, tail.strip())


def si_unit(kind):
    return _SI[kind]
