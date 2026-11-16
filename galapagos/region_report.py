"""Read committed region summaries without interacting with or teaching agents."""
import argparse
from itertools import cycle
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('run',type=Path)
    args=parser.parse_args()
    plan=json.loads((args.run/'plan.json').read_text())
    folders=sorted((args.run/'rounds').glob('[0-9]*'))
    summaries=[json.loads((folder/'summary.json').read_text()) for folder in folders]
    if not summaries:
        parser.error('no committed rounds')
    latest=summaries[-1]
    population=json.loads((folders[-1]/'checkpoint.json').read_text())['state']['speakers']
    lines=['# Roman-collapse-inspired regional experiment','',
           f"Latest committed round: **{latest['round']} / {plan['rounds']}**.",
           f"Phase: **{latest.get('geographic_phase','initialization')}**. Population: **{latest['population']}**.",'',
           'These are synthetic linguistic populations, not reconstructions of historical languages.','',
           '| Region | Speakers | Most frequent form for water | Preferred construction |',
           '| --- | ---: | --- | --- |']
    for i,name in enumerate(plan['regions']):
        people=[s for s in population if s['island']==i]
        words={}; orders={}
        for speaker in people:
            for key,target in [('lexicon',words),('constructions',orders)]:
                evidence=speaker[key]['water'] if key=='lexicon' else speaker[key]
                total=sum(evidence.values())
                for word,value in evidence.items(): target[word]=target.get(word,0)+value/total
        lines.append(f"| {name} | {len(people)} | {max(words,key=words.get) if words else 'empty'} | {max(orders,key=orders.get) if orders else 'empty'} |")
    lines.extend(['','## Observations','',
                  f"Mean lexical distance: {latest['mean_lexical_distance']:.4f} (0 = identical production distributions, 1 = disjoint).",'',
                  'Held-out comprehension is tested centrally without creating agent contact or learning. It is not an interaction across a closed network boundary.','',
                  '![Population and divergence](regional-results.png)'])
    (args.run/'report.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    axes[0].plot([s['round'] for s in summaries],[s['mean_lexical_distance'] for s in summaries],color='#8e5c2e')
    for group in plan.get('measurement_groups', {}):
        axes[0].plot([s['round'] for s in summaries], [s.get('within_group_lexical_distance', {}).get(group) for s in summaries], label=group.replace('_', ' '))
    colors=['#d6e9f5','#f7dfd5','#d9ecd3']
    start=0
    for phase,color in zip(plan['phases'],cycle(colors)):
        end=min(phase['through'],latest['round'])
        if end>start:
            axes[0].axvspan(start,end,alpha=.45,color=color,label=phase['name'].replace('_',' '))
        start=phase['through']
    axes[0].set(xlabel='Round',ylabel='Mean lexical total variation distance',ylim=(0,1),title='Lexical divergence (overall and groups)')
    axes[0].legend(fontsize=8)
    audits=[s['held_out_comprehension'] for s in summaries if 'held_out_comprehension' in s]
    if audits:
        audit=audits[-1]
        data=[[float('nan') if value is None else value for value in row] for row in audit['source_by_listener']]
        im=axes[1].imshow(data,vmin=0,vmax=1,cmap='viridis')
        axes[1].set(xticks=range(len(plan['regions'])),yticks=range(len(plan['regions'])),
                    xticklabels=plan['regions'],yticklabels=plan['regions'],
                    xlabel='Listener region',ylabel='Source region',title=f"Held-out comprehension, round {audit['round']}")
        axes[1].tick_params(axis='x',rotation=45)
        figure.colorbar(im,ax=axes[1],label='Successful fraction')
    figure.suptitle(f"Galapagos: {latest['round']} / {plan['rounds']} rounds committed")
    figure.savefig(args.run/'regional-results.png',dpi=160)
    figure.savefig(args.run/'regional-results.svg')
    print(args.run/'report.md')


if __name__=='__main__':
    main()
