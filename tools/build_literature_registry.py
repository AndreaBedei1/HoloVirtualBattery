"""Build the machine-readable literature registry from the evidence workbook and local PDFs.

Inputs (never modified):
  * the HoloEnergy literature/hardware workbook (sheets Papers, Datasheets, Downloads);
  * a directory of manually downloaded PDFs.

Output: ``holoenergy/evidence/data/literature.yaml`` with one entry per workbook paper
(P001...) and manufacturer source (D001...).  PDFs are matched by DOI found on their
first pages, then by exact normalised title, then by fuzzy title similarity (flagged).
Only file names and SHA-256 hashes are stored; PDFs are never copied into the
repository (copyright).  ``pdftotext`` (poppler) is used when available.

Usage:
  python tools/build_literature_registry.py --excel <workbook.xlsx> --pdf-dir <papers dir>
"""

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "holoenergy" / "evidence" / "data" / "literature.yaml"
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
FUZZY_THRESHOLD = 0.80

PUBLICATION_TYPES = {
    "Journal Article": "journal_article",
    "Article": "journal_article",
    "Proceedings Article": "conference_paper",
    "Article / Proceedings": "conference_paper",
    "Proceedings / journal-indexed": "conference_paper",
    "Preprint / article": "journal_article",
    "Preprint": "journal_article",
    "Working paper/article": "journal_article",
}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def normalise_doi(value):
    if not value:
        return None
    value = str(value).strip().lower().rstrip(".,;)")
    return value.removeprefix("https://doi.org/").removeprefix("doi:") or None


def normalise_title(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def pdf_text(path, workdir, pages=2):
    """First pages as text, or '' when no extractor is available."""
    exe = shutil.which("pdftotext")
    if exe is None:
        try:
            from pypdf import PdfReader  # optional
        except ImportError:
            return ""
        reader = PdfReader(str(path))
        return "\n".join((p.extract_text() or "") for p in reader.pages[:pages])
    # Short temporary names avoid Windows MAX_PATH failures with long titles.
    src = Path(workdir) / "in.pdf"
    out = Path(workdir) / "out.txt"
    shutil.copyfile(path, src)
    subprocess.run(
        [exe, "-f", "1", "-l", str(pages), "-layout", str(src), str(out)],
        capture_output=True,
        check=False,
    )
    return out.read_text(encoding="utf-8", errors="replace") if out.exists() else ""


def read_workbook(path):
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)

    def rows(name):
        data = [list(r) for r in wb[name].iter_rows(values_only=True)]
        header = data[0]
        return [
            dict(zip(header, r, strict=False)) for r in data[1:] if any(c is not None for c in r)
        ]

    return rows("Papers"), rows("Datasheets"), rows("Downloads")


def match_pdfs(papers, pdf_dir):
    by_doi = {normalise_doi(p["DOI"]): p["ID"] for p in papers if p.get("DOI")}
    by_title = {normalise_title(p["Title"]): p["ID"] for p in papers}
    matches, unmatched, seen_hash = {}, [], {}
    with tempfile.TemporaryDirectory() as tmp:
        for pdf in sorted(Path(pdf_dir).glob("*.pdf")):
            digest = sha256(pdf)
            record = {"local_pdf": pdf.name, "local_pdf_sha256": digest}
            if digest in seen_hash:
                record["duplicate_of_file"] = seen_hash[digest]
            seen_hash.setdefault(digest, pdf.name)
            text = pdf_text(pdf, tmp)
            found = None
            for doi in DOI_RE.findall(text[:6000]):
                doi = normalise_doi(doi)
                if doi in by_doi:
                    found = (by_doi[doi], "doi", 1.0)
                    break
            if found is None:
                # arXiv PDFs rarely print their DataCite DOI: match the arXiv identifier.
                for doi, pid in by_doi.items():
                    if doi and doi.startswith("10.48550/arxiv."):
                        arxiv_id = doi.removeprefix("10.48550/arxiv.")
                        if arxiv_id in pdf.stem or f"arXiv:{arxiv_id}" in text[:6000]:
                            found = (pid, "arxiv_id", 1.0)
                            break
            if found is None:
                compact = normalise_title(text[:4000])
                for title, pid in by_title.items():
                    if title and len(title) > 25 and title in compact:
                        found = (pid, "exact_title", 1.0)
                        break
            if found is None:
                stem = normalise_title(pdf.stem.replace("_", " "))
                best = max(
                    ((SequenceMatcher(None, stem, t).ratio(), pid) for t, pid in by_title.items()),
                    default=(0, None),
                )
                if best[0] >= FUZZY_THRESHOLD:
                    found = (best[1], "fuzzy_filename_title", round(best[0], 3))
            if found is None:
                unmatched.append(record)
                continue
            pid, method, score = found
            record.update(match_method=method, match_score=score)
            matches.setdefault(pid, []).append(record)
    return matches, unmatched


