"""Source-derived tests and complete binary oracle for the native TOM runtime.

No GPU is launched by this script. --exe invokes only the supplied CPU runner.
--emit creates a mixed valid/malformed fixture; --verify-output checks an
externally produced CPU or GPU result, including every original/history byte.
"""
from __future__ import annotations
import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from tom.native import (
    NONE, Config, Flag, InverseLogEcho, NativeCase, Op, RequestCode, Status,
    SOURCE_EXPRESSION, apply, arch_scalar, decl, definition_equal, encode_terms, evaluate_words,
    expand_declared_abbreviations, parse_source_expression, read_source_provenance,
    later, normalize_records, parse_term, read_batch, self_name, source_root,
    unpack_result, verify_results, write_batch,
)

CONFIG = Config(40, 16, 4, 4)


def evaluate(case, config=CONFIG):
    return unpack_result(evaluate_words(case.pack(config), config), config)


def flatten_history(value):
    return bytes(b for row in value for b in row)


def acceptance_cases():
    document = json.loads((ROOT / "examples/native_acceptance_cases.json").read_text())
    defaults = document["defaults"]
    converted = []
    for source in document["cases"]:
        spec = {**defaults, **source}
        time = {**defaults["time"], **source.get("time", {})}
        symbols = spec["symbol_ids"]
        comparing = spec["operation"] == "assert_definition_equality"
        term = parse_term(spec["left"] if comparing else spec["term"], symbols)
        # Comparison is a read-only query over retained native terms, not a
        # new evolution rule. Keep history stationary for that operation.
        proposed = spec["history_before"] if comparing else spec["history_proposed"]
        requests = [(term, spec["mode"])]
        if comparing:
            requests.append((parse_term(spec["right"], symbols), 0))
        guards = [(g["id"], g["met"], parse_term(g["assigned_result"], symbols)
                   if "assigned_result" in g else None) for g in spec.get("guards", [])]
        case = NativeCase.from_term(term, guards=guards, requests=requests,
                    old_history=flatten_history(spec["history_before"]),
                    proposed_history=flatten_history(proposed), flags=spec["flags"], **time)
        words = case.pack(CONFIG)
        if not spec.get("sdf", True):
            words[16+8*case.root+6] = 0
        if "resource" in spec:
            # Inject a declared extent beyond the caller's selected capacity;
            # this tests the ABI's atomic rejection, not a GPU allocator.
            words[0] = CONFIG.term_capacity+1
        converted.append((spec["id"], words, spec))
    return converted


