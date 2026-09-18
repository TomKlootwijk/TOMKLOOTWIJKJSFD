#!/usr/bin/env python3
"""Change the executable kernel's stored selector definition, without rebuilding CUDA."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from tom.compiler import Image
p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--selector-table',type=lambda s:int(s,0),required=True)
a=p.parse_args()
if not 0<=a.selector_table<256:p.error('selector table is an 8-bit field')
im=Image.load(a.input);offset=im.header[10]*16+3;previous=im.words[offset];im.words[offset]=a.selector_table
im.metadata['kernel_edit']={'previous_selector_table':previous,'current_selector_table':a.selector_table,
 'semantics':'changes the evaluator, not only an application gate; lowered backend must reject noncanonical kernel'}
im.save(a.output);print(json.dumps(im.metadata['kernel_edit'],indent=2))
