# TOM V0.7 — bounded native execution

**Tom Klootwijk · NL200678942 · date supplied 10-07-1990**

Target: **GeForce RTX 5070 Ti Laptop**, user's stated **12 GB VRAM**. Build target
`sm_120`; actual device capabilities and free memory are queried at runtime.

**Current execution, 18 September 2026:** `tom_native_cpu.exe` and
`tom_native_cuda.exe` execute the full source expression, its assigned structural
laws, guarded continuation requests and exact finite-history preservation.
Read the [native execution results](docs/NATIVE_EXECUTION_RESULTS.md) and
[source contract](docs/NATIVE_CONTRACT.md).

The final mixed run held **1,851,297 full-expression cases**, including all ten
native opcodes and assigned, pending and unassigned continuations. It filled the
available CUDA allocation budget with **10.7656 GiB** of resident input/output,
evaluated a pass in **128.126 ms**, and matched **1,823,527,545 independently
expected final result words**, with zero mismatches. This is memory saturation;
maximum arithmetic throughput has not been reached. Case histories vary across
eight declared templates; this is not the entire unbounded possibility space.

The literal source expression also ran on the GPU and matched every independently
expected word. Original syntax, source bytes and completed history survive.
The source leaves unique jitter, actualization, intrinsic pinion and physical
observation laws unassigned; the runtime exposes those limits explicitly.

```powershell
cmake -S . -B build-cuda128 -G "Visual Studio 17 2022" -A x64 -T cuda=12.8 -DTOM_ENABLE_CUDA=ON -DTOM_CUDA_ARCH=120
cmake --build build-cuda128 --config Release --parallel
ctest --test-dir build-cuda128 -C Release --output-on-failure
python tools/compile_native_source.py --expression TOM --require-tom --out verification/native_20260918/my_source.ton
.\build-cuda128\Release\tom_native_cuda.exe --input verification/native_20260918/my_source.ton --output verification/native_20260918/my_source.gpu.tor --verify
python tools/native_workbench.py inspect verification/native_20260918/my_source.gpu.tor
python tools/native_continuation_demo.py --exe build-cuda128/Release/tom_native_cuda.exe
```

The shared native implementation is `include/tom/native_core.hpp`; Python's
independent reference is `python/tom/native.py`. The [ABI](docs/native_abi.json)
and [31 source-derived cases](examples/native_acceptance_cases.json) make the
external representation and obligations inspectable.

## Clean SDF/Klein semantic core

`python/tom/sdf_core.py` is the reference semantic layer for the universal
substrate direction. It treats SDF as a definition-level operator relation,
not as a mandatory Euclidean distance or coordinate grid. A term carries its
ordered operator identity, sign, exact value or symbolic value, double-packed
`KleinPack`, optional seed-derived `Pinion`, provenance, history, and open
obligations. `pack_term` and `Registry.pack` provide canonical digest-checked
serialization.

`python/tom/sdf_lowering.py` is the explicit compatibility seam into the
validated TOM/K1 evaluator. It lowers only operators declared by the selected
profile and emits a semantic sidecar for fields that the fixed ABI cannot yet
carry. Unsupported operators and unresolved obligations are rejected; they are
never silently flattened into a scalar or Boolean result. See
[`docs/SDF_CORE.md`](docs/SDF_CORE.md) and the `tom_sdf_core`/
`tom_sdf_lowering` tests.

## Historical Boolean K1 implementation

Everything below describes the earlier `tom_cpu` / `tom_cuda` Boolean circuit
and original package, unless explicitly dated otherwise. Its large certificate
case counts are not native TOM execution. The historical
[capacity study](docs/V07_GPU_CAPACITY_RESULTS.md),
[realization map](docs/V07_REALIZATION_MAP.md),
[session report](docs/LOCAL_SESSION_20260918.md) and
[event-admission demo](docs/EVENT_DEMO.md) remain available for provenance.

## What you receive — and what actually ran

The CPU executable and shared integer core **were compiled and tested**. The tests
verified every signed 8-bit Arch input pair, temporal/retention certificates,
self-reference, complete kernel quotation, changed-kernel behavior, resumption
and generated programs. CPU AddressSanitizer/UndefinedBehaviorSanitizer checks
also passed.

**CUDA was not compiled or run in the original delivery environment.** Neither `nvcc`
nor an NVIDIA GPU is installed there; an attempted official-toolkit download was
unavailable. The archive contains CUDA source and validation/build scripts, **not
a precompiled Windows executable**. Source-token checks found no floating types
in the authored compute core. PTX/SASS and device behavior still require a real
CUDA build. See `verification/environment.json` and `integer_audit.json`.