def generated_cases(random_count=256, valid_only=False):
    """Deterministic legal structures plus independently varied ABI faults."""
    cases = [(name, words) for name, words, _ in acceptance_cases()]
    rng = random.Random(0x070918)
    for index in range(random_count):
        pool = [decl("T"), decl("phi"), decl(256), self_name(), decl("A")]
        for _ in range(rng.randrange(1, 14)):
            op = rng.choice([Op.J, Op.INVLOG, Op.C, Op.E, Op.ARCH,
                             Op.INVERSE_OCCAM, Op.LATER_T, Op.FORWARD_T])
            if op == Op.J: new = apply(op, pool[0])
            elif op == Op.INVLOG: new = apply(op, pool[1])
            elif op == Op.E: new = apply(op, apply(Op.C, rng.choice(pool)), apply(Op.INVLOG, pool[1]))
            elif op == Op.ARCH: new = apply(op, rng.choice(pool), rng.choice(pool))
            elif op == Op.LATER_T: new = later(rng.randrange(3), rng.choice(pool))
            else: new = apply(op, rng.choice(pool))
            pool.append(new)
        root = source_root("A" if index%7 == 0 else "T") if index%3 == 0 else pool[-1]
        if valid_only:
            if index%3 == 0:
                root = apply(Op.FORWARD_T,apply(Op.INVERSE_OCCAM,root.args[0]))
            else:
                root = apply(Op.INVERSE_OCCAM,apply(Op.INVERSE_OCCAM,root))
        request_term = later(index%3, self_name()) if index%2 else root
        before = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 35)))
        proposed = before + bytes(rng.randrange(256) for _ in range(rng.randrange(0, 16)))
        previous = rng.choice([0, 1, (1<<32)-1, (1<<63)+11, (1<<64)-32])
        duration = rng.randrange(1 if valid_only else 0, 16)
        flags = (int(Flag.ALIAS_A_T | Flag.ADVANCE_TRANSACTION | Flag.SCALAR_LOG_ECHO) |
                 (int(Flag.REQUIRE_SOURCE_TOM) if index%3 == 0 else 0)) if valid_only else index%16
        case = NativeCase.from_term(root, guards=[(index%3, valid_only or index%5 != 0, decl(256) if valid_only or index%7 else None)],
                    requests=[(request_term, index%2)], old_history=before, proposed_history=proposed,
                    previous=previous, now=previous+duration, elapsed=duration,
                    latest_available=previous, flags=flags)
        words = case.pack(CONFIG)
        fault = 0 if valid_only else index%23
        if fault == 1: words[10] ^= 1
        elif fault == 2: words[12], words[13] = NONE, NONE
        elif fault == 3 and before: words[CONFIG.proposed_offset] ^= 1
        elif fault == 4: words[14] |= 16
        elif fault == 5: words[16+8*rng.randrange(len(case.records))+6] = 0
        elif fault == 6: words[16+8*case.root+7] = 7
        elif fault == 7: words[0] = CONFIG.term_capacity+1
        elif fault == 8: words[2] = 4*CONFIG.history_capacity_words+1
        elif fault == 9: words[3] = 4*CONFIG.history_capacity_words+1
        elif fault == 10: words[CONFIG.requests_offset+1] = 2
        elif fault == 11: words[CONFIG.guards_offset+1] = 2
        elif fault == 12: words[16+8*case.root+2] = case.root  # invalid used or unused ref
        elif fault == 13: words[16] = 99
        elif fault == 14: words[15] = 1
        elif fault == 15: words[4] = CONFIG.guard_capacity+1
        elif fault == 16: words[5] = CONFIG.request_capacity+1
        elif fault == 17: words[CONFIG.requests_offset] = NONE
        elif fault == 18: words[CONFIG.guards_offset+2] = NONE-1
        elif fault == 19: words[16+5] = 1
        elif fault == 20: words[16+4] = 13
        elif fault == 21: words[0] = 0
        elif fault == 22: words[1] = NONE
        cases.append((f"generated_{index:04d}", words))
    return cases


