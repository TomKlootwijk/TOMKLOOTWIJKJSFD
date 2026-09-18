#!/usr/bin/env python3
"""Real GPU validation driver. A PASS is emitted only for runs actually executed."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exe',type=Path,required=True);p.add_argument('--out',type=Path,default=ROOT/'verification/laptop');p.add_argument('--quick',action='store_true');a=p.parse_args();a.exe=a.exe.resolve();a.out.mkdir(parents=True,exist_ok=True)
info=json.loads(subprocess.check_output([str(a.exe),'--info'],text=True));reports={}
for backend in ('texture','global','shared'):
    dest=a.out/f'{backend}.json';cmd=[sys.executable,str(ROOT/'tests/validate.py'),'--exe',str(a.exe),'--backend',backend,'--out',str(dest)]
    if a.quick:cmd.append('--quick')
    subprocess.run(cmd,check=True);report=json.loads(dest.read_text())
    if report['status']!='PASS' or not report['gpu_executed']:raise RuntimeError('expected an executed GPU test')
    reports[backend]={'status':report['status'],'counts':report['counts'],'skipped':report['skipped']}
summary={'status':'PASS','gpu_executed':True,'hardware':info,'backends':reports}
(a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
