#!/usr/bin/env python3
"""Lint the written TOM contract. Does not construct TOM from a data structure.

JSON keys, lists, finite test cases and ordinary program syntax are editorial
artifacts. They are not intrinsic coordinates, graph nodes or cardinalities of
TOM. This linter can catch specification regressions, not prove completeness.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / 'formalization' / 'TOM_V0_7.json'


def validate(spec: dict) -> list[str]:
    issues = []
    if spec.get('name') != 'TOM' or spec.get('version') != 'V0.7':
        issues.append('Name and version must be TOM / V0.7')
    if spec.get('name_expansion') is not None:
        issues.append('No acronym expansion is declared')
    commitments = spec.get('intrinsic_commitments', {})
    for name in ('everything_admitted_is_SDF', 'uncheated_time',
                 'no_external_Psi_envelope', 'no_fixed_intrinsic_nesting_depth',
                 'no_observation_based_definition_erasure'):
        if commitments.get(name) is not True:
            issues.append('Missing commitment: ' + name)
    for name in ('coordinate_arena_required', 'external_metric_required',
                 'operator_nodes_or_edges_required', 'cardinality_observable_required',
                 'renderer_required', 'hardware_runtime_required'):
        if commitments.get(name) is not False:
            issues.append('Intrinsic regression: ' + name)
    if commitments.get('pinion_symbol') != 'phi' or commitments.get('pinion_display') != 'φ':
        issues.append('Pinion must remain lowercase phi')
    if 'authorship metadata' not in spec.get('attribution', {}).get('role', ''):
        issues.append('Personal attribution cannot silently parameterize physics')
    if len(spec.get('temporal_contracts', [])) != 5:
        issues.append('Temporal contract register missing an entry')
    diagnostic = spec.get('optional_scalar_reading', {})
    if diagnostic.get('does_not_select_jitter') is not True:
        issues.append('Zero identity cannot select a jitter dynamics')
    if diagnostic.get('does_not_prove_causality_or_entropy') is not True:
        issues.append('Scalar balance is not a physics proof')
    if diagnostic.get('does_not_erase_structure') is not True:
        issues.append('A readout has been promoted to defining identity')
    return issues


def self_test(spec: dict) -> dict:
    if validate(spec):
        raise AssertionError(validate(spec))
    checked = 1
    for name in ('coordinate_arena_required', 'external_metric_required',
                 'operator_nodes_or_edges_required', 'cardinality_observable_required',
                 'renderer_required', 'hardware_runtime_required'):
        altered = copy.deepcopy(spec)
        altered['intrinsic_commitments'][name] = True
        if not validate(altered):
            raise AssertionError('Failed to catch ' + name)
        checked += 1
    altered = copy.deepcopy(spec)
    altered['intrinsic_commitments']['pinion_display'] = 'Φ'
    if not validate(altered):
        raise AssertionError('Failed to catch uppercase pinion')
    checked += 1
    altered = copy.deepcopy(spec)
    altered['optional_scalar_reading']['does_not_erase_structure'] = False
    if not validate(altered):
        raise AssertionError('Failed to catch readout collapse')
    checked += 1
    altered = copy.deepcopy(spec)
    altered['attribution']['role'] = 'physical law derived from personal number'
    if not validate(altered):
        raise AssertionError('Failed to catch identity regression')
    checked += 1
    return {'status': 'PASS', 'editorial_validation_cases': checked,
            'meaning': 'Known contract regressions caught; not proof of the entire formal system'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path, nargs='?', default=DEFAULT)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding='utf-8'))
    issues = validate(spec)
    result = {'status': 'FAIL' if issues else 'PASS', 'issues': issues,
              'scope': 'editorial contract, not a TOM implementation'}
    if args.self_test and not issues:
        result['regression_tests'] = self_test(spec)
    text = json.dumps(result, indent=2)
    print(text)
    if args.json:
        args.json.write_text(text + '\n', encoding='utf-8')
    if issues:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
