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
    """Map a semantic declaration id to a stable external TOM symbol id."""
    digest = hashlib.sha256(definition_id.encode("utf-8")).digest()
    value = int.from_bytes(digest[:4], "little") | 0x100
    return value & 0xFFFFFFFF


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
               cache: dict[str, native.Term]) -> native.Term:
    if term.definition_id in cache:
        return cache[term.definition_id]
    if term.obligations:
        raise LoweringError(
            f"{term.definition_id} has unresolved obligations: {term.obligations}")
    if term.operator in ("DECL", "DECLARATION"):
        lowered = native.Term(native.Op.DECL, aux=_stable_symbol_id(term.definition_id))
    elif term.operator == "SELF":
        lowered = native.Term(native.Op.SELF, aux=_stable_symbol_id(term.definition_id))
    elif term.operator == "QUOTE":
        raise LoweringError(
            "QUOTE has no lossless representation in TOM/K1; use a versioned ABI extension")
    elif term.operator not in profile:
        raise LoweringError(
            f"operator {term.operator!r} is not declared by lowering profile")
    else:
        op = profile[term.operator]
        args = tuple(_lower_one(registry.require(ref), registry, profile, cache)
                     for ref in term.operands)
        try:
            lowered = native.Term(op, args)
        except (KeyError, ValueError) as exc:
            raise LoweringError(
                f"operator {term.operator!r} has incompatible TOM/K1 arity") from exc
    cache[term.definition_id] = lowered
    return lowered


def lower_term(root_id: str, registry: Registry, *, profile_name: str = "TOM-K1-SDF",
               profile: Mapping[str, native.Op] | None = None) -> LoweredTerm:
    """Lower one supported semantic term without silently erasing metadata."""
    selected = dict(DEFAULT_PROFILE if profile is None else profile)
    root = registry.require(root_id)
    native_root = _lower_one(root, registry, selected, {})
    sidecar = {
        "semantic_term": root.canonical(),
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

