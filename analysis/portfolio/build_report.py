"""Render the five-page case study from the frozen SQL aggregate export."""

import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = json.loads((HERE / "data/analysis.json").read_text())
Q = DATA["quality"][0]
OUT = ROOT / "output/pdf/Dockside_Case_Study.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)
W, H = 612, 792
INK = colors.HexColor("#173B32")
GREEN = colors.HexColor("#287D65")
MUTED = colors.HexColor("#5F7068")
GOLD = colors.HexColor("#B47024")
PALE = colors.HexColor("#EDF3EF")
c = canvas.Canvas(str(OUT), pagesize=(W, H))
c.setTitle("Dockside: Where is returning a bicycle difficult?")
c.setAuthor("Ian Lin")
c.setSubject("Exploratory analysis of self-collected Toronto dock availability")


def text(x, y, value, size=10, color=INK, bold=False):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, str(value))


def para(x, y, value, width=516, size=11, color=INK):
    p = Paragraph(
        value,
        ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=size,
            leading=size * 1.45,
            textColor=color,
            spaceAfter=0,
        ),
    )
    _, height = p.wrap(width, 700)
    p.drawOn(c, x, y - height)
    return y - height


def page(number, title, subtitle):
    c.setFillColor(colors.white)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    text(48, 753, "DOCKSIDE", 11, bold=True)
    text(373, 753, "ANALYTICAL CASE STUDY / 2026", 9, MUTED)
    c.setStrokeColor(GREEN)
    c.line(48, 738, 564, 738)
    text(48, 704, title, 24, bold=True)
    para(48, 685, subtitle, size=10, color=MUTED)
    text(48, 30, "Ian Lin | Exploratory evidence, not a validated forecast", 9, MUTED)
    text(540, 30, f"{number} / 5", 9, MUTED)


def finish():
    c.showPage()


def table(top, headers, rows, widths):
    style = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=12, textColor=INK)
    hstyle = ParagraphStyle(
        "header", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.white
    )
    cells = [[Paragraph(escape(str(v)), hstyle) for v in headers]]
    cells += [[Paragraph(escape(str(v)), style) for v in row] for row in rows]
    t = Table(cells, colWidths=widths, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#CEDAD2")),
            ]
        )
    )
    _, height = t.wrap(516, 650)
    t.drawOn(c, 48, top - height)
    return top - height


def barplot(x, y, w, h, labels, values, title, percent=True):
    text(x, y + h + 22, title, 12, bold=True)
    maximum = 1 if percent else max(values or [1])
    for tick in range(5):
        value = maximum * tick / 4
        yy = y + h * tick / 4
        c.setStrokeColor(colors.HexColor("#E1E8E3"))
        c.line(x, yy, x + w, yy)
        text(x - 32, yy - 3, f"{value:.0%}" if percent else f"{value:g}", 8, MUTED)
    step = w / len(labels)
    for i, (label, value) in enumerate(zip(labels, values, strict=True)):
        c.setFillColor(GREEN)
        c.rect(x + i * step + 2, y, max(2, step - 4), h * value / maximum, fill=1, stroke=0)
        if len(labels) < 15 or i % 4 == 0 or i == len(labels) - 1:
            text(x + i * step, y - 16, label, 8, MUTED)


def pct(x):
    return f"{x:.1%}"


coverage = Q["successful_minutes"] / Q["expected_minutes"]
availability = Q["available_reports"] / Q["eligible_reports"]
ranked = sorted(
    [r for r in DATA["stations"] if r["ranking_eligible"]],
    key=lambda r: (-r["full_rate"], r["station_id"]),
)
daily = DATA["daily"]
no_days = sum(r["attempted_minutes"] == 0 for r in daily)
repeats = Q["canonical_rows"] - Q["missing_report_time"] - Q["unique_reports"]

page(
    1,
    "Where is returning a bike difficult?",
    "Toronto dock availability | September 16 - October 17, 2026 | Analysis version 1.0.0",
)
para(
    48,
    637,
    "<b>Decision:</b> identify observed return-pressure locations and investigate nearby alternatives. "
    "The evidence supports a targeted exploratory analysis, not a citywide service guarantee.",
    size=13,
)
for x, value, label in [
    (48, pct(availability), "Observed dock availability"),
    (224, pct(coverage), "Successful poll coverage"),
    (400, str(Q["observed_days"]), "Dates with eligible reports"),
]:
    text(x, 531, value, 32, bold=True)
    text(x, 510, label, 9, MUTED)
