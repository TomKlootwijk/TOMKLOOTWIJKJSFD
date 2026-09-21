# SDF semantic-core architecture rundown

**Recorded:** 2026-09-21 06:08:22 UTC  
**Context:** Magnum-opus universal SDF/Klein substrate design discussion  
**Source:** Assistant architecture response, preserved at the user's request

**Fidelity correction, 2026-09-21:** This file is an abridged restatement, not
the complete verbatim response. The earlier statement that the full reply had
been stored was inaccurate. Preserve this record as an abridgment.

## Recorded reply

The existing validated kernel and the new semantic core solve different problems.

The existing TOM v0.7/K1 kernel is a concrete finite execution machine. It already provides:

- fixed-width term and definition records;
- Boolean and integer execution;
- ordered operands and precedence;
- guarded continuations;
- forward-time checks;
- retained history and atomic commit/rejection;
- quotation and finite self-reference;
- CPU/GPU execution paths;
- independent validation and replay.

Its ABI is compact and efficient, but fixed. The ABI does not natively carry the complete semantic object required by the larger design: full Klein relation, pinion, provenance, application obligations, readout bindings, and universal operator metadata.

The new semantic core defines what the kernel terms mean before they are lowered into the existing executor. Its canonical object is an SDF operator term containing definition identity, operator role, ordered operands, signed field relation, double-packed Klein relation, pinion/temporal identity, availability tick, provenance, committed history, unresolved obligations, application bindings, and lowering metadata.

The project-specific SDF meaning is not inherently Euclidean distance, a coordinate, a grid, a scalar magnitude, or inside/outside. Those are explicit application readouts. They are not the underlying ontology.

The architecture is:

```text
SDF/Klein semantic term
        -> canonical validation and qualification
        -> loss-preserving lowering
        -> existing TOM v0.7 kernel
        -> CPU / GPU / LUT / FPGA / storage / network execution
```

The advantage is semantic universality, not faster execution. The existing kernel answers whether a finite declared machine executes deterministically. The semantic core answers what canonical operator object is being executed and whether its meaning survives translation across domains and machines.

The Klein component is a coupled, recoverable host/inversion/seam/orientation/return relation alongside the signed field operator. A scalar readout, sign match, or zero result must not flatten those two parts into one value.

The pinion target is a deterministic hop identity containing seed, parent pinion, hop index, packed phase/time, elapsed relation, dependency frontier, payload or operator identity, provenance, and commit status. A new hop is accepted only when it agrees with its committed predecessor.

The implementation order is:

1. Freeze the canonical SDF/Klein term schema.
2. Define semantic equality versus readout equality.
3. Complete Klein seam, inversion, orientation, and closure laws.
4. Define quoted self-reference and delayed continuation.
5. Define canonical pinion and single-host replay.
6. Build a loss-preserving adapter into the current TOM v0.7 ABI.
7. Compare complete terms, history, obligations, and readouts between reference and lowered execution.
8. Add application readout packs for geometry, routing, memory, sensing, and other domains.
9. Extend pinion chaining from one process to multiple hops.
10. Build the datacenter-wide substrate only after the single-host contracts are closed.

The semantic core is not a replacement for the validated kernel. It gives that kernel the universal semantic envelope required by the larger architecture. Without it, the current kernel is a strong finite machine. With it, the kernel becomes the first lowering of a shared SDF/Klein operator substrate.

## Evidence boundary

The current semantic-core implementation is a reference scaffold. It does not yet prove complete Klein topology, distributed synchronization, universal physical embodiment, or lossless lowering of every possible SDF term into the existing fixed ABI. Those are explicit next obligations rather than implicit claims.
