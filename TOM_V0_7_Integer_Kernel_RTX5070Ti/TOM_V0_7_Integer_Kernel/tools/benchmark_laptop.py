#!/usr/bin/env python3
"""Compare GPU memory paths and verified kernel lowering with fixed batch sizes.

This tool does not change clocks, voltages, firmware, drivers or power policies.
Times are integer nanoseconds, not inferred from peak hardware specifications.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from tom.compiler import Image

def call(exe,args):return json.loads(subprocess.run([str(exe),*args],capture_output=True,text=True,check=True).stdout)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exe',type=Path,required=True);p.add_argument('--program',type=Path,default=ROOT/'examples/tom_conformance.tsdf')
    p.add_argument('--lanes',type=int,default=262144);p.add_argument('--ticks',type=int,default=8);p.add_argument('--samples',type=int,default=5);p.add_argument('--percent',default='')
    p.add_argument('--blocks',default='128',help='comma-separated block sizes, e.g. 64,128,256')
    p.add_argument('--warmup',type=int,default=2,help='untimed compute ticks inside each measured process, followed by initial-state restoration; 0 measures cold launches')
    p.add_argument('--out',type=Path,default=ROOT/'verification/laptop_benchmark.json');a=p.parse_args();a.exe=a.exe.resolve();a.program=a.program.resolve()
    if a.samples<1 or a.ticks<1 or a.lanes<32 or a.lanes%32:p.error('positive counts; lanes multiple of 32')
    if not 0<=a.warmup<=0xffffffff:p.error('warmup must be 0..4294967295')
    try:blocks=list(dict.fromkeys(int(value) for value in a.blocks.split(',')))
    except ValueError:p.error('blocks must be a comma-separated list of 64,128,256')
    if not blocks or any(block not in (64,128,256) for block in blocks):p.error('blocks must be 64,128,256')
    im=Image.load(a.program);hardware=call(a.exe,['--info']);batch_sizes=[a.lanes]
    for percent in filter(None,a.percent.split(',')):
        value=int(percent)
        if not 1<=value<=100:p.error('percent must be 1..100')
        free=call(a.exe,['--info'])['free_bytes'];budget=(free//100)*value
        words=(budget-len(im.words)*4)//(4*(2*im.header[8]+im.header[9]))
        if words<1:raise RuntimeError('selected memory budget fits no lane word')
        batch_sizes.append(words*32)
    report={'hardware':hardware,'program':a.program.name,'gpu_executed':True,'cases':[],
      'program_sha256':hashlib.sha256(a.program.read_bytes()).hexdigest(),'executable_sha256':hashlib.sha256(a.exe.read_bytes()).hexdigest(),
      'warmup_ticks':a.warmup,'block_threads':blocks,'samples_per_choice':a.samples,
      'scope':'identical definition/data for all modes; each process runs optional warmup then restores initial state before timing; timer includes launches and completion, not setup or warmup; no trace export; sample verification not exhaustive high-batch validation'}
    backends=['texture','global']+(['shared'] if len(im.words)*4<=hardware['shared_optin_bytes'] else [])
    for lanes in batch_sizes:
        cases={(backend,evaluator,block):[] for backend in backends for evaluator in ('field','lowered') for block in blocks}
        common=['--program',str(a.program),'--lanes',str(lanes),'--ticks',str(a.ticks),'--warmup',str(a.warmup),'--verify']
        first_digest=None
        # Every measured process warms its own loaded compute kernel and context.
        # Rotate the complete option set to spread order-dependent variation.
        options=list(cases)
        for sample in range(a.samples):
            order=options[sample%len(options):]+options[:sample%len(options)]
            for backend,evaluator,block in order:
                result=call(a.exe,[*common,'--backend',backend,'--evaluator',evaluator,'--block',str(block)])
                if not result['sample_verified']:raise RuntimeError('GPU output not verified')
                if result.get('warmup_ticks')!=a.warmup:raise RuntimeError('executable did not report the requested in-process warmup')
                if first_digest is None:first_digest=result['sample_digest']
                if result['sample_digest']!=first_digest:raise RuntimeError('different outputs across execution modes')
                cases[(backend,evaluator,block)].append(result)
        item={'lanes':lanes,'choices':[]}
        for (backend,evaluator,block),samples in cases.items():
            times=sorted(x['elapsed_host_ns'] for x in samples)
            median=(times[(len(times)-1)//2]+times[len(times)//2])//2
            item['choices'].append({'backend':backend,'evaluator':evaluator,'block_threads':block,'warmup_ticks':a.warmup,
              'min_ns':times[0],'median_ns':median,'max_ns':times[-1],
              'transitions_per_second_integer_floor':lanes*a.ticks*1_000_000_000//max(1,median),'samples':samples})
        report['cases'].append(item);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'PASS','result':str(a.out),'executed_batches':len(report['cases'])}))
if __name__=='__main__':main()
