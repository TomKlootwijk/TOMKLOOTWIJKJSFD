"""Reference tests for the clean project-specific SDF/Klein core."""

from __future__ import annotations

from fractions import Fraction
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from tom.sdf_core import (  # noqa: E402
    KleinPack,
    Registry,
    SDFError,
    SDFKernel,
    SDFTerm,
    Sign,
    Status,
    Symbolic,
    bind_readout,
    derive_pinion,
    Evaluation,
    make_kernel_terms,
    pack_term,
    term_from_canonical,
    unpack_term,
)


class SDFCoreTests(unittest.TestCase):
    def term(self, name: str = "term:v1", **kwargs) -> SDFTerm:
        return SDFTerm(
            definition_id=name,
            operator=kwargs.pop("operator", "FIELD"),
            role=kwargs.pop("role", "relation"),
            sign=kwargs.pop("sign", Sign.UNKNOWN),
            value=kwargs.pop("value", Fraction(3, 2)),
            klein=kwargs.pop("klein", KleinPack("test", "s0")),
            provenance=kwargs.pop("provenance", "fixture"),
            **kwargs,
        )

    def test_core_accepts_exact_values_and_rejects_floats(self):
        value = self.term(value=Fraction(5, 7))
        self.assertIn(b'"kind":"fraction"', value.canonical_bytes)
        with self.assertRaises(SDFError):
            self.term(value=0.5)

    def test_terms_freeze_caller_owned_sequences(self):
        operands = ["dep"]
        history = ["h0"]
        obligations = ["law"]
        term = self.term("frozen", operands=operands, history=history,
                         obligations=obligations)
        digest = term.digest
        operands.append("changed")
        history.append("changed")
        obligations.append("changed")
        self.assertEqual(term.operands, ("dep",))
        self.assertEqual(term.history, ("h0",))
        self.assertEqual(term.obligations, ("law",))
        self.assertEqual(term.digest, digest)

    def test_canonical_decoder_rejects_coercion_and_unknown_shape(self):
        canonical = self.term("strict", value=1).canonical()
        for bad in (1.9, True, "01"):
            candidate = dict(canonical)
            candidate["value"] = {"kind": "int", "value": bad}
            with self.assertRaises(SDFError):
                term_from_canonical(candidate)
        candidate = dict(canonical)
        candidate["unexpected"] = 1
        with self.assertRaises(SDFError):
            term_from_canonical(candidate)
        candidate = dict(canonical)
        candidate["operands"] = "dep"
        with self.assertRaises(SDFError):
            term_from_canonical(candidate)

    def test_unpack_rejects_duplicate_json_fields(self):
        with self.assertRaises(SDFError):
            unpack_term((
                b'{"format":"TOM-SDF-KLEIN-TERM-1",'
                b'"format":"TOM-SDF-KLEIN-TERM-1","term":{},"digest":"x"}'
            ))

    def test_double_packed_term_round_trips_and_detects_tampering(self):
        term = self.term(value=Symbolic("kappa*(a+b*phi)"),
                         obligations=("bind_application_law",))
        packed = pack_term(term)
        self.assertEqual(unpack_term(packed), term)
        tampered = packed.replace(b"bind_application_law", b"changed_law")
        with self.assertRaises(SDFError):
            unpack_term(tampered)

    def test_readout_does_not_change_definition_identity(self):
        first = self.term("term:first", value=0)
        second = self.term("term:second", value=0)
        self.assertNotEqual(first.digest, second.digest)
        first_readout = bind_readout(
            first, profile="distance", law="x-boundary", units="m",
            value=0, domain="application", falsifier="outside-sample",
        )
        second_readout = bind_readout(
            second, profile="distance", law="x-boundary", units="m",
            value=0, domain="application", falsifier="outside-sample",
        )
        self.assertEqual(first_readout.value, second_readout.value)
        self.assertNotEqual(first_readout.source_digest, second_readout.source_digest)

    def test_klein_pack_is_explicit_and_invertible(self):
        pack = KleinPack("host", "seam", 1, False, "declared")
        inverse = pack.inverted_pack()
        self.assertEqual(inverse.orientation, -1)
        self.assertTrue(inverse.inverted)
        self.assertTrue(pack.compatible_with(inverse))
        self.assertNotEqual(pack.canonical(), inverse.canonical())

    def test_self_reference_is_a_quoted_definition_not_a_python_cycle(self):
        registry, root = make_kernel_terms(seed="fixture-seed")
        kernel = registry.require(root)
        self.assertEqual(kernel.operands, ("kernel:quote:v1",))
        quote = registry.require("kernel:quote:v1")
        self.assertEqual(quote.operands, (root,))
        self.assertEqual(len(registry.canonical_bytes()), len(registry.canonical_bytes()))
        self.assertEqual(type(registry).unpack(registry.pack()).digest(), registry.digest())

    def test_evaluation_keeps_open_laws_explicit(self):
        registry, root = make_kernel_terms()
        kernel = SDFKernel(registry)
        result = kernel.evaluate(root, now=0, evidence_available=0)
        self.assertEqual(result.status, Status.OPEN_LAW)
        self.assertIn("obligations", result.reason)

    def test_valid_commit_and_rejection_preserve_previous_state(self):
        registry, _ = make_kernel_terms(seed="seed")
        term = self.term("term:commit", available_tick=1)
        registry.register(term)
        kernel = SDFKernel(registry, seed="seed", capacity=1)
        evaluation = kernel.evaluate(term.definition_id, now=1, evidence_available=1)
        self.assertEqual(evaluation.status, Status.DECLARED)
        pinion = derive_pinion("seed", None, 1, term.digest)
        committed = kernel.commit(evaluation, pinion=pinion)
        self.assertEqual(committed.status, Status.COMMITTED)
        before = kernel.state

        later = self.term("term:later", available_tick=2, history=kernel.state.history)
        registry.register(later)
        evaluation = kernel.evaluate(later.definition_id, now=2, evidence_available=2)
        second_pinion = derive_pinion("seed", pinion, 2, later.digest)
        rejected = kernel.commit(evaluation, pinion=second_pinion)
        self.assertEqual(rejected.status, Status.CAPACITY)
        self.assertEqual(kernel.state, before)

    def test_future_evidence_does_not_commit(self):
        registry = Registry()
        term = self.term("term:future", available_tick=3)
        registry.register(term)
        kernel = SDFKernel(registry, seed="seed")
        result = kernel.evaluate(term.definition_id, now=2, evidence_available=2)
        self.assertEqual(result.status, Status.FUTURE_EVIDENCE)

    def test_quote_cannot_admit_a_future_dependency(self):
        registry = Registry()
        target = self.term("target", value=42, available_tick=9)
        quote = self.term("quote", operator="QUOTE", operands=(target.definition_id,))
        registry.register(target)
        registry.register(quote)
        result = SDFKernel(registry).evaluate(quote.definition_id, now=1,
                                               evidence_available=1)
        self.assertEqual(result.status, Status.FUTURE_EVIDENCE)

    def test_commit_requires_kernel_bound_evidence_and_exact_pinion(self):
        registry = Registry()
        term = self.term("commit-bound", available_tick=1)
        registry.register(term)
        kernel = SDFKernel(registry, seed="seed")
        valid = derive_pinion("seed", None, 1, term.digest)
        forged = kernel.commit(Evaluation(Status.DECLARED, term), pinion=valid)
        self.assertEqual(forged.status, Status.INVALID)

        evaluation = kernel.evaluate(term.definition_id, now=1, evidence_available=1)
        wrong = type(valid)("seed", None, 99, 1, 1, 1, term.digest)
        rejected = kernel.commit(evaluation, pinion=wrong)
        self.assertEqual(rejected.status, Status.TEMPORAL)
        committed = kernel.commit(evaluation, pinion=valid)
        self.assertEqual(committed.status, Status.COMMITTED)

    def test_commit_rejects_stale_evaluation_tick(self):
        registry = Registry()
        term = self.term("stale", available_tick=1)
        registry.register(term)
        kernel = SDFKernel(registry, seed="seed")
        evaluation = kernel.evaluate(term.definition_id, now=1, evidence_available=1)
        pinion = derive_pinion("seed", None, 2, term.digest)
        rejected = kernel.commit(evaluation, pinion=pinion)
        self.assertEqual(rejected.status, Status.TEMPORAL)


if __name__ == "__main__":
    unittest.main()
