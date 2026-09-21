# Build and verify the SDF/Klein core

The semantic reference layer uses only the Python standard library. CMake and
a C++17 compiler are needed for the native CPU backend. CUDA 12.8 or later,
Visual Studio's C++ tools, and an NVIDIA driver are needed for the optional
GPU run.

All commands below start in this directory, the one containing `CMakeLists.txt`.

## CPU-only build

```powershell
cmake -S . -B build-sdf-core -DTOM_ENABLE_CUDA=OFF
cmake --build build-sdf-core --config Release --parallel
ctest --test-dir build-sdf-core -C Release --output-on-failure
python -m unittest discover -s tests -p '*sdf*tests.py' -v
```

The CTest suite includes the existing integer/native checks and the semantic
core/lowering tests. The direct Python command is useful when changing only
the reference layer. Run it from the repository root; running discovery from
the parent directory finds no `tests` package and is not a valid verification.

## CUDA build and semantic fixture

In a Visual Studio Developer PowerShell with CUDA integration installed:

```powershell
cmake -S . -B build-cuda128 -G "Visual Studio 17 2022" -A x64 -T cuda=12.8 `
  -DTOM_ENABLE_CUDA=ON -DTOM_CUDA_ARCH=120
cmake --build build-cuda128 --config Release --parallel
ctest --test-dir build-cuda128 -C Release --output-on-failure
python tools/validate_sdf_backends.py --require-cuda
```

The last command lowers the `T/phi/J/C/E/ARCH` semantic fixture, runs the
Python reference, `tom_native_cpu`, and `tom_native_cuda`, and compares every
result word. It writes reproducible small artifacts under
`verification/sdf_backends/`. Without a CUDA executable or device, omit
`--require-cuda` to record an explicit `skipped` result.

## Inspecting the semantic API

```powershell
python -c "import sys; sys.path.insert(0, 'python'); from tom.sdf_core import make_kernel_terms, SDFKernel; r, root = make_kernel_terms(); print(SDFKernel(r).evaluate(root, now=0, evidence_available=0).status)"
```

The expected result is `Status.OPEN_LAW`, because the small self-reference
fixture deliberately names its application law as unresolved. That is a
successful explicit boundary, not a failed distance calculation.

The snapshot API is used after a valid commit:

```python
snapshot = kernel.snapshot()
restored = SDFKernel.from_snapshot(snapshot)
```

Both methods authenticate the registry and complete predecessor pinion before
the restored process can accept another hop.
