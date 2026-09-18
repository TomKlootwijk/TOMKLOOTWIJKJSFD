#!/usr/bin/env python3
"""Regression checks for compilation order, deep clauses, and builder widths."""
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from tom.builder import Builder
from tom.compiler import FULL,compile_definition,reference_tick,seed_words


class CompilerTests(unittest.TestCase):
    def test_existing_images_are_byte_identical(self):
        # Quotation can expose record addresses and scratch slots, so preserving
        # the exact existing compiled image matters in addition to gate results.
        for path in sorted((ROOT/'examples').glob('*.map.json')):
            with self.subTest(image=path.name):
                metadata=json.loads(path.read_text(encoding='utf-8'))
                image=compile_definition(metadata['source_definition'])
                packed=struct.pack('<16I',*image.header)+struct.pack(f'<{len(image.words)}I',*image.words)
                self.assertEqual(packed,path.with_name(path.name.removesuffix('.map.json')+'.tsdf').read_bytes())

    def test_deep_chain_and_shared_dependencies(self):
        b=Builder('deep chain')
        value=b.bit('x',1)
        for _ in range(4097):
            value=b.inverse(value)
        # Both branches share the same long dependency chain; it must be emitted
        # once, with no false cycle and the same snapshot semantics in each mode.
        b.spec['next']['x']=b.gate('XOR',value,b.inverse(value))
        for recycle in (True,False):
            with self.subTest(recycle=recycle):
                image=b.compile(recycle)
                schedule=image.words[image.header[4]:image.header[4]+image.header[5]]
                self.assertEqual(len(schedule),len(set(schedule)))
                actual=reference_tick(image,seed_words(image,2),2)
                self.assertEqual(actual,[FULL,FULL])

    def test_deep_cycle_is_diagnosed(self):
        b=Builder('deep cycle')
        b.bit('x')
        for i in range(4097):
            b.gate('NOT',f'node{(i+1)%4097}',name=f'node{i}')
        b.spec['next']['x']='node0'
        with self.assertRaisesRegex(ValueError,'instantaneous self-reference'):
            b.compile()

    def test_dynamic_rule_cycle_is_diagnosed(self):
        b=Builder('dynamic cycle')
        b.bit('x')
        b.spec['rules']['D']={'rows':['loop']+['ZERO']*7}
        b.gate('D','x',name='loop')
        b.spec['next']['x']='loop'
        with self.assertRaisesRegex(ValueError,'instantaneous self-reference'):
            b.compile()

    def test_mux_rejects_mismatched_widths_before_emitting_gates(self):
        b=Builder('mismatched mux')
        with self.assertRaisesRegex(ValueError,'equal widths needed'):
            b.mux_bits(['ONE','ZERO'],['ZERO'],'ONE')
        self.assertEqual(b.spec['expressions'],{})


if __name__=='__main__':
    unittest.main()
