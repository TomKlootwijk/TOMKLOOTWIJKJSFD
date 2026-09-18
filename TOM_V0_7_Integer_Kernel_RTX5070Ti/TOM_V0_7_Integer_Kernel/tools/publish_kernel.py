#!/usr/bin/env python3
"""Publish an evaluator microprogram reconstructed from its own quoted packed output.

This is explicit between-run publication. Neither CUDA instructions nor immutable
same-launch input definitions are rewritten by the device while being read.
"""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from tom.compiler import Image,load_state,lane_value
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--copy-program',type=Path,required=True);p.add_argument('--snapshot',type=Path,required=True)
p.add_argument('--target-program',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--lane',type=int,default=0)
a=p.parse_args();copy=Image.load(a.copy_program);target=Image.load(a.target_program);slots,words,epoch,state=load_state(a.snapshot)
if slots!=copy.header[8] or not 0<=a.lane<words*32:raise ValueError('snapshot/copy program mismatch')
code=[]
for i in range(28):
    group=copy.metadata['groups'].get(f'word{i}')
    if group is None or len(group['bits'])!=32:raise ValueError('missing self-quoted evaluator word')
    indices=[copy.metadata['state_slots'][x] for x in group['bits']]
    code.append(lane_value(state,words,indices,a.lane))
for i in range(7):
    d,x,y,c=code[4*i:4*i+4]
    if d!=11+i or max(x,y,c)>=d:raise ValueError('quoted code violates declared local precedence')
base=target.record(target.header[10])[1];target.words[base:base+28]=code
metadata={'from_snapshot_sha256':hashlib.sha256(a.snapshot.read_bytes()).hexdigest(),'observed_epoch':epoch,'lane':a.lane,
          'reconstructed_instruction_words':28,'rewrites_native_GPU_instructions':False}
target.metadata['publication']=metadata;target.save(a.out);print(json.dumps(metadata,indent=2))
