"""Compile source c/e/TOM bindings to executable native terms with source retention."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from tom.native import (Config, Flag, NativeCase, SOURCE_PDF_SHA256,
                        evaluate_words, parse_source_expression,
                        source_provenance, unpack_result, write_batch)


def require_distinct_paths(paths):
    """Reject spelling aliases, symlink aliases, and existing hard-link aliases."""
    selected = [(label,path) for label,path in paths if path is not None]
    for index,(label,path) in enumerate(selected):
        resolved = os.path.normcase(str(path.resolve()))
        for other_label,other_path in selected[:index]:
            same = resolved == os.path.normcase(str(other_path.resolve()))
            if not same and path.exists() and other_path.exists():
                same = path.samefile(other_path)
            if same:
                raise ValueError(f"{label} and {other_label} refer to the same file; source and output paths must be distinct")


def publish_staged_files(artifacts):
    """Serialize every artifact before atomic per-file replacement.

    A serializer/write failure leaves every existing destination untouched.
    Replacement failures can leave a mix of old and new COMPLETE files; this
    deliberately does not claim a multi-file atomic transaction.
    """
    staged = []
    try:
        for destination,serialize in artifacts:
            destination = destination.resolve()
            destination.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix=f".{destination.name}.",suffix=".tmp",
                                             dir=destination.parent,delete=False) as stream:
                temporary = Path(stream.name)
            staged.append((temporary,destination))
            serialize(temporary)
            with temporary.open("r+b") as stream:
                stream.flush()
                os.fsync(stream.fileno())
        for temporary,destination in staged:
            os.replace(temporary,destination)
    finally:
        for temporary,_ in staged:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def compile_source(text: str, *, require_tom=False, alias_a_t=False, scalar_log_echo=False,
                   term_capacity=None, history_capacity_words=None):
    """Return (Config,input_words,oracle_words,metadata) without filesystem effects.

    Original UTF-8 source is a complete supplied provenance commitment in both
    old and proposed history. It is copied by native execution, so names and
    whitespace are recoverable even after licensed definition expansion.
    """
    root = parse_source_expression(text,alias_a_t=alias_a_t)
    provenance = source_provenance(text)
    flags = ((int(Flag.REQUIRE_SOURCE_TOM) if require_tom else 0) |
             (int(Flag.ALIAS_A_T) if alias_a_t else 0) |
             (int(Flag.SCALAR_LOG_ECHO) if scalar_log_echo else 0))
    case = NativeCase.from_term(root, requests=[(root,0)], flags=flags,
                               old_history=provenance, proposed_history=provenance)
    config = Config(term_capacity if term_capacity is not None else len(case.records),
                    history_capacity_words if history_capacity_words is not None else (len(provenance)+3)//4,
                    0, 1)
    words = case.pack(config)
    oracle = evaluate_words(words,config)
    result = unpack_result(oracle,config)
    if result["status"]:
        raise ValueError(f"source failed native admission with status {result['status']}")
    metadata = {
        "schema":"tom-native-source-compilation-v1",
        "source_pdf_sha256":SOURCE_PDF_SHA256,
        "source_text":text,
        "source_utf8_sha256":hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "declared_bindings":"c := C[J[T]]; e := E[c; InvLog[phi]]; TOM := InverseOccam[Arch[c;e]] qualified_by forward_T_precedence",
        "expansion_semantics":"Textual c/e/TOM references resolve the source's declared definitions before encoding. First-class DECL names remain available separately; expansion assigns no dynamic law.",
        "source_provenance":{
            "location":"complete old and proposed history bytes, then committed history in successful output",
            "format":"8-byte TOMSRC1\\0 magic, uint64 little-endian UTF-8 byte length, exact UTF-8 source",
            "bytes":len(provenance),
            "utf8_offset_bytes":16,
            "classification":"external retained source metadata, not an additional intrinsic operator or causal event",
        },
        "term_count":len(case.records),
        "root_id":case.root,
        "term_capacity":config.term_capacity,
        "history_capacity_words":config.history_capacity_words,
        "case_words":config.case_words,
        "result_words":config.result_words,
        "full_source_tom":result["source_tom"],
        "io_rewrites":result["io_rewrites"],
        "alias_rewrites":result["alias_rewrites"],
        "optional_scalar_echo_zero_proved":result["optional_scalar_echo_zero_proved"],
        "unique_dynamics_assigned":False,
    }
    return config, words, oracle, metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--expression",help="source expression or c/e/TOM definition sequence; default TOM")
    source.add_argument("--source-file",type=Path,help="UTF-8 expression text (not TOM.tom editorial headers/checklists)")
    parser.add_argument("--out",type=Path,required=True,help="native TON1 input image")
    parser.add_argument("--oracle",type=Path,help="optional independent Python TOR1 expected output")
    parser.add_argument("--json",type=Path,help="metadata path; default OUT.source.json")
    parser.add_argument("--require-tom",action="store_true")
    parser.add_argument("--alias-a-t",action="store_true")
    parser.add_argument("--scalar-log-echo",action="store_true")
    parser.add_argument("--term-capacity",type=int)
    parser.add_argument("--history-capacity-words",type=int)
    args = parser.parse_args()
    try:
        json_path = args.json or args.out.with_suffix(".source.json")
        require_distinct_paths([("--source-file",args.source_file),("--out",args.out),
                                ("--oracle",args.oracle),("--json",json_path)])
        # read_bytes preserves BOMs/newlines exactly through UTF-8 round-trip.
        text = args.source_file.read_bytes().decode("utf-8") if args.source_file else (
            "TOM" if args.expression is None else args.expression)
        config, words, oracle, metadata = compile_source(text,require_tom=args.require_tom,
            alias_a_t=args.alias_a_t,scalar_log_echo=args.scalar_log_echo,
            term_capacity=args.term_capacity,history_capacity_words=args.history_capacity_words)
        metadata["input"] = str(args.out.resolve())
        if args.oracle: metadata["oracle"] = str(args.oracle.resolve())
        serialized_metadata = (json.dumps(metadata,indent=2,ensure_ascii=False)+"\n").encode("utf-8")
        artifacts = [(args.out,lambda path: write_batch(path,config,[words]))]
        if args.oracle:
            artifacts.append((args.oracle,lambda path: write_batch(path,config,[oracle],output=True)))
        artifacts.append((json_path,lambda path: path.write_bytes(serialized_metadata)))
        publish_staged_files(artifacts)
        print(json.dumps(metadata,ensure_ascii=True))
    except (OSError,ValueError,KeyError) as exc:
        parser.exit(2,f"compile_native_source: {exc}\n")


if __name__ == "__main__":
    main()
