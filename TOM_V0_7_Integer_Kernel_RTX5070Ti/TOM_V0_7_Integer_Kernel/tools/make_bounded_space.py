#!/usr/bin/env python3
"""Build an exhaustive bounded certificate interpretation of the V0.7 contract.

Each input lane has a distinct, reversible counter encoding. This enumerates
candidate certificates; it does not supply the source's unassigned dynamics.
"""
import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from tom.builder import Builder

DEFAULT_PDF=ROOT.parents[1]/'TOM_V0_7_Formalization.pdf'
DEFAULT_PACKAGE=ROOT.parents[1]/'TOM_V0_7_Package.zip'
CONTRACT_MEMBER='TOM_V0_7/formalization/TOM_V0_7.json'


def source_contract(pdf=DEFAULT_PDF,package=DEFAULT_PACKAGE):
    raw_pdf=Path(pdf).read_bytes()
    with zipfile.ZipFile(package) as archive:
        raw_contract=archive.read(CONTRACT_MEMBER)
        if archive.read('TOM_V0_7/TOM_V0_7_Formalization.pdf')!=raw_pdf:
            raise ValueError('source PDF differs from the companion package PDF')
    contract=json.loads(raw_contract)
    return {'pdf_name':Path(pdf).name,'pdf_sha256':hashlib.sha256(raw_pdf).hexdigest(),
            'package_name':Path(package).name,'package_sha256':hashlib.sha256(Path(package).read_bytes()).hexdigest(),
            'contract_member':CONTRACT_MEMBER,'contract_sha256':hashlib.sha256(raw_contract).hexdigest(),
            'core_expression':contract['core_expression'],'editorial_contract':contract}


