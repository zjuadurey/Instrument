"""Finite guarded quantum/classical IR and an independent numerical oracle.

Wire 0 is the most significant tensor factor. Inputs are arbitrary density
operators, not implicitly initialized to |0>. Only explicitly supported ops
are accepted. Measurements are non-destructive and SSA bits are immutable.
"""
from copy import deepcopy
from itertools import product
import hashlib
import json
import numpy as np

GATES = {'I':1, 'X':1, 'Y':1, 'Z':1, 'H':1, 'S':1, 'SDG':1,
         'T':1, 'TDG':1, 'CX':2, 'CZ':2, 'SWAP':2}
INVERSE = {'I':'I','X':'X','Y':'Y','Z':'Z','H':'H','S':'SDG',
           'SDG':'S','T':'TDG','TDG':'T','CX':'CX','CZ':'CZ','SWAP':'SWAP'}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def stores(bits):
    return [dict(zip(bits, values)) for values in product((0, 1), repeat=len(bits))]

def enabled(op, store):
    return all(store[k] == v for k, v in op.get('guard', {}).items())

def validate(p):
    n = p['qubits']
    if not isinstance(n, int) or not 1 <= n <= 8:
        raise ValueError('Expected 1..8 qubits')
    inputs = p.get('inputs', [])
    if len(set(inputs)) != len(inputs):
        raise ValueError('Duplicate input bit')
    defined, live, ids = set(inputs), set(range(n)), set()
    for op in p['ops']:
        if not isinstance(op.get('id'), str) or op['id'] in ids:
            raise ValueError('Missing/duplicate stable operation ID')
        ids.add(op['id'])
        kind, wires = op['op'], op.get('q', [])
        if len(set(wires)) != len(wires) or not set(wires) <= live:
            raise ValueError('Aliased or non-live wire')
        guard = op.get('guard', {})
        if not set(guard) <= defined or any(v not in (0, 1) for v in guard.values()):
            raise ValueError('Undefined or non-Boolean guard')
        if kind in GATES:
            if len(wires) != GATES[kind]:
                raise ValueError('Wrong gate arity')
        elif kind in ('measure', 'reset', 'drop'):
            if len(wires) != 1 or guard:
                raise ValueError('Channel requires one wire and unconditional execution')
            if kind == 'drop':
                live.remove(wires[0])
        elif kind == 'xor':
            if guard or wires or not set(op.get('args', [])) <= defined:
                raise ValueError('Invalid classical SSA assignment')
            if op.get('constant', 0) not in (0, 1):
                raise ValueError('Invalid Boolean constant')
        elif kind == 'barrier':
            if guard:
                raise ValueError('Guarded barriers unsupported')
        else:
            raise ValueError('Unsupported operation: '+kind)
        if kind in ('measure', 'xor'):
            out = op.get('out')
            if not isinstance(out, str) or out in defined:
                raise ValueError('SSA output must be fresh')
            defined.add(out)
    if not set(p['outputs']) <= defined or len(set(p['outputs'])) != len(p['outputs']):
        raise ValueError('Invalid public observation')
    return sorted(defined), sorted(live)

def local_gate(kind):
    i = 1j
    single = {'I': [[1,0],[0,1]], 'X':[[0,1],[1,0]], 'Y':[[0,-i],[i,0]],
              'Z':[[1,0],[0,-1]], 'H':np.array([[1,1],[1,-1]])/np.sqrt(2),
              'S':[[1,0],[0,i]], 'SDG':[[1,0],[0,-i]],
              'T':[[1,0],[0,np.exp(i*np.pi/4)]], 'TDG':[[1,0],[0,np.exp(-i*np.pi/4)]]}
    if kind in single:
        return np.asarray(single[kind], dtype=complex)
    if kind == 'CX':
        return np.eye(4, dtype=complex)[[0,1,3,2]]
    if kind == 'CZ':
        return np.diag([1,1,1,-1]).astype(complex)
    if kind == 'SWAP':
        return np.eye(4, dtype=complex)[[0,2,1,3]]
    raise ValueError(kind)

def embed(local, wires, n):
    out = np.zeros((2**n, 2**n), complex)
    for col in range(2**n):
        bits = [(col >> (n-1-j)) & 1 for j in range(n)]
        k = sum(bits[q] << (len(wires)-1-j) for j,q in enumerate(wires))
        for r in range(2**len(wires)):
            target = bits.copy()
            for j,q in enumerate(wires):
                target[q] = (r >> (len(wires)-1-j)) & 1
            row = sum(v << (n-1-j) for j,v in enumerate(target))
            out[row, col] = local[r,k]
    return out

