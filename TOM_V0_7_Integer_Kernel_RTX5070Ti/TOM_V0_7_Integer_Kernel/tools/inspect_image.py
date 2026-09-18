#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from tom.compiler import Image
p=argparse.ArgumentParser(description='Inspect self-referential kernel/program definitions in the same packed image')
p.add_argument('program',type=Path);p.add_argument('--field',default='KERNEL');a=p.parse_args();im=Image.load(a.program)
ident=im.metadata['names'][a.field];record=im.record(ident)
report={'field':a.field,'id':ident,'self_reference':record[14],'record_uint32':record,'A_equals_T':im.metadata['names']['A']==im.metadata['names']['T'],'native_SDF_convention':'TOM declaration encoding; no metric geometry imposed'}
if a.field=='KERNEL':
    base=record[1];report['executable_microprogram']=[im.words[i:i+4] for i in range(base,base+record[2]*4,4)]
print(json.dumps(report,indent=2))
