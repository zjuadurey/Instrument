"""Reproducible functional microbenchmark; not a hardware performance experiment."""
from pathlib import Path
import json,sys,platform
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from copy import deepcopy
from instrumentmt.certificates import propose,check,run_pair
from instrumentmt.ir import digest
def collect():
    p={'qubits':2,'inputs':[],'outputs':['b'],'ops':[
      {'id':'h','op':'H','q':[0]}, {'id':'s','op':'S','q':[1]},
      {'id':'m','op':'measure','q':[0],'out':'b'}, {'id':'drop','op':'drop','q':[0]},
      {'id':'x','op':'X','q':[1],'guard':{'b':1}}]}
    rows=[]
    for rule,site,args in [('cancel',0,{'gate':'H','q':[0]}),('disjoint',0,{}),('phase_z',2,{}),('rename',0,{'mapping':{'b':'r'}})]:
        q,w=propose(p,rule,site,**args);good=check(p,q,w)
        bad=deepcopy(q);bad['ops'][-1]['op']='Z';wb=deepcopy(w);wb['target']=digest(bad)
        rejected=not check(p,bad,wb)
        result=run_pair(p,q,w,lambda x:x)
        assert good and rejected and not result['discrepancy']
        rows.append({'rule':rule,'valid_accepted':int(good),'tampered_rejected':int(rejected),'operator_basis_residual':result['source_residual']})
    return rows
def plot(ax,rows):
    import numpy as np
    x=np.arange(len(rows));w=.35
    ax.bar(x-w/2,[r['valid_accepted'] for r in rows],w,label='Valid witness accepted')
    ax.bar(x+w/2,[r['tampered_rejected'] for r in rows],w,label='Tampered target rejected')
    ax.set(xticks=x,xticklabels=[r['rule'] for r in rows],ylabel='Checks passed (one pair per rule)',ylim=(0,1.35),title='Certificate acceptance and rejection')

if __name__=='__main__':
    rows=collect();out=ROOT/'results';out.mkdir(exist_ok=True)
    (out/'microbench.json').write_text(json.dumps({'benchmark':'deterministic functional microbenchmark','python':platform.python_version(),'rows':rows},indent=2)+'\n')
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(7.4,4.3),layout='constrained');plot(ax,rows)
    ax.grid(axis='y',alpha=.2);ax.legend(loc='best',fontsize=8)
    dest=ROOT/'results'/'figures';dest.mkdir(parents=True,exist_ok=True)
    fig.savefig(dest/'evaluation.png',dpi=180);fig.savefig(dest/'evaluation.svg')
    print(json.dumps(rows,indent=2))
