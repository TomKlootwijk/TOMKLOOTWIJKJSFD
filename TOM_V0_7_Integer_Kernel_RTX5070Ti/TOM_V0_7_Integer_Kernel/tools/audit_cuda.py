#!/usr/bin/env python3
"""Audit authored sources, compiled PTX entries, and optional executable SASS.

This static instruction audit does not replace on-device correctness tests and
does not cover host code or third-party CUDA/driver internals.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
FLOAT_PTX=re.compile(r'\.(?:f16x2|f16|f32|f64|bf16x2|bf16|tf32|e4m3|e5m2)\b')
FLOAT_SASS=re.compile(r'^(?:F(?:ADD|MUL|FMA|MNMX|SET|SETP|SEL|CHK|2F|2I)|I2F|D(?:ADD|MUL|FMA|MNMX|SET|SETP)|H(?:ADD2|MUL2|FMA2|SET2|SETP2|MMA)|MUFU|RRO)')
# Unknown instruction families require review rather than an assumed PASS.
INTEGER_SASS=set('IADD IADD3 IMAD IMUL IABS ISETP ISET IMNMX IDP IDP4A LEA LOP3 PLOP3 POPC FLO SHF SHL SHR BFE BFI BMSK BREV PRMT SEL VABSDIFF VABSDIFF4 VADD VADD2 VADD4 VSET VSETP VIADD VIMNMX'.split())
MEMORY_SASS=set('LD LDG LDL LDS LDC LDCU ST STG STL STS TEX TLD TLD4 TXQ LDSM LDGSTS REDG'.split())
CONTROL_SASS=set('BSSY BSYNC BRA BRX BREAK BPT CALL RET EXIT NOP YIELD WARPSYNC BAR DEPBAR MEMBAR ERRBAR S2R S2UR CS2R MOV UMOV R2UR UR2R P2R R2P PSETP VOTE VOTEU MATCH REDUX SHFL SETCTAID GETLMEMBASE SETLMEMBASE CCTL CCTLL CCTLT'.split())
UNIFORM_SASS=set('UIADD3 UIMAD UISETP ULOP3 USHF USHFL USEL UPRMT UFLO UBMSK ULEA UPOPC UPLOP3 UPSETP USETMAXREG'.split())


def sha256(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def entry_role(name):
    match=re.search(r'execute_kernelILi([012])ELb([01])E',name)
    if match:return ('texture','global','shared')[int(match[1])]+'/'+('field','lowered')[int(match[2])]
    if 'initialize' in name:return 'initialize'
    if 'count_state' in name:return 'count_state'
    return 'unknown'


def coverage(names):
    expected={'initialize','count_state'}|{backend+'/'+mode for backend in ('texture','global','shared') for mode in ('field','lowered')}
    actual=[entry_role(name) for name in names]
    return {'status':'PASS' if len(actual)==len(expected) and set(actual)==expected else 'FAIL',
            'expected_entry_count':len(expected),'actual_entry_count':len(actual),'roles':actual,'missing_roles':sorted(expected-set(actual))}


def without_comments(text):return re.sub(r'//[^\n]*|/\*.*?\*/','',text,flags=re.S)


def ptx_entries(text):
    entries=[]
    for match in re.finditer(r'\.entry\s+([^\s(]+)\s*\(',text):
        start=text.find('{',match.end())
        if start<0:continue
        depth=1;end=start+1
        while end<len(text) and depth:
            depth+=(text[end]=='{')-(text[end]=='}');end+=1
        body=text[start+1:end-1]
        entries.append({'name':match[1],'role':entry_role(match[1]),'body_lines':len(body.splitlines()),
                        'floating_lines':[line.strip() for line in body.splitlines() if FLOAT_PTX.search(line)]})
    return entries


def sass_functions(text):
    functions=[];current=None
    for line in text.splitlines():
        match=re.search(r'Function\s*:\s*(\S+)',line)
        if match:
            current={'name':match[1],'role':entry_role(match[1]),'opcodes':Counter(),'floating_instructions':[],
                     'constant_zero_float_instructions':[],'other_float_instructions':[],'unclassified_opcodes':set()}
            functions.append(current);continue
        instruction=re.match(r'\s*/\*[0-9a-fA-F]+\*/\s+(?:@!?\w+\s+)?([A-Z][A-Z0-9_.]*)(?=[\s;])',line)
        if current is None or not instruction:continue
        opcode=instruction[1];family=opcode.split('.')[0];current['opcodes'][opcode]+=1
        if FLOAT_SASS.match(family) or FLOAT_PTX.search(opcode.lower()):
            current['floating_instructions'].append(line.strip())
            # ptxas can initialize a register with a half2 FMA on literal zeros.
            # Keep this in the strict floating-opcode count, but distinguish it
            # from floating arithmetic that could depend on program data.
            zero=re.search(r'\bHFMA2\s+R\d+,\s*-RZ,\s*RZ,\s*0,\s*0\s*(?:[&?;]|$)',line)
            current['constant_zero_float_instructions' if zero else 'other_float_instructions'].append(line.strip())
        elif family not in INTEGER_SASS|MEMORY_SASS|CONTROL_SASS|UNIFORM_SASS:current['unclassified_opcodes'].add(opcode)
    for item in functions:
        item['instruction_count']=sum(item['opcodes'].values());item['opcodes']=dict(sorted(item['opcodes'].items()))
        item['unclassified_opcodes']=sorted(item['unclassified_opcodes'])
    return functions


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compile',action='store_true');parser.add_argument('--arch',default='compute_120')
    parser.add_argument('--nvcc',help='nvcc path; defaults to PATH discovery')
    parser.add_argument('--ccbin',help='supported host compiler directory or executable')
    parser.add_argument('--binary',type=Path,help='built CUDA executable for SASS disassembly')
    parser.add_argument('--cuobjdump',help='cuobjdump path; defaults to nvcc sibling or PATH')
    parser.add_argument('--out',type=Path,default=ROOT/'verification/integer_audit.json')
    args=parser.parse_args();args.out.parent.mkdir(parents=True,exist_ok=True)
    report={'source_status':'PASS','ptx_compile':'NOT_RUN','ptx_float_audit':'NOT_RUN','sass_disassembly':'NOT_RUN','sass_float_audit':'NOT_RUN','files':{}}
    for relative in ('include/tom/core.hpp','cuda/main.cu'):
        path=ROOT/relative;plain=without_comments(path.read_text())
        tokens=re.findall(r'\b(?:float|double|__half|__nv_bfloat16)\b',plain)
        report['files'][relative]={'sha256':sha256(path),'floating_type_tokens':tokens}
        if tokens:report['source_status']='FAIL'
    compiler=args.nvcc or shutil.which('nvcc')
    if args.compile:
        if compiler is None:report['ptx_compile']='UNAVAILABLE: nvcc not installed or not on PATH'
        else:
            target=args.out.with_suffix('.ptx').resolve()
            command=[compiler,'--ptx','-std=c++17',f'-arch={args.arch}','-I',str(ROOT/'include'),str(ROOT/'cuda/main.cu'),'-o',str(target)]
            if args.ccbin:command.extend(['-ccbin',args.ccbin])
            completed=subprocess.run(command,capture_output=True,text=True)
            report['command']=command;report['compiler_output']=completed.stdout+completed.stderr
            report['ptx_compile']='PASS' if completed.returncode==0 else 'FAIL'
            if not completed.returncode:
                text=without_comments(target.read_text());entries=ptx_entries(text)
                floating=[line.strip() for line in text.splitlines() if FLOAT_PTX.search(line)]
                report['ptx']={'path':str(target),'sha256':sha256(target),'entries':entries,'coverage':coverage([item['name'] for item in entries])}
                report['floating_ptx_lines']=floating;report['ptx_float_audit']='REVIEW_REQUIRED' if floating else 'PASS'
    if args.binary:
        disassembler=args.cuobjdump or (str(Path(compiler).with_name('cuobjdump.exe' if Path(compiler).suffix=='.exe' else 'cuobjdump')) if compiler else shutil.which('cuobjdump'))
        if disassembler is None:report['sass_disassembly']='UNAVAILABLE: cuobjdump not installed or not on PATH'
        else:
            command=[disassembler,'--dump-sass',str(args.binary.resolve())]
            completed=subprocess.run(command,capture_output=True,text=True)
            report['sass_command']=command;report['sass_output_diagnostics']=completed.stderr
            report['sass_disassembly']='PASS' if completed.returncode==0 else 'FAIL'
            if not completed.returncode:
                target=args.out.with_suffix('.sass.txt').resolve();target.write_text(completed.stdout)
                functions=sass_functions(completed.stdout)
                report['sass']={'path':str(target),'sha256':sha256(target),'binary':str(args.binary.resolve()),'binary_sha256':sha256(args.binary),
                                'functions':functions,'coverage':coverage([item['name'] for item in functions])}
                coverage_failed=report['sass']['coverage']['status']!='PASS'
                requires_review=coverage_failed or any(item['floating_instructions'] or item['unclassified_opcodes'] or not item['instruction_count'] for item in functions)
                report['sass_float_audit']='REVIEW_REQUIRED' if requires_review else 'PASS'
                report['sass']['constant_zero_float_instruction_count']=sum(len(item['constant_zero_float_instructions']) for item in functions)
                report['sass']['other_float_instruction_count']=sum(len(item['other_float_instructions']) for item in functions)
                report['sass']['data_computation_audit']='REVIEW_REQUIRED' if coverage_failed or any(item['other_float_instructions'] or item['unclassified_opcodes'] or not item['instruction_count'] for item in functions) else 'PASS'
                report['sass']['classification_reference']='https://docs.nvidia.com/cuda/cuda-binary-utilities/'
    report['scope']='Static authored-device-code audit: source token scan, PTX floating-type scan, and recognized SASS instruction-family inventory. Integer/bit computation, address calculation, memory/texture access, and control instructions are included. Host executable instructions, runtime/driver internals, and physical device behavior are outside this claim. PTX source hashes and the separately audited executable hash identify their respective artifacts; source/binary correspondence must be established by the build.'
    statuses=[report[key] for key in ('source_status','ptx_compile','ptx_float_audit','sass_disassembly','sass_float_audit')]
    coverages=[report[key]['coverage']['status'] for key in ('ptx','sass') if key in report]
    failed=any(value in ('FAIL','REVIEW_REQUIRED') for value in statuses+coverages)
    unavailable=any(value.startswith('UNAVAILABLE') for value in statuses)
    report['status']='REVIEW_REQUIRED' if failed else 'INCOMPLETE' if unavailable or not (args.compile and args.binary) else 'PASS'
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'source_status':report['source_status'],'ptx_compile':report['ptx_compile'],'ptx_float_audit':report['ptx_float_audit'],
                      'ptx_entries':report.get('ptx',{}).get('coverage',{}),'sass_disassembly':report['sass_disassembly'],'sass_float_audit':report['sass_float_audit'],
                      'sass_entries':report.get('sass',{}).get('coverage',{}),
                      'constant_zero_float_instruction_count':report.get('sass',{}).get('constant_zero_float_instruction_count'),
                      'other_float_instruction_count':report.get('sass',{}).get('other_float_instruction_count'),'output':str(args.out)},indent=2))
    if failed:raise SystemExit(1)


if __name__=='__main__':main()
