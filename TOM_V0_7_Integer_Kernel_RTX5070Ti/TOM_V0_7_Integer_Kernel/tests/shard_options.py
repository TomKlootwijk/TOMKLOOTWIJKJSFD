#!/usr/bin/env python3
"""Regress CUDA sharding, verification coverage, state counts and grid limits."""
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
from tom.compiler import compile_definition, load_state, reference_tick, save_state, seed_words

FULL64 = (1 << 64) - 1
VERIFY_SCOPE = 'first_and_last_up_to_64_words_per_shard'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(words):
    value = 1469598103934665603
    for word in words:
        value = ((value ^ word) * 1099511628211) & FULL64
    return value


def window(state, slots, words, first, count):
    return [value for slot in range(slots)
            for value in state[slot * words + first:slot * words + first + count]]


def sample_windows(words):
    result = [(0, min(64, words))]
    if words > 64:
        first = max(64, words - 64)
        result.append((first, words - first))
    return result


def fixture_image():
    # Counter bits beyond 31 exercise wide shift semantics. The smaller counter
    # bits and two distinct hash seeds expose an incorrect shard-local origin.
    states = {
        'hash_a': {'hash': 0xFFFFFFFF},
        'hash_b': {'hash': 0x80000001},
        'counter0': {'counter_bit': 0},
        'counter5': {'counter_bit': 5},
        'counter6': {'counter_bit': 6},
        'counter10': {'counter_bit': 10},
        'counter31': {'counter_bit': 31},
        'counter32': {'counter_bit': 32},
        'counter63': {'counter_bit': 63},
        'flag': 1,
        'result': {'hash': 0x9E3779B9},
    }
    return compile_definition({
        'name': 'shard offsets and aggregate counts regression',
        'state': states,
        'rules': {
            'XOR3': 0x96,
            'NOT': 0x55,
            'D': {'rows': ['ZERO', 'hash_a', 'counter5', 'ONE',
                           'hash_b', 'result', 'counter6', 'flag']},
        },
        'expressions': {
            'a_next': {'rule': 'XOR3', 'args': ['hash_a', 'counter5', 'result']},
            'b_next': {'rule': 'XOR3', 'args': ['hash_b', 'counter6', 'flag']},
            'flag_next': {'rule': 'NOT', 'args': ['flag']},
            'result_next': {'rule': 'D', 'args': ['hash_a', 'hash_b', 'counter0']},
        },
        'next': {'hash_a': 'a_next', 'hash_b': 'b_next',
                 'flag': 'flag_next', 'result': 'result_next'},
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ROOT / 'verification/shard_options.json')
    args = parser.parse_args()
    exe = args.exe.resolve()
    info = json.loads(subprocess.check_output([str(exe), '--info'], text=True))
    image = fixture_image()
    slots = image.header[8]
    require(len(image.words) * 4 <= info['shared_optin_bytes'], 'test image must fit shared memory')
    runs = []
    rejected = []
    state_slots = image.metadata['state_slots']
    selected_slots = [state_slots[name] for name in ('hash_a', 'result', 'counter5', 'counter63', 'flag')]
    cache = {}

    with tempfile.TemporaryDirectory(prefix='tom-shard-options-') as directory:
        work = Path(directory)
        program = work / 'shard_fixture.tsdf'
        image.save(program)
        program_sha256 = hashlib.sha256(program.read_bytes()).hexdigest()

        def oracle(words, ticks, resumed):
            key = (words, ticks, resumed)
            if key not in cache:
                initial = seed_words(image, words)
                epoch = 0
                if resumed:
                    # Give every plane independently varying data, including the
                    # high counter planes which are zero in these small batches.
                    initial = [(value ^ (((slot + 1) * 0x9E3779B9 + word * 0x85EBCA6B) & 0xFFFFFFFF))
                               for slot in range(slots)
                               for word, value in enumerate(initial[slot * words:(slot + 1) * words])]
                    initial = reference_tick(image, initial, words)
                    epoch = (1 << 32) + 17
                frames = [initial]
                for _ in range(ticks):
                    frames.append(reference_tick(image, frames[-1], words))
                cache[key] = epoch, frames
            return cache[key]

        def execute(backend, evaluator, scenario, words, ticks, warmup,
                    cap=None, blocks_per_sm=None, resumed=False, counted=True, block=128):
            name = f'{backend}_{evaluator}_{scenario}'
            output = work / f'{name}.tsdf'
            trace = work / f'{name}.ttrace'
            source = work / f'{name}_input.tsdf'
            initial_epoch, frames = oracle(words, ticks, resumed)
            expected = frames[-1]
            command = [str(exe), '--program', str(program), '--backend', backend,
                       '--evaluator', evaluator, '--ticks', str(ticks), '--warmup', str(warmup),
                       '--block', str(block), '--verify', '--out', str(output), '--trace', str(trace)]
            if resumed:
                save_state(source, frames[0], slots, words, initial_epoch)
                command += ['--data', str(source)]
            else:
                command += ['--lanes', str(words * 32)]
            if cap is not None:
                command += ['--shard-words', str(cap)]
            if blocks_per_sm is not None:
                command += ['--blocks-per-sm', str(blocks_per_sm)]
            if counted:
                # A repeated slot must be counted once, in first-request order.
                for slot in [*selected_slots, selected_slots[0]]:
                    command += ['--count-state', str(slot)]
            completed = subprocess.run(command, capture_output=True, text=True)
            require(completed.returncode == 0, name + ': ' + completed.stderr)
            report = json.loads(completed.stdout)
            actual_slots, actual_words, epoch, actual = load_state(output)
            shard_limit = cap or words  # All fixtures are below hardware/indexing limits.
            shard_extents = [(first, min(shard_limit, words - first))
                             for first in range(0, words, shard_limit)]
            first_words = shard_extents[0][1]
            effective_blocks = blocks_per_sm if blocks_per_sm is not None else 8
            require(report['gpu_executed'] is True, name + ': CUDA execution missing')
            require(report['backend'] == backend and report['evaluator'] == evaluator, name + ': execution mode')
            require(report['lanes'] == words * 32, name + ': full input extent')
            require(report['shards'] == len(shard_extents), name + ': shard count')
            require(report['shard_words_cap'] == (cap or 0), name + ': requested shard cap/default')
            automatic_cap = report['automatic_shard_words']
            require(automatic_cap >= words, name + ': fixture exceeds automatic shard limit')
            require(report['effective_shard_words'] == min(automatic_cap, cap or automatic_cap),
                    name + ': effective shard limit')
            require(report['blocks_per_sm'] == effective_blocks, name + ': grid limit/default')
            require(report['block_threads'] == block, name + ': block size')
            require(report['ticks'] == ticks and report['warmup_ticks'] == warmup, name + ': tick counts')
            require(report['compute_executed'] is (ticks > 0), name + ': zero-tick execution flag')
            require(report['compute_launches'] == ticks * len(shard_extents), name + ': measured launches')
            require(report['warmup_compute_launches'] == warmup * len(shard_extents), name + ': warmup launches')
            require(report['epoch'] == epoch == initial_epoch + ticks, name + ': epoch changed by sharding/warmup')
            require((actual_slots, actual_words) == (slots, first_words), name + ': exported shard extent')
            require(report['exported_first_shard_lanes'] == first_words * 32, name + ': exported extent report')
            require(actual == window(expected, slots, words, 0, first_words), name + ': first-shard snapshot oracle')

            sample_words = min(first_words, 64)
            require(report['sample_lanes'] == sample_words * 32, name + ': legacy sample extent')
            require(report['sample_digest'] == digest(window(expected, slots, words, 0, sample_words)),
                    name + ': legacy sample digest oracle')
            require(report['sample_verified'] is True, name + ': legacy verification flag')
            summaries = report['shard_summaries']
            require(len(summaries) == len(shard_extents), name + ': omitted shard summaries')
            require(report['shard_summaries_shown'] == len(shard_extents) and report['shard_summaries_omitted'] == 0,
                    name + ': summary truncation accounting')
            verified_words = 0
            expected_sample_digests = []
            for index, ((first, count), summary) in enumerate(zip(shard_extents, summaries)):
                require((summary['index'], summary['first_word'], summary['words']) == (index, first, count),
                        name + f': shard {index} global extent')
                expected_blocks = min((count + block - 1) // block, info['sm_count'] * effective_blocks)
                require(summary['launch_blocks'] == expected_blocks, name + f': shard {index} grid limit')
                windows = sample_windows(count)
                require(len(summary['samples']) == len(windows), name + f': shard {index} sample coverage')
                for (offset, size), sample in zip(windows, summary['samples']):
                    first_global = first + offset
                    expected_digest = digest(window(expected, slots, words, first_global, size))
                    require((sample['first_word'], sample['words']) == (first_global, size),
                            name + f': shard {index} sample global offset')
                    require(sample['digest'] == expected_digest, name + f': shard {index} sample digest oracle')
                    require(sample['verified'] is True, name + f': shard {index} unverified sample')
                    verified_words += size
                    expected_sample_digests.append({'first_word': first_global, 'words': size, 'digest': expected_digest})
            verification = report['verification']
            require(verification['enabled'] is True and verification['scope'] == VERIFY_SCOPE,
                    name + ': verification scope')
            require(verification['shards_verified'] == len(shard_extents), name + ': every shard must be verified')
            require(verification['words_verified'] == verified_words, name + ': distinct verified word count')
            require(verification['lanes_verified'] == verified_words * 32, name + ': verified lane count')
            require(verification['all_lane_words_verified'] is (verified_words == words), name + ': coverage completeness')

            counts = report['state_counts']
            require(len(counts) == (len(selected_slots) if counted else 0), name + ': requested state count cardinality')
            require(report['state_count_launches'] == len(counts) * len(shard_extents), name + ': deduplicated count launches')
            require(report['state_counts_in_compute_timing'] is False, name + ': count work included in compute timer')
            require(report['state_count_elapsed_host_ns'] >= 0, name + ': count elapsed time')
            if not counted:
                require(report['state_count_elapsed_host_ns'] == 0, name + ': unrequested count timing')
            expected_counts = []
            for slot, count_report in zip(selected_slots, counts):
                ones = sum(value.bit_count() for value in expected[slot * words:(slot + 1) * words])
                require(count_report['slot'] == slot, name + ': counted state slot')
                require(count_report['ones'] == ones and count_report['zeros'] == words * 32 - ones,
                        name + f': full-batch popcount oracle for slot {slot}')
                require(count_report['lanes'] == words * 32 and count_report['scope'] == 'all_lanes_all_shards',
                        name + ': state count must cover all shards')
                expected_counts.append({'slot': slot, 'ones': ones, 'zeros': words * 32 - ones})

            resources = report['kernel_resources']
            require(resources['registers_per_thread'] > 0 and resources['local_bytes_per_thread'] >= 0,
                    name + ': kernel register/local resource report')
            require(resources['static_shared_bytes'] >= 0, name + ': static shared memory resource report')
            require(resources['dynamic_shared_bytes'] == (len(image.words) * 4 if backend == 'shared' else 0),
                    name + ': dynamic shared memory resource report')
            require(resources['max_threads_per_block'] >= block, name + ': supported thread count')
            active_blocks = resources['theoretical_active_blocks_per_sm']
            active_warps = resources['theoretical_active_warps_per_sm']
            require(active_blocks > 0 and active_warps == active_blocks * block // 32,
                    name + ': theoretical occupancy arithmetic')
            require(0 < active_warps <= resources['max_warps_per_sm'], name + ': theoretical occupancy bound')

            raw_trace = trace.read_bytes()
            magic, trace_slots, trace_words, start, frame_count = struct.unpack_from('<8sIIQQ', raw_trace)
            require(magic == b'TOM7TRC\0', name + ': trace magic')
            require((trace_slots, trace_words, start, frame_count) == (slots, first_words, initial_epoch, ticks + 1),
                    name + ': trace extent/epoch includes warmup or other shards')
            frame_size = slots * first_words * 4
            require(len(raw_trace) == 32 + frame_count * frame_size, name + ': trace byte extent')
            for frame, full_state in enumerate(frames):
                trace_state = list(struct.unpack_from(f'<{slots * first_words}I', raw_trace, 32 + frame * frame_size))
                require(trace_state == window(full_state, slots, words, 0, first_words),
                        name + f': trace frame {frame} independent oracle')
            if resumed and ticks == 0 and first_words == words:
                require(output.read_bytes() == source.read_bytes(), name + ': zero-tick output differs from input')
            runs.append({'scenario': scenario, 'report': report,
                         'expected_sample_digests': expected_sample_digests, 'expected_state_counts': expected_counts,
                         'state_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                         'trace_sha256': hashlib.sha256(raw_trace).hexdigest()})

        for backend in ('texture', 'global', 'shared'):
            for evaluator in ('field', 'lowered'):
                execute(backend, evaluator, 'defaults', 149, 3, 0, counted=False)
                execute(backend, evaluator, 'single_word_shards', 19, 2, 0, cap=1, blocks_per_sm=1)
                execute(backend, evaluator, 'uneven_warmed_shards', 19, 3, 2, cap=7, blocks_per_sm=2)
                execute(backend, evaluator, 'separate_head_tail_windows', 285, 1, 1, cap=131, blocks_per_sm=8)
                execute(backend, evaluator, 'resumed_shards', 19, 2, 3, cap=7, blocks_per_sm=4, resumed=True)
                execute(backend, evaluator, 'zero_ticks_warmed_shards', 19, 0, 3, cap=7, resumed=True)
                execute(backend, evaluator, 'explicit_automatic_sharding', 19, 2, 0, cap=0, resumed=True)

        # These two grids are large enough to make the per-SM cap observable;
        # the small sharding fixtures above usually launch only one block/shard.
        grid_words = info['sm_count'] * 64 * 3 + 17
        for grid_cap in (1, 3):
            execute('global', 'lowered', f'grid_cap_{grid_cap}', grid_words, 1, 0,
                    cap=0, blocks_per_sm=grid_cap, block=64)
        execute('global', 'lowered', 'adjacent_head_tail_windows', 211, 1, 0, cap=97)

        invalid_options = [
            ('zero_grid_cap', ['--blocks-per-sm', '0']),
            ('negative_shard_cap', ['--shard-words', '-1']),
            ('out_of_range_state_slot', ['--count-state', str(slots)]),
            ('negative_state_slot', ['--count-state', '-1']),
        ]
        for name, options in invalid_options:
            completed = subprocess.run([str(exe), '--program', str(program), '--lanes', '32', *options],
                                       capture_output=True, text=True)
            require(completed.returncode != 0, name + ': invalid option accepted')
            rejected.append({'scenario': name, 'options': options, 'stderr': completed.stderr.strip()})

    result = {'status': 'PASS', 'gpu_executed': True, 'hardware': info,
              'program_sha256': program_sha256, 'executable_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
              'counts': {'gpu_runs': len(runs), 'invalid_option_runs': len(rejected), 'backends': 3, 'evaluators': 2},
              'scope': ('Independent minterm oracle validates every reported shard sample digest, all-lane state popcounts, '
                        'complete exported first-shard snapshots and every trace frame. Covers seed/data global offsets, '
                        'nonmultiple final shards, overlapping-window avoidance, sparse coverage, warmup, zero ticks, '
                        'default/explicit grid caps and theoretical occupancy arithmetic. High counter seeds are tested '
                        'at small global offsets; this does not validate allocations above the uint32 word boundary.'),
              'runs': runs, 'rejected_options': rejected}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'counts': result['counts'], 'output': str(args.out)}, indent=2))


if __name__ == '__main__':
    main()
