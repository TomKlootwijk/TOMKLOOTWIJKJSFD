# TOM V0.7: source and bounded realization

**Historical Boolean certificate realization.** This document describes the
earlier K1 circuit. It is superseded for native execution by
[NATIVE_CONTRACT.md](NATIVE_CONTRACT.md) and
[NATIVE_EXECUTION_RESULTS.md](NATIVE_EXECUTION_RESULTS.md). Statements below that
the full expression exists only as metadata apply to K1, not `tom_native_cuda`.

Source: **TOM V0.7 Formalization**, 18 pages, authored by Tom Klootwijk. Page
references below refer to that formalization, not its earlier 37-page source.
The parent PDF and the copy in `TOM_V0_7_Package.zip` are byte-identical. PDF SHA256:
`97582a16bd54d690b27105f9b09dc48d2b5716bbae2fff2a5e74190278640fbc`.

The companion contract gives the full expression exactly as:

```text
TOM := InverseOccam[ Arch[ C[J[T]], E[C[J[T]]; InvLog[phi]] ] ] qualified_by forward_T_precedence
```

The generated image's `.map.json` retains this expression, the complete editorial
contract, source hashes, bounds and interpretation choices under
`bounded_realization`. **The complete native operator expression is preserved in
metadata; it is not executed by the present certificate circuit.** Its native
operators have not been replaced with guessed behavior.

## What the program does, in simple terms

Imagine writing every possible small candidate for a next step on separate cards.
Each card says what time was and is, how much time elapsed, when its latest input
was available, which recorded distinctions remain, and two optional scalar
readings. The program checks every chosen card against the declared rules and
counts which pass. It keeps the supplied fields so that two cards with the same
answer can still be distinguished.

This can find counterexamples, count accepted combinations, and verify that
changing a bound or an optional filter has the expected effect. It does not choose
which next step actually happens. Page 14 leaves that law open. Repeating a tick
on this particular circuit rechecks the same retained inputs; it does not evolve
native jitter, the pinion or entropy.

## The declared finite box

These are **implementation-chosen bounds and external readings**. They are not
intrinsic TOM units and were not derived from GPU hardware.

| Input | 29-bit profile | 31-bit profile |
|---|---|---|
| Previous time, current time, elapsed duration, latest dependency | Four unsigned 3-bit fields, each 0–7 | Same |
| Retained before / after | Two 3-bit membership masks | Same |
| Direct / echo | Two signed 4-bit integers, each −8–7 | Same |
| Left / right definition witnesses | Unsigned 2-bit / 1-bit labels: 0–3 / 0–1 | Unsigned 3-bit / 2-bit labels: 0–7 / 0–3 |
| Entire distinct input domain | 2^29 = 536,870,912 candidates | 2^31 = 2,147,483,648 candidates |

Disjoint slices of the candidate index encode every input bit. No two indices in
the declared domain encode the same complete input. All input fields retain their
values after a tick. A partial run covers a distinct prefix; it is exhaustive
only if it covers the entire declared domain. `prefix_counts(profile, lanes)`
independently computes exact flag totals for any such prefix.

The temporal/retention flag requires strict forward order, exact elapsed
difference, latest dependency no later than current time, and no lost membership
bits. The exact signed-integer Arch residual and its neutrality flag are separate
outputs. Combined flags are optional intersections, not additional native laws.

## Source-to-implementation map

| Source clause and pages | Present implementation | Status and remaining scope |
|---|---|---|
| Whole expression, typed roles, binding and SDF qualification; pp. 3–5, 7, 18 | Full contract/expression preserved in metadata; native role names retained. | **Partial.** No executable native compound-language semantics or general SDF-closure checker. Binding of the source expression is recorded, not evaluated. |
| TC1: no anticipation; pp. 6–7 | `latest_dependency <= current_time`; execution reads the old snapshot. | **Exact bounded check.** Availability stamps are supplied witnesses. The comparison does not authenticate observations or prove non-anticipation for every possible external history. |
| TC2: completed-prefix preservation; p. 6 | `(retained_before & ~retained_after) == 0`; all supplied inputs remain visible. | **Partial.** Masks track membership of three declared distinctions, not the contents of every completed observation. Full prefix-content preservation needs an explicit bounded history interpretation. |
| TC3: structural inversion is not time reversal; p. 6 | Scalar signs do not affect forward execution epochs; epoch overflow is rejected. | **Exact operational restriction.** No native inversion dynamics is supplied. |
| TC4: forward-guarded self-reference; pp. 6–7 | Old-state reads and separate next-state publication; unresolved instantaneous cycles rejected. | **Implemented for this execution contract.** The source does not select this particular recurrence or actuality trigger. |
| TC5: elapsed duration is not erased; p. 6 | Strict unsigned time order plus exact `current - previous == elapsed`, with no accepted wraparound. | **Exact bounded check.** Numeric time readings and their units are declared externally. |
| Inverse-Occam non-erasure; p. 8 | Inputs and both witness labels survive independently of the scalar readout. | **Partial.** Different labels are evidence supplied by the profile, not a universal decision procedure for definition identity. |
| Inverse-Occam idempotence; pp. 8, 14 | The law is retained in the source contract. | **Unimplemented structural operation.** A native expression representation and licensed rewrite must establish `InverseOccam[InverseOccam[e]] ≡def InverseOccam[e]` while preserving `e`; retaining the name alone does not execute this law. |
| Optional Arch scalar diagnostic; pp. 10–11 | Exact `abs(a)+abs(b)-abs(a-b)` for every declared integer pair, with widths extended before arithmetic. | **Implemented on the bounded domain.** Grouping and direct/inverse roles remain relevant; a scalar equality does not authorize reassociation or identify definitions. |
| Optional inverse-log echo relation; pp. 10, 13 | Independent direct/echo fields and the exact Arch-zero test. | **Partial.** `a*b <= 0` is equivalent to Arch neutrality, not to `echo = ln(1/phi)*direct`. A source-faithful symbolic echo relation must preserve that expression and its binding. Testing zero cannot substitute for it. |
| No intrinsic nesting cutoff; p. 9 | Explicit finite representation limits. | **Bounded realization only.** Finite enumeration does not implement completed infinity or establish a topology. |
| Unassigned native dynamics; pp. 5, 14 | Open clauses are recorded explicitly. | **Open in the source.** Jitter behavior, when continuation becomes actual, intrinsic pinion transformation, a physical observation protocol, a recoverable-history codec and thermodynamic entropy interpretation are not assigned. |

## What a more complete realization would require

The next structural work is to represent the native nested expression with its
declared operand roles and execute only explicitly licensed equivalences, including
preservation idempotence. It must distinguish definition identity from equal
readouts and retain the inverse-log relation symbolically instead of replacing it
with a sign test. A bounded history interpretation would also have to preserve
actual completed contents, not only mask membership.

None of that chooses a jitter or pinion evolution law. Page 14 specifies a family
of admissible continuations and explicitly requires additional assignments for
those dynamics. Exact bounded exploration can enumerate candidates satisfying
the stated interpretation; a unique native evolution requires those missing laws
to be supplied and identified as an extension. Hardware throughput and memory
measurements belong to the separate execution report.
