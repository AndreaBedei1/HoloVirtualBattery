"""Small validation/interpolation helpers shared by physical models."""

from bisect import bisect_right
from collections.abc import Mapping
from math import isfinite


class ConfigurationError(ValueError):
    """A configuration is invalid or lacks a required measured/user parameter."""


def number(value, name, *, minimum=None, maximum=None, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{name} must be a finite number")
    result = float(value)
    if not isfinite(result):
        raise ConfigurationError(f"{name} must be a finite number")
    if positive and result <= 0:
        raise ConfigurationError(f"{name} must be > 0")
    if minimum is not None and result < minimum:
        raise ConfigurationError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise ConfigurationError(f"{name} must be <= {maximum}")
    return result


def required(data, key):
    if key not in data or data[key] is None:
        raise ConfigurationError(f"Missing {key}: supply a measured or explicit user value")
    return data[key]


def keys(data, allowed, context):
    if not isinstance(data, Mapping):
        raise ConfigurationError(f"{context} must be a mapping")
    extra = set(data) - set(allowed) - {"metadata"}
    if extra:
        raise ConfigurationError(f"Unknown {context} fields: {sorted(extra)}")


def curve(data, name, *, y_min=None, y_max=None, positive=False):
    if not isinstance(data, (list, tuple)) or not data:
        raise ConfigurationError(f"{name} must contain [x, y] points")
    points = []
    for row in data:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ConfigurationError(f"{name} must contain [x, y] points")
        x = number(row[0], name)
        y = number(row[1], name, minimum=y_min, maximum=y_max, positive=positive)
        if points and x <= points[-1][0]:
            raise ConfigurationError(f"{name} x coordinates must be strictly increasing")
        points.append((x, y))
    return tuple(points)


def interpolate(points, x):
    """Piecewise linear interpolation; clamp at measured endpoints."""
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    j = bisect_right(points, x, key=lambda p: p[0])
    x0, y0 = points[j - 1]
    x1, y1 = points[j]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def timestep(value):
    return number(value, "dt_s", positive=True)
