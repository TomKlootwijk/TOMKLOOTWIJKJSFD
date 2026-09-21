"""Compatibility tests for explicit SDF/Klein -> TOM/K1 lowering."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from tom import native  # noqa: E402
from tom.sdf_core import KleinPack, Registry, SDFTerm, Sign  # noqa: E402
from tom.sdf_lowering import LoweringError, lower_term  # noqa: E402


class LoweringTests(unittest.TestCase):
    def setUp(self):
        self.registry = Registry()
        klein = KleinPack("fixture", "root")
        self.registry.register(SDFTerm("decl:T", "DECL", "declaration",
                                       sign=Sign.UNKNOWN, klein=klein))
        self.registry.register(SDFTerm("decl:phi", "DECL", "declaration",
                                       sign=Sign.UNKNOWN, klein=klein))
        self.registry.register(SDFTerm("j", "J", "field",
                                       operands=("decl:T",), klein=klein))
        self.registry.register(SDFTerm("c", "C", "field",
                                       operands=("j",), klein=klein))
        self.registry.register(SDFTerm("invlog", "INVLOG", "field",
                                       operands=("decl:phi",), klein=klein))
        self.registry.register(SDFTerm("e", "E", "field",
                                       operands=("c", "invlog"), klein=klein))
        self.registry.register(SDFTerm("arch", "ARCH", "field",
                                       operands=("c", "e"), klein=klein))

    def test_supported_terms_lower_with_semantic_sidecar(self):
        lowered = lower_term("arch", self.registry)
        self.assertEqual(lowered.native_term.op.name, "ARCH")
        self.assertEqual(lowered.sidecar["semantic_term"]["definition_id"], "arch")
        self.assertIn("klein", lowered.sidecar["preserved_above_abi"])
        self.assertEqual(len(lowered.sidecar["semantic_closure"]), 7)
        self.assertEqual(lowered.native_term.args[0].args[0].args[0].aux, native.SYMBOL_IDS["T"])
        self.assertEqual(lowered.native_term.args[1].args[1].args[0].aux, native.SYMBOL_IDS["phi"])
        self.assertEqual(lowered.manifest_bytes(), lower_term("arch", self.registry).manifest_bytes())

    def test_supported_lowering_executes_in_validated_native_backend(self):
        lowered = lower_term("arch", self.registry)
        config = native.Config(32, 8, 0, 0)
        case = native.NativeCase.from_term(lowered.native_term)
        result = native.unpack_result(native.evaluate_words(case.pack(config), config), config)
        self.assertEqual(result["status"], 0)

    def test_lowering_rejects_malformed_declarations_and_cycles(self):
        malformed = SDFTerm("malformed", "DECL", "declaration",
                            operands=("missing",), klein=KleinPack("fixture", "root"))
        self.registry.register(malformed)
        with self.assertRaises(LoweringError):
            lower_term("malformed", self.registry)

        cycle_a = SDFTerm("cycle:a", "J", "field", operands=("cycle:b",),
                          klein=KleinPack("fixture", "root"))
        cycle_b = SDFTerm("cycle:b", "J", "field", operands=("cycle:a",),
                          klein=KleinPack("fixture", "root"))
        self.registry.register(cycle_a)
        self.registry.register(cycle_b)
        with self.assertRaises(LoweringError):
            lower_term("cycle:a", self.registry)

    def test_unsupported_quote_is_rejected_instead_of_flattened(self):
        quote = SDFTerm("quote", "QUOTE", "quote",
                        operands=("arch",), klein=KleinPack("fixture", "root"))
        self.registry.register(quote)
        with self.assertRaises(LoweringError):
            lower_term("quote", self.registry)

    def test_open_obligation_is_rejected(self):
        open_term = SDFTerm("open", "FIELD", "field",
                            klein=KleinPack("fixture", "root"),
                            obligations=("bind_law",))
        self.registry.register(open_term)
        with self.assertRaises(LoweringError):
            lower_term("open", self.registry)


if __name__ == "__main__":
    unittest.main()
