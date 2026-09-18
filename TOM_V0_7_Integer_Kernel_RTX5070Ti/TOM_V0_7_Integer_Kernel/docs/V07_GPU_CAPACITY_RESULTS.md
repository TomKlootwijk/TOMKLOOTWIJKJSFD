# TOM v0.7: bounded execution on Tom's RTX 5070 Ti Laptop

**Historical Boolean certificate measurements.** These counts do not describe
the subsequently implemented native-term executor. Current source execution,
capacity and performance evidence is in
[NATIVE_EXECUTION_RESULTS.md](NATIVE_EXECUTION_RESULTS.md).

Measured on 18 September 2026 against Tom Klootwijk's parent-folder
`TOM_V0_7_Formalization.pdf` and its companion package. The
[source-to-implementation map](V07_REALIZATION_MAP.md) identifies each implemented,
partial and open source requirement. All raw evidence is in
[`verification/formalization_20260918`](../verification/formalization_20260918/).

## What happened, in simple terms

Think of a candidate as a card containing a proposed before/after situation. This
kernel checked hundreds of millions of different cards for forward time, correct
elapsed duration, no declared input from the future, and no lost membership bits.
It also calculated the optional Arch scalar reading while keeping the original
inputs and definition-witness labels distinct.

The complete selected box contained **536,870,912 different cards**. The GPU
checked it in **32.40 milliseconds per pass**, using **9.625 GiB** of working
payload. **9,289,728 cards passed the temporal/retention interpretation.** A saved
64 MiB answer bitmap contains the result for every card; every answer bit was
compared with an independent integer calculation and matched.

A second run made the box larger and filled the available CUDA allocation budget:
**572,194,368 distinct candidates**, **10.658 GiB** of working payload, **100% peak
reported GPU busy time**, and **zero CUDA-reported free bytes after allocation**.
That run covers a prefix of a larger domain, not every possible 31-bit candidate.

These are exact results for explicitly declared finite checks. **The current
kernel does not execute the entire native TOM expression.** It retains its roles
and source contract, but native structural operations remain partly unimplemented,
and page 14 leaves jitter, actuality and pinion behavior open. More GPU memory
alone would not supply those missing semantics.

## Precisely what was enumerated

The complete profile has four time fields of 3 bits each (values 0–7), two retained
membership masks of 3 bits each, two signed scalar readings of 4 bits each
(−8 through 7), and two witness labels of 2 and 1 bits. These total 29 independent
input bits. A counter's disjoint bit slices enumerate each combination exactly
once. No input field is discarded after evaluation.

These small field widths make the Cartesian product exhaustive. They are chosen
external readings, not claimed native TOM units. The 31-bit profile increases the
two witness labels to 3 and 2 bits. Its entire domain has 2,147,483,648 cases and
needs 40 GiB of state/scratch payload, beyond this card's resident capacity.

The temporal/retention predicate is:

```text
current_time > previous_time
AND elapsed == current_time - previous_time
AND latest_dependency <= current_time
AND (retained_before & ~retained_after) == 0
```

This checks supplied availability stamps and three membership bits. It does not
authenticate when physical observations became available or preserve the complete
contents of every past observation. Those are additional interpretation choices.
The optional exact Arch residual is `abs(a) + abs(b) - abs(a-b)`; its zero test is
separate from temporal admission. Arbitrary opposite-sign readings establish Arch
neutrality, not the stronger source relation `echo = ln(1/phi) * direct`.

## Measured capacity and speed

Device: NVIDIA GeForce RTX 5070 Ti **Laptop** GPU, 46 SMs, compute capability 12.0.
CUDA 12.8.61, driver 591.59, MSVC 19.44. The runtime reported 12,820,480,000 total
device bytes. No clock, voltage, driver, watchdog or power-limit settings changed.

| Metric | Entire 29-bit box | 31-bit capacity prefix |
|---|---:|---:|
| Distinct candidates | 536,870,912 | 572,194,368 |
| Complete declared domain? | Yes | No |
| Resident state/scratch payload | 9.625 GiB | 10.657951 GiB |
| Shards | 64 | 69 |
| Repeated measured passes per process | 4 | 64 |
| Median compute time for those passes | 129.6102 ms | 2,482.7463 ms |
| Median compute time per pass | 32.40255 ms | 38.79291 ms |
| Computed candidate checks per second | 16.57 billion | 14.75 billion |
| Median whole-process time | 0.9755 s | 5.4694 s |
| Minimum CUDA free bytes after allocation | 1,090,519,040 | 0 |

