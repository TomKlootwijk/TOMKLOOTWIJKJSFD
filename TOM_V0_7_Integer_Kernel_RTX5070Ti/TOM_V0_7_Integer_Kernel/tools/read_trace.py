#!/usr/bin/env python3
"""Read a lane's complete saved history without loading the whole trace into RAM."""
import argparse,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from tom.compiler import Image
p=argparse.ArgumentParser(description=__doc__);p.add_argument('program',type=Path);p.add_argument('trace',type=Path);p.add_argument('--lane',type=int,default=0);p.add_argument('--out',type=Path)
a=p.parse_args();im=Image.load(a.program);observations=[]
with a.trace.open('rb') as f:
    if f.read(8)!=b'TOM7TRC\0':raise ValueError('invalid trace magic')
    slots,words,start,frames=struct.unpack('<2I2Q',f.read(24))
    if slots!=im.header[8] or not 0<=a.lane<words*32:raise ValueError('trace extent differs from program/lane')
    if a.trace.stat().st_size!=32+4*slots*words*frames:raise ValueError('trace is truncated or has extra bytes')
    for frame in range(frames):
        values={}
        for name in im.metadata['outputs']:
            group=im.metadata['groups'].get(name,{'bits':[name],'signed':False});value=0
            for bit,field in enumerate(group['bits']):
                slot=im.metadata['state_slots'][field]
                f.seek(32+4*((frame*slots+slot)*words+a.lane//32));word,=struct.unpack('<I',f.read(4));value|=((word>>(a.lane%32))&1)<<bit
            if group.get('signed',False) and value&(1<<(len(group['bits'])-1)):value-=1<<len(group['bits'])
            values[name]=value
        observations.append({'epoch':start+frame,'values':values})
text=json.dumps({'lane':a.lane,'full_recorded_epochs':frames,'observations':observations},indent=2);print(text)
if a.out:a.out.write_text(text+'\n')
