# aTOMos Gate

A compact universal state-transition firewall applied through the same admission relation to workflow/file updates, sensor/benchmark events, biological stages, and document/provenance revisions.

Replay digest: `53d2fc80ee1d895033e22ef8c7ae8083c8552db5ebf6890f42a805b841c27e98`

## Core relation

AB accepts only when the proposal is fresh, strictly advances sequence and time, has exact elapsed time, does not depend on the future, does not erase retained facts, belongs to the stream, and stays within the declared 16-bit bound.

Accepted updates commit atomically and emit a transient relation. Rejected updates leave the core state unchanged and set only bounded reason bits in negative memory W.

## Fixtures

| Case | Decision | Reasons | Four adapters agree |
|---|---|---|---|
| valid_append | accept | - | yes |
| replay | reject | stale_sequence, backward_time, wrong_elapsed | yes |
| backward_time | reject | backward_time | yes |
| wrong_elapsed | reject | wrong_elapsed | yes |
| future_dependency | reject | future_dependency | yes |
| fact_erasure | reject | fact_erasure | yes |
| not_fresh | reject | not_fresh | yes |
| u16_overflow | reject | u16_overflow | yes |
| wrong_stream | reject | wrong_stream | yes |
| recovery_after_reject | accept | - | yes |

## Local measurement

10,000 sequential admissions; 10,000 accepted; median gate latency 1300 ns in this Python run.

Rejected-core preservation: `True`; final bounded W mask: `255`.

This is a useful safety and consistency primitive, not cryptographic authentication and not proof of physical universality. The same contract is portable; the adapters remain explicit.