class NativeSourceTests(unittest.TestCase):
    def test_source_frontend_expands_declared_references(self):
        direct = apply(Op.C,apply(Op.J,decl("T")))
        echo = apply(Op.E,direct,apply(Op.INVLOG,decl("phi")))
        for name,expected in [("c",direct),("e",echo),("TOM",source_root())]:
            self.assertTrue(definition_equal(parse_source_expression(name),expected))
            self.assertTrue(definition_equal(expand_declared_abbreviations(name),expected))
        for source in [SOURCE_EXPRESSION,
                       "InverseOccam⟨Arch⟨c;e⟩⟩ ≺T",
                       "c := C<J<T>>; e := E<c;InvLog<phi>>; TOM := InverseOccam<Arch<c;e>> QUALIFIED_BY FORWARD_T_PRECEDENCE",
                       "c := C[J[T]]; e := E[c;InvLog[φ]]; TOM"]:
            with self.subTest(source=source):
                self.assertTrue(definition_equal(parse_source_expression(source),source_root()))
        # A stored first-class name and explicit evaluation of its binding are
        # distinct API requests; no implicit recurrence/observation is inferred.
        self.assertFalse(definition_equal(decl("TOM"),source_root()))
        alias_source = "c := C[J[A]]; e := E[c;InvLog[phi]]; InverseOccam[Arch[c;e]] qualified_by forward_T_precedence"
        with self.assertRaises(ValueError): parse_source_expression(alias_source)
        self.assertTrue(definition_equal(parse_source_expression(alias_source,alias_a_t=True),source_root(),alias_a_t=True))

    def test_source_frontend_rejects_changed_bindings(self):
        for source in ["c := J[T]", "e := E[InvLog[phi];c]", "TOM := Arch[c;e]",
                       "TOM := InverseOccam[Arch[e;c]] qualified_by forward_T_precedence",
                       "InvLog[Φ]", "unknown", "TOM trailing", "C[T)"]:
            with self.subTest(source=source):
                with self.assertRaises(ValueError): parse_source_expression(source)

    def test_source_frontend_depth_and_exact_spelling_retention(self):
        term = parse_source_expression("InverseOccam["*1400+"T"+"]"*1400)
        self.assertTrue(definition_equal(term,apply(Op.INVERSE_OCCAM,decl("T"))))
        sys.path.insert(0,str(ROOT/"tools"))
        from compile_native_source import compile_source
        source = "\ufeff# exact retained spelling\r\n  InverseOccam⟨Arch⟨c; e⟩⟩ ≺T\r\n"
        config,words,oracle,metadata = compile_source(source,require_tom=True)
        result = unpack_result(oracle,config)
        self.assertTrue(result["source_tom"])
        self.assertEqual(read_source_provenance(result["committed_history"]),source)
        self.assertEqual(result["original"],words)
        self.assertEqual(metadata["source_text"],source)

    def test_source_compiler_cli_rejects_overlapping_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base/"source.txt"
            source.write_bytes(b"TOM")
            out = base/"output.ton"
            cases = [
                ["--source-file",str(source),"--out",str(source)],
                ["--source-file",str(source),"--out",str(out),"--oracle",str(source)],
                ["--source-file",str(source),"--out",str(out),"--json",str(source)],
                ["--expression","TOM","--out",str(out),"--oracle",str(base/"."/"output.ton")],
                ["--expression","TOM","--out",str(out),"--json",str(out)],
                ["--expression","TOM","--out",str(out),"--oracle",str(base/"output.source.json")],
            ]
            source_link = base/"source-hardlink.txt"
            os.link(source,source_link)
            cases.append(["--source-file",str(source),"--out",str(source_link)])
            first = base/"existing-output.ton"
            second = base/"existing-oracle.tor"
            first.write_bytes(b"untouched")
            os.link(first,second)
            cases.append(["--expression","TOM","--out",str(first),"--oracle",str(second)])
            for arguments in cases:
                with self.subTest(arguments=arguments):
                    completed = subprocess.run([sys.executable,str(ROOT/"tools"/"compile_native_source.py"),*arguments],capture_output=True,text=True)
                    self.assertEqual(completed.returncode,2)
                    self.assertIn("same file",completed.stderr)
                    self.assertEqual(source.read_bytes(),b"TOM")
                    self.assertEqual(first.read_bytes(),b"untouched")
                    self.assertFalse(out.exists())

    def test_source_compiler_serialization_failure_preserves_all_artifacts(self):
        sys.path.insert(0,str(ROOT/"tools"))
        from compile_native_source import publish_staged_files
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            destinations = [base/"input.ton",base/"oracle.tor",base/"provenance.json"]
            originals = [b"existing input",b"existing oracle",b"existing provenance"]
            for path,data in zip(destinations,originals): path.write_bytes(data)
            for fail_at in range(len(destinations)):
                def serialize(path,index):
                    path.write_bytes(b"partially serialized candidate")
                    if index == fail_at:
                        raise ValueError("injected serialization failure")
                artifacts = [(path,lambda staging,index=i: serialize(staging,index)) for i,path in enumerate(destinations)]
                with self.assertRaisesRegex(ValueError,"serialization failure"):
                    publish_staged_files(artifacts)
                self.assertEqual([path.read_bytes() for path in destinations],originals)
                self.assertEqual(set(base.iterdir()),set(destinations))

    def test_source_compiler_replacement_failure_leaves_complete_files(self):
        sys.path.insert(0,str(ROOT/"tools"))
        import compile_native_source as compiler
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            destinations = [base/"input.ton",base/"oracle.tor",base/"provenance.json"]
            for path in destinations: path.write_bytes(b"complete old artifact")
            artifacts = [(path,lambda staging: staging.write_bytes(b"complete new artifact")) for path in destinations]
            actual_replace = os.replace
            calls = 0
            def replace(source,destination):
                nonlocal calls
                calls += 1
                if calls == 2: raise OSError("injected replace failure")
                actual_replace(source,destination)
            with mock.patch.object(compiler.os,"replace",side_effect=replace):
                with self.assertRaisesRegex(OSError,"replace failure"):
                    compiler.publish_staged_files(artifacts)
            self.assertEqual([path.read_bytes() for path in destinations],
                             [b"complete new artifact",b"complete old artifact",b"complete old artifact"])
            self.assertEqual(set(base.iterdir()),set(destinations))

    def test_source_expression_and_scalar_diagnostic_are_distinct(self):
        root = source_root()
        case = NativeCase.from_term(root, flags=Flag.REQUIRE_SOURCE_TOM | Flag.SCALAR_LOG_ECHO)
        result = evaluate(case)
        self.assertEqual(result["status"], 0)
        self.assertTrue(result["source_tom"])
        self.assertTrue(result["optional_scalar_echo_zero_proved"])
        self.assertEqual(result["normalized"][result["normalized_root"]][0], Op.FORWARD_T)
        self.assertEqual(result["original"], case.pack(CONFIG))
        self.assertEqual(result["term_count"], 9)
        for direct in [Fraction(-7,3), Fraction(0), Fraction(19,7)]:
            self.assertEqual(InverseLogEcho(direct).arch_with_direct(), 0)
        self.assertEqual(arch_scalar(1, -1), arch_scalar(1, -2))
        self.assertFalse(definition_equal(apply(Op.ARCH,decl(256),decl(257)), apply(Op.ARCH,decl(256),decl(258))))

    def test_licensed_io_idempotence_does_not_erase_content(self):
        original = apply(Op.ARCH, decl(256), decl(257))
        once = apply(Op.INVERSE_OCCAM, original)
        twice = apply(Op.INVERSE_OCCAM, once)
        self.assertTrue(definition_equal(once, twice))
        self.assertFalse(definition_equal(once, original))
        result = evaluate(NativeCase.from_term(twice))
        self.assertEqual(result["io_rewrites"], 1)
        self.assertEqual(result["term_count"], 5)
        self.assertEqual(result["normalized"][result["normalized_root"]][0], Op.INVERSE_OCCAM)

    def test_alias_requires_explicit_law(self):
        self.assertFalse(definition_equal(decl("A"), decl("T")))
        self.assertTrue(definition_equal(decl("A"), decl("T"), alias_a_t=True))
        unlicensed = evaluate(NativeCase.from_term(source_root("A"), flags=Flag.REQUIRE_SOURCE_TOM))
        licensed = evaluate(NativeCase.from_term(source_root("A"), flags=Flag.REQUIRE_SOURCE_TOM | Flag.ALIAS_A_T))
        self.assertTrue(unlicensed["status"] & Status.INVALID)
        self.assertEqual(licensed["status"], 0)
        self.assertEqual(licensed["alias_rewrites"], 1)

    def test_operand_roles_and_sdf_closure(self):
        for term in [apply(Op.J,decl("phi")), apply(Op.INVLOG,decl("T")),
                     apply(Op.E,decl("T"),decl("phi")), apply(Op.J,apply(Op.INVERSE_OCCAM,decl("T")))]:
            with self.subTest(op=term.op):
                result = evaluate(NativeCase.from_term(term))
                self.assertTrue(result["status"] & Status.INVALID)
                self.assertNotEqual(result["normalized_root"], NONE)  # inspectable role failure
        case = NativeCase.from_term(apply(Op.C,decl(256)))
        words = case.pack(CONFIG)
        words[16+6] = 0  # a missing child qualification invalidates the compound
        result = unpack_result(evaluate_words(words, CONFIG), CONFIG)
        self.assertTrue(result["status"] & Status.INVALID)
        self.assertEqual(result["normalized_root"], NONE)

    def test_order_and_grouping_remain_defining(self):
        a,b,c = decl(256),decl(257),decl(258)
        self.assertFalse(definition_equal(apply(Op.ARCH,a,b),apply(Op.ARCH,b,a)))
        self.assertFalse(definition_equal(apply(Op.ARCH,a,apply(Op.ARCH,b,c)),apply(Op.ARCH,apply(Op.ARCH,a,b),c)))
        self.assertEqual(arch_scalar(1,arch_scalar(2,3)), 2)
        self.assertEqual(arch_scalar(arch_scalar(1,2),3), 4)
        phi = decl("phi")
        self.assertFalse(definition_equal(apply(Op.INVLOG,apply(Op.INVLOG,phi)),phi))

    def test_declaration_and_future_result_are_distinct(self):
        own_name = self_name()
        declared = NativeCase.from_term(own_name, requests=[(own_name,0)])
        self.assertEqual(evaluate(declared)["status"], 0)  # stationary declaration permitted
        consumed = NativeCase.from_term(own_name, requests=[(own_name,1)], now=1, elapsed=1)
        self.assertEqual(evaluate(consumed)["status"], Status.UNGUARDED_RESULT)

    def test_later_does_not_invent_result(self):
        term = later(4,self_name())
        kwargs = dict(requests=[(term,1)], previous=8, now=9, elapsed=1, latest_available=8)
        no_guard = evaluate(NativeCase.from_term(term, **kwargs))
        no_law = evaluate(NativeCase.from_term(term, guards=[(4,True,None)], **kwargs))
        resolved = evaluate(NativeCase.from_term(term, guards=[(4,True,decl(256))], **kwargs))
        self.assertEqual(no_guard["status"], Status.PENDING_GUARD)
        self.assertEqual(no_law["status"], Status.OPEN_LAW)
        self.assertEqual(resolved["status"], 0)
        self.assertEqual(resolved["resolved"], 1)
        self.assertEqual(resolved["requests"][0][0], RequestCode.RESOLVED)

    def test_rejected_transaction_does_not_publish_supplied_result(self):
        term = later(4,self_name())
        case = NativeCase.from_term(term, guards=[(4,True,decl(256))], requests=[(term,1)],
                                   previous=8, now=8, elapsed=0, latest_available=8,
                                   old_history=b"abc", proposed_history=b"abcd")
        result = evaluate(case)
        self.assertEqual(result["status"], Status.TEMPORAL)
        self.assertEqual(result["requests"][0][0], RequestCode.BLOCKED_TRANSACTION)
        self.assertEqual(result["resolved"], 0)
        self.assertEqual(result["committed_history"], b"abc")

    def test_complete_history_prefix_not_hash_or_count(self):
        old = bytes([0,255,17,19,23])
        for proposed, expected in [(old+b"\x00\x80",0), (old[:-1],Status.PREFIX_REWRITE),
                                   (old[:-1]+b"X",Status.PREFIX_REWRITE), (old[::-1],Status.PREFIX_REWRITE)]:
            result = evaluate(NativeCase.from_term(decl(256), old_history=old, proposed_history=proposed))
            self.assertEqual(result["status"], expected)
            self.assertEqual(result["committed_history"], old if expected else proposed)
        case = NativeCase.from_term(decl(256), old_history=old, proposed_history=old)
        words = case.pack(CONFIG)
        words[CONFIG.old_offset+1] |= 0xFFFFFF00
        words[CONFIG.proposed_offset+1] |= 0xABCD0000
        result = unpack_result(evaluate_words(words,CONFIG),CONFIG)
        self.assertEqual(result["status"],0)  # padding is not history
        self.assertEqual(result["committed_history"],old)

    def test_external_time_no_wrap_or_duration_erasure(self):
        tests = [(0,0,0,0,0,0), (0,0,0,0,8,Status.TEMPORAL),
                 ((1<<64)-2,(1<<64)-1,1,(1<<64)-1,8,0),
                 ((1<<64)-1,0,1,0,0,Status.TEMPORAL),
                 (5,8,0,8,8,Status.TEMPORAL), (5,8,3,9,8,Status.FUTURE_EVIDENCE)]
        for previous,now,elapsed,available,flags,expected in tests:
            result = evaluate(NativeCase.from_term(decl(256),previous=previous,now=now,elapsed=elapsed,latest_available=available,flags=flags))
            self.assertEqual(result["status"],expected)

    def test_capacity_failure_and_all_original_words_retained(self):
        words = NativeCase.from_term(source_root(),old_history=b"retain",proposed_history=b"retain more").pack(CONFIG)
        words[0] = CONFIG.term_capacity+1
        result = unpack_result(evaluate_words(words,CONFIG),CONFIG)
        self.assertEqual(result["status"],Status.CAPACITY)
        self.assertEqual(result["normalized_root"],NONE)
        self.assertEqual(result["committed_history"],b"retain")
        self.assertEqual(result["original"],words)
        # Large capacities can be DESCRIBED when word strides fit. No allocation.
        self.assertGreater(Config((1<<20)+1,0,0,0).term_capacity,1<<20)

    def test_deep_nesting_is_resource_parameter(self):
        term = decl(256)
        for _ in range(1400): term = apply(Op.INVERSE_OCCAM,term)
        config = Config(1401,0,0,0)
        result = evaluate(NativeCase.from_term(term),config)
        self.assertEqual(result["status"],0)
        self.assertEqual(result["io_rewrites"],1399)
        self.assertEqual(result["normalized_root"],1)
        self.assertEqual(result["term_count"],1401)

    def test_valid_structural_stress_actually_normalizes(self):
        cases = generated_cases(128,valid_only=True)[len(acceptance_cases()):]
        for _,words in cases:
            result = unpack_result(evaluate_words(words,CONFIG),CONFIG)
            self.assertEqual(result["status"],0)
            self.assertGreaterEqual(result["io_rewrites"],1)

    def test_duplicates_unreferenced_records_and_multiple_requests(self):
        # Repeated source c is represented independently but is definitionally equal.
        a = apply(Op.C,apply(Op.J,decl("T")))
        b = apply(Op.C,apply(Op.J,decl("T")))
        root = apply(Op.FORWARD_T,apply(Op.INVERSE_OCCAM,apply(Op.ARCH,a,apply(Op.E,b,apply(Op.INVLOG,decl("phi"))))))
        result = evaluate(NativeCase.from_term(root,flags=Flag.REQUIRE_SOURCE_TOM))
        self.assertEqual(result["status"],0)
        self.assertTrue(result["source_tom"])
        pending, supplied = later(8,self_name()), later(9,self_name())
        case = NativeCase.from_term(root,guards=[(9,True,decl(256))],requests=[(pending,1),(supplied,1)],now=1,elapsed=1)
        result = evaluate(case)
        self.assertEqual(result["status"],Status.PENDING_GUARD)
        self.assertEqual(result["requests"][1][0],RequestCode.BLOCKED_TRANSACTION)
        self.assertEqual(result["resolved"],0)
        # An invalid extra definition outside the root remains subject to checks.
        invalid_extra = apply(Op.J,decl("phi"))
        case = NativeCase.from_term(root,requests=[(invalid_extra,0)])
        self.assertEqual(evaluate(case)["status"],Status.INVALID)

    def test_independent_source_acceptance_fixtures(self):
        for name,words,spec in acceptance_cases():
            with self.subTest(case=name):
                result = unpack_result(evaluate_words(words,CONFIG),CONFIG)
                expected = spec["expected"]
                if spec["operation"] == "assert_definition_equality":
                    self.assertEqual(result["requests"][0][1] == result["requests"][1][1], expected["definitionally_equal"])
                    continue
                if expected["status"] in ("admitted","rewritten"):
                    self.assertEqual(result["status"],0)
                elif expected["status"] == "pending":
                    self.assertTrue(result["status"] & (Status.PENDING_GUARD | Status.OPEN_LAW))
                else:
                    self.assertNotEqual(result["status"],0)
                if "history" in expected:
                    key = "history_proposed" if expected["history"] == "proposed" else "history_before"
                    self.assertEqual(result["committed_history"],flatten_history(spec[key]))
                self.assertEqual(result["original"],words)
                if "term" in expected:
                    term = parse_term(spec["term"],spec["symbol_ids"])
                    target = parse_term(expected["term"],spec["symbol_ids"])
                    self.assertTrue(definition_equal(term,target,alias_a_t=bool(spec["flags"] & Flag.ALIAS_A_T)))

    def test_batch_roundtrip_and_full_oracle(self):
        cases = [words for _,words in generated_cases(12)]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/"in.ton"
            out = Path(temporary)/"out.tor"
            write_batch(path,CONFIG,cases)
            write_batch(out,CONFIG,[evaluate_words(case,CONFIG) for case in cases],output=True)
            self.assertEqual(read_batch(path),(CONFIG,cases))
            self.assertTrue(verify_results(path,out)["all_words_equal"])


