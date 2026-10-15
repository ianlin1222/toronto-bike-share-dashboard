# Model card — pending live validation

Status: **no approved model**. The code can create a non-approvable fixture artifact
to test serialization, but fixture metrics are not Toronto performance evidence and
the API refuses to return their probabilities.

The intended target is the probability that a station is installed, accepting
returns, and reports at least one usable dock at the common arrival horizon. A
future label uses the first canonical snapshot retrieved at or after arrival and no
later than 90 seconds afterward. The report must be no more than five minutes old
at retrieval and no more than 30 seconds in the future. Absent/stale/incomplete
future evidence produces an unknown label.

The first comparison is pooled logistic regression versus histogram gradient
boosting. Global chronological folds are 49/7/7/7/14 days for training, model
validation, sigmoid calibration, policy selection, and untouched test. Every fold
has a 30-minute embargo and labels crossing a boundary are purged. Preprocessing,
feature choice, calibration, and ranking penalties may not use the final test.

Feature families and limitations are detailed in `feature-contract.md`. The model
does not observe individual pickups/returns; inventory change also reflects
rebalancing, disabled equipment and unobserved intermediate activity. A forecast
does not reserve a dock. Twelve weeks does not establish seasonal generalization.
