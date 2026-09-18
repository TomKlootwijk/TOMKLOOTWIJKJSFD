param([string]$Arch = "120", [string]$CudaVersion = "", [string]$BuildDir = "build-local")
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    if (-not $CudaVersion) {
        $cudaCompiler = Get-Command nvcc -ErrorAction Stop
        $versionText = (& $cudaCompiler.Source --version) -join "`n"
        if ($versionText -notmatch 'release (\d+\.\d+)') { throw "Cannot identify the installed CUDA toolkit version." }
        $CudaVersion = $Matches[1]
    }
    cmake -S . -B $BuildDir -G "Visual Studio 17 2022" -A x64 -T "cuda=$CudaVersion" -DTOM_ENABLE_CUDA=ON "-DTOM_CUDA_ARCH=$Arch"
    if ($LASTEXITCODE -ne 0) { throw "CMake failed. Check nvcc, supported Visual Studio C++ tools and CUDA VS integration." }
    cmake --build $BuildDir --config Release --parallel
    if ($LASTEXITCODE -ne 0) { throw "Build failed; no GPU validation result has been produced." }
    ctest --test-dir $BuildDir -C Release --output-on-failure
    if ($LASTEXITCODE -ne 0) { throw "Integer-core tests failed." }
    Write-Host "Next: python tools\validate_laptop.py --exe $BuildDir\Release\tom_cuda.exe --quick --out verification\laptop"
} finally { Pop-Location }
