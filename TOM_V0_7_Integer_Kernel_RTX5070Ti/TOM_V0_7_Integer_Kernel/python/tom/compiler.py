"""Compile finite TOM-SDF clause encodings, not a spatial/ontological graph.

Kernel microcode, operator coefficients, expressions and their self addresses
share one packed-bit atlas. Explicit temporal state references close recurrence.
The source's native pinion/jitter dynamics remain uninterpreted declarations.
"""
from __future__ import annotations
from dataclasses import dataclass
import copy
import heapq
import json
from pathlib import Path
import struct

FULL=(1<<32)-1
MAGIC=0x374D4F54
KERNEL,TIME,CONST,STATE,RULE,DYNAMIC,EXPR,QUOTE,NATIVE=range(1,10)
VALUE={CONST,STATE,EXPR,QUOTE}
MICRO=[11,0,1,8,12,2,3,8,13,4,5,8,14,6,7,8,15,11,12,9,16,13,14,9,17,15,16,10]
NATIVE_NAMES=('TOM','phi','jitter','inverse_log_phi','ArchU','causality','entropy','InverseOccam','sheet','double_UU','Klein','Matryoshka')

@dataclass
class Image:
    header:list[int]
    words:list[int]
    metadata:dict
    def record(self,ident:int):return self.words[ident*16:ident*16+16]
    def save(self,path:Path):
        path.write_bytes(struct.pack('<16I',*self.header)+struct.pack(f'<{len(self.words)}I',*self.words))
        path.with_suffix('.map.json').write_text(json.dumps(self.metadata,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    @classmethod
    def load(cls,path:Path):
        raw=path.read_bytes()
        if len(raw)<64:raise ValueError('truncated image')
        h=list(struct.unpack_from('<16I',raw))
        if h[0]!=MAGIC or h[1]!=1 or len(raw)!=64+4*h[12]:raise ValueError('image size/version mismatch')
        meta_path=path.with_suffix('.map.json')
        meta=json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}
        return cls(h,list(struct.unpack_from(f'<{h[12]}I',raw,64)),meta)

def compile_definition(source:dict,recycle:bool=True)->Image:
    source=copy.deepcopy(source)
    states=source.get('state',{})
    if not states:raise ValueError('at least one state field is required')
    constants={'ZERO':0,'ONE':1,**source.get('constants',{})}
    rules=source.get('rules',{})
    expressions=source.get('expressions',{})
    quotes=source.get('quotes',{})
    records=[];names={}
    def add(name,kind):
        if name in names:raise ValueError('duplicate declaration: '+name)
        ident=len(records);names[name]=ident;record=[kind]+[0]*15;record[14]=ident;record[15]=FULL;records.append(record);return ident
    def ref(name):
        if name not in names:raise ValueError('undeclared field: '+name)
        return names[name]
    kid=add('KERNEL',KERNEL);tid=add('T',TIME);names['A']=tid
    for name in NATIVE_NAMES:add(name,NATIVE)
    for name in constants:add(name,CONST)
    for name in states:add(name,STATE)
    for name,item in rules.items():add(name,DYNAMIC if isinstance(item,dict) else RULE)
    for name in expressions:add(name,EXPR)
    for name in quotes:add(name,QUOTE)
    for name,v in constants.items():
        if type(v) not in (int,bool) or v not in (0,1):raise ValueError('constant must be a bit')
        records[ref(name)][1]=int(v)
    for slot,(name,initial) in enumerate(states.items()):
        r=records[ref(name)];r[1]=slot
        if type(initial) in (int,bool) and initial in (0,1):r[2]=int(initial)
        elif isinstance(initial,dict) and set(initial)=={'counter_bit'}:
            bit=initial['counter_bit']
            if type(bit) is not int or not 0<=bit<64:raise ValueError('counter bit 0..63')
            r[2:4]=[2,bit]
        elif isinstance(initial,dict) and set(initial)=={'hash'}:
            value=initial['hash']
            if type(value) is not int or not 0<=value<=FULL:raise ValueError('hash seed uint32')
            r[2:4]=[3,value]
        else:raise ValueError('state seed needs 0,1,counter_bit,or hash')
    for name,item in rules.items():
        r=records[ref(name)]
        if isinstance(item,dict):
            rows=item.get('rows')
            if not isinstance(rows,list) or len(rows)!=8:raise ValueError('dynamic rule needs eight field names')
            r[1:9]=[ref(x) for x in rows]
        else:
            if type(item) is not int or not 0<=item<256:raise ValueError('truth table must be 8 bits')
            r[1]=item
    for name,item in expressions.items():
        args=item.get('args',[])
        if len(args)>3:raise ValueError('at most three expression operands')
        operator=ref(item['rule'])
        if records[operator][0] not in (RULE,DYNAMIC):raise ValueError('native declaration has no executable truth interpretation: '+item['rule'])
        records[ref(name)][1:5]=[operator]+[ref(x) for x in args]+[ref('ZERO')]*(3-len(args))
    binding=[]
    updates=source.get('next',{})
    if any(x not in states for x in updates):raise ValueError('next target is not a state field')
    for name in states:
        expr=ref(updates.get(name,name))
        if records[expr][0] not in VALUE:raise ValueError('next binding must refer to a value field')
        binding.extend((ref(name),expr))
    def dependencies(ident):
        r=records[ident]
        if r[0]!=EXPR:return []
        result=r[2:5];rule=records[r[1]]
        if rule[0]==DYNAMIC:result=result+rule[1:9]
        return list(dict.fromkeys(result))
    order=[];colour={}
    def visit(ident):
        # Keep the recursive DFS's dependency order without consuming Python's
        # call stack: valid long chains must not depend on the recursion limit.
        pending=[(ident,False)]
        while pending:
            current,finished=pending.pop()
            if finished:
                colour[current]=2;order.append(current)
                continue
            if records[current][0] not in VALUE:raise ValueError('not an evaluable field')
            if colour.get(current)==1:raise ValueError('instantaneous self-reference; use a State / T-boundary')
            if colour.get(current)==2:continue
            colour[current]=1
            pending.append((current,True))
            pending.extend((d,False) for d in reversed(dependencies(current)))
    for root in binding[1::2]:visit(root)
    last={ident:i for i,ident in enumerate(order)}
    for i,ident in enumerate(order):
        for d in dependencies(ident):last[d]=max(last[d],i)
    for ident in binding[1::2]:last[ident]=len(order)
    free=[];allocated=0
    for i,ident in enumerate(order):
        slot=heapq.heappop(free) if recycle and free else allocated
        if slot==allocated:allocated+=1
        records[ident][15]=slot
        if recycle:
            for d in dependencies(ident):
                if last[d]==i:heapq.heappush(free,records[d][15])
    micro_offset=len(records)*16
    records[kid][1:5]=[micro_offset,7,0xCA,17]
    plan_offset=micro_offset+28;bind_offset=plan_offset+len(order)
    records[tid][1:4]=[bind_offset,len(states),tid]
    for name,item in quotes.items():
        if 'object' in item:
            b=item['bit']
            if type(b) is not int or not 0<=b<512:raise ValueError('quoted record bit outside 0..511')
            address=ref(item['object'])*512+b
        elif 'kernel_bit' in item:
            b=item['kernel_bit']
            if type(b) is not int or not 0<=b<28*32:raise ValueError('kernel tape bit outside 0..895')
            address=micro_offset*32+b
        else:raise ValueError('quote needs object+bit or kernel_bit')
        records[ref(name)][1]=address
    words=[x for r in records for x in r]+MICRO+order+binding
    words += [0]*((-len(words))%16)
    if len(words)>1<<27:raise ValueError('image too large for selected ABI')
    header=[MAGIC,1,16,len(records),plan_offset,len(order),bind_offset,len(states),len(states),allocated,kid,tid,len(words),0,0,0]
    groups=source.get('groups',{})
    for name,g in groups.items():
        if not g.get('bits') or any(x not in states for x in g['bits']):raise ValueError('group must reference state fields: '+name)
    meta={'name':source.get('name','TOM finite interpretation'),'version':'0.7-K1','author':'Tom Klootwijk','identifier':'NL200678942','date_supplied':'10-07-1990',
          'names':names,'state_slots':{name:i for i,name in enumerate(states)},'groups':groups,'outputs':source.get('outputs',list(states)),
          'objects':len(records),'scheduled_values':len(order),'scratch_slots':allocated,'unrecycled_slots':len(order),
          'kernel_microcode_words':28,'kernel_table_word':kid*16+3,'native_roles_uninterpreted':list(NATIVE_NAMES),
          'scope':'finite validation representation; not intrinsic TOM nodes, dimensions, metric or physical evolution',
          'source_definition':source}
    return Image(header,words,meta)

def mix(x):
    x=((x^(x>>16))*0x7feb352d)&FULL;x=((x^(x>>15))*0x846ca68b)&FULL;return x^(x>>16)

def seed_words(p:Image,words:int,first_word:int=0):
    result=[0]*(p.header[8]*words)
    for ident in range(p.header[3]):
        r=p.record(ident)
        if r[0]!=STATE:continue
        slot,mode,param=r[1:4]
        for w in range(words):
            i=first_word+w
            value=0 if mode==0 else FULL if mode==1 else mix((i&FULL)^(i>>32)^param) if mode==3 else sum(((((i*32+b)>>param)&1)<<b) for b in range(32))
            result[slot*words+w]=value
    return result

def truth_by_minterms(a,b,c,table):
    result=0
    for row in range(8):
        result |= (a if row&1 else a^FULL)&(b if row&2 else b^FULL)&(c if row&4 else c^FULL)&table[row]
    return result

def reference_tick(p:Image,state:list[int],words:int):
    # Independent values keyed by definition id, with minterm evaluation.
    # For canonical kernel only: tests for changed microcode use literal_reference.
    vals={}
    for ident in p.words[p.header[4]:p.header[4]+p.header[5]]:
        r=p.record(ident);k=r[0]
        if k==CONST:v=[FULL if r[1] else 0]*words
        elif k==STATE:v=state[r[1]*words:(r[1]+1)*words]
        elif k==QUOTE:v=[FULL if (p.words[r[1]>>5]>>(r[1]&31))&1 else 0]*words
        elif k==EXPR:
            a,b,c=[vals[i] for i in r[2:5]];rule=p.record(r[1])
            table=([vals[i] for i in rule[1:9]] if rule[0]==DYNAMIC else [[FULL if (rule[1]>>i)&1 else 0]*words for i in range(8)])
            v=[truth_by_minterms(a[w],b[w],c[w],[x[w] for x in table]) for w in range(words)]
        else:raise ValueError('invalid value kind')
        vals[ident]=v
    result=[0]*len(state)
    for i in range(p.header[7]):
        dst,src=p.words[p.header[6]+2*i:p.header[6]+2*i+2];slot=p.record(dst)[1]
        result[slot*words:(slot+1)*words]=vals[src]
    return result

def save_state(path:Path,state:list[int],slots:int,words:int,epoch:int=0):
    if len(state)!=slots*words or not 0<=epoch<1<<64:raise ValueError('state/epoch extent')
    path.write_bytes(b'TOM7BIT\0'+struct.pack('<2IQ',slots,words,epoch)+struct.pack(f'<{len(state)}I',*state))

def load_state(path:Path):
    raw=path.read_bytes()
    if len(raw)<24 or raw[:8]!=b'TOM7BIT\0':raise ValueError('not a packed TOM state')
    slots,words,epoch=struct.unpack_from('<2IQ',raw,8)
    if len(raw)!=24+slots*words*4:raise ValueError('state length')
    return slots,words,epoch,list(struct.unpack_from(f'<{slots*words}I',raw,24))

def lane_value(state:list[int],words:int,slots:list[int],lane:int,signed=False):
    value=sum(((state[slot*words+lane//32]>>(lane%32))&1)<<i for i,slot in enumerate(slots))
    return value-(1<<len(slots)) if signed and value&(1<<(len(slots)-1)) else value
