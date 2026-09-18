# TOM v0.7 native execution — 18 September 2026

The current `tom_native_cpu.exe` and `tom_native_cuda.exe` execute the full
declared expression and the assigned structural laws in Tom Klootwijk's v0.7
formalization. They normalize actual native terms, process explicitly supplied
guarded continuation requests, and preserve complete finite history contents.
The earlier `tom_cpu` / `tom_cuda` Boolean certificate circuit did not do this.
Its larger case counts are historical and must not be presented as native TOM
execution or compared directly with the native counts below.

This is a bounded execution of the assigned structural laws and a declared
continuation contract. V0.7 leaves the unique jitter, actualization, intrinsic
pinion transformation, physical observation protocol and recurrence law open.
The implementation reports those unassigned results; it does not invent them.

## Actual source and implementation

The governing 18-page PDF is `C:/TOMKLOOTWIJKJSFD/TOM_V0_7_Formalization.pdf`,
SHA-256 `97582a16bd54d690b27105f9b09dc48d2b5716bbae2fff2a5e74190278640fbc`.
The literal companion-contract expression was compiled and executed on the GPU:

```text
TOM := InverseOccam[ Arch[ C[J[T]], E[C[J[T]]; InvLog[phi]] ] ] qualified_by forward_T_precedence
```

Its twelve encoded records retain both printed occurrences of `C[J[T]]`.
Canonical comparison recognizes their equality without deleting the original
input. All 331 result words match the independently written Python reference.
The exact source bytes are preserved in the result's history provenance.
`source_full.origin.json` records extraction from the companion contract.

| Source obligation | Executed behavior | Evidence / implementation |
| --- | --- | --- |
| Full expression, c/e/TOM definitions, ordered roles (pp.3–5) | Expand declared source references; enforce J(T), InvLog(phi), E(C(...),InvLog(phi)); recognize the complete qualified root | `source_full.*`, `python/tom/native.py`, `include/tom/native_core.hpp` |
| SDF qualification and first-class definitions (pp.4–5) | Retain and check every term record, including declarations outside the selected root | 31 source-derived fixtures plus malformed cases |
| Explicit A=T and preservation idempotence (pp.5,8) | Apply only the declared alias and adjacent InverseOccam idempotence; retain original terms and rewrite counts | Source cases, normalization-heavy suite, both capacity workloads |
| Equal observations do not imply equal definitions (p.8) | Compare exact normalized structural records; preserve ordered roles and nesting | Equality, role-swap and reassociation fixtures |
| TC1–TC5 and forward precedence (p.6) | Check supplied availability/order/elapsed witnesses; retain and compare every completed byte; prohibit immediate self-result consumption | Source cases, resume suite, mixed capacity workload |
| Guarded self-reference (p.7) | Distinguish own-name declaration, pending guard, open law and assigned result; atomically block resolved candidates when another obligation fails | Guard fixtures and mixed capacity workload |
| No intrinsic nesting ceiling (p.9) | Iterative finite storage with checked ABI/address limits; no arbitrary semantic nesting cap | 1,409-term GPU case with 1,400 licensed rewrites |
| Klein/Matryoshka roles (p.9) | Preserve named definitions without fabricating operation laws | Named-role fixtures and every mixed workload case |
| Optional scalar reading (pp.10–13) | Exact symbolic theorem for the selected finite-real logarithmic echo; it never replaces native structure or computes a physical observation | Scalar reference tests and explicit theorem flag |
| Completed-content preservation (pp.6,8) | Failed proposals retain actual prior bytes; resume reexecutes every prior result word; output publication uses checked temporary files | Twelve GPU resume scenarios and output-failure tests |

Full requirements, source page references and open clauses are in
[NATIVE_CONTRACT.md](NATIVE_CONTRACT.md). The binary layout is in
[native_abi.json](native_abi.json). A separate source review found no additional
unimplemented assigned structural rule within this documented representation.
Finite tests and that review are not a mathematical proof for every possible
extension of TOM.

## What ran on the laptop

Device: NVIDIA GeForce RTX 5070 Ti Laptop GPU, 46 SMs, SM120. Built with CUDA
12.8.61 and MSVC 19.44; driver 591.59. Measured GPU executable SHA-256:
`b761ba159020aac24ba84d68dd0e0418db7fb29c2d6effb5f9576e391c7c8c30`.

Both workloads retain every input and output allocation on the GPU until the run
ends. Each measurement uses three separate runs, two warm-up passes and sixteen
timed passes, 256 threads per block and 32,768 cases per shard. A pass reevaluates
the same supplied proposals; it does not advance a simulated universe.

| Measurement | Full-expression normalization | Full expression with mixed continuations |
| --- | ---: | ---: |
| Distinct retained-history cases resident together | 2,474,208 | 1,851,297 |
| Working bytes | 11,559,499,776 | 11,559,498,468 |
| Working GiB | 10.765623 | 10.765622 |
| CUDA free bytes after allocation, all three runs | 0 | 0 |
| Median evaluation time per pass | 126.634 ms | 128.126 ms |
| Throughput | 19.538 million cases/s | 14.449 million cases/s |
| Final output words independently compared per run | 1,821,017,088 | 1,823,527,545 |
| Mismatched words, all three runs | 0 | 0 |
| Admitted cases | 2,474,208 | 231,413 |
| Cases retaining old history | 0 | 1,619,884 |
| Median complete process, including sixteen passes and verification | 2.881 s | 2.839 s |

