#!/usr/bin/env python3
"""Execute float-free validation images; compare complete outputs with independent oracles."""
from __future__ import annotations
import argparse,copy,json,random,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'));sys.path.insert(0,str(ROOT/'tools'))
from tom.compiler import Image,compile_definition,load_state,save_state,seed_words,reference_tick,lane_value,MICRO,FULL
from tom.builder import Builder
from pack_cases import pack

def signed8(x):return x-256 if x>=128 else x

def execute(exe,program,out,*,lanes=128,ticks=1,data=None,evaluator='field',backend=None):
    args=[str(exe),'--program',str(program),'--ticks',str(ticks),'--evaluator',evaluator,'--out',str(out)]
    if data:args+=['--data',str(data)]
    else:args+=['--lanes',str(lanes)]
    if backend:args+=['--backend',backend,'--verify']
    done=subprocess.run(args,check=True,capture_output=True,text=True)
    report=json.loads(done.stdout);slots,words,epoch,result=load_state(out)
    return report,words,epoch,result

def conformance_cases():
    base={'previous_time':10,'current_time':15,'elapsed':5,'latest_dependency':12,
          'retained_before':0b0011,'retained_after':0b0111,'direct':8,'echo':-4,
          'left_definition_witness':11,'right_definition_witness':17}
    cases=[base]
    for changes in ({'latest_dependency':16},{'current_time':9,'elapsed':65535},
                    {'elapsed':0},{'retained_after':1},{'echo':4}):cases.append({**base,**changes})
    rng=random.Random(20260918)
    for _ in range(512):
        old=rng.randrange(65536);now=rng.randrange(65536);prior=rng.randrange(256)
        cases.append({'previous_time':old,'current_time':now,'elapsed':(now-old)&65535 if rng.randrange(2) else rng.randrange(65536),
          'latest_dependency':rng.randrange(65536),'retained_before':prior,'retained_after':prior|rng.randrange(256) if rng.randrange(2) else rng.randrange(256),
          'direct':rng.randrange(-128,128),'echo':rng.randrange(-128,128),'left_definition_witness':rng.randrange(256),'right_definition_witness':rng.randrange(256)})
    return cases

def check_conformance(image,state,words,cases):
    slot=image.metadata['state_slots']
    for lane,case in enumerate(cases):
        expected={
          'forward':case['current_time']>case['previous_time'],
          'elapsed_preserved':case['current_time']>case['previous_time'] and (case['current_time']-case['previous_time'])==case['elapsed'],
          'future_independent':case['latest_dependency']<=case['current_time'],
          'retention_preserved':(case['retained_before']&~case['retained_after'])==0,
          'Arch_neutral':case['direct']*case['echo']<=0,
          'distinct_witnesses':case['left_definition_witness']!=case['right_definition_witness']}
        expected['temporal_retention_conformant']=all(expected[k] for k in ('forward','elapsed_preserved','future_independent','retention_preserved'))
        expected['all_reported_checks']=expected['temporal_retention_conformant'] and expected['Arch_neutral']
        for name,value in expected.items():
            if lane_value(state,words,[slot[name]],lane)!=int(value):raise AssertionError(('conformance',lane,name,value))
    return True

