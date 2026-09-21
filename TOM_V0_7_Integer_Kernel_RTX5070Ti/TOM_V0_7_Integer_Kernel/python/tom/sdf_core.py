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


@dataclass(frozen=True)
class CoreLimits:
    """Deterministic admission and evaluation budgets for one core profile."""

    max_terms: int = 4096
    max_term_bytes: int = 1 << 20
    max_bundle_bytes: int = 16 << 20
    max_definition_chars: int = 256
    max_operator_chars: int = 128
    max_role_chars: int = 256
    max_provenance_chars: int = 4096
    max_operands: int = 64
    max_history_entries: int = 4096
    max_obligations: int = 64
    max_text_chars: int = 4096
    max_value_chars: int = 16384
    max_eval_depth: int = 256

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise SDFError(f"{name} must be a positive integer")


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


def _tuple_of_strings(value: Any, label: str) -> tuple[str, ...]:
    """Validate and freeze an ordered collection of non-empty strings."""
    if not isinstance(value, (tuple, list)):
        raise SDFError(f"{label} must be a tuple or list of strings")
    frozen = tuple(value)
    if not all(isinstance(item, str) and item for item in frozen):
        raise SDFError(f"{label} entries must be non-empty strings")
    return frozen


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
        if isinstance(self.orientation, bool) or not isinstance(self.orientation, int):
            raise SDFError("Klein orientation must be an integer")
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
        _u64(self.elapsed, "pinion elapsed")
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
        object.__setattr__(self, "operands",
                           _tuple_of_strings(self.operands, "operands"))
        if not isinstance(self.sign, Sign):
            raise SDFError("sign must be a Sign value")
        _exact_value(self.value)
        _u64(self.available_tick, "available tick")
        if not isinstance(self.provenance, str):
            raise SDFError("provenance must be text")
        object.__setattr__(self, "history",
                           _tuple_of_strings(self.history, "history"))
        object.__setattr__(self, "obligations",
                           _tuple_of_strings(self.obligations, "obligations"))

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


def _check_term_limits(term: SDFTerm, limits: CoreLimits) -> None:
    """Reject oversized semantic records before they enter a registry."""
    text_fields = ((term.definition_id, limits.max_definition_chars, "definition id"),
                   (term.operator, limits.max_operator_chars, "operator"),
                   (term.role, limits.max_role_chars, "role"),
                   (term.provenance, limits.max_provenance_chars, "provenance"))
    for value, maximum, label in text_fields:
        if len(value) > maximum:
            raise SDFError(f"{label} exceeds the configured resource limit")
    if len(term.operands) > limits.max_operands:
        raise SDFError("term operand count exceeds the configured resource limit")
    if len(term.history) > limits.max_history_entries:
        raise SDFError("term history exceeds the configured resource limit")
    if len(term.obligations) > limits.max_obligations:
        raise SDFError("term obligation count exceeds the configured resource limit")
    for values, label in ((term.operands, "operand"),
                          (term.history, "history entry"),
                          (term.obligations, "obligation")):
        if any(len(value) > limits.max_text_chars for value in values):
            raise SDFError(f"{label} exceeds the configured resource limit")
    encoded_value = _exact_value(term.value)
    if encoded_value is not None and any(
            len(value) > limits.max_value_chars for value in encoded_value.values()):
        raise SDFError("exact value exceeds the configured resource limit")
    if term.pinion is not None and any(
            len(value) > limits.max_text_chars
            for value in (term.pinion.seed, term.pinion.parent or "", term.pinion.payload)):
        raise SDFError("pinion text exceeds the configured resource limit")
    if len(term.canonical_bytes) > limits.max_term_bytes:
        raise SDFError("term exceeds the configured byte limit")


