"""Small bit-clause builder for explicit finite interpretations and test circuits."""
from __future__ import annotations
from .compiler import compile_definition

class Builder:
    def __init__(self,name):
        self.spec={'name':name,'state':{},'rules':{'NOT':0x55,'AND':0x88,'OR':0xEE,'XOR':0x66,'EQ':0x99,'MUX':0xCA,'SUM3':0x96,'MAJ3':0xE8},'expressions':{},'next':{},'quotes':{},'groups':{},'outputs':[]}
        self.counter=0
    def bit(self,name,seed=0):
        if name in self.spec['state']:raise ValueError('duplicate state')
        self.spec['state'][name]=seed;return name
    def bits(self,name,width,*,signed=False,counter_start=None,seed=0):
        bits=[self.bit(f'{name}.{i}',{'counter_bit':counter_start+i} if counter_start is not None else seed) for i in range(width)]
        self.spec['groups'][name]={'bits':bits,'signed':signed};return bits
    def gate(self,rule,*args,name=None):
        if name is None:name=f'$v{self.counter}';self.counter+=1
        self.spec['expressions'][name]={'rule':rule,'args':list(args)};return name
    def inverse(self,a):return self.gate('NOT',a)
    def reduce(self,rule,items,identity):
        result=identity
        for item in items:result=self.gate(rule,result,item)
        return result
    def eq(self,a,b):
        if len(a)!=len(b):raise ValueError('equal widths needed')
        return self.reduce('AND',[self.gate('EQ',x,y) for x,y in zip(a,b)],'ONE')
    def less(self,a,b):
        if len(a)!=len(b):raise ValueError('equal widths needed')
        result='ZERO'
        for x,y in zip(a,b):
            lower=self.gate('AND',self.inverse(x),y)
            result=self.gate('OR',lower,self.gate('AND',self.gate('EQ',x,y),result))
        return result
    def add(self,a,b,carry='ZERO'):
        if len(a)!=len(b):raise ValueError('equal widths needed')
        result=[]
        for x,y in zip(a,b):
            result.append(self.gate('SUM3',x,y,carry));carry=self.gate('MAJ3',x,y,carry)
        return result,carry
    def sub(self,a,b):return self.add(a,[self.inverse(x) for x in b],'ONE')[0]
    def mux_bits(self,a,b,c):
        if len(a)!=len(b):raise ValueError('equal widths needed')
        return [self.gate('MUX',x,y,c) for x,y in zip(a,b)]
    def negate(self,a):return self.add([self.inverse(x) for x in a],['ZERO']*len(a),'ONE')[0]
    def output(self,name,expression):
        self.bit(name);self.spec['next'][name]=expression;self.spec['outputs'].append(name);return name
    def output_group(self,name,expressions,*,signed=False):
        bits=self.bits(name,len(expressions),signed=signed)
        self.spec['next'].update(zip(bits,expressions));self.spec['outputs'].append(name);return bits
    def compile(self,recycle=True):return compile_definition(self.spec,recycle)
