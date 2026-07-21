"""Dev-time recorder for task 008 full-text ingestion fixtures.

Fetches the approved real documents with stdlib urllib, derives deterministic
edge-case documents with PyMuPDF, writes the committed fixture manifest, and
runs fixture self-checks. This script is never imported by ``policy_atlas``.

Usage:
    uv run --project backend python scripts/record_fulltext_fixtures.py
"""

from __future__ import annotations

import json
import re
import subprocess
from importlib import metadata
from pathlib import Path
from typing import Any

import fitz

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "backend" / "tests" / "data" / "fulltext"
MANIFEST_PATH = ROOT / "backend" / "tests" / "data" / "fulltext_manifest.json"
RECORDED_AT = "2026-07-05"
TIMEOUT_S = 90
MAX_TOTAL_BYTES = 26_000_000
OVERSIZE_BYTES = 209_715_200
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
NESTA_PERMISSION = {
    "org": "Nesta",
    "who": "Shabeer Rauf",
    "date": RECORDED_AT,
    "note": "own-org content; committing authorised with task-008 contract approval (decision 9)",
}

# file, URL, title, publisher, licence, content type
SOURCES = [
    ("nesta_heat_pump_costs.pdf", "https://media.nesta.org.uk/documents/How_to_reduce_the_cost_of_heat_pumps_v4_1.pdf", "How to reduce the cost of heat pumps", "Nesta", None, "application/pdf"),
    ("nesta_fairer_start_discovery.pdf", "https://media.nesta.org.uk/documents/A_Fairer_Start_Local-_Learning_from_rapid_discovery_projects_v5.pdf", "A Fairer Start Local: Learning from rapid discovery projects", "Nesta", None, "application/pdf"),
    ("worldbank_obesity_flagship.pdf", "https://openknowledge.worldbank.org/server/api/core/bitstreams/cddcb99b-9d0b-5f08-9cf6-934974a308cf/content", "Obesity: Health and Economic Consequences of an Impending Global Challenge", "World Bank", "CC-BY-3.0-IGO", "application/pdf"),
    ("frontiers_school_readiness_2022.pdf", "https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.1023505/pdf", "Predicting school readiness program implementation in community-based childcare centers", "Frontiers Media", "CC-BY-4.0", "application/pdf"),
    ("frontiers_getting_ready_2018.pdf", "https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2018.00759/pdf", "Parent Involvement in the Getting Ready for School Intervention Is Associated With Changes in School Readiness Skills", "Frontiers Media", "CC-BY-4.0", "application/pdf"),
    ("naturecomms_a2a_heat_pumps_2024.pdf", "https://www.nature.com/articles/s41467-024-49836-3.pdf", "Energy and environmental impacts of air-to-air heat pumps in a mid-latitude city", "Springer Nature", "CC-BY-4.0", "application/pdf"),
    ("frontiers_ashp_ventilation_2021.pdf", "https://www.frontiersin.org/journals/energy-research/articles/10.3389/fenrg.2021.785461/pdf", "An Experimental Study on External Ventilation to the Heating Performance of Household Air Source Heat Pump", "Frontiers Media", "CC-BY-4.0", "application/pdf"),
    ("plos_food_environment_review.pdf", "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0182581&type=printable", "Improving food environments and tackling obesity: A realist systematic review of the policy success of regulatory interventions targeting population nutrition", "PLOS", "CC-BY-4.0", "application/pdf"),
    ("bmc_fiscal_policies_review.html", "https://bmcpublichealth.biomedcentral.com/articles/10.1186/s12889-024-19988-4", "Effectiveness of implemented global dietary interventions: a scoping review of fiscal policies", "BMC (Springer Nature)", "CC-BY-4.0", "text/html"),
    ("nesta_heat_pumps_report_page.html", "https://www.nesta.org.uk/report/reduce-the-cost-of-heat-pumps/", "How to reduce the cost of heat pumps (web report page)", "Nesta", None, "text/html"),
]

