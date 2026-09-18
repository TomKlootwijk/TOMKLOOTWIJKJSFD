#!/usr/bin/env python3
"""Create source-related validation and self-reference images, not invented TOM dynamics."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from tom.builder import Builder
from tom.compiler import compile_definition

def save(name,builder):
    (ROOT/'examples'/f'{name}.json').write_text(json.dumps(builder.spec,indent=2)+'\n')
    builder.compile().save(ROOT/'examples'/f'{name}.tsdf')

# Exact unsigned observer chronology / causal availability / no erasure.
b=Builder('TOM finite causal and inverse-Occam conformance certificate')
prev=b.bits('previous_time',16);now=b.bits('current_time',16)
elapsed=b.bits('elapsed',16);dep=b.bits('latest_dependency',16)
old=b.bits('retained_before',8);new=b.bits('retained_after',8)
a=b.bits('direct',8,signed=True);e=b.bits('echo',8,signed=True)
left=b.bits('left_definition_witness',8);right=b.bits('right_definition_witness',8)
forward=b.less(prev,now)
time_diff=b.sub(now,prev)
elapsed_ok=b.gate('AND',forward,b.eq(time_diff,elapsed))
causal=b.inverse(b.less(now,dep))
retained=b.reduce('AND',[b.gate('OR',b.inverse(x),y) for x,y in zip(old,new)],'ONE')
zeroa=b.inverse(b.reduce('OR',a,'ZERO'));zeroe=b.inverse(b.reduce('OR',e,'ZERO'))
neutral=b.gate('OR',b.gate('XOR',a[-1],e[-1]),b.gate('OR',zeroa,zeroe))
structural_distinct=b.inverse(b.eq(left,right))
for name,val in [('forward',forward),('elapsed_preserved',elapsed_ok),('future_independent',causal),('retention_preserved',retained),('Arch_neutral',neutral),('distinct_witnesses',structural_distinct)]:b.output(name,val)
b.output('temporal_retention_conformant',b.reduce('AND',[forward,elapsed_ok,causal,retained],'ONE'))
b.output('all_reported_checks',b.reduce('AND',[forward,elapsed_ok,causal,retained,neutral],'ONE'))
save('tom_conformance',b)

# Source Arch formula, exact on every signed 8-bit pair, width extended before abs.
b=Builder('Exact integer observer audit of source Arch U; operands retained')
a=b.bits('a',8,signed=True,counter_start=0);c=b.bits('b',8,signed=True,counter_start=8)
a=a+[a[-1]]*2;c=c+[c[-1]]*2
abs_a=b.mux_bits(a,b.negate(a),a[-1]);abs_c=b.mux_bits(c,b.negate(c),c[-1])
diff=b.sub(a,c);abs_diff=b.mux_bits(diff,b.negate(diff),diff[-1])
sum_,_=b.add(abs_a,abs_c)
residual=b.sub(sum_,abs_diff)
b.output_group('Arch',residual)
save('arch_exact_int8',b)

# Every 8-bit table and every 3-bit input: the kernel executes its own declared law.
b=Builder('All 256 ternary operator fields x all 8 inputs')
a=b.bit('a',{'counter_bit':0});c=b.bit('b',{'counter_bit':1});d=b.bit('c',{'counter_bit':2})
rows=b.bits('truth',8,counter_start=3)
b.spec['rules']['test_rule']={'rows':rows}
b.output('result',b.gate('test_rule',a,c,d))
# Read exact evaluator coefficients and a self-address bit as part of the program.
for i in range(8):
    q=f'quote_kernel_coeff.{i}';b.spec['quotes'][q]={'object':'KERNEL','bit':96+i};b.output(f'kernel_coeff.{i}',q)
save('kernel_reflection',b)

# Actual rule behavior alternates identity / NOT through future T-bound coefficients.
b=Builder('Self-referential operator: quote definitions, publish future truth rows')
x=b.bit('input',{'counter_bit':0});rows=[]
for i in range(8):rows.append(b.bit(f'self_row.{i}',(0xAA>>i)&1))
b.spec['groups']['current_rule']={'bits':rows,'signed':False}
b.spec['rules']['SELF']={'rows':rows}
b.output('answer',b.gate('SELF',x))
for name in rows:b.spec['next'][name]=b.inverse(name)
for i in range(8):
    q=f'own_id_bit.{i}';b.spec['quotes'][q]={'object':'SELF','bit':448+i};b.output(f'read_own_id.{i}',q)
b.spec['groups']['read_own_id']={'bits':[f'read_own_id.{i}' for i in range(8)],'signed':False}
q='read_kernel_bit';b.spec['quotes'][q]={'object':'KERNEL','bit':97};b.output('kernel_selector_bit1',q)
b.spec['outputs']=['input','answer','current_rule','read_own_id','kernel_selector_bit1']
save('self_reference',b)

# Reconstruct the complete field-described kernel body (28 words) via quotation.
b=Builder('Exact self-quotation of the entire evaluator microprogram')
for w in range(28):
    values=[]
    for bit in range(32):
        q=f'kernel.{w}.{bit}';b.spec['quotes'][q]={'kernel_bit':w*32+bit};values.append(q)
    b.output_group(f'word{w}',values)
save('kernel_selfcopy',b)
print('Wrote five TOM validation images and their editable definitions.')
