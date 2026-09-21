"""Clean project-specific SDF/Klein semantic core.

This module is the reference layer for the universal substrate described in
``MAGNUM_OPUS_TODO.md``.  In this profile SDF is a definition-level operator
relation.  A Euclidean distance, coordinate, scalar magnitude, or
inside/outside result is an explicitly bound application readout; none is
required by the core.

The implementation is deliberately small and exact:

* terms contain ordered operator identity, sign, provenance, obligations,
  temporal availability, and a double-packed Klein relation;
* values are integers, Fractions, or symbolic expressions; floats are rejected;
* self-reference uses explicit quoted definition identifiers rather than an
  in-memory cycle;
* pinions form a seed-derived, hash-chained temporal packing profile;
* commits are forward-only, prefix-preserving, capacity-bounded transactions;
* readouts are separate records and cannot change term identity.

This is a semantic/reference core, not a claim that the current implementation
already provides a distributed or physical Klein-bottle substrate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
import hashlib
import json
import re
from typing import Any, Mapping


class SDFError(ValueError):
    """Invalid term, pack, or transaction input."""


TERM_FORMAT = "TOM-SDF-KLEIN-TERM-1"
BUNDLE_FORMAT = "TOM-SDF-KLEIN-BUNDLE-1"


class Sign(str, Enum):
    NEGATIVE = "-"
    ZERO = "0"
    POSITIVE = "+"
    UNKNOWN = "?"


class Status(str, Enum):
    COMMITTED = "committed"
    DECLARED = "declared"
    OPEN_LAW = "open_law"
    INVALID = "invalid"
    FUTURE_EVIDENCE = "future_evidence"
    TEMPORAL = "temporal"
    PREFIX_REWRITE = "prefix_rewrite"
    CAPACITY = "capacity"
    PENDING = "pending"


def _nonempty(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SDFError(f"{label} must be a non-empty string")
    return value


def _u64(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 1 << 64:
        raise SDFError(f"{label} must be an unsigned 64-bit integer")
    return value


def _exact_value(value: Any) -> dict[str, str] | None:
    """Canonical exact value encoding; no float values are accepted."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise SDFError("boolean values must be represented as a signed relation")
    if isinstance(value, int):
        return {"kind": "int", "value": str(value)}
    if isinstance(value, Fraction):
        return {"kind": "fraction", "numerator": str(value.numerator),
                "denominator": str(value.denominator)}
    if isinstance(value, Symbolic):
        return {"kind": "symbolic", "expression": value.expression}
    raise SDFError("core values must be int, Fraction, Symbolic, or None")


@dataclass(frozen=True)
class Symbolic:
    """An exact named expression whose application law remains explicit."""

    expression: str

    def __post_init__(self) -> None:
        _nonempty(self.expression, "symbolic expression")


@dataclass(frozen=True)
class KleinPack:
    """The second half of the double-packed SDF/Klein term.

    The fields are semantic declarations, not an implicit Euclidean embedding.
    ``closure`` names the declared closure predicate that an application must
    bind before claiming a closed physical/topological realization.
    """

    host: str
    seam: str
    orientation: int = 1
    inverted: bool = False
    closure: str = "open"

    def __post_init__(self) -> None:
        _nonempty(self.host, "Klein host")
        _nonempty(self.seam, "Klein seam")
        if self.orientation not in (-1, 1):
            raise SDFError("Klein orientation must be -1 or 1")
        if not isinstance(self.inverted, bool):
            raise SDFError("Klein inversion flag must be boolean")
        _nonempty(self.closure, "Klein closure")

    def inverted_pack(self) -> "KleinPack":
        """Return the explicit inverse/orientation presentation."""
        return KleinPack(self.host, self.seam, -self.orientation,
                         not self.inverted, self.closure)

    def compatible_with(self, other: "KleinPack") -> bool:
        """Apply the declared finite closure key; no topology is inferred."""
        return (self.host == other.host and self.seam == other.seam and
                self.closure == other.closure and
                (self.orientation != other.orientation or
                 self.inverted != other.inverted))

    def canonical(self) -> dict[str, Any]:
        return {"host": self.host, "seam": self.seam,
                "orientation": self.orientation, "inverted": self.inverted,
                "closure": self.closure}


