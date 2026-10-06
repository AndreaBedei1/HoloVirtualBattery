"""Energy accounting for marine robot simulation, without hardware interfaces."""

__version__ = "0.1.0"

# Imported after the version because logging uses it for run metadata.
from .env_wrapper import EnergyAwareEnv
from .models.actuator import ActuatorEnergyModel, DirectEffortActuatorModel, register_actuator_model
from .models.components import ElectricalComponent
from .models.vehicle import VehicleProfile

__all__ = [
    "EnergyAwareEnv",
    "VehicleProfile",
    "ActuatorEnergyModel",
    "DirectEffortActuatorModel",
    "ElectricalComponent",
    "register_actuator_model",
    "__version__",
]