def partial_trace(rho, live, n):
    dead = [q for q in range(n) if q not in live]
    out = np.zeros((2**len(live), 2**len(live)), complex)
    for a in range(2**n):
        for b in range(2**n):
            if all(((a >> (n-1-q)) & 1) == ((b >> (n-1-q)) & 1) for q in dead):
                ai = sum(((a >> (n-1-q)) & 1) << (len(live)-1-j) for j,q in enumerate(live))
                bi = sum(((b >> (n-1-q)) & 1) << (len(live)-1-j) for j,q in enumerate(live))
                out[ai,bi] += rho[a,b]
    return out

def execute(p, rho, inputs=None, mode='inst'):
    bits, live = validate(p)
    inputs = inputs or {}
    if set(inputs) != set(p.get('inputs', [])) or any(v not in (0,1) for v in inputs.values()):
        raise ValueError('Supply all classical input bits')
    n = p['qubits']
    if rho.shape != (2**n, 2**n):
        raise ValueError('Wrong input operator shape')
    branches = [(dict(inputs), rho.copy())]
    for op in p['ops']:
        nxt = []
        for s, r in branches:
            kind = op['op']
            if not enabled(op, s):
                nxt.append((s,r)); continue
            if kind in GATES:
                u = embed(local_gate(kind), op['q'], n)
                nxt.append((s, u @ r @ u.conj().T))
            elif kind == 'measure':
                for value in (0,1):
                    proj = embed(np.diag([1-value,value]), op['q'], n)
                    nxt.append((dict(s, **{op['out']:value}), proj @ r @ proj))
            elif kind in ('reset','drop'):
                rr = np.zeros_like(r)
                for value in (0,1):
                    k = np.zeros((2,2)); k[0,value] = 1
                    k = embed(k, op['q'], n)
                    rr += k @ r @ k.conj().T
                nxt.append((s,rr))
            elif kind == 'xor':
                value = op.get('constant',0)
                for arg in op.get('args',[]): value ^= s[arg]
                nxt.append((dict(s, **{op['out']:value}),r))
            else:
                nxt.append((s,r))
        branches = nxt
    outputs = bits if mode == 'cp' else p['outputs']
    result = {}
    for s,r in branches:
        label = tuple(s[b] for b in outputs)
        value = np.trace(r) if mode == 'eff' else partial_trace(r,live,n)
        result[label] = result.get(label,0) + value
    return result

def semantic_distance(p, q, mode='eff', max_qubits=3, classical_map=None):
    """Max entrywise residual across an entire operator basis and all inputs.

    Numerical validation only, never used as an exact deletion certificate.
    classical_map maps source bit names to target names for alpha-renaming.
    """
    bp,lp = validate(p); bq,lq = validate(q)
    if mode not in ('cp','inst','eff') or p['qubits'] != q['qubits'] or p['qubits'] > max_qubits:
        raise ValueError('Unsupported oracle mode/dimension')
    ren = classical_map or {}
    if mode != 'eff' and lp != lq:
        raise ValueError('Quantum interfaces differ')
    if {ren.get(b,b) for b in p.get('inputs',[])} != set(q.get('inputs',[])):
        raise ValueError('Input interfaces differ')
    source_labels = bp if mode == 'cp' else p['outputs']
    target_labels = bq if mode == 'cp' else q['outputs']
    mapped = [ren.get(b,b) for b in source_labels]
    if set(mapped) != set(target_labels): raise ValueError('Output interfaces differ')
    order = [target_labels.index(b) for b in mapped]
    largest = 0.0
    d = 2**p['qubits']
    for s in stores(p.get('inputs',[])):
        t = {ren.get(b,b):v for b,v in s.items()}
        for a in range(d):
            for b in range(d):
                rho = np.zeros((d,d),complex); rho[a,b] = 1
                left = execute(p,rho,s,mode)
                right0 = execute(q,rho,t,mode)
                right = {tuple(k[j] for j in order):v for k,v in right0.items()}
                for key in left.keys() | right.keys():
                    largest = max(largest,float(np.max(np.abs(left.get(key,0)-right.get(key,0)))))
    return largest
