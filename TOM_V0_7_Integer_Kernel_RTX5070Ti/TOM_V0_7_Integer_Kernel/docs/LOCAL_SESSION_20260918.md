# Local execution and application exploration — 18 September 2026

**Historical first-session evidence.** The subsequent
[source-bound capacity study](V07_GPU_CAPACITY_RESULTS.md) adds distinct exhaustive
inputs, every-shard verification, all-shard counts/export and the final eight-kernel
machine-code audit. The measurements and implementation scope below describe the
earlier build and remain unchanged as historical evidence.

The kernel was built and executed on the NVIDIA GeForce RTX 5070 Ti Laptop GPU.
The final GPU validation suite passes on texture, global and shared backends.
A stateful event-admission application now demonstrates conditional commits,
rejection without state loss, replay detection and recovery.

## What this implementation is

Within a tick, expression dependencies form a directed acyclic graph (DAG).
The compiler schedules those expressions; state bindings carry recurrence between
ticks. This architecture was already present in the supplied package. The new
event demo uses it directly, and the compiler fix replaces recursive traversal
with iterative traversal while preserving the same order and compiled image.

The measurements validate this finite Boolean state machine and its editable
evaluator. They do not establish that a DAG is TOM's native representation or
that the implementation realizes unspecified native SDF dynamics. Calling the
stored definitions SDF declarations does not eliminate their dependency graph.
A requirement for execution without that representation would need a different,
explicit execution contract and independent validation.

## Reproduce the useful demonstration

From the package directory:

```powershell
cmake -S . -B build-cuda128 -G "Visual Studio 17 2022" -A x64 -T cuda=12.8 -DTOM_ENABLE_CUDA=ON -DTOM_CUDA_ARCH=120
cmake --build build-cuda128 --config Release --parallel
ctest --test-dir build-cuda128 -C Release --output-on-failure
python tools\make_event_demo.py --exe build-cuda128\Release\tom_cuda.exe --backend shared --out verification\event_admission_gpu.json
```

Edit `examples/event_admission_cases.json` to change the streams and proposals.
The runner preserves that input file. Edit `build_policy()` in
`tools/make_event_demo.py` to change the actual circuit and state-update policy.
See [the application guide](EVENT_DEMO.md) for the five checks and finite widths.

All three GPU backends and both evaluators matched the independent integer
policy and the full minterm-state oracle: **24 proposals, 17 accepted, 7 rejected**
per evaluator, followed by an idle tick that consumes no additional proposal.
Rejected proposals preserve the last accepted sequence, timestamp and fact mask.
The eight streams cover append, replay, regressed time, incorrect elapsed time,
future dependency claims, erased facts, combined failure/recovery and uint16 wrap.

This is a useful policy demonstration, not a durable ingestion service. Timestamps,
dependency claims and fact meanings come from supplied data. Eight streams are
too small to justify a GPU speed claim; process startup and transfers dominate
end-to-end use of this demonstration.

## Measured configuration tuning

Workload: unchanged `tom_conformance.tsdf`, 262,144 independent lanes, eight
measured ticks, two untimed in-process warmup ticks with exact state restoration,
five samples per configuration, rotated run order, no trace. Host timing includes
launches and completion and excludes allocation, initialization, verification and
result export. Eighteen configurations were measured on the final executable.

| Configuration | Block threads | Median total | Min–max |
|---|---:|---:|---:|
| Original default: texture / field | 128 | 3.5138 ms | 3.5110–3.5181 ms |
| Best measured texture / field | 64 | 3.4262 ms | 3.4193–3.4647 ms |
| Best measured global / field | 64 | 2.8459 ms | 2.8346–2.8498 ms |
| Best measured shared / field | 256 | 2.3070 ms | 2.3010–2.3140 ms |
| Best measured global / lowered | 64 | 1.6577 ms | 1.6546–1.6607 ms |
| Best measured shared / lowered | 256 | **0.9564 ms** | 0.9554–0.9599 ms |

Shared/field is **1.52×** faster than the original default for this workload.
Shared/lowered is **3.67×** faster. These gains select existing equivalent
execution modes; they are not a newly discovered algorithmic speedup.
Lowering requires the exact canonical stored kernel. Edited kernels are rejected
in lowered mode. Shared memory requires the entire image to fit its device limit.
Defaults remain texture/field; the measurements do not establish universal winners.

```powershell
.\build-cuda128\Release\tom_cuda.exe --program examples\tom_conformance.tsdf --lanes 262144 --ticks 8 --warmup 2 --backend shared --evaluator lowered --block 256 --verify
python tools\benchmark_laptop.py --exe build-cuda128\Release\tom_cuda.exe --lanes 262144 --ticks 8 --samples 5 --blocks 64,128,256 --warmup 2 --out verification\repeat_benchmark.json
```

### Experiment rejected

A source change replaced generic truth-table evaluation with direct selection
when the stored selector is 0xCA, while still reading the actual microprogram.
It passed correctness checks, but improved global/field only about 3–4%, slowed
texture/field about 1–2%, and slowed the fastest shared/field case about 4%.
It was **reverted**. The final `core.hpp` is byte-identical to the original.

