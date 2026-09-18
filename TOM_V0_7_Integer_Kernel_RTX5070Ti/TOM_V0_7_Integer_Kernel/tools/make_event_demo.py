#!/usr/bin/env python3
"""Build and run an editable, stateful event admission example on the TOM kernel."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from tom.builder import Builder
from tom.compiler import FULL, Image, lane_value, load_state, reference_tick, save_state, seed_words

CHECKS = ('sequence_forward', 'time_forward', 'elapsed_exact',
          'dependency_not_future', 'facts_retained')
MEMORY = ('last_sequence', 'last_time', 'retained_facts')
INPUTS = ('event_sequence', 'event_time', 'claimed_elapsed',
          'latest_dependency', 'proposed_facts')


def build_policy():
    b = Builder('Stateful event admission: finite ordering and fact-retention policy')
    present = b.bit('proposal_present')
    last_seq = b.bits('last_sequence', 16)
    last_time = b.bits('last_time', 16)
    facts = b.bits('retained_facts', 8)
    seq = b.bits('event_sequence', 16)
    now = b.bits('event_time', 16)
    elapsed = b.bits('claimed_elapsed', 16)
    dependency = b.bits('latest_dependency', 16)
    proposed = b.bits('proposed_facts', 8)
    # The extra bit prevents a negative elapsed difference from matching a
    # wrapped uint16 claim (e.g. 104 - 105 must not equal 65535).
    difference = b.sub(now + ['ZERO'], last_time + ['ZERO'])
    checks = [
        b.less(last_seq, seq),
        b.less(last_time, now),
        b.eq(difference, elapsed + ['ZERO']),
        b.inverse(b.less(now, dependency)),
        b.reduce('AND', [b.gate('OR', b.inverse(old), new)
                         for old, new in zip(facts, proposed)], 'ONE'),
    ]
    accepted = b.reduce('AND', [present, *checks], 'ONE')
    for name, expression in zip(CHECKS, checks):
        b.output(name, expression)
    b.output('accepted', accepted)
    # These bindings are the actual transaction commit. A rejected proposal
    # leaves all three persistent fields unchanged in the kernel itself.
    for old, candidate in ((last_seq, seq), (last_time, now), (facts, proposed)):
        b.spec['next'].update(zip(old, b.mux_bits(old, candidate, accepted)))
    # Consume each host submission once. Subsequent ticks cannot resubmit it
    # unless the host deliberately sets proposal_present again.
    b.spec['next']['proposal_present'] = 'ZERO'
    b.spec['outputs'] = [*CHECKS, 'accepted', *MEMORY]
    return b


def proposal(seq, time, elapsed, dependency, facts):
    return dict(zip(INPUTS, (seq, time, elapsed, dependency, facts)))


def default_cases():
    initial = {'last_sequence': 40, 'last_time': 100, 'retained_facts': 3}
    first = proposal(41, 105, 5, 100, 7)
    good_second = proposal(42, 110, 5, 105, 15)
    recovery = proposal(42, 110, 5, 105, 15)
    streams = []
    examples = [
        ('append', 'Three valid appends extend the accepted state.', good_second,
         proposal(43, 115, 5, 110, 31), [1, 1, 1]),
        ('replay', 'Duplicate sequence is rejected; a later fresh event succeeds.',
         proposal(41, 110, 5, 105, 15), recovery, [1, 0, 1]),
        ('backward_time', 'A regressed timestamp and wrapped elapsed claim are rejected.',
         proposal(42, 104, 65535, 100, 15), recovery, [1, 0, 1]),
        ('wrong_elapsed', 'An incorrect elapsed claim fails despite a forward timestamp.',
         proposal(42, 110, 4, 105, 15), recovery, [1, 0, 1]),
        ('future_dependency', 'A dependency timestamp beyond this event is rejected.',
         proposal(42, 110, 5, 111, 15), recovery, [1, 0, 1]),
        ('fact_erasure', 'A candidate cannot clear an already retained fact bit.',
         proposal(42, 110, 5, 105, 3), recovery, [1, 0, 1]),
        ('combined_recovery', 'All five checks fail, then valid recovery uses unchanged state.',
         proposal(40, 104, 65535, 106, 1), recovery, [1, 0, 1]),
    ]
    for name, purpose, second, third, decisions in examples:
        streams.append({'name': name, 'purpose': purpose, 'initial': dict(initial),
                        'events': [dict(first), second, third],
                        'expected_acceptance': decisions})
    streams.append({
        'name': 'uint16_boundary',
        'purpose': '65535 is valid; implicit rollover to zero is rejected.',
        'initial': {'last_sequence': 65533, 'last_time': 65533, 'retained_facts': 3},
        'events': [proposal(65534, 65534, 1, 65533, 7),
                   proposal(65535, 65535, 1, 65534, 15),
                   proposal(0, 0, 1, 0, 31)],
        'expected_acceptance': [1, 1, 0],
    })
    return {'description': 'Eight independent streams, three submitted events per stream.',
            'fact_legend': {'0': 'record received', '1': 'schema checked',
                           '2': 'payload processed', '3': 'result recorded',
                           '4': 'receipt recorded'},
            'streams': streams}


def integer_oracle(memory, event):
    """Ordinary integer/set comparisons, independent of circuit construction."""
    checks = dict(zip(CHECKS, (
        event['event_sequence'] > memory['last_sequence'],
        event['event_time'] > memory['last_time'],
        event['event_time'] - memory['last_time'] == event['claimed_elapsed'],
        event['latest_dependency'] <= event['event_time'],
        (memory['retained_facts'] & ~event['proposed_facts']) == 0,
    )))
    accepted = all(checks.values())
    after = ({'last_sequence': event['event_sequence'], 'last_time': event['event_time'],
              'retained_facts': event['proposed_facts']} if accepted else dict(memory))
    return {**checks, 'accepted': accepted, **after}


def write_fields(image, state, words, lane, fields):
    """Inject host submissions without resetting the persisted result state."""
    for name, value in fields.items():
        bits = image.metadata['groups'].get(name, {'bits': [name]})['bits']
        if type(value) not in (int, bool) or not 0 <= value < (1 << len(bits)):
            raise ValueError(f'{name}: expected unsigned {len(bits)}-bit integer')
        for bit, field in enumerate(bits):
            index = image.metadata['state_slots'][field] * words + lane // 32
            mask = 1 << (lane % 32)
            if (value >> bit) & 1:
                state[index] |= mask
            else:
                state[index] &= FULL ^ mask


def read_fields(image, state, words, lane):
    result = {}
    for name in image.metadata['outputs']:
        bits = image.metadata['groups'].get(name, {'bits': [name]})['bits']
        slots = [image.metadata['state_slots'][field] for field in bits]
        result[name] = lane_value(state, words, slots, lane)
    return result


def validate_cases(cases):
    streams = cases['streams']
    if not streams or any(not stream['events'] for stream in streams):
        raise ValueError('at least one stream and event per stream are required')
    ticks = len(streams[0]['events'])
    if any(len(stream['events']) != ticks for stream in streams):
        raise ValueError('streams must contain the same number of submitted events')
    if len({stream['name'] for stream in streams}) != len(streams):
        raise ValueError('stream names must be unique')
    for stream in streams:
        if set(stream['initial']) != set(MEMORY):
            raise ValueError('initial must contain exactly the three persistent fields')
        if any(set(event) != set(INPUTS) for event in stream['events']):
            raise ValueError('events must contain exactly the five proposal fields')
        expected = stream.get('expected_acceptance')
        if expected is not None and (len(expected) != ticks or any(x not in (0, 1) for x in expected)):
            raise ValueError('expected_acceptance must contain one Boolean per tick')
    return ticks


def run_demo(image, program, cases, exe, backend, output):
    ticks = validate_cases(cases)
    streams = cases['streams']
    words = (len(streams) + 31) // 32
    executions = []
    first_results = None
    with tempfile.TemporaryDirectory(prefix='tom-event-demo-') as temporary:
        temporary = Path(temporary)
        for evaluator in ('field', 'lowered'):
            state = seed_words(image, words)
            memory = [copy.deepcopy(stream['initial']) for stream in streams]
            for lane, values in enumerate(memory):
                write_fields(image, state, words, lane, values)
            observations = []
            reports = []
            for tick in range(ticks):
                for lane, stream in enumerate(streams):
                    write_fields(image, state, words, lane,
                                 {'proposal_present': 1, **stream['events'][tick]})
                expected_state = reference_tick(image, state, words)
                input_path = temporary / 'input.tsdf'
                result_path = temporary / 'result.tsdf'
                save_state(input_path, state, image.header[8], words, epoch=tick)
                command = [str(exe), '--program', str(program), '--data', str(input_path),
                           '--ticks', '1', '--evaluator', evaluator, '--out', str(result_path)]
                if backend != 'cpu':
                    command += ['--backend', backend, '--verify']
                completed = subprocess.run(command, check=True, capture_output=True, text=True)
                reports.append(json.loads(completed.stdout))
                slots, actual_words, epoch, state = load_state(result_path)
                if slots != image.header[8] or actual_words != words or epoch != tick + 1:
                    raise AssertionError('state extent or resumed epoch is incorrect')
                if state != expected_state:
                    raise AssertionError(f'{evaluator}: complete state differs from minterm evaluator')
                for lane, stream in enumerate(streams):
                    event = stream['events'][tick]
                    expected = integer_oracle(memory[lane], event)
                    if 'expected_acceptance' in stream and expected['accepted'] != stream['expected_acceptance'][tick]:
                        raise AssertionError(f'{stream["name"]}: declared expected decision is wrong at tick {tick + 1}')
                    actual = read_fields(image, state, words, lane)
                    if actual != expected:
                        raise AssertionError((evaluator, stream['name'], tick + 1, actual, expected))
                    observations.append({'stream': stream['name'], 'tick': tick + 1,
                                         'before': dict(memory[lane]), 'event': event,
                                         'checks': {name: bool(actual[name]) for name in CHECKS},
                                         'accepted': bool(actual['accepted']),
                                         'after': {name: actual[name] for name in MEMORY}})
                    memory[lane] = {name: actual[name] for name in MEMORY}
            # A tick with no new submission must never commit an event.
            dormant = reference_tick(image, state, words)
            save_state(input_path, state, image.header[8], words, epoch=ticks)
            completed = subprocess.run(command, check=True, capture_output=True, text=True)
            reports.append(json.loads(completed.stdout))
            _, _, idle_epoch, idle = load_state(result_path)
            if idle != dormant or idle_epoch != ticks + 1:
                raise AssertionError('idle consumption tick differs from independent evaluator')
            for lane in range(words * 32):
                actual = read_fields(image, idle, words, lane)
                if actual['accepted']:
                    raise AssertionError('proposal was admitted without a fresh submission')
                if lane < len(streams) and any(actual[name] != memory[lane][name] for name in MEMORY):
                    raise AssertionError('idle tick changed persisted state')
            if first_results is not None and observations != first_results:
                raise AssertionError('field and lowered decisions differ')
            first_results = observations
            executions.append({'evaluator': evaluator, 'observations': observations, 'run_reports': reports})
    decisions = [row['accepted'] for row in first_results]
    report = {'status': 'PASS', 'backend': backend, 'gpu_executed': backend != 'cpu',
              'streams': len(streams), 'submitted_ticks': ticks, 'idle_ticks': 1,
              'decisions_per_evaluator': len(decisions), 'accepted_per_evaluator': sum(decisions),
              'rejected_per_evaluator': len(decisions) - sum(decisions),
              'allocated_lanes': words * 32, 'padding_lanes': words * 32 - len(streams),
              'validation': ['plain integer policy oracle', 'complete minterm state comparison',
                             'field/lowered equivalence', 'resumed epoch and state', 'idle submission consumption'],
              'scope': 'Finite supplied-data policy; no timestamp authentication, dependency existence proof, or physical causality proof.',
              'program': str(program), 'executions': executions}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Checks: sequence / time / elapsed / dependency / facts (PASS=1, FAIL=0)')
    for stream in streams:
        for row in first_results:
            if row['stream'] != stream['name']:
                continue
            checks = ' '.join(str(int(row['checks'][name])) for name in CHECKS)
            memory = row['after']
            print(f'{stream["name"]:19} tick {row["tick"]}: {checks}  '
                  f'{"ACCEPT" if row["accepted"] else "REJECT"}  '
                  f'seq={memory["last_sequence"]} time={memory["last_time"]} facts=0x{memory["retained_facts"]:02x}')
    print(f'PASS: both evaluators, {len(decisions)} decisions each; {sum(decisions)} accepted, '
          f'{len(decisions)-sum(decisions)} rejected. Saved {output}')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, help='also execute and validate with this tom_cpu or tom_cuda binary')
    parser.add_argument('--backend', choices=('cpu', 'texture', 'global', 'shared'), default='cpu')
    parser.add_argument('--cases', type=Path, default=ROOT / 'examples/event_admission_cases.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'verification/event_admission_cpu.json')
    args = parser.parse_args()
    if args.backend != 'cpu' and args.exe is None:
        parser.error('--backend requires --exe')
    builder = build_policy()
    source = ROOT / 'examples/event_admission.json'
    program = source.with_suffix('.tsdf')
    source.write_text(json.dumps(builder.spec, indent=2) + '\n', encoding='utf-8')
    image = builder.compile()
    image.save(program)
    if not args.cases.exists():
        args.cases.parent.mkdir(parents=True, exist_ok=True)
        args.cases.write_text(json.dumps(default_cases(), indent=2) + '\n', encoding='utf-8')
    print(f'Built {program}: {image.header[8]} state bits, {image.header[5]} scheduled values, '
          f'{image.header[9]} scratch slots.')
    if args.exe:
        cases = json.loads(args.cases.read_text(encoding='utf-8'))
        run_demo(image, program, cases, args.exe.resolve(), args.backend, args.out.resolve())


if __name__ == '__main__':
    main()
