"""Super aTOMos Field Lens.

Compact cross-domain application of the source document's operator idea.
It ingests source PDFs, project files, and benchmark/verification traces,
then applies one generic relation pipeline to every node:

    raw signal -> signed relation -> phase -> AB -> bounded negative memory
    -> finite closure/deadlock -> transient SVG observation

Domain adapters may extract a raw signal, but the operator pipeline is shared.
Coordinates used by the SVG are observation output only; they are not retained
in field.json as resident state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None


PHI = 0.618
TARGET = 0.70
MAX_BYTES = 2_000_000
KEYWORDS = {
    "unassigned", "undefined", "unvalidated", "missing", "failure", "mismatch",
    "deadlock", "error", "open", "pass", "passed", "verified", "source",
}


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_phase(identity: str) -> float:
    return int(hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12], 16) / float(16**12)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_BYTES]
    except OSError:
        return ""


def token_set(text: str) -> set[str]:
    return {x.lower() for x in re.findall(r"[a-z][a-z0-9_-]{3,}", text) if x.lower() not in {"this", "that", "with", "from"}}


@dataclass(frozen=True)
class Node:
    node_id: str
    domain: str
    kind: str
    label: str
    source_path: str
    content_sha256: str
    raw_signal: float
    signed_relation: float
    phase: float
    ab: int
    negative_memory: float
    closure: str
    evidence: dict[str, Any]


def generic_operator(node_id: str, domain: str, kind: str, label: str, source_path: str, content: str, raw_signal: float, evidence: dict[str, Any]) -> Node:
    raw_signal = clamp(raw_signal)
    signed = raw_signal - TARGET
    phase = stable_phase(node_id + ":" + content[:2048])
    ab = int(raw_signal >= TARGET)
    negative_memory = clamp(PHI * max(0.0, -signed))
    if evidence.get("hard_failure"):
        closure = "deadlocked"
    elif ab and negative_memory < 0.20:
        closure = "closed"
    else:
        closure = "open"
    return Node(
        node_id=node_id,
        domain=domain,
        kind=kind,
        label=label,
        source_path=source_path,
        content_sha256=sha256_bytes(content.encode("utf-8", errors="replace")),
        raw_signal=round(raw_signal, 6),
        signed_relation=round(signed, 6),
        phase=round(phase, 6),
        ab=ab,
        negative_memory=round(negative_memory, 6),
        closure=closure,
        evidence=evidence,
    )


def pdf_nodes(root: Path) -> list[Node]:
    wanted = [
        root / "Tom_Klootwijk_Signed_Distance_Field_Edition.pdf",
        root / "Tom_Klootwijk_SDF_Consolidated_Formalization_D1.pdf",
        root / "TOM_V0_7_Formalization.pdf",
    ]
    out: list[Node] = []
    for path in wanted:
        if not path.exists() or PdfReader is None:
            continue
        try:
            reader = PdfReader(str(path))
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as exc:  # pragma: no cover
            text = f"read error: {exc}"
        lower = text.lower()
        unresolved = sum(lower.count(term) for term in ("unassigned", "undefined", "not assigned", "left open", "unvalidated"))
        headings = len(re.findall(r"\b(?:section|chapter|appendix)\b", lower))
        evidence = {
            "pages": len(reader.pages),
            "unresolved_markers": unresolved,
            "section_markers": headings,
            "hard_failure": False,
        }
        # A document's signal is evidence density minus unresolved interface load.
        signal = clamp(0.45 + min(0.35, headings / 80.0) - min(0.35, unresolved / 30.0))
        out.append(generic_operator(f"pdf:{path.name}", "source", "pdf", path.stem, str(path.relative_to(root)), text, signal, evidence))
    return out


def project_nodes(root: Path) -> list[Node]:
    candidates: list[Path] = []
    for folder in (root / "atomos_resilient_swarm", root / "TOM_V0_7_Integer_Kernel_RTX5070Ti" / "TOM_V0_7_Integer_Kernel"):
        if folder.exists():
            candidates.extend(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in {".py", ".md", ".cpp", ".h", ".hpp", ".tsdf"})
    # Keep this a compact lens, choosing deterministically by path and useful documentation/code files.
    candidates = sorted(candidates, key=lambda p: str(p).lower())[:80]
    out: list[Node] = []
    for path in candidates:
        text = read_text(path)
        if not text:
            continue
        lower = text.lower()
        checks = sum(lower.count(term) for term in ("assert", "verify", "validation", "invariant", "test", "contract"))
        unresolved = sum(lower.count(term) for term in ("todo", "unassigned", "undefined", "not implemented", "review_required"))
        lines = max(1, len(text.splitlines()))
        signal = clamp(0.48 + min(0.34, checks / 80.0) - min(0.30, unresolved / 20.0))
        evidence = {
            "lines": lines,
            "validation_markers": checks,
            "unresolved_markers": unresolved,
            "hard_failure": "review_required" in lower or "mismatch" in lower and "mismatched words, all three runs | 0" not in lower,
        }
        rel = path.relative_to(root)
        out.append(generic_operator(f"project:{rel.as_posix()}", "implementation", path.suffix.lower().lstrip("."), path.name, str(rel), text, signal, evidence))
    return out


def json_nodes(root: Path) -> list[Node]:
    candidates: list[Path] = []
    for folder in (root / "atomos_resilient_swarm" / "results", root / "TOM_V0_7_Integer_Kernel_RTX5070Ti" / "TOM_V0_7_Integer_Kernel" / "verification"):
        if folder.exists():
            candidates.extend(p for p in folder.rglob("*.json") if p.is_file())
    candidates = sorted(candidates, key=lambda p: str(p).lower())[:80]
    out: list[Node] = []
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            text = json.dumps(data, sort_keys=True)
        except Exception:
            continue
        lower = text.lower()
        fail = sum(lower.count(term) for term in ("fail", "mismatch", "error", "review_required"))
        success = sum(lower.count(term) for term in ("pass", "passed", "verified", "success", "0 mismatch"))
        numeric: list[float] = []
        def collect(value: Any) -> None:
            if isinstance(value, bool):
                return
            if isinstance(value, (int, float)) and -1e9 < value < 1e9:
                numeric.append(float(value))
            elif isinstance(value, dict):
                for v in value.values(): collect(v)
            elif isinstance(value, list):
                for v in value[:1000]: collect(v)
        collect(data)
        numeric_signal = clamp((sum(1 for x in numeric if x >= 0) / max(1, len(numeric))))
        signal = clamp(0.45 + min(0.32, success / 30.0) + 0.12 * numeric_signal - min(0.48, fail / 20.0))
        evidence = {
            "numeric_values": len(numeric),
            "success_markers": success,
            "failure_markers": fail,
            "hard_failure": fail > success and fail > 0,
        }
        rel = path.relative_to(root)
        out.append(generic_operator(f"trace:{rel.as_posix()}", "measurement", "json", path.name, str(rel), text, signal, evidence))
    return out


def git_state(root: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(["git", "status", "--short", "--untracked-files=no"], cwd=root, text=True, capture_output=True, check=False)
        return {"tracked_changes": proc.stdout.splitlines(), "git_exit": proc.returncode}
    except OSError:
        return {"tracked_changes": [], "git_exit": None}


def relation_edges(nodes: list[Node]) -> list[dict[str, Any]]:
    tokens = {n.node_id: token_set(n.label + " " + n.source_path) for n in nodes}
    edges: list[dict[str, Any]] = []
    # A bounded, deterministic cross-domain relation set. No coordinates are needed.
    for i, left in enumerate(nodes):
        for right in nodes[i + 1:]:
            if left.domain == right.domain:
                continue
            overlap = tokens[left.node_id] & tokens[right.node_id]
            if overlap or left.kind == right.kind:
                strength = clamp(0.25 + 0.08 * len(overlap) + 0.20 * (1.0 - abs(left.signed_relation - right.signed_relation)))
                edges.append({"from": left.node_id, "to": right.node_id, "strength": round(strength, 6), "shared_terms": sorted(overlap)[:8]})
    return sorted(edges, key=lambda x: (x["from"], x["to"]))[:500]


def action_queue(nodes: Iterable[Node]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for n in nodes:
        if n.closure == "deadlocked" or n.signed_relation < -0.10:
            reason = "close unresolved interface or investigate failure evidence"
            priority = abs(n.signed_relation) + (0.35 if n.closure == "deadlocked" else 0.0)
        elif n.closure == "open":
            reason = "define missing transition or improve evidence"
            priority = abs(n.signed_relation)
        else:
            reason = "retain as a closed relation and use as a reference"
            priority = 0.0
        actions.append({"priority": round(priority, 6), "node_id": n.node_id, "action": reason, "domain": n.domain, "closure": n.closure})
    return sorted(actions, key=lambda x: (-x["priority"], x["node_id"]))[:20]


def build(root: Path) -> dict[str, Any]:
    nodes = pdf_nodes(root) + project_nodes(root) + json_nodes(root)
    nodes = sorted(nodes, key=lambda n: n.node_id)
    edges = relation_edges(nodes)
    domains = Counter(n.domain for n in nodes)
    result = {
        "application": "Super aTOMos Field Lens",
        "operator": {
            "target": TARGET,
            "phi": PHI,
            "resident_state": ["signed_relation", "phase", "AB", "negative_memory", "closure"],
            "observation": "SVG positions are derived and released; field.json stores no coordinates.",
        },
        "git": git_state(root),
        "summary": {"node_count": len(nodes), "edge_count": len(edges), "domains": dict(sorted(domains.items()))},
        "nodes": [asdict(n) for n in nodes],
        "edges": edges,
        "action_queue": action_queue(nodes),
    }
    return result


def svg(result: dict[str, Any]) -> str:
    nodes = result["nodes"]
    width, height = 1200, 760
    domain_y = {"source": 170, "implementation": 380, "measurement": 590}
    positions: dict[str, tuple[float, float]] = {}
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for n in nodes:
        by_domain[n["domain"]].append(n)
    for domain, group in by_domain.items():
        group.sort(key=lambda n: n["node_id"])
        for i, n in enumerate(group):
            x = 80 + (i + 0.5) * (width - 160) / max(1, len(group))
            y = domain_y.get(domain, 380) + (n["phase"] - 0.5) * 80
            positions[n["node_id"]] = (round(x, 2), round(y, 2))
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<title>Super aTOMos Field Lens transient relation field</title>',
             '<desc>Cross-domain relation map of source, implementation, and measurement nodes. Positions are observation output.</desc>',
             '<rect width="100%" height="100%" fill="#f8faf9"/>']
    for domain, y in domain_y.items():
        lines.append(f'<text x="24" y="{y - 85}" font-family="Arial" font-size="20" fill="#2f7774">{domain}</text>')
    for edge in result["edges"]:
        if edge["from"] in positions and edge["to"] in positions:
            x1, y1 = positions[edge["from"]]; x2, y2 = positions[edge["to"]]
            opacity = min(0.65, 0.15 + edge["strength"])
            lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#9ab8b5" stroke-width="1.2" opacity="{opacity:.3f}"/>')
    for n in nodes:
        x, y = positions[n["node_id"]]
        if n["closure"] == "closed": fill = "#2f7774"
        elif n["closure"] == "deadlocked": fill = "#aa4c4c"
        else: fill = "#d38a35"
        radius = 5 + 8 * abs(n["signed_relation"])
        label = n["label"][:30].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f'<circle cx="{x}" cy="{y}" r="{radius:.2f}" fill="{fill}" opacity="0.86"><title>{label} | {n["closure"]} | AB={n["ab"]}</title></circle>')
    lines.append('<text x="24" y="735" font-family="Arial" font-size="14" fill="#65757b">teal = closed relation | orange = open relation | red = deadlocked relation | coordinates released after observation</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "field.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    (output / "field.svg").write_text(svg(result), encoding="utf-8")
    digest = sha256_bytes(json.dumps(result, sort_keys=True).encode("utf-8"))
    counts = result["summary"]["domains"]
    actions = result["action_queue"][:5]
    report = [
        "# Super aTOMos Field Lens",
        "",
        "Compact cross-domain application of the relation-first paradigm.",
        "",
        f"Deterministic field digest: `{digest}`",
        f"Nodes: {result['summary']['node_count']}  |  relations: {result['summary']['edge_count']}  |  domains: {counts}",
        "",
        "## Shared operator pipeline",
        "",
        "Every source PDF, project file, and measurement trace receives the same `raw signal -> signed relation -> phase -> AB -> bounded negative memory -> closure/deadlock` pipeline. Domain adapters only extract the raw signal.",
        "",
        "Coordinates exist only in `field.svg` as a released observation. They are absent from `field.json` resident state.",
        "",
        "## Highest-priority actions",
        "",
    ]
    for action in actions:
        report.append(f"- `{action['priority']:.3f}` {action['action']} - {action['node_id']}")
    report += [
        "",
        "## Interpretation boundary",
        "",
        "This lens tests transportability and usefulness across unlike local assets. It does not prove physical universality, eliminate conventional storage, or validate the source's unassigned equations. Its first success criterion is that the same operator code path produces replayable, actionable state across all three domains.",
    ]
    (output / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "digest": digest, "summary": result["summary"], "top_actions": actions}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "results")
    parser.add_argument("--verify-replay", action="store_true")
    args = parser.parse_args()
    first = build(args.root)
    second = build(args.root)
    digest_a = sha256_bytes(json.dumps(first, sort_keys=True).encode("utf-8"))
    digest_b = sha256_bytes(json.dumps(second, sort_keys=True).encode("utf-8"))
    if args.verify_replay and digest_a != digest_b:
        raise SystemExit(f"replay mismatch: {digest_a} != {digest_b}")
    write_outputs(first, args.out)
    if args.verify_replay:
        print("replay: PASS")


if __name__ == "__main__":
    main()
