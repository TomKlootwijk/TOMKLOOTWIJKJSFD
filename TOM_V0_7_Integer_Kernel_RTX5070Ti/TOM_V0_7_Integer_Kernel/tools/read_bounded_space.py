#!/usr/bin/env python3
"""Inspect an actual saved GPU answer and recover its complete bounded inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from tom.compiler import Image
from make_bounded_space import decode_candidate,oracle


def file_hash(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1<<20):value.update(chunk)
    return value.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,default=ROOT/'verification/formalization_20260918/full_domain_admission_mask.json')
    p.add_argument('--case',type=int,nargs='+',default=[0,72,1096,67108936])
    p.add_argument('--out',type=Path)
    args=p.parse_args();report=json.loads(args.report.read_text())
    if report['status']!='PASS':raise ValueError('measurement report did not pass')
    saved=report['runs'][-1]['complete_admission_bitmap_verification']
    if not saved or saved['status']!='PASS':raise ValueError('no fully verified saved bitmap')
    path=Path(saved['path']);program=Path(report['program'])
    if file_hash(path)!=saved['sha256'] or file_hash(program)!=report['program_sha256']:
        raise ValueError('saved bitmap or program changed since verification')
    image=Image.load(program);profile=image.metadata['bounded_realization'];rows=[]
    with path.open('rb') as bitmap:
        magic,slot,version,lanes,epoch=struct.unpack('<8sIIQQ',bitmap.read(32))
        if magic!=b'TOM7MSK\0' or version!=1 or slot!=image.metadata['state_slots']['temporal_retention_admissible']:
            raise ValueError('bitmap format or state plane differs')
        for lane in args.case:
            if not 0<=lane<lanes:raise ValueError('case outside saved domain: '+str(lane))
            bitmap.seek(32+(lane>>3));raw=bitmap.read(1)
            if len(raw)!=1:raise ValueError('truncated bitmap')
            admitted=(raw[0]>>(lane&7))&1
            case=decode_candidate(lane,profile);expected=oracle(case)
            if admitted!=expected['temporal_retention_admissible']:raise AssertionError('saved answer differs from integer oracle')
            rows.append({'case_index':lane,'inputs':case,'saved_gpu_admissible':bool(admitted),'independent_checks':expected})
    result={'status':'PASS','epoch':epoch,'saved_candidates':lanes,'source_pdf_sha256':profile['source']['pdf_sha256'],
            'scope':'Exact saved bounded certificate answers; candidate indices and witnesses are implementation data, not native TOM constituents.',
            'cases':rows}
    output=json.dumps(result,indent=2)+'\n'
    if args.out:args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(output)
    print(output)


if __name__=='__main__':main()
