# Findings and publication record

**Edition:** 1.0.0, 2026-10-17. **Author:** Ian Lin.
**Status:** completed exploratory analysis of real collected observations;
forecast validation and rider recommendation evaluation remain pending.

## Executive conclusion

The collected reports identify locations worth monitoring more closely, but do
not establish month-long station reliability. Collection continuity is the most
important improvement before making broader operational recommendations.

In this frozen extract, **790,386 of 840,283 eligible reports (94.1%)** show at
least one usable dock. However, only **1,503 of 44,525 intended minute slots
(3.4%)** contain a successful poll. These measure different things. Neither is a
forecast accuracy or rider-success rate.

## 1. Coverage comes before interpretation

The window runs from September 16, 2026 at 18:55 UTC through October 17 at
17:00 UTC, exclusive. It contains 32 Toronto calendar dates, with partial first
and last dates. Only 11 dates have eligible reports; 21 have no attempted polls.
The longest absent-date span is September 23 through October 13.

| Measure | Observed count | Interpretation |
| --- | ---: | --- |
| Intended minute slots | 44,525 | Includes minutes when the collector did not run |
| Attempted slots | 1,747 | 3.9% of intended slots |
| Successful slots | 1,503 | 3.4% of intended slots |
| Partial slots | 203 | Valid records may still contribute observations |
| Failed slots | 41 | No successful poll in these recorded attempts |
| Retrieved live snapshot rows | 1,628,401 | Repeated station reports are still present here |
| Unique canonical station/report timestamps | 840,383 | Earliest canonical retrieval within the window |
| Eligible reports | 840,283 | Fresh, installed, accepting returns, known dock count |
| Eligible stations | 1,075 | Not an assertion about the current system size |

Missing intervals are not interpolated. This is a report-weighted analysis of
observed periods, not an estimate of the percentage of elapsed time docks were
available. Closely spaced reports and neighboring stations are correlated.

## 2. Some observed stations were full much more often

The support rule requires at least 100 eligible reports on at least five dates.
It admits 1,067 stations; the other eight remain visible in the workbook.
These are the first three stations by full-report share among supported stations:

| Station | ID | Full / eligible reports | Full share | Observed dates |
| --- | --- | ---: | ---: | ---: |
| Queen St E / Hammersmith Ave | 7315 | 443 / 782 | 56.6% | 11 |
| Ellis Ave / The Queensway | 7478 | 416 / 781 | 53.3% | 11 |
| 2300 Lakeshore Blvd W | 7471 | 404 / 788 | 51.3% | 11 |

**Action supported:** prioritize these locations for further observation and
compare them on well-covered, matched dates.
**Not supported:** naming Toronto's worst stations, estimating lost trips,
explaining rider demand, or recommending a rebalancing schedule from these data.

## 3. A simultaneous nearby option was sometimes available

For the ten highest supported full-share stations, select the nearest fresh,
operational neighbor within 750 m from the same fetched feed. Selection is by
distance, independently of its dock count. The first three stations above give:

| Full primary | Full reports | Neighbor matched | Neighbor with a dock | Share of matched | Mean distance |
| --- | ---: | ---: | ---: | ---: | ---: |
| 7315 | 443 | 442 | 219 | 49.5% | 255 m |
| 7478 | 416 | 416 | 262 | 63.0% | 313 m |
| 7471 | 404 | 404 | 400 | 99.0% | 352 m |

Station 7315 has one unmatched report, retained in the full-report denominator.
Neighbor identities can change across observations; see `data/nearby.csv` for
the observed names. These are straight-line distances and same-feed comparisons,
not exactly simultaneous physical measurements. Reports can be up to five minutes
old. A rider's later arrival, route and effect on inventory are not modeled.
These rates must not be presented as backup recommendation success.

## 4. Temporal views are exploratory

The workbook provides weekday/weekend and local-hour comparisons with report,
date and station counts. Chart cells require at least 100 reports across three
observed dates; the underlying table retains all cells. The notebook PDF shows
separate weekday/weekend panels; the workbook's chart follows its day-type selector.

Differences in collected dates and station mix can explain apparent hourly
patterns. No peak-period causal effect or statistically established weekday/weekend
difference is claimed. A useful next analysis would compare the same stations on
complete dates, then examine stability across independent weeks.

## 5. Quality checks and sensitivity