The report `gpu_executed: true` is produced only by the real CUDA executable.
The package does not replace that evidence with CPU timings or imaginary GPU
performance. It never modifies clocks, voltage, drivers, firmware or power limits.
Local hardware validation and compiled-code audit results are recorded separately
under `verification/session_20260918/`; see the session report for their scope.

## The exact meaning of “kernel, programs and data as SDFs” here

The common carrier is a packed encoding of **TOM SDF declarations**, using the
source's final definition-level meaning, not a conventional sampled metric SDF.

- The `KERNEL` field contains an actual executable seven-clause selector law.
  The `field` evaluator **reads and executes that stored law** for program gates.
- A program expression refers to a rule definition and its operands. The same
  image holds truth tables, dynamic truth-row references, quotation and bindings.
- Data is bit-sliced: a uint32 contains one Boolean signal for **32 independent
  cases**. Multi-bit values are collections of such Boolean signal planes.
- Every definition record stores its own address. `Quote` reads exact bits of
  definitions and the kernel tape. Dynamic rules can use old state bits as their
  truth coefficients, publishing new coefficients only into the next snapshot.
- `A` and `T` name the **same stored time-binding definition**. Its bindings select
  what becomes the next state. Old and next state never alias during a tick.

A small C++/CUDA **bootstrap reader** still executes machine instructions. NVIDIA
cannot execute an uninterpreted source term as a machine instruction merely
because it is called SDF. This bootstrap is explicit: the package does not claim
that all hardware interpretation has disappeared. `kernel_selfcopy` proves that
the operational evaluator's entire 896-bit microprogram can be read by its own
program language and republished byte-for-byte. It is not a claim of a completely
self-hosting CUDA compiler or unlimited structural self-replication.

`docs/SEMANTICS.md` distinguishes source requirements, the native declaration
layer, finite interpretation choices, and the bootstrap. The intrinsic actions of
`phi`, `inverse_log_phi`, jitter and other unspecified source roles are preserved
as named declarations, not silently replaced by rotations or made-up functions.
Attempting to execute one as an unassigned truth table is a compiler error.

## First build on the laptop

Requirements: CUDA Toolkit **12.8 or later with SM120 support**, a compatible
NVIDIA driver, CMake **3.24+**, a C++17 compiler supported by that CUDA toolkit, and
Python **3.10+**. Python tools use only the standard library. This implementation
does not require PyTorch, CuPy, a graphics API or an AI model.

### Windows

Use a Visual Studio 2022 Developer PowerShell with Desktop C++ tools and CUDA's
Visual Studio integration installed. In the extracted package directory:

```powershell
cmake -S . -B build -G "Visual Studio 17 2022" -A x64 -T cuda=12.8 -DTOM_ENABLE_CUDA=ON -DTOM_CUDA_ARCH=120
cmake --build build --config Release --parallel
ctest --test-dir build -C Release --output-on-failure
.\build\Release\tom_cuda.exe --info
python tools\validate_laptop.py --exe build\Release\tom_cuda.exe --quick --out verification\laptop
```

`build_windows.ps1` detects the installed nvcc version, explicitly selects that
Visual Studio CUDA toolset, and defaults to `build-local/`. Override with
`-BuildDir build-cuda128 -CudaVersion 12.8` to use this session's directory.
It performs configure/build/core/compiler tests and stops on errors. A
compiler/driver failure is never written as a passing GPU result. Remove `--quick`
for the larger generated-program suite; the quick suite still runs the complete
65,536-pair Arch test, all 2,048 ternary-rule cases and the temporal certificates.

### Linux

```bash
cmake -S . -B build -DTOM_ENABLE_CUDA=ON -DTOM_CUDA_ARCH=120 -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
python tools/validate_laptop.py --exe build/tom_cuda --quick --out verification/laptop
```

### CPU-only reproduction

```bash
cmake -S . -B build-cpu -DTOM_ENABLE_CUDA=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build-cpu --config Release --parallel
python tests/validate.py --exe build-cpu/tom_cpu --out verification/local_cpu.json
```

Windows CPU path: `build-cpu/Release/tom_cpu.exe`.

## Validate TOM's actual finite obligations first

Six editable examples have the same general format in `examples/certificates.json`:
a valid certificate, future dependence, retrograde chronology, erased elapsed
time, erased retained distinctions, and a non-neutral Arch reading. Run:

```powershell
.\build\Release\tom_cuda.exe --program examples\tom_conformance.tsdf --data examples\certificates_data.tsdf --ticks 1 --backend texture --verify --out certificates_out.tsdf
python tools\readout.py examples\tom_conformance.tsdf certificates_out.tsdf --lanes 0,1,2,3,4,5
```

