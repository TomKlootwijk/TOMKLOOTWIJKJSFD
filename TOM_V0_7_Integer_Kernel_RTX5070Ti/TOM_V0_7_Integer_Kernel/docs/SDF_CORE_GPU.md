# SDF/Klein lowering on CPU and GPU

The semantic core is evaluated by Python, then lowered into the existing
validated TOM/K1 native term ABI. The CUDA executable evaluates that same
finite native image; it does not reinterpret the semantic sidecar or claim
that the GPU is executing an unbounded universal ontology.

The checked-in fixture is the definition-level chain
`T/phi -> J/C and InvLog -> E -> ARCH`. Its declaration table preserves the
native source ids `T=1` and `phi=2`. `tools/validate_sdf_backends.py` performs
these checks:

1. Build the semantic registry and lower `arch`.
2. Pack the lowered native term into the fixed TOM/K1 input format.
3. Evaluate the exact words with the independent Python native reference.
4. Run the CPU executable and compare every output word.
5. Run the CUDA executable with `--verify` and compare every output word again.

From a CUDA-enabled Windows build directory:

```powershell
python tools/validate_sdf_backends.py --require-cuda
```

The command writes a small fixture and report under
`verification/sdf_backends/`. A successful report records `all_words_equal: true`
for both backends and the CUDA runner's device, launch, and verification data.
The CUDA run is optional in source-only environments; omit `--require-cuda` to
record a missing executable or unavailable device as `skipped`.

The native output is a finite backend result. Semantic fields that the fixed
ABI cannot carry remain in the lowering sidecar and its closure digest. A
future ABI may move those fields into device memory, but it must preserve the
same exact comparison and rejection policy.