@dataclass(frozen=True)
class Pinion:
    """Seed-derived temporal packing identity for one admitted hop."""

    seed: str
    parent: str | None
    hop: int
    tick: int
    elapsed: int
    phase: int
    payload: str

    def __post_init__(self) -> None:
        _nonempty(self.seed, "pinion seed")
        if self.parent is not None:
            _nonempty(self.parent, "pinion parent")
        _u64(self.hop, "pinion hop")
        _u64(self.tick, "pinion tick")
        if isinstance(self.elapsed, bool) or not isinstance(self.elapsed, int) or self.elapsed < 0:
            raise SDFError("pinion elapsed must be a non-negative integer")
        _u64(self.phase, "pinion phase")
        _nonempty(self.payload, "pinion payload")

    def canonical(self) -> dict[str, Any]:
        return {"seed": self.seed, "parent": self.parent, "hop": self.hop,
                "tick": self.tick, "elapsed": self.elapsed,
                "phase": self.phase, "payload": self.payload}

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(canonical_json(self.canonical())).hexdigest()


def derive_pinion(seed: str, parent: Pinion | None, tick: int,
                  payload: str, *, elapsed: int | None = None) -> Pinion:
    """Derive a reproducible pinion from its committed predecessor."""
    _nonempty(seed, "pinion seed")
    _nonempty(payload, "pinion payload")
    _u64(tick, "pinion tick")
    if parent is None:
        hop = 0
        parent_id = None
        # The kernel starts at logical tick zero.  The first admitted hop may
        # therefore begin at any positive tick and consumes that full elapsed
        # interval.
        expected_elapsed = tick
    else:
        if parent.seed != seed:
            raise SDFError("pinion seed changed across a hop")
        hop = parent.hop + 1
        parent_id = parent.digest
        expected_elapsed = tick - parent.tick if tick >= parent.tick else -1
    if elapsed is None:
        elapsed = expected_elapsed
    if elapsed < 0 or (parent is not None and elapsed != expected_elapsed):
        raise SDFError("pinion elapsed does not match the committed predecessor")
    material = canonical_json({"seed": seed, "parent": parent_id,
                               "hop": hop, "tick": tick,
                               "elapsed": elapsed, "payload": payload})
    phase = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
    return Pinion(seed, parent_id, hop, tick, elapsed, phase, payload)


@dataclass(frozen=True)
class SDFTerm:
    """One definition-level signed-field operator term."""

    definition_id: str
    operator: str
    role: str
    operands: tuple[str, ...] = ()
    sign: Sign = Sign.UNKNOWN
    value: int | Fraction | Symbolic | None = None
    klein: KleinPack = field(default_factory=lambda: KleinPack("seed", "root"))
    pinion: Pinion | None = None
    available_tick: int = 0
    provenance: str = ""
    history: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.definition_id, "definition id")
        _nonempty(self.operator, "operator")
        _nonempty(self.role, "role")
        if not all(isinstance(item, str) and item for item in self.operands):
            raise SDFError("operands must be non-empty definition identifiers")
        if not isinstance(self.sign, Sign):
            raise SDFError("sign must be a Sign value")
        _exact_value(self.value)
        _u64(self.available_tick, "available tick")
        if not isinstance(self.provenance, str):
            raise SDFError("provenance must be text")
        if not all(isinstance(item, str) and item for item in self.history):
            raise SDFError("history entries must be non-empty strings")
        if not all(isinstance(item, str) and item for item in self.obligations):
            raise SDFError("obligations must be non-empty strings")

    def canonical(self) -> dict[str, Any]:
        return {
            "definition_id": self.definition_id,
            "operator": self.operator,
            "role": self.role,
            "operands": list(self.operands),
            "sign": self.sign.value,
            "value": _exact_value(self.value),
            "klein": self.klein.canonical(),
            "pinion": None if self.pinion is None else self.pinion.canonical(),
            "available_tick": self.available_tick,
            "provenance": self.provenance,
            "history": list(self.history),
            "obligations": list(self.obligations),
        }

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json(self.canonical())

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_bytes).hexdigest()


@dataclass(frozen=True)
class Readout:
    """An application view that cannot replace its source SDF term."""

    source_digest: str
    profile: str
    law: str
    units: str
    value: int | Fraction | Symbolic | None
    domain: str
    falsifier: str

    def __post_init__(self) -> None:
        for value, label in ((self.source_digest, "source digest"),
                             (self.profile, "readout profile"),
                             (self.law, "readout law"),
                             (self.units, "readout units"),
                             (self.domain, "readout domain"),
                             (self.falsifier, "readout falsifier")):
            _nonempty(value, label)
        _exact_value(self.value)

    def canonical(self) -> dict[str, Any]:
        return {"source_digest": self.source_digest, "profile": self.profile,
                "law": self.law, "units": self.units,
                "value": _exact_value(self.value), "domain": self.domain,
                "falsifier": self.falsifier}


