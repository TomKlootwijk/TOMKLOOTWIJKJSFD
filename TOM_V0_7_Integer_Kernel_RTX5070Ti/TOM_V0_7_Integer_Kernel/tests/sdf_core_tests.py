"""Reference tests for the clean project-specific SDF/Klein core."""

from __future__ import annotations

from fractions import Fraction
from dataclasses import replace
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from tom.sdf_core import (  # noqa: E402
    CoreLimits,
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
        composed = pack.compose(inverse)
        self.assertEqual(composed.orientation, -1)
        self.assertTrue(composed.inverted)
        with self.assertRaises(SDFError):
            pack.compose(KleinPack("other", "seam", 1, False, "declared"))

    def test_evaluation_executes_the_finite_klein_seam_gate(self):
        registry = Registry()
        target = self.term("target", klein=KleinPack("target-host", "root"))
        quote = self.term("quote", operator="QUOTE", operands=(target.definition_id,))
        registry.register(target)
        registry.register(quote)
        result = SDFKernel(registry).evaluate("quote", now=1, evidence_available=1)
        self.assertEqual(result.status, Status.INVALID)

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

    def test_registry_and_evaluation_limits_are_explicit(self):
        limits = CoreLimits(max_terms=4, max_eval_depth=1, max_text_chars=8)
        registry = Registry(limits=limits)
        base = self.term("base", provenance="ok")
        registry.register(base)
        quote = self.term("quote", operator="QUOTE", operands=(base.definition_id,))
        registry.register(quote)
        deep = self.term("deep", operator="QUOTE", operands=(quote.definition_id,))
        registry.register(deep)
        registry.register(self.term("overflow"))
        with self.assertRaises(SDFError):
            registry.register(self.term("overflow2"))
        result = SDFKernel(registry, limits=limits).evaluate(
            deep.definition_id, now=0, evidence_available=0)
        self.assertEqual(result.status, Status.CAPACITY)

    def test_unknown_and_malformed_laws_cannot_enter_through_quote(self):
        for candidate, expected in (
            (self.term("target", operator="NO_SUCH_LAW"), Status.OPEN_LAW),
            (self.term("target", operator="DECL", operands=("missing",)), Status.INVALID),
            (self.term("target", operator="KERNEL", operands=("leaf",)), Status.OPEN_LAW),
        ):
            with self.subTest(operator=candidate.operator):
                registry = Registry()
                registry.register(candidate)
                registry.register(self.term("quote", operator="QUOTE", operands=("target",)))
                result = SDFKernel(registry).evaluate("quote", now=1, evidence_available=1)
                self.assertEqual(result.status, expected)

    def test_forged_context_cannot_bypass_an_open_law(self):
        registry = Registry()
        term = self.term("open", obligations=("unassigned",))
        registry.register(term)
        kernel = SDFKernel(registry, seed="seed")
        fake = replace(kernel.evaluate("open", now=1, evidence_available=1),
                       status=Status.DECLARED)
        before = kernel.state
        result = kernel.commit(fake, pinion=derive_pinion("seed", None, 1, term.digest))
        self.assertEqual(result.status, Status.OPEN_LAW)
        self.assertEqual(kernel.state, before)

    def test_zero_repeated_and_backward_pinion_ticks_are_rejected(self):
        first = derive_pinion("seed", None, 2, "payload")
        for parent, tick, elapsed in ((None, 0, None), (None, 2, 1),
                                      (first, 2, None), (first, 1, None)):
            with self.subTest(tick=tick, elapsed=elapsed):
                with self.assertRaises(SDFError):
                    derive_pinion("seed", parent, tick, "payload", elapsed=elapsed)

    def test_uncommitted_history_suffix_cannot_disappear_on_commit(self):
        registry = Registry()
        term = self.term("extra", history=("never-committed",))
        registry.register(term)
        kernel = SDFKernel(registry, seed="seed")
        result = kernel.commit(kernel.evaluate("extra", now=1, evidence_available=1),
                               pinion=derive_pinion("seed", None, 1, term.digest))
        self.assertEqual(result.status, Status.PREFIX_REWRITE)
        self.assertEqual(kernel.state.history, ())

    def test_snapshot_restores_full_chain_and_continues(self):
        registry = Registry()
        first = self.term("first", available_tick=1)
        second = self.term("second", available_tick=2, history=(first.digest,))
        registry.register(first)
        registry.register(second)
        kernel = SDFKernel(registry, seed="seed", capacity=4)
        first_eval = kernel.evaluate("first", now=1, evidence_available=1)
        first_pinion = derive_pinion("seed", None, 1, first.digest)
        self.assertEqual(kernel.commit(first_eval, pinion=first_pinion).status,
                         Status.COMMITTED)
        restored = SDFKernel.from_snapshot(kernel.snapshot())
        self.assertEqual(restored.state, kernel.state)
        self.assertEqual(restored.registry.digest(), kernel.registry.digest())
        second_eval = restored.evaluate("second", now=2, evidence_available=2)
        second_pinion = derive_pinion("seed", restored.state.pinion, 2, second.digest)
        self.assertEqual(restored.commit(second_eval, pinion=second_pinion).status,
                         Status.COMMITTED)
        self.assertEqual(restored.state.history, (first.digest, second.digest))

    def test_snapshot_digest_covers_nested_state(self):
        registry = Registry()
        term = self.term("snap", available_tick=1)
        registry.register(term)
        kernel = SDFKernel(registry, seed="seed")
        payload = json.loads(kernel.snapshot().decode("utf-8"))
        payload["state"]["tick"] = 99
        with self.assertRaises(SDFError):
            SDFKernel.from_snapshot(json.dumps(payload).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
