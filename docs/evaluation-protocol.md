# Frozen historical request replay protocol

Status: draft implementation contract; it must be hashed/frozen before final-test
access. Seed is `20260907`.

- Select 250 destinations from station coordinates known before validation using
  deterministic uniform station sampling plus a 0–150 m seeded offset.
- Replay every 30 minutes for all 5/10/15/30-minute horizons and 750 m radius.
- Give all policies identical point-in-time station, metadata, freshness,
  geographical and generic-bicycle eligibility evidence.
- Compare `nearest_operational_v1`, `nearest_current_dock_v1`,
  `current_buffer_distance_v1`, and `forecast_distance_v1`.
- Select distance penalties only on policy-selection data from
  `{0, .05, .10, .20, .30}`. Require at least 95% recommendation coverage and no
  more than 200 m median extra distance versus nearest operational.
- Primary success is a known positive future label at the selected station. The
  alternative is evaluated only at the original ETA—not after a failed primary.
- End-to-end success divides successes by all otherwise evaluable requests;
  abstentions and missing outcomes do not become success. Conditional success and
  coverage are reported alongside it.
- Paired uplift uses only matched cases where all compared outcomes are known and
  explicitly states complete-case counts.
- Report all numerators/denominators, abstentions, unknown outcomes, exclusions,
  horizon, peak/off-peak (Toronto weekdays 07–10 and 16–19), scarcity (at least
  half of candidates currently full), distance, and extra distance.
- Day-block bootstrap 95% intervals use 2,000 resamples. Adjacent observations are
  never treated as independent riders.

Offline replay is hypothetical. It assumes a recommendation would not change the
recorded inventory and is not presented as a live rider trial.
