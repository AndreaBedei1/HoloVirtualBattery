import math

import pytest

from holoenergy._validation import ConfigurationError
from holoenergy.evidence import EvidenceRecord, EvidenceRegistry, Source, coverage, default_registry
from holoenergy.units import Quantity, celsius_to_kelvin, convert, dbm_to_watt, to_si, unit_kind


def test_si_conversions():
    assert to_si(15, "W") == 15
    assert to_si(220, "mA") == pytest.approx(0.22)
    assert to_si(1, "Wh") == 3600
    assert to_si(18, "Ah") == 64800
    assert to_si(1, "kgf") == pytest.approx(9.80665)
    assert convert(3600, "J", "Wh") == pytest.approx(1)
    assert celsius_to_kelvin(25) == pytest.approx(298.15)
    assert convert(298.15, "K", "degC") == pytest.approx(25)
    assert Quantity.parse("5 W").si == 5
    assert Quantity(100, "mA").to("A").value == pytest.approx(0.1)


def test_ambiguous_and_non_electrical_units_rejected():
    with pytest.raises(ConfigurationError, match="Ambiguous"):
        unit_kind("C")
    with pytest.raises(ConfigurationError, match="Unknown unit"):
        unit_kind("watts")
    # Acoustic source level is not electrical power.
    with pytest.raises(ConfigurationError, match="no hardware-independent"):
        to_si(135, "dB re 1 uPa")
    with pytest.raises(ConfigurationError, match="no hardware-independent"):
        to_si(14, "dBm")
    with pytest.raises(ConfigurationError, match="expected power"):
        to_si(5, "V", kind="power")
    assert dbm_to_watt(30) == pytest.approx(1.0)


def _registry():
    registry = EvidenceRegistry()
    registry.add_source(
        {"id": "SRC", "type": "manufacturer_datasheet", "title": "x", "url": "https://example.org"}
    )
    return registry


def test_evidence_grade_cannot_exceed_relation():
    registry = _registry()
    with pytest.raises(ConfigurationError, match="allows at best grade C"):
        registry.add_record(
            {
                "id": "proxy.power",
                "component": "proxy",
                "quantity": "electrical_power",
                "unit": "W",
                "value": 4.0,
                "bound": "typical",
                "relation": "proxy",
                "grade": "A",
                "sources": ["SRC"],
            }
        )


def test_unconfigured_record_keeps_null_and_grade_d():
    registry = _registry()
    record = registry.add_record(
        {
            "id": "esc.idle_power",
            "component": "esc",
            "quantity": "electrical_power",
            "unit": "W",
            "value": None,
            "relation": "unsupported",
            "grade": "D",
        }
    )
    assert record.status == "unconfigured" and not record.configured
    with pytest.raises(ConfigurationError, match="value null"):
        EvidenceRecord.from_mapping(
            {
                "id": "x",
                "component": "x",
                "quantity": "q",
                "unit": "W",
                "value": 1,
                "status": "unconfigured",
            }
        )
    with pytest.raises(ConfigurationError, match="cite at least one source"):
        registry.add_record(
            {
                "id": "nosrc",
                "component": "x",
                "quantity": "q",
                "unit": "W",
                "value": 1,
                "bound": "typical",
                "relation": "representative",
                "grade": "B",
            }
        )
    with pytest.raises(ConfigurationError, match="unknown source"):
        registry.add_record(
            {
                "id": "badsrc",
                "component": "x",
                "quantity": "q",
                "unit": "W",
                "value": 1,
                "bound": "typical",
                "relation": "representative",
                "grade": "B",
                "sources": ["MISSING"],
            }
        )


def test_upper_bound_interval_and_derivation_rules():
    registry = _registry()
    record = registry.add_record(
        {
            "id": "cam.max",
            "component": "cam",
            "quantity": "electrical_power",
            "unit": "W",
            "value": 1.1,
            "bound": "upper_bound",
            "relation": "exact",
            "grade": "A",
            "sources": ["SRC"],
        }
    )
    assert record.interval_si() == (None, 1.1)
    with pytest.raises(ConfigurationError, match="derivation"):
        registry.add_record(
            {
                "id": "derived",
                "component": "x",
                "quantity": "q",
                "unit": "W",
                "value": 1,
                "bound": "derived",
                "relation": "exact",
                "grade": "A",
                "sources": ["SRC"],
            }
        )


def test_source_requires_locator():
    with pytest.raises(ConfigurationError, match="DOI or URL"):
        Source.from_mapping({"id": "s", "type": "journal_article", "title": "t"})


def test_coverage_is_energy_weighted_share():
    result = coverage({"A": 8.7, "B": 1.0, "C": 0.3})
    assert result["total_Wh"] == pytest.approx(10.0)
    assert result["share_percent"]["A"] == pytest.approx(87.0)
    assert result["share_percent"]["D"] == 0
    assert "not" in coverage({})["definition"] or coverage({})["total_Wh"] == 0


def test_packaged_registry_loads_and_is_consistent():
    registry = default_registry()
    assert registry.sources and registry.records
    for record in registry.records.values():
        record.validate(registry.sources)
        if record.configured and record.value is not None:
            assert math.isfinite(record.si())
    rows = registry.table()
    assert all(r["grade"] in "ABCD" for r in rows)
