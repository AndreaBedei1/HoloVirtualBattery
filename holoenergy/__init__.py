"""Energy accounting for marine robot simulation, without hardware interfaces."""

__version__ = "0.1.0"

# Imported after the version because logging uses it for run metadata.
from .env_wrapper import EnergyAwareEnv

__all__ = ["EnergyAwareEnv", "__version__"]
