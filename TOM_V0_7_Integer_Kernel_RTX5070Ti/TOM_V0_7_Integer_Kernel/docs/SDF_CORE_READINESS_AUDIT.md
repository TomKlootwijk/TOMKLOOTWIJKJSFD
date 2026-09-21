# SDF/Klein core readiness audit

Date: 2026-09-21
Initial audited revision: `1077a7e`; follow-up repairs through `ac41c72`
Scope: `python/tom/sdf_core.py`, `python/tom/sdf_lowering.py`, their tests,
and the existing native backend contract. No implementation was changed by this audit.

## Follow-up decision

The initial blockers below were reproduced at `1077a7e`. They are now repaired
in the pushed implementation: immutable term collections, strict canonical
decoding, dependency and arity validation, quote availability propagation,
kernel-bound evaluation contexts, exact seed-derived pinion admission, bounded
resources, complete lowering closure, injective native declaration mapping,
snapshot/restart, and executable finite Klein seam composition. Focused tests
and all eight CTest targets pass. The lowered `T/phi/J/C/E/ARCH` fixture also
matches every Python, CPU, and real RTX 5070 Ti CUDA output word; see
`docs/SDF_CORE_GPU.md` and `verification/sdf_backends/`.

The core is still a finite local reference profile rather than the full
universal/dedicated architecture requested in the long-term todo. The remaining
gaps are executable self-hosting kernel-law packing, source-defined pinion
semantics and multi-host synchronization, a native ABI carrying the semantic
sidecar, and datacenter transport/topology. Those are open scope, not silently
filled with conventional distance or AI assumptions.

## Historical decision

The new layer is a prototype and is not ready to be presented as a completed,
reusable universal SDF/Klein execution core. The earlier eight passing CTest
targets are regression evidence for their exercised cases, not proof of the
new semantic guarantees. The findings below were reproduced with in-memory
calls against the checked-in implementation.

The architectural target remains unchanged: definitions, rules, the kernel
itself, double packing and pinions must have executable SDF operator semantics.
Correcting the implementation must preserve that target.

## Reproduced correctness blockers

| Finding | Observed result | Required repair |
| --- | --- | --- |
| Caller-supplied evaluation bypass | An open-law term returns `OPEN_LAW` normally, but `Evaluation(Status.DECLARED, term)` commits it. | Revalidate the complete candidate and obligations at commit; bind it to the evaluated snapshot and evidence. |
| Evidence tick lost at commit | Evaluation with evidence available at tick 100 can commit at tick 1. | Retain and validate evaluation/evidence context at the publication boundary. |
| QUOTE loses target availability | A target value available at 999 becomes a quote result available at 0 and commits at 1. | Preserve the target's availability and provenance; distinguish quoting a definition from reading its unavailable result. |
| Pinion fields not verified | A directly constructed pinion with hop 99, arbitrary phase and unrelated payload commits. | Validate the expected hop, selected phase law, exact payload, seed and predecessor together. |
| Unknown operator and absent operand | `NO_SUCH_LAW` referencing `missing-child` evaluates as `DECLARED` and commits. | Use a closed executable operator registry; explicitly distinguish opaque declarations from executable applications. Validate dependencies. |
| Mutable registered definitions | Passing a list as operands and mutating it changes the registered term's digest despite the frozen dataclass. | Strictly validate or freeze collections and nested values before registration. |
| Exact decoder silently coerces | Replacing the serialized integer `"1"` with JSON number `1.9` still unpacks as integer 1 with the old digest. | Reject wrong types, noncanonical numbers, unknown/duplicate keys and malformed shapes before constructing values. |
| Lowering fixture fails native evaluation | The existing lowering test's `arch` fixture returns native status 1 (`INVALID`). | Preserve explicit bindings to native T/phi symbols and execute the generated backend image in conformance tests. |
| Distinct declarations collapse | `collision:22168` and `collision:22964` both map to native symbol 323658012 and compare definition-equal. | Replace truncated-hash symbol assignment with an injective checked mapping retained in the bundle. |
| Incomplete preservation sidecar | The sidecar contains the root term and registry digest, but no referenced term bodies. | Carry the complete reachable definition closure and explicit mapping, and verify reconstruction. A digest alone cannot reconstruct a definition. |
| Invalid structures bypass or crash lowering | DECL ignores supplied operands; a cyclic C expression raises `RecursionError`. | Validate arities and references, distinguish quoted/delayed references from immediate dependencies, and enforce bounded traversal. |