def canonical_json(value: Any) -> bytes:
    """Canonical UTF-8 JSON bytes used by every semantic identity."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _decode_exact_value(value: Any) -> int | Fraction | Symbolic | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        raise SDFError("invalid canonical exact value")
    kind = value["kind"]
    if kind == "int":
        return int(value["value"])
    if kind == "fraction":
        return Fraction(int(value["numerator"]), int(value["denominator"]))
    if kind == "symbolic":
        return Symbolic(value["expression"])
    raise SDFError(f"unknown exact value kind: {kind}")


def _decode_klein(value: Any) -> KleinPack:
    if not isinstance(value, dict):
        raise SDFError("invalid canonical Klein pack")
    return KleinPack(value["host"], value["seam"], value["orientation"],
                     value["inverted"], value["closure"])


def _decode_pinion(value: Any) -> Pinion | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise SDFError("invalid canonical pinion")
    return Pinion(value["seed"], value["parent"], value["hop"],
                  value["tick"], value["elapsed"], value["phase"],
                  value["payload"])


def term_from_canonical(value: Mapping[str, Any]) -> SDFTerm:
    """Reconstruct one term after strict canonical-shape validation."""
    if not isinstance(value, Mapping):
        raise SDFError("canonical term must be an object")
    return SDFTerm(
        definition_id=value["definition_id"], operator=value["operator"],
        role=value["role"], operands=tuple(value.get("operands", ())),
        sign=Sign(value["sign"]), value=_decode_exact_value(value.get("value")),
        klein=_decode_klein(value["klein"]),
        pinion=_decode_pinion(value.get("pinion")),
        available_tick=value.get("available_tick", 0),
        provenance=value.get("provenance", ""),
        history=tuple(value.get("history", ())),
        obligations=tuple(value.get("obligations", ())),
    )


def pack_term(term: SDFTerm) -> bytes:
    """Pack one double-packed term with a self-checking semantic digest."""
    return canonical_json({"format": TERM_FORMAT, "term": term.canonical(),
                           "digest": term.digest})


def unpack_term(data: bytes) -> SDFTerm:
    """Unpack and verify one canonical double-packed term."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SDFError("invalid canonical term bytes") from exc
    if payload.get("format") != TERM_FORMAT:
        raise SDFError("unsupported SDF/Klein term format")
    term = term_from_canonical(payload.get("term"))
    if payload.get("digest") != term.digest:
        raise SDFError("canonical term digest mismatch")
    return term


class Registry:
    """Content-addressable term registry with explicit self-reference."""

    def __init__(self) -> None:
        self._terms: dict[str, SDFTerm] = {}

    def register(self, term: SDFTerm) -> str:
        existing = self._terms.get(term.definition_id)
        if existing is not None and existing.canonical_bytes != term.canonical_bytes:
            raise SDFError(f"definition id collision: {term.definition_id}")
        self._terms[term.definition_id] = term
        return term.definition_id

    def require(self, definition_id: str) -> SDFTerm:
        try:
            return self._terms[definition_id]
        except KeyError as exc:
            raise SDFError(f"unknown definition: {definition_id}") from exc

    def canonical_bytes(self) -> bytes:
        return canonical_json([self._terms[key].canonical()
                               for key in sorted(self._terms)])

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_bytes()).hexdigest()

    def pack(self) -> bytes:
        """Pack the complete ordered registry with its content identity."""
        return canonical_json({
            "format": BUNDLE_FORMAT,
            "terms": [self._terms[key].canonical() for key in sorted(self._terms)],
            "digest": self.digest(),
        })

    @classmethod
    def unpack(cls, data: bytes) -> "Registry":
        """Unpack and verify a complete registry bundle."""
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SDFError("invalid canonical registry bytes") from exc
        if payload.get("format") != BUNDLE_FORMAT:
            raise SDFError("unsupported SDF/Klein registry format")
        registry = cls()
        terms = payload.get("terms")
        if not isinstance(terms, list):
            raise SDFError("registry terms must be an array")
        for item in terms:
            registry.register(term_from_canonical(item))
        if payload.get("digest") != registry.digest():
            raise SDFError("canonical registry digest mismatch")
        return registry


@dataclass(frozen=True)
class KernelState:
    tick: int = 0
    pinion_id: str | None = None
    history: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _u64(self.tick, "kernel tick")
        if self.pinion_id is not None:
            _nonempty(self.pinion_id, "kernel pinion id")
        if not all(isinstance(item, str) and item for item in self.history):
            raise SDFError("kernel history entries must be non-empty strings")


@dataclass(frozen=True)
class Evaluation:
    status: Status
    term: SDFTerm | None
    reason: str = ""


@dataclass(frozen=True)
class Commit:
    status: Status
    state: KernelState
    reason: str = ""


