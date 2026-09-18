#!/usr/bin/env python3
"""Pack named integer/Boolean observer cases into one-bit signal planes (no floats)."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from tom.compiler import Image,seed_words,save_state,FULL

def pack(image,cases):
    if not cases:raise ValueError('at least one case required')
    words=(len(cases)+31)//32;state=seed_words(image,words)
    for lane,case in enumerate(cases):
        for name,value in case.items():
            if type(value) not in (int,bool):raise ValueError('integer/Boolean input required; no floating-point values')
            groups=image.metadata.get('groups',{})
            if name in groups:
                g=groups[name];bits=g['bits'];signed=g.get('signed',False);width=len(bits)
                lo=-(1<<(width-1)) if signed else 0;hi=(1<<(width-1))-1 if signed else (1<<width)-1
                if not lo<=value<=hi:raise ValueError(f'{name} outside declared bit width')
            else:
                if name not in image.metadata['state_slots'] or value not in (0,1):raise ValueError('unknown field or non-Boolean value: '+name)
                bits=[name]
            for b,field in enumerate(bits):
                index=image.metadata['state_slots'][field]*words+lane//32;mask=1<<(lane%32)
                if (value>>b)&1:state[index]|=mask
                else:state[index]&=FULL^mask
    return state,words

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('program',type=Path);p.add_argument('cases',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();im=Image.load(a.program);cases=json.loads(a.cases.read_text());state,words=pack(im,cases)
    save_state(a.output,state,im.header[8],words)
    print(json.dumps({'cases':len(cases),'allocated_lanes':32*words,'padding_lanes_are_not_test_cases':32*words-len(cases),'bytes':a.output.stat().st_size}))
if __name__=='__main__':main()