Expected `all_reported_checks` values are **1,0,0,0,0,0**. In cases 1–4, the Arch
reading remains neutral while a temporal or retention obligation fails. The
program exposes the separate flags rather than treating a zero residual as proof
of all the surrounding semantics. Case 5 has valid temporal/retention flags but
fails Arch neutrality. Equal residuals do not overwrite the supplied definition
witnesses: inputs remain in the state and are not reduced to the output bit.

To change input values, edit the JSON and pack them without floats:

```powershell
python tools\pack_cases.py examples\tom_conformance.tsdf examples\certificates.json my_cases.tsdf
```

Unsigned timestamp inputs have declared 16-bit width, retained-mask witnesses
8-bit width, and the direct/echo readings signed 8-bit width. `elapsed_preserved`
requires forward order as well as exact integer difference: wraparound cannot
pass. Padding to a multiple of 32 allocates extra lanes; those padding lanes are
not counted as user test cases. Wider circuits can be generated explicitly with
`python/tom/builder.py`; finite widths are implementation choices, not native TOM
cardinality. Real-time availability claims must be measured/authenticated outside
this arithmetic certificate checker.

## Demonstrate real self-reference

```powershell
.\build\Release\tom_cuda.exe --program examples\self_reference.tsdf --lanes 64 --ticks 3 --backend texture --verify --trace self.ttrace --out self_final.tsdf
python tools\read_trace.py examples\self_reference.tsdf self.ttrace --lane 0
```

At epoch 0 the stored truth field is identity (`170`, hex AA). Epoch 1 uses that
rule, then publishes NOT (`85`, hex 55) for the next epoch. Epoch 2 uses NOT and
publishes identity again. The same program also reads its own definition id and
an actual kernel-coefficient bit. The recorded lane-0 answers are **0,0,1,0** for
initial state and epochs 1–3. The stored `current_rule` at each completed epoch is
the rule ready for the **next** evaluation, not a retrospective rewrite.

Time here is a monotone uint64 **execution epoch**, separate from the native time
role and the certificate's measured time inputs. Epoch wrap is rejected rather
than quietly resetting to zero. `--data` resumes the saved state and epoch. The
trace stores every snapshot including the initial one; it is not a lossy ring
buffer described as complete retention. Large traces cost host memory and I/O.

## The kernel definition itself can be inspected, changed and copied

```powershell
python tools\inspect_image.py examples\kernel_reflection.tsdf --field KERNEL
python tools\patch_kernel.py examples\kernel_reflection.tsdf changed_kernel.tsdf --selector-table 0xAC
.\build\Release\tom_cuda.exe --program changed_kernel.tsdf --lanes 2048 --ticks 1 --evaluator field --verify --out changed.tsdf
```

Changing this field changes the **evaluator law**, not merely an application
constant. The executed CPU test found 1,024 changed outputs among the 2,048 cases.
The optimized lowered evaluator explicitly rejects an edited noncanonical kernel
rather than ignoring it and claiming equivalence.

Copy the whole operational kernel through quotation and republish it:

```powershell
.\build\Release\tom_cuda.exe --program examples\kernel_selfcopy.tsdf --lanes 32 --ticks 1 --backend texture --verify --out kernel_copy.tsdf
python tools\publish_kernel.py --copy-program examples\kernel_selfcopy.tsdf --snapshot kernel_copy.tsdf --target-program examples\tom_conformance.tsdf --out republished.tsdf
```

The CPU test reproduced the target program byte-for-byte this way. Structural
publication is deliberately **between** runs. The CUDA machine code is not being
modified from inside a texture read. The large self-copy program might not fit
per-block shared memory; texture/global modes remain available. GPU validation
records the shared-memory size skip instead of treating it as a passed run.

## Why the source's logarithm does not require floats in this test

In the supplied scalar reading, the coefficient `ln(1/phi)` is negative for the
positive golden-ratio calibration. The Arch zero predicate depends on signs:
`abs(a)+abs(b)-abs(a-b)==0` iff `a*b<=0`. The conformance program tests that exact
relation with bits; it does not approximate the logarithm or declare that a
selected binary constant *is* the native inverse-log pinion.

`arch_exact_int8.tsdf` additionally evaluates the full residual exactly for every
signed 8-bit input pair, extending widths before absolute value and subtraction.
A correct zero says only what that scalar formula says. It does not establish an
unbounded continuum, physical causality, entropy growth or a selected jitter law.

## Optimizations and device memory

- **32 independent cases per word** for each Boolean signal; adjacent GPU threads
  access adjacent words. The field bits are not floats reinterpreted as integers.
- **One whole program schedule per word-thread**, not one GPU launch per gate.
- **Lifetime-based scratch reuse**, checked against an unrecycled reference.
- **Kernel lowering**, allowed only after the exact stored canonical microprogram
  and selector table are verified. `--evaluator field` remains the default.
