"""Formal evidence registry: sources, parameter records, grades and coverage.

Every configurable electrical/physical number that HoloEnergy ships is an
``EvidenceRecord`` that points to one or more ``Source`` entries with an exact
extraction location.  Grades follow the project methodology:

A  exact vehicle/component experimental or primary manufacturer evidence
B  strong representative real component / closely matching vehicle
C  literature proxy or incomplete mapping
D  user-defined, unsupported or unconfigured

The grade is bounded by the *relation* between the evidence and the modelled
item (``exact`` -> A, ``representative`` -> B, ``proxy`` -> C, ``user`` /
``unsupported`` -> D), so a proxy can never be registered as A-grade evidence.
A record without a defensible value keeps ``value: null`` and status
``unconfigured``; nothing is filled with a default.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import files

import yaml

from .._validation import ConfigurationError
from ..units import to_si, unit_kind

GRADES = ("A", "B", "C", "D")
GRADE_MEANING = {
    "A": "exact vehicle/component experimental or primary manufacturer evidence",
    "B": "strong representative real component or closely matching vehicle",
    "C": "literature proxy or incomplete mapping",
    "D": "user-defined, unsupported or unconfigured",
}
RELATION_MAX_GRADE = {
    "exact": "A",
    "representative": "B",
    "proxy": "C",
    "user": "D",
    "unsupported": "D",
}
SOURCE_TYPES = {
    "journal_article",
    "conference_paper",
    "thesis",
    "dataset",
    "manufacturer_datasheet",
    "manufacturer_webpage",
    "manufacturer_dataset",
    "official_documentation",
    "simulator_source",
    "software",
    "standard",
    "user",
    "derived",
}
BOUNDS = {
    "exact",
    "measured_mean",
    "typical",
    "nominal",
    "upper_bound",
    "lower_bound",
    "range",
    "budget",
    "derived",
    "unknown",
}
LOCATION_KEYS = {"page", "section", "table", "figure", "equation", "line", "sheet", "note"}


def _grade_rank(grade):
    return GRADES.index(grade)


def cap_grade(grade, relation):
    """Grade of evidence when used with ``relation`` (never better than the relation allows)."""
    limit = RELATION_MAX_GRADE[relation]
    return grade if _grade_rank(grade) >= _grade_rank(limit) else limit


@dataclass(frozen=True)
class Source:
    id: str
    type: str
    title: str
    authors: tuple = ()
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    publisher: str | None = None
    accessed: str | None = None
    revision: str | None = None
    local_file: str | None = None
    sha256: str | None = None
    redistribution: str = "reference_only"
    notes: str | None = None

    @classmethod
    def from_mapping(cls, data):
        allowed = set(cls.__dataclass_fields__)
        extra = set(data) - allowed
        if extra:
            raise ConfigurationError(f"Unknown source fields {sorted(extra)} in {data.get('id')}")
        for key in ("id", "type", "title"):
            if not isinstance(data.get(key), str) or not data[key].strip():
                raise ConfigurationError(f"Source requires nonempty {key}")
        if data["type"] not in SOURCE_TYPES:
            raise ConfigurationError(f"Source {data['id']}: unknown type {data['type']}")
        if not (data.get("doi") or data.get("url") or data["type"] in ("user", "derived")):
            raise ConfigurationError(f"Source {data['id']} needs a DOI or URL")
        values = dict(data)
        values["authors"] = tuple(values.get("authors") or ())
        return cls(**values)

    def citation(self):
        authors = ", ".join(self.authors[:3]) + (" et al." if len(self.authors) > 3 else "")
        parts = [p for p in (authors, f"({self.year})" if self.year else None, self.title) if p]
        locator = f"doi:{self.doi}" if self.doi else self.url
        return ". ".join(parts) + (f". {locator}" if locator else "")


@dataclass(frozen=True)
class EvidenceRecord:
    """One parameter value (or an explicit gap) with its full provenance."""

    id: str
    component: str
    quantity: str
    unit: str | None
    value: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    bound: str = "unknown"
    relation: str = "unsupported"
    grade: str = "D"
    status: str = "unconfigured"
    sources: tuple = ()
    location: Mapping = field(default_factory=dict)
    conditions: Mapping = field(default_factory=dict)
    derivation: str | None = None
    uncertainty: Mapping = field(default_factory=dict)
    notes: str | None = None
    snippet: str | None = None
    dataset: Mapping = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data, sources=None):
        allowed = set(cls.__dataclass_fields__)
        extra = set(data) - allowed
        if extra:
            raise ConfigurationError(f"Unknown evidence fields {sorted(extra)} in {data.get('id')}")
        values = copy.deepcopy(dict(data))
        values["sources"] = tuple(values.get("sources") or ())
        has_number = any(values.get(k) is not None for k in ("value", "value_min", "value_max"))
        has_number = has_number or bool(values.get("dataset"))
        values.setdefault("status", "configured" if has_number else "unconfigured")
        record = cls(**values)
        record.validate(sources)
        return record

    def validate(self, sources=None):
        name = self.id
        if not isinstance(name, str) or not name:
            raise ConfigurationError("Evidence record requires an id")
        if self.grade not in GRADES:
            raise ConfigurationError(f"{name}: grade must be one of {GRADES}")
        if self.relation not in RELATION_MAX_GRADE:
            raise ConfigurationError(f"{name}: unknown relation {self.relation}")
        if _grade_rank(self.grade) < _grade_rank(RELATION_MAX_GRADE[self.relation]):
            raise ConfigurationError(
                f"{name}: relation '{self.relation}' allows at best grade "
                f"{RELATION_MAX_GRADE[self.relation]}, not {self.grade}"
            )
        if self.bound not in BOUNDS:
            raise ConfigurationError(f"{name}: unknown bound {self.bound}")
        if self.status not in ("configured", "unconfigured"):
            raise ConfigurationError(f"{name}: status must be configured or unconfigured")
        if self.status == "configured":
            if (
                self.value is None
                and self.value_min is None
                and self.value_max is None
                and not self.dataset
            ):
                raise ConfigurationError(
                    f"{name}: configured records need a value, range or dataset"
                )
            if self.unit is None and not self.dataset:
                raise ConfigurationError(f"{name}: configured records need an explicit unit")
        else:
            if self.value is not None:
                raise ConfigurationError(f"{name}: an unconfigured record must keep value null")
            if self.grade != "D":
                raise ConfigurationError(f"{name}: an unconfigured record is grade D")
        if self.dataset and not isinstance(self.dataset.get("path"), str):
            raise ConfigurationError(f"{name}: dataset requires a package-relative path")
        if self.unit is not None:
            unit_kind(self.unit)
        for key in ("value", "value_min", "value_max"):
            v = getattr(self, key)
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
                raise ConfigurationError(f"{name}: {key} must be numeric or null")
        if self.value_min is not None and self.value_max is not None:
            if self.value_min > self.value_max:
                raise ConfigurationError(f"{name}: value_min exceeds value_max")
        if self.bound == "derived" and not self.derivation:
            raise ConfigurationError(f"{name}: derived values must state their derivation")
        if self.status == "configured" and self.grade in ("A", "B", "C") and not self.sources:
            raise ConfigurationError(f"{name}: graded evidence must cite at least one source")
        unknown = set(self.location) - LOCATION_KEYS
        if unknown:
            raise ConfigurationError(f"{name}: unknown location fields {sorted(unknown)}")
        if sources is not None:
            missing = [s for s in self.sources if s not in sources]
            if missing:
                raise ConfigurationError(f"{name}: unknown source ids {missing}")

    @property
    def configured(self):
        return self.status == "configured"

    def si(self, which="value"):
        value = getattr(self, which)
        return None if value is None else to_si(value, self.unit)

    def interval_si(self):
        """Defensible numeric interval [low, high] in SI, or None when only a point exists.

        An upper bound without a published lower value yields (None, high): the
        caller decides how to treat the open side and must report it.
        """
        low = self.si("value_min")
        high = self.si("value_max")
        if self.bound == "upper_bound" and high is None:
            high = self.si("value")
        if self.bound == "lower_bound" and low is None:
            low = self.si("value")
        if low is None and high is None:
            return None
        return (low, high)

    def to_dict(self):
        result = {k: copy.deepcopy(getattr(self, k)) for k in self.__dataclass_fields__}
        result["sources"] = list(self.sources)
        result["location"] = dict(self.location)
        result["conditions"] = dict(self.conditions)
        result["uncertainty"] = dict(self.uncertainty)
        result["dataset"] = dict(self.dataset)
        return result


class EvidenceRegistry:
    """In-memory registry; the packaged one is loaded with :func:`default_registry`."""

    def __init__(self, sources=(), records=(), *, version=None):
        self.version = version
        self.sources = {}
        self.records = {}
        self.literature = None
        for source in sources:
            self.add_source(source)
        for record in records:
            self.add_record(record)

    def add_source(self, source):
        if not isinstance(source, Source):
            source = Source.from_mapping(source)
        if source.id in self.sources:
            raise ConfigurationError(f"Duplicate source id {source.id}")
        self.sources[source.id] = source
        return source

    def add_record(self, record):
        if not isinstance(record, EvidenceRecord):
            record = EvidenceRecord.from_mapping(record, self.sources)
        else:
            record.validate(self.sources)
        if record.id in self.records:
            raise ConfigurationError(f"Duplicate evidence id {record.id}")
        self.records[record.id] = record
        return record

    def get(self, record_id):
        try:
            return self.records[record_id]
        except KeyError as exc:
            raise ConfigurationError(f"Unknown evidence record {record_id}") from exc

    def source(self, source_id):
        return self.sources[source_id]

    def for_component(self, component):
        return [r for r in self.records.values() if r.component == component]

    def unconfigured(self):
        return [r for r in self.records.values() if not r.configured]

    def table(self, record_ids=None):
        """Flat rows (parameter, value, unit, source, DOI/URL, grade, ...) for reports/papers."""
        ids = record_ids if record_ids is not None else sorted(self.records)
        rows = []
        for rid in ids:
            record = self.get(rid)
            cited = [self.sources[s] for s in record.sources]
            rows.append(
                {
                    "parameter": record.id,
                    "component": record.component,
                    "quantity": record.quantity,
                    "value": record.value,
                    "value_min": record.value_min,
                    "value_max": record.value_max,
                    "unit": record.unit,
                    "bound": record.bound,
                    "grade": record.grade,
                    "relation": record.relation,
                    "status": record.status,
                    "sources": [s.id for s in cited],
                    "citation": "; ".join(s.citation() for s in cited),
                    "doi_or_url": "; ".join(
                        (s.doi and f"doi:{s.doi}") or s.url or "" for s in cited
                    ),
                    "location": dict(record.location),
                    "conditions": dict(record.conditions),
                    "uncertainty": dict(record.uncertainty),
                    "derivation": record.derivation,
                    "notes": record.notes,
                }
            )
        return rows

    @classmethod
    def from_mappings(cls, sources_doc, parameter_docs, version=None):
        registry = cls(version=version)
        for source in sources_doc.get("sources", []):
            registry.add_source(source)
        for doc in parameter_docs:
            for record in doc.get("parameters", []):
                registry.add_record(record)
        return registry


def _load_yaml(resource):
    value = yaml.safe_load(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConfigurationError(f"{resource} must contain a mapping")
    return value


def literature_sources(literature):
    """Convert generated literature.yaml entries to Source mappings (single bibliography)."""
    result = []
    for entry in literature.get("entries", []):
        copies = entry.get("local_copies") or []
        if entry["kind"] == "paper":
            result.append(
                {
                    "id": entry["paper_id"],
                    "type": entry.get("source_type", "journal_article"),
                    "title": entry["title"],
                    "authors": entry.get("authors") or [],
                    "year": entry.get("year"),
                    "doi": entry.get("doi"),
                    "url": entry.get("publisher_url") or entry.get("open_access_url"),
                    "local_file": copies[0]["local_pdf"] if copies else None,
                    "sha256": copies[0]["local_pdf_sha256"] if copies else None,
                    "redistribution": entry.get("redistribution", "reference_only"),
                }
            )
        else:
            result.append(
                {
                    "id": entry["paper_id"],
                    "type": "manufacturer_webpage",
                    "title": entry["title"],
                    "publisher": entry.get("manufacturer"),
                    "url": entry.get("url"),
                    "notes": "Workbook manufacturer source; values verified separately.",
                }
            )
    return result


@lru_cache(maxsize=1)
def default_registry():
    """Packaged evidence registry (literature.yaml + sources.yaml + parameters/*.yaml)."""
    root = files("holoenergy").joinpath("evidence", "data")
    sources = _load_yaml(root.joinpath("sources.yaml"))
    literature = _load_yaml(root.joinpath("literature.yaml"))
    parameter_docs = [
        _load_yaml(item)
        for item in sorted(root.joinpath("parameters").iterdir(), key=lambda p: p.name)
        if item.name.endswith(".yaml")
    ]
    merged = {"sources": literature_sources(literature) + list(sources.get("sources", []))}
    registry = EvidenceRegistry.from_mappings(
        merged, parameter_docs, version=sources.get("registry_version")
    )
    registry.literature = literature
    return registry


def coverage(energy_by_grade_Wh):
    """Energy-weighted evidence-grade shares.

    ``energy_by_grade_Wh`` maps grade -> predicted energy (Wh) whose electrical
    power model is parameterised by evidence of that grade.  The result states
    which share of the *predicted energy* rests on each evidence grade.  It is a
    provenance descriptor, not a probability, accuracy or significance measure:
    an A-grade share says the parameters are primary data for the configured
    hardware, not that the mission prediction has been validated.
    """
    totals = {g: float(energy_by_grade_Wh.get(g, 0.0)) for g in GRADES}
    if any(v < -1e-12 for v in totals.values()):
        raise ConfigurationError("Energy by grade must be nonnegative")
    total = sum(totals.values())
    return {
        "energy_Wh": totals,
        "share_percent": {g: (100 * v / total if total > 0 else 0.0) for g, v in totals.items()},
        "total_Wh": total,
        "definition": (
            "Share of predicted energy whose electrical power model parameters carry "
            "each evidence grade; vehicle hydrodynamics are simulator-owned and excluded."
        ),
    }


__all__ = [
    "GRADES",
    "GRADE_MEANING",
    "RELATION_MAX_GRADE",
    "EvidenceRecord",
    "EvidenceRegistry",
    "Source",
    "cap_grade",
    "coverage",
    "default_registry",
]