def literal_micro_reference(image,a,b,c,table):
    regs=[FULL if (table>>i)&1 else 0 for i in range(8)]+[a,b,c]+[0]*7
    k=image.record(image.header[10]);base,count,selector,out=k[1:5]
    for offset in range(base,base+4*count,4):
        dst,x,y,z=image.words[offset:offset+4]
        value=0
        for row in range(8):
            if (selector>>row)&1:value|=(regs[x] if row&1 else regs[x]^FULL)&(regs[y] if row&2 else regs[y]^FULL)&(regs[z] if row&4 else regs[z]^FULL)
        regs[dst]=value
    return regs[out]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--backend',choices=('cpu','texture','global','shared'),default='cpu')
    parser.add_argument('--quick',action='store_true');parser.add_argument('--out',type=Path,default=ROOT/'verification/local_validation.json')
    args=parser.parse_args();exe=args.exe.resolve();backend=None if args.backend=='cpu' else args.backend
    start=time.perf_counter_ns();runs=[];skips=[];counts={}
    gpu_info=json.loads(subprocess.check_output([str(exe),'--info'],text=True)) if backend else None
    def fits(image):
        return not (args.backend=='shared' and len(image.words)*4>gpu_info['shared_optin_bytes'])
    with tempfile.TemporaryDirectory() as temp:
        temp=Path(temp)
        for evaluator in ('field','lowered'):
            # All input triples for all 256 table definitions.
            path=ROOT/'examples/kernel_reflection.tsdf';image=Image.load(path)
            report,words,epoch,state=execute(exe,path,temp/'out.tsdf',lanes=2048,evaluator=evaluator,backend=backend)
            slot=image.metadata['state_slots']['result']
            for lane in range(2048):
                assert lane_value(state,words,[slot],lane)==((lane>>3)>>(lane&7))&1
            runs.append(report)
            counts['all_table_input_cases_per_evaluator']=2048
            # Source scalar audit, signed operands retained in full packed inputs.
            path=ROOT/'examples/arch_exact_int8.tsdf';image=Image.load(path)
            if fits(image):
                report,words,epoch,state=execute(exe,path,temp/'out.tsdf',lanes=65536,evaluator=evaluator,backend=backend)
                slots=[image.metadata['state_slots'][n] for n in image.metadata['groups']['Arch']['bits']]
                for lane in range(65536):
                    a=signed8(lane&255);b=signed8(lane>>8)
                    assert lane_value(state,words,slots,lane)==abs(a)+abs(b)-abs(a-b)
                runs.append(report);counts['signed_int8_Arch_pairs_per_evaluator']=65536
            else:skips.append({'program':'arch_exact_int8','evaluator':evaluator,'reason':'shared image exceeds device limit'})
            # Real TOM temporal/retention obligations, distinct from neutrality.
            path=ROOT/'examples/tom_conformance.tsdf';image=Image.load(path)
            if fits(image):
                cases=conformance_cases();initial,words=pack(image,cases);save_state(temp/'input.tsdf',initial,image.header[8],words)
                report,words,epoch,state=execute(exe,path,temp/'out.tsdf',data=temp/'input.tsdf',evaluator=evaluator,backend=backend)
                check_conformance(image,state,words,cases)
                runs.append(report);counts['temporal_retention_certificates_per_evaluator']=len(cases)
            else:skips.append({'program':'tom_conformance','evaluator':evaluator,'reason':'shared image exceeds device limit'})
            # Full state matches independent minterm evaluator over several T commits.
            path=ROOT/'examples/self_reference.tsdf';image=Image.load(path)
            for ticks in (0,1,2,3,17):
                report,words,epoch,state=execute(exe,path,temp/'out.tsdf',lanes=128,ticks=ticks,evaluator=evaluator,backend=backend)
                oracle=seed_words(image,words)
                for _ in range(ticks):oracle=reference_tick(image,oracle,words)
                assert state==oracle and epoch==ticks
                runs.append(report)
            counts['self_reference_tick_configurations_per_evaluator']=5
            # Every bit of the operational kernel microprogram copies itself via Quote.
            path=ROOT/'examples/kernel_selfcopy.tsdf';image=Image.load(path)
            if fits(image):
                report,words,epoch,state=execute(exe,path,temp/'copy.tsdf',lanes=32,evaluator=evaluator,backend=backend)
                copied=[]
                for w in range(28):
                    slots=[image.metadata['state_slots'][n] for n in image.metadata['groups'][f'word{w}']['bits']]
                    copied.append(lane_value(state,words,slots,0))
                assert copied==MICRO
                runs.append(report);counts['kernel_microprogram_bits_copied_per_evaluator']=896
            else:skips.append({'program':'kernel_selfcopy','evaluator':evaluator,'reason':'full quotation image exceeds shared limit; texture/global still test it'})
        # A changed kernel field changes what executes, not merely its name.
        path=ROOT/'examples/kernel_reflection.tsdf';changed=Image.load(path)
        changed.words[changed.header[10]*16+3]=0xAC
        changed.save(temp/'changed.tsdf')
        _,words,epoch,state=execute(exe,temp/'changed.tsdf',temp/'out.tsdf',lanes=2048,backend=backend)
        slot=changed.metadata['state_slots']['result'];difference=0
        for lane in range(2048):
            a,b,c=[FULL if lane&(1<<i) else 0 for i in range(3)]
            expected=literal_micro_reference(changed,a,b,c,lane>>3)&1
            assert lane_value(state,words,[slot],lane)==expected
            difference+=expected!=(((lane>>3)>>(lane&7))&1)
        assert difference>0
        fail=subprocess.run([str(exe),'--program',str(temp/'changed.tsdf'),'--evaluator','lowered'],capture_output=True)
        assert fail.returncode!=0 and b'edited kernel' in fail.stderr
        counts['modified_kernel_cases']=2048;counts['modified_kernel_outputs_changed']=difference
        # Resumption does not reset the epoch or change deterministic state.
        path=ROOT/'examples/self_reference.tsdf'
        _,_,_,step=execute(exe,path,temp/'prefix.tsdf',lanes=128,ticks=3,backend=backend)
        _,w,ep,resumed=execute(exe,path,temp/'resume.tsdf',data=temp/'prefix.tsdf',ticks=5,backend=backend)
        _,_,_,full=execute(exe,path,temp/'full.tsdf',lanes=128,ticks=8,backend=backend)
        assert resumed==full and ep==8
        counts['resume_cases']=1
        # Independent generated descriptions, mixed constant/dynamic rules.
        rng=random.Random(1782);random_count=8 if args.quick else 48
        for test in range(random_count):
            b=Builder(f'generated conformance realization {test}')
            fields=[b.bit(f'x{i}',{'hash':rng.randrange(1<<32)}) for i in range(4)]
            refs=['ZERO','ONE',*fields]
            for k in range(4):b.spec['rules'][f'R{k}']=rng.randrange(256)
            for k in range(15):refs.append(b.gate(f'R{rng.randrange(4)}',*(rng.choice(refs) for _ in range(3))))
            b.spec['rules']['D']={'rows':[rng.choice(refs) for _ in range(8)]}
            refs.append(b.gate('D',*(rng.choice(refs) for _ in range(3))))
            for name in fields:b.spec['next'][name]=rng.choice(refs)
            image=b.compile();image.save(temp/'random.tsdf');unrecycled=b.compile(False);unrecycled.save(temp/'raw.tsdf')
            ticks=test%4+1
            _,words,epoch,actual=execute(exe,temp/'random.tsdf',temp/'out.tsdf',lanes=96,ticks=ticks,backend=backend)
            expected=seed_words(image,words)
            for _ in range(ticks):expected=reference_tick(image,expected,words)
            assert actual==expected
            _,_,_,raw=execute(exe,temp/'raw.tsdf',temp/'rawout.tsdf',lanes=96,ticks=ticks,backend=backend,evaluator='lowered')
            assert raw==actual
        counts['random_programs']=random_count;counts['random_execution_layouts']=random_count*2
        # Explicit diagnostics: no instantaneous self-loop or made-up native phi opcode.
        b=Builder('invalid');b.bit('x');b.spec['expressions']['loop']={'rule':'NOT','args':['loop']};b.spec['next']['x']='loop'
        try:b.compile()
        except ValueError:pass
        else:raise AssertionError('instantaneous cycle accepted')
        b=Builder('invalid native');b.bit('x');b.spec['expressions']['bad']={'rule':'phi','args':['x']};b.spec['next']['x']='bad'
        try:b.compile()
        except ValueError:pass
        else:raise AssertionError('undefined native pinion was turned into invented arithmetic')
        base=Image.load(ROOT/'examples/self_reference.tsdf')
        for mutate in ('future_micro','self_id','unknown_kind','corrupt_schedule'):
            broken=copy.deepcopy(base)
            if mutate=='future_micro':broken.words[broken.record(0)[1]+1]=17
            elif mutate=='self_id':broken.words[14]=111111
            elif mutate=='unknown_kind':broken.words[base.metadata['names']['SELF']*16]=37
            else:broken.words[broken.header[4]]=FULL
            broken.save(temp/'invalid.tsdf')
            result=subprocess.run([str(exe),'--program',str(temp/'invalid.tsdf'),'--lanes','32'],capture_output=True)
            assert result.returncode!=0
        data=seed_words(base,1);save_state(temp/'last_epoch.tsdf',data,base.header[8],1,(1<<64)-1)
        result=subprocess.run([str(exe),'--program',str(ROOT/'examples/self_reference.tsdf'),'--data',str(temp/'last_epoch.tsdf'),'--ticks','1'],capture_output=True)
        assert result.returncode!=0 and b'epoch' in result.stderr
        counts['invalid_input_and_time_cases']=7
    report={'name':'TOM','version':'0.7-K1','status':'PASS','backend':args.backend,'gpu_executed':bool(backend),'device':gpu_info,
       'counts':counts,'skipped':skips,'run_reports':runs,'elapsed_test_host_ns':time.perf_counter_ns()-start,
       'scope':'finite packed-field representation tests; source scalar readings and explicit temporal/retention certificates, NOT intrinsic continuum physics'}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'PASS','backend':args.backend,'counts':counts,'skipped':skips,'output':str(args.out)},indent=2))
if __name__=='__main__':main()
