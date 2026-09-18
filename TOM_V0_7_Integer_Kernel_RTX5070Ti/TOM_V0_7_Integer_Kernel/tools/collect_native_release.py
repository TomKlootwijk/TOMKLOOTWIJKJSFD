#!/usr/bin/env python3
"""Collect verified release evidence; does not run or invent GPU measurements."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'verification/native_20260918'


def sha(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):value.update(block)
    return value.hexdigest()


def main():
    binary=ROOT/'build-cuda128/Release/tom_native_cuda.exe'
    digest=sha(binary)
    summary={'status':'PASS','binary_sha256':digest,'workloads':{}}
    for name in ['release_capacity','release_mixed_capacity']:
        path=EVIDENCE/(name+'.json');data=json.loads(path.read_text())
        assert data['status']=='PASS' and data['binary_sha256']==digest
        runner=data['runs'][0]['runner']
        for run in data['runs']:
            check=run['runner']['full_word_verification']
            assert check['enabled'] and check['passed'] and check['mismatched_words']==0
            assert check['checked_words']==run['runner']['cases']*run['runner']['result_words']
        ns=data['median_compute_ns']/runner['repeat']
        metrics={key:runner[key] for key in ['cases','working_bytes','case_words','result_words',
            'accepted_cases','not_committed_cases','source_tom_cases','inverse_occam_rewrites',
            'alias_rewrites','resolved_requests','unresolved_requests']}
        metrics.update(median_compute_ms_per_pass=ns/1e6,cases_per_second=runner['cases']*1e9/ns,
            median_process_seconds=data['median_process_ns']/1e9,
            working_GiB=runner['working_bytes']/(1<<30),
            cuda_free_after_bytes=[run['runner']['free_after_bytes'] for run in data['runs']],
            final_output_words_compared_per_run=runner['full_word_verification']['checked_words'],
            final_output_mismatched_words=[run['runner']['full_word_verification']['mismatched_words'] for run in data['runs']],
            samples=len(data['runs']),timed_passes_per_sample=runner['repeat'])
        summary['workloads'][name]=metrics
    conformance=json.loads((EVIDENCE/'release_conformance.json').read_text())
    assert conformance['status']=='PASS'
    assert all(value['all_words_equal'] for value in conformance.values() if isinstance(value,dict) and 'all_words_equal' in value)
    resume=json.loads((EVIDENCE/'release_resume_gpu.json').read_text());assert resume['status']=='PASS'
    demo=json.loads((EVIDENCE/'demo/gpu/demo_report.json').read_text())
    assert demo['all_steps_verified'] and demo['executable_sha256']==digest
    assert all(step['runner']['gpu_executed'] for step in demo['steps'])
    assert all(step['runner']['resume_validated'] for step in demo['steps'][1:])
    assert '100% tests passed, 0 tests failed out of 6' in (EVIDENCE/'release_ctest.log').read_text()
    summary['validation']={'ctest_suites_passed':6,'gpu_resume_scenarios':len(resume['cases']),
        'gpu_demo_steps':len(demo['steps']),'gpu_demo_words_compared':demo['words_compared'],
        'conformance':conformance,'source_review':'No additional unimplemented assigned structural law found within the documented finite representation.'}
    for name in ['memcheck','synccheck','racecheck']:
        content=(EVIDENCE/('release_'+name+'.log')).read_text()
        assert ('0 hazards displayed (0 errors, 0 warnings)' if name=='racecheck' else 'ERROR SUMMARY: 0 errors') in content
    profile=(EVIDENCE/'release_mixed_profile.csv').read_text().splitlines()
    start=next(i for i,line in enumerate(profile) if line.startswith('"ID"'))
    metrics={row['Metric Name']:float(row['Metric Value'].replace('.','').replace(',','.')) for row in csv.DictReader(profile[start:])}
    summary['representative_mixed_profile']={'cases':32768,'scope':'Separate profiled shard; not the full-memory run',
        'SM_percent_of_peak':metrics['sm__throughput.avg.pct_of_peak_sustained_elapsed'],
        'DRAM_percent_of_peak':metrics['dram__throughput.avg.pct_of_peak_sustained_elapsed'],
        'active_warp_occupancy_percent':metrics['sm__warps_active.avg.pct_of_peak_sustained_active']}
    summary['limits']=['Eight declared structural templates per capacity workload with distinct retained-history IDs; not exhaustive TOM possibility space.',
        'No unique dynamics assigned by the source.', 'Available CUDA allocation budget filled; maximum compute throughput not established.',
        'Only each run final output is compared independently; timed passes reevaluate the same inputs.']
    (EVIDENCE/'release_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    sources=[ROOT/'CMakeLists.txt',ROOT/'README.md',binary,ROOT/'build-cuda128/Release/tom_native_cpu.exe',
        ROOT/'include/tom/native_core.hpp',ROOT/'include/tom/native_image.hpp',ROOT/'src/native_cpu.cpp',ROOT/'cuda/native_main.cu',
        ROOT/'python/tom/native.py',ROOT/'examples/native_acceptance_cases.json']
    sources.extend(ROOT/path for path in ['docs/NATIVE_CONTRACT.md','docs/NATIVE_EXECUTION_RESULTS.md','docs/native_abi.json'])
    sources.extend(ROOT.glob('tools/*native*.py'));sources.extend(ROOT.glob('tests/native*'))
    sources.extend(path for path in EVIDENCE.glob('release_*') if path.is_file() and path.name!='release_manifest.json')
    sources.extend(path for path in EVIDENCE.glob('source_full.*') if path.is_file())
    sources.extend(path for path in EVIDENCE.glob('native*template*') if path.is_file())
    for stem in ['native_cases','native_valid','native_deep']:
        sources.extend(EVIDENCE/(stem+suffix) for suffix in ['.ton','.reference.tor','.release.gpu.tor'])
    sources.extend(EVIDENCE/name for name in ['tune_256_32768.json','optimized_256.json'])
    sources.extend(ROOT/'verification/formalization_20260918'/name for name in ['TOM.tom','TOM_V0_7.json','formalization.txt'])
    sources.extend(path for path in (EVIDENCE/'demo').rglob('*') if path.is_file())
    pdf=ROOT.parents[1]/'TOM_V0_7_Formalization.pdf'
    assert sha(pdf)=='97582a16bd54d690b27105f9b09dc48d2b5716bbae2fff2a5e74190278640fbc'
    manifest={'schema':'tom-native-release-evidence-v1','created_utc':datetime.now(timezone.utc).isoformat(),
        'source_pdf':str(pdf),'source_pdf_sha256':sha(pdf),'binary_sha256':digest,
        'scope':'Bounded execution of assigned source structural laws and explicit continuation contract, not unique autonomous dynamics or global maximum compute performance.',
        'files':{str(path.relative_to(ROOT)):sha(path) for path in sorted(set(sources))}}
    (EVIDENCE/'release_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'status':'PASS','manifest_files':len(manifest['files']),'binary_sha256':digest,
        'summary':str(EVIDENCE/'release_summary.json')}))


if __name__=='__main__':main()
