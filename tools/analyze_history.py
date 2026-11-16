"""Extract bounded phase/diagnostic snapshots and compare completed historical runs."""
import json
from pathlib import Path
import argparse


def extract(root):
    results={}
    for name in ['historical-main','historical-continuous','historical-related']:
        run=root/name
        plan=json.loads((run/'plan.json').read_text())
        audit=json.loads((run/'completion-audit.json').read_text())
        assert audit['passed'] and audit['rounds']==plan['rounds']
        rounds=sorted({0,plan['rounds'],*[p['through'] for p in plan['phases']],*range(250,plan['rounds']+1,250)})
        records=[]
        for n in rounds:
            s=json.loads((run/'rounds'/f'{n:06d}'/'summary.json').read_text())
            row={'round':n,'illustrative_year':-100+n/10,'overall_distance':s['mean_lexical_distance'],
                 'core_distance':s['within_group_lexical_distance']['romance_analogue'],
                 'external_distance':s['within_group_lexical_distance']['external_comparisons'],
                 'between_distance':s['between_group_lexical_distance']['romance_analogue__external_comparisons']}
            m=s.get('held_out_comprehension',{}).get('source_by_listener')
            if m:
                pairs={'core':[(i,j) for i in range(6) for j in range(6) if i!=j],
                       'core_to_external':[(i,j) for i in range(6) for j in range(6,10)],
                       'external_to_core':[(i,j) for i in range(6,10) for j in range(6)]}
                row['comprehension']={k:sum(m[i][j] for i,j in v)/len(v) for k,v in pairs.items()}
            records.append(row)
        results[name]={'run_id':audit['run_id'],'audit':audit,'snapshots':records,
                       'final_regions':s['islands'],'final_comprehension':m}
    return results


def plot(results,out,root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(2,2,figsize=(14,10),layout='constrained')
    colors=['#1769aa','#d55e00','#228833']
    names=['Historical fragmentation','Sustained-contact control','Shared-ancestry control']
    for (key,run),color,label in zip(results.items(),colors,names):
        rows=run['snapshots'];x=[r['illustrative_year'] for r in rows]
        axs[0,0].plot(x,[r['core_distance'] for r in rows],label=label,color=color,lw=2)
        axs[0,1].plot(x,[r['between_distance'] for r in rows],label=label,color=color,lw=2)
    axs[0,0].set(title='Related core: initial differences mostly disappear',ylabel='Within-core lexical distance',ylim=(0,.1))
    axs[0,1].set(title='Core–external differences persist until broad contact',ylabel='Between-group lexical distance',ylim=(0,1.04))
    axs[0,0].legend(fontsize=8)
    rows=results['historical-main']['snapshots'];x=[r['illustrative_year'] for r in rows]
    for key,label,color in [('core_to_external','External listeners understanding core speech','#1769aa'),('external_to_core','Core listeners understanding external speech','#d55e00')]:
        axs[1,0].plot(x,[100*r['comprehension'][key] for r in rows],label=label,color=color,lw=2)
    axs[1,0].set(title='Comprehension is strongly directional',ylabel='Held-out task success (%)',ylim=(0,103))
    axs[1,0].legend(fontsize=8)
    main=results['historical-main'];regions=main['final_regions']
    initial=json.loads((root/'historical-main/plan.json').read_text())
    from galapagos.game import OBJECTS
    ancestral=dict(zip(OBJECTS,initial['initialization']['lexicons'][0]))
    shares=[sum(a['frequencies'][c].get(w,0) for c,w in ancestral.items())/len(ancestral) for a in regions]
    axs[1,1].bar(range(10),[100*v for v in shares],color=['#1769aa']*6+['#d55e00']*4)
    axs[1,1].set(title='Final production favors the core ancestral vocabulary',ylabel='Mean ancestral-form production probability (%)',ylim=(0,103),xticks=range(10),xticklabels=['Iberia','Gaul','Italia','Balkans','Sardinia','Adriatic','Ext A','Ext B','Ext C','Ext D'])
    axs[1,1].tick_params(axis='x',rotation=45)
    for ax in [axs[0,0],axs[0,1],axs[1,0]]:
        for year in [450,1000,1800,1990]:ax.axvline(year,color='gray',lw=.6,alpha=.5)
        ax.set(xlabel='Illustrative calendar year (not historically calibrated)',xlim=(-100,2025))
        ax.grid(axis='y',alpha=.2)
    fig.suptitle('Historical contact study: what the model actually did\nOne seed per treatment; lines show stored diagnostics, not uncertainty intervals',fontsize=14)
    fig.savefig(out/'comparison.png',dpi=160)
    fig.savefig(out/'comparison.svg')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path('runtime/local-data/experiment'))
    parser.add_argument('--output',type=Path,default=Path('docs/results/historical-comparison'))
    args=parser.parse_args()
    data=extract(args.root);args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'metrics.json').write_text(json.dumps({'notes':['One seed per treatment.','Distances are total variation over word-production distributions, not percent words changed.','Comprehension uses 160 trials per ordered region pair; group means weight pairs equally.','No causal ablations of learning mechanics were run.'],'runs':data},indent=2)+'\n')
    plot(data,args.output,args.root)
    print(args.output/'comparison.png')
