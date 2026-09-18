# First validation on the RTX 5070 Ti Laptop

1. Install a CUDA Toolkit with SM120 support (12.8 or later), a supported Visual
   Studio 2022 C++ toolset and CMake. Use the developer PowerShell.
2. In this package directory, run:

```powershell
.\build_windows.ps1
python tools\validate_laptop.py --exe build-local\Release\tom_cuda.exe --quick --out verification\laptop
```

This checks actual GPU output against complete test expectations for small
batches. `shared` may record the large kernel-selfcopy image as skipped when it
does not fit the GPU's per-block limit; texture/global still check the image.

For this machine's existing build, use `build-cuda128/Release/tom_cuda.exe`.
Its script-signing policy blocks unsigned `.ps1` files; use the direct CMake
commands in the local session report when reproducing on this machine.
See the current [source-bound capacity results](V07_GPU_CAPACITY_RESULTS.md),
[v0.7 implementation map](V07_REALIZATION_MAP.md), and
[the stateful event demo](EVENT_DEMO.md). In commands below, replace `build` with
the directory selected by your build command (`build-local` for the script).

3. Inspect TOM's finite temporal and retention conditions:

```powershell
.\build\Release\tom_cuda.exe --program examples\tom_conformance.tsdf --data examples\certificates_data.tsdf --ticks 1 --verify --out result.tsdf
python tools\readout.py examples\tom_conformance.tsdf result.tsdf --lanes 0,1,2,3,4,5
```

Expected final Boolean checks: 1,0,0,0,0,0. The separate output flags explain why
each case passes or fails. Data and program are packed bit definitions. No float
input or numerical logarithm is used.

4. See the program read its own definitions and prepare a different future rule:

```powershell
.\build\Release\tom_cuda.exe --program examples\self_reference.tsdf --lanes 64 --ticks 3 --verify --trace self.ttrace
python tools\read_trace.py examples\self_reference.tsdf self.ttrace --lane 0
```

The rule alternates identity and NOT; its current truth rows are part of state,
not a rewritten account of an earlier execution. The trace contains every saved
snapshot. The kernel and the program can also quote the evaluator's entire body;
see `publish_kernel.py` in the README.

5. Inspect generated device instructions only after a real compiler is installed:

```powershell
python tools\audit_cuda.py --compile --out verification\local_ptx_audit.json
```

The original delivered CPU results did not stand in for a CUDA build. This laptop
has now run the GPU suites and the PTX/SASS audits. Source and PTX integer checks
passed; SASS contains compiler-generated floating opcodes that construct constant
zero, so the strict no-floating-opcode audit remains REVIEW_REQUIRED. See the
current capacity report for exact coverage, results and remaining source semantics.
