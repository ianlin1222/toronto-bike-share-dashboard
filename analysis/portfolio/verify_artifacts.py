"""Independently check the delivered Office/PDF containers; not a native Excel test."""

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
XLSX = ROOT / "outputs/portfolio-2026-10-17/Dockside_Analysis.xlsx"
PDF = ROOT / "output/pdf/Dockside_Case_Study.pdf"
NOTEBOOK = HERE / "Dockside_Case_Study.ipynb"
HTML = ROOT / "output/notebook/Dockside_Case_Study.html"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
q = json.loads((HERE / "data/analysis.json").read_text())["quality"][0]

with ZipFile(XLSX) as package:
    assert package.testzip() is None
    paths = package.namelist()
    workbook = ET.fromstring(package.read("xl/workbook.xml"))
    sheets = [s.attrib["name"] for s in workbook.findall("m:sheets/m:sheet", NS)]
    assert sheets == [
        "Overview",
        "Stations",
        "Daily coverage",
        "Time patterns",
        "Nearby alternatives",
        "Source QA",
        "Read Me",
    ]
    assert not any("vbaProject" in p or "externalLinks/" in p for p in paths)
    assert "xl/connections.xml" not in paths
    names = {n.attrib["name"]: n.text for n in workbook.findall("m:definedNames/m:definedName", NS)}
    assert "StationIDs" in names and "Stations" in names["StationIDs"]
    worksheet_paths = [
        p for p in paths if p.startswith("xl/worksheets/sheet") and p.endswith(".xml")
    ]
    formula_count = validation_count = 0
    for name in worksheet_paths:
        tree = ET.fromstring(package.read(name))
        for cell in tree.findall(".//m:sheetData/m:row/m:c", NS):
            assert cell.attrib.get("t") != "e", (name, cell.attrib)
            if cell.find("m:f", NS) is not None:
                formula_count += 1
                assert cell.find("m:v", NS) is not None, (name, cell.attrib)
        validation_count += len(tree.findall("m:dataValidations/m:dataValidation", NS))
    assert formula_count > 3000 and validation_count == 2
    overview = ET.fromstring(package.read("xl/worksheets/sheet1.xml"))
    expected = {
        "C6": q["eligible_reports"],
        "C7": q["available_reports"] / q["eligible_reports"],
        "C8": q["successful_minutes"] / q["expected_minutes"],
        "C9": q["observed_days"],
        "C10": q["eligible_stations"],
    }
    for address, value in expected.items():
        actual = overview.find(f".//m:c[@r='{address}']/m:v", NS)
        assert actual is not None and abs(float(actual.text) - value) < 1e-10
    chart_count = sum("/charts/chart" in p and p.endswith(".xml") for p in paths)
    tables = [p for p in paths if p.startswith("xl/tables/table") and p.endswith(".xml")]
    assert chart_count == 2 and len(tables) == 8
    assert all(ET.fromstring(package.read(p)).find("m:autoFilter", NS) is not None for p in tables)

reader = PdfReader(PDF)
assert not reader.is_encrypted and len(reader.pages) == 6
texts = [page.extract_text() for page in reader.pages]
assert all(len(t) > 500 for t in texts)
assert "94.1%" in texts[0] and "3.4%" in texts[0]
assert "840,283" in texts[0] and "198,740" in texts[-1]
assert all(f"{i} / 6" in text for i, text in enumerate(texts, start=1))
notebook = json.loads(NOTEBOOK.read_text())
code = [c for c in notebook["cells"] if c["cell_type"] == "code"]
assert [c["execution_count"] for c in code] == list(range(1, len(code) + 1))
assert all(o["output_type"] != "error" for c in code for o in c["outputs"])
source_strings = ["".join(c["source"]) for c in code]
assert (
    hashlib.sha256(json.dumps(source_strings).encode()).hexdigest()
    == notebook["metadata"]["dockside"]["executed_code_sha256"]
)
assert (
    notebook["metadata"]["dockside"]["data_sha256"]
    == hashlib.sha256((HERE / "data/analysis.json").read_bytes()).hexdigest()
)
assert "<script" not in HTML.read_text().lower()
result = {
    "scope": "Saved XLSX/PDF structure, cached formula results and source count checks",
    "xlsx": {
        "sheets": sheets,
        "formula_cells": formula_count,
        "cached_formula_errors": 0,
        "charts": chart_count,
        "native_tables": len(tables),
        "dropdowns": validation_count,
        "station_selector_named_range": names["StationIDs"],
        "macros_external_links_and_connections": False,
        "native_excel_application_check": "Not verified: application did not respond",
    },
    "notebook": {
        "executed_code_cells": len(code),
        "execution_errors": 0,
        "code_and_data_hashes_verified": True,
        "offline_html_without_scripts": True,
    },
    "pdf": {
        "pages": len(texts),
        "format": "executed Jupyter notebook / nbconvert classic",
        "extractable_text_characters": [len(t) for t in texts],
    },
    "sha256": {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [XLSX, PDF, NOTEBOOK, HTML]
    },
}
(HERE / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
