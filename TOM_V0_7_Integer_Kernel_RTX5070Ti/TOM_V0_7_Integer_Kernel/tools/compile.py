#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from tom.compiler import compile_definition
p=argparse.ArgumentParser(description='Compile a declared finite TOM validation program to a packed SDF-definition image')
p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--no-recycle',action='store_true')
a=p.parse_args();image=compile_definition(json.loads(a.source.read_text()),not a.no_recycle);image.save(a.output)
print(json.dumps({k:image.metadata[k] for k in ('name','objects','scheduled_values','scratch_slots','unrecycled_slots')},indent=2))