- **Texture / global / shared modes** with identical logical input definitions.
  Integer texture reads have no normalized coordinates, interpolation or filtering.
- **Queried memory limits and sharded batches**, with overflow and allocation
  errors made explicit. All shard launches use the same CUDA stream ordering.

`--backend shared` stages the full immutable definition image per block while
old state uses texture reads. This is block-lifetime residency, not permanent
texture-cache pinning. The definition image is reloaded on each launch. Scratch
uses ordinary thread-owned loads/stores because its values are read after being
written in the same kernel. Next state is separate from current state.

For B lane-words, S state signals, V scratch slots and D definition bytes, working
payload is **D + 4*B*(2*S+V)**. GPU/texture allocator overhead is additional. The
conformance image has S=120 and V=149: one million (1,048,576) cases use **48.625
MiB** for current/next/scratch, plus **32,064 bytes** of definition data. The same
Boolean planes as FP32 would use 32 times as much payload. That is a representation
comparison, not lossless compression of arbitrary numerical distances.

A large generated batch can use a percentage of currently free VRAM:

```powershell
.\build\Release\tom_cuda.exe --program examples\kernel_reflection.tsdf --vram-percent 80 --ticks 1 --evaluator lowered --backend texture --verify --json memory_test.json
```

This increases independent lanes. It does **not** enlarge the intrinsic definition
or prove the input cases are all unique: declared counter seeds can repeat.
`--data` keeps its supplied case count and cannot be combined with this capacity
option. At 100%, resource overhead or another process can still cause allocation
failure. Start with the small validation commands; long launches on display GPUs
can encounter the operating system's watchdog. Reduce batch size rather than
changing driver/security policies. No such system changes are made by the tools.

Saved `--out` snapshots and `--trace` cover the **first shard only**; the JSON
reports its size and the total shard count. `--verify` compares the first and last
up to 64 lane-words (2,048 lanes at each edge) of **every shard** against the CPU
field evaluator, outside the timer. Overlapping ranges are checked once. The
supplied test suite separately checks complete small-batch outputs, including all
65,536 Arch cases.

`--count-state SLOT` (repeatable) counts that Boolean plane over **all lanes in all
shards**, outside compute timing. `--state-mask-out PATH --state-mask-slot SLOT`
exports one Boolean plane over all shards in global lane order, with a 32-byte
header and packed little-endian uint32 words. See [the format](docs/FORMAT.md).
`--shard-words CAP` limits each shard (0 selects automatically), and
`--blocks-per-sm N` controls the launch grid cap (default 8). These controls do not
change the logical case definitions.

## Measure and inspect actual GPU code

```powershell
python tools\benchmark_laptop.py --exe build\Release\tom_cuda.exe --out verification\laptop_benchmark.json
python tools\audit_cuda.py --compile --out verification\local_ptx_audit.json
compute-sanitizer --tool memcheck .\build\Release\tom_cuda.exe --program examples\self_reference.tsdf --lanes 128 --ticks 3 --verify
```

Benchmark JSON uses integer nanoseconds and exact result digests. It compares
identical lane counts across backends and lowering choices. Runtime setup, host
uploads, result export and CPU verification are excluded; launches and completion
are included. Traces are disabled during the benchmark. It does not claim that
filling VRAM necessarily accelerates one question.

The benchmark now defaults to two untimed warmup ticks **inside each measured
process**, then restores the exact initial state before timing. `--warmup 0`
measures cold launches. Use `--blocks 64,128,256` for a block-size sweep; reports
include all samples, min/median/max and executable/program hashes. The executable
itself retains `--warmup 0` as its default.

`audit_cuda.py` compiles real PTX only when nvcc exists, then looks for floating PTX
suffixes. In the delivered report compilation is **UNAVAILABLE**, not PASS. Inspect
native instructions with `cuobjdump --dump-sass build\Release\tom_cuda.exe` after
building. A source-token scan is not a machine-code audit, and no guarantee about
all third-party driver internals is made.

## Trust and interpretation boundaries

`--verify` means the GPU and CPU evaluated the **same supplied image** identically.
It does not prove that an edited program still encodes the intended TOM laws. The
independent mathematical cases and canonical images give that additional check.
The manifest detects file changes relative to a known copy, not identity or an
unforgeable physical presence. Rules and data are inspectable, not secret keys.

The package preserves the latest source's refusal to identify TOM with a spatial
grid, graph, conventional metric or physical personal identity. It does not turn
undefined intrinsic actions into algorithms by renaming an instruction. Those
unassigned native definitions are present and quoted, while only declared finite
interpretations execute. The source/implementation map is in `docs/SEMANTICS.md`.
