"""Run a small guarded revision history through a real TOM native executable.

The caller chooses the plan, guard and supplied result. This demonstrates the
declared continuation contract; it is not a prediction or an invented TOM law.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"python"))
from tom.native import (Config,Flag,NativeCase,Op,RequestCode,SOURCE_EXPRESSION,
                        SOURCE_PDF_SHA256,Status,decl,evaluate_words,later,
                        parse_source_expression,read_batch,self_name,
                        unpack_result,verify_results,write_batch)
from compile_native_source import publish_staged_files


def event_bytes(event):
    return (json.dumps(event,ensure_ascii=False,separators=(",",":"))+"\n").encode("utf-8")


def history_events(data):
    return [json.loads(line) for line in data.decode("utf-8").splitlines()]


def friendly_history(events):
    if not events: return "Empty."
    labels = []
    for event in events:
        if event["event"] == "source_definition": labels.append("Full TOM source definition.")
        elif event["event"] == "supplied_revision": labels.append(event["plan"])
        else: labels.append("Later correction: "+event["plan"]+" Earlier blue plan retained.")
    return " / ".join(labels)


def resumed_case(previous_path,proposed_kind,guard_met,result_symbol):
    """Read actual runner output; retain its original terms and committed bytes."""
    config,values = read_batch(previous_path,output=True)
    if len(values) != 1: raise ValueError("demo resume requires exactly one actual result")
    result = unpack_result(values[0],config)
    original = result["original"]
    records = [tuple(original[16+8*i:24+8*i]) for i in range(original[0])]
    root = original[1]
    deferred = next(i for i,record in enumerate(records) if record[0] == Op.LATER_T)
    symbol_ids = {record[4]:i for i,record in enumerate(records) if record[0] == Op.DECL}
    old = result["committed_history"]
    if proposed_kind == "blue":
        proposed = old+event_bytes({"event":"supplied_revision","symbol":256,"plan":"Paint the door blue."})
    elif proposed_kind == "overwrite":
        if b"blue" not in old: raise AssertionError("the accepted blue commitment is missing")
        proposed = old.replace(b"blue",b"teal",1)  # same byte length; actual content changes
    elif proposed_kind == "correction":
        proposed = old+event_bytes({"event":"later_correction","symbol":257,"plan":"Paint the door teal.",
                                   "note":"The earlier blue commitment stays in its original position."})
    else: raise ValueError("unknown demo proposal")
    committed_offset=6 if result['status'] else 8
    previous = original[committed_offset] | (original[committed_offset+1]<<32)
    now = (original[8] | (original[9]<<32))+1
    case = NativeCase(records,root,old,proposed,
        guards=((7,int(guard_met),symbol_ids[result_symbol],0),),
        requests=((root,0,0,0),(deferred,1,0,0),(symbol_ids[257],0,0,0)),
        previous=previous,now=now,elapsed=now-previous,latest_available=now,
        flags=Flag.REQUIRE_SOURCE_TOM|Flag.ADVANCE_TRANSACTION)
    return config,case


def run_demo(executable: Path,directory: Path):
    executable = executable.resolve()
    if not executable.is_file(): raise ValueError(f"native executable is missing: {executable}")
    directory.mkdir(parents=True,exist_ok=True)
    root = parse_source_expression(SOURCE_EXPRESSION)
    deferred = later(7,self_name())
    initial_history = event_bytes({"event":"source_definition","text":SOURCE_EXPRESSION})
    blue_history = event_bytes({"event":"supplied_revision","symbol":256,"plan":"Paint the door blue."})
    correction_history = event_bytes({"event":"later_correction","symbol":257,"plan":"Paint the door teal.",
                                      "note":"The earlier blue commitment stays in its original position."})
    initial = NativeCase.from_term(root,guards=[(7,False,decl(256))],
                    requests=[(root,0),(deferred,0),(decl(257),0)],
                    proposed_history=initial_history,flags=Flag.REQUIRE_SOURCE_TOM)
    config = Config(len(initial.records),(len(initial_history+blue_history+correction_history)+3)//4,1,3)
    scenarios = [
        ("01_source_admitted","Start with the source definition",None,False,None,0,
         "The full source is admitted. A named later continuation is declared, without consuming a future result."),
        ("02_waiting_for_guard","Wait for the caller's condition","blue",False,256,int(Status.PENDING_GUARD),
         "The caller proposes a blue plan, but the supplied guard is false. Nothing is added to completed history."),
        ("03_supplied_revision","Accept the supplied revision","blue",True,256,0,
         "The caller now supplies a met guard and the blue result. The revision is appended after the existing source commitment."),
        ("04_forbidden_overwrite","Reject editing the accepted past","overwrite",True,257,int(Status.PREFIX_REWRITE),
         "Changing the existing blue bytes to teal is rejected, even though their lengths match and the guard is met. The candidate result is blocked."),
        ("05_legal_correction","Append a correction","correction",True,257,0,
         "The caller appends a teal correction. Both the earlier blue commitment and the later correction remain visible in order."),
    ]
    steps = []
    previous_path = None
    for stem,title,kind,met,symbol,wanted_status,meaning in scenarios:
        if previous_path is None:
            case = initial
        else:
            config,case = resumed_case(previous_path,kind,met,symbol)
        input_path = directory/(stem+".ton")
        reference_path = directory/(stem+".reference.tor")
        output_path = directory/(stem+".tor")
        runner_report = directory/(stem+".runner.json")
        words = case.pack(config)
        expected = evaluate_words(words,config)
        publish_staged_files([(input_path,lambda path:write_batch(path,config,[words])),
                              (reference_path,lambda path:write_batch(path,config,[expected],output=True))])
        command = [str(executable),"--input",str(input_path),"--output",str(output_path),
                   "--repeat","1","--json",str(runner_report)]
        if previous_path:command += ['--resume',str(previous_path)]
        completed = subprocess.run(command,capture_output=True,text=True)
        if completed.returncode:
            raise RuntimeError(f"native execution failed at {title}: {completed.stderr.strip()}")
        verification = verify_results(input_path,output_path)
        actual_config,actual_values = read_batch(output_path,output=True)
        actual = unpack_result(actual_values[0],actual_config)
        if actual["status"] != wanted_status:
            raise AssertionError(f"{title}: status {actual['status']} differs from scenario {wanted_status}")
        if not actual["source_tom"]: raise AssertionError("full source binding was lost")
        wanted_history = case.old_history if wanted_status else case.proposed_history
        if actual["committed_history"] != wanted_history:
            raise AssertionError("actual committed bytes differ from the scenario's exact expected history")
        request = actual["requests"][1]
        if kind == "overwrite" and request[0] != RequestCode.BLOCKED_TRANSACTION:
            raise AssertionError("the forbidden overwrite published its supplied result")
        runner = json.loads(runner_report.read_text())
        if previous_path and not runner.get('resume_validated'):
            raise AssertionError('runner did not validate the actual prior result')
        step = {
            "step":len(steps)+1,"name":title,"meaning":meaning,
            "status":[status.name for status in Status if actual["status"]&status] or ["ADMITTED"],
            "continuation_request":RequestCode(request[0]).name,
            "resolved_requests":actual["resolved"],"full_source_tom":actual["source_tom"],
            "resumed_from_actual_output":str(previous_path.resolve()) if previous_path else None,
            "previous_output_sha256":hashlib.sha256(previous_path.read_bytes()).hexdigest() if previous_path else None,
            "before":history_events(case.old_history),"proposed":history_events(case.proposed_history),
            "committed":history_events(actual["committed_history"]),
            "history_bytes":{"before":len(case.old_history),"proposed":len(case.proposed_history),
                             "committed":len(actual["committed_history"])},
            "external_order_tags":{"previous_committed":case.previous,"this_attempt":case.now,"elapsed":case.elapsed},
            "input":str(input_path.resolve()),"output":str(output_path.resolve()),
            "output_sha256":hashlib.sha256(output_path.read_bytes()).hexdigest(),
            "verification":verification,"runner":runner,
        }
        steps.append(step)
        previous_path = output_path
    report = {
        "title":"A plan can be corrected without rewriting its past",
        "purpose":"A small guarded revision-history demo using the full source TOM expression and a real native runner.",
        "caller_choices":"The caller chooses every guard, plan value, result symbol and order tag. These are demonstration inputs, not dynamics or observations selected by TOM.",
        "time_policy":"Each attempt uses a later external order tag. Its previous tag remains the last committed tag, so elapsed time includes rejected attempts. The runner reexecutes and validates the actual prior result through --resume before accepting a continuation.",
        "history_codec":"JSON Lines is an explicitly chosen external history codec. The native engine compares and preserves its complete bytes; it does not assign meaning to the plan text.",
        "source_pdf_sha256":SOURCE_PDF_SHA256,"source_expression":SOURCE_EXPRESSION,
        "executable":str(executable),"executable_sha256":hashlib.sha256(executable.read_bytes()).hexdigest(),
        "all_steps_verified":True,"words_compared":sum(step["verification"]["total_words_compared"] for step in steps),
        "all_continuations_loaded_from_actual_previous_output":True,"steps":steps,
    }
    markdown = ["# "+report["title"],"",report["purpose"],"",report["caller_choices"],"",
                "| Step | Result | Before | Proposed | Kept |","| --- | --- | --- | --- | --- |"]
    for step in steps:
        markdown.append("| "+" | ".join([step["name"],", ".join(step["status"]),
                         friendly_history(step["before"]),friendly_history(step["proposed"]),
                         friendly_history(step["committed"])])+" |")
    markdown += [""]
    for step in steps: markdown.append(f"{step['step']}. {step['meaning']}")
    markdown += ["",f"Every step was checked against the independent Python reference: {report['words_compared']:,} result words matched.",
                 "Each continuation reads the preceding runner output file, including its committed history. A rejected attempt adds no history entry. The earlier accepted bytes survive both the failed overwrite and the legal correction.",
                 "",report["time_policy"],"",report["history_codec"],""]
    publish_staged_files([(directory/"demo_report.json",lambda path:path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")),
                          (directory/"demo_report.md",lambda path:path.write_text("\n".join(markdown),encoding="utf-8"))])
    return {"report":str((directory/"demo_report.md").resolve()),"steps":len(steps),
            "all_steps_verified":True,"words_compared":report["words_compared"],
            "statuses":[step["status"] for step in steps],"gpu_executed":all(step['runner'].get('gpu_executed',False) for step in steps)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe",type=Path,default=ROOT/"build-cuda128/Release/tom_native_cpu.exe")
    parser.add_argument("--out",type=Path)
    args = parser.parse_args()
    try:
        directory=args.out or ROOT/'verification/native_20260918/demo'/('gpu' if 'cuda' in args.exe.name.lower() else 'cpu')
        print(json.dumps(run_demo(args.exe,directory),indent=2))
    except (OSError,ValueError,RuntimeError,AssertionError) as exc:
        parser.exit(1,f"native_continuation_demo: {exc}\n")


if __name__ == "__main__":
    main()