def canonical_json(value: Any) -> bytes:
    """Canonical UTF-8 JSON bytes used by every semantic identity."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


_CANONICAL_INT = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")


def _canonical_int_text(value: Any, label: str) -> int:
    if not isinstance(value, str) or not _CANONICAL_INT.fullmatch(value):
        raise SDFError(f"{label} must be a canonical decimal integer string")
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SDFError(f"{label} is not a valid integer") from exc


def _object_with_shape(value: Any, *, label: str,
                       required: set[str], optional: set[str] = frozenset()) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SDFError(f"{label} must be an object")
    allowed = required | optional
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise SDFError(f"{label} contains unknown fields: {sorted(unknown)!r}")
    if missing:
        raise SDFError(f"{label} is missing fields: {sorted(missing)!r}")
    return value


def _decode_exact_value(value: Any) -> int | Fraction | Symbolic | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        raise SDFError("invalid canonical exact value")
    kind = value["kind"]
    if kind == "int":
        obj = _object_with_shape(value, label="canonical integer",
                                 required={"kind", "value"})
        return _canonical_int_text(obj["value"], "canonical integer value")
    if kind == "fraction":
        obj = _object_with_shape(value, label="canonical fraction",
                                 required={"kind", "numerator", "denominator"})
        numerator = _canonical_int_text(obj["numerator"], "fraction numerator")
        denominator = _canonical_int_text(obj["denominator"], "fraction denominator")
        if denominator <= 0:
            raise SDFError("fraction denominator must be positive")
        result = Fraction(numerator, denominator)
        if (str(result.numerator), str(result.denominator)) != (obj["numerator"], obj["denominator"]):
            raise SDFError("fraction is not in canonical reduced form")
        return result
    if kind == "symbolic":
        obj = _object_with_shape(value, label="canonical symbolic value",
                                 required={"kind", "expression"})
        return Symbolic(obj["expression"])
    raise SDFError(f"unknown exact value kind: {kind}")


def _decode_klein(value: Any) -> KleinPack:
    obj = _object_with_shape(value, label="canonical Klein pack",
                             required={"host", "seam", "orientation", "inverted", "closure"})
    return KleinPack(obj["host"], obj["seam"], obj["orientation"],
                     obj["inverted"], obj["closure"])


def _decode_pinion(value: Any) -> Pinion | None:
    if value is None:
        return None
    obj = _object_with_shape(value, label="canonical pinion",
                             required={"seed", "parent", "hop", "tick", "elapsed", "phase", "payload"})
    return Pinion(obj["seed"], obj["parent"], obj["hop"], obj["tick"],
                  obj["elapsed"], obj["phase"], obj["payload"])


def term_from_canonical(value: Mapping[str, Any]) -> SDFTerm:
    """Reconstruct one term after strict canonical-shape validation."""
    obj = _object_with_shape(
        value, label="canonical term",
        required={"definition_id", "operator", "role", "operands", "sign", "value",
                  "klein", "pinion", "available_tick", "provenance", "history", "obligations"})
    if not isinstance(obj["operands"], list):
        raise SDFError("canonical term operands must be an array")
    if not isinstance(obj["history"], list):
        raise SDFError("canonical term history must be an array")
    if not isinstance(obj["obligations"], list):
        raise SDFError("canonical term obligations must be an array")
    try:
        sign = Sign(obj["sign"])
    except (TypeError, ValueError) as exc:
        raise SDFError("canonical term sign is invalid") from exc
    return SDFTerm(
        definition_id=obj["definition_id"], operator=obj["operator"], role=obj["role"],
        operands=obj["operands"], sign=sign, value=_decode_exact_value(obj["value"]),
        klein=_decode_klein(obj["klein"]), pinion=_decode_pinion(obj["pinion"]),
        available_tick=obj["available_tick"], provenance=obj["provenance"],
        history=obj["history"], obligations=obj["obligations"],
    )


def _strict_json_loads(data: bytes, label: str) -> Any:
    if not isinstance(data, (bytes, bytearray)):
        raise SDFError(f"{label} must be bytes")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise SDFError(f"{label} contains a duplicate field: {key!r}")
            result[key] = item
        return result

    def reject_constant(value: str) -> Any:
        raise SDFError(f"{label} contains non-finite JSON number: {value}")

    try:
        return json.loads(bytes(data).decode("utf-8"), object_pairs_hook=reject_duplicates,
                          parse_constant=reject_constant)
    except SDFError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SDFError(f"invalid {label} bytes") from exc


def pack_term(term: SDFTerm, *, limits: CoreLimits | None = None) -> bytes:
    """Pack one double-packed term with a self-checking semantic digest."""
    selected_limits = limits or CoreLimits()
    _check_term_limits(term, selected_limits)
    packed = canonical_json({"format": TERM_FORMAT, "term": term.canonical(),
                             "digest": term.digest})
    if len(packed) > selected_limits.max_term_bytes:
        raise SDFError("term envelope exceeds the configured byte limit")
    return packed


def unpack_term(data: bytes, *, limits: CoreLimits | None = None) -> SDFTerm:
    """Unpack and verify one canonical double-packed term."""
    selected_limits = limits or CoreLimits()
    if not isinstance(data, (bytes, bytearray)):
        raise SDFError("canonical term bytes must be bytes")
    if len(data) > selected_limits.max_term_bytes:
        raise SDFError("canonical term exceeds the configured byte limit")
    payload = _strict_json_loads(data, "canonical term")
    payload = _object_with_shape(payload, label="canonical term envelope",
                                 required={"format", "term", "digest"})
    if payload["format"] != TERM_FORMAT:
        raise SDFError("unsupported SDF/Klein term format")
    term = term_from_canonical(payload["term"])
    _check_term_limits(term, selected_limits)
    if payload["digest"] != term.digest:
        raise SDFError("canonical term digest mismatch")
    return term


class Registry:
    """Content-addressable term registry with explicit self-reference."""

    def __init__(self, *, limits: CoreLimits | None = None) -> None:
        self._terms: dict[str, SDFTerm] = {}
        self.limits = limits or CoreLimits()

    def register(self, term: SDFTerm) -> str:
        if not isinstance(term, SDFTerm):
            raise SDFError("registry entries must be SDFTerm values")
        _check_term_limits(term, self.limits)
        existing = self._terms.get(term.definition_id)
        if existing is not None and existing.canonical_bytes != term.canonical_bytes:
            raise SDFError(f"definition id collision: {term.definition_id}")
        if existing is None and len(self._terms) >= self.limits.max_terms:
            raise SDFError("registry term count exceeds the configured resource limit")
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
        packed = canonical_json({
            "format": BUNDLE_FORMAT,
            "terms": [self._terms[key].canonical() for key in sorted(self._terms)],
            "digest": self.digest(),
        })
        if len(packed) > self.limits.max_bundle_bytes:
            raise SDFError("registry bundle exceeds the configured byte limit")
        return packed

    @classmethod
    def unpack(cls, data: bytes, *, limits: CoreLimits | None = None) -> "Registry":
        """Unpack and verify a complete registry bundle."""
        selected_limits = limits or CoreLimits()
        if not isinstance(data, (bytes, bytearray)):
            raise SDFError("canonical registry bytes must be bytes")
        if len(data) > selected_limits.max_bundle_bytes:
            raise SDFError("canonical registry exceeds the configured byte limit")
        payload = _strict_json_loads(data, "canonical registry")
        payload = _object_with_shape(payload, label="canonical registry envelope",
                                     required={"format", "terms", "digest"})
        if payload["format"] != BUNDLE_FORMAT:
            raise SDFError("unsupported SDF/Klein registry format")
        registry = cls(limits=selected_limits)
        terms = payload["terms"]
        if not isinstance(terms, list):
            raise SDFError("registry terms must be an array")
        for item in terms:
            registry.register(term_from_canonical(item))
        if payload["digest"] != registry.digest():
            raise SDFError("canonical registry digest mismatch")
        return registry


@dataclass(frozen=True)
class KernelState:
    tick: int = 0
    pinion_id: str | None = None
    history: tuple[str, ...] = ()
    pinion: Pinion | None = None

    def __post_init__(self) -> None:
        _u64(self.tick, "kernel tick")
        if self.pinion_id is not None:
            _nonempty(self.pinion_id, "kernel pinion id")
        object.__setattr__(self, "history",
                           _tuple_of_strings(self.history, "kernel history"))
        if self.pinion is not None:
            if self.pinion.tick != self.tick or self.pinion.digest != self.pinion_id:
                raise SDFError("kernel pinion does not match kernel state")
        elif self.pinion_id is not None:
            raise SDFError("kernel state requires the complete pinion, not only its digest")


@dataclass(frozen=True)
class Evaluation:
    status: Status
    term: SDFTerm | None
    reason: str = ""
    source_definition_id: str | None = None
    evaluated_tick: int | None = None
    evidence_available: int | None = None
    registry_digest: str | None = None
    kernel_seed: str | None = None


@dataclass(frozen=True)
class Commit:
    status: Status
    state: KernelState
    reason: str = ""


class SDFKernel:
    """Reference evaluator and atomic commit boundary."""

    _ARITIES = {
        "DECL": 0, "DECLARATION": 0, "SELF": 0, "FIELD": 0,
        "QUOTE": 1, "QUOTE_RESULT": 1, "KERNEL": 1,
    }

    def __init__(self, registry: Registry, *, capacity: int = 1024,
                 seed: str = "TOM-SDF-SEED",
                 limits: CoreLimits | None = None) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise SDFError("kernel capacity must be positive")
        self.registry = registry
        self.capacity = capacity
        self.seed = _nonempty(seed, "kernel seed")
        self.limits = limits or registry.limits
        self.state = KernelState()

    def evaluate(self, definition_id: str, *, now: int,
                 evidence_available: int) -> Evaluation:
        _u64(now, "evaluation tick")
        _u64(evidence_available, "evidence availability tick")
        term = self.registry.require(definition_id)

        def result(status: Status, candidate: SDFTerm | None = term,
                   reason: str = "") -> Evaluation:
            return Evaluation(status, candidate, reason, definition_id, now,
                              evidence_available, self.registry.digest(), self.seed)

        def check_dependencies(candidate: SDFTerm, active: set[str], depth: int) -> Evaluation | None:
            if depth > self.limits.max_eval_depth:
                return result(Status.CAPACITY, candidate,
                              "dependency depth exceeds the configured resource limit")
            if candidate.definition_id in active:
                return result(Status.INVALID, candidate,
                              "cyclic evaluation requires an explicit delayed law")
            active.add(candidate.definition_id)
            try:
                for ref in candidate.operands:
                    try:
                        dependency = self.registry.require(ref)
                    except SDFError as exc:
                        return result(Status.INVALID, candidate, str(exc))
                    if dependency.available_tick > now:
                        return result(Status.FUTURE_EVIDENCE, candidate,
                                      f"dependency {ref} is unavailable at this tick")
                    if dependency.obligations:
                        return result(Status.OPEN_LAW, candidate,
                                      f"dependency {ref} has unresolved application obligations")
                    failure = check_dependencies(dependency, active, depth + 1)
                    if failure is not None and failure.status != Status.DECLARED:
                        return failure
                return None
            finally:
                active.remove(candidate.definition_id)

        if term.available_tick > now or evidence_available > now:
            return result(Status.FUTURE_EVIDENCE, term,
                          "term or evidence is unavailable at this tick")
        expected_arity = self._ARITIES.get(term.operator)
        if expected_arity is None:
            return result(Status.OPEN_LAW, term,
                          f"operator {term.operator!r} has no bound application law")
        if len(term.operands) != expected_arity:
            return result(Status.INVALID, term,
                          f"operator {term.operator!r} requires {expected_arity} operands")
        if term.obligations:
            return result(Status.OPEN_LAW, term,
                          "term has unresolved application obligations")
        dependency_failure = check_dependencies(term, set(), 0)
        if dependency_failure is not None:
            return dependency_failure
        if term.operator == "QUOTE":
            target = self.registry.require(term.operands[0])
            quoted = SDFTerm(
                definition_id=f"quote:{term.definition_id}", operator="QUOTE_RESULT",
                role="quoted_definition", operands=(target.definition_id,),
                sign=target.sign, value=target.value, klein=term.klein,
                pinion=term.pinion, available_tick=max(term.available_tick,
                                                       target.available_tick),
                provenance=f"{term.provenance}|quotes:{target.definition_id}",
                history=term.history, obligations=target.obligations)
            return result(Status.OPEN_LAW if quoted.obligations else Status.DECLARED,
                          quoted, "quoted definition retained as a distinct term")
        return result(Status.DECLARED, term)

    def commit(self, evaluation: Evaluation, *, pinion: Pinion) -> Commit:
        """Atomically append one fully qualified term or leave state unchanged."""
        old = self.state
        if evaluation.term is None:
            return Commit(Status.INVALID, old, "cannot commit an empty evaluation")
        if evaluation.status not in (Status.DECLARED, Status.COMMITTED):
            return Commit(evaluation.status, old, evaluation.reason)
        term = evaluation.term
        if (evaluation.source_definition_id is None or
                evaluation.evaluated_tick is None or
                evaluation.evidence_available is None or
                evaluation.registry_digest is None or
                evaluation.kernel_seed is None):
            return Commit(Status.INVALID, old,
                          "evaluation is not bound to a kernel evidence context")
        if evaluation.kernel_seed != self.seed or evaluation.registry_digest != self.registry.digest():
            return Commit(Status.INVALID, old,
                          "evaluation was produced by a different kernel context")
        if evaluation.evaluated_tick != pinion.tick:
            return Commit(Status.TEMPORAL, old,
                          "pinion tick does not match evaluation tick")
        if evaluation.evidence_available > pinion.tick:
            return Commit(Status.FUTURE_EVIDENCE, old,
                          "evaluation evidence is in the future")
        fresh = self.evaluate(evaluation.source_definition_id,
                              now=pinion.tick,
                              evidence_available=evaluation.evidence_available)
        if fresh.status not in (Status.DECLARED, Status.COMMITTED):
            return Commit(fresh.status, old, fresh.reason)
        if fresh.term is None or fresh.term.digest != term.digest:
            return Commit(Status.INVALID, old,
                          "evaluation term does not match the current registry")
        if old.pinion_id is not None and old.pinion is None:
            return Commit(Status.TEMPORAL, old, "committed state lacks its predecessor pinion")
        try:
            expected_pinion = derive_pinion(self.seed, old.pinion, pinion.tick,
                                            term.digest)
        except SDFError as exc:
            return Commit(Status.TEMPORAL, old, str(exc))
        if pinion != expected_pinion:
            return Commit(Status.TEMPORAL, old,
                          "pinion is not the seed-derived next hop for this term")
        if term.history[:len(old.history)] != old.history:
            return Commit(Status.PREFIX_REWRITE, old, "candidate rewrites committed history")
        if len(old.history) + 1 > self.capacity:
            return Commit(Status.CAPACITY, old, "history capacity would be exceeded")
        new_state = KernelState(pinion.tick, pinion.digest,
                                old.history + (term.digest,), pinion)
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