Every mixed case contains all ten native opcodes, the full source expression,
an own-name definition, a later-qualified request and the named historical roles.
Eight explicit scenarios cover an assigned result, false guard, unassigned law,
missing guard, future evidence, inconsistent elapsed duration, unguarded result,
and a transaction with one resolved and one pending request. The last case blocks
both from publication. The full mixed pass performs 6,479,536 preservation rewrites,
925,648 explicit aliases and resolves 231,413 supplied continuations.

There are eight structural templates per workload. Unique case IDs change actual
retained history bytes. These are distinct native cases, **not exhaustive
enumeration of every possible TOM term, history, guard or extension law**.
The independent GPU verifier compares every final result word with Python-created
template results, substituting only the six history words containing the exact
case identity. The verifier does not call the native evaluator. Verification is
outside the reported evaluation time (about 29 ms per capacity run). Intermediate
timed passes are not individually exported or independently compared.

## What “saturated” means here

In simple terms, the available CUDA storage was filled with complete cases and
their results. The card was observed busy 100% of a sampled interval. Those are
two different measurements from how close its arithmetic units are to their peak.

A separate Nsight Compute profile of 32,768 mixed cases measured 3.28% SM
throughput, 25.99% DRAM throughput and 46.53% active-warp occupancy. This does
**not** establish maximum compute throughput. The implementation still has
performance headroom. That profile is a representative shard, not a measurement
of the complete memory-capacity run. Profiling overhead is excluded from the
ordinary timings above. Clocks and cache policy were left unchanged.

The GPU physically exposes 12,820,480,000 bytes. CUDA's allocatable budget is
smaller because of the driver/display/runtime and allocation granularity. Zero
reported CUDA free bytes is not a claim that every physical byte is application
data. Mixed-run process telemetry peaked at 69 C, 139.69 W and 100% GPU busy;
these peaks can occur at different instants and include setup and verification.

## Optimization and validation

The measured optimization removed a redundant global-memory clear immediately
followed by a full input copy. On the same 262,144-case normalization workload,
median pass time fell from 16.055 ms to 13.302 ms: 17.15% less elapsed time,
or 20.69% higher throughput. A launch/shard sweep established the selected
configuration. This comparison is from the recorded tuning binaries; the final
binary's capacity measurements are separately pinned above.

Final-release validation:

- CTest: 6/6 suites passed, including 22 native semantic/reference tests.
- Two 4,127-case GPU suites: all 3,334,616 words matched per suite. They include
  the 31 source-derived requirements and deterministic valid/malformed proposals.
- Literal source: 331/331 words matched. Deep source: 23,994/23,994 matched.
- Mixed template fixture: 7,880/7,880 words matched.
- Twelve GPU resume scenarios passed, including forged history/time, shortened
  history, corrupted prior status/content/normalization and path collisions.
- Deliberately corrupting one expected normalized opcode produced exactly 33
  mismatches among 257 generated cases and a failing exit code, as required.
- Compute Sanitizer memcheck and synccheck: zero errors; racecheck: zero hazards.
- Atomic publication tests verify preservation on abandoned writes, failed
  streams and publication failures. Source compiler staging has failure tests too.

Evidence is under `verification/native_20260918/`, especially
`release_conformance.json`, `release_ctest.log`, `release_resume_gpu.json`,
`release_capacity.json`, `release_mixed_capacity.json`, and
`release_mixed_profile.csv`. The release manifest pins source, binaries and evidence.

## Useful applications and limits

The executable can serve as a formal-definition workbench: determine whether a
proposal is the declared TOM expression, inspect exactly which licensed rewrites
apply, preserve different definitions even when a selected reading agrees, and
exercise guarded revision proposals without erasing completed history. These
capabilities support append-only revision processing and exploration of explicit
bounded continuation choices.

The continuation demo uses the real executable to admit a complete source
definition, defer a proposal, admit it once an explicit guard and result are
supplied, reject a past rewrite, and append a correction. Each step resumes from
the previous actual result and is checked independently. The application chooses
the guard/result and record contents; TOM does not secretly generate them.
The [five-step GPU report](../verification/native_20260918/demo/gpu/demo_report.md)
records 2,980 matching words and confirms host resume validation at every
continuation. Pending and rejected attempts retain the last committed time;
the next proposal's elapsed witness includes the intervening attempts.

Uint64 time/order witnesses, record addresses and the byte-history codec are
explicit external interpretation choices. The runtime trusts supplied availability
and guard evidence; it does not authenticate physical time or resolve arbitrary
observations from history. Its source-text frontend handles the declared page-3
expressions and abbreviations; page-7 guarded operations use the lower-level API.
No measured result establishes physical predictions, thermodynamic entropy,
autonomous dynamics, infinite capacity, or a need for a DAG ontology.

## Reproduce

Run these from the project directory after the CMake build:

```powershell
ctest --test-dir build-cuda128 -C Release --output-on-failure
python tools/compile_native_source.py --expression TOM --require-tom --scalar-log-echo --out verification/native_20260918/replay_source.ton --oracle verification/native_20260918/replay_source.reference.tor
.\build-cuda128\Release\tom_native_cuda.exe --input verification/native_20260918/replay_source.ton --output verification/native_20260918/replay_source.gpu.tor --verify
python tools/native_workbench.py templates --mixed-continuations
python tools/measure_native.py --percent 100 --repeat 16 --warmup 2 --samples 3 --block 256 --shard-cases 32768 --templates verification/native_20260918/native_mixed_templates.ton --expected verification/native_20260918/native_mixed_templates_expected.tor --out verification/native_20260918/replay_capacity.json
python tools/native_continuation_demo.py --exe build-cuda128/Release/tom_native_cuda.exe
```

Capacity is measured afresh at runtime and can change with other GPU users.
For a small run, replace `--percent 100` with `--cases 32768`.
