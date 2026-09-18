#!/usr/bin/env python3
"""Read actual packed result fields; epoch is interpreter order, not physical time."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from tom.compiler import Image,load_state,lane_value
p=argparse.ArgumentParser(description=__doc__);p.add_argument('program',type=Path);p.add_argument('state',type=Path);p.add_argument('--lanes',default='0,1,2,3');p.add_argument('--out',type=Path)
a=p.parse_args();im=Image.load(a.program);slots,words,epoch,data=load_state(a.state)
if slots!=im.header[8]:raise ValueError('program/state mismatch')
result=[]
for lane in map(int,a.lanes.split(',')):
    if not 0<=lane<words*32:raise ValueError('lane out of range')
    values={}
    for name in im.metadata['outputs']:
        group=im.metadata['groups'].get(name,{'bits':[name],'signed':False})
        indices=[im.metadata['state_slots'][n] for n in group['bits']]
        values[name]=lane_value(data,words,indices,lane,group.get('signed',False))
    result.append({'case_lane':lane,'outputs':values})
text=json.dumps({'epoch':epoch,'interpretation':'finite implementation readings, not intrinsic TOM coordinates','cases':result},indent=2)
print(text)
if a.out:a.out.write_text(text+'\n')
