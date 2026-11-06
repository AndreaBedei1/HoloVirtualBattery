"""Optional integrations. None of them imports third-party simulators at import time."""

from .communications import CommunicationEnergyAdapter, ModemPowerProfile

__all__ = ["CommunicationEnergyAdapter", "ModemPowerProfile"]
