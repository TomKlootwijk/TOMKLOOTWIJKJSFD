# Executed validation status

This document records the **original delivery**. Actual RTX 5070 Ti Laptop
execution is now documented in [the 18 September local session](LOCAL_SESSION_20260918.md)
with separate evidence under `verification/session_20260918/`.

This is the finite implementation K1 of TOM V0.7. CPU tests executed; no CUDA compiler or NVIDIA GPU was available in the delivery environment.

## Results

| Check | Executed result |
|---|---:|
| All ternary tables and their inputs, each evaluator | 2,048 / PASS |
| Signed 8-bit Arch input pairs, each evaluator | 65,536 / PASS |
| Temporal and retention certificates, each evaluator | 518 / PASS |
| Complete operational-kernel quotation | 896 bits / exact |
| Edited-kernel cases | 2,048 / PASS; 1,024 changed outputs |
| Self-reference epoch configurations per evaluator | 5 / PASS |
| Generated rule programs | 48 / PASS |
| Recycled/unrecycled random program executions | 96 / PASS |
| Invalid binary, native-rule and epoch cases | 7 / rejected |
| Shared bootstrap truth-table lane assertions | 8,192 / PASS |
| Random dynamic coefficient words | 4,096 / PASS |
| Stored kernel body vs lowered equation | 4,096 / PASS |
| CPU AddressSanitizer / UndefinedBehaviorSanitizer | PASS |
| CUDA compilation | NOT RUN: toolkit unavailable |
| CUDA execution | NOT RUN: no NVIDIA GPU |

Both the default field-defined interpreter and the verified lowered implementation were tested. Counts are test cases, not independent native TOM constituents or physical experiments.

## Why this validates more than a zero residual

The included baseline and four temporally/retentionally invalid certificates all have neutral Arch readings. Only the baseline passes the temporal/retention conjunction. A sixth case preserves temporal requirements but has nonneutral Arch. The program keeps each input witness and each separate decision bit.

## Self-reference evidence

The operative kernel is actually read from its field image. Changing its selector-table byte from 0xCA to 0xAC changes 1,024 of the 2,048 outputs in the exhaustive rule/input fixture. The lowered execution mode rejects this changed kernel. The kernel-selfcopy program quotes all 28 microprogram words, and publication reconstructs the target image byte-for-byte.

## Timing

Raw CPU run timing in JSON is measured but not presented as RTX performance. Use `benchmark_laptop.py` after on-device validation. No claims about cache residency or a performance advantage are substituted for that measurement.

## Evidence files

`cpu_validation.json`, `core_tests.json`, `sanitized_validation.json`, `core_sanitized.json`, `certificate_readout.json`, `self_reference_trace.json`, `kernel_publication.json`, `integer_audit.json` and `environment.json` contain the actual results and scope.
