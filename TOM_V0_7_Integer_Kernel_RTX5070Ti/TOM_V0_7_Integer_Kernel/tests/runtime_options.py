#!/usr/bin/env python3
"""Verify that CUDA warmup preserves complete snapshots, traces and epochs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from tom.compiler import Image, load_state, reference_tick, seed_words


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ROOT / 'verification/runtime_options.json')
    args = parser.parse_args()
    exe = args.exe.resolve()
    program = ROOT / 'examples/self_reference.tsdf'
    image = Image.load(program)
    info = json.loads(subprocess.check_output([str(exe), '--info'], text=True))
    require(len(image.words) * 4 <= info['shared_optin_bytes'], 'test image must fit shared memory')
    words = 3
    runs = []
    comparisons = 0

    with tempfile.TemporaryDirectory(prefix='tom-runtime-options-') as directory:
        work = Path(directory)

        def execute(backend, evaluator, scenario, ticks, warmup, source=None):
            name = f'{backend}_{evaluator}_{scenario}_warmup{warmup}'
            output = work / f'{name}.tsdf'
            trace = work / f'{name}.ttrace'
            command = [str(exe), '--program', str(program), '--backend', backend,
                       '--evaluator', evaluator, '--ticks', str(ticks),
                       '--warmup', str(warmup), '--verify', '--out', str(output),
                       '--trace', str(trace)]
            if source is None:
                initial_epoch = 0
                initial = seed_words(image, words)
                command += ['--lanes', str(words * 32)]
            else:
                source_slots, source_words, initial_epoch, initial = load_state(source)
                require(source_slots == image.header[8] and source_words == words, name + ': source extent')
                command += ['--data', str(source)]
            completed = subprocess.run(command, capture_output=True, text=True)
            require(completed.returncode == 0, name + ': ' + completed.stderr)
            report = json.loads(completed.stdout)
            slots, actual_words, epoch, actual = load_state(output)
            require(report['gpu_executed'] is True, name + ': CUDA backend was not reported')
            require(report['sample_verified'] is True, name + ': sample verification missing')
            require(report['compute_executed'] is (ticks > 0), name + ': compute execution flag')
            require(report['ticks'] == ticks and report['warmup_ticks'] == warmup, name + ': tick counts')
            require(report['shards'] == 1, name + ': unexpected sharding')
            require(report['compute_launches'] == ticks, name + ': compute launch count')
            require(report['warmup_compute_launches'] == warmup, name + ': warmup launch count')
            require(report['epoch'] == epoch == initial_epoch + ticks, name + ': warmup changed epoch')
            require(slots == image.header[8] and actual_words == words, name + ': snapshot extent')

            raw_trace = trace.read_bytes()
            magic, trace_slots, trace_words, start, frames = struct.unpack_from('<8sIIQQ', raw_trace)
            require(magic == b'TOM7TRC\0', name + ': trace magic')
            require((trace_slots, trace_words, start, frames) == (slots, words, initial_epoch, ticks + 1),
                    name + ': trace contains warmup frames or incorrect epoch')
            frame_size = slots * words * 4
            require(len(raw_trace) == 32 + frame_size * frames, name + ': trace extent')
            expected = initial
            for frame in range(frames):
                state = list(struct.unpack_from(f'<{slots * words}I', raw_trace, 32 + frame * frame_size))
                require(state == expected, name + f': frame {frame} differs from independent oracle')
                if frame < ticks:
                    expected = reference_tick(image, expected, words)
            require(actual == expected, name + ': final snapshot differs from independent oracle')
            if ticks == 0 and source is not None:
                require(output.read_bytes() == source.read_bytes(), name + ': zero-tick output changed input')
            runs.append({'scenario': scenario, 'report': report,
                         'state_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                         'trace_sha256': hashlib.sha256(raw_trace).hexdigest()})
            return output, trace

        for backend in ('texture', 'global', 'shared'):
            for evaluator in ('field', 'lowered'):
                baseline = execute(backend, evaluator, 'seeded', 3, 0)
                for warmup in (2, 3):
                    warmed = execute(backend, evaluator, 'seeded', 3, warmup)
                    for original, candidate in zip(baseline, warmed):
                        require(original.read_bytes() == candidate.read_bytes(),
                                f'{backend}/{evaluator}: seeded bytes differ after warmup {warmup}')
                    comparisons += 1
                for scenario, ticks in (('resumed', 2), ('zero_ticks', 0)):
                    cold = execute(backend, evaluator, scenario, ticks, 0, baseline[0])
                    warmed = execute(backend, evaluator, scenario, ticks, 3, baseline[0])
                    for original, candidate in zip(cold, warmed):
                        require(original.read_bytes() == candidate.read_bytes(),
                                f'{backend}/{evaluator}: {scenario} bytes differ after warmup')
                    comparisons += 1

    report = {'status': 'PASS', 'gpu_executed': True, 'hardware': info,
              'program': program.name, 'program_sha256': hashlib.sha256(program.read_bytes()).hexdigest(),
              'executable_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
              'counts': {'gpu_runs': len(runs), 'full_state_and_trace_equalities': comparisons,
                         'backends': 3, 'evaluators': 2, 'lanes_per_run': words * 32},
              'scope': 'Full snapshots and every trace frame checked against an independent oracle; warmup preserves seed and resumed input, epoch and zero-tick outputs.',
              'runs': runs}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'counts': report['counts'], 'output': str(args.out)}, indent=2))


if __name__ == '__main__':
    main()
