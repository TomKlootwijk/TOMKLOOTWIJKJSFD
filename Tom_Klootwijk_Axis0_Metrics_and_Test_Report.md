# Axis 0 kernel: what it does, what passed, and measured comparisons

**Tom Klootwijk · NL200678942 · 10-07-1990**  
Kernel 1.0.0 · formal specification v2.0, profile R · delivery measurements from this build session

## In five-year-old language

Imagine a bead moving through a row of doors. At each door it has a planned left/right choice, a switch that can flip that choice, and a twist that can turn its local orientation over. The bead writes down the door it actually used. Each next geometric step is about 61.8% as large as the previous one. Its signed distance is also the number this model calls local time. A separate orientation bit tells us how to read that signed number consistently.

The bead stops when it has processed all the input doors. “Now” selects one of the evaluated steps and returns the written path. A GPU runs many independent beads at once; it does not make a single bead visit infinitely many doors.

The implemented input is three equal-length bit strings Q, J and H. It is not a natural-language prompt interpreter. The exact example is:

```text
Q = 0110
J = 1010
H = 1011
output = 1100
```

The implementation also returns/reconstructs address 28, parity 1, entropy 4, radius `5 - 3*phi`, local T `phi - 3`, lifted T `3 - phi`, and a Cantor-prefix interval `[72/81, 73/81]` for this example. The full record is in `results/reference_exact.json`.

## Does it work?

**Yes as the defined, finite profile-R computation on the tested CPU backends. Its GPU execution remains to be verified on your laptop.** The result does not establish the broader physical or universal-computing claims in the source explanations.

| Evidence | Actual delivery result | What that means |
|---|---:|---|
| Unit tests | 21 passed | Arithmetic, geometry/deck transforms, field closure, self-represented evaluation, errors, addressing and backend agreement were exercised. |
| Inputs checked against the exact oracle | 37,642 per tested batch configuration | All input triples of lengths 0–5, 100 at length 32, and 93 at lengths 65/257/1600. |
| Branch transitions in that verification set | 244,678 per configuration | This is a test-workload count, not an estimate of all possible programs. |
| Output/address/parity mismatches | 0 observed | Discrete results matched the exact reference in those cases. |
| Largest float64 local-time error | 2.22e-16 | Approximately 0.000000000000000222 model units in the verified set. |
| Largest float32 local-time error | 3.49e-07 | Approximately 0.000000349 model units in the verified set. |
| Literal CUDA-body host check | 14 batches / 1,640 trajectories passed | The actual .cu body was compiled as host C++ with launch indices emulated. This is not GPU execution. |
| NVIDIA GPU execution here | Not performed | No NVIDIA device, NVRTC or CUDA runtime was available in the build environment. |
| RTX 5070 Ti Laptop throughput | Not measured | The package records real results when its GPU commands run on the laptop. |

Raw evidence: `results/unit_tests.txt`, `results/verify_numpy_f64.json`, `results/verify_native_f64.json`, `results/verify_native_f32.json`, `results/cuda_host_shim.json`, and `results/build_environment.json`.

## Actual speed: CPU, not a claimed RTX measurement

Hardware reported by this environment: **INTEL(R) XEON(R) PLATINUM 8573C**; Linux; Python 3.13.5; NumPy 2.3.5. The native recurrence is a single-threaded C++ loop; the container exposes 5 logical CPUs. This is a shared execution environment, not a controlled laptop laboratory.

Workload: **65,536 trajectories × 256 steps = 16,777,216 transitions**, float64. Below are medians of seven prepared-buffer runs after three warmups. They exclude input generation, initialization/reset, allocations and downloading/copying the final result.

| Calculation | Median time | Comparison scope |
|---|---:|---|
| Full profile-R kernel, shared C++ CPU backend | 212.88 ms | Executes the defined recurrence separately for every trajectory. |
| Full profile-R kernel, NumPy CPU mirror | 756.61 ms | Same state calculation through NumPy operations. |
| Simpler factored NumPy terminal-state calculation | 13.66 ms | Matches every returned terminal array, including numerical diagnostics. |
| Ordinary NumPy XOR | 2.00 ms | Matches only the emitted bit string, not the extra geometric/counter state. |

The native full kernel processed **78.81 million branch transitions per second** on this test. Its median warm-cache end-to-end time was **261.19 ms**, including validation, allocations, execution and result copies. Native prepared-run samples ranged from 198.68 to 233.44 ms.

In this workload, the simpler same-terminal-state calculation was **15.58× faster** than the native full recurrence. XOR alone was **106.43× faster**, but performs a narrower job. These comparisons do not predict the laptop GPU ratios.

