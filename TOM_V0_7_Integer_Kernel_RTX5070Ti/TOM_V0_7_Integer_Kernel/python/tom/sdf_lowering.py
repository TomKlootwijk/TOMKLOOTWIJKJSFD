"""Explicit lowering seam from SDF/Klein terms to the validated TOM backend.

The fixed TOM/K1 ABI cannot carry every universal semantic field. This module
therefore refuses unsupported operators and emits an explicit sidecar for the
fields that remain above the backend ABI. No Klein, pinion, provenance, or
obligation data is silently discarded.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Mapping

from . import native
from .sdf_core import Registry, SDFError, SDFTerm, canonical_json


class LoweringError(SDFError):
    """The selected TOM profile cannot represent a semantic term safely."""


DEFAULT_PROFILE: dict[str, native.Op] = {
    "J": native.Op.J,
    "INVLOG": native.Op.INVLOG,
    "InvLog": native.Op.INVLOG,
    "C": native.Op.C,
    "E": native.Op.E,
    "ARCH": native.Op.ARCH,
    "Arch": native.Op.ARCH,
    "INVERSE_OCCAM": native.Op.INVERSE_OCCAM,
    "InverseOccam": native.Op.INVERSE_OCCAM,
    "FORWARD_T": native.Op.FORWARD_T,
    "Forward_T": native.Op.FORWARD_T,
}


@dataclass(frozen=True)
class LoweredTerm:
    """Backend term plus an explicit semantic preservation sidecar."""

    semantic_id: str
    semantic_digest: str
    native_term: native.Term
    profile: str
    sidecar: dict

    def manifest_bytes(self) -> bytes:
        return canonical_json({
            "semantic_id": self.semantic_id,
            "semantic_digest": self.semantic_digest,
            "profile": self.profile,
            "native": native_term_json(self.native_term),
            "sidecar": self.sidecar,
        })


def _stable_symbol_id(definition_id: str) -> int:
    """Legacy hash mapping retained for callers of the old helper.

    Lowering no longer uses this lossy mapping.  A bundle-local, injective
    table is built by :func:`_symbol_table` instead.
    """
    digest = hashlib.sha256(definition_id.encode("utf-8")).digest()
    value = int.from_bytes(digest[:4], "little") | 0x100
    return value & 0xFFFFFFFF


def _symbol_name(definition_id: str) -> str | None:
    """Return a native well-known name encoded by a semantic declaration id."""
    candidates = (definition_id.removeprefix("decl:"), definition_id)
    for candidate in candidates:
        if candidate in native.SYMBOL_IDS:
            return candidate
    return None


def _reachable_terms(root_id: str, registry: Registry,
                     profile: Mapping[str, native.Op]) -> dict[str, SDFTerm]:
    """Validate and collect the complete reachable semantic closure.

    The old recursive lowering could overflow on deep inputs and returned an
    uncontrolled ``RecursionError`` for cycles.  An explicit active path gives
    callers a typed lowering failure instead.
    """
    seen: dict[str, SDFTerm] = {}
    active: set[str] = set()
    stack: list[tuple[str, bool]] = [(root_id, False)]
    while stack:
        definition_id, leaving = stack.pop()
        if leaving:
            active.discard(definition_id)
            continue
        if definition_id in active:
            raise LoweringError(f"cyclic semantic dependency at {definition_id!r}")
        if definition_id in seen:
            continue
        term = registry.require(definition_id)
        if term.operator in ("DECL", "DECLARATION", "SELF"):
            expected = 0
        elif term.operator == "QUOTE":
            raise LoweringError("QUOTE has no lossless representation in TOM/K1")
        elif term.operator in profile:
            op = profile[term.operator]
            try:
                expected = native.ARITIES[op]
            except (KeyError, TypeError) as exc:
                raise LoweringError(f"invalid native profile opcode for {term.operator!r}") from exc
        else:
            raise LoweringError(f"operator {term.operator!r} is not declared by lowering profile")
        if len(term.operands) != expected:
            raise LoweringError(
                f"operator {term.operator!r} requires {expected} operands, got {len(term.operands)}")
        seen[definition_id] = term
        active.add(definition_id)
        stack.append((definition_id, True))
        for operand in reversed(term.operands):
            if operand in active:
                raise LoweringError(f"cyclic semantic dependency at {operand!r}")
            if operand not in seen:
                stack.append((operand, False))
    return seen


def _symbol_table(terms: Mapping[str, SDFTerm]) -> dict[str, int]:
    """Build an injective native symbol table for one semantic closure."""
    result: dict[str, int] = {}
    owners: dict[int, str] = {}
    declarations = sorted(
        definition_id for definition_id, term in terms.items()
        if term.operator in ("DECL", "DECLARATION", "SELF"))
    for definition_id in declarations:
        name = _symbol_name(definition_id)
        if name is not None:
            symbol = native.SYMBOL_IDS[name]
        else:
            symbol = 256 + len([v for v in result.values() if v >= 256])
            while symbol in owners:
                symbol += 1
        owner = owners.get(symbol)
        if owner is not None and owner != definition_id:
            raise LoweringError(
                f"native symbol collision: {owner!r} and {definition_id!r} map to {symbol}")
        owners[symbol] = definition_id
        result[definition_id] = symbol
    return result


def native_term_json(term: native.Term) -> list:
    result = [term.op.name]
    if term.op in (native.Op.DECL, native.Op.SELF):
        result.append(term.aux)
    elif term.op == native.Op.LATER_T:
        result.extend([term.aux, native_term_json(term.args[0])])
    else:
        result.extend(native_term_json(arg) for arg in term.args)
    return result


def _lower_one(term: SDFTerm, registry: Registry, profile: Mapping[str, native.Op],
               cache: dict[str, native.Term], symbols: Mapping[str, int],
               closure: Mapping[str, SDFTerm]) -> native.Term:
    """Lower an already validated closure without Python recursion."""
    stack: list[tuple[str, bool]] = [(term.definition_id, False)]
    while stack:
        definition_id, leaving = stack.pop()
        if definition_id in cache:
            continue
        source = closure[definition_id]
        if source.obligations:
            raise LoweringError(
                f"{definition_id} has unresolved obligations: {source.obligations}")
        if not leaving:
            stack.append((definition_id, True))
            for operand in reversed(source.operands):
                if operand not in cache:
                    stack.append((operand, False))
            continue
        if source.operator in ("DECL", "DECLARATION"):
            lowered = native.Term(native.Op.DECL, aux=symbols[definition_id])
        elif source.operator == "SELF":
            lowered = native.Term(native.Op.SELF, aux=symbols[definition_id])
        else:
            op = profile[source.operator]
            args = tuple(cache[ref] for ref in source.operands)
            try:
                lowered = native.Term(op, args)
            except (KeyError, ValueError) as exc:
                raise LoweringError(
                    f"operator {source.operator!r} has incompatible TOM/K1 arity") from exc
        cache[definition_id] = lowered
    return cache[term.definition_id]


def lower_term(root_id: str, registry: Registry, *, profile_name: str = "TOM-K1-SDF",
               profile: Mapping[str, native.Op] | None = None) -> LoweredTerm:
    """Lower one supported semantic term without silently erasing metadata."""
    selected = dict(DEFAULT_PROFILE if profile is None else profile)
    root = registry.require(root_id)
    closure = _reachable_terms(root_id, registry, selected)
    symbols = _symbol_table(closure)
    native_root = _lower_one(root, registry, selected, {}, symbols, closure)
    closure_terms = [closure[key].canonical() for key in sorted(closure)]
    sidecar = {
        "semantic_term": root.canonical(),
        "semantic_closure": closure_terms,
        "closure_digest": "sha256:" + hashlib.sha256(canonical_json(closure_terms)).hexdigest(),
        "registry_digest": registry.digest(),
        "preserved_above_abi": [
            "sign", "klein", "pinion", "available_tick", "provenance",
            "history", "obligations", "value",
        ],
        "readout_policy": "application_readouts_are separate records",
        "loss_policy": "reject unsupported operators; never silently flatten",
    }
    return LoweredTerm(root.definition_id, root.digest, native_root,
                       profile_name, sidecar)