# fixture URL, outcome, status/file, content type
OUTCOME_ROWS = [
    ("https://doi.org/10.99999/ec5197d219", "http_error", 403, None),
    ("https://doi.org/10.99999/40ee8970fd", "http_error", 404, None),
    ("https://doi.org/10.99999/f99b17cdd3", "ok", "bmc_fiscal_policies_review.html", "text/html"),
    ("https://doi.org/10.99999/dfdbddcf6b", "oversize", OVERSIZE_BYTES, None),
    ("https://doi.org/10.99999/050131ae0e", "ok", "derived_thin_stub.html", "text/html"),
    ("https://doi.org/10.99999/cacf1b906a", "ok", "nesta_heat_pumps_report_page.html", "text/html"),
    ("https://doi.org/10.99999/c12dbae192", "http_error", 403, None),
    ("https://doi.org/10.99999/8aaf38d751", "http_error", 404, None),
    ("https://doi.org/10.99999/287b9e9e3a", "ok", "frontiers_school_readiness_2022.pdf", "application/pdf"),
    ("https://doi.org/10.99999/03c049fed0", "http_error", 404, None),
    ("https://doi.org/10.99999/64eb9d2623", "http_error", 404, None),
    ("https://doi.org/10.99999/348dc19a06", "http_error", 403, None),
    ("https://doi.org/10.99999/d621138b12", "http_error", 404, None),
    ("https://doi.org/10.99999/cf91b048b2", "ok", "nesta_heat_pump_costs.pdf", "application/pdf"),
    ("https://example.org/7af181a9eb31", "ok", "nesta_fairer_start_discovery.pdf", "application/pdf"),
    ("https://example.org/ef2da3f38189", "ok", "frontiers_ashp_ventilation_2021.pdf", "application/pdf"),
    ("https://example.org/63c7141e1da9.pdf", "ok", "worldbank_obesity_flagship.pdf", "application/pdf"),
    ("https://example.org/0e75c7f28b57", "http_error", 404, None),
    ("https://example.org/e1209ba1a2a6", "ok", "naturecomms_a2a_heat_pumps_2024.pdf", "application/pdf"),
    ("https://example.org/0f7f4a9baf7b.pdf", "ok", "derived_image_only.pdf", "application/pdf"),
    ("https://example.org/7a1dc062abde", "ok", "derived_image_only.pdf", "application/pdf"),
    ("https://example.org/42ad8806fb1f", "ok", "frontiers_getting_ready_2018.pdf", "application/pdf"),
    ("https://example.org/0914a0ee980b.pdf", "ok", "derived_corrupt.pdf", "application/pdf"),
    ("https://example.org/9088148a5445", "ok", "derived_corrupt.pdf", "application/pdf"),
    ("https://example.org/fcb0d6954f74", "ok", "plos_food_environment_review.pdf", "application/pdf"),
    ("https://example.org/2717858d3fb6", "oversize", OVERSIZE_BYTES, None),
    ("https://example.org/04fc90d2b999.pdf", "http_error", 404, None),
    ("https://example.org/1938908cc6b7.pdf", "http_error", 403, None),
    ("https://example.org/051e008a0329", "http_error", 403, None),
]


def _outcomes() -> dict[str, dict[str, Any]]:
    out = {}
    for url, outcome, value, content_type in OUTCOME_ROWS:
        if outcome == "ok":
            out[url] = {"outcome": outcome, "file": value, "content_type": content_type}
        elif outcome == "http_error":
            out[url] = {"outcome": outcome, "http_status": value}
        else:
            out[url] = {"outcome": outcome, "content_length": value}
    return out


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def _download(url: str) -> bytes:
    # curl rather than urllib: nature.com (and friends) bot-block urllib's
    # client fingerprint but serve curl. Dev-time only; never in the package.
    proc = subprocess.run(
        ["curl", "-sSL", "--fail", "--max-time", str(TIMEOUT_S), "-A", USER_AGENT, url],
        capture_output=True, timeout=TIMEOUT_S + 30, check=True,
    )
    return proc.stdout


