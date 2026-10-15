from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import uvicorn

from bikeshare.config import get_settings
from bikeshare.db.repository import IngestionRepository
from bikeshare.db.session import get_engine
from bikeshare.ingestion.collector import Collector
from bikeshare.ingestion.service import IngestionService
from bikeshare.logging import configure_logging


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bikeshare")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("ingest-once", help="fetch and persist one full live GBFS batch")
    subparsers.add_parser("collect", help="run the restartable collector")
    subparsers.add_parser("data-audit", help="print collection coverage and database size")
    subparsers.add_parser("data-readiness", help="evaluate live-history readiness gates")
    subparsers.add_parser("refresh-summaries", help="refresh bounded reporting aggregates")
    dashboard = subparsers.add_parser('dashboard-backfill', help='aggregate retained real snapshots for the dashboard')
    dashboard.add_argument('--days', type=int, choices=range(1, 366), default=31)
    subparsers.add_parser("ensure-partitions", help="create current and next monthly partitions")
    archive = subparsers.add_parser("archive", help="export and verify expired history")
    archive.add_argument("--snapshot-cutoff-days", type=int, default=14)
    archive.add_argument("--raw-cutoff-days", type=int, default=7)
    archive.add_argument("--output", type=Path, default=Path("var/archive"))
    archive.add_argument("--delete-after-verify", action="store_true")
    subparsers.add_parser("serve", help="run the local API")
    train = subparsers.add_parser("train", help="run a gated one-off training job")
    train.add_argument("--dataset", choices=("fixture", "live"), default="fixture")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    result: dict[str, Any] | None = None
    if args.command == "ingest-once":
        engine = get_engine()
        repository = IngestionRepository(engine)
        result = IngestionService(settings, repository).ingest_once(include_metadata=True)
    elif args.command == "collect":
        engine = get_engine()
        repository = IngestionRepository(engine)
        Collector(settings, repository, engine).run()
    elif args.command == "data-audit":
        repository = IngestionRepository(get_engine())
        result = repository.data_audit()
    elif args.command == "data-readiness":
        from dataclasses import asdict

        from bikeshare.modeling.readiness import assess_live_history

        result = asdict(assess_live_history(get_engine()))
    elif args.command == "refresh-summaries":
        from bikeshare.ingestion.summaries import refresh_reporting_summaries

        result = refresh_reporting_summaries(get_engine())
    elif args.command == "ensure-partitions":
        from bikeshare.ingestion.archive import ensure_monthly_partitions

        result = {"partitions": ensure_monthly_partitions(get_engine())}
    elif args.command == 'dashboard-backfill':
        from bikeshare.ingestion.dashboard import refresh_dashboard_hours

        now = datetime.now(UTC)
        result = {'dashboard_rows': refresh_dashboard_hours(
            get_engine(), now=now, since=now-timedelta(days=args.days)),
            'note': 'Retained snapshots only; absent history is not reconstructed.'}
    elif args.command == "archive":
        from bikeshare.ingestion.archive import archive_history

        now = datetime.now(tz=UTC)
        result = archive_history(
            get_engine(),
            output_root=args.output,
            snapshot_cutoff=now - timedelta(days=args.snapshot_cutoff_days),
            raw_cutoff=now - timedelta(days=args.raw_cutoff_days),
            delete_after_verify=args.delete_after_verify,
        )
    elif args.command == "serve":
        uvicorn.run(
            "bikeshare.api.main:app",
            host=settings.bind_host,
            port=settings.bind_port,
        )
    elif args.command == "train":
        from bikeshare.modeling.training import train

        result = train(dataset=args.dataset, settings=settings)
    if result is not None:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