Medians use three independent process runs, each with two untimed warmup passes
followed by restoration of the exact starting state. Compute timing includes
launches and completion. It excludes initialization, population counts, exports
and CPU verification; whole-process timing includes those requested phases.
Repeated passes recheck the same inputs: 64 passes are not 64 times as many unique
possibilities, and they do not evolve native TOM dynamics.

The separate complete-bitmap run exported 67,108,896 bytes (32-byte header plus
64 MiB of answers), with 31.6218 ms compute and 1.6678 s whole GPU-process time.
The independent host comparison followed that process and is not included in its
wall time. See `full_domain_admission_mask.json` for that run.

The capacity process selected 99% of its reported free-memory budget for payload.
After allocation CUDA reported zero free bytes; the remaining consumption was not
isolated by cause. NVIDIA's separate device-memory telemetry still showed a minimum 515 MiB
free, so this is **exhaustion of the process's available CUDA budget**, not proof
that every physical byte was occupied. It is a successful measured operating
point, not a proof of maximum capacity under every allocation strategy. Memory
availability can differ on the next run.

## What “saturated” actually means here

During the long capacity runs, telemetry reached 100% GPU busy, 58% memory busy,
11,430 MiB device memory used, 76°C and 169.81 W. These are separate peaks over
all process phases, sampled every 200 ms; they need not occur simultaneously.
GPU busy is a time-utilization measure, not the fraction of all arithmetic units
performing useful operations ([NVIDIA telemetry documentation](https://docs.nvidia.com/deploy/nvidia-smi/)).

Nsight Compute measured a representative 8,388,608-candidate shard separately:

| Definition backend | SM throughput / tool peak | DRAM throughput / tool peak | Active warp occupancy | Kernel duration |
|---|---:|---:|---:|---:|
| Shared | 81.46% | 42.68% | 76.69% | 0.4610 ms |
| Global | 61.59% | 26.02% | 92.89% | 0.7576 ms |
| Texture | 48.20% | 22.71% | 93.05% | 0.8564 ms |

These hardware-counter measurements are from the representative shard, not the
full-memory run. The definitions follow the
[Nsight Compute profiling guide](https://docs.nvidia.com/nsight-compute/ProfilingGuide/index.html).
Shared was faster despite lower occupancy: occupancy alone is not useful speed.
The integer workload does not need every Tensor or ray-tracing unit; no measurement
establishes 100% use of every GPU resource.

A full-memory Nsight replay attempt was stopped after its buffer copies pressured
the laptop's 16 GiB of host RAM. It produced no usable counter result. Its timings
are excluded. Normal unprofiled full-memory execution succeeded. All measurement
and profiler processes have ended and released their allocations.

## Optimization and correctness

An 18-configuration sweep compared three definition backends, three block sizes
and two grid caps on identical inputs. Shared definitions, the canonical lowered
evaluator, 256 threads/block and a grid cap of 24 blocks/SM were fastest in that
sweep. At 8,388,608 candidates and 64 passes, the median was 30.2018 ms versus
33.2066 ms with an 8-block/SM cap: about 9% less elapsed time, or 10% more throughput.
The cap controls launched work; it does not assert that 24 blocks reside on an SM
simultaneously. Universal CLI defaults were not changed based on this one circuit.

The shared integer evaluation core was preserved. The runner gained explicit
shard/grid controls, all-shard Boolean population counts, every-shard edge checks,
and complete single-plane bitmap export. The bounded-space generator, measurement
tool and saved-answer reader connect those facilities to the parent formalization.

Validation completed:

- CTest: 3/3 suites passed, including exhaustive small-domain circuit/oracle checks.
- GPU regression suite passed for texture, global and shared backends with both
  evaluators. The oversized kernel-quotation example is explicitly skipped only
  for shared memory; texture/global cover it.
- Every admission bit in the complete 536,870,912-case domain matched its independent
  integer oracle. All ten reported Boolean population totals also matched exact
  expected totals in full-domain and capacity runs.
- Complete states at both ends of every shard matched the CPU field evaluator.
  This samples full states; it is not an every-bit comparison of every state plane.
- Shard controls: 45 valid GPU cases and four invalid-option cases passed.
  Bitmap export: 25 GPU exports, one disabled-export case and four invalid cases
  passed, including small shards, all six execution modes, resumption and the
  export-buffer boundary.
- Compute Sanitizer memcheck, racecheck and synccheck reported zero errors/hazards
  on the new bounded circuit with forced small shards, counting and export enabled.
- The original companion package's formula and editorial-contract audits passed.

The authored compute source and generated PTX passed integer checks. The SASS
audit covers all eight device kernels and finds **24 compiler-generated `HFMA2`
constant-zero instructions**, with no other floating arithmetic found. Its strict
“no floating opcode anywhere” verdict remains **REVIEW_REQUIRED**, not PASS. The
data-computation audit passed separately; an integer result does not justify
claiming that the machine code contains zero floating opcodes.

Two binary revisions were measured. The tuning sweep and three-sample complete-box
timing pin SHA256 `2940be3743e209dcba90ff3b0ee00442dcf56a4aa3381ece572cdf1bc8d892d2`.
After adding bitmap export, the capacity runs, complete-bitmap run, final regression
and instruction audit use the current binary SHA256
`a00a3c0968fb3f3acd49bd65d8040ba541788805a170a769a254a3b61eeb1201`.
The table reports the actual measured runs, not a claim that all measurements used
one binary. The latter build's full-domain single pass is reported separately
above. Each raw measurement pins its own executable and program hashes.

## What this can do now

1. **Exhaustively inspect a chosen finite interpretation.** Count all accepted
   candidates, retrieve individual saved answers and explain each failed predicate.
2. **Find counterexamples to overly strong claims.** Case 1096 has Arch zero but
   fails because its declared input arrives after the current time. Zero residual
   is therefore insufficient for temporal admission even inside this small box.
3. **Preserve distinctions that share a reading.** Cases 72 and 67,108,936 both
   pass and have Arch zero, while retaining different supplied witness labels.
4. **Compare declared extensions.** Additional explicit candidate rules or bounds
   can be encoded and their effects measured against this reproducible baseline.
   They must be identified as extensions, not attributed to unassigned source laws.

A practical application direction is a bounded verifier for event histories or
proposed state transitions, with application-defined witnesses. Actual deployment
would need contents/history preservation and authenticated inputs appropriate to
that application. This study does not establish physical prediction, a unique
native evolution or thermodynamic behavior.

For a fuller TOM realization, the next source-supported work is executable native
term structure, licensed preservation/idempotence rewrites, symbolic inverse-log
binding, and explicit bounded completed-history contents. Jitter, actuality and
pinion evolution still require named additional assignments from the source's
open clauses. The source map separates those two kinds of remaining work.

## Reproduce and inspect

Run from the kernel directory, with the source PDF and ZIP in the parent tree:

```powershell
cmake -S . -B build-cuda128 -G "Visual Studio 17 2022" -A x64 -T cuda=12.8 -DTOM_ENABLE_CUDA=ON -DTOM_CUDA_ARCH=120
cmake --build build-cuda128 --config Release --parallel
ctest --test-dir build-cuda128 -C Release --output-on-failure
python tools/make_bounded_space.py
python tools/make_bounded_space.py --witness-bits 5
python tools/measure_bounded_space.py --exe build-cuda128/Release/tom_cuda.exe --program examples/bounded_space_29bit.tsdf --lanes 536870912 --ticks 4 --samples 3 --blocks-per-sm 24 --out verification/repeat_full_domain.json
python tools/read_bounded_space.py --case 72 1096 67108936
```

The reader uses the already verified saved bitmap and checks its hash. To generate
another complete bitmap, use the measurement command with `--ticks 1 --samples 1
--mask-out verification/repeat_admission.tommask` and a new report path. Pass that
report to the reader using `--report`.

The measured capacity command used `bounded_space_31bit.tsdf --percent 99 --ticks
64 --samples 3 --blocks-per-sm 24`. Its case count is selected from current free
memory and can change. The complete-domain command above uses a fixed count.

Machine-readable summary: `study_summary.json`. Detailed runs:
`full_domain_29bit.json`, `capacity_99.json`, `full_domain_admission_mask.json`.
Profile counters: `ncu_tile_{shared,global,texture}.csv`. The saved bitmap SHA256 is
`f44792b897ff22a69d540b8ea9b2cac3fbd3e415b890f7f5e905d070aedb967f`.
The source PDF SHA256 is
`97582a16bd54d690b27105f9b09dc48d2b5716bbae2fff2a5e74190278640fbc`.
