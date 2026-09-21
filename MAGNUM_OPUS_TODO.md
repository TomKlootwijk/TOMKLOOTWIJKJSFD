# Magnum Opus TODO

## Universal SDF operator substrate

This document records the governing direction for the project.

### Current conversation directive

The architecture must not be reduced to a conventional AI verifier with SDF as an optional layer. The intended direction is to pack **everything**, including the self-referential kernel itself, as signed-distance-field operators inside the double-packed Klein/SDF carrier. The clean kernel core comes first as the universal substrate; deterministic AI, domain profiles, lowerings, pinion synchronization, and datacenter composition are derived uses of that substrate.

The goal is to build a universal, self-referencing kernel in which **everything is packed as signed-distance-field operators**: domain objects, relations, observations, memory, geometry, time, programs, the kernel's own definition, and transitions between states.

The project-specific meaning of SDF is definition-level and operator-level. A conventional Euclidean distance, coordinate grid, scalar magnitude, or inside/outside test is an application readout, not a mandatory ontology.

The packed carrier is a **double-packed Klein-bottle/SDF operator structure**. The Klein component carries the return, inversion, seam, orientation, and closure relations. The SDF component carries the signed field relation, operator identity, ordered operands, and application readout. These two definitions remain recoverable together; a matching scalar or sign never erases the distinction between them.

The first concrete deliverable is a **clean kernel core**. It is the universal substrate from which domain profiles, lowerings, and datacenter composition are derived. GPU, CPU, LUT, bitplane, FPGA, storage, and network forms are execution lowerings of the same semantic object and must be checked for semantic equivalence.

## Provenance of the semantic-core direction

The full architecture rundown from the 21 September 2026 design discussion is preserved in [provenance/2026-09-21_sdf_semantic_core_rundown.md](provenance/2026-09-21_sdf_semantic_core_rundown.md). Its governing conclusion is:

```text
SDF/Klein semantic term
        -> canonical validation and qualification
        -> loss-preserving lowering
        -> existing TOM v0.7 kernel
        -> CPU / GPU / LUT / FPGA / storage / network execution
```

The existing validated kernel remains the finite execution backend. The new
semantic core defines the canonical operator object: SDF relation, Klein host,
pinion, provenance, obligations, self-reference, and explicit application
readouts. The new layer earns its place only when complete terms, histories,
obligations, and readouts survive lowering with independent equivalence proof.

## Ontological wrapper

Every packed term must be representable as an explicit record with at least:

```text
identity
signed field relation / polarity
operator role
ordered operands and precedence
double-pack / Klein host relation
pinion / phase relation
evaluation tick and elapsed relation
evidence-availability tick
units or application binding
provenance and source identity
retained committed history
unresolved obligations and capacity requirements
representation/lowering metadata
```

Unknown, open, ambiguous, rejected, pending, and out-of-profile states are first-class field/operator results. They are never silently converted to zero, identity, success, or a guessed physical law.

## Clean kernel core

Implement and specify the core before adding application-specific intelligence.

1. Define the canonical SDF operator and double-packed Klein record format.
2. Define exact canonicalization, packing, unpacking, hashing, and ordered operand rules.
3. Define the minimal operator registry, including the kernel's own definition as a quoted/referencable term.
4. Define the transition rule: read one committed snapshot, derive a candidate, qualify it, and atomically commit the complete next term or publish an explicit status.
5. Preserve forward temporal precedence, evidence availability, non-erasure, guarded continuation, and finite-capacity admission.
6. Keep temporary readouts, scratch evaluation, and just-in-time geometry disposable while preserving authoritative definitions and required evidence.
7. Provide independent reference and lowered evaluators whose complete semantic outputs and histories compare byte-for-byte.

The kernel must be able to inspect and reproduce its own operator definition. Self-reference is delayed and guarded: a continuation may publish a later state only after the current state, elapsed relation, evidence, and capacity checks have passed. Zero-delay paradoxes and retroactive rewrites are rejected explicitly.

## Pinion time packing and hop synchronization

Treat a pinion as a seed-derived temporal packing relation, not merely a timestamp. A hop record must bind, at minimum:

```text
seed identity
parent pinion / committed predecessor
hop index or epoch
phase and packed time
declared elapsed relation
dependency frontier
payload or operator-definition identity
provenance and availability
commit/admission status
```

The next pinion is derived only from the committed previous pinion and admitted field transition. A hop is rejected when its seed, parent, phase, elapsed time, dependency frontier, retained history, operator law, or capacity does not agree.

The eventual datacenter layer will chain these pinions across machines and domains. Network transport, clock drift, host failure, authentication, replay protection, and distributed publication order require explicit protocols; they must not be smuggled in as assumptions.

## Domain unification

Every domain profile must supply an SDF/Klein operator pack rather than bypassing the core with an unrelated host model. Candidate profiles include:

- geometry and transient just-in-time coordinate readouts;
- routing and Kiki-style closure/non-intersection relations;
- negative-memory and deviation fields;
- sensing, observation, and actualization;
- biological, morphogenetic, and ecological relations;
- simulations, documents, code, and model revisions;
- deterministic planning and controlled action.

Each profile must declare its units, boundary or observation law, parameter domain, prediction, falsifier, evidence requirements, representation budget, and admissible lowering. A domain name does not create a physical law.

## Build order

1. Freeze the clean core specification and canonical seed.
2. Implement the reference packed evaluator.
3. Implement the self-quotation and delayed self-reference profile.
4. Implement the double-packed Klein/SDF closure and return predicates.
5. Add exact pinion time packing and single-host hop replay.
6. Add independent CPU/GPU/LUT/bitplane lowerings with equivalence certificates.
7. Add cross-domain operator packs and adapter-level replay tests.
8. Add multi-hop and then datacenter-wide pinion chaining.
9. Add observation, learning, planning, and action profiles only as SDF operator families governed by the core.

## Required evidence for each milestone

- canonical source, packed bytes, and content identity;
- independent evaluator agreement;
- complete transition and history replay;
- explicit rejection cases for future evidence, retrograde time, missing dependencies, erased distinctions, invalid Klein closure, and capacity overflow;
- self-reference and resume tests;
- lowering-equivalence tests including translation and readout costs;
- cross-domain adapter agreement;
- a written boundary separating demonstrated finite behavior from an unassigned physical or universal claim.

## Current status and boundary

Existing TOM v0.7/v0.7.2, TOMAGI, WQK, aTOMos Gate, field-lens, and GPU artifacts are prototypes, profiles, and lowerings that can supply parts of this roadmap. They are not allowed to redefine the universal substrate by convenience. The double-packed Klein/SDF semantics, complete self-referential closure, pinion hop protocol, and datacenter composition remain the primary work.

The project may claim a universal **semantic architecture** only as the core contracts become executable and independently replayable across domains. Datacenter-wide synchronization, physical embodiment, fault tolerance, authenticated observation, infinite capacity, and general intelligence remain open engineering and research obligations until their specific contracts and evidence exist.
