import argparse,json
from pathlib import Path
from .certificates import propose,check,run_pair
def main():
    ap=argparse.ArgumentParser();ap.add_argument('program');ap.add_argument('--output',default='witness.json');a=ap.parse_args()
    p=json.loads(Path(a.program).read_text());q,w=propose(p,'cancel',gate='H',q=[0])
    assert check(p,q,w)
    def injected_fault(x):
        x['ops']=[op for op in x['ops'] if op['id']!='inserted.u'];return x
    result={'identity_backend':run_pair(p,q,w,lambda x:x),'injected_fault':run_pair(p,q,w,injected_fault)}
    Path(a.output).write_text(json.dumps({'source':p,'variant':q,'witness':w,'validation':result},indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
