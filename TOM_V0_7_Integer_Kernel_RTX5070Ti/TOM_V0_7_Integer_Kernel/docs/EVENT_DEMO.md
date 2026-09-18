# Stateful event admission demonstration

This example turns the existing finite bit-circuit evaluator into a small,
editable event-processing policy. It is useful as a starting point for ordered
event ingestion, deterministic replay validation, or checks on a bounded
workflow's claimed progress. Each packed lane owns an independent history.

Each proposal supplies a 16-bit sequence, timestamp, elapsed-time claim and
latest-dependency timestamp, plus an 8-bit proposed fact mask. The kernel accepts
the proposal only when all five checks pass:

| Output | Exact policy |
| --- | --- |
| `sequence_forward` | Proposed sequence is greater than the last accepted sequence. Gaps are allowed. |
| `time_forward` | Proposed timestamp is greater than the last accepted timestamp. |
| `elapsed_exact` | Claimed elapsed equals proposed timestamp minus last accepted timestamp, without uint16 wraparound. |
| `dependency_not_future` | Claimed latest dependency timestamp is no later than the proposed timestamp. |
| `facts_retained` | Every previously accepted fact bit remains set in the proposed mask. |

`accepted` additionally requires a fresh host submission. The TOM `next` bindings
commit the new sequence, timestamp and fact mask together when accepted. A failed
proposal leaves that accepted state unchanged. The submission flag is consumed
at each tick, so an idle tick cannot admit an event again.

The included fixture has eight streams and three submissions each: valid append,
replayed sequence, backward time, wrong elapsed, future dependency, fact erasure,
combined failure followed by recovery, and the uint16 upper boundary. Expected
results are **17 accepted and 7 rejected** per evaluator. The last boundary
proposal wraps to zero and must be rejected. There are 24 meaningful submissions;
the packed allocation has 32 lanes, with inactive padding lanes.

## Run and edit

From the project directory in PowerShell:

```powershell
python tools\make_event_demo.py --exe build-cuda128\Release\tom_cpu.exe
```

This generates `examples/event_admission.json`, `.tsdf` and `.map.json`, prints
each proposal's five check results, and saves the detailed report to
`verification/event_admission_cpu.json`. Both field and lowered evaluators run
three resumed submission ticks plus an idle tick. Every result is checked with
ordinary Python integer comparisons; the entire state is also compared with the
independent minterm evaluator. Rejection/recovery checks establish that rejected
proposals do not silently change the persistent history.

For the actual GPU executable:

```powershell
python tools\make_event_demo.py --exe build-cuda128\Release\tom_cuda.exe --backend texture --out verification\event_admission_gpu.json
```

The tiny demonstration is for behavior and inspectability. GPU launch, process
startup and host submission overhead dominate this workload; this command is
not evidence of an application speedup. Independent streams can be added to
`examples/event_admission_cases.json` to explore larger batches. All streams must
have the same number of submissions. This fixture is only created when absent,
so running the script preserves edits to the events. Optional per-stream
`expected_acceptance` arrays catch accidental changes to intended outcomes.

Edit `build_policy()` in `tools/make_event_demo.py` to regenerate the policy.
The generated JSON is also an editable circuit definition; compile a customized
copy with `tools/compile.py`. Running the generator overwrites its own policy JSON.
The 17-bit elapsed subtraction is deliberate: a negative difference must not
match a wrapped unsigned claim.

## Meaning and limits

Timestamps and fact meanings are host-supplied assertions. Passing this policy
does not authenticate a clock, establish physical causality, prove that a
dependency exists, or prove that a fact is true. The fact mask encodes a bounded
set of workflow flags; retaining its bits is not retention of arbitrary payload
bytes. The sample legend names these flags in the cases JSON.

This is an unsigned finite policy with no automatic sequence/time rollover.
Wider counters or an explicit rollover protocol would be needed for longer
histories. Each lane tracks one ordered stream; cross-stream dependencies are
not resolved. The host may initialize state and submits event fields between
ticks; no untrusted-ingestion or durable-storage system is supplied. The kernel
itself performs checks and conditional state updates, and interpreter epochs
count execution ticks rather than wall-clock time.