The full sample arrays and timing scopes are in `results/benchmark_native_f64.json` and `results/benchmark_numpy_f64.json`. GPU speed is not extrapolated from NVIDIA AI TOPS, memory bandwidth or game frame rates.

## Why the simpler comparison gives the same data

This is an observation about the completed implementation:

```text
emitted bits = Q XOR J
final orientation parity = sum(H) modulo 2
final v = sum(H)
final entropy = input length
radius(n) = phi**(-n)
lifted_time(n) = sum(phi**(-k), k=1..n)
local_time = (-1)**parity * lifted_time
```

Consequently, radius and lifted time are shared by all trajectories of the same depth. A conventional array calculation can calculate that common clock once, calculate XOR for the output, count H for the twist state, and attach the resulting signs and metadata. The after-the-fact baseline checks the complete returned arrays, not only a matching output string. It includes the common clock computation inside its measured function.

**The current geometric rules do not add information to the emitted bit string beyond XOR.** Their additional effect is the structured geometric/orientation/time state. This can be studied or used as application state, but it does not demonstrate better compression, learning, rendering, search complexity or general computational power.

The analysis was deliberately performed after the implementation. Core freeze time: `2026-09-18T05:57:39.402653+00:00`. Source hashes are in `results/core_freeze.json`; the baseline code lives only in `benchmarks/`. The comparison findings were not used to replace the delivered per-trajectory kernel.

## Memory: what your 12 GB GPU is being asked to store

The batch backend uses arrays, not a dense 4-D voxel universe. Its explicit device-array requirement is:

```text
bytes = tracks * (4*steps + 3*sizeof(float_type) + 6*8)
```

For the benchmark workload in float64, that is **71,827,456 bytes = 68.5 MiB**. At one million 256-step trajectories it is **about 1.021 GiB** of explicit arrays. CUDA context, allocator caches, the display and other processes consume additional memory; those numbers are not total VRAM measurements.

A 256-step path has 256 logical bits. This implementation's fast batch layout stores it as 256 bytes for straightforward coalesced access. Conventional bit packing would store those same bits in 32 bytes; the API provides `packed_path()` for export. That is ordinary representation packing, not a new compression result. Returning L bits from three L-bit inputs is not lossless compression: the emitted word does not retain the independent jitter and orientation inputs.

## Time precision: a meaningful operational limitation

On the tested CPU arithmetic, two successive rounded lifted-time values first become equal at **step 35 in float32** and **step 77 in float64**. At that scale, the next increment is too small to change the rounded accumulated value. A visually unchanged clock value does not mean the mathematical trajectory stopped.

The kernel therefore does not identify events by float equality. It retains an exact symbolic time key `(profile R, step)`, exact branch bits and integer counters. Complete algebraic values are available through the exact CPU reference. Diagnostics report loss of float resolution; they never silently stop the run. Raw audit: `results/precision_native.json`.

## What this does and does not establish

It establishes a runnable, inspectable realization of the specified finite transition model, including an executable seed, exact reference arithmetic, a quotient-field interpretation, field-readable operator descriptors, a termination condition and a decoder.

It does not demonstrate that the physical world identifies distance with duration, that entropy guarantees arbitrary programs halt, that a parity flip resolves causal paradoxes, or that all algorithms have been encoded in geometry. The delivered entropy is the selected count n, and termination is the selected finite input length. Self-reference through the implemented registry is distinct from a proven universal interpreter or an autonomous replication process.

Unassigned source terms remain visible in `axis0 operators` rather than receiving invented implementations. The tested profile is a useful starting executable model, but its current output computation is no stronger than the explicitly stated conventional operations.

## Reproduce on the laptop

After setup, run:

```text
python -m axis0 verify --backend cuda --json results/laptop_verify.json
python -m axis0 precision --backend cuda --json results/laptop_precision.json
python benchmarks/benchmark.py --backend cuda --json results/laptop_benchmark.json
```

These reports distinguish compiled/running GPU code, kernel-event timing, end-to-end latency, precision behavior and the output-only XOR comparison. They replace an estimate with actual data from the user's machine.

## Source notes

The definition and its temporal vocabulary come from the supplied materials and preceding v2.0 formalization; `docs/SPECIFICATION_MAP.md` maps those to code. The results above are newly measured or algebraically derived from the delivered implementation, not claims quoted from the exported search text.

Hardware and setup references appear in `docs/CUDA_SETUP.md`. The conventional comparison operations are documented by NumPy at https://numpy.org/doc/stable/reference/generated/numpy.bitwise_xor.html and https://numpy.org/doc/stable/reference/generated/numpy.sum.html . Those documentation pages do not supply or validate the reported timing numbers.
