# TOM V0.7 / K1: declaration encoding and validation contract

## Source hierarchy

The requested source is the 37-page `DON EN AD ...` PDF, hashed in METADATA.json.
Its late author corrections govern: no mandatory quaternion/metric carrier
(pp.21,26), lowercase phi and non-cheated temporal precedence (p.28), no intrinsic
node/graph model (p.31), inverse-Occam sheet and inverse-log jitter (pp.32–34), and
causality/entropy as SDF definitions (pp.34–37). Page 23 makes the personal identity
an attribution choice rather than a physical invariant.

The source itself does not specify a complete CUDA instruction set, an intrinsic
pinion dynamics, a binary precision, a unique jitter law or a measured entropy
functional. This is an **explicit finite interpretation for testing declarations
and observer certificates**, added in response to the present request for a
kernel. It is not the native continuum renamed as machine memory.

## Three different layers

1. **Native TOM declaration:** the source's operative SDF roles and precedence.
   Named `phi`, `inverse_log_phi`, `jitter`, `ArchU`, `causality`, `entropy`, sheet,
   inverse Occam, double UU, Klein and Matryoshka are preserved in the image.
2. **Finite validation representation:** packed Boolean clauses, temporal state
   bindings, ordinary device addresses, bounded bit widths and test cases. These
   are observation/implementation choices, not ontological points or dimensions.
3. **Physical bootstrap:** a small C++/CUDA reader performs memory operations and
   three-input Boolean selection. The operational selection decomposition is
   itself represented as a readable/executable field. Hardware machine code
   still exists; representation does not eliminate instruction decoding.

This use of SDF means a packed *declaration encoding in TOM's final native sense*.
No Euclidean distance, interval-code geometry, Eikonal condition, unit gradient,
spatial inside/outside or signed-distance magnitude is introduced as its carrier.
Kernel/program/data bits are one common bit representation with roles. Claiming
that any bit string is consequently an arbitrary exact metric SDF would be false;
this package makes no such claim.

## Field encoding and operational kernel

All image payload is little-endian uint32. A definition occupies 16 words (512
bits). Word 14 contains its own id. Word 15 assigns a reusable temporary slot for
value-producing clauses. Identifiers are physical encoding references, not
intrinsic nodes. The layout is a finite executable description; it does not
assert a graph as the definition of TOM.

Kernel id 0 has:

- kind=Kernel in word 0;
- word 1: microprogram offset in the same atlas;
- word 2: number of clauses (7);
- word 3: the primitive selector's eight-bit truth field (canonical 0xCA);
- word 4: final local result index (17);
- word 14: its own id.

There are eight coefficient inputs, three Boolean argument inputs and seven
intermediate words. A microclause `(dst,x,y,condition)` applies the kernel's stored
selector table to the named local words. Each clause may use only input words or
previously defined temporaries. The canonical body is:

    11 = select(0,1,8)      12 = select(2,3,8)
    13 = select(4,5,8)      14 = select(6,7,8)
    15 = select(11,12,9)    16 = select(13,14,9)
    17 = select(15,16,10)

Here coefficient words 0..7 are 32 parallel truth coefficients; inputs a,b,c occupy
8,9,10. For bit inputs the selected row is a+2b+4c. `select(x,y,c)` chooses x at
c=0 and y at c=1. The bootstrap uses XOR/AND, not floating arithmetic.

The `field` engine reads these actual words each time an expression is evaluated.
Changing the selector field or valid microprogram changes semantics. The `lowered`
engine is a partial evaluation of this canonical body into direct bit selectors;
the loader verifies all body words and the selector byte before permitting it.
It rejects edited noncanonical kernels instead of silently ignoring them.

## Program values and recursive definitions

| Kind | Payload words |
|---|---|
| Constant | word1 is the Boolean value |
| State | word1 state slot; word2 seed mode; word3 parameter |
| Rule | word1 eight-bit truth table |
| DynamicRule | words1..8 references to evaluated truth-row fields |
| Expression | word1 rule id; words2..4 operands |
| Quote | word1 exact bit address in the definition atlas |
| Time | word1 binding offset; word2 binding count; word3 self id |
| NativeDeclaration | named source role with no assigned executable arithmetic |

