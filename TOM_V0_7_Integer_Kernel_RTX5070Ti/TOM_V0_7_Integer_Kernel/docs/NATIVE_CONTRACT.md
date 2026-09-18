# TOM V0.7 native-term realization contract

This contract specifies a finite execution representation of the **complete
declared expression, its licensed equivalences, and explicit continuation
obligations**. Its requirements are acceptance criteria, not a claim that an
implementation already passes them. Current execution and validation evidence
is in [NATIVE_EXECUTION_RESULTS.md](NATIVE_EXECUTION_RESULTS.md).
Passing them does not supply a unique
physical evolution: V0.7 expressly leaves continuation laws open (PDF p.14).

## Pinned source

The governing release is `C:/TOMKLOOTWIJKJSFD/TOM_V0_7_Formalization.pdf`, 18 pages,
SHA-256 `97582a16bd54d690b27105f9b09dc48d2b5716bbae2fff2a5e74190278640fbc`.
The companion declarations are retained under
`verification/formalization_20260918/`:

| File | SHA-256 |
| --- | --- |
| `TOM.tom` | `c58d7050ed5ca36e2432ffe0ef6d4b195c1f3bd900701f1e5d375f8b9e9971ce` |
| `TOM_V0_7.json` | `cf3ef6707555bb61b13112763526841284b4cdb5b7dbc2933ff5e7040b5bbf2c` |

Page references below refer to that PDF. Line references refer to the extracted
`verification/formalization_20260918/formalization.txt`. The PDF's explicit TC4
wording governs the JSON summary: a definition may contain its own name; it is
dependence on its continuation's **result** that requires later qualification.

## Representation and operations

The whole source expression is retained with this binding:

```text
FORWARD_T(INVERSE_OCCAM(ARCH(C(J(T)), E(C(J(T)), INVLOG(phi)))))
```

These are storage opcodes for source roles, not a claim that intrinsic TOM is an
operator graph. `DECL` stores a first-class named definition. Physical addresses,
term counts, storage sharing, and input/output bytes are realization details.

| Opcode | Number | Operands / auxiliary meaning |
| --- | ---: | --- |
| `DECL` | 1 | Named definition; symbol ID in auxiliary field |
| `J` | 2 | One bound temporal expression |
| `INVLOG` | 3 | One bound pinion expression |
| `C` | 4 | One causally qualified expression |
| `E` | 5 | Ordered causal and inverse-log roles |
| `ARCH` | 6 | Ordered direct and inverse roles |
| `INVERSE_OCCAM` | 7 | One preservation-qualified expression |
| `LATER_T` | 8 | One deferred expression; explicit guard ID |
| `SELF` | 9 | Own-definition name; symbol ID, not an available future result |
| `FORWARD_T` | 10 | The source's temporal qualification |

The binary term record is eight uint32 words:
`[opcode, arity, arg0, arg1, aux0, aux1, sdf, reserved]`. Missing operands use
`0xffffffff`; `sdf=1`, `reserved=0`, and unused auxiliary fields are zero.
Built-in symbol IDs are `T=1, phi=2, J=3, InvLog=4, C=5, E=6, Arch=7,
InverseOccam=8, TOM=9, Klein=10, Matryoshka=11, A=12`; explicit external
declarations start at 256. Lowercase `phi` is preserved. IDs have no physical
meaning and authorship metadata does not parameterize execution.

Definition admission, definition equality, and consumption of a continuation
are separate operations. A well-formed symbolic declaration need not have an
available dynamic result. A term that is different from the required complete
TOM expression must not pass an assertion that it is that expression merely
because it is well formed or has the same scalar reading. Arity is only a syntax
check: p.5, lines 148–150 additionally requires the declared operand roles.
`J` requires `T`, `INVLOG` requires lowercase `phi`, and `E` requires a causal
`C(...)` expression followed by `INVLOG(phi)`. Apply explicitly enabled aliases
and licensed preservation idempotence before these checks, but do not remove a
single `INVERSE_OCCAM` wrapper: `INVERSE_OCCAM(e) = e` is not a source law.
Full-source identity further requires `C(J(T))` in both declared causal positions.