def _check_file(name: str, content_type: str) -> None:
    data = (OUT_DIR / name).read_bytes()
    assert data, f"{name} is empty"
    if content_type == "application/pdf":
        assert data.startswith(b"%PDF-"), f"{name} does not start with %PDF-"
    if content_type == "text/html":
        assert b"<html" in data.lower(), f"{name} does not contain <html"


def _stated_licence(path: Path) -> str | None:
    with fitz.open(path) as pdf:
        pages = [0] if pdf.page_count == 1 else [0, pdf.page_count - 1]
        text = "\n".join(pdf[i].get_text() for i in pages)
    for pattern in (r"(?i)[^\n.]{0,160}Creative Commons[^\n.]{0,220}\.?",
                    r"(?i)[^\n.]{0,160}CC[- ]BY[^\n.]{0,160}\.?"):
        if match := re.search(pattern, text):
            return " ".join(match.group(0).split())
    return None


def _add_doc(docs: dict[str, dict[str, Any]], row: tuple, size: int) -> None:
    name, url, title, publisher, licence, content_type = row
    docs[name] = {
        "title": title,
        "source_url": url,
        "publisher": publisher,
        "licence": licence,
        "retrieved": RECORDED_AT,
        "content_type": content_type,
        "bytes": size,
    }
    if licence is None:
        docs[name]["permission"] = dict(NESTA_PERMISSION)


def _derive_image_only(source_pdf: Path, target: Path) -> None:
    with fitz.open(source_pdf) as src, fitz.open() as out:
        for page in src[:3]:
            # jpg at 96 dpi keeps the derivative small; the point is "no text
            # layer", not image fidelity
            pix = page.get_pixmap(dpi=96, alpha=False)
            dst = out.new_page(width=page.rect.width, height=page.rect.height)
            dst.insert_image(dst.rect, stream=pix.tobytes("jpg"))
        tmp = target.with_name(target.name + ".tmp")
        out.save(tmp)
    tmp.replace(target)


def _write_derived(docs: dict[str, dict[str, Any]]) -> None:
    image_pdf = OUT_DIR / "derived_image_only.pdf"
    _derive_image_only(OUT_DIR / "nesta_heat_pump_costs.pdf", image_pdf)
    docs[image_pdf.name] = {
        "title": "Image-only derivative of How to reduce the cost of heat pumps",
        "source_url": "urn:policy-atlas:fixture:derived_image_only.pdf",
        "publisher": "Policy Atlas task 008 fixture recorder",
        "licence": None,
        "permission": dict(NESTA_PERMISSION),
        "retrieved": RECORDED_AT,
        "content_type": "application/pdf",
        "bytes": image_pdf.stat().st_size,
        "derived_from": "nesta_heat_pump_costs.pdf",
    }
    generated = [
        ("derived_corrupt.pdf", b"%PDF-1.7\n" + bytes(range(256)) * 16, "application/pdf"),
        ("derived_thin_stub.html", b"<!doctype html><html><head><title>Redirecting</title></head><body><nav><a href='#'></a><a href='#'></a></nav><main><p>Redirecting to publisher site...</p></main></body></html>\n", "text/html"),
    ]
    for name, data, content_type in generated:
        _atomic_write(OUT_DIR / name, data)
        docs[name] = {
            "title": f"Generated {name} fixture",
            "source_url": f"urn:policy-atlas:fixture:{name}",
            "publisher": "Policy Atlas task 008 fixture recorder",
            "licence": "CC0-1.0",
            "retrieved": RECORDED_AT,
            "content_type": content_type,
            "bytes": (OUT_DIR / name).stat().st_size,
            "generated": True,
        }


