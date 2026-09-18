# TOM V0.7

**Tom Klootwijk · NL200678942 · date supplied 10-07-1990**

TOM is the requested name; V0.7 is the requested version. This release upgrades
the **formal definition** according to the later corrections in the newly
attached 37-page source. It does not rename a graph kernel or arithmetic engine
and claim that the source's objections have disappeared.

## Read first

- `TOM_V0_7_Formalization.pdf`: the typeset consolidated release.
- `formalization/TOM_V0_7.md`: editable complete text.
- `formalization/TOM_V0_7.json`: machine-checkable editorial contract.
- `formalization/TOM_V0_7.tex`: editable typesetting source.
- `docs/SOURCE_DECISIONS.md`: precise source evolution and decisions.
- `verification/`: actual executed diagnostic results, not hardware benchmarks.

The intrinsic core preserves lowercase φ, SDF-qualified definitions throughout,
one forward temporal precedence, inverse-log jitter, source-named causality and
entropy, Arch U without U, and the inverse-Occam sheet. It does not require a
spatial arena, metric, SDF graph, renderer, finite-state grid or fixed exterior Ψ.
Authorship identifiers do not become cosmological constants or keys.

## The major technical upgrade

The source's final scalar expression

    |c| + |ln(1/varphi)*c| - |c-ln(1/varphi)*c|

is zero for every finite real c, because ln(1/varphi) is negative. It therefore
cannot select a jitter law or prove causal progression. The release keeps this
exact reading but separates it from the total defining structure. Inverse Occam
is formalized as a non-erasure commitment: equal selected observations do not
by themselves identify the underlying definitions. Temporal admissibility is
specified separately instead of inferred from that zero result.

All added laws and all optional numerical readings are marked as such. SDF in
this core is the author's native definition qualification; ordinary exact
metric signed-distance properties require a separately declared interpretation.
The source's equations using those ordinary properties are audited explicitly,
not silently repaired or presented as the intrinsic theory.

## Run the optional external audits

Python 3.10+; standard library only, no network or installation dependencies:

```bash
python audit/audit_formulas.py --json reproduced_scalar_audit.json
python audit/audit_contract.py --self-test --json reproduced_contract_audit.json
```

The formula audit uses exact rational arithmetic for its main assertions. A
70-digit Decimal display of ln(1/varphi) is clearly labelled approximate. The
proof in the document establishes its sign and the general identity. The tests
are not a simulation or a discretization of intrinsic TOM. The contract linter
checks a written specification and known regressions; it does not prove physical
truth, mathematical completeness or a uniquely determined dynamics.

## Why no new CUDA executable?

The latest source rejects rendering/computer-science foundations, quaternion
coordinates, metric/vector replacements and finally SDFs-as-graph-nodes. The
current user request is for a major **formalization** upgrade. V0.7 therefore
keeps source-code audit artifacts external instead of substituting another
finite machine as TOM itself. Prior v6 spatial applications may remain usable
application models; they do not become an intrinsic graph-free TOM by renaming.

No statement of physical incarnation, cosmic equilibrium, thermodynamic entropy,
infinite information storage, bypassed elapsed time, unique historical priority
or GPU throughput is validated by this release. Those are different claims from
the supplied definition and the exact algebra checked here.

## Typeset again

From `formalization/`, run `pdflatex TOM_V0_7.tex` twice with a LaTeX installation
providing newpx, amsmath, tcolorbox, tabularx, hyperref and standard packages.
No font files are included. The finished PDF was rendered and visually checked
before delivery. `MANIFEST.sha256` identifies the shipped files.
