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
    make_kernel_terms,
    pack_term,
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


if __name__ == "__main__":
    unittest.main()
