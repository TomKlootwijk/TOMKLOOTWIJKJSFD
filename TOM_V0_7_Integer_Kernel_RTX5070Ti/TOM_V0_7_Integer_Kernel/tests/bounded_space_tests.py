#!/usr/bin/env python3
"""Independent finite-domain validation of bounded certificate generation."""
import argparse
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'python'))
from make_bounded_space import analytic_counts,build_profile,decode_candidate,oracle,prefix_counts,source_contract
from pack_cases import pack
from tom.compiler import lane_value,load_state,save_state

EXE=ROOT/'build-cuda128'/'Release'/'tom_cpu.exe'


class BoundedSpaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=source_contract()
        cls.spec,cls.image=build_profile(time_bits=1,retention_bits=1,direct_bits=2,witness_bits=2,source=cls.source)
        cls.profile=cls.image.metadata['bounded_realization']

    def test_source_binding_and_profile_layout(self):
        p=self.profile
        self.assertEqual(p['source']['pdf_sha256'],'97582a16bd54d690b27105f9b09dc48d2b5716bbae2fff2a5e74190278640fbc')
        self.assertEqual(p['source']['core_expression'],p['source']['editorial_contract']['core_expression'])
        self.assertEqual(p['unique_candidate_count'],4096)
        all_bits=[bit for field in p['input_layout'] for bit in range(field['counter_start'],field['counter_start']+field['bits'])]
        self.assertEqual(all_bits,list(range(p['input_bits'])))
        decoded={tuple(decode_candidate(lane,p).values()) for lane in range(p['unique_candidate_count'])}
        self.assertEqual(len(decoded),p['unique_candidate_count'])

    def test_analytic_and_arbitrary_prefix_counts(self):
        p=self.profile;full=p['unique_candidate_count'];counts={name:0 for name in p['analytic_full_domain_counts']}
        prefixes={0,1,31,32,33,255,256,257,full-1,full}
        prefixes.update(random.Random(984).sample(range(full),64))
        self.assertEqual(prefix_counts(p,0),counts)
        for lane in range(full):
            values=oracle(decode_candidate(lane,p));counts['total_candidates']+=1
            for name in counts:
                if name!='total_candidates':counts[name]+=values[name]
            if lane+1 in prefixes:self.assertEqual(prefix_counts(p,lane+1),counts)
        self.assertEqual(counts,p['analytic_full_domain_counts'])
        for witness_bits in (3,5):
            _,image=build_profile(witness_bits=witness_bits,source=self.source)
            profile=image.metadata['bounded_realization']
            self.assertEqual(prefix_counts(profile,profile['unique_candidate_count']),profile['analytic_full_domain_counts'])
        with self.assertRaises(ValueError):prefix_counts(p,full+1)

    def test_complete_small_domain_on_cpu(self):
        if not EXE.is_file():self.fail('CPU executable missing; pass --exe PATH')
        image=self.image;p=self.profile;lanes=p['unique_candidate_count']
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);program=folder/'bounded.tsdf';image.save(program)
            for evaluator in ('field','lowered'):
                for ticks in (1,2):
                    with self.subTest(evaluator=evaluator,ticks=ticks):
                        output=folder/'out.tsdf'
                        subprocess.run([str(EXE),'--program',str(program),'--lanes',str(lanes),'--ticks',str(ticks),
                                        '--evaluator',evaluator,'--out',str(output)],check=True,capture_output=True,text=True)
                        slots,words,epoch,state=load_state(output)
                        self.assertEqual(epoch,ticks);self.assertEqual(slots,image.header[8])
                        totals={name:0 for name in p['analytic_full_domain_counts']};totals['total_candidates']=lanes
                        for lane in range(lanes):
                            case=decode_candidate(lane,p);expected={**case,**oracle(case)}
                            for name,value in expected.items():
                                if name in image.metadata['groups']:
                                    group=image.metadata['groups'][name]
                                    group_slots=[image.metadata['state_slots'][bit] for bit in group['bits']]
                                    actual=lane_value(state,words,group_slots,lane,group.get('signed',False))
                                else:actual=lane_value(state,words,[image.metadata['state_slots'][name]],lane)
                                self.assertEqual(actual,value,(lane,name,case))
                                if name in totals:totals[name]+=actual
                        self.assertEqual(totals,p['analytic_full_domain_counts'])

    def test_default_signed_arch_and_unequal_witness_domains(self):
        if not EXE.is_file():self.fail('CPU executable missing; pass --exe PATH')
        _,image=build_profile(source=self.source)
        fixed={'previous_time':2,'current_time':5,'elapsed':3,'latest_dependency':4,'retained_before':3,'retained_after':7}
        cases=[{**fixed,'direct':a,'echo':e,'left_definition_witness':left,'right_definition_witness':right}
               for a in range(-8,8) for e in range(-8,8) for left in range(4) for right in range(2)]
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);program=folder/'bounded.tsdf';image.save(program)
            state,words=pack(image,cases);input_path=folder/'input.tsdf'
            save_state(input_path,state,image.header[8],words)
            for evaluator in ('field','lowered'):
                with self.subTest(evaluator=evaluator):
                    output=folder/'out.tsdf'
                    subprocess.run([str(EXE),'--program',str(program),'--data',str(input_path),'--evaluator',evaluator,
                                    '--out',str(output)],check=True,capture_output=True,text=True)
                    _,words,_,state=load_state(output)
                    for lane,case in enumerate(cases):
                        for name,expected in oracle(case).items():
                            group=image.metadata['groups'].get(name,{'bits':[name]})
                            slots=[image.metadata['state_slots'][bit] for bit in group['bits']]
                            self.assertEqual(lane_value(state,words,slots,lane),expected,(lane,name,case))


if __name__=='__main__':
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--exe',type=Path)
    args,remaining=parser.parse_known_args()
    if args.exe:EXE=args.exe.resolve()
    unittest.main(argv=[sys.argv[0],*remaining])
