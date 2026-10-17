"""Run portfolio SQL in one read-only database snapshot; publish only aggregates."""

import csv
import hashlib
import io
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def export():
    cfg = json.loads((HERE / "config.json").read_text())
    bounds = [datetime.fromisoformat(cfg[k]) for k in ("start_utc", "end_utc_exclusive")]
    if cfg["poll_seconds"] != 60 or any(
        b.tzinfo is None or b.second or b.microsecond for b in bounds
    ):
        raise ValueError(
            "This SQL contract requires 60-second polls and timezone-aware minute bounds"
        )
    if bounds[1] <= bounds[0]:
        raise ValueError("The exclusive end must follow the start")
    parts = [
        "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;",
        "SET LOCAL timezone='UTC'; SET LOCAL statement_timeout='300s'; SET LOCAL work_mem='64MB';",
    ]
    prefix = (HERE / "sql/00_prepare.sql").read_text()
    queries = sorted((HERE / "sql").glob("*.sql"))[1:]
    aggregates = []
    for file in queries:
        query = file.read_text().rstrip().removesuffix(";")
        # Nest the analysis SELECT so its own WITH names can see the common CTEs.
        aggregates.append(
            f"'{file.stem[3:]}',(SELECT coalesce(json_agg(q),'[]'::json) FROM ({query}) q)"
        )
    parts.append(prefix + "\nSELECT json_build_object(" + ",\n".join(aggregates) + ");")
    parts.append("ROLLBACK;")
    cmd = [
        "python3",
        "scripts/manage.py",
        "compose",
        "exec",
        "-T",
        "db",
        "sh",
        "-c",
        'exec psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"',
        "sh",
    ]
    for k, v in cfg.items():
        cmd.extend(["-v", f"{k}={v}"])
    result = subprocess.run(cmd, input="\n".join(parts), text=True, cwd=ROOT, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    data = json.loads(result.stdout)
    output = HERE / "data"
    output.mkdir(exist_ok=True)
    hashes = {}
    for name, rows in data.items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
        path = output / f"{name}.csv"
        path.write_text(stream.getvalue())
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / "analysis.json").write_text(json.dumps(data, indent=2) + "\n")
    manifest = {
        "configuration": cfg,
        "extracted_at_utc": datetime.now(UTC).isoformat(),
        "source_kind": "live",
        "snapshot_table": "station_snapshots",
        "transaction": "REPEATABLE READ READ ONLY; common CTEs; rollback",
        "git_commit_at_extraction": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "csv_sha256": hashes,
        "analysis_json_sha256": hashlib.sha256((output / "analysis.json").read_bytes()).hexdigest(),
        "sql_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((HERE / "sql").glob("*.sql"))
        },
        "source_url": "https://toronto.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json",
        "attribution": "Contains information licensed under the Open Government Licence - Toronto.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(data["quality"][0], indent=2))


if __name__ == "__main__":
    export()
