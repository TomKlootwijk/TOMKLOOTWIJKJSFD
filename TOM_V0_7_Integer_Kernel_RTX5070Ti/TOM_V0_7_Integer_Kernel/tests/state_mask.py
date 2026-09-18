#!/usr/bin/env python3
"""Verify all-shard CUDA state-mask files against an independent packed oracle."""
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
from tom.compiler import compile_definition, reference_tick, save_state, seed_words

MASK_MAGIC = b'TOM7MSK\0'
MASK_VERSION = 1
FULL = (1 << 32) - 1


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def fixture_image():
    return compile_definition({
        'name': 'all-shard mask export regression',
        'state': {
            'hash': {'hash': 0xFFFFFFFF},
            'counter5': {'counter_bit': 5},
            'counter31': {'counter_bit': 31},
            'counter32': {'counter_bit': 32},
            'counter63': {'counter_bit': 63},
            'flip': 1,
            'mask': {'hash': 0x80000001},
        },
        'rules': {
            'XOR3': 0x96,
            'NOT': 0x55,
            'D': {'rows': ['ZERO', 'hash', 'counter5', 'ONE',
                           'mask', 'flip', 'counter63', 'hash']},
        },
        'expressions': {
            'hash_next': {'rule': 'XOR3', 'args': ['hash', 'counter5', 'mask']},
            'flip_next': {'rule': 'NOT', 'args': ['flip']},
            'mask_next': {'rule': 'D', 'args': ['hash', 'mask', 'flip']},
        },
        'next': {'hash': 'hash_next', 'flip': 'flip_next', 'mask': 'mask_next'},
    })


def mask_bytes(slot, words, epoch, values):
    require(len(values) == words, 'oracle mask extent')
    return struct.pack('<8sIIQQ', MASK_MAGIC, slot, MASK_VERSION, words * 32, epoch) + struct.pack(f'<{words}I', *values)


