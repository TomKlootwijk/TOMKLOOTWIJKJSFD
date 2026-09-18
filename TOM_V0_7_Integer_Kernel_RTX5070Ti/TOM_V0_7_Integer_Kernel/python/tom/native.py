"""Executable, finite external representation of TOM v0.7's stated term laws.

This module is an independent CPU reference, not an assignment of the open
jitter, actualization, pinion, observation, or recurrence laws on source p.14.
It executes binding/SDF checks, licensed normalization, exact history prefix
preservation, and a continuation relation with explicitly supplied guards.
Opaque symbolic roles remain opaque; a symbolic result is not a physical
observation. The optional scalar diagnostic never replaces a native term.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, IntFlag
from fractions import Fraction
from pathlib import Path
import re
import struct
from typing import Iterable, Mapping, Sequence

NONE = 0xFFFFFFFF
INPUT_MAGIC = 0x314E4F54
OUTPUT_MAGIC = 0x31524F54
ABI_VERSION = 1
SOURCE_EXPRESSION = (
    "TOM := InverseOccam[ Arch[ C[J[T]], E[C[J[T]]; InvLog[phi]] ] ] "
    "qualified_by forward_T_precedence"
)
SOURCE_PDF_SHA256 = "97582a16bd54d690b27105f9b09dc48d2b5716bbae2fff2a5e74190278640fbc"


class Op(IntEnum):
    DECL = 1
    J = 2
    INVLOG = 3
    C = 4
    E = 5
    ARCH = 6
    INVERSE_OCCAM = 7
    LATER_T = 8
    SELF = 9
    FORWARD_T = 10


class Status(IntFlag):
    INVALID = 1
    TEMPORAL = 2
    PREFIX_REWRITE = 4
    FUTURE_EVIDENCE = 8
    PENDING_GUARD = 16
    OPEN_LAW = 32
    UNGUARDED_RESULT = 64
    CAPACITY = 128


class Flag(IntFlag):
    ALIAS_A_T = 1
    REQUIRE_SOURCE_TOM = 2
    SCALAR_LOG_ECHO = 4
    ADVANCE_TRANSACTION = 8


class RequestCode(IntEnum):
    DECLARED = 0
    RESOLVED = 1
    PENDING_GUARD = 2
    OPEN_CONTINUATION_LAW = 3
    UNGUARDED_RESULT = 4
    INVALID = 5
    BLOCKED_TRANSACTION = 6


SYMBOL_IDS = {
    "T": 1, "phi": 2, "J": 3, "InvLog": 4, "C": 5, "E": 6,
    "Arch": 7, "InverseOccam": 8, "TOM": 9, "Klein": 10,
    "Matryoshka": 11, "A": 12,
}
ARITIES = {op: (0 if op in (Op.DECL, Op.SELF) else
                2 if op in (Op.E, Op.ARCH) else 1) for op in Op}
Record = tuple[int, int, int, int, int, int, int, int]


def _word(value: int) -> int:
    if not isinstance(value, int) or not 0 <= value <= NONE:
        raise ValueError("ABI word must be an unsigned 32-bit integer")
    return value


def _wide_words(value: int) -> tuple[int, int]:
    if not isinstance(value, int) or not 0 <= value < 1 << 64:
        raise ValueError("external temporal reading must fit unsigned 64 bits")
    return value & NONE, value >> 32


def symbol_id(name: str | int, declared: Mapping[str, int] | None = None) -> int:
    value = name if isinstance(name, int) else (
        SYMBOL_IDS[name] if name in SYMBOL_IDS else (declared or {})[name])
    _word(value)
    if value == 0 or 12 < value < 256:
        raise ValueError("external declaration ids must be >=256")
    return value


@dataclass(frozen=True, eq=False)
class Term:
    """A finite syntax value; Python object identity is not definition equality."""
    op: Op
    args: tuple[Term, ...] = ()
    aux: int = 0

    def __post_init__(self):
        if len(self.args) != ARITIES[self.op]:
            raise ValueError(f"{self.op.name} needs {ARITIES[self.op]} operands")
        if self.op in (Op.DECL, Op.SELF):
            symbol_id(self.aux)
        elif self.op == Op.LATER_T:
            _word(self.aux)
        elif self.aux:
            raise ValueError("only declarations, self names and Later_T use aux")


def decl(name: str | int, declared: Mapping[str, int] | None = None) -> Term:
    return Term(Op.DECL, aux=symbol_id(name, declared))


def self_name(name: str | int = "TOM") -> Term:
    return Term(Op.SELF, aux=symbol_id(name))


def apply(op: Op | str, *args: Term) -> Term:
    return Term(Op[op] if isinstance(op, str) else op, tuple(args))


def later(guard_id: int, value: Term) -> Term:
    return Term(Op.LATER_T, (value,), guard_id)


def source_root(time_name: str = "T") -> Term:
    direct = apply(Op.C, apply(Op.J, decl(time_name)))
    echo = apply(Op.E, direct, apply(Op.INVLOG, decl("phi")))
    return apply(Op.FORWARD_T, apply(Op.INVERSE_OCCAM, apply(Op.ARCH, direct, echo)))


def expand_declared_abbreviations(name: str) -> Term:
    """Evaluate the p.3 declared binding c/e/TOM, without adding native opcodes.

    This is distinct from ``decl('TOM')``, which stores the first-class name.
    Source evaluation resolves a named reference to its supplied definition;
    it does not assign a dynamic observation to that definition.
    """
    direct = apply(Op.C, apply(Op.J, decl("T")))
    echo = apply(Op.E, direct, apply(Op.INVLOG, decl("phi")))
    bindings = {"c": direct, "e": echo,
                "TOM": apply(Op.FORWARD_T, apply(Op.INVERSE_OCCAM, apply(Op.ARCH, direct, echo)))}
    try:
        return bindings[name]
    except KeyError as exc:
        raise ValueError(f"no source abbreviation is declared for {name!r}") from exc


def parse_source_expression(text: str, *, alias_a_t: bool = False) -> Term:
    """Parse source bindings and expand c/e/TOM before binary serialization.

    Supports p.3 bracket notation, ordered semicolon/comma operands, explicit
    forward qualification, and c/e/TOM definition lines. Definition lines are
    checked against the source binding; this is not permission to redefine it.
    The iterative parser places no fixed semantic limit on nesting depth.
    It intentionally is not a parser for the TOM.tom document's editorial
    attribution/header/checklist sections or an unrestricted extension language.
    """
    if not isinstance(text, str):
        raise TypeError("source must be Unicode text")
    token_pattern = re.compile(r"\s+|\ufeff|\#[^\n]*|//[^\n]*|:=|≺|[A-Za-z_][A-Za-z0-9_]*|φ|[][(),;⟨⟩<>]")
    tokens = []
    position = 0
    while position < len(text):
        match = token_pattern.match(text, position)
        if not match:
            raise ValueError(f"unsupported source token at character {position}: {text[position:position+16]!r}")
        token = match.group()
        if not (token.isspace() or token == "\ufeff" or token.startswith(("#", "//"))):
            tokens.append("phi" if token == "φ" else token)
        position = match.end()
    if not tokens:
        raise ValueError("source expression is empty")
    bindings = {name: expand_declared_abbreviations(name) for name in ("c", "e", "TOM")}
    operators = {"J": Op.J, "InvLog": Op.INVLOG, "INVLOG": Op.INVLOG,
                 "C": Op.C, "E": Op.E, "Arch": Op.ARCH, "ARCH": Op.ARCH,
                 "InverseOccam": Op.INVERSE_OCCAM, "INVERSE_OCCAM": Op.INVERSE_OCCAM,
                 "FORWARD_T": Op.FORWARD_T}
    closing = {"[": "]", "(": ")", "⟨": "⟩", "<": ">"}

    def read_expression(index):
        stack = []
        while True:
            if index >= len(tokens):
                raise ValueError("missing source operand")
            name = tokens[index]
            index += 1
            if index < len(tokens) and tokens[index] in closing:
                if name not in operators:
                    raise ValueError(f"{name!r} has no source application rule")
                stack.append((name, closing[tokens[index]], []))
                index += 1
                continue
            if name in bindings:
                value = bindings[name]
            elif name in SYMBOL_IDS:
                value = decl(name)
            elif name == "self_TOM":
                value = self_name()
            else:
                raise ValueError(f"unknown source reference {name!r}")
            while stack:
                name, close, arguments = stack[-1]
                arguments.append(value)
                if index >= len(tokens):
                    raise ValueError(f"missing closing {close!r}")
                following = tokens[index]
                index += 1
                if following in (",", ";"):
                    break
                if following != close:
                    raise ValueError(f"expected ordered operand separator or {close!r}; got {following!r}")
                stack.pop()
                value = apply(operators[name], *arguments)
            else:
                return value, index

    def qualify(value, index):
        if index < len(tokens) and tokens[index] in ("qualified_by", "QUALIFIED_BY"):
            if index+1 >= len(tokens) or tokens[index+1] not in ("forward_T_precedence", "FORWARD_T_PRECEDENCE"):
                raise ValueError("unknown source qualification")
            return apply(Op.FORWARD_T, value), index+2
        if index < len(tokens) and tokens[index] == "≺":
            if index+1 >= len(tokens) or tokens[index+1] != "T":
                raise ValueError("precedence must be qualified by T")
            return apply(Op.FORWARD_T, value), index+2
        return value, index

    index = 0
    while index < len(tokens):
        assignment = index+1 < len(tokens) and tokens[index+1] == ":="
        if assignment:
            name = tokens[index]
            if name not in bindings:
                raise ValueError(f"{name!r} is not a source-declared abbreviation")
            value, index = read_expression(index+2)
            value, index = qualify(value, index)
            if not definition_equal(value, expand_declared_abbreviations(name), alias_a_t=alias_a_t):
                raise ValueError(f"definition of {name!r} changes the source binding")
            bindings[name] = value
        else:
            value, index = read_expression(index)
            value, index = qualify(value, index)
        if index < len(tokens):
            if not assignment or tokens[index] != ";":
                raise ValueError(f"unexpected material after source expression: {tokens[index]!r}")
            index += 1
    return value


SOURCE_PROVENANCE_MAGIC = b"TOMSRC1\x00"


def source_provenance(text: str) -> bytes:
    """Length-prefixed UTF-8 source bytes; external metadata, not another SDF law."""
    data = text.encode("utf-8")
    return SOURCE_PROVENANCE_MAGIC + struct.pack("<Q", len(data)) + data


def read_source_provenance(data: bytes) -> str:
    if len(data) < 16 or data[:8] != SOURCE_PROVENANCE_MAGIC:
        raise ValueError("invalid source provenance record")
    length = struct.unpack("<Q", data[8:16])[0]
    if len(data) != 16+length:
        raise ValueError("source provenance byte length mismatch")
    return data[16:].decode("utf-8")


def parse_term(value: Sequence, declared: Mapping[str, int] | None = None) -> Term:
    """Read ordered fixture arrays; no flattening, reassociation, or swapping."""
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("term must be a nonempty nested array")
    op = Op[value[0]]
    if op in (Op.DECL, Op.SELF):
        if len(value) != 2:
            raise ValueError("a declaration requires its explicit symbol")
        return Term(op, aux=symbol_id(value[1], declared))
    if op == Op.LATER_T:
        if len(value) != 3:
            raise ValueError("LATER_T requires guard id and child")
        return later(value[1], parse_term(value[2], declared))
    return Term(op, tuple(parse_term(v, declared) for v in value[1:]))


def encode_terms(roots: Iterable[Term]) -> tuple[list[Record], dict[int, int]]:
    """Iterative postorder encoder; runtime capacity is not an intrinsic depth law."""
    records: list[Record] = []
    ids: dict[int, int] = {}
    active: set[int] = set()
    for root in roots:
        stack = [(root, False)]
        while stack:
            term, leaving = stack.pop()
            identity = id(term)
            if identity in ids:
                continue
            if leaving:
                refs = [ids[id(arg)] for arg in term.args]
                records.append((int(term.op), len(refs), *(refs + [NONE] * (2-len(refs))),
                                term.aux, 0, 1, 0))
                ids[identity] = len(records) - 1
                active.remove(identity)
            else:
                if identity in active:
                    raise ValueError("cyclic storage is not a finite term; use a declared SELF name")
                active.add(identity)
                stack.append((term, True))
                stack.extend((child, False) for child in reversed(term.args))
    return records, ids


def normalize_records(records: Sequence[Record], alias_a_t: bool = False):
    """Only p.8 IO idempotence and explicitly selected p.5 alias are rewrites.

    Exact tuple equality checks all fields and ordered child representatives.
    The dictionary accelerates lookup; equality never relies on a hash alone.
    """
    normalized: list[Record] = []
    representatives: list[int] = []
    exact: dict[Record, int] = {}
    io_rewrites = alias_rewrites = 0
    for index, source in enumerate(records):
        p = list(source)
        for operand in range(p[1]):
            p[2+operand] = representatives[p[2+operand]]
        if p[0] == Op.DECL and p[4] == SYMBOL_IDS["A"] and alias_a_t:
            p[4] = SYMBOL_IDS["T"]
            alias_rewrites += 1
        if p[0] == Op.INVERSE_OCCAM and normalized[p[2]][0] == Op.INVERSE_OCCAM:
            p = list(normalized[p[2]])
            io_rewrites += 1
        record = tuple(p)
        representative = exact.setdefault(record, index)
        normalized.append(record)
        representatives.append(representative)
    return normalized, representatives, io_rewrites, alias_rewrites


def definition_equal(left: Term, right: Term, *, alias_a_t: bool = False) -> bool:
    records, ids = encode_terms((left, right))
    _, reps, _, _ = normalize_records(records, alias_a_t)
    return reps[ids[id(left)]] == reps[ids[id(right)]]


def arch_scalar(a: Fraction | int, b: Fraction | int) -> Fraction:
    """The explicitly separate p.10 exact rational scalar diagnostic."""
    a, b = Fraction(a), Fraction(b)
    return abs(a) + abs(b) - abs(a-b)


@dataclass(frozen=True)
class InverseLogEcho:
    """Exact symbolic k*c, k=-ln((1+sqrt(5))/2)<0; not a float approximation."""
    direct: Fraction
    coefficient: str = "-ln((1+sqrt(5))/2)"

    def __post_init__(self):
        object.__setattr__(self, "direct", Fraction(self.direct))
        if self.coefficient != "-ln((1+sqrt(5))/2)":
            raise ValueError("this diagnostic fixes the source's optional coefficient")

    @property
    def sign(self) -> int:
        return -(self.direct > 0) + (self.direct < 0)

    def arch_with_direct(self) -> Fraction:
        # p.10: c and k*c have opposite signs or are zero, since k<0.
        return Fraction(0)


@dataclass(frozen=True)
class Config:
    term_capacity: int
    history_capacity_words: int
    guard_capacity: int
    request_capacity: int

    def __post_init__(self):
        if not 1 <= self.term_capacity <= NONE:
            raise ValueError("term capacity is outside this binary format's address limits")
        for value in (self.history_capacity_words, self.guard_capacity, self.request_capacity):
            if not 0 <= value <= NONE:
                raise ValueError("capacity is outside this binary format's address limits")
        _word(self.case_words)
        _word(self.result_words)

    @property
    def case_words(self):
        return 16 + 8*self.term_capacity + 2*self.history_capacity_words + 4*self.guard_capacity + 4*self.request_capacity

    @property
    def result_words(self):
        return 16 + self.case_words + 9*self.term_capacity + 4*self.request_capacity + self.history_capacity_words

    @property
    def old_offset(self): return 16 + 8*self.term_capacity
    @property
    def proposed_offset(self): return self.old_offset + self.history_capacity_words
    @property
    def guards_offset(self): return self.proposed_offset + self.history_capacity_words
    @property
    def requests_offset(self): return self.guards_offset + 4*self.guard_capacity
    @property
    def normalized_offset(self): return 16 + self.case_words
    @property
    def reps_offset(self): return self.normalized_offset + 8*self.term_capacity
    @property
    def results_offset(self): return self.reps_offset + self.term_capacity
    @property
    def committed_offset(self): return self.results_offset + 4*self.request_capacity

    def header(self, cases: int, output: bool = False) -> list[int]:
        if not 1 <= cases <= NONE:
            raise ValueError("a batch must have at least one case")
        return [OUTPUT_MAGIC if output else INPUT_MAGIC, ABI_VERSION, cases,
                self.term_capacity, self.history_capacity_words, self.guard_capacity,
                self.request_capacity, self.case_words, self.result_words] + [0]*7


def bytes_to_words(data: bytes, capacity: int) -> list[int]:
    if len(data) > 4*capacity:
        raise ValueError("supplied bytes exceed selected storage capacity")
    data = data + bytes(4*capacity-len(data))
    return list(struct.unpack(f"<{capacity}I", data)) if capacity else []


def words_to_bytes(words: Sequence[int], length: int | None = None) -> bytes:
    data = struct.pack(f"<{len(words)}I", *words)
    return data if length is None else data[:length]


@dataclass
class NativeCase:
    records: list[Record]
    root: int
    old_history: bytes = b""
    proposed_history: bytes = b""
    guards: tuple[tuple[int, int, int, int], ...] = ()
    requests: tuple[tuple[int, int, int, int], ...] = ()
    previous: int = 0
    now: int = 0
    elapsed: int = 0
    latest_available: int = 0
    flags: int = 0

    @classmethod
    def from_term(cls, root: Term, *, guards=(), requests=(), **kwargs):
        """Guards=(id,met,Term|None); requests=(Term,declare0/consume1)."""
        roots = [root] + [g[2] for g in guards if g[2] is not None] + [q[0] for q in requests]
        records, ids = encode_terms(roots)
        return cls(records, ids[id(root)],
                   guards=tuple((gid, int(met), NONE if result is None else ids[id(result)], 0)
                                for gid, met, result in guards),
                   requests=tuple((ids[id(term)], mode, 0, 0) for term, mode in requests), **kwargs)

    def pack(self, config: Config) -> list[int]:
        if len(self.records) > config.term_capacity or len(self.guards) > config.guard_capacity or len(self.requests) > config.request_capacity:
            raise ValueError("case exceeds selected capacity; enlarge the external representation")
        header = [len(self.records), self.root, len(self.old_history), len(self.proposed_history),
                  len(self.guards), len(self.requests), *_wide_words(self.previous),
                  *_wide_words(self.now), *_wide_words(self.elapsed),
                  *_wide_words(self.latest_available), int(self.flags), 0]
        values = header + [v for record in self.records for v in record]
        values += [0]*(8*(config.term_capacity-len(self.records)))
        values += bytes_to_words(self.old_history, config.history_capacity_words)
        values += bytes_to_words(self.proposed_history, config.history_capacity_words)
        values += [v for g in self.guards for v in g] + [0]*(4*(config.guard_capacity-len(self.guards)))
        values += [v for q in self.requests for v in q] + [0]*(4*(config.request_capacity-len(self.requests)))
        for v in values: _word(v)
        return values


def _records_valid(records: Sequence[Record]) -> bool:
    for index, p in enumerate(records):
        try:
            op = Op(p[0])
        except ValueError:
            return False
        if p[1] != ARITIES[op] or p[5] != 0 or p[6] != 1 or p[7] != 0:
            return False
        if any(p[2+i] >= index for i in range(p[1])):
            return False
        if any(p[2+i] != NONE for i in range(p[1], 2)):
            return False
        if op in (Op.DECL, Op.SELF):
            if not p[4] or 12 < p[4] < 256:
                return False
        elif op != Op.LATER_T and p[4]:
            return False
    return True


def _source_pattern(records: Sequence[Record], root: int) -> bool:
    """Compare against independently constructed full source syntax modulo licensed laws."""
    expected, ids = encode_terms((source_root(),))
    # Cross-table structural comparison avoids relying on matching record numbers.
    stack = [(root, len(expected)-1)]
    while stack:
        actual_id, expected_id = stack.pop()
        a, b = records[actual_id], expected[expected_id]
        if (a[0], a[1], a[4:]) != (b[0], b[1], b[4:]):
            return False
        stack.extend((a[2+i], b[2+i]) for i in range(a[1]))
    return True


def _declared_operand_roles(records: Sequence[Record]) -> bool:
    """p.5 admits applications with their declared operands, not only arity."""
    def named(index, name):
        return records[index][0] == Op.DECL and records[index][4] == SYMBOL_IDS[name]
    for p in records:
        if p[0] == Op.J and not named(p[2], "T"):
            return False
        if p[0] == Op.INVLOG and not named(p[2], "phi"):
            return False
        if p[0] == Op.E:
            echo = records[p[3]]
            if records[p[2]][0] != Op.C or echo[0] != Op.INVLOG or not named(echo[2], "phi"):
                return False
    return True


def evaluate_words(values: Sequence[int], config: Config) -> list[int]:
    """Total bounded ABI reference including malformed inputs and failed transactions.

    Resolution means the supplied symbolic proposal is admissible under the
    selected external relation. This does not generate or authenticate a
    physical future result. Failure preserves the complete available old bytes.
    """
    if len(values) != config.case_words:
        raise ValueError("input case word extent mismatch")
    for v in values: _word(v)
    count, root, old_len, proposed_len, ng, nq = values[:6]
    previous, now, elapsed, available = (values[i] | (values[i+1] << 32) for i in (6,8,10,12))
    flags = values[14]
    records = [tuple(values[16+8*i:24+8*i]) for i in range(min(count, config.term_capacity))]
    guards = [tuple(values[config.guards_offset+4*i:config.guards_offset+4*i+4]) for i in range(min(ng, config.guard_capacity))]
    requests = [tuple(values[config.requests_offset+4*i:config.requests_offset+4*i+4]) for i in range(min(nq, config.request_capacity))]
    old = words_to_bytes(values[config.old_offset:config.proposed_offset])
    proposed = words_to_bytes(values[config.proposed_offset:config.guards_offset])
    status = Status(0)
    capacity = (count > config.term_capacity or old_len > len(old) or proposed_len > len(proposed)
                or ng > config.guard_capacity or nq > config.request_capacity)
    if capacity: status |= Status.CAPACITY
    if count == 0 or root >= count or values[15] or flags & ~15:
        status |= Status.INVALID
    advance = bool(flags & Flag.ADVANCE_TRANSACTION) or any(q[1] == 1 for q in requests)
    if now < previous or elapsed != now-previous or (advance and now == previous):
        status |= Status.TEMPORAL
    if available > now: status |= Status.FUTURE_EVIDENCE
    prefix = old_len <= len(old) and old_len <= proposed_len <= len(proposed) and old[:old_len] == proposed[:old_len]
    if not prefix: status |= Status.PREFIX_REWRITE
    if not capacity:
        valid = _records_valid(records)
        valid &= all(g[1] <= 1 and g[3] == 0 and (g[2] == NONE or g[2] < count) for g in guards)
        valid &= len({g[0] for g in guards}) == len(guards)
        valid &= all(q[0] < count and q[1] <= 1 and q[2] == q[3] == 0 for q in requests)
        if not valid: status |= Status.INVALID
    output = [0]*config.result_words
    output[1] = NONE
    output[16:16+config.case_words] = values
    output[6] = int(prefix)
    output[config.reps_offset:config.reps_offset+config.term_capacity] = [NONE]*config.term_capacity
    result_records = [[0, NONE, NONE, 0] for _ in range(config.request_capacity)]
    if not status & (Status.INVALID | Status.CAPACITY):
        norm, reps, io_rewrites, alias_rewrites = normalize_records(records, bool(flags & Flag.ALIAS_A_T))
        if not _declared_operand_roles(norm): status |= Status.INVALID
        output[1], output[2], output[8], output[9] = reps[root], count, io_rewrites, alias_rewrites
        output[7] = int(_source_pattern(norm, reps[root]))
        output[10] = int(bool(flags & Flag.SCALAR_LOG_ECHO) and bool(output[7]))
        if flags & Flag.REQUIRE_SOURCE_TOM and not output[7]: status |= Status.INVALID
        output[config.normalized_offset:config.normalized_offset+8*count] = [v for p in norm for v in p]
        output[config.reps_offset:config.reps_offset+count] = reps
        by_id = {g[0]: g for g in guards}
        for index, (term_id, mode, _, _) in enumerate(requests):
            canonical = reps[term_id]
            r = result_records[index]
            r[1] = canonical
            if mode == 0: continue
            term = norm[canonical]
            guard = by_id.get(term[4]) if term[0] == Op.LATER_T else None
            if term[0] != Op.LATER_T:
                r[0] = RequestCode.UNGUARDED_RESULT
                status |= Status.UNGUARDED_RESULT
            elif guard is None or guard[1] == 0:
                r[0] = RequestCode.PENDING_GUARD
                status |= Status.PENDING_GUARD
            elif guard[2] == NONE:
                r[0] = RequestCode.OPEN_CONTINUATION_LAW
                status |= Status.OPEN_LAW
            else:
                r[0], r[2] = RequestCode.RESOLVED, reps[guard[2]]
                output[4] += 1
                continue
            output[5] += 1
    else:
        for r in result_records[:len(requests)]: r[0] = RequestCode.INVALID
    if status:
        for r in result_records[:len(requests)]:
            if r[0] == RequestCode.RESOLVED:
                r[0] = RequestCode.BLOCKED_TRANSACTION
                output[4] -= 1
                output[5] += 1
    output[config.results_offset:config.committed_offset] = [int(v) for r in result_records for v in r]
    kept = old[:min(old_len, len(old))] if status else proposed[:proposed_len]
    output[config.committed_offset:] = bytes_to_words(kept, config.history_capacity_words)
    output[0], output[3] = int(status), len(kept)
    return output


def unpack_result(values: Sequence[int], config: Config) -> dict:
    if len(values) != config.result_words: raise ValueError("result stride mismatch")
    return {
        "status": values[0], "normalized_root": values[1], "term_count": values[2],
        "committed_history": words_to_bytes(values[config.committed_offset:], values[3]),
        "resolved": values[4], "unresolved": values[5], "prefix_preserved": bool(values[6]),
        "source_tom": bool(values[7]), "io_rewrites": values[8], "alias_rewrites": values[9],
        "optional_scalar_echo_zero_proved": bool(values[10]),
        "original": list(values[16:16+config.case_words]),
        "normalized": [tuple(values[config.normalized_offset+8*i:config.normalized_offset+8*i+8]) for i in range(values[2])],
        "representatives": list(values[config.reps_offset:config.reps_offset+values[2]]),
        "requests": [tuple(values[config.results_offset+4*i:config.results_offset+4*i+4]) for i in range(config.request_capacity)],
    }


def write_batch(path: str | Path, config: Config, cases: Sequence[Sequence[int]], *, output=False):
    stride = config.result_words if output else config.case_words
    if any(len(case) != stride for case in cases): raise ValueError("batch stride mismatch")
    with Path(path).open("wb") as stream:
        stream.write(words_to_bytes(config.header(len(cases), output)))
        for case in cases: stream.write(words_to_bytes(case))


def read_batch(path: str | Path, *, output=False):
    data = Path(path).read_bytes()
    if len(data) < 64 or len(data) % 4: raise ValueError("truncated native batch")
    words = struct.unpack(f"<{len(data)//4}I", data)
    h = words[:16]
    if h[0] != (OUTPUT_MAGIC if output else INPUT_MAGIC) or h[1] != ABI_VERSION or not h[2] or any(h[9:]):
        raise ValueError("invalid native batch header")
    config = Config(*h[3:7])
    if (h[7], h[8]) != (config.case_words, config.result_words): raise ValueError("native batch stride mismatch")
    stride = config.result_words if output else config.case_words
    if len(words) != 16+h[2]*stride: raise ValueError("native batch extent mismatch")
    return config, [list(words[16+i*stride:16+(i+1)*stride]) for i in range(h[2])]


def verify_results(input_path: str | Path, output_path: str | Path) -> dict:
    """Verify EVERY word, including originals, normalization, padding and histories."""
    config, cases = read_batch(input_path)
    result_config, results = read_batch(output_path, output=True)
    if config != result_config or len(cases) != len(results): raise AssertionError("input/result configuration mismatch")
    for index, (case, actual) in enumerate(zip(cases, results)):
        expected = evaluate_words(case, config)
        if actual != expected:
            first = next(i for i, (a,b) in enumerate(zip(actual,expected)) if a != b)
            raise AssertionError(f"case {index}, word {first}: actual={actual[first]}, reference={expected[first]}")
    return {"cases": len(cases), "words_per_result": config.result_words,
            "total_words_compared": len(cases)*config.result_words, "all_words_equal": True}
