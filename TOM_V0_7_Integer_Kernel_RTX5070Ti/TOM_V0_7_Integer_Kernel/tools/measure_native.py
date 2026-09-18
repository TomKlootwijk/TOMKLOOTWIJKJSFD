#!/usr/bin/env python3
"""Measure the native-term executor only with every-word independent expectations."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe',type=Path,default=ROOT/'build-cuda128/Release/tom_native_cuda.exe')
    p.add_argument('--templates',type=Path,default=ROOT/'verification/native_20260918/native_templates.ton')
    p.add_argument('--expected',type=Path,default=ROOT/'verification/native_20260918/native_templates_expected.tor')
    count=p.add_mutually_exclusive_group(required=True);count.add_argument('--cases',type=int);count.add_argument('--percent',type=int)
    p.add_argument('--repeat',type=int,default=1);p.add_argument('--warmup',type=int,default=1)
    p.add_argument('--block',type=int,default=128);p.add_argument('--shard-cases',type=int,default=16384)
    p.add_argument('--samples',type=int,default=3);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if min(a.samples,a.repeat)<1:p.error('positive samples and repetitions required')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    command=[str(a.exe.resolve()),'--input',str(a.templates.resolve()),'--expected-templates',str(a.expected.resolve()),
        '--repeat',str(a.repeat),'--warmup',str(a.warmup),'--block',str(a.block),'--shard-cases',str(a.shard_cases),'--verify']
    command+=['--generate-cases',str(a.cases)] if a.cases is not None else ['--vram-percent',str(a.percent)]
    report={'status':'RUNNING','command':command,'binary_sha256':sha(a.exe),'templates_sha256':sha(a.templates),
        'independent_expectations_sha256':sha(a.expected),
        'scope':'Full native source terms, declared rewrites and exact finite histories; each result word compared with independently computed template expectations plus exact candidate identity.',
        'source_pdf_sha256':'97582a16bd54d690b27105f9b09dc48d2b5716bbae2fff2a5e74190278640fbc','runs':[]}
    for sample in range(a.samples):
        telemetry_file=a.out.with_name(a.out.stem+f'_telemetry_{sample}.csv')
        with telemetry_file.open('w') as stream:
            telemetry=subprocess.Popen(['nvidia-smi','--id=0',
                '--query-gpu=timestamp,memory.used,memory.free,utilization.gpu,utilization.memory,temperature.gpu,power.draw',
                '--format=csv,noheader,nounits','--loop-ms=200'],stdout=stream,stderr=subprocess.STDOUT)
            started=time.perf_counter_ns()
            try:done=subprocess.run(command,capture_output=True,text=True,timeout=180)
            finally:
                wall=time.perf_counter_ns()-started;telemetry.terminate();telemetry.wait(timeout=10)
        if done.returncode:
            report.update(status='FAIL',error={'returncode':done.returncode,'stderr':done.stderr,'stdout':done.stdout})
            a.out.write_text(json.dumps(report,indent=2)+'\n');raise RuntimeError(done.stderr)
        result=json.loads(done.stdout)
        # The runner exits nonzero if independent full-result verification fails;
        # require explicit measured coverage as well as successful process exit.
        verified=result.get('full_word_verification',{})
        if not verified.get('enabled') or not verified.get('passed') or verified.get('mismatched_words')!=0 or verified.get('checked_words')!=result['cases']*result['result_words']:
            raise AssertionError('every native result word must match independent expectations')
        telemetry_rows=[]
        for row in csv.reader(telemetry_file.read_text().splitlines()):
            if len(row)!=7:continue
            try:telemetry_rows.append([row[0]]+[float(value.strip()) for value in row[1:]])
            except ValueError:pass
        peaks={name:max(row[i] for row in telemetry_rows) for i,name in enumerate(
            ['timestamp','memory_used_MiB','memory_free_MiB','gpu_busy_percent','memory_busy_percent','temperature_C','power_W'])
            if i and telemetry_rows}
        report['runs'].append({'runner':result,'process_wall_ns':wall,'telemetry_peaks':peaks,
            'telemetry_scope':'all process phases; peaks need not coincide','telemetry_file':str(telemetry_file)})
        a.out.write_text(json.dumps(report,indent=2)+'\n')
    times=[r['runner']['elapsed_compute_host_ns'] for r in report['runs']]
    report.update(status='PASS',median_compute_ns=int(statistics.median(times)),
        median_process_ns=int(statistics.median(r['process_wall_ns'] for r in report['runs'])))
    a.out.write_text(json.dumps(report,indent=2)+'\n')
    last=report['runs'][-1]['runner'];duration=report['median_compute_ns']/a.repeat
    print(json.dumps({'status':'PASS','out':str(a.out),'cases':last['cases'],'working_GiB':last['working_bytes']/(1<<30),
        'median_ms_per_pass':duration/1e6,'native_cases_per_second':last['cases']*1e9/duration,
        'median_process_s':report['median_process_ns']/1e9,'cuda_free_after_bytes':last['free_after_bytes']}))


if __name__=='__main__':main()
