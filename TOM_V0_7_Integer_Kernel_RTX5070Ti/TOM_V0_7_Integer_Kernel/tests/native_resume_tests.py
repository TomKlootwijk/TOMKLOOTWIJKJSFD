#!/usr/bin/env python3
"""The actual result of one native run constrains the next completed prefix."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from tom.native import Config,NativeCase,source_root,Flag,write_batch,verify_results


def main():
    p=argparse.ArgumentParser();p.add_argument('--exe',type=Path,required=True);p.add_argument('--out',type=Path)
    args=p.parse_args();config=Config(9,8,0,0);runs=[]
    with tempfile.TemporaryDirectory() as folder:
        folder=Path(folder);previous=folder/'first.tor'
        def run(name,before,after,old_time,new_time,resume=None,expect_success=True,expect_reason=None):
            source=folder/(name+'.ton');target=folder/(name+'.tor')
            case=NativeCase.from_term(source_root(),old_history=before,proposed_history=after,
                previous=old_time,now=new_time,elapsed=new_time-old_time,latest_available=new_time,
                flags=Flag.REQUIRE_SOURCE_TOM|Flag.ADVANCE_TRANSACTION)
            write_batch(source,config,[case.pack(config)])
            command=[str(args.exe.resolve()),'--input',str(source),'--output',str(target)]
            if resume:command+=['--resume',str(resume)]
            result=subprocess.run(command,capture_output=True,text=True)
            if expect_success:
                if result.returncode:raise AssertionError(result.stderr)
                checked=verify_results(source,target)
            else:
                if not result.returncode or target.exists():raise AssertionError('forged completed state was admitted or wrote output')
                if expect_reason and expect_reason not in result.stderr:
                    raise AssertionError('rejected for the wrong reason: '+result.stderr)
                checked={'rejected_before_output':True,'reason':result.stderr.strip()}
            runs.append({'name':name,'verification':checked})
            return target
        previous=run('first',b'past',b'pastA',0,1)
        digest=hashlib.sha256(previous.read_bytes()).hexdigest()
        next_result=run('second',b'pastA',b'pastAB',1,2,previous)
        run('forged_history',b'castA',b'castAB',1,2,previous,False)
        run('forged_time',b'pastA',b'pastAB',0,2,previous,False)
        run('shortened_history',b'past',b'pastB',1,2,previous,False)
        # Kernel-level rejection also leaves an executable old state for retry.
        rejected=run('rejected_new_prefix',b'pastAB',b'pastXX',2,3,next_result)
        run('retry_from_rejected',b'pastAB',b'pastABC',2,3,rejected)
        # Supply next-state bytes/time that satisfy the corrupted file's old
        # binding checks. Rejection must come from full prior-result validation.
        corruptions=(
            ('corrupt_prior_status',0,1,b'pastA',0),
            ('corrupt_prior_committed_history',config.committed_offset,ord('p')^ord('c'),b'castA',1),
            ('corrupt_prior_normalized_term',config.normalized_offset,1,b'pastA',1),
        )
        for name,word,xor,before,old_time in corruptions:
            corrupted=folder/(name+'_prior.tor')
            data=bytearray(previous.read_bytes());data[64+4*word]^=xor
            corrupted.write_bytes(data)
            run(name,before,before+b'B',old_time,2,corrupted,False,
                'resume result inconsistency at case 0, word '+str(word))
            if corrupted.read_bytes()!=data:raise AssertionError('corrupted prior input was modified')
        for option in ('--output','--json'):
            command=[str(args.exe.resolve()),'--input',str(folder/'second.ton'),'--resume',str(previous),option,str(previous)]
            result=subprocess.run(command,capture_output=True,text=True)
            if result.returncode==0:raise AssertionError('output could overwrite retained prior result')
            if hashlib.sha256(previous.read_bytes()).hexdigest()!=digest:raise AssertionError('retained prior result was overwritten')
            runs.append({'name':'protect_prior_'+option[2:],'verification':{'rejected_before_overwrite':True}})
        if hashlib.sha256(previous.read_bytes()).hexdigest()!=digest:raise AssertionError('prior result changed')
    report={'status':'PASS','executable':str(args.exe.resolve()),'cases':runs,'prior_results_unchanged':True}
    if args.out:args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
