#!/usr/bin/env python3
"""Measure distinct source-pinned certificate candidates and verify all mask totals.

GPU utilization telemetry covers process lifetime. It is not an ALU-efficiency
metric; obtain compute/DRAM counters separately with Nsight Compute.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from tom.compiler import Image
from make_bounded_space import prefix_counts,decode_candidate,oracle


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe',type=Path,required=True)
    p.add_argument('--program',type=Path,required=True)
    extent=p.add_mutually_exclusive_group(required=True)
    extent.add_argument('--lanes',type=int)
    extent.add_argument('--percent',type=int)
    p.add_argument('--backend',choices=['texture','global','shared'],default='shared')
    p.add_argument('--evaluator',choices=['field','lowered'],default='lowered')
    p.add_argument('--block',type=int,default=256)
    p.add_argument('--blocks-per-sm',type=int,default=8)
    p.add_argument('--shard-words',type=int,default=262144)
    p.add_argument('--ticks',type=int,default=8)
    p.add_argument('--warmup',type=int,default=2)
    p.add_argument('--samples',type=int,default=3)
    p.add_argument('--mask-out',type=Path,help='save and exhaustively verify the all-shard temporal/retention admission bitmap (requires samples=1)')
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.samples<1 or args.ticks<1:p.error('positive samples and measured ticks required')
    if args.mask_out and args.samples!=1:p.error('bitmap export requires samples=1')
    exe=args.exe.resolve();program=args.program.resolve()
    image=Image.load(program);profile=image.metadata['bounded_realization']
    if args.lanes and (args.lanes%32 or args.lanes<32 or args.lanes>profile['unique_candidate_count']):
        p.error('lanes must be a supported multiple of32 within the distinct counter domain')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    base=[str(exe),'--program',str(program),'--backend',args.backend,'--evaluator',args.evaluator,
          '--block',str(args.block),'--blocks-per-sm',str(args.blocks_per_sm),
          '--shard-words',str(args.shard_words),'--ticks',str(args.ticks),'--warmup',str(args.warmup),'--verify']
    base+=['--lanes',str(args.lanes)] if args.lanes else ['--vram-percent',str(args.percent)]
    masks=list(profile['analytic_full_domain_counts'])
    masks.remove('total_candidates')
    for name in masks:base+=['--count-state',str(image.metadata['state_slots'][name])]
    if args.mask_out:
        args.mask_out.parent.mkdir(parents=True,exist_ok=True)
        base+=['--state-mask-out',str(args.mask_out.resolve()),'--state-mask-slot',str(image.metadata['state_slots']['temporal_retention_admissible'])]
    report={'status':'RUNNING','program':str(program),'program_sha256':hashlib.sha256(program.read_bytes()).hexdigest(),
            'executable':str(exe),'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
            'source':{k:v for k,v in profile['source'].items() if k!='editorial_contract'},
            'profile':{k:v for k,v in profile.items() if k!='source'},'command':base,'runs':[],
            'scope':'Exact bounded certificate predicates and distinct counter candidates. No assigned native jitter/pinion dynamics. Samples check complete states at every shard edge; integer population counts check each selected plane over every lane against an independent exact prefix oracle.'}
    columns=['timestamp','memory.used','memory.free','utilization.gpu','utilization.memory',
             'clocks.sm','clocks.mem','temperature.gpu','power.draw']
    for sample in range(args.samples):
        telemetry_path=args.out.with_name(args.out.stem+f'_telemetry_{sample}.csv')
        telemetry=None
        with telemetry_path.open('w',encoding='utf-8') as stream:
            if shutil.which('nvidia-smi'):
                telemetry=subprocess.Popen(['nvidia-smi','--id=0','--query-gpu='+','.join(columns),
                    '--format=csv,noheader,nounits','--loop-ms=200'],stdout=stream,stderr=subprocess.STDOUT)
            start=time.perf_counter_ns()
            try:
                done=subprocess.run(base,capture_output=True,text=True,timeout=180)
            finally:
                wall_ns=time.perf_counter_ns()-start
                if telemetry:
                    telemetry.terminate()
                    telemetry.wait(timeout=10)
        if done.returncode:
            report['status']='FAIL';report['error']={'returncode':done.returncode,'stdout':done.stdout,'stderr':done.stderr}
            args.out.write_text(json.dumps(report,indent=2)+'\n')
            raise RuntimeError(done.stderr.strip())
        run=json.loads(done.stdout)
        if run['lanes']>profile['unique_candidate_count']:
            raise RuntimeError('capacity run exceeded unique candidate domain')
        expected=prefix_counts(profile,run['lanes'])
        actual_by_slot={item['slot']:item['ones'] for item in run['state_counts']}
        comparison={name:{'expected':expected[name],'actual':actual_by_slot[image.metadata['state_slots'][name]]} for name in masks}
        if any(item['expected']!=item['actual'] for item in comparison.values()):
            raise AssertionError(comparison)
        if not run['sample_verified'] or run['verification']['shards_verified']!=run['shards']:
            raise AssertionError('every shard must be verified')
        bitmap_validation=None
        if args.mask_out:
            # The admission predicate uses only the temporal and retention input
            # groups. Form its complete independent low-bit truth table, then
            # compare EVERY exported bit, including all scalar/witness repetitions.
            period_bits=4*profile['widths']['time_bits']+2*profile['widths']['retention_bits']
            period=1<<period_bits
            expected_pattern=bytearray((period+7)//8)
            for lane in range(period):
                if oracle(decode_candidate(lane,profile))['temporal_retention_admissible']:
                    expected_pattern[lane>>3]|=1<<(lane&7)
            expected_pattern=bytes(expected_pattern)
            digest=hashlib.sha256();offset=0
            with args.mask_out.open('rb') as bitmap:
                header=bitmap.read(32);digest.update(header)
                magic,slot,version,lanes,epoch=struct.unpack('<8sIIQQ',header)
                if (magic,slot,version,lanes,epoch)!=(b'TOM7MSK\0',image.metadata['state_slots']['temporal_retention_admissible'],1,run['lanes'],run['epoch']):
                    raise AssertionError('bitmap header differs from executed result')
                while chunk:=bitmap.read(1<<20):
                    digest.update(chunk)
                    pattern_start=offset%len(expected_pattern)
                    repeated=expected_pattern*((pattern_start+len(chunk)+len(expected_pattern)-1)//len(expected_pattern))
                    if chunk!=repeated[pattern_start:pattern_start+len(chunk)]:
                        raise AssertionError('exported admission bitmap differs from integer oracle at byte '+str(offset))
                    offset+=len(chunk)
                if offset*8!=run['lanes']:raise AssertionError('bitmap size differs from complete lane domain')
            bitmap_validation={'status':'PASS','scope':'every admission bit independently verified','lanes':run['lanes'],
                'path':str(args.mask_out.resolve()),'sha256':digest.hexdigest(),'file_bytes':offset+32,
                'independent_predicate_period_lanes':period}
        telemetry_rows=[]
        for row in csv.reader(telemetry_path.read_text(encoding='utf-8').splitlines()):
            if len(row)!=len(columns):continue
            item={'timestamp':row[0].strip()}
            for key,value in zip(columns[1:],row[1:]):
                try:item[key]=float(value.strip())
                except ValueError:item[key]=None
            telemetry_rows.append(item)
        measured={'runner':run,'process_wall_ns':wall_ns,'exact_mask_totals':comparison,
                  'complete_admission_bitmap_verification':bitmap_validation,
                  'complete_declared_domain':run['lanes']==profile['unique_candidate_count'],
                  'distinct_candidates':run['lanes'],'telemetry_file':str(telemetry_path),
                  'telemetry_scope':'all process phases including initialization, computation and verification',
                  'telemetry_samples':len(telemetry_rows),'telemetry_peak':{}}
        for key in columns[1:]:
            values=[row[key] for row in telemetry_rows if row[key] is not None]
            if values:measured['telemetry_peak'][key]=max(values)
        report['runs'].append(measured)
        args.out.write_text(json.dumps(report,indent=2)+'\n')
    times=sorted(run['runner']['elapsed_host_ns'] for run in report['runs'])
    report.update(status='PASS',min_compute_ns=times[0],median_compute_ns=(times[(len(times)-1)//2]+times[len(times)//2])//2,max_compute_ns=times[-1])
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    last=report['runs'][-1]['runner']
    print(json.dumps({'status':'PASS','out':str(args.out),'distinct_candidates':last['lanes'],
        'working_GiB':last['working_bytes']/(1<<30),'median_compute_ms':report['median_compute_ns']/1e6,
        'ticks':last['ticks'],'shards':last['shards'],'every_shard_sample_verified':True,
        'all_mask_totals_exact':True,'complete_domain':report['runs'][-1]['complete_declared_domain']}))


if __name__=='__main__':main()
