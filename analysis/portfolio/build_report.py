"""Execute the actual notebook, export nbconvert HTML, then print it to PDF."""

import argparse
import hashlib
import json
import os
from pathlib import Path

import nbformat
from bs4 import BeautifulSoup
from nbclient import NotebookClient
from nbconvert import HTMLExporter
from nbconvert.preprocessors import TagRemovePreprocessor
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NOTEBOOK = HERE / "Dockside_Case_Study.ipynb"
HTML = ROOT / "output/notebook/Dockside_Case_Study.html"
PDF = ROOT / "output/pdf/Dockside_Case_Study.pdf"


def build(browser_path=None):
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(notebook)
    NotebookClient(
        notebook,
        timeout=120,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
        record_timing=False,
    ).execute()
    code_cells = [c for c in notebook.cells if c.cell_type == "code"]
    assert all(
        c.execution_count and not any(o.output_type == "error" for o in c.outputs)
        for c in code_cells
    )
    notebook.metadata["dockside"] = {
        "data_sha256": hashlib.sha256((HERE / "data/analysis.json").read_bytes()).hexdigest(),
        "executed_code_sha256": hashlib.sha256(
            json.dumps([c.source for c in code_cells]).encode()
        ).hexdigest(),
    }
    hidden_inputs = {"load-verify", "coverage-table", "station-chart", "freshness-results", "quality-results"}
    for cell in code_cells:
        cell.metadata["tags"] = ["report-hide-input"] if cell.id in hidden_inputs else []
    nbformat.write(notebook, NOTEBOOK)
    exporter = HTMLExporter(template_name="classic")
    exporter.exclude_input_prompt = False
    exporter.exclude_output_prompt = False
    exporter.mathjax_url = ""
    exporter.require_js_url = ""
    exporter.register_preprocessor(
        TagRemovePreprocessor(remove_input_tags={"report-hide-input"}), enabled=True
    )
    body, _ = exporter.from_notebook_node(notebook)
    # Static output needs no CDN scripts; the saved HTML is usable offline.
    soup = BeautifulSoup(body, "html.parser")
    for script in soup.find_all("script"):
        script.decompose()
    body = str(soup)
    css = (HERE / "notebook_print.css").read_text()
    body = body.replace("</head>", f"<style>{css}</style></head>")
    body = "\n".join(line.rstrip() for line in body.splitlines()) + "\n"
    HTML.parent.mkdir(parents=True, exist_ok=True)
    PDF.parent.mkdir(parents=True, exist_ok=True)
    HTML.write_text(body)
    with sync_playwright() as p:
        launch = {"headless": True}
        if browser_path:
            launch["executable_path"] = browser_path
        browser = p.chromium.launch(**launch)
        page = browser.new_page(viewport={"width": 1050, "height": 1100})
        # A local artifact render, never a network-connected browser session.
        page.route("http://**/*", lambda route: route.abort())
        page.route("https://**/*", lambda route: route.abort())
        page.goto(HTML.as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        page.emulate_media(media="print")
        page.pdf(
            path=str(PDF),
            format="A4",
            print_background=True,
            margin={"top": "17mm", "bottom": "17mm", "left": "14mm", "right": "14mm"},
            display_header_footer=True,
            header_template='<div style="font:8px Arial;width:100%;text-align:center;color:#777">'
            "DOCKSIDE | EXPLORATORY NOTEBOOK | REAL COLLECTED DATA</div>",
            footer_template='<div style="font:8px Arial;width:100%;text-align:center;color:#777">'
            '<span class="pageNumber"></span> / '
            '<span class="totalPages"></span></div>',
        )
        browser.close()
    print(f"Executed {len(code_cells)} code cells; exported notebook, HTML and PDF.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--browser-path",
        default=os.getenv("NOTEBOOK_CHROMIUM_PATH"),
        help="Optional installed Chrome/Chromium executable; otherwise Playwright Chromium",
    )
    build(parser.parse_args().browser_path)
