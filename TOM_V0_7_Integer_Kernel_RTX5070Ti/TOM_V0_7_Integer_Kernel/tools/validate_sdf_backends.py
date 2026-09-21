"""Compare one lowered SDF/Klein closure across Python, CPU and CUDA.

The semantic layer is intentionally above the fixed native ABI. This command
therefore creates a canonical semantic fixture, lowers it, evaluates the exact
native image with the independent Python reference, and compares every output
word from each available executable. CUDA is reported as skipped when no
executable or device is available; ``--require-cuda`` turns that into failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from tom import native  # noqa: E402
from tom.sdf_core import KleinPack, Registry, SDFTerm, Sign  # noqa: E402
from tom.sdf_lowering import lower_term  # noqa: E402


def fixture() -> Registry:
    registry = Registry()
    klein = KleinPack("fixture", "root")
    registry.register(SDFTerm("decl:T", "DECL", "declaration",
                              sign=Sign.UNKNOWN, klein=klein))
    registry.register(SDFTerm("decl:phi", "DECL", "declaration",
                              sign=Sign.UNKNOWN, klein=klein))
    registry.register(SDFTerm("j", "J", "field", operands=("decl:T",), klein=klein))
    registry.register(SDFTerm("c", "C", "field", operands=("j",), klein=klein))
    registry.register(SDFTerm("invlog", "INVLOG", "field",
                              operands=("decl:phi",), klein=klein))
    registry.register(SDFTerm("e", "E", "field", operands=("c", "invlog"), klein=klein))
    registry.register(SDFTerm("arch", "ARCH", "field", operands=("c", "e"), klein=klein))
    return registry


def run_one(executable: Path, input_path: Path, output_path: Path,
            report_path: Path, *, cuda: bool = False) -> dict:
    command = [str(executable), "--input", str(input_path),
               "--output", str(output_path), "--json", str(report_path)]
    if cuda:
        command += ["--verify", "--block", "128"]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(
            f"{executable.name} failed ({completed.returncode}): "
            f"{completed.stderr.strip() or completed.stdout.strip()}")
    return json.loads(report_path.read_text(encoding="utf-8"))


def output_values(path: Path, config: native.Config) -> list[int]:
    actual_config, values = native.read_batch(path, output=True)
    if actual_config != config:
        raise AssertionError(f"{path} returned a different native configuration")
    if len(values) != 1:
        raise AssertionError(f"{path} did not contain exactly one result")
    return values[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu", type=Path,
                        default=ROOT / "build-cuda128" / "Release" / "tom_native_cpu.exe")
    parser.add_argument("--cuda", type=Path,
                        default=ROOT / "build-cuda128" / "Release" / "tom_native_cuda.exe")
    parser.add_argument("--out", type=Path, default=ROOT / "verification" / "sdf_backends")
    parser.add_argument("--require-cuda", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    registry = fixture()
    lowered = lower_term("arch", registry)
    config = native.Config(len(native.NativeCase.from_term(lowered.native_term).records), 1, 0, 0)
    case = native.NativeCase.from_term(lowered.native_term)
    input_words = case.pack(config)
    reference_words = native.evaluate_words(input_words, config)
    input_path = args.out / "sdf_arch.ton"
    reference_path = args.out / "sdf_arch.reference.tor"
    native.write_batch(input_path, config, [input_words])
    native.write_batch(reference_path, config, [reference_words], output=True)
    expected_digest = hashlib.sha256(reference_path.read_bytes()).hexdigest()

    report: dict = {
        "semantic_id": lowered.semantic_id,
        "semantic_digest": lowered.semantic_digest,
        "registry_digest": registry.digest(),
        "closure_digest": lowered.sidecar["closure_digest"],
        "native_term": native_term_json(lowered.native_term),
        "reference_output_sha256": expected_digest,
        "fixture": str(input_path.resolve()),
        "backends": {},
    }
    for label, executable, is_cuda in (("cpu", args.cpu, False), ("cuda", args.cuda, True)):
        if not executable.is_file():
            if is_cuda and not args.require_cuda:
                report["backends"][label] = {"status": "skipped", "reason": "executable missing"}
                continue
            raise FileNotFoundError(executable)
        output_path = args.out / f"sdf_arch.{label}.tor"
        runner_path = args.out / f"sdf_arch.{label}.json"
        try:
            runner = run_one(executable, input_path, output_path, runner_path, cuda=is_cuda)
        except RuntimeError as exc:
            if is_cuda and not args.require_cuda:
                report["backends"][label] = {"status": "skipped", "reason": str(exc)}
                continue
            raise
        actual_words = output_values(output_path, config)
        if actual_words != reference_words:
            raise AssertionError(f"{label} output differs from Python native reference")
        report["backends"][label] = {
            "status": "passed",
            "output_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
            "all_words_equal": True,
            "runner": runner,
        }
    report_path = args.out / "sdf_arch.backends.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def native_term_json(term: native.Term) -> list:
    if term.op in (native.Op.DECL, native.Op.SELF):
        return [term.op.name, term.aux]
    if term.op == native.Op.LATER_T:
        return [term.op.name, term.aux, native_term_json(term.args[0])]
    return [term.op.name, *(native_term_json(arg) for arg in term.args)]


if __name__ == "__main__":
    raise SystemExit(main())
