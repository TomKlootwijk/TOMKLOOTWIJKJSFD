# SDF/Klein semantic core

The project-specific meaning of SDF is definition-level and operator-level.
A Euclidean distance, coordinate grid, scalar magnitude, or inside/outside
test is an application readout, not a mandatory ontology.

`python/tom/sdf_core.py` is the exact reference layer for that semantic
carrier. The existing TOM/K1 native runtime is the finite execution backend;
`python/tom/sdf_lowering.py` is the explicit seam between them.

## What is enforced

An `SDFTerm` carries an ordered operator and role, definition-id operands, a
four-valued sign, an exact integer/rational/symbolic value, a `KleinPack`, an
optional `Pinion`, availability tick, provenance, history, and unresolved
obligations. Collections are frozen into tuples at construction. Floats and
booleans cannot become exact values.

Canonical term, registry, and snapshot formats reject wrong shapes, unknown or
duplicate fields, noncanonical integer text, malformed fractions, and digest
mismatches. `CoreLimits` bounds term bytes, bundle bytes, registry entries,
text, operands, obligations, and dependency depth before admission or
evaluation.

Evaluation has a closed reference operator table for the operators it can
execute. Unknown operators remain `OPEN_LAW`; wrong arity, missing operands,
cycles without an explicit delayed law, future dependencies, and incompatible
Klein seams are rejected. `QUOTE` preserves the maximum availability and
obligations of the complete dependency it quotes.

The commit boundary revalidates the current registry and evidence context. It
requires the evaluation tick to equal the candidate pinion tick, derives the
next pinion from the seed, full predecessor, tick, elapsed time, and term
digest, and rejects forged phase, hop, parent, or payload fields. Candidate
history must exactly identify the committed predecessor.

The versioned finite seam law is `TOM-SDF-KLEIN-COMPOSE-1`: packs compose only
when host, seam, and closure agree; orientation multiplies and inversion parity
XORs. This is an executable finite algebra for the semantic boundary. It does
not infer a Euclidean embedding or claim a physical Klein bottle.

`SDFKernel.snapshot()` and `SDFKernel.from_snapshot()` preserve and verify the
complete registry, state history, tick, seed, capacity, and predecessor pinion.
A restored kernel can continue the same seed-derived chain.

## Double packing and readouts

The first pack is the ordered SDF definition. The second pack is the explicit
Klein seam record. A readout is a separate `Readout` record containing the
source digest, application profile, named law, units, value, domain, and
falsifier. A readout never replaces its source term or establishes definition
equality.

Self-reference uses a declared `kernel:clean:v1` identity quoted by a separate
term, so the registry remains finite. Its unresolved `bind_application_law`
obligation is intentionally reported as `OPEN_LAW`: the current Python
evaluator is not pretending that this small registry already contains a
self-hosting executable copy of its own implementation.

## Lowering contract

```text
SDF/Klein registry
  -> canonical validation and bounded closure walk
  -> explicit TOM/K1 operator profile
  -> native term plus complete semantic closure sidecar
  -> Python reference, CPU, or CUDA backend
```

The lowering table preserves native source declaration ids (`T=1`, `phi=2`,
and other known names) and assigns deterministic injective ids to additional
declarations inside the closure. It rejects unsupported operators, unresolved
obligations, malformed arity, missing references, and cycles. The sidecar
contains the complete reachable semantic closure and a closure digest; a
registry digest alone would not be enough to reconstruct definitions.

The fixed native ABI cannot carry every semantic field, so sidecar fields remain
above the backend. `docs/SDF_CORE_GPU.md` and
`tools/validate_sdf_backends.py` compare every native output word against the
Python reference and record CPU/CUDA execution. The checked-in evidence is in
`verification/sdf_backends/`.

## Remaining boundary

The local reference core now has bounded, replayable, finite semantics. The
following are still explicit future work rather than implied by names:

- packing the evaluator, admission rules, and delayed continuation as an
  executable self-referential SDF operator body;
- a source-defined pinion law and multi-host synchronization protocol;
- a versioned native ABI that carries the semantic sidecar on the device;
- physical or datacenter-wide topology and transport.

Those boundaries are recorded in `SDF_CORE_READINESS_AUDIT.md` and the project
todo. No application readout, hash identity, or single-GPU equivalence result
is presented as proof of those broader claims.
