from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Engine, text


@dataclass(frozen=True, slots=True)
class LiveHistoryReadiness:
    qualifying_days: int
    first_day: date | None
    last_day: date | None
    overall_poll_success_rate: float | None
    minimum_daily_attempt_rate: float | None
    accepted_station_record_rate: float | None
    ready_for_label_audit: bool
    blockers: tuple[str, ...]


def assess_live_history(engine: Engine, *, polls_per_day: int = 1440) -> LiveHistoryReadiness:
    with engine.connect() as connection:
        aggregate = connection.execute(
            text(
                """
                SELECT
                    min(scheduled_at::date) AS first_day,
                    max(scheduled_at::date) AS last_day,
                    count(DISTINCT scheduled_at::date) FILTER (
                      WHERE source.source_kind = 'live'
                    ) AS observed_days,
                    avg((batch.status = 'success')::integer) FILTER (
                      WHERE source.source_kind = 'live'
                    ) AS success_rate,
                    sum(batch.accepted_records) FILTER (
                      WHERE source.source_kind = 'live'
                    )::double precision
                      / NULLIF(sum(batch.expected_records) FILTER (
                          WHERE source.source_kind = 'live'
                        ), 0) AS station_record_rate
                FROM poll_batches batch
                JOIN source_datasets source ON source.id = batch.source_id
                """
            )
        ).mappings().one()
        minimum_daily = connection.scalar(
            text(
                """
                SELECT min(attempted::double precision / :polls_per_day)
                FROM (
                  SELECT scheduled_at::date, count(*) AS attempted
                  FROM poll_batches batch
                  JOIN source_datasets source ON source.id = batch.source_id
                  WHERE source.source_kind = 'live'
                  GROUP BY 1
                ) daily
                """
            ),
            {"polls_per_day": polls_per_day},
        )
    observed_days = int(aggregate["observed_days"] or 0)
    success_rate = (
        float(aggregate["success_rate"]) if aggregate["success_rate"] is not None else None
    )
    station_rate = (
        float(aggregate["station_record_rate"])
        if aggregate["station_record_rate"] is not None
        else None
    )
    daily_rate = float(minimum_daily) if minimum_daily is not None else None
    blockers: list[str] = []
    if observed_days < 84:
        blockers.append(f"qualifying_days={observed_days}; requires at least 84")
    if success_rate is None or success_rate < 0.95:
        blockers.append("overall successful-poll rate is below 95% or unavailable")
    if daily_rate is None or daily_rate < 0.90:
        blockers.append("at least one day has below 90% scheduled-poll coverage or is unavailable")
    if station_rate is None or station_rate < 0.98:
        blockers.append("accepted station-record coverage is below 98% or unavailable")
    return LiveHistoryReadiness(
        qualifying_days=observed_days,
        first_day=aggregate["first_day"],
        last_day=aggregate["last_day"],
        overall_poll_success_rate=success_rate,
        minimum_daily_attempt_rate=daily_rate,
        accepted_station_record_rate=station_rate,
        ready_for_label_audit=not blockers,
        blockers=tuple(blockers),
    )
