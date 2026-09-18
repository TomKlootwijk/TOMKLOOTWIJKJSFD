#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
cmake -S . -B build -DTOM_ENABLE_CUDA=ON -DTOM_CUDA_ARCH="${TOM_CUDA_ARCH:-120}" -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
printf '\nNext: python tools/validate_laptop.py --exe build/tom_cuda --quick --out verification/laptop\n'
