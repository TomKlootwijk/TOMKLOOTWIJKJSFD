# Recorded SDF backend check

This directory records the result of
`python tools/validate_sdf_backends.py --require-cuda` on 2026-09-21.

The semantic `arch` fixture, Python reference output, compiled CPU output, and
compiled CUDA output are retained. The three `.tor` files have the same
SHA-256 (`25785bbfd256f5b89e223b659706d7439edbfaff3df34cab34f4bf87d84d40a1`).
The CUDA report records `gpu_executed: true` on an NVIDIA GeForce RTX 5070 Ti
Laptop GPU and verified all one-case output words through the executable's
shared CPU comparison. This is a finite lowering/backend equivalence result;
it is not a claim that the semantic sidecar is executed natively by CUDA.
