"""Lingua Franca: synthetic trade communities and contextual-bandit communication.

No LLM, broker, or Kubernetes required. SQLite commits events, metrics and state
atomically. The model describes artificial agents, not human populations.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import sqlite3
import time

GOODS=('grain','water','timber','ore','cloth','medicine')
STRATEGIES=('conventional','accommodate','clarify','innovate')
BASE=('nara','poma','taku','sima','pane','sala')
VERSION='lingua-franca-1'


def rng_for(seed,*parts):
    return random.Random(int.from_bytes(hashlib.sha256(json.dumps([seed,*parts]).encode()).digest(),'big'))


def initialize(seed,population):
    rng=rng_for(seed,'initial')
    agents=[]
    for region in range(6):
        for j in range(population):
            words=BASE if region<3 else tuple(f'{chr(107+region)}{w}' for w in BASE)
            agents.append(dict(id=len(agents),region=region,openness=(.15,.5,.85)[region%3],
                inventory=[2.0]*6,tastes=[rng.uniform(.8,1.2) for _ in GOODS],
                lexicon=[{w:8.0,f'{w}{chr(97+region)}':1.0} for w in words],
                experience={},q={ctx:[0.0]*4 for ctx in ('local','remote')},
                counts={ctx:[0]*4 for ctx in ('local','remote')},trust={},age=0))
    return dict(round=0,agents=agents)


def schedule(round_number,total):
    fraction=round_number/total
    if fraction<=.2:return 'connected',.12,[[j for j in range(6) if j!=i] for i in range(6)]
    if fraction<=.65:return 'fragmented',.01,[[1],[0],[],[4],[3],[]]
    if fraction<=.9:return 'trade_routes',.08,[[1],[0,2],[1,3],[2,4],[3,5],[4]]
    if fraction<=.98:return 'mass_contact',.20,[[j for j in range(6) if j!=i] for i in range(6)]
    return 'dense_contact',.45,[[j for j in range(6) if j!=i] for i in range(6)]


def choose(rng,weights):
    keys=sorted(weights)
    return rng.choices(keys,[weights[k] for k in keys])[0]


def interpret(agent,word,available,rng):
    evidence={g:agent['lexicon'][g].get(word,0) for g in available}
    evidence={g:v for g,v in evidence.items() if v>0}
    return choose(rng,evidence) if evidence else None


def utility(agent):
    return sum(t*math.log1p(v) for t,v in zip(agent['tastes'],agent['inventory']))


def step(state,seed,total,condition,encounters=2):
    n=state['round']+1;agents=state['agents'];rng=rng_for(seed,n,'world')
    phase,contact,edges=schedule(n,total)
    before=sum(sum(a['inventory']) for a in agents)
    produced=consumed=discarded=0.0
    drought=(n//600)%6
    for a in agents:
        a['age']+=1
        # Productive specializations are diverse within each community, regionally biased.
        specialty=a['region'] if a['id']%3 else (a['region']+a['id']//6+1)%6
        production=.22 if specialty==drought else .65
        a['inventory'][specialty]+=production;produced+=production
        for g in range(6):
            use=min(a['inventory'][g],.075*a['tastes'][g]);a['inventory'][g]-=use;consumed+=use
            excess=max(0,a['inventory'][g]-20);a['inventory'][g]-=excess;discarded+=excess
        if n%20==0:
            for lex in a['lexicon']:
                strongest=max(lex,key=lex.get)
                for w in list(lex):
                    lex[w]*=.98
                    if lex[w]<.08 and w!=strongest:del lex[w]
                lex[strongest]=max(.08,lex[strongest])
    groups=[[a for a in agents if a['region']==i] for i in range(6)]
    events=[];metrics=Counter();rewards=0.0;costs=0.0;gains=0.0
    order=list(range(len(agents)));rng.shuffle(order)
    for buyer_id in order:
        buyer=agents[buyer_id]
        for attempt in range(encounters):
            r=rng_for(seed,n,buyer_id,attempt,'encounter')
            remote=r.random()<contact and bool(edges[buyer['region']])
            region=r.choice(edges[buyer['region']]) if remote else buyer['region']
            pool=[a for a in groups[region] if a['id']!=buyer_id]
            seller=r.choices(pool,[max(.1,buyer['trust'].get(str(a['id']),.5)) for a in pool])[0]
            ctx='remote' if remote else 'local'
            if condition=='fixed' or r.random()<.12:strategy=r.randrange(4)
            else:
                q=buyer['q'][ctx];best=max(q);strategy=r.choice([i for i,v in enumerate(q) if abs(v-best)<1e-12])
            action=STRATEGIES[strategy]
            openness=.5 if condition=='uniform' else buyer['openness']
            seller_open=.5 if condition=='uniform' else seller['openness']
            target=r.choices(range(6),[buyer['tastes'][g]/(1+buyer['inventory'][g])**2 for g in range(6)])[0]
            offers=[g for g in range(6) if g!=target and buyer['inventory'][g]>=1]
            offer=min(offers,key=lambda g:buyer['tastes'][g]/(1+buyer['inventory'][g])) if offers else None
            word=choose(r,buyer['lexicon'][target]);cost=.01
            if action=='accommodate':
                learned=buyer['experience'].get(str(seller['region']),{}).get(str(target))
                if learned:word=learned
                cost+=.025*(1-openness)
            if action=='innovate':word=''.join(r.choice(('la','mi','ku','se','po','ra','ni','tu')) for _ in range(3));cost+=.04*(1-openness)
            available=[g for g in range(6) if seller['inventory'][g]>=1]
            understood=interpret(seller,word,available,r)
            first=understood==target
            gesture=action=='clarify'
            repair=not first and not gesture and r.random()<.1+.4*seller_open
            if gesture or repair:
                understood=target if target in available else None
                cost+=.06
            known=seller['lexicon'][target].get(word,0)>0
            grounded=understood==target
            if grounded:
                lex=seller['lexicon'][target];lex[word]=lex.get(word,0)+(.2+.8*seller_open)
                # Store only observable successful speech, never a peer's private dictionary.
                seller['experience'].setdefault(str(buyer['region']),{})[str(target)]=word
                if action=='innovate':buyer['lexicon'][target][word]=buyer['lexicon'][target].get(word,0)+.3
            gain_b=gain_s=0.0;traded=False
            if grounded and offer is not None and offer!=target:
                b0,s0=utility(buyer),utility(seller)
                buyer['inventory'][offer]-=1;seller['inventory'][offer]+=1
                seller['inventory'][target]-=1;buyer['inventory'][target]+=1
                gain_b,gain_s=utility(buyer)-b0,utility(seller)-s0
                if gain_b>0 and gain_s>0:traded=True
                else:
                    buyer['inventory'][offer]+=1;seller['inventory'][offer]-=1
                    seller['inventory'][target]+=1;buyer['inventory'][target]-=1
                    gain_b=gain_s=0.0
            reward=gain_b-cost
            if condition!='fixed':buyer['q'][ctx][strategy]+=.08*(reward-buyer['q'][ctx][strategy])
            buyer['counts'][ctx][strategy]+=1
            key=str(seller['id']);old=buyer['trust'].get(key,.5)
            buyer['trust'][key]=max(.05,min(.95,old+.05*((1 if traded else 0)-old)))
            metrics[action]+=1;metrics['encounters']+=1;metrics['trades']+=traded;metrics['first_success']+=first
            metrics['repairs']+=repair;metrics['remote']+=remote;metrics['new_form_learned']+=grounded and not known
            rewards+=reward;costs+=cost;gains+=gain_b+gain_s
            events.append((buyer_id,seller['id'],buyer['region'],seller['region'],action,target,offer,word,int(first),int(repair or gesture),int(grounded),int(traded),reward,gain_b,gain_s))
    # Cultural succession: retain physical goods, acquire language from three local tutors.
    for a in agents:
        r=rng_for(seed,n,a['id'],'succession')
        if r.random()<.0015:
            tutors=r.choices(groups[a['region']],k=3)
            lexicon=[{} for _ in GOODS]
            for tutor in tutors:
                for g in range(6):
                    word=choose(r,tutor['lexicon'][g]);lexicon[g][word]=lexicon[g].get(word,0)+1
            a.update(lexicon=lexicon,experience={},q={c:[0.0]*4 for c in ('local','remote')},counts={c:[0]*4 for c in ('local','remote')},trust={},age=0)
            a['openness']=min(.95,max(.05,sum(t['openness'] for t in tutors)/3+r.gauss(0,.03)))
            metrics['successions']+=1
    after=sum(sum(a['inventory']) for a in agents)
    residual=after-before-produced+consumed+discarded
    if abs(residual)>1e-7 or any(v< -1e-9 for a in agents for v in a['inventory']):raise ValueError('resource conservation failure')
    count=metrics['encounters'];summary=dict(round=n,phase=phase,**metrics,mean_reward=rewards/count,
        mean_cost=costs/count,total_trade_gain=gains,inventory=after,produced=produced,consumed=consumed,discarded=discarded,
        balance_residual=residual,mean_utility=sum(utility(a) for a in agents)/len(agents),
        shortage=sum(v<.5 for a in agents for v in a['inventory'])/(6*len(agents)),
        region_utility=[sum(utility(a) for a in group)/len(group) for group in groups],
        region_openness=[sum(a['openness'] for a in group)/len(group) for group in groups])
    if n%200==0 or n==total:
        frequencies=[]
        for group in groups:
            region=[]
            for g in range(6):
                f=Counter()
                for a in group:
                    mass=sum(a['lexicon'][g].values())
                    for w,v in a['lexicon'][g].items():f[w]+=v/mass/len(group)
                region.append(dict(f))
            frequencies.append(region)
        distances=[]
        for i in range(6):
            for j in range(i+1,6):distances.append(sum(sum(abs(frequencies[i][g].get(w,0)-frequencies[j][g].get(w,0)) for w in frequencies[i][g].keys()|frequencies[j][g].keys())/2 for g in range(6))/6)
        summary['lexical_distance']=sum(distances)/len(distances)
        summary['vocabulary']=frequencies
    state['round']=n
    return events,summary


class Ledger:
    def __init__(self,path,config):
        self.db=sqlite3.connect(path);self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS metadata(config TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS checkpoint(id INTEGER PRIMARY KEY CHECK(id=1),round INTEGER,state TEXT);
        CREATE TABLE IF NOT EXISTS summaries(round INTEGER PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(round INTEGER,seq INTEGER,buyer INTEGER,seller INTEGER,source_region INTEGER,target_region INTEGER,strategy TEXT,requested INTEGER,offered INTEGER,word TEXT,first_success INTEGER,repair_used INTEGER,grounded INTEGER,traded INTEGER,reward REAL,buyer_gain REAL,seller_gain REAL,PRIMARY KEY(round,seq)) WITHOUT ROWID;''')
        encoded=json.dumps(config,sort_keys=True)
        row=self.db.execute('SELECT config FROM metadata').fetchone()
        if row and row[0]!=encoded:raise ValueError('ledger configuration/source mismatch')
        if not row:
            with self.db:self.db.execute('INSERT INTO metadata VALUES (?)',(encoded,))
    def restore(self):
        row=self.db.execute('SELECT state FROM checkpoint WHERE id=1').fetchone()
        return json.loads(row[0]) if row else None
    def commit(self,state,events,summary):
        n=state['round']
        with self.db:
            self.db.executemany('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',[(n,i,*event) for i,event in enumerate(events)])
            self.db.execute('INSERT INTO summaries VALUES (?,?)',(n,json.dumps(summary,separators=(',',':'))))
            self.db.execute('INSERT OR REPLACE INTO checkpoint VALUES (1,?,?)',(n,json.dumps(state,separators=(',',':'))))
    def close(self):
        self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)');self.db.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--rounds',type=int,default=24000);parser.add_argument('--population',type=int,default=20);parser.add_argument('--seed',type=int,default=476);parser.add_argument('--condition',choices=['adaptive','fixed','uniform'],default='adaptive');parser.add_argument('--stop-after',type=int)
    args=parser.parse_args()
    if args.rounds<1 or args.population<2:parser.error('positive rounds and at least two agents per region required')
    args.output.mkdir(parents=True,exist_ok=True)
    config=dict(version=VERSION,seed=args.seed,rounds=args.rounds,population=args.population,condition=args.condition,source=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    ledger=Ledger(args.output/'ledger.sqlite',config);state=ledger.restore() or initialize(args.seed,args.population)
    import shutil
    try:
        while state['round']<args.rounds:
            if shutil.disk_usage(args.output).free<20*1024**3:raise RuntimeError('free space below 20 GiB')
            events,summary=step(state,args.seed,args.rounds,args.condition);ledger.commit(state,events,summary)
            if state['round']%100==0 or state['round']==args.rounds:
                status=dict(round=state['round'],total=args.rounds,state='complete' if state['round']==args.rounds else 'running',condition=args.condition,seed=args.seed,updated=time.time())
                temp=args.output/'status.pending';temp.write_text(json.dumps(status));temp.replace(args.output/'status.json');print(json.dumps(status),flush=True)
            if args.stop_after and state['round']>=args.stop_after:break
    finally:ledger.close()

if __name__=='__main__':main()
