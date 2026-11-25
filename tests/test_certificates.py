from copy import deepcopy
from pathlib import Path
import json,math
import pytest
from instrumentmt.certificates import *
from instrumentmt.ir import semantic_distance,digest
P=json.loads((Path(__file__).resolve().parents[1]/'examples/program.json').read_text())

@pytest.mark.parametrize('rule,site,args',[('cancel',0,{'gate':'T','q':[1]}),('disjoint',0,{}),('phase_z',2,{}),('rename',0,{'mapping':{'b':'result'}})])
def test_all_rules_full_operator_basis(rule,site,args):
    q,w=propose(P,rule,site,**args);assert check(P,q,w)
    assert semantic_distance(P,q,'cp',classical_map=args.get('mapping'))<1e-10

def test_changed_unlisted_instruction_rejected():
    q,w=propose(P,'cancel');q['ops'][-1]['op']='Z';w['target']=digest(q)
    assert not check(P,q,w)

def test_missing_rename_use_rejected():
    q,w=propose(P,'rename',mapping={'b':'new'})
    q['ops'][-1]['guard']={'b':1};w['target']=digest(q)
    assert not check(P,q,w)

def test_wrong_mode_and_context():
    q,w=propose(P,'cancel',mode='eff');assert check(P,q,w)
    assert not check(P,q,w,terminal=False)
    w['mode']='unitary';assert not check(P,q,w)

def test_live_wire_phase_rejected():
    p=deepcopy(P);p['ops']=[op for op in p['ops'] if op['id']!='drop']
    q,w=propose(p,'phase_z',2);assert not check(p,q,w)

def test_effect_agreement_is_not_cp_agreement():
    p={'qubits':1,'inputs':[],'outputs':[],'ops':[]}
    q={**p,'ops':[{'id':'x','op':'X','q':[0]}]}
    assert semantic_distance(p,q,'eff')==0
    assert semantic_distance(p,q,'cp')==1

def test_injected_fault_is_detected():
    q,w=propose(P,'cancel',gate='H',q=[0])
    def faulty(p):p['ops']=[op for op in p['ops'] if op['id']!='inserted.u'];return p
    assert not run_pair(P,q,w,lambda p:p)['discrepancy']
    assert run_pair(P,q,w,faulty)['discrepancy']

def test_fixed_family_budget_and_threshold():
    f=FixedFamily(2,(0,1),10000)
    assert f.threshold==2*math.sqrt(math.log(4*2*2/.05)/(2*10000))
    assert not f.compare({0:5000,1:5000},{0:5000,1:5000})['flagged']
    assert f.compare({0:10000,1:0},{0:0,1:10000})['flagged']
    with pytest.raises(ValueError):f.compare({0:5000,1:5000},{0:5000,1:5000})

def test_wrong_shot_count_rejected():
    with pytest.raises(ValueError):FixedFamily(1,(0,1),10).compare({0:5,1:4},{0:5,1:5})

def test_unobservable_fault_is_not_a_spurious_alarm():
    # X before H and a terminal Z measurement changes only the discarded phase.
    q,w=propose(P,'cancel',gate='X',q=[0])
    def faulty(p):p['ops']=[op for op in p['ops'] if op['id']!='inserted.u'];return p
    assert not run_pair(P,q,w,faulty)['discrepancy']