text(48, 463, "What the evidence says", 15, bold=True)
y = 435
for title, body in [
    (
        "Coverage is the main constraint.",
        f"{Q['successful_minutes']:,} successful minute slots out of {Q['expected_minutes']:,} expected. "
        f"{no_days} local dates have no attempted polls. Large report counts do not compensate for missing time.",
    ),
    (
        "Availability varies across observed stations.",
        f"{Q['eligible_reports']:,} fresh, unique, operational reports cover {Q['eligible_stations']:,} stations. "
        f"The highest observed full rate among supported stations is {pct(ranked[0]['full_rate'])} at {escape(ranked[0]['name'])}.",
    ),
    (
        "Nearby alternatives deserve investigation.",
        "Same-feed neighboring stations are compared while selected stations are full. "
        "This describes a simultaneous option, not the chance of finding a dock after traveling there.",
    ),
]:
    text(48, y, title, 12, bold=True)
    y = para(48, y - 13, body, size=11) - 28
para(
    48,
    142,
    "<b>Recommended action:</b> improve collector continuity first. Use live freshness-aware recommendations for actual trips; "
    "use this case study to prioritize which locations and hours to monitor next.",
    size=11,
)
finish()

page(
    2,
    "Coverage before conclusions",
    "Collection completeness and report-level quality are separate measures.",
)
barplot(
    82,
    445,
    474,
    130,
    [r["local_date"][5:] for r in daily],
    [r["successful_minutes"] / r["expected_minutes"] for r in daily],
    "Successful polls / expected minute slots",
)
para(
    48,
    408,
    "The chart includes dates with no collection. September 16 starts at 14:55 and October 17 ends at 13:00 Toronto time. "
    "All other dates use complete local-day denominators. A successful poll is a collector outcome, not a rider outcome.",
    size=10,
)
rows = [
    ["Retrieved live snapshots", f"{Q['raw_rows']:,}"],
    ["Unique canonical station timestamps", f"{Q['unique_reports']:,}"],
    ["Repeated canonical timestamps removed", f"{repeats:,}"],
    ["Unique reports outside freshness window", f"{Q['stale_unique_reports']:,}"],
    ["Eligible fresh operational reports", f"{Q['eligible_reports']:,}"],
    [
        "Conflicting station/report timestamps (diagnostic)",
        f"{Q['conflicting_report_timestamps']:,}",
    ],
    ["Quarantined records: future last_reported", f"{Q['quarantined_records']:,}"],
]
bottom = table(348, ["Quality stage or diagnostic", "Records"], rows, [380, 136])
conf = DATA["conflict_sensitivity"][0]
para(
    48,
    bottom - 16,
    f"Excluding conflicting timestamps gives {pct(conf['available_reports'] / conf['reports'])} availability "
    f"over {conf['reports']:,} reports. Quarantined future clocks and conflicts warrant investigation; "
    "their causes are not established. Diagnostic counts are not an additive waterfall.",
    size=9,
)
finish()

page(
    3,
    "Where full docks were observed",
    "Stations are compared only within the available collection periods.",
)
para(
    48,
    637,
    "The following stations have the largest observed full-report shares among stations with at least "
    "<b>100 eligible reports on 5 distinct dates</b>. This support rule is fixed for this exploratory release; "
    "it does not establish long-term reliability.",
    size=11,
)
rows = [
    [r["name"], r["station_id"], f"{r['reports']:,}", str(r["observed_days"]), pct(r["full_rate"])]
    for r in ranked[:6]
]
bottom = table(
    560, ["Station", "ID", "Reports", "Dates", "Full share"], rows, [272, 50, 70, 47, 77]
)
text(48, bottom - 34, "How to read the ranking", 13, bold=True)
para(
    48,
    bottom - 52,
    "Full share = unique fresh operational reports with zero reported docks / all eligible reports for that station. "
    "The name is the last observed eligible name in the study window. Coordinates and capacity are joined through the "
    "metadata version stored with each snapshot.",
    size=11,
)
para(
    48,
    bottom - 131,
    f"{len(ranked):,} of {Q['eligible_stations']:,} stations meet the support rule. All stations remain in the workbook, "
    "including low-support rows. Compare report counts and observed dates before interpreting small differences. "
    "Do not call this a ranking of Toronto's worst stations or infer unmet trip demand.",
    size=11,
)
finish()

page(
    4,
    "When, and what is nearby?",
    "Patterns in observations suggest follow-up questions, not causal explanations.",
)
hours = []
for hour in range(24):
    subset = [r for r in DATA["time_patterns"] if r["local_hour"] == hour]
    total = sum(r["reports"] for r in subset)
    dates = sum(r["observed_days"] for r in subset)
    hours.append(
        sum(r["available_reports"] for r in subset) / total if total >= 100 and dates >= 3 else None
    )
