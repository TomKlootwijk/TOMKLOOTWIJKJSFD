"""aTOMos Gate: a compact universal state-transition firewall.

The same admission relation is applied to four adapters:
workflow/file updates, sensor/benchmark events, biological stage transitions,
and document/provenance revisions.

Core state is intentionally small and history-free:
  last sequence, last time, retained fact mask, and bounded negative-memory bits.

Accepted proposals commit atomically and emit a transient relation. Rejected
proposals leave the core state unchanged and update only bounded reason bits.
This is an executable test of the source's finite transition, retention,
freshness, and zero-update ideas; it does not claim physical security.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, List, Tuple


MAX_U16 = 65_535
REASON_BITS = {
    "stale_sequence": 1 << 0,
    "backward_time": 1 << 1,
    "wrong_elapsed": 1 << 2,
    "future_dependency": 1 << 3,
    "fact_erasure": 1 << 4,
    "not_fresh": 1 << 5,
    "wrong_stream": 1 << 6,
    "u16_overflow": 1 << 7,
}


@dataclass(frozen=True)
class Proposal:
    stream_id: str
    seq: int
    t: int
    elapsed: int
    latest_dependency_t: int
    retained_fact_mask_before: int
    retained_fact_mask_after: int
    fresh: bool
    adapter: str
    label: str


@dataclass(frozen=True)
class GateState:
    stream_id: str
    last_seq: int = 0
    last_t: int = 0
    retained_fact_mask: int = 0
    negative_memory_bits: int = 0
    accepted_count: int = 0
    rejected_count: int = 0


@dataclass(frozen=True)
class Decision:
    accepted: bool
    reasons: Tuple[str, ...]
    before: GateState
    after: GateState
    transient_relation: dict[str, Any] | None
    latency_ns: int


def normalize(raw: dict[str, Any], adapter: str, label: str) -> Proposal:
    """All domain adapters enter the same canonical proposal tuple."""
    return Proposal(
        stream_id=str(raw["stream_id"]),
        seq=int(raw["seq"]),
        t=int(raw["t"]),
        elapsed=int(raw["elapsed"]),
        latest_dependency_t=int(raw.get("latest_dependency_t", raw["t"])),
        retained_fact_mask_before=int(raw.get("retained_fact_mask_before", 0)) & 0xFF,
        retained_fact_mask_after=int(raw.get("retained_fact_mask_after", raw.get("retained_fact_mask_before", 0))) & 0xFF,
        fresh=bool(raw.get("fresh", True)),
        adapter=adapter,
        label=label,
    )


def workflow_update(**raw: Any) -> Proposal:
    return normalize(raw, "workflow/file", str(raw.get("path", "workflow")))


def sensor_event(**raw: Any) -> Proposal:
    return normalize(raw, "sensor/benchmark", str(raw.get("sensor", "event")))


def biological_stage(**raw: Any) -> Proposal:
    return normalize(raw, "biological/stage", str(raw.get("stage", "stage")))


def document_revision(**raw: Any) -> Proposal:
    return normalize(raw, "document/provenance", str(raw.get("document", "revision")))


def evaluate(state: GateState, proposal: Proposal) -> Decision:
    start = time.perf_counter_ns()
    reasons: list[str] = []
    if proposal.stream_id != state.stream_id:
        reasons.append("wrong_stream")
    if not proposal.fresh:
        reasons.append("not_fresh")
    if proposal.seq <= state.last_seq:
        reasons.append("stale_sequence")
    if proposal.t <= state.last_t:
        reasons.append("backward_time")
    if proposal.elapsed != proposal.t - state.last_t:
        reasons.append("wrong_elapsed")
    if proposal.latest_dependency_t > proposal.t:
        reasons.append("future_dependency")
    # Retention is checked against the committed state, not a caller-supplied
    # "before" field that could simply lie about what was already retained.
    if state.retained_fact_mask & ~proposal.retained_fact_mask_after:
        reasons.append("fact_erasure")
    if not (0 <= proposal.seq <= MAX_U16 and 0 <= proposal.t <= MAX_U16 and 0 <= proposal.latest_dependency_t <= MAX_U16):
        reasons.append("u16_overflow")

    before = state
    bitmask = state.negative_memory_bits
    for reason in reasons:
        bitmask |= REASON_BITS[reason]
    if reasons:
        # Core state is unchanged; only bounded diagnostic memory changes.
        after = replace(state, negative_memory_bits=bitmask, rejected_count=state.rejected_count + 1)
        relation = None
        accepted = False
    else:
        after = GateState(
            stream_id=state.stream_id,
            last_seq=proposal.seq,
            last_t=proposal.t,
            retained_fact_mask=proposal.retained_fact_mask_after,
            negative_memory_bits=state.negative_memory_bits,
            accepted_count=state.accepted_count + 1,
            rejected_count=state.rejected_count,
        )
        # JIT relation: observable for the caller, not retained in GateState.
        relation = {
            "stream_id": proposal.stream_id,
            "adapter": proposal.adapter,
            "from_seq": state.last_seq,
            "to_seq": proposal.seq,
            "from_t": state.last_t,
            "to_t": proposal.t,
            "elapsed": proposal.elapsed,
            "retained_fact_mask": proposal.retained_fact_mask_after,
        }
        accepted = True
    return Decision(accepted, tuple(reasons), before, after, relation, time.perf_counter_ns() - start)


def canonical(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "stream_id": raw["stream_id"],
        "seq": raw["seq"],
        "t": raw["t"],
        "elapsed": raw["elapsed"],
        "latest_dependency_t": raw.get("latest_dependency_t", raw["t"]),
        "retained_fact_mask_before": raw.get("retained_fact_mask_before", 0),
        "retained_fact_mask_after": raw.get("retained_fact_mask_after", raw.get("retained_fact_mask_before", 0)),
        "fresh": raw.get("fresh", True),
    }


def equivalent_domain_adapters(base: dict[str, Any]) -> list[Proposal]:
    c = canonical(base)
    return [
        workflow_update(**c, path="commit.toml"),
        sensor_event(**c, sensor="benchmark-stream"),
        biological_stage(**c, stage="development-cycle"),
        document_revision(**c, document="formalization.pdf"),
    ]


def fixture_cases() -> list[tuple[str, dict[str, Any], bool, set[str]]]:
    common = {"stream_id": "demo", "seq": 1, "t": 10, "elapsed": 10, "latest_dependency_t": 10, "retained_fact_mask_before": 0b0011, "retained_fact_mask_after": 0b0011, "fresh": True}
    return [
        ("valid_append", common, True, set()),
        ("replay", {**common, "seq": 1, "t": 10}, False, {"stale_sequence", "backward_time", "wrong_elapsed"}),
        ("backward_time", {**common, "seq": 2, "t": 9, "elapsed": -1, "latest_dependency_t": 9}, False, {"backward_time"}),
        ("wrong_elapsed", {**common, "seq": 2, "t": 20, "elapsed": 19}, False, {"wrong_elapsed"}),
        ("future_dependency", {**common, "seq": 2, "t": 20, "elapsed": 10, "latest_dependency_t": 21}, False, {"future_dependency"}),
        ("fact_erasure", {**common, "seq": 2, "t": 20, "elapsed": 10, "retained_fact_mask_before": 0, "retained_fact_mask_after": 0b0001}, False, {"fact_erasure"}),
        ("not_fresh", {**common, "seq": 2, "t": 20, "elapsed": 10, "fresh": False}, False, {"not_fresh"}),
        ("u16_overflow", {**common, "seq": 2, "t": 65_536, "elapsed": 65_526, "latest_dependency_t": 65_536}, False, {"u16_overflow"}),
        ("wrong_stream", {**common, "stream_id": "other", "seq": 2, "t": 20, "elapsed": 10}, False, {"wrong_stream"}),
        ("recovery_after_reject", {**common, "seq": 2, "t": 20, "elapsed": 10}, True, set()),
    ]


def run_fixtures() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    state = GateState("demo")
    all_rejected_core_states_preserved = True
    for name, raw, expected, expected_reasons in fixture_cases():
        proposals = equivalent_domain_adapters(raw)
        decisions = [evaluate(state, p) for p in proposals]
        accepted_values = {d.accepted for d in decisions}
        reason_values = {tuple(sorted(d.reasons)) for d in decisions}
        if len(accepted_values) != 1 or len(reason_values) != 1:
            raise AssertionError(f"adapter divergence in {name}")
        decision = decisions[0]
        observed = set(decision.reasons)
        if decision.accepted != expected or observed != expected_reasons:
            raise AssertionError(f"fixture {name}: {decision.accepted}/{observed} != {expected}/{expected_reasons}")
        # Only an accepted proposal commits core state.
        core_before = (state.last_seq, state.last_t, state.retained_fact_mask)
        next_state = decision.after
        if not decision.accepted and (next_state.last_seq, next_state.last_t, next_state.retained_fact_mask) != core_before:
            all_rejected_core_states_preserved = False
            raise AssertionError(f"rejected core state mutated: {name}")
        # The diagnostic W/count fields advance even when the core snapshot
        # is rejected; retain that bounded memory for the next evaluation.
        state = next_state
        rows.append({
            "name": name,
            "accepted": decision.accepted,
            "reasons": list(decision.reasons),
            "adapter_count": len(proposals),
            "core_state_committed": decision.accepted,
            "rejected_core_state_preserved": (
                decision.accepted
                or (next_state.last_seq, next_state.last_t, next_state.retained_fact_mask) == core_before
            ),
        })
    return {
        "fixtures": rows,
        "final_state": asdict(state),
        "all_rejected_core_states_preserved": all_rejected_core_states_preserved,
    }


def benchmark(iterations: int = 10_000) -> dict[str, Any]:
    state = GateState("bench")
    raw = {"stream_id": "bench", "seq": 0, "t": 0, "elapsed": 0, "latest_dependency_t": 0, "retained_fact_mask_before": 0, "retained_fact_mask_after": 0, "fresh": True}
    timings: list[int] = []
    accepted = 0
    rejected = 0
    for i in range(1, iterations + 1):
        raw = {**raw, "seq": i, "t": i, "elapsed": 1, "latest_dependency_t": i, "fresh": True}
        d = evaluate(state, workflow_update(**raw, path="bench"))
        timings.append(d.latency_ns)
        if d.accepted:
            accepted += 1
            state = d.after
        else:
            rejected += 1
    return {"iterations": iterations, "accepted": accepted, "rejected": rejected, "median_latency_ns": statistics.median(timings), "max_latency_ns": max(timings)}


def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def semantic_fixture_view(obj: Any) -> Any:
    """Remove wall-clock measurements before replay comparison."""
    if isinstance(obj, dict):
        return {key: semantic_fixture_view(value) for key, value in obj.items() if key != "latency_ns"}
    if isinstance(obj, list):
        return [semantic_fixture_view(value) for value in obj]
    return obj


def write_report(output: Path, fixtures: dict[str, Any], bench: dict[str, Any], replay_digest: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = {"application": "aTOMos Gate", "operator": {"AB": "atomic admission bit", "W": "bounded reason mask", "JIT": "accepted relation emitted then released"}, "fixtures": fixtures, "benchmark": bench, "replay_digest": replay_digest}
    (output / "gate_results.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# aTOMos Gate",
        "",
        "A compact universal state-transition firewall applied through the same admission relation to workflow/file updates, sensor/benchmark events, biological stages, and document/provenance revisions.",
        "",
        f"Replay digest: `{replay_digest}`",
        "",
        "## Core relation",
        "",
        "AB accepts only when the proposal is fresh, strictly advances sequence and time, has exact elapsed time, does not depend on the future, does not erase retained facts, belongs to the stream, and stays within the declared 16-bit bound.",
        "",
        "Accepted updates commit atomically and emit a transient relation. Rejected updates leave the core state unchanged and set only bounded reason bits in negative memory W.",
        "",
        "## Fixtures",
        "",
        "| Case | Decision | Reasons | Four adapters agree |",
        "|---|---|---|---|",
    ]
    for row in fixtures["fixtures"]:
        reasons = ", ".join(row["reasons"]) or "-"
        lines.append(f"| {row['name']} | {'accept' if row['accepted'] else 'reject'} | {reasons} | yes |")
    lines += [
        "",
        "## Local measurement",
        "",
        f"{bench['iterations']:,} sequential admissions; {bench['accepted']:,} accepted; median gate latency {bench['median_latency_ns']:.0f} ns in this Python run.",
        "",
        f"Rejected-core preservation: `{fixtures['all_rejected_core_states_preserved']}`; final bounded W mask: `{fixtures['final_state']['negative_memory_bits']}`.",
        "",
        "This is a useful safety and consistency primitive, not cryptographic authentication and not proof of physical universality. The same contract is portable; the adapters remain explicit.",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "results")
    parser.add_argument("--iterations", type=int, default=10_000)
    args = parser.parse_args()
    first = run_fixtures()
    second = run_fixtures()
    if digest(semantic_fixture_view(first)) != digest(semantic_fixture_view(second)):
        raise SystemExit("replay mismatch")
    bench = benchmark(args.iterations)
    replay_digest = digest(semantic_fixture_view(first))
    write_report(args.out, first, bench, replay_digest)
    print(json.dumps({"out": str(args.out), "replay": "PASS", "digest": replay_digest, "benchmark": bench}, indent=2))


if __name__ == "__main__":
    main()
