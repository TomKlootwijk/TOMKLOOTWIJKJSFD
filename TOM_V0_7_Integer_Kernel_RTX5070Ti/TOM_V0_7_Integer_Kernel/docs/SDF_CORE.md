# Clean SDF/Klein semantic core

## Purpose

The existing TOM/K1 runtime is the validated finite execution backend. The
clean core defines the semantic object that may be lowered into that backend
or another execution target.

The project-specific meaning of SDF is definition-level and operator-level.
The core does not require a Euclidean metric, coordinate grid, scalar
magnitude, or inside/outside classification. Those are explicit application
readouts bound by a named law, domain, unit, and falsifier.

## Canonical term

`tom.sdf_core.SDFTerm` contains:

```text
definition_id
operator and role
ordered operand definition ids
sign: negative, zero, positive, or unknown
exact value: integer, rational, or symbolic
KleinPack: host, seam, orientation, inversion, closure declaration
Pinion: seed-derived temporal identity when assigned
availability tick
provenance
committed history references
unresolved obligations
```

The canonical JSON bytes are the semantic serialization. Floats are rejected
in the core. A readout is a separate `Readout` record containing the source
term digest, application profile, law, units, value, domain, and falsifier.
Readout equality never establishes definition equality.

## Self-reference and time

The clean kernel registry uses an explicit quoted definition id for the kernel
itself. This represents self-reference without creating an in-memory cycle.
Continuation is guarded and delayed. A commit requires a forward tick, exact
elapsed relation, matching seed and parent pinion, available evidence, intact
history, and sufficient capacity.

`derive_pinion` is the first deterministic seed-derived hop profile. It is a
reference synchronization identity, not yet a distributed clock or a claim
of physical time authority.

## Lowering boundary

`tom.sdf_lowering.lower_term` lowers only operators explicitly supported by the
selected TOM/K1 profile. The backend's fixed ABI cannot carry the complete
semantic object, so the lowering emits a sidecar that preserves the SDF term,
registry digest, Klein data, pinion, provenance, history, obligations, and
value. Unsupported operators such as `QUOTE` are rejected rather than
flattened.

```text
SDF/Klein term
  -> canonical validation
  -> explicit lowering profile
  -> TOM/K1 native term + semantic sidecar
  -> backend execution
```

The sidecar is temporary compatibility scaffolding until a versioned backend
ABI can carry the full term natively. A lowering is valid only when complete
term, history, obligation, and readout equivalence is independently checked.

## Current scope

The core and lowering tests cover exact-value rejection, readout separation,
Klein inversion declarations, quoted self-reference, open-law handling,
forward atomic commits, capacity rejection, future-evidence rejection, and
explicit unsupported-lowering rejection. Complete Klein closure laws,
versioned native ABI support, multi-hop pinion replay, and datacenter
publication remain next implementation layers.

