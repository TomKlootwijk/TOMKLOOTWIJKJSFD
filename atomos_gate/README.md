# aTOMos Gate / Research Continuity Firewall

This is the smallest application I would attempt first from the source
paradigm: a local admission gate for new research, workflow, measurement, or
document state. Every adapter maps its update to the same proposal tuple;
the gate either commits the complete next snapshot or leaves the committed
snapshot untouched.

The shared policy is deliberately finite:

```text
AB = fresh
 AND sequence advances
 AND time advances
 AND elapsed = new_time - old_time
 AND dependency <= new_time
 AND retained facts are not erased
 AND stream and 16-bit bounds are valid
```

Accepted proposals emit a transient relation. Rejected proposals update only
bounded diagnostic memory `W`. The four adapters are workflow/file updates,
sensor/benchmark events, biological stages, and document/provenance revisions.

Run it with:

```powershell
python atomos_gate.py --iterations 10000
```

The generated report is a semantics smoke test: it checks agreement between
four renamed adapters, replay determinism, adversarial rejection, immutable
next-state construction, core-state preservation, and local timing. It is not
a durable file transaction, cryptographic authentication, timestamp proof,
physical universality, or evidence that this beats ordinary validators on real
streams. The next useful experiment is to feed actual Git/document/benchmark
events and compare false rejects and replay catches against the existing
per-domain checks.
