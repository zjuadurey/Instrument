"""Typed rewrite witnesses, strict replay checking, and fixed-family testing."""
from copy import deepcopy
from dataclasses import dataclass
import math
from .ir import GATES, INVERSE, digest, validate, semantic_distance

def _rename(op,mapping):
    op=deepcopy(op)
    if 'out' in op: op['out']=mapping.get(op['out'],op['out'])
    if 'args' in op: op['args']=[mapping.get(k,k) for k in op['args']]
    if 'guard' in op: op['guard']={mapping.get(k,k):v for k,v in op['guard'].items()}
    return op

def propose(p,rule,site=0,mode='cp',**params):
    """Untrusted generator. Every output must pass check() before use."""
    validate(p); q=deepcopy(p); footprint=[]
    if rule=='cancel':
        name=params.get('gate','H'); wires=params.get('q',[0])
        ids=params.get('ids',['inserted.u','inserted.udag'])
        q['ops'][site:site]=[{'id':ids[0],'op':name,'q':wires},
                             {'id':ids[1],'op':INVERSE[name],'q':wires}]
        params={'gate':name,'q':wires,'ids':ids}; footprint=ids
    elif rule=='disjoint':
        q['ops'][site],q['ops'][site+1]=q['ops'][site+1],q['ops'][site]
        footprint=[p['ops'][site]['id'],p['ops'][site+1]['id']]
    elif rule=='phase_z':
        name=params.get('gate','T'); ident=params.get('id','inserted.phase')
        q['ops'].insert(site,{'id':ident,'op':name,'q':p['ops'][site]['q'].copy()})
        params={'gate':name,'id':ident}; footprint=[ident,p['ops'][site]['id']]
    elif rule=='rename':
        mapping=params['mapping']
        q['ops']=[_rename(op,mapping) for op in p['ops']]
        q['inputs']=[mapping.get(k,k) for k in p.get('inputs',[])]
        q['outputs']=[mapping.get(k,k) for k in p['outputs']]
        footprint=[a['id'] for a,b in zip(p['ops'],q['ops']) if a!=b]
    else: raise ValueError('Unknown mutation')
    return q,{'source':digest(p),'target':digest(q),'rule':rule,'site':site,
              'mode':mode,'params':params,'footprint':footprint}

def check(p,q,w,terminal=True):
    """Whitelist replay; no call to generator, optimizer, or numerical oracle."""
    try:
        source_bits,_=validate(p); validate(q)
        if w['source']!=digest(p) or w['target']!=digest(q): return False
        mode=w['mode']
        if mode not in ('cp','inst','eff') or (mode!='cp' and not terminal): return False
        if p['qubits']!=q['qubits']: return False
        site=w['site']; rule=w['rule']; args=w['params']; expected=deepcopy(p)
        if not isinstance(site,int) or not 0<=site<=len(p['ops']): return False
        if rule=='cancel':
            g=args['gate']; wires=args['q']; ids=args['ids']
            if g not in GATES or len(ids)!=2 or ids[0]==ids[1]: return False
            if set(ids)&{op['id'] for op in p['ops']}: return False
            new=[{'id':ids[0],'op':g,'q':wires},{'id':ids[1],'op':INVERSE[g],'q':wires}]
            expected['ops'][site:site]=new; footprint=ids
        elif rule=='disjoint':
            a,b=p['ops'][site:site+2]
            if a['op'] not in GATES or b['op'] not in GATES: return False
            if set(a['q'])&set(b['q']): return False
            # Gates define no classical state; both guards already dominate both uses.
            expected['ops'][site:site+2]=[deepcopy(b),deepcopy(a)]
            footprint=[a['id'],b['id']]
        elif rule=='phase_z':
            op=p['ops'][site]
            if op['op']!='measure' or args['gate'] not in ('Z','S','SDG','T','TDG'): return False
            wire=op['q'][0]
            later=[x for x in p['ops'][site+1:] if wire in x.get('q',[])]
            if len(later)!=1 or later[0]['op']!='drop': return False
            new={'id':args['id'],'op':args['gate'],'q':[wire]}
            expected['ops'].insert(site,new); footprint=[args['id'],op['id']]
        elif rule=='rename':
            mapping=args['mapping']
            if not set(mapping)<=set(source_bits) or any(not isinstance(v,str) for v in mapping.values()): return False
            images=[mapping.get(b,b) for b in source_bits]
            if len(set(images))!=len(source_bits): return False
            # Independently rebuild all definitions, uses, guards, and interfaces.
            for op in expected['ops']:
                for field in ('out',):
                    if field in op: op[field]=mapping.get(op[field],op[field])
                if 'args' in op: op['args']=[mapping.get(b,b) for b in op['args']]
                if 'guard' in op: op['guard']={mapping.get(b,b):v for b,v in op['guard'].items()}
            expected['inputs']=[mapping.get(b,b) for b in p.get('inputs',[])]
            expected['outputs']=[mapping.get(b,b) for b in p['outputs']]
            footprint=[a['id'] for a,b in zip(p['ops'],expected['ops']) if a!=b]
        else: return False
        return expected==q and footprint==w['footprint']
    except (KeyError,IndexError,ValueError,TypeError): return False

def run_pair(p,q,w,compiler,terminal=True):
    if not check(p,q,w,terminal): raise ValueError('Rejected metamorphic relation')
    ren=w['params'].get('mapping',{}) if w['rule']=='rename' else None
    source_error=semantic_distance(p,q,w['mode'],classical_map=ren)
    left,right=compiler(deepcopy(p)),compiler(deepcopy(q))
    compiled_error=semantic_distance(left,right,w['mode'],classical_map=ren)
    return {'accepted':True,'source_residual':source_error,'compiled_residual':compiled_error,
            'discrepancy':compiled_error>1e-10,'mode':w['mode']}

@dataclass
class FixedFamily:
    comparisons: int
    categories: tuple
    shots: int
    alpha: float = 0.05
    used: int = 0

    def __post_init__(self):
        if self.comparisons<1 or self.shots<1 or not 0<self.alpha<1 or not self.categories:
            raise ValueError('Invalid predeclared sampling plan')
        if len(set(self.categories))!=len(self.categories): raise ValueError('Duplicate categories')

    @property
    def threshold(self):
        return 2*math.sqrt(math.log(4*self.comparisons*len(self.categories)/self.alpha)/(2*self.shots))

    def compare(self,left,right):
        if self.used>=self.comparisons: raise ValueError('Predeclared comparison budget exhausted')
        for counts in (left,right):
            if set(counts)!=set(self.categories) or any(type(x) is not int or x<0 for x in counts.values()):
                raise ValueError('Counts must cover the predeclared alphabet')
            if sum(counts.values())!=self.shots: raise ValueError('Incorrect fixed sample size')
        self.used+=1
        delta=max(abs(left[k]-right[k])/self.shots for k in self.categories)
        return {'max_difference':delta,'threshold':self.threshold,'flagged':delta>self.threshold,
                'comparison':self.used,'interpretation':'No flag does not establish equivalence.'}
