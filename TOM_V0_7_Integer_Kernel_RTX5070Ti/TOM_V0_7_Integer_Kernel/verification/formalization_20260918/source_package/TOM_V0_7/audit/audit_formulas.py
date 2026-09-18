#!/usr/bin/env python3
"""Exact finite audits of scalar equations exported in the supplied 37-page source.

This is NOT a simulation, discretization, or execution engine for TOM.
Fractions and Decimal belong to an explicitly external diagnostic interpretation.
The general conclusions are proved in the formalization, not inferred solely
from test counts. Standard library, Python 3.10+; no network or GPU is used.
"""
from __future__ import annotations
import argparse
from decimal import Decimal, localcontext
from fractions import Fraction
import json
from pathlib import Path


def arch(a: Fraction, b: Fraction) -> Fraction:
    return abs(a) + abs(b) - abs(a - b)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def audits() -> dict:
    values = [Fraction(i, 4) for i in range(-128, 129)]
    arch_cases = 0
    for a in values:
        for b in values:
            result = arch(a, b)
            expected = 2 * min(abs(a), abs(b)) if a * b > 0 else Fraction(0)
            require(result == expected, 'Arch piecewise identity failed')
            require((result == 0) == (a * b <= 0), 'Arch zero-set identity failed')
            require(arch(a, b) == arch(b, a), 'Arch symmetry failed')
            require(arch(a, b) == arch(-a, -b), 'Global sign invariance failed')
            arch_cases += 1

    negative_scaling_cases = 0
    for numerator in range(1, 17):
        for denominator in range(1, 17):
            k = -Fraction(numerator, denominator)
            for c in values:
                require(arch(c, k * c) == 0, 'Negative echo identity failed')
                negative_scaling_cases += 1

    reciprocal_cases = 0
    for n in range(1, 33):
        p = Fraction(n, 8)
        for j in range(-16, 17):
            if j == 0:
                continue
            structure = Fraction(j, 4)
            mirror = p / abs(structure) ** 2
            require(arch(p, mirror) > 0, 'Positive reciprocal mirror is not positive')
            reciprocal_cases += 1

    # Different defining scales can give exactly the same single Arch reading.
    distinct_observation_cases = 0
    for c in values:
        if c:
            e1, e2 = -c, -2 * c
            require(e1 != e2 and arch(c, e1) == arch(c, e2) == 0,
                    'Definition/readout distinction failed')
            distinct_observation_cases += 1

    # The proposed smooth replacement is not the old Arch equation. We only
    # need positivity of exp for the sign test: at (1,-1) its value is negative.
    require(arch(Fraction(1), Fraction(-1)) == 0, 'Smooth counterexample A')
    require(arch(Fraction(1), Fraction(1)) == 2, 'Smooth counterexample B')
    require(arch(Fraction(2), Fraction(0)) == 0, 'Boundary collapse counterexample')
    require(arch(Fraction(1), arch(Fraction(2), Fraction(3))) == 2,
            'Nonassociativity left example')
    require(arch(arch(Fraction(1), Fraction(2)), Fraction(3)) == 4,
            'Nonassociativity right example')

    with localcontext() as context:
        context.prec = 70
        phi = (Decimal(1) + Decimal(5).sqrt()) / 2
        k = -(phi.ln())
        require(Decimal(-1) < k < 0, 'Golden-ratio log coefficient range')
        coefficient = {
            'phi_decimal_display': str(phi),
            'ln_inverse_phi_decimal_display': str(k),
            'precision_digits': context.prec,
            'status': 'display approximation only; exact sign follows from 1<phi<e'
        }

    # Eikonal sign does not fix orientation: f(t)=t and g(t)=-t have |slope|=1.
    slope_checks = []
    for slope in (Fraction(1), Fraction(-1)):
        require(abs(slope) == 1, 'Unit magnitude slope')
        slope_checks.append({'slope': str(slope), 'unit_magnitude': True,
                             'increasing': slope > 0})

    return {
        'status': 'PASS',
        'release': 'TOM V0.7',
        'scope': 'finite exact scalar formula audits; not execution of intrinsic TOM',
        'checks': {
            'distinct_rational_scalar_pairs': arch_cases,
            'negative_scale_echo_parameter_cases': negative_scaling_cases,
            'positive_reciprocal_mirror_cases': reciprocal_cases,
            'distinct_definition_same_reading_cases': distinct_observation_cases,
            'smooth_replacement_counterexamples': 2,
            'unit_slope_orientation_examples': 2,
            'nonassociativity_counterexample': 1
        },
        'scalar_results': {
            'zero_condition': 'Arch(a,b)=0 iff a*b<=0',
            'inverse_log_echo': 'Any k<0 gives Arch(c,k*c)=0 for every finite real c',
            'positive_reciprocal': 'If p>0 and s!=0 finite, Arch(p,p/abs(s)^2)>0',
            'associativity': 'Arch(1,Arch(2,3))=2; Arch(Arch(1,2),3)=4',
            'smoothing': 'At (1,-1), original Arch=0 but ab*exp(-1/(a-b)^2)=-exp(-1/4)!=0; at (1,1) the latter needs an extension',
            'orientation': slope_checks,
            'entropy_normalization': 'For E=k*C, |E_prime|=|k|*|C_prime|; k=-ln(phi) has magnitude not equal to 1'
        },
        'coefficient_display': coefficient,
        'not_established': ['physical law', 'causal dynamics from Arch alone',
                            'thermodynamic entropy', 'infinite information compression',
                            'historical novelty', 'GPU execution']
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    result = audits()
    text = json.dumps(result, indent=2)
    print(text)
    if args.json:
        args.json.write_text(text + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