Primary locations in the audited revision:

- `sdf_core.py:462-511`: evaluation and commit authority.
- `sdf_core.py:475-485`: quote result construction.
- `sdf_core.py:175-202`: proposed hash-derived pinion profile.
- `sdf_core.py:222-237`: collection/type validation.
- `sdf_core.py:299-420`: canonical decoding and registry loading.
- `sdf_lowering.py:58-62`: declaration symbol assignment.
- `sdf_lowering.py:76-102`: lowering traversal and arity handling.
- `sdf_lowering.py:106-123`: incomplete preservation sidecar.
- `tests/sdf_lowering_tests.py:35-40`: fixture checks without backend execution.

## Architectural work still required

### Executable packed kernel

`make_kernel_terms()` currently creates KERNEL/QUOTE references. It does not pack
the implementation of evaluation, admission or transition as executable SDF
operator bodies. Those decisions remain in Python methods. Quotation copies
selected target fields rather than reproducing the entire operational kernel.
The new module also has no executable delayed-continuation operator.

The next milestone must demonstrate that the runtime reads the packed operator
law and executes it. A valid law change must change the resulting execution;
invalid changes must be rejected. Full quotation, reconstruction and guarded
later publication must preserve the body and its defining distinctions. The
existing K1 stored-selector and quotation mechanisms are useful implementation
resources; their previous validation does not automatically validate this layer.

### Executable Klein packing

`KleinPack` currently stores host/seam/closure strings and orientation flags.
`compatible_with()` compares labels and flags; evaluation/commit do not call it.
It is not a complete executable double-packing or closure law.

Specify the project's actual seam, return, inversion, composition and closure
laws as versioned SDF operator definitions. Check full pack/unpack and composition
with independent examples and counterexamples. Preserve unspecified laws as
open rather than substituting arbitrary geometry or flag tests.

### Pinion law provenance

The SHA-256-derived 64-bit phase in the prototype was an implementation choice.
It has not been derived from the project's source-defined pinion law. Specify
the exact seed/time-packing operator and its relationship to elapsed time and
hop dependencies. A byte identity hash must not silently become that law.
Single-host sequence validation and replay precede distributed synchronization.

### Durable replay and bounded resources

KernelState currently retains ticks, a pinion digest and term digests, with no
state restore/replay interface. Referenced term bodies and the full pinion/evidence
chain are not retained by the state alone. Capacity limits count commits but
do not bound term size, exact integer size, registry bytes or traversal depth.

A clean release needs a complete snapshot/journal format, rejection without
partial state, declared resource budgets and a reproducible process restart
demonstration. Local durability and distributed publication are separate scopes.

## Release work order

1. Repair admission, evidence/pinion binding, immutable values and strict parsing.
2. Repair native symbol bindings, dependency traversal and complete bundle retention.
3. Implement and verify packed executable kernel laws, Klein composition and
   guarded continuation; document any newly selected profile as a new assignment.
4. Demonstrate exact snapshot/restart and multi-hop replay, including rejected
   future evidence, replayed hops, wrong parents and capacity exhaustion.
5. Compare reference and actual native executable results using complete retained
   definitions, histories and statuses. GPU equivalence is a separate measured
   result; this audit did not execute a new GPU profile.
6. Produce a clean source-only package with pinned dependencies, versioned formats,
   small runnable examples, a build/test command, specification, ELI5 guide and
   explicit current status. Verify it from an empty directory.

Datacenter-wide operation can remain a later milestone for a scoped local-core
release. The local release must not label hash chaining as completed network
synchronization or stored metadata as an executed operator law.

## Provenance correction

The existing `provenance/2026-09-21_sdf_semantic_core_rundown.md` is an abridged
restatement of the conversation response, not the full verbatim reply previously
claimed. Retain it as an abridged record and add the full source response when
preparing the provenance package. Preserve this distinction in the clean repo.