The candidate source and executable are preserved as
`core_selector_candidate.hpp` and `tom_cuda_selector_candidate.exe` inside the
session evidence directory. `before_selector_benchmark.json` and
`after_selector_benchmark.json` record that experiment. The directory named
`optimized_validation/` belongs to the rejected candidate; `final_validation/`
belongs to the retained build. `baseline_cold_benchmark.json` is exploratory
cold-start evidence and is not used for the warm speedup claim.

## Fixes retained

- Explicitly select installed CUDA 12.8 in the Windows build script. Automatic
  Visual Studio selection initially chose a stale CUDA 12.9 integration.
  This machine's script-signing policy prevents running the unsigned PowerShell
  script directly; the native CMake commands above were executed instead.
  No execution-policy setting was changed.
- Rename `tools/inspect.py` to `tools/inspect_image.py`; its old name shadowed
  Python's standard `inspect` module and prevented the supplied tools from running.
- Compile deep circuits without Python recursion-limit failure. A 4,097-gate
  chain now compiles and executes; all existing example images retain their bytes.
- Reject unequal-width `Builder.mux_bits` operands instead of silently truncating.
- Add in-process benchmark warmup, exact state restoration, block-size sweeps,
  all samples and min/median/max, and executable/program SHA-256 identifiers.
- Audit actual PTX and SASS, entry coverage and instruction families separately.

## Validation and audit

| Check | Final result |
|---|---|
| CTest | 2/2 passing: C++ core and Python compiler regressions |
| Arbitrary microprogram operands and all 256 selectors | 4,096 randomized cases, independent minterm oracle |
| GPU ternary table/input fixture | 2,048 cases per evaluator and backend |
| GPU exact signed-int8 Arch fixture | 65,536 pairs per evaluator and backend |
| Temporal/retention certificate fixture | 518 cases per evaluator and backend |
| Generated programs / execution layouts | 48 / 96 per backend |
| Self-reference, edited selector, resume, invalid-input cases | Passing on all three backends |
| Whole kernel quotation | 896 bits exact on texture/global; shared skipped for capacity |
| Warmup, trace, resume, zero ticks | 42 GPU runs; 24 complete state-and-trace equality comparisons |
| Event application | Passing on all three backends, both evaluators |
| Compute Sanitizer memcheck | Six backend/evaluator combinations, zero errors |
| Compute Sanitizer racecheck / synccheck | Shared/field self-reference case, zero hazards/errors |
| PTX | Seven expected kernels present; no floating-type instructions |
| SASS | Seven expected kernels; 23 constant-zero HFMA2 instructions; no other floating instructions detected |

**Strict absence of floating opcodes is not established: it is false for this
compiled executable.** NVIDIA generated `HFMA2 Rn, -RZ, RZ, 0, 0` zero idioms.
The source and PTX use integer/Boolean computation; the SASS inventory found no
floating operations on input or state data. The audit intentionally reports
`sass_float_audit: REVIEW_REQUIRED` and exits 1, while its separately scoped
`data_computation_audit` passes. See `integer_audit_final.json` and its disassembly.
NVIDIA identifies HFMA2 in its [CUDA binary utilities instruction reference](https://docs.nvidia.com/cuda/cuda-binary-utilities/).

Large-batch `--verify` compares only the first 2,048 lanes of the first shard.
The independent fixture tests compare complete small outputs; these benchmarks
use one shard. This session does not validate later-shard offsets, near-capacity
allocation or long sustained thermal behavior. Sanitizer runs are bounded small
cases. Different compiled layouts may expose different addresses or scratch slots
through quotation, so reflective-program equivalence across layouts is conditional.

## Evidence and next application directions

Evidence lives in `verification/session_20260918/`. `final_benchmark.json` contains
all timings and hashes, `final_validation/summary.json` records the full GPU suite,
`runtime_options.json` records warmup checks, `event_admission_*.json` contains each
GPU application decision, and `sanitizer_summary.json` points to sanitizer logs.
The original `MANIFEST.sha256` identifies the delivered package and is retained;
it is not a manifest of this modified working tree. `session_manifest.json`
identifies the retained sources, executable and main evidence files.

Hardware: RTX 5070 Ti Laptop, compute capability 12.0, 46 SMs, 12,227 MiB reported
by nvidia-smi, driver 591.59, CUDA toolkit 12.8.61, MSVC 19.44, Python 3.13.11.
Final executable SHA-256:
`9a5fbe21c356fe72e78bd5d9875e78e1f68e090ca6651e190b77d3954407d9f9`.

| Direction | What the next demonstration would establish |
|---|---|
| Dependency existence | Require a bounded set of actual predecessor acknowledgements, beyond timestamp comparisons |
| Workflow policy comparison | Run the same event traces against several editable acceptance policies and expose differing decisions |
| Stateful protocol/game rules | Encode legal state transitions and test replay, rejection and recovery across independent sessions |
| Native TOM execution contract | Define the required operations and observables first, then determine whether the DAG representation is acceptable |

These are bounded next experiments, not already implemented capabilities.
