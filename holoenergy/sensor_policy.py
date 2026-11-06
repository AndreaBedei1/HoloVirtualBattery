"""Electrical meaning of HoloOcean 2.3.0 sensors (registry names from holoocean.sensors).

* ``state``: simulator ground truth / interfaces (Pose, Velocity, Dynamics, ...). They are
  not hardware and contribute 0 W; a component may not attach power to them.
* ``derived``: semantic outputs (SemanticSegmentationCamera, RaycastSemanticLidar). Their
  energy must be decomposed into the physical sensor plus an explicit compute workload.
* ``physical``: physically inspired sensors that a real device can represent.  The listed
  profiles are representative choices with their own evidence, never the only mapping.
* ``host``: visualisation/capture on the simulation host, not vehicle electrical load.
* ``unmapped``: physically inspired but with no defensible default device; the user
  must configure hardware explicitly.
"""

from __future__ import annotations

from ._validation import ConfigurationError

STATE = {
    "PoseSensor",
    "LocationSensor",
    "VelocitySensor",
    "RotationSensor",
    "OrientationSensor",
    "DynamicsSensor",
    "WorldNumSensor",
    "CollisionSensor",
    "JointRotationSensor",
    "RelativeSkeletalPositionSensor",
    "PressureSensor",
    "BallLocationSensor",
    "AbuseSensor",
    "DistanceTask",
    "LocationTask",
    "FollowTask",
    "AvoidTask",
    "CupGameTask",
    "CleanUpTask",
}
HOST = {"ViewportCapture"}
DERIVED = {
    "SemanticSegmentationCamera": ("RGBCamera-like physical camera", "compute workload"),
    "RaycastSemanticLidar": ("physical lidar (where appropriate)", "compute workload"),
}
PHYSICAL = {
    "DVLSensor": ["waterlinked-dvl-a50", "sonardyne-sprint-nav-mini"],
    "ImagingSonar": ["tritech-gemini-720is", "kongsberg-m3-500m", "bluerobotics-ping360"],
    "ProfilingSonar": ["cerulean-surveyor-240-16", "kongsberg-m3-500m", "tritech-micron"],
    "SidescanSonar": ["edgetech-2205"],
    "SinglebeamSonar": ["bluerobotics-ping-sonar"],
    "RGBCamera": ["bluerobotics-lowlight-usb-camera", "bluerobotics-4k-camera"],
    "CameraSensor": ["bluerobotics-lowlight-usb-camera", "bluerobotics-4k-camera"],
    "IMUSensor": ["vectornav-vn100-rugged", "bluerobotics-navigator"],
    "MagnetometerSensor": ["vectornav-vn100-rugged", "bluerobotics-navigator"],
    "GPSSensor": ["ublox-zed-f9p"],
    "DepthSensor": ["te-ms5837-30ba"],
    "BSTSensor": ["seabird-sbe49"],
    "AcousticBeaconSensor": ["communications adapter: acoustic modem profile"],
    "OpticalModemSensor": ["communications adapter: optical modem profile"],
}
UNMAPPED = {"RangeFinderSensor", "RaycastLidar", "DepthCamera"}
REGISTRY = STATE | HOST | set(DERIVED) | set(PHYSICAL) | UNMAPPED


def classify(sensor_type):
    if sensor_type in STATE:
        return {"kind": "state", "power_W": 0.0, "note": "simulator ground truth; 0 W"}
    if sensor_type in HOST:
        return {"kind": "host", "power_W": 0.0, "note": "host-side capture; not vehicle load"}
    if sensor_type in DERIVED:
        sensor, compute = DERIVED[sensor_type]
        return {"kind": "derived", "power_W": None, "decompose_into": [sensor, compute]}
    if sensor_type in PHYSICAL:
        return {
            "kind": "physical",
            "power_W": None,
            "representative_profiles": PHYSICAL[sensor_type],
        }
    if sensor_type in UNMAPPED:
        return {"kind": "unmapped", "power_W": None, "note": "no defensible default device"}
    raise ConfigurationError(f"Unknown HoloOcean 2.3.0 sensor type {sensor_type!r}")


def check_component_mapping(name, simulation_sensor, has_power):
    """Refuse electrical loads attached to non-physical or derived sensors."""
    if simulation_sensor is None:
        return
    kind = classify(simulation_sensor)["kind"]
    if kind in ("state", "host") and has_power:
        raise ConfigurationError(
            f"{name}: {simulation_sensor} is a simulator {kind} sensor and contributes 0 W; "
            "do not attach hardware power to it"
        )
    if kind == "derived":
        raise ConfigurationError(
            f"{name}: {simulation_sensor} is a derived semantic output; configure the physical "
            "sensor and a compute workload as separate components"
        )


def audit_agent_sensors(sensor_types, components):
    """Map each sensor of a HoloOcean agent to configured electrical components.

    ``sensor_types``: iterable of HoloOcean sensor type names on the agent.
    ``components``: mapping name -> component (with ``simulation_sensor``).
    """
    by_sensor = {}
    for name, item in components.items():
        sensor = getattr(item, "simulation_sensor", None)
        if sensor:
            by_sensor.setdefault(sensor, []).append(name)
    rows = []
    for sensor in sensor_types:
        info = classify(sensor)
        rows.append(
            {
                "sensor": sensor,
                **info,
                "configured_components": by_sensor.get(sensor, []),
                "status": "zero_power"
                if info["kind"] in ("state", "host")
                else ("configured" if by_sensor.get(sensor) else "no electrical model configured"),
            }
        )
    return rows