def emit_fixture(path: Path, random_count: int, valid_only=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    named = generated_cases(random_count,valid_only)
    cases = [words for _,words in named]
    oracle = [evaluate_words(case,CONFIG) for case in cases]
    write_batch(path,CONFIG,cases)
    reference = path.with_suffix(".reference.tor")
    write_batch(reference,CONFIG,oracle,output=True)
    report = {"source_cases":len(acceptance_cases()),"generated_cases":random_count,
              "generated_cases_all_admitted":valid_only,
              "case_count":len(cases),"input":str(path),"reference":str(reference),
              "case_words":CONFIG.case_words,"result_words":CONFIG.result_words,
              "cases":[{"name":name,"status":result[0]} for (name,_),result in zip(named,oracle)]}
    path.with_suffix(".manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit",type=Path)
    parser.add_argument("--random-cases",type=int,default=512)
    parser.add_argument("--valid-only",action="store_true")
    parser.add_argument("--input",type=Path)
    parser.add_argument("--verify-output",type=Path)
    parser.add_argument("--exe",type=Path)
    args = parser.parse_args()
    if args.emit:
        report=emit_fixture(args.emit,args.random_cases,args.valid_only)
        print(json.dumps({k:v for k,v in report.items() if k != "cases"}))
    elif args.verify_output:
        if not args.input: parser.error("--verify-output requires --input")
        print(json.dumps(verify_results(args.input,args.verify_output)))
    else:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(NativeSourceTests)
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        if not result.wasSuccessful(): sys.exit(1)
        if args.exe:
            with tempfile.TemporaryDirectory() as temporary:
                input_path=Path(temporary)/"native.ton"
                output_path=Path(temporary)/"native.cpu.tor"
                emit_fixture(input_path,args.random_cases,args.valid_only)
                subprocess.run([str(args.exe.resolve()),"--input",str(input_path),"--output",str(output_path)],check=True)
                print(json.dumps(verify_results(input_path,output_path)))