For each evaluation snapshot, State reads only the old data. All instantaneous
expression dependencies must already be available in the schedule. Cyclic
instantaneous expressions are rejected; a recurrence through old State and a
future Time binding is valid. `A` is an exact name alias of Time `T` (id 1).
A dynamic truth row can thus inspect old self coefficients and generate future
ones, without a same-snapshot race or an input retroactively changing its own
past use.

The data record can hold runtime rule coefficients or ordinary observer inputs;
both are Boolean planes, with one word packing 32 independent cases. No execution
case is claimed to be a spatial point of native TOM. Structural publication of a
new immutable definition image happens explicitly between runs. The selfcopy
program reproduces the whole 28-word operational kernel body as Boolean outputs,
and `publish_kernel.py` can rebuild a target image from that result.

## Precedence and non-collapse checks

The example certificate program separately tests:

    forward = current_time > previous_time
    elapsed_preserved = forward AND (current_time - previous_time == elapsed)
    future_independent = latest_dependency <= current_time
    retention_preserved = (retained_before AND NOT retained_after) == 0
    Arch_neutral = direct*echo <= 0          // implemented by sign/zero bits

The first four are required for `temporal_retention_conformant`; neutrality is
reported separately and also combined into `all_reported_checks`. The program
retains input operands and definition-witness bytes, so equal residuals do not
replace distinct descriptions with the single number zero.

The timestamps are unsigned 16-bit external readings and the difference is
accepted only under strict forward order. A modular subtraction on its own is
not enough. Retention masks hold eight explicitly tracked assertions. This is a
bounded witness to selected V0.7 conditions, not infinite retained history or a
physical entropy functional. A maliciously incorrect availability stamp can
satisfy arithmetic; the kernel does not authenticate the real-world origin of
observer data.

The source's real Arch expression satisfies:

    |a| + |b| - |a-b| = 0 iff a*b <= 0.

For a finite scalar j and a negative coefficient ell=ln(1/g), with numerical
calibration g>1, j*(ell*j)<=0. This identity can be audited without evaluating an
irrational logarithm at runtime. It does not determine native pinion dynamics or
causality. `arch_exact_int8` tests the full residual over the signed 8-bit domain;
sign extension to 10 bits precedes negation/absolute value, preventing overflow
at -128 or in differences as large as 255. No float or implicit real truncation
is used.

## Observer epochs and histories

Scratch recycling preserves logical gate results for programs that do not
observe layout changes. Quotation can read physical definition addresses and
scratch-slot metadata; recompiling a program with a different layout may therefore
change its quoted values. Equivalence of arbitrary reflective programs across
different compiled images is not claimed.

The runner's uint64 epoch counts completed finite transitions and survives
resumption from a saved state. It rejects overflow. The epoch is not equated with
elapsed physical duration. Program timestamps are their own declared input data.

Optional traces keep all recorded snapshots, initial included. They incur real
space/transfer/time cost and are never described as lossless finite storage for
unbounded intrinsic distinctions. GPU export covers the first memory shard only;
that scope is reported. Lowering preserves the canonical expression's observable
bit output; the complete definition image remains present as evidence rather
than being equated with that output.

## CUDA data access

A GPU word-thread executes one complete program schedule for 32 independent cases.
Current state is immutable; next state is distinct. Scratch slots are reused only
after last use and stay thread-owned. Textures read unsigned element data with
integer coordinates. There are no filtered or normalized coordinates, trigonometric
calls, scalar SDF distance calculations, probability samples or floating timers
in the authored kernel paths.

`shared` stages the full immutable image per block and checks its actual device
limit. It is not a permanent texture-cache allocation. `global` supplies a
non-texture comparison, while `texture` uses the integer fetch path. CUDA API
structs and third-party drivers may contain floating fields internally; the
float-free claim concerns the authored calculation and its data, not every
instruction executed anywhere by an operating system.

## Not silently claimed

No finite GPU program proves an unbounded non-graph continuum. No unknown native
operator receives a convenient numerical formula. No mask is promoted to a
Euclidean signed-distance sample. No cache policy guarantees maximum throughput.
No root self-address proves universal self-hosting or autonomous reproduction.
No neutral Arch reading certifies temporal conformance. No pass on an edited rule
image proves the same source semantics: the independent oracle cases and immutable
expected definitions must be checked too.
