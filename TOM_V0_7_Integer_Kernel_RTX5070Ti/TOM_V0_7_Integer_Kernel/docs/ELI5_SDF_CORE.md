# The SDF/Klein core in plain language

Imagine a box of cards. Each card says:

- what this thing is called;
- which rule made it;
- which other cards it uses;
- what is known about it right now;
- where it came from; and
- which promises are still waiting for an application to define them.

That card is an SDF term in this project. “Signed distance field” is the
project's name for the signed, related definition. It does not force the card
to contain metres, pixels, a coordinate grid, or an inside/outside answer. If
an application wants a distance, it adds a separate readout that names the
distance rule, units, domain, and a way to disprove the answer.

## Why two packs?

The first pack is the card's ordered definition. The second pack is its seam
record: host, seam name, orientation, inversion parity, and closure law. The
reference profile has one small executable seam rule. Matching seams compose;
orientation signs multiply; inversion flags combine by parity. This lets the
kernel reject a mismatched seam before it is treated as an answer.

It is a bookkeeping and composition law. The implementation does not claim
that a JSON record has become a physical Klein bottle.

## What happens when a card is used?

The registry checks the card's shape and size. The evaluator checks that all
cards it points at exist, are available at the current tick, use a known rule,
fit the rule's arity, and have compatible seams. A quoted card keeps the latest
availability tick of everything it inspected, so a future card cannot sneak
into an earlier result.

To commit a result, the caller supplies a pinion. Think of a pinion as a
numbered receipt in a chain: it names the seed, predecessor receipt, tick,
elapsed time, phase, and exact term digest. The kernel recomputes the receipt.
Changing the hop number, parent, phase, payload, or time makes the commit fail.

The history is append-only. A candidate must name exactly the history it saw;
it cannot edit an earlier card. The snapshot file stores the cards, history,
and complete predecessor receipt so a restarted process can continue the same
chain.

## Where does the GPU fit?

The existing TOM/K1 backend is a fast finite machine. The SDF layer translates
supported cards into that machine's fixed format and keeps the remaining
semantic information in a sidecar. The CPU and CUDA programs then receive the
same packed native words. The checked-in GPU report proves that the small
fixture produced identical words on the Python reference, CPU executable, and
an RTX 5070 Ti.

That proves this lowering path for this finite fixture. It does not prove an
unlimited self-writing AI, a physical topology, or a datacenter-wide clock.
Those are separate engineering layers and remain named as open work rather
than being smuggled in under the word “SDF”.

## The smallest honest mental model

SDF term = **a signed, named definition card**.

Klein pack = **the card's seam passport**.

Pinion = **a seed-checked receipt in time order**.

Readout = **an application-specific answer attached to a card**.

Lowering = **putting the card into the existing finite machine without losing
the information the machine cannot carry**.
