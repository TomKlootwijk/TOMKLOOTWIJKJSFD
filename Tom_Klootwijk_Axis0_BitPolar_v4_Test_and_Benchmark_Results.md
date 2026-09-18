# Executed verification and post-hoc comparisons

**Artifact:** Axis0 BitPolar v4.0 · Tom Klootwijk · NL200678942 · 10-07-1990.

## Validation status

| Component | Actual status |
|---|---|
| C++17 shared integer core and CPU runner | Compiled and executed with GCC 14.2.0. |
| CPU tests with AddressSanitizer and UndefinedBehaviorSanitizer | Passed; leak detection enabled. |
| Scene/history utilities and integer geometry generator | Executed and checked. |
| CUDA source compilation | **Not run: no CUDA compiler/toolkit in the environment.** |
| GPU self-tests and performance | **Not run: no NVIDIA GPU in the environment.** |
| Actual generated PTX float-instruction audit | **Not run: no CUDA compiler.** The audit utility itself passed its two synthetic fixtures. |

CUDA kernels are supplied as source, with SM120 build configuration and device-side self-tests. CPU success is not described as evidence that GPU execution has already occurred. The CUDA self-test is designed to check 972 transition/chart cases and a multi-step texture wave; those are planned on-device cases, not part of the executed counts below.

## Executed correctness tests

| Test family | Cases / result |
|---|---:|
| Every allowed/seed configuration on an embedded 3x3 grid | 19,683 passed |
| Additional complete waves, rect/polar/Klein | 240 passed |
| Packed stencil patterns against coordinate scatter | 1,152 passed |
| Packed mode transitions against a scalar oracle | 6,912 passed |
| Exchange followed by its inverse | 2,304 passed |
| Heterogeneous atlas charts: no cross-chart leakage | 144 passed |
| Scene serialization round trip | 1 passed |
| Full 37-step forward/inverse file equality, jitter off/on | 2 passed |

A 3x3 grid has three legal statuses at each cell: blocked, allowed/nonseed, or seed. Thus 3^9=19,683 exhausts all such inputs. Both packed first-arrival distances and routes are compared to a separate coordinate-based queue BFS. The same core suite was run with sanitizers; see cpu_sanitizers.json.

The polar example has 1,024 addressed cells, 62 blocked cells and 962 reached cells. The route from (4,2) to (4,13) has 49 native graph edges. Its full wave takes 65 updates to produce the empty frontier. The rectangular example reaches 37 allowed cells, decodes a 12-edge route and exhausts on update 14.

The geometry tests compare 1,024 radial samples and 256 angular direction samples to an 85-digit Decimal reference. In those finite tests, maximum relative radius error was approximately 4.61e-10; maximum absolute direction error was approximately 1.04e-8. These are measurements of the tested fixed-point tables, not a global error bound for every possible layout or a distance-field accuracy result.

Raw evidence: cpu_core_tests.json, cpu_sanitizers.json, tools_tests.json, polar_cpu_run.json and polar_route_readout.json. The tiny example's elapsed time includes history I/O and is not used as a general performance benchmark.

## Kernel frozen before comparisons

kernel_freeze.json records hashes of the production implementation before the comparison source was written. Those hashes were unchanged after the comparison runs. The baseline executable is an optional separate CMake target and is not part of either production engine. posthoc_environment.json records the comparison environment.

## Measured CPU comparison

**Host:** AMD EPYC 9V74 80-Core Processor, one benchmark thread, GCC 14.2.0, CMake Release (-O3 -DNDEBUG). No CPU-frequency lock or affinity was configured. Five timed runs after one warm-up per backend; medians shown. The virtualized/shared preparation environment is not the user's laptop.

All backends solve the same complete reachability query on an open polar graph, from one seed, through frontier exhaustion. Buffers are preallocated. Reset/initialization, allocation and result checking are excluded from the timed interval. Frontier stop detection is included. The queue also retains integer distances; the dense sweeps retain reachability, not all distances. Results are checked against an independent BFS after every run. Backend groups were measured sequentially; these are illustrative reproducible baselines, not laboratory-controlled rankings.

| Implementation | 512x64 cells, 289 wave rounds | 1024x256 cells, 641 wave rounds |
|---|---:|---:|
| Packed integer core | 1.009ms | 19.180ms |
| Byte-per-cell Boolean sweep | 24.182ms | 413.270ms |
| FP32-per-cell Boolean sweep | 33.694ms | 598.014ms |
| Ordinary coordinate queue BFS | 0.140ms | 1.280ms |

For the larger case, the packed sweep took about 1/21.55 of the byte sweep's time and1/31.18 of the FP32 Boolean sweep's time. However, the queue BFS took about 1/14.98 of the packed sweep's time. The queue was also faster on the smaller case, by about 7.21x.

**Interpretation:** packing makes a full-grid Boolean sweep much cheaper. It does not remove repeated scanning of already inactive cells at every wave layer. A sparse queue can do substantially less work for a single reachability query. This is a concrete reason not to infer "faster than existing pathfinding" from bit density alone.

The FP32 baseline stores only 0/1 values in float slots. It is not a real-valued Euclidean SDF evaluation or a ray marcher, and none of these measurements compare against a specialized optimized GPU library. The figures do not predict the RTX 5070 Ti Laptop's speedup. Raw samples and methods are in cpu_posthoc_benchmarks.json; benchmark source is benchmarks/cpu_compare.cpp.

## Exact storage arithmetic

For 1,048,576 cells(1024x1024), assuming no padding:

| Representation / allocation | Bytes |
|---|---:|
| One packed one-bit plane | 131,072 =128KiB |
| One FP32 plane | 4,194,304 =4MiB |
| Two conceptual live Boolean planes | 262,144 =256KiB |
| All five GPU state/mask planes | 655,360 =640KiB |
| 1,024-row LUT | 16,384 =16KiB |
| Five equivalent FP32 Boolean-storage planes | 20,971,520 =20MiB |

Thus the bitplane uses 32x less storage than a float plane holding the same Boolean values. Relative to a real distance value, it holds less information: one sign/phase bit does not preserve a32-bit magnitude. These ratios exclude context, allocator, texture-object and counter overhead, and exclude optional history. During initialization, three one-chart template planes are also present temporarily.

## What remains to measure on the laptop

Use tools/benchmark_gpu.py to compare texture reads and ordinary global reads at identical chart counts. It checks final state/count agreement and records median whole-run timings. Its VRAM-percentage option derives a chart count once and reuses it for both backends; it does not silently compare different-sized workloads.

No supplied measurement establishes a texture-cache hit rate, DRAM bandwidth, power saving, or optimal VRAM fill percentage. High allocation occupancy is a capacity choice, not proof of high compute utilization. The atlas consists of independent replicated charts, so higher atlas size means more independent work rather than a single more powerful connected computation.