def read_mask(path):
    raw = path.read_bytes()
    require(len(raw) >= 32, 'mask header truncated')
    magic, slot, version, lanes, epoch = struct.unpack_from('<8sIIQQ', raw)
    require(magic == MASK_MAGIC, 'mask magic differs')
    require(version == MASK_VERSION, 'mask version differs')
    require(lanes > 0 and lanes % 32 == 0, 'mask lanes are not complete packed words')
    words = lanes // 32
    require(len(raw) == 32 + words * 4, 'mask payload truncated or has trailing bytes')
    values = list(struct.unpack_from(f'<{words}I', raw, 32))
    return slot, lanes, epoch, values, raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ROOT / 'verification/state_mask.json')
    args = parser.parse_args()
    exe = args.exe.resolve()
    hardware = json.loads(subprocess.check_output([str(exe), '--info'], text=True))
    image = fixture_image()
    slots = image.header[8]
    require(len(image.words) * 4 <= hardware['shared_optin_bytes'], 'test image must fit shared memory')
    state_slots = image.metadata['state_slots']
    runs = []
    rejected = []
    oracle_cache = {}

    def oracle(words, ticks, resumed):
        key = (words, ticks, resumed)
        if key not in oracle_cache:
            initial = seed_words(image, words)
            if resumed:
                # Each plane differs in every shard, including high counter
                # planes that would be zero for these small seeded workloads.
                initial = [(value ^ (((slot + 1) * 0x9E3779B9 + word * 0x85EBCA6B) & FULL))
                           for slot in range(slots)
                           for word, value in enumerate(initial[slot * words:(slot + 1) * words])]
            final = initial
            for _ in range(ticks):
                final = reference_tick(image, final, words)
            oracle_cache[key] = initial, final
        return oracle_cache[key]

    with tempfile.TemporaryDirectory(prefix='tom-state-mask-') as directory:
        work = Path(directory)
        program = work / 'mask_fixture.tsdf'
        image.save(program)
        program_sha256 = hashlib.sha256(program.read_bytes()).hexdigest()

        def execute(backend, evaluator, scenario, *, words=19, ticks=2, warmup=0,
                    cap=7, field='mask', resumed=False, explicit_plane=None):
            name = f'{backend}_{evaluator}_{scenario}'
            slot = state_slots[field]
            output = work / f'{name}.tmask'
            source = work / f'{name}_input.tsdf'
            initial_epoch = (1 << 40) + 31 if resumed else 0
            if explicit_plane is None:
                initial, final = oracle(words, ticks, resumed)
                expected_plane = final[slot * words:(slot + 1) * words]
            else:
                require(ticks == 0 and not resumed, name + ': explicit oracle must describe seeded zero-tick state')
                initial = None
                expected_plane = explicit_plane
            expected_epoch = initial_epoch + ticks
            expected_raw = mask_bytes(slot, words, expected_epoch, expected_plane)
            # Export must truncate existing output instead of retaining a stale
            # tail. Only temporary test files are overwritten.
            output.write_bytes(b'old mask bytes\xA5' * (len(expected_raw) // 14 + 20))
            command = [str(exe), '--program', str(program), '--backend', backend,
                       '--evaluator', evaluator, '--ticks', str(ticks), '--warmup', str(warmup),
                       '--shard-words', str(cap), '--state-mask-out', str(output),
                       '--state-mask-slot', str(slot), '--count-state', str(slot), '--verify']
            if resumed:
                save_state(source, initial, slots, words, initial_epoch)
                source_bytes = source.read_bytes()
                command += ['--data', str(source)]
            else:
                command += ['--lanes', str(words * 32)]
            completed = subprocess.run(command, capture_output=True, text=True)
            require(completed.returncode == 0, name + ': ' + completed.stderr)
            report = json.loads(completed.stdout)
            actual_slot, actual_lanes, actual_epoch, actual_plane, raw = read_mask(output)
            require((actual_slot, actual_lanes, actual_epoch) == (slot, words * 32, expected_epoch),
                    name + ': mask header metadata')
            require(raw == expected_raw and actual_plane == expected_plane,
                    name + ': complete global-order mask differs from independent oracle')
            if resumed:
                require(source.read_bytes() == source_bytes, name + ': export changed resumed input')
            require(report['gpu_executed'] is True, name + ': CUDA execution flag')
            require(report['compute_executed'] is (ticks > 0), name + ': zero-tick compute flag')
            require(report['lanes'] == words * 32 and report['epoch'] == expected_epoch, name + ': runner extent/epoch')
            shard_count = (words + cap - 1) // cap if cap else 1
            require(report['shards'] == shard_count, name + ': forced shard count')
            require(report['compute_launches'] == ticks * shard_count, name + ': measured compute launches')
            require(report['warmup_compute_launches'] == warmup * shard_count, name + ': warmup compute launches')
            require(report['state_mask_in_compute_timing'] is False, name + ': mask export included in compute timing')
            export = report['state_mask_export']
            require(Path(export['path']).resolve() == output.resolve(), name + ': exported path report')
            require((export['slot'], export['version'], export['lanes'], export['epoch']) ==
                    (slot, MASK_VERSION, words * 32, expected_epoch), name + ': export metadata report')
            require(export['scope'] == 'all_lanes_all_shards', name + ': export scope')
            require(export['data_bytes'] == words * 4 and export['file_bytes'] == len(raw), name + ': export byte counts')
            ones = sum(value.bit_count() for value in expected_plane)
            counts = report['state_counts']
            require(len(counts) == 1 and counts[0]['slot'] == slot, name + ': mask state count selection')
            require(counts[0]['ones'] == ones and counts[0]['zeros'] == words * 32 - ones,
                    name + ': exported bitmap/popcount consistency')
            require(counts[0]['lanes'] == words * 32 and counts[0]['scope'] == 'all_lanes_all_shards',
                    name + ': population count global scope')
            runs.append({'scenario': scenario, 'report': report, 'expected_ones': ones,
                         'mask_sha256': hashlib.sha256(raw).hexdigest(), 'file_bytes': len(raw)})

        for backend in ('texture', 'global', 'shared'):
            for evaluator in ('field', 'lowered'):
                execute(backend, evaluator, 'seeded_single_word_shards', cap=1, field='hash')
                execute(backend, evaluator, 'warmed_dynamic_mask', ticks=3, warmup=3)
                execute(backend, evaluator, 'resumed_high_counter_plane', resumed=True, warmup=2, field='counter63')
                execute(backend, evaluator, 'zero_ticks_warmed_resume', resumed=True, ticks=0, warmup=3)

        # The first shard itself exceeds a 1 MiB transfer buffer, and the last
        # six words belong to a second shard. Counter bit 5 is all ones in odd
        # global words and all zeros in even global words, giving a direct oracle.
        large_words = (1 << 18) + 9
        execute('global', 'lowered', 'streaming_buffer_and_shard_boundary', words=large_words,
                ticks=0, cap=(1 << 18) + 3, field='counter5',
                explicit_plane=[FULL if word & 1 else 0 for word in range(large_words)])

        completed = subprocess.run([str(exe), '--program', str(program), '--backend', 'global',
                                    '--lanes', '32', '--ticks', '0'], capture_output=True, text=True)
        require(completed.returncode == 0, 'disabled export: ' + completed.stderr)
        disabled_report = json.loads(completed.stdout)
        require(disabled_report['state_mask_export'] is None, 'disabled mask export must report null')
        require(disabled_report['state_mask_in_compute_timing'] is False, 'disabled mask timing flag')

        invalid_output = work / 'invalid.tmask'
        invalid_options = [
            ('missing_slot', ['--state-mask-out', str(invalid_output)]),
            ('missing_path', ['--state-mask-slot', '0']),
            ('slot_out_of_range', ['--state-mask-out', str(invalid_output), '--state-mask-slot', str(slots)]),
            ('negative_slot', ['--state-mask-out', str(invalid_output), '--state-mask-slot', '-1']),
        ]
        for scenario, options in invalid_options:
            completed = subprocess.run([str(exe), '--program', str(program), '--lanes', '32', *options],
                                       capture_output=True, text=True)
            require(completed.returncode != 0, scenario + ': invalid mask options accepted')
            require(not invalid_output.exists(), scenario + ': invalid options created an output file')
            rejected.append({'scenario': scenario, 'stderr': completed.stderr.strip()})

    result = {'status': 'PASS', 'gpu_executed': True, 'hardware': hardware,
              'program_sha256': program_sha256, 'executable_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
              'counts': {'mask_gpu_runs': len(runs), 'disabled_export_runs': 1,
                         'invalid_option_runs': len(rejected), 'backends': 3, 'evaluators': 2},
              'scope': ('Every exported mask byte checked against an independent minterm oracle, including header, '
                        'global word order, population totals, existing-file truncation, seeded and resumed data, '
                        'warmup and zero ticks. Includes a selected plane larger than 1 MiB crossing both a transfer '
                        'chunk and shard boundary; this checks output correctness, not the exporter peak allocation.'),
              'runs': runs, 'disabled_export_report': disabled_report, 'rejected_options': rejected}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'counts': result['counts'], 'output': str(args.out)}, indent=2))


if __name__ == '__main__':
    main()