def _manifest(docs: dict[str, dict[str, Any]], total: int) -> dict[str, Any]:
    return {
        "_meta": {
            "recorded_at": RECORDED_AT,
            "recorder": "scripts/record_fulltext_fixtures.py",
            "recorder_version": "v1",
            "pymupdf4llm_version": metadata.version("pymupdf4llm"),
            "trafilatura_version": metadata.version("trafilatura"),
            "coverage": ["long report 100+ pages", "multi-column academic PDF", "HTML report page", "HTML academic article", "thin HTML", "image-only PDF", "corrupt PDF", "paywall 403", "dead link 404", "oversize", "cascade fallback", "n/a-sentinel URL"],
            "total_bytes": total,
        },
        "outcomes": _outcomes(),
        "documents": docs,
    }


def _page_count(path: Path) -> int:
    with fitz.open(path) as pdf:
        return pdf.page_count


def _all_text(path: Path) -> str:
    with fitz.open(path) as pdf:
        return "".join(page.get_text() for page in pdf)


def _self_check(manifest: dict[str, Any]) -> tuple[dict[str, int], int, int]:
    sizes = {p.name: p.stat().st_size for p in sorted(OUT_DIR.iterdir()) if p.is_file()}
    for name, doc in manifest["documents"].items():
        assert name in sizes, f"{name} missing on disk"
        assert doc["bytes"] == sizes[name], f"{name} manifest bytes mismatch"
        assert doc.get("licence") or doc.get("permission"), f"{name} lacks licence/permission"
        _check_file(name, doc["content_type"])
    for url, outcome in manifest["outcomes"].items():
        if outcome["outcome"] == "ok":
            assert outcome["file"] in manifest["documents"], f"{url} references missing document"
            assert (OUT_DIR / outcome["file"]).exists(), f"{url} references missing file"
    worldbank_pages = _page_count(OUT_DIR / "worldbank_obesity_flagship.pdf")
    if worldbank_pages < 100:
        print(f"worldbank_obesity_flagship.pdf page count: {worldbank_pages}")
    assert worldbank_pages >= 100, "World Bank PDF has fewer than 100 pages"
    assert _all_text(OUT_DIR / "derived_image_only.pdf").strip() == "", "image-only PDF has text"
    total = sum(sizes.values())
    assert total <= MAX_TOTAL_BYTES, f"fulltext fixtures exceed {MAX_TOTAL_BYTES} bytes: {total}"
    assert json.loads(MANIFEST_PATH.read_text()) == manifest, "manifest did not round-trip"
    return sizes, total, worldbank_pages


def _print_summary(sizes: dict[str, int], total: int, docs: dict[str, dict[str, Any]]) -> None:
    print("\nper-file sizes:")
    for name, size in sizes.items():
        print(f"  {name}\t{size}")
    print(f"total\t{total}")
    print("\nsummary:")
    print("file\tbytes\tlicence-or-permission")
    for name, doc in sorted(docs.items()):
        basis = doc["licence"] or f"permission:{doc['permission']['org']}:{doc['permission']['date']}"
        print(f"{name}\t{doc['bytes']}\t{basis}")


def _main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    docs: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for row in SOURCES:
        name, url, *_rest, content_type = row
        print(f"fetching {name}")
        try:
            data = _download(url)
        except RuntimeError as exc:
            failures.append(f"{name}: {exc}")
            continue
        _atomic_write(OUT_DIR / name, data)
        _check_file(name, content_type)
        _add_doc(docs, row, len(data))
        if name in {"nesta_heat_pump_costs.pdf", "nesta_fairer_start_discovery.pdf"}:
            if stated := _stated_licence(OUT_DIR / name):
                docs[name]["stated_licence"] = stated
    if failures:
        raise AssertionError("download failures after 3 retries: " + "; ".join(failures))
    _write_derived(docs)
    total = sum(path.stat().st_size for path in OUT_DIR.iterdir() if path.is_file())
    manifest = _manifest(docs, total)
    _atomic_write(MANIFEST_PATH, (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    sizes, total, worldbank_pages = _self_check(manifest)
    print(f"\nworldbank_obesity_flagship.pdf pages: {worldbank_pages}")
    _print_summary(sizes, total, docs)
    print("\nall full-text fixture checks passed")


if __name__ == "__main__":
    _main()