Only declared abbreviation expansion, explicitly enabled `A=T`, and adjacent
`INVERSE_OCCAM(INVERSE_OCCAM(e)) = INVERSE_OCCAM(e)` may change the source's
representation without changing its definition. Retain the original statement
and the applied law as provenance. All other role order and nesting survives.
Equality of normalized terms means equality under these declared laws, not a
proof that no future extension could adopt another law.

The source frontend `parse_source_expression` evaluates the declared references
`c`, `e`, and `TOM` before encoding. `expand_declared_abbreviations` exposes this
operation directly. Definition sequences must preserve the p.3 bindings;
explicitly selected A=T and preservation idempotence remain the only additional
equivalences. A low-level `DECL("TOM")` stores a first-class name, while parsing
the source reference `TOM` evaluates its full declared binding. Neither operation
assigns a dynamic observation. No intrinsic c/e opcodes are added.

`tools/compile_native_source.py` retains the exact input UTF-8 spelling, including
BOMs and newlines, inside both supplied history buffers. The external provenance
record is `TOMSRC1` plus NUL, a uint64 byte length, then the original UTF-8 bytes.
Successful execution retains the same record in committed history. This is
source metadata, not an added physical event or source-native history codec.
Compiler paths must be distinct even through filesystem aliases. It stages all
serialized artifacts before replacing each destination atomically; publication
across the input image, oracle and JSON sidecar is not one atomic transaction.

## Coverage checklist

| Required behavior | Source | Acceptance evidence |
| --- | --- | --- |
| Retain the full precedence-qualified statement and c/e expansion | p.3, lines 60–81; p.18, line 606 | `full_source`, `wrong_e_binding` |
| Keep every admitted definition and compound SDF-qualified | p.4, lines 101–124; p.14, 448–449 | `sdf_qualification`, invalid SDF marker rejection |
| Preserve first-class definitions, argument roles and binding | p.5, 148–151; p.7, 200–206 | `first_class_definition`, `j_requires_temporal_operand`, `invlog_requires_pinion_operand`, `e_requires_declared_roles`, `single_io_is_not_identity`, `arch_role_swap`, `arch_reassociation` |
| Apply A=T only when explicitly declared | p.5, 156–159 | `alias_explicit`, `alias_not_enabled` |
| Apply preservation idempotence without deleting content | p.8, 244–248 | `io_idempotence` |
| Never infer definition identity from equal selected observations | p.8, 234–251 | `equal_readings_distinct_definitions` |
| TC1: consume only completed/present material | p.6, 169–172 | `future_input_rejection`, `present_input_allowed`, `stationary_symbolic_declaration` |
| TC2: preserve completed content and its order | p.6, 173–175 | `history_append`, `history_content_overwrite`, `history_reorder` |
| TC3: structural inversion cannot reverse time | p.6, 176–179 | `inverse_does_not_reverse_time` |
| TC4: own-name declaration is legal; immediate self-result is unavailable | p.6, 180–183 | `self_name_allowed`, `immediate_self_result_invalid` |
| TC4: later self-reference requires an explicit fulfilled condition and assigned result | p.7, 208–214 | `guarded_self_deferred`, `guard_false_pending`, `guard_met_open_law`, `guard_met_assigned_result`, `same_now_cannot_consume_later_result` |
| TC5: preserve a declared positive elapsed duration | p.6, 184–190 | `elapsed_loss` |
| No fixed intrinsic depth or mandatory exterior; resource failure must preserve data | p.9, 259–288 | capacity-driven deep-term test; `capacity_reject_no_erasure` |
| Keep Klein/Matryoshka as named roles without invented operation laws | p.9, 265–275 | `historical_role_preserved` |
| No compulsory metric, coordinate grid, quaternion arena, graph ontology, counting observable, or Psi enclosure | pp.2,4,9,18 | representational inspection; no such required parameter |
| Keep scalar diagnostics external and role-distinguishing | pp.10–13; p.18, 607–609 | existing formula audit plus `equal_readings_distinct_definitions` |
| Keep author metadata separate from physical parameters | p.1, 18–20; p.15, 514–517 | metadata inspection |

The checklist includes inspection and stress obligations beyond the finite
fixtures. A finite case count is not a completeness proof for all extensions.
The ordinary Arch scalar symmetries do not license intrinsic swaps; its printed
nonassociativity counterexample is p.11. No involution law is licensed for `INVLOG`. Neither
reciprocal mirroring nor a smoothing formula silently replaces the final form.