class SDFKernel:
    """Reference evaluator and atomic commit boundary."""

    def __init__(self, registry: Registry, *, capacity: int = 1024,
                 seed: str = "TOM-SDF-SEED") -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise SDFError("kernel capacity must be positive")
        self.registry = registry
        self.capacity = capacity
        self.seed = _nonempty(seed, "kernel seed")
        self.state = KernelState()

    def evaluate(self, definition_id: str, *, now: int,
                 evidence_available: int) -> Evaluation:
        _u64(now, "evaluation tick")
        _u64(evidence_available, "evidence availability tick")
        term = self.registry.require(definition_id)
        if term.available_tick > now or evidence_available > now:
            return Evaluation(Status.FUTURE_EVIDENCE, term,
                              "term or evidence is unavailable at this tick")
        if term.obligations:
            return Evaluation(Status.OPEN_LAW, term,
                              "term has unresolved application obligations")
        if term.operator == "QUOTE":
            if len(term.operands) != 1:
                return Evaluation(Status.INVALID, term, "QUOTE requires one operand")
            target = self.registry.require(term.operands[0])
            quoted = SDFTerm(
                definition_id=f"quote:{term.definition_id}", operator="QUOTE_RESULT",
                role="quoted_definition", operands=(target.definition_id,),
                sign=target.sign, value=target.value, klein=term.klein,
                pinion=term.pinion, available_tick=term.available_tick,
                provenance=f"{term.provenance}|quotes:{target.definition_id}",
                history=term.history, obligations=target.obligations)
            return Evaluation(Status.OPEN_LAW if quoted.obligations else Status.DECLARED,
                              quoted, "quoted definition retained as a distinct term")
        return Evaluation(Status.DECLARED, term)

    def commit(self, evaluation: Evaluation, *, pinion: Pinion) -> Commit:
        """Atomically append one fully qualified term or leave state unchanged."""
        old = self.state
        if evaluation.term is None:
            return Commit(Status.INVALID, old, "cannot commit an empty evaluation")
        if evaluation.status not in (Status.DECLARED, Status.COMMITTED):
            return Commit(evaluation.status, old, evaluation.reason)
        term = evaluation.term
        if term.available_tick > pinion.tick:
            return Commit(Status.FUTURE_EVIDENCE, old, "term availability is in the future")
        if pinion.seed != self.seed:
            return Commit(Status.INVALID, old, "pinion seed does not match kernel seed")
        if pinion.parent != old.pinion_id:
            return Commit(Status.TEMPORAL, old, "pinion parent does not match committed state")
        if pinion.tick <= old.tick or pinion.elapsed != pinion.tick - old.tick:
            return Commit(Status.TEMPORAL, old, "pinion does not advance by its declared elapsed time")
        if term.history[:len(old.history)] != old.history:
            return Commit(Status.PREFIX_REWRITE, old, "candidate rewrites committed history")
        if len(old.history) + 1 > self.capacity:
            return Commit(Status.CAPACITY, old, "history capacity would be exceeded")
        new_state = KernelState(pinion.tick, pinion.digest,
                                old.history + (term.digest,))
        self.state = new_state
        return Commit(Status.COMMITTED, new_state)


def bind_readout(term: SDFTerm, *, profile: str, law: str, units: str,
                 value: int | Fraction | Symbolic | None, domain: str,
                 falsifier: str) -> Readout:
    """Bind an application readout without changing the source term."""
    return Readout(term.digest, profile, law, units, value, domain, falsifier)


def make_kernel_terms(*, seed: str = "TOM-SDF-SEED") -> tuple[Registry, str]:
    """Create the smallest clean self-referential kernel registry.

    The explicit ``kernel:clean:v1`` identifier is the seed-level identity that
    breaks the otherwise impossible content-hash cycle of a term quoting its
    own definition.  The registry digest still covers the complete canonical
    body, including that explicit self-reference.
    """
    registry = Registry()
    klein = KleinPack(host="kernel", seam="root", orientation=1,
                      inverted=False, closure="declared")
    quote = SDFTerm("kernel:quote:v1", "QUOTE", "operator_definition",
                    operands=("kernel:clean:v1",), sign=Sign.UNKNOWN,
                    klein=klein, provenance="clean-kernel-self-reference")
    kernel = SDFTerm("kernel:clean:v1", "KERNEL", "universal_substrate",
                     operands=(quote.definition_id,), sign=Sign.UNKNOWN,
                     klein=klein, provenance=f"seed:{seed}",
                     obligations=("bind_application_law",))
    registry.register(quote)
    registry.register(kernel)
    return registry, kernel.definition_id
