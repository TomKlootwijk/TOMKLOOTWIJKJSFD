#!/usr/bin/env python3
"""Build and inspect actual TOM native-term executions, with explicit source scope."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from tom.native import (Config,NativeCase,Op,Flag,Status,NONE,SYMBOL_IDS,apply,source_root,
    encode_terms,evaluate_words,write_batch,read_batch,unpack_result,SOURCE_PDF_SHA256,
    decl,self_name,later)


def make_templates(directory,mixed_continuations=False):
    """Eight source-equivalent terms, with original syntax and actual history retained."""
    directory.mkdir(parents=True,exist_ok=True)
    cases=[];descriptions=[]
    for index in range(8):
        base=source_root('A' if index&1 else 'T')
        wrapped=base.args[0]
        for _ in range(index):wrapped=apply(Op.INVERSE_OCCAM,wrapped)
        root=apply(Op.FORWARD_T,wrapped)
        case=None
        if mixed_continuations:
            own=self_name();deferred=later(7,own)
            guards=[(7,True,root)]
            requests=[(own,0),(deferred,1),(decl('Klein'),0),(decl('Matryoshka'),0)]
            if index==1:guards=[(7,False,root)]
            elif index==2:guards=[(7,True,None)]
            elif index==3:guards=[]
            elif index==6:requests.append((own,1))
            elif index==7:requests.append((later(8,own),1))
            case=NativeCase.from_term(root,guards=guards,requests=requests)
            records=case.records;root_id=case.root
        else:
            records,ids=encode_terms([root]);root_id=ids[id(root)]
        # This chosen finite history codec retains complete term bytes and its
        # root/length, with an externally declared order tag. It is not a claim
        # that native TOM supplied an intrinsic codec or physical observation.
        initial=b'\0'*8+b'completed commitment retained exactly'
        extension=struct.pack('<QII',15,len(records),root_id)
        extension+=struct.pack('<'+str(8*len(records))+'I',*(x for record in records for x in record))
        proposed=initial+extension
        flags=Flag.REQUIRE_SOURCE_TOM|Flag.SCALAR_LOG_ECHO|Flag.ADVANCE_TRANSACTION
        if index&1:flags|=Flag.ALIAS_A_T
        if case is None:case=NativeCase(records,root_id)
        case.old_history=initial;case.proposed_history=proposed
        case.previous=10;case.now=15;case.elapsed=4 if mixed_continuations and index==5 else 5
        case.latest_available=16 if mixed_continuations and index==4 else 12
        case.flags=flags;cases.append(case)
        descriptions.append({'template':index,'original_records':len(records),'extra_preservation_qualifications':index,
            'explicit_A_T_alias':bool(index&1),'old_history_bytes':len(initial),'proposed_history_bytes':len(proposed)})
    config=Config(max(len(c.records) for c in cases),(max(len(c.proposed_history) for c in cases)+3)//4,
        max(len(c.guards) for c in cases),max(len(c.requests) for c in cases))
    packed=[case.pack(config) for case in cases]
    expected=[evaluate_words(case,config) for case in packed]
    if any(not result[7] for result in expected):raise AssertionError('source template lost full source expression')
    if not mixed_continuations and any(result[0] for result in expected):raise AssertionError('source template did not pass independent reference')
    if mixed_continuations:
        wanted=[0,16,32,16,8,2,64,16]
        if [result[0] for result in expected]!=wanted:raise AssertionError('mixed continuation statuses differ from declared scenario')
        if any({record[0] for record in case.records}!=set(Op) for case in cases):
            raise AssertionError('mixed template must retain every native opcode')
        for description,result in zip(descriptions,expected):
            description.update(status=result[0],resolved_requests=result[4],unresolved_requests=result[5])
    stem='native_mixed_templates' if mixed_continuations else 'native_templates'
    input_path=directory/(stem+'.ton');oracle_path=directory/(stem+'_expected.tor')
    write_batch(input_path,config,packed);write_batch(oracle_path,config,expected,output=True)
    metadata={'source_pdf_sha256':SOURCE_PDF_SHA256,'input':str(input_path.resolve()),'expected':str(oracle_path.resolve()),
        'input_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),
        'expected_sha256':hashlib.sha256(oracle_path.read_bytes()).hexdigest(),
        'case_words':config.case_words,'result_words':config.result_words,
        'bytes_per_resident_case':4*(config.case_words+config.result_words),'templates':descriptions,
        'scope':'Full bound source expression, actual licensed normalization and complete retained history contents. No unique native dynamics assigned.',
        'generated_variation':'Round-robin source-equivalent terms; distinct uint64 candidate identity in the first eight bytes of both completed and proposed history.'}
    metadata['mixed_continuations']=mixed_continuations
    if mixed_continuations:metadata['scenarios']=['assigned result','false guard','unassigned law','missing guard','future evidence','lost elapsed duration','unguarded result','one resolved plus one pending; atomic block']
    (directory/(stem+'.json')).write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata


def term_text(records,root):
    names={value:key for key,value in SYMBOL_IDS.items()};rendered=[]
    for record in records:
        op=Op(record[0]);count=record[1]
        if op in (Op.DECL,Op.SELF):
            name=names.get(record[4],f'declared_{record[4]}')
            value=name if op==Op.DECL else 'SELF['+name+']'
        elif op==Op.LATER_T:value=f'LATER_T[guard={record[4]}; {rendered[record[2]]}]'
        else:value=op.name+'['+'; '.join(rendered[record[2+k]] for k in range(count))+']'
        rendered.append(value)
    return rendered[root]


def inspect(path,selected):
    config,results=read_batch(path,output=True);rows=[]
    for index in selected:
        value=unpack_result(results[index],config)
        flags=[status.name for status in Status if value['status']&status]
        rows.append({'case':index,'admitted':value['status']==0,'status':flags or ['ADMITTED'],
            'source_TOM':value['source_tom'],
            'normalized_expression':None if value['normalized_root']==NONE else term_text(value['normalized'],value['normalized_root']),
            'InverseOccam_rewrites':value['io_rewrites'],'explicit_alias_rewrites':value['alias_rewrites'],
            'retained_original_input_words':len(value['original']),
            'committed_history_bytes':len(value['committed_history']),
            'committed_history_sha256':hashlib.sha256(value['committed_history']).hexdigest(),
            'optional_exact_log_echo_zero_proved':value['optional_scalar_echo_zero_proved'],
            'resolved_requests':value['resolved'],'unresolved_requests':value['unresolved']})
    return {'scope':'Actual saved native execution results; symbolic roles are not invented dynamics.','cases':rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    make=commands.add_parser('templates');make.add_argument('--out',type=Path,default=ROOT/'verification/native_20260918')
    make.add_argument('--mixed-continuations',action='store_true')
    read=commands.add_parser('inspect');read.add_argument('path',type=Path);read.add_argument('--cases',type=int,nargs='+',default=[0])
    args=parser.parse_args()
    result=make_templates(args.out,args.mixed_continuations) if args.command=='templates' else inspect(args.path,args.cases)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