## Continuation and storage contract

The concrete transaction descriptor may carry external uint64 order tags
`previous`, `now`, `elapsed`, and `latest_available`. For a requested forward
transaction, require `now > previous`, `elapsed = now - previous`, and
`latest_available <= now`, without wraparound. These numeric tags and units are
declared realization witnesses; the source does not impose an integer clock.
Strict positive advancement is a forward-transaction policy, not a source claim
that every symbolic definition admission consumes positive measured time.
Unadvanced symbolic admission permits `now = previous` and `elapsed = 0`.
Flag bits are `1` for explicit A=T, `2` for requiring the full source TOM
expression, `4` for an optional external scalar echo check, and `8` for
`ADVANCE_TRANSACTION`. Flag 8 or continuation-consumption mode 1 requires strict
advancement. A passing optional scalar check never replaces the native term.

The ABI resolves term-table references and guard-assigned result IDs from the
supplied proposal. Its `latest_available` witness is caller-supplied; it does not
authenticate physical availability or implement a general lookup of observations
inside opaque history bytes. Compare the completed prefix's **actual bytes and order**, not just length,
counts, timestamps, masks, or unchecked hashes. A later correction appends a
new commitment. It does not change a previously committed byte.

Mode 0 declares a symbolic term. Mode 1 requests a continuation result. An
unqualified `SELF` cannot satisfy mode 1. `LATER_T` with a missing or false guard
remains pending. A met guard without an assigned continuation result reports
`OPEN_LAW`; it does not synthesize a result. With both supplied, the assigned
result is checked and preserved as the explicitly declared continuation law.
Guard evidence is a supplied contract input, not authentication of physical time.

Requests commit together at the case boundary. If any overall status bit is set,
an otherwise resolved request becomes `BLOCKED_TRANSACTION`; its supplied term
ID remains inspectable as a candidate, but the resolved count is zero and old
history remains committed. To resume, a caller resubmits the proposal with the
required guard/result and admissible temporal witnesses, preserving the complete
committed prefix. The evaluator checks the whole case again. There is no hidden
running continuation, generated recurrence law, or automatic advancement, and a
candidate becomes available only after the complete transaction is admitted.

`--resume` derives the completed-prefix obligation and time from an actual prior
TOR1 result. It first reexecutes the retained original proposal and compares
every result word, then checks the next proposal's old history and previous time.
This detects inconsistent artifacts; it is not cryptographic authentication.
Output paths cannot alias input, prior result or independent reference files.
CPU/GPU result and JSON writes publish an adjacent temporary only after checked
flush/close. Each file replacement is atomic; multiple output files are not a
single atomic group, and no power-loss durability guarantee is asserted.

Validation, pending guards, unresolved laws, and allocation failures must leave
the previously committed definition and history unchanged. Allocate the entire
candidate before publication; do not truncate or overwrite earlier material to
fit. No arbitrary semantic depth ceiling is admitted. Any unavoidable ABI or
address limit must be reported as a realization limit, never an intrinsic TOM
law. Memory capacity does not make an unspecified continuation rule defined.

## Exact open clauses

| Still unassigned | Source |
| --- | --- |
| Unique jitter behavior, distribution, waveform, or frequency | p.5, 133–134; p.14, 469 |
| When and how a continuation becomes actual | p.7, 208–214; p.14, 469 |
| Intrinsic pinion transformation beyond its named relation | p.14, 470 |
| A recurrence/fixed-point law establishing its result, existence, or uniqueness | p.7, 212–214 |
| Physical observation protocol | p.14, 470 |
| Recoverable-history codec and numerical thermodynamic entropy interpretation | p.13, 436–439; p.14, 471–472 |
| Additional Klein/Matryoshka operational laws or topology | p.9, 265–275 |

No numerical J, logarithm, echo, topology, or physical recurrence is supplied by
renaming an instruction. `TOM.tom:9` labels the source a human-readable
declaration, not machine instructions; `TOM_V0_7.json:11` asserts no execution
kernel. A faithful implementation must report the open clauses while executing
every assigned structural and transactional operation. It must not represent a
partial checker, a retained name, or an optional application as complete dynamics.

Independent expected cases are in `examples/native_acceptance_cases.json`.
They are source-derived requirements to test, not results copied from the runtime.