| Freshness limit | Eligible reports | Reports with a dock | Observed availability |
| --- | ---: | ---: | ---: |
| 60 seconds | 679,157 | 639,262 | 94.1% |
| 120 seconds | 823,378 | 774,530 | 94.1% |
| 300 seconds | 840,283 | 790,386 | 94.1% |

The rounded rate is stable under these freshness rules. That does **not** repair
the missing-time selection bias.

- 787,957 repeated canonical station/report timestamps were removed.
- 100 unique reports fell outside the permitted freshness window.
- 31,070 station/report timestamps contain conflicting status values across
  canonical retrievals. The primary rule keeps the first; excluding such
  timestamps yields 760,397 / 809,223, or **94.0%**.
- 198,740 quarantined records carry `future_last_reported`. Their cause is not
  established; investigate both collector and publisher timestamp evidence before
  assigning blame or changing the validation rule.
- One eligible report has invalid local coordinates; it is excluded from spatial
  pairing, not from nonspatial totals. 99 have unknown/zero capacity; one reports
  more docks than capacity. Reported dock availability remains authoritative.

Quality diagnostics can overlap and are not an additive exclusion waterfall.
No fabricated confidence interval treats hundreds of thousands of correlated
reports as independent trials.

## How to demonstrate the work

1. Open the PDF: explain the business question and coverage limitation first.
2. Open Excel **Overview**: change the amber station-ID cell and explain its
   formula-linked results. Use **Stations** filters to compare support and full share.
3. Change **Time patterns** between Weekday and Weekend. Explain why changing
   the mix can change the rate and why unsupported chart cells are omitted.
4. Show **Daily coverage** and **Source QA**: missing dates, freshness sensitivity,
   conflicts, quarantine reasons and three zero reconciliation residuals.
5. Walk through `sql/00_prepare.sql` and `sql/07_nearby.sql`: source-timestamp
   deduplication, knowledge cutoff, metadata history and nearest-neighbor matching.

This demonstrates SQL window functions and joins, defensible denominator design,
Excel formulas and controls, data-quality analysis, sensitivity checks, visual
communication and reproducible engineering. It is not yet evidence of predictive
model performance or a completed Power BI report.

## Verification and reproducibility

| Check | Evidence |
| --- | --- |
| Real extraction | SELECT-only, repeatable-read transaction; live provenance only; frozen configuration |
| Source trail | 1,706 distinct status payload hashes; ordered fetch/hash fingerprint and aggregate/SQL SHA-256 manifest |
| Aggregate checks | Station, date, hour and station-date totals reconcile; CSV/JSON/SQL hashes match |
| Database and application tests | 65 passed against disposable PostgreSQL 18.6; two upstream deprecation warnings |
| Notebook revision checks | 10 cells executed without errors; code/data hashes checked; 57 non-database tests passed, including the new executed-notebook regression test |
| Spreadsheet | Seven sheets, native tables/charts, formulas, two dropdown controls; recalculation and saved-container checks |
| Visual inspection | All seven sheet previews reviewed; PDF revised to an executed notebook export and all six pages inspected |
| Native Excel | Not verified: Microsoft Excel did not respond to the native-app check; no claim of an Excel UI test |
| Model/Power BI | Unvalidated / unverified; this release does not change those statuses |

See [verification.json](verification.json) for delivered-file hashes and structural
checks. The workbook was authored with `@oai/artifact-tool` 2.8.94; PDF generation
now executes the Jupyter notebook using nbclient and exports nbconvert classic HTML
through Chromium; the optional environment is hash-locked in `requirements-report.txt`.
Validation uses pypdf 6.10.0. The public aggregate files are
enough to regenerate this edition; raw feed evidence and credentials remain local.
The extraction manifest records the base Git commit at extraction; its separate
SQL hashes identify the new analysis code, which was not yet committed then.

### Notebook-format revision

At the user's request, the designed PDF was replaced with a cleaner notebook export:
visible Python cells, pandas output tables, matplotlib charts and plain-language
interpretation. The report now separates weekday/weekend panels; unsupported hours
are blank rather than zero. The original PDF pooled day types. Neither presentation
changes the data, aggregate metrics, support thresholds or analytical conclusions.
The Excel workbook and SQL extracts are unchanged.

## Next decisions

1. Improve collection continuity, disk monitoring and scheduled maintenance.
2. Investigate future-clock quarantines and same-timestamp status conflicts.
3. Repeat matched-station comparisons after sufficient well-covered weeks exist.
4. Keep forecast and replay evidence pending until the original readiness gates
   and untouched chronological evaluation can genuinely be satisfied.