observed = [(h, v) for h, v in enumerate(hours) if v is not None]
barplot(
    82,
    428,
    474,
    162,
    [str(h) for h, v in observed],
    [v for h, v in observed],
    "Observed availability by Toronto local hour",
)
para(
    48,
    389,
    "Hours pool the reports actually collected, with different dates and station mixes. "
    "The workbook separates weekdays/weekends and shows report counts and distinct dates. "
    "The chart omits hours with fewer than 100 reports or 3 observed dates; all cells remain in the workbook.",
    size=10,
)
text(48, 326, "Nearest same-feed alternative for selected full stations", 12, bold=True)
nearby_by_id = {r["station_id"]: r for r in DATA["nearby"]}
rows = []
for station in ranked[:3]:
    r = nearby_by_id.get(station["station_id"])
    if r:
        rows.append(
            [
                station["station_id"],
                str(r["full_reports"]),
                str(r["matched_reports"]),
                str(r["nearby_available_reports"]),
                pct(r["nearby_available_reports"] / r["matched_reports"])
                if r["matched_reports"]
                else "n.a.",
                f"{r['mean_distance_m']:.0f}" if r["mean_distance_m"] is not None else "n.a.",
            ]
        )
bottom = table(
    308,
    ["Station ID", "Full reports", "Matched", "With dock", "Share of matched", "Mean metres"],
    rows,
    [76, 85, 80, 80, 105, 90],
)
para(
    48,
    bottom - 18,
    "The nearest fresh operational neighbor within 750 m is selected independently of its dock count. "
    "Distance is straight-line, not a route. Unmatched reports are disclosed. The alternative may change across observations. "
    "Neither travel delay nor dock reservations are modeled.",
    size=10,
)
sens = DATA["sensitivity"]
s60 = next(r for r in sens if r["fresh_seconds"] == 60)
para(
    48,
    115,
    f"<b>Sensitivity:</b> a 60-second freshness limit yields {pct(s60['available_reports'] / s60['reports'])} availability "
    f"over {s60['reports']:,} reports, versus {pct(availability)} over {Q['eligible_reports']:,} at 300 seconds. "
    "Freshness sensitivity does not remove collection-selection bias.",
    size=10,
)
finish()

page(
    5,
    "Methods, limits and next steps",
    "A reproducible analytical foundation, with a clearly bounded interpretation.",
)
text(48, 635, "Reproduce the evidence", 13, bold=True)
para(
    48,
    616,
    "The repository contains versioned SQL, configuration, aggregate CSV/JSON exports, an extraction manifest "
    "with hashes, automated reconciliation tests, the Excel builder and this PDF builder. The SQL runs in a "
    "repeatable-read, read-only transaction. The frozen exports let readers rebuild the artifacts without private database access.",
    size=11,
)
text(48, 528, "What this analysis does not establish", 13, bold=True)
para(
    48,
    509,
    "The collector was not continuously online. Missing time is nonrandom and cannot be repaired by interpolation. "
    "One station report timestamp is counted once; this can weight stations with more frequent source updates more heavily. "
    "Reported inventory changes do not identify individual pickups, returns or rebalancing. Generic bicycle compatibility "
    "is assumed. There is no seasonal generalization, live rider trial, validated forecast, or measured 82% / +14 pp result.",
    size=11,
)
text(48, 389, "Recommended next steps", 13, bold=True)
para(
    48,
    370,
    "<b>1. Collection:</b> maintain continuous operation and monitor daily completeness before drawing broader patterns.<br/>"
    "<b>2. Analysis:</b> repeat station/hour comparisons on well-covered, matched dates; assess stability across weeks.<br/>"
    "<b>3. Evaluation:</b> freeze a historical request-replay protocol and compare simple policies before training a forecast model.",
    size=11,
)
text(48, 263, "Sources and attribution", 13, bold=True)
para(
    48,
    244,
    "Self-collected Bike Share Toronto GBFS v3 station-information and station-status observations. "
    "Source clocks are distinct from retrieval and ingestion clocks. Raw data and credentials are not published.<br/><br/>"
    "Contains information licensed under the Open Government Licence - Toronto. Independent portfolio project; "
    "no City of Toronto or Bike Share Toronto endorsement. The recorded catalogue/directory licensing discrepancy remains documented.",
    size=10,
)
links = [
    (
        "Repository and reproducible analysis",
        "https://github.com/ianlin1222/toronto-bike-share-dashboard/tree/main/analysis/portfolio",
    ),
    ("GBFS v3 specification (accessed 2026-10-17)", "https://gbfs.org/documentation/reference/"),
    (
        "Open Government Licence - Toronto (accessed 2026-10-17)",
        "https://www.toronto.ca/city-government/data-research-maps/open-data/open-data-licence/",
    ),
]
for i, (label, url) in enumerate(links):
    y = 121 - i * 20
    text(48, y, label, 9, GREEN)
    c.linkURL(url, (48, y - 3, 564, y + 10), relative=0)
finish()
c.save()
print(OUT)