def analytic_counts(time_bits,retention_bits,direct_bits,witness_bits):
    n=1<<time_bits;m=1<<direct_bits
    left_bits=(witness_bits+1)//2;right_bits=witness_bits//2
    witness_total=1<<witness_bits;distinct=witness_total-(1<<min(left_bits,right_bits))
    time_total=n**4;retention_total=1<<(2*retention_bits);scalar_total=m*m
    total=time_total*retention_total*scalar_total*witness_total
    forward_pairs=n*(n-1)//2
    temporal=n*(n*n-1)//3
    retention=3**retention_bits
    neutral=m*m//2+m-1
    base=temporal*retention
    return {'total_candidates':total,
            'forward':forward_pairs*n*n*retention_total*scalar_total*witness_total,
            'elapsed_preserved':forward_pairs*n*retention_total*scalar_total*witness_total,
            'future_independent':n*n*(n*(n+1)//2)*retention_total*scalar_total*witness_total,
            'retention_preserved':time_total*retention*scalar_total*witness_total,
            'temporal_retention_admissible':base*scalar_total*witness_total,
            'Arch_neutral':time_total*retention_total*neutral*witness_total,
            'distinct_witnesses':time_total*retention_total*scalar_total*distinct,
            'temporal_and_arch_neutral':base*neutral*witness_total,
            'temporal_and_distinct':base*scalar_total*distinct,
            'temporal_arch_and_distinct':base*neutral*distinct}


def build_profile(*,time_bits=3,retention_bits=3,direct_bits=4,witness_bits=3,source=None):
    if min(time_bits,retention_bits,direct_bits)<1 or witness_bits<2:
        raise ValueError('time/retention/direct widths must be positive; witness width at least two')
    input_bits=4*time_bits+2*retention_bits+2*direct_bits+witness_bits
    if input_bits>63:raise ValueError('counter profile exceeds supported lane-index width')
    b=Builder(f'TOM V0.7 bounded certificate space: {input_bits} independent input bits')
    layout=[];offset=0
    def field(name,width,signed=False):
        nonlocal offset
        bits=b.bits(name,width,signed=signed,counter_start=offset)
        layout.append({'name':name,'bits':width,'counter_start':offset,'signed':signed})
        offset+=width;return bits
    previous=field('previous_time',time_bits);current=field('current_time',time_bits)
    elapsed=field('elapsed',time_bits);dependency=field('latest_dependency',time_bits)
    before=field('retained_before',retention_bits);after=field('retained_after',retention_bits)
    direct=field('direct',direct_bits,True);echo=field('echo',direct_bits,True)
    left=field('left_definition_witness',(witness_bits+1)//2)
    right=field('right_definition_witness',witness_bits//2)
    forward=b.less(previous,current)
    duration=b.gate('AND',forward,b.eq(b.sub(current,previous),elapsed))
    available=b.inverse(b.less(current,dependency))
    retained=b.reduce('AND',[b.gate('OR',b.inverse(x),y) for x,y in zip(before,after)],'ONE')
    temporal=b.reduce('AND',[forward,duration,available,retained],'ONE')
    direct_zero=b.inverse(b.reduce('OR',direct,'ZERO'));echo_zero=b.inverse(b.reduce('OR',echo,'ZERO'))
    neutral=b.gate('OR',b.gate('XOR',direct[-1],echo[-1]),b.gate('OR',direct_zero,echo_zero))
    width=max(len(left),len(right))
    distinct=b.inverse(b.eq(left+['ZERO']*(width-len(left)),right+['ZERO']*(width-len(right))))
    for name,value in [('forward',forward),('elapsed_preserved',duration),('future_independent',available),
                       ('retention_preserved',retained),('temporal_retention_admissible',temporal),
                       ('Arch_neutral',neutral),('distinct_witnesses',distinct),
                       ('temporal_and_arch_neutral',b.gate('AND',temporal,neutral)),
                       ('temporal_and_distinct',b.gate('AND',temporal,distinct)),
                       ('temporal_arch_and_distinct',b.reduce('AND',[temporal,neutral,distinct],'ONE'))]:
        b.output(name,value)
    # Two guard bits represent abs(min_signed), the widest difference, and their
    # sum without modular overflow before the final nonnegative residual.
    a=direct+[direct[-1]]*2;e=echo+[echo[-1]]*2
    abs_a=b.mux_bits(a,b.negate(a),a[-1]);abs_e=b.mux_bits(e,b.negate(e),e[-1])
    difference=b.sub(a,e);abs_difference=b.mux_bits(difference,b.negate(difference),difference[-1])
    total,_=b.add(abs_a,abs_e)
    b.output_group('Arch_residual',b.sub(total,abs_difference))
    image=b.compile()
    widths={'time_bits':time_bits,'retention_bits':retention_bits,'direct_bits':direct_bits,'witness_bits':witness_bits}
    words_per_case_numerator=2*image.header[8]+image.header[9]
    profile={'name':'bounded certificate interpretation','widths':widths,'input_bits':input_bits,
             'unique_candidate_count':1<<input_bits,'candidate_encoding':'Input groups take disjoint low-to-high bits of the zero-based lane index; all inputs are retained unchanged by each tick.',
             'input_layout':layout,'analytic_full_domain_counts':analytic_counts(**widths),
             'working_bytes_per_case_numerator':words_per_case_numerator,'working_bytes_per_case_denominator':8,
             'full_domain_working_bytes':words_per_case_numerator*(1<<input_bits)//8,
             'source':source if source is not None else source_contract(),
             'source_mapping':[
                 {'pages':[6,7],'clause':'TC1','realization':'latest_dependency <= current_time; availability stamps are supplied witnesses, not authenticated provenance'},
                 {'pages':[6,8],'clause':'TC2 / inverse-Occam','realization':'retained_before is a subset of retained_after; every input and both distinct-definition witnesses remain visible; membership masks do not certify arbitrary historical content'},
                 {'pages':[6],'clause':'TC3','realization':'sign changes affect only the optional reading; they never reverse the runner epoch'},
                 {'pages':[6,7],'clause':'TC4','realization':'all lane inputs remain old-state reads; outputs publish to a separate next snapshot; no native continuation law is selected'},
                 {'pages':[6],'clause':'TC5','realization':'current_time > previous_time and exact unsigned elapsed difference; bounded numeric readings are declared external units'},
                 {'pages':[10],'clause':'optional Arch reading','realization':'exact signed-integer residual and zero predicate; arbitrary echo is NOT asserted equal to ln(1/phi)*direct'},
                 {'pages':[3,5,8,14,18],'clause':'native roles and binding','realization':'the exact source expression and entire editorial contract are retained in metadata; their unassigned operators are not replaced by the certificate arithmetic'}],
             'open_laws':['jitter behavior','when a continuation becomes actual','intrinsic pinion transformation','physical observation protocol','recoverable unbounded-history codec','thermodynamic entropy interpretation'],
             'interpretation_limits':['Finite bounded certificate exploration, not a unique native evolution or empirical physics claim.',
                 'Arch neutrality is an optional filter, separate from temporal/retention acceptance.',
                 'Different witness integers are supplied definition labels; they do not establish a universal definition-equivalence decision procedure.',
                 'Preservation idempotence is retained as a source law; this certificate circuit does not implement a general native rewrite calculus.',
                 'A prefix contains distinct candidates but is not exhaustive unless every declared candidate index is covered exactly once.']}
    image.metadata['bounded_realization']=profile
    return b.spec,image


def decode_candidate(index,profile):
    if not 0<=index<profile['unique_candidate_count']:raise ValueError('candidate index outside declared profile')
    result={}
    for field in profile['input_layout']:
        value=(index>>field['counter_start'])&((1<<field['bits'])-1)
        if field['signed'] and value&(1<<(field['bits']-1)):value-=1<<field['bits']
        result[field['name']]=value
    return result


def oracle(case):
    forward=case['current_time']>case['previous_time']
    duration=forward and case['elapsed']==case['current_time']-case['previous_time']
    available=case['latest_dependency']<=case['current_time']
    retained=(case['retained_before']&~case['retained_after'])==0
    temporal=forward and duration and available and retained
    a,e=case['direct'],case['echo'];residual=abs(a)+abs(e)-abs(a-e)
    neutral=residual==0;distinct=case['left_definition_witness']!=case['right_definition_witness']
    return {'forward':int(forward),'elapsed_preserved':int(duration),'future_independent':int(available),
            'retention_preserved':int(retained),'temporal_retention_admissible':int(temporal),'Arch_neutral':int(neutral),
            'distinct_witnesses':int(distinct),'temporal_and_arch_neutral':int(temporal and neutral),
            'temporal_and_distinct':int(temporal and distinct),'temporal_arch_and_distinct':int(temporal and neutral and distinct),
            'Arch_residual':residual}


@lru_cache(maxsize=16)
def predicate_tables(time_bits,retention_bits,direct_bits,witness_bits):
    """Cumulative counts for independent low-to-high input groups."""
    sizes=[1<<(4*time_bits),1<<(2*retention_bits),1<<(2*direct_bits),1<<witness_bits]
    if max(sizes)>1<<20:raise ValueError('prefix oracle group exceeds the supported exhaustive table size')
    tables=[]
    for group,size in enumerate(sizes):
        predicates={name:[0] for name in (('all','forward','duration','available','temporal') if group==0 else ('all','valid'))}
        for value in range(size):
            if group==0:
                mask=(1<<time_bits)-1
                old=value&mask;now=(value>>time_bits)&mask
                elapsed=(value>>(2*time_bits))&mask;dependency=value>>(3*time_bits)
                forward=now>old;duration=forward and elapsed==now-old;available=dependency<=now
                flags={'all':True,'forward':forward,'duration':duration,'available':available,'temporal':duration and available}
            elif group==1:
                mask=(1<<retention_bits)-1;before=value&mask;after=value>>retention_bits
                flags={'all':True,'valid':(before&~after)==0}
            elif group==2:
                n=1<<direct_bits;a=value&(n-1);e=value>>direct_bits
                if a&(n>>1):a-=n
                if e&(n>>1):e-=n
                flags={'all':True,'valid':a*e<=0}
            else:
                left_bits=(witness_bits+1)//2
                flags={'all':True,'valid':(value&((1<<left_bits)-1))!=(value>>left_bits)}
            for name,flag in flags.items():predicates[name].append(predicates[name][-1]+int(flag))
        tables.append({name:tuple(counts) for name,counts in predicates.items()})
    return tuple(sizes),tuple(tables)


def prefix_counts(profile,lanes):
    """Exact output-mask totals over candidate indices [0, lanes), without GPU IO.

    Each table counts one independent contiguous group. Splitting at the highest
    group counts complete lower-group blocks plus one partial block recursively.
    """
    if not isinstance(lanes,int) or not 0<=lanes<=profile['unique_candidate_count']:
        raise ValueError('prefix outside the unique candidate domain')
    widths=profile['widths'];sizes,tables=predicate_tables(**widths)
    factors={
        'forward':('forward','all','all','all'),
        'elapsed_preserved':('duration','all','all','all'),
        'future_independent':('available','all','all','all'),
        'retention_preserved':('all','valid','all','all'),
        'temporal_retention_admissible':('temporal','valid','all','all'),
        'Arch_neutral':('all','all','valid','all'),
        'distinct_witnesses':('all','all','all','valid'),
        'temporal_and_arch_neutral':('temporal','valid','valid','all'),
        'temporal_and_distinct':('temporal','valid','all','valid'),
        'temporal_arch_and_distinct':('temporal','valid','valid','valid')}
    result={'total_candidates':lanes}
    for name,predicates in factors.items():
        lower_sizes=[1];lower_totals=[1]
        for size,table,predicate in zip(sizes,tables,predicates):
            lower_sizes.append(lower_sizes[-1]*size)
            lower_totals.append(lower_totals[-1]*table[predicate][-1])
        def count(group,length):
            if group<0:return length
            complete,remainder=divmod(length,lower_sizes[group])
            cumulative=tables[group][predicates[group]]
            total=cumulative[complete]*lower_totals[group]
            if remainder and cumulative[complete+1]!=cumulative[complete]:
                total+=count(group-1,remainder)
            return total
        result[name]=count(len(sizes)-1,lanes)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name,default in [('time-bits',3),('retention-bits',3),('direct-bits',4),('witness-bits',3)]:parser.add_argument('--'+name,type=int,default=default)
    parser.add_argument('--source-pdf',type=Path,default=DEFAULT_PDF);parser.add_argument('--source-package',type=Path,default=DEFAULT_PACKAGE)
    parser.add_argument('--out',type=Path,help='output .tsdf path; defaults to examples/bounded_space_<inputbits>bit.tsdf')
    args=parser.parse_args()
    spec,image=build_profile(time_bits=args.time_bits,retention_bits=args.retention_bits,direct_bits=args.direct_bits,witness_bits=args.witness_bits,
                             source=source_contract(args.source_pdf,args.source_package))
    profile=image.metadata['bounded_realization'];path=args.out or ROOT/'examples'/f'bounded_space_{profile["input_bits"]}bit.tsdf'
    path.parent.mkdir(parents=True,exist_ok=True);image.save(path);path.with_suffix('.json').write_text(json.dumps(spec,indent=2)+'\n')
    print(json.dumps({'path':str(path),'input_bits':profile['input_bits'],'unique_candidates':profile['unique_candidate_count'],
                      'states':image.header[8],'scratch_slots':image.header[9],'definition_bytes':len(image.words)*4,
                      'working_bytes_per_case':profile['working_bytes_per_case_numerator']/8,
                      'full_domain_working_bytes':profile['full_domain_working_bytes'],'analytic_counts':profile['analytic_full_domain_counts']},indent=2))


if __name__=='__main__':main()
