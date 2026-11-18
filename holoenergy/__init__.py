"""Energy accounting for marine robot simulation, without hardware interfaces."""

__version__ = "0.2.0"

# Imported after the version because logging uses it for run metadata.
from .decision import assess_energy_requirement, compare_energy
from .env_wrapper import EnergyAwareEnv
from .models.actuator import ActuatorEnergyModel, DirectEffortActuatorModel, register_actuator_model
from .models.components import ElectricalComponent
from .models.vehicle import VehicleProfile
from .robot import (
    AuxiliaryProfile,
    BatteryProfile,
    CommunicationProfile,
    ComponentProfile,
    ComputeProfile,
    ConverterProfile,
    EvidenceRecordSpec,
    EvidenceSourceSpec,
    Ref,
    RobotEnergyProfile,
    SensorProfile,
    State,
    ThrusterProfile,
)

__all__ = [
    "EnergyAwareEnv",
    "VehicleProfile",
    "ActuatorEnergyModel",
    "DirectEffortActuatorModel",
    "ElectricalComponent",
    "register_actuator_model",
    "assess_energy_requirement",
    "compare_energy",
    "RobotEnergyProfile",
    "ThrusterProfile",
    "BatteryProfile",
    "ComponentProfile",
    "SensorProfile",
    "ComputeProfile",
    "CommunicationProfile",
    "AuxiliaryProfile",
    "ConverterProfile",
    "EvidenceSourceSpec",
    "EvidenceRecordSpec",
    "Ref",
    "State",
    "__version__",
]