def topic_of(category):
    return {
        "BlueROV/T200": "bluerov_t200",
        "Thruster configurations": "thruster_configuration",
        "Hovering AUV": "hovering_auv",
        "Torpedo AUV": "torpedo_auv",
        "Mission energy": "mission_energy",
        "Battery": "battery",
        "USV": "surface_vessel",
        "Simulation / HoloOcean": "simulation",
    }.get(category, "other")


def build(excel, pdf_dir):
    papers, datasheets, downloads = read_workbook(excel)
    access = {d["ID"]: d for d in downloads}
    matches, unmatched = match_pdfs(papers, pdf_dir) if pdf_dir else ({}, [])
    entries = []
    for p in papers:
        doi = normalise_doi(p.get("DOI"))
        url = p.get("Preferred source / download URL")
        entries.append(
            {
                "paper_id": p["ID"],
                "kind": "paper",
                "title": p["Title"],
                "authors": [a.strip() for a in str(p.get("Authors") or "").split(";") if a.strip()],
                "year": int(p["Year"]) if p.get("Year") else None,
                "doi": doi,
                "source_type": PUBLICATION_TYPES.get(p.get("Publication type"), "journal_article"),
                "publication_type_workbook": p.get("Publication type"),
                "publisher_url": f"https://doi.org/{doi}" if doi else url,
                "open_access_url": url
                if access.get(p["ID"], {}).get("Access status") == "Direct/open link listed"
                else None,
                "topic": topic_of(p.get("Category")),
                "category_workbook": p.get("Category"),
                "vehicle_or_component": p.get("Vehicle / component"),
                "evidence_type": p.get("Evidence type"),
                "why_useful": p.get("Why useful for HoloEnergy"),
                "workbook_confidence": p.get("Confidence"),
                "workbook_citations": p.get("Citations"),
                "local_copies": matches.get(p["ID"], []),
                "redistribution": "reference_only",
            }
        )
    by_title = {
        str(d["Title / model"]).strip(): d["ID"] for d in downloads if str(d["ID"]).startswith("D")
    }
    for d in datasheets:
        name = str(d["Real device / model"]).strip()
        did = by_title.get(name)
        if did is None:
            raise SystemExit(f"Datasheet {name!r} has no Downloads ID")
        entries.append(
            {
                "paper_id": did,
                "kind": "manufacturer_source",
                "title": name,
                "manufacturer": d.get("Manufacturer"),
                "category_workbook": d.get("Category"),
                "holoocean_mapping": d.get("HoloOcean / framework mapping"),
                "url": d.get("Primary source URL"),
                "workbook_values_unverified": {
                    "supply": d.get("Supply"),
                    "typical_power": d.get("Typical / nominal power"),
                    "peak_or_other": d.get("Peak / other electrical"),
                },
                "modelling_note": d.get("Modelling note"),
                "workbook_confidence": d.get("Confidence"),
                "redistribution": "reference_only",
            }
        )
    return {
        "registry": "HoloEnergy literature registry",
        "generated": date.today().isoformat(),
        "generator": "tools/build_literature_registry.py",
        "workbook": {"file": Path(excel).name, "sha256": sha256(excel)},
        "pdf_directory_name": Path(pdf_dir).name if pdf_dir else None,
        "matching": {
            "order": ["doi on first two pages", "exact normalised title", "fuzzy filename/title"],
            "fuzzy_threshold": FUZZY_THRESHOLD,
        },
        "policy": (
            "Workbook values are an initial evidence map, not verified evidence; verified "
            "parameters live in parameters/*.yaml with exact source locations. PDFs are not "
            "redistributed; only names and hashes are recorded."
        ),
        "entries": entries,
        "unmatched_local_pdfs": unmatched,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--excel", required=True)
    parser.add_argument("--pdf-dir")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    result = build(args.excel, args.pdf_dir)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(result, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    papers = [e for e in result["entries"] if e["kind"] == "paper"]
    local = sum(1 for e in papers if e["local_copies"])
    print(
        f"{len(papers)} papers ({local} with local PDF), "
        f"{len(result['entries']) - len(papers)} manufacturer sources, "
        f"{len(result['unmatched_local_pdfs'])} unmatched PDFs -> {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
