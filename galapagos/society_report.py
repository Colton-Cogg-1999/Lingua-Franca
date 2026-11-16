"""Audit and report completed Lingua Franca experiments, including null results."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
import statistics

from .society import STRATEGIES, schedule


def read_run(directory):
    db = sqlite3.connect(f'file:{directory / "ledger.sqlite"}?mode=ro', uri=True)
    config = json.loads(db.execute('SELECT config FROM metadata').fetchone()[0])
    rows = [json.loads(row[0]) for row in db.execute('SELECT payload FROM summaries ORDER BY round')]
    expected = config['rounds'] * config['population'] * 6 * 2
    count, lo, hi, trades, rewards, gains = db.execute('SELECT count(*),min(round),max(round),sum(traded),sum(reward),sum(buyer_gain+seller_gain) FROM events').fetchone()
    bad_events = db.execute('''SELECT count(*) FROM events WHERE buyer=seller OR
        (traded=1 AND (buyer_gain<=0 OR seller_gain<=0 OR grounded!=1 OR requested=offered)) OR
        (traded=0 AND (abs(buyer_gain)>1e-10 OR abs(seller_gain)>1e-10))''').fetchone()[0]
    topology_violations = 0
    # Independent inspection of the actual logged pairs, grouped to keep memory small.
    for n, source, target in db.execute('SELECT round,source_region,target_region FROM events WHERE source_region!=target_region GROUP BY round,source_region,target_region'):
        if target not in schedule(n, config['rounds'])[2][source]:
            topology_violations += 1
    checkpoint = db.execute('SELECT round,state FROM checkpoint WHERE id=1').fetchone()
    final_state = json.loads(checkpoint[1])
    actual_inventory = sum(sum(a['inventory']) for a in final_state['agents'])
    expected_inventory = config['population'] * 6 * 12 + sum(r['produced']-r['consumed']-r['discarded'] for r in rows)
    checks = dict(sqlite_integrity=db.execute('PRAGMA quick_check').fetchone()[0]=='ok',
        complete_rounds=[r['round'] for r in rows]==list(range(1, config['rounds']+1)),
        event_count=count==expected, checkpoint=checkpoint[0]==config['rounds'],
        per_round_counts=all(n==config['population']*12 for (n,) in db.execute('SELECT count(*) FROM events GROUP BY round')),
        valid_events=bad_events==0, topology=topology_violations==0,
        resource_balance=abs(actual_inventory-expected_inventory)<1e-6,
        summary_trades=trades==sum(r['trades'] for r in rows),
        summary_rewards=abs(rewards-sum(r['mean_reward']*r['encounters'] for r in rows))<1e-5,
        summary_gains=abs(gains-sum(r['total_trade_gain'] for r in rows))<1e-5)
    db.close()
    phases = {}
    for phase in dict.fromkeys(r['phase'] for r in rows):
        subset = [r for r in rows if r['phase']==phase]
        encounters = sum(r['encounters'] for r in subset)
        phases[phase] = dict(rounds=len(subset), encounters=encounters,
            trade_rate=sum(r['trades'] for r in subset)/encounters,
            first_success=sum(r['first_success'] for r in subset)/encounters,
            mean_reward=sum(r['mean_reward']*r['encounters'] for r in subset)/encounters,
            shortage=statistics.mean(r['shortage'] for r in subset),
            utility=statistics.mean(r['mean_utility'] for r in subset),
            remote_rate=sum(r['remote'] for r in subset)/encounters,
            strategies={a:sum(r.get(a,0) for r in subset)/encounters for a in STRATEGIES})
    lex = [r for r in rows if 'lexical_distance' in r]
    result = dict(config=config,audit=checks,events=count,trades=trades,
        trade_rate=trades/count,mean_reward=rewards/count,trade_gain=gains,
        mean_shortage=statistics.mean(r['shortage'] for r in rows),
        final_lexical_distance=lex[-1]['lexical_distance'] if lex else None,
        final_region_utility=rows[-1]['region_utility'],final_region_openness=rows[-1]['region_openness'],
        successions=sum(r.get('successions',0) for r in rows),
        learned_novel_form_events=sum(r.get('new_form_learned',0) for r in rows),
        resource_balance_error=actual_inventory-expected_inventory,phases=phases)
    # Aggregate trajectories without publishing the large event databases or private checkpoints.
    trajectory=[]
    for start in range(0,len(rows),200):
        block=rows[start:start+200]; n=sum(r['encounters'] for r in block)
        trajectory.append(dict(round=block[-1]['round'],trade_rate=sum(r['trades'] for r in block)/n,
            mean_reward=statistics.mean(r['mean_reward'] for r in block),
            shortage=statistics.mean(r['shortage'] for r in block),
            utility=statistics.mean(r['mean_utility'] for r in block),
            lexical_distance=next((r['lexical_distance'] for r in reversed(block) if 'lexical_distance' in r),None),
            conventional=sum(r.get('conventional',0) for r in block)/n))
    dominant=[]
    for region in range(6):
        words=[]
        for good in range(6):
            counts=Counter()
            for agent in final_state['agents']:
                if agent['region']==region:
                    lexicon=agent['lexicon'][good];mass=sum(lexicon.values())
                    for word,value in lexicon.items():counts[word]+=value/mass
            words.append(counts.most_common(1)[0][0])
        dominant.append(words)
    result['dominant_words']=dominant
    result['trajectory']=trajectory
    return result


def generate(root, output):
    manifest=json.loads((root/'manifest.json').read_text())
    results=[read_run(root/spec['name']) for spec in manifest['runs']]
    for spec, result in zip(manifest['runs'], results):
        config=result['config']
        result['audit']['study_configuration']=all(config[k]==manifest[k] for k in ('rounds','population','source')) and all(config[k]==spec[k] for k in ('seed','condition'))
    output.mkdir(parents=True,exist_ok=True)
    (output/'metrics.json').write_text(json.dumps(results,indent=2)+'\n')
    groups=defaultdict(list)
    for r in results:groups[r['config']['condition']].append(r)
    paired={}
    for condition in ('fixed','uniform'):
        if 'adaptive' in groups and condition in groups:
            peers={r['config']['seed']:r for r in groups[condition]}
            paired[condition]={key:[r[key]-peers[r['config']['seed']][key] for r in groups['adaptive']]
                for key in ('trade_rate','mean_reward','mean_shortage','final_lexical_distance')}
    passed=all(all(r['audit'].values()) for r in results)
    lines=['# Lingua Franca: trade, learning, and cultural change', '',
        f'Completed {len(results)} runs, {sum(r["config"]["rounds"] for r in results):,} rounds, and {sum(r["events"] for r in results):,} recorded encounters.',
        '',f'**Integrity audit: {"PASS" if passed else "FAIL — interpret these results only after resolving the failed checks"}.**', '',
        'This is a controlled experiment in an artificial society. It does not establish facts about people, historical language change, or the fall of Rome. The historical analogy supplies a contact schedule, not an empirical calibration.', '',
        '## Design and mechanisms', '',
        'Six communities each contain 20 agent slots in the full study. Regions 0–2 initially share a common lexicon with regional variants; regions 3–5 have distinct lexicons. There are six concrete goods: grain, water, timber, ore, cloth, and medicine. Agents produce specialized goods, consume all six, and prefer a diverse inventory through a weighted logarithmic utility function. A rotating drought reduces production of one good every 600 rounds. Storage above 20 units per good is discarded before encounters.', '',
        'Each agent attempts two trades per round. It samples a desired good with weight taste/(1+inventory)^2, offers its least valuable available alternative, and requests the desired good using a word from its own lexicon. A seller interprets that word using its own lexicon and available stock. A barter exchanges one unit each and happens only when both agents gain inventory utility. Goods and willingness to accept are observable; no agent can inspect another agent’s private vocabulary. Trade acceptance evaluates inventory utility before the buyer’s communication cost; a completed trade can therefore still earn a negative learning reward.', '',
        'Four strategies compete: conventional speech, accommodation using previously heard successful regional words, explicit clarification through pointing, and a newly coined word. A successful grounded encounter strengthens the word in the listener’s lexicon. Unknown words can receive probabilistic pointing-based repair. New words are not automatically rewarded. Words decay, and each agent slot has a 0.0015 chance per round of cultural succession: a successor samples three local tutors, inherits physical resources, and resets strategy learning and social memory. Tutors can include the previous occupant. This is cultural turnover, not a demographic or survival model.', '',
        'Learning is an epsilon-greedy contextual bandit (epsilon 0.12, learning rate 0.08), with separate local and remote action values. Reward is the buyer’s actual inventory utility gain minus communication effort. Conventional cost is 0.01; accommodation adds 0.025×(1−openness); innovation adds 0.04×(1−openness); clarification or repair adds 0.06. Learning optimizes the agent’s immediate reward, not a collective linguistic goal. Successful trades also update partner preference, which affects later partner sampling.', '',
        'Initial cultural openness is 0.15, 0.50, or 0.85 in each vocabulary group. It affects the effort of accommodation and innovation, listener uptake, and the probability of repair. Successors inherit tutor-average openness plus bounded noise. This bundles several mechanisms into one synthetic attitude variable; it is not a validated measurement of culture.', '',
        '## Timeline', '',
        '| Phase | Share of run | Full-study rounds | Remote encounter probability | Allowed links |',
        '|---|---:|---:|---:|---|',
        '| Connected | 20% | 1–4,800 | 12% | All pairs |',
        '| Fragmented | 45% | 4,801–15,600 | 1% where connected | 0↔1 and 3↔4; 2 and 5 completely isolated |',
        '| Trade routes | 25% | 15,601–21,600 | 8% | Neighboring regions along a chain |',
        '| Mass contact | 8% | 21,601–23,520 | 20% | All pairs |',
        '| Dense contact | 2% | 23,521–24,000 | 45% | All pairs |', '',
        'Round counts scale proportionally for smoke tests. Rounds have no mapping to historical years. Isolation is enforced by the simulator’s partner graph, not network namespaces. The audit checks actual event pairs against that graph.', '',
        '## Controls and reproducibility', '',
        'The full study uses seeds 476, 911, and 2026 for each of three conditions: **adaptive** (learned strategies and heterogeneous culture), **fixed** (uniform random strategies and heterogeneous culture), and **uniform** (learned strategies with effective openness fixed at 0.50). Production, initial conditions, succession draws, and the contact schedule are seeded. Conditions share exogenous seeds, but behavioral decisions consume different random draws and create different trajectories; they are not identical encounter-by-encounter counterfactuals. The fixed baseline still learns vocabulary and partner preferences. It disables only strategy-value learning.', '',
        'The seeds were chosen before the full run. Three repetitions support exploratory comparisons, not strong statistical generalizations. All complete runs appear below, including unfavorable outcomes. Differences between adaptive and fixed estimate the effect of strategy learning relative to this particular random policy; differences between adaptive and uniform bundle attitude level, variation, and its modeled consequences.', '',
        '## Per-run results', '',
        '| Condition | Seed | Trades / encounters | Mean reward | Mean shortage | Final lexical distance |',
        '|---|---:|---:|---:|---:|---:|']
    for r in results:
        lines.append(f'| {r["config"]["condition"]} | {r["config"]["seed"]} | {r["trade_rate"]:.3%} | {r["mean_reward"]:.5f} | {r["mean_shortage"]:.3%} | {r["final_lexical_distance"]:.5f} |')
    lines += ['', 'Shortage is the fraction of agent–good inventory cells below 0.5 units; it is not mortality. Lexical distance is the mean pairwise total-variation distance between normalized regional word distributions, averaged across six goods (0 identical, 1 disjoint). It measures form distributions, not mutual intelligibility. First-pass success below additionally requires seller stock and therefore mixes comprehension with resource availability.', '', '## Matched comparisons and unwanted outcomes', '']
    for baseline,metrics in paired.items():
        lines += [f'### Adaptive minus {baseline}', '', '| Metric | Mean difference | Per-seed differences |', '|---|---:|---|']
        for key, values in metrics.items():
            lines.append(f'| {key} | {statistics.mean(values):+.6f} | '+', '.join(f'{v:+.6f}' for v in values)+' |')
        values=metrics['mean_reward'];positive=sum(v>0 for v in values)
        lines += ['', f'Adaptive reward was higher in {positive}/{len(values)} matched seeds. Mean reward difference was {statistics.mean(values):+.6f}. '+('This comparison did not show a consistent reward advantage.' if positive<len(values) else 'The advantage was consistent across these seeds, within this model only.'), '']
    lines += ['Learning can raise net reward simply by reducing costly clarification rather than improving trade. Compare reward, trade rate, and shortages together. Cultural differences can also disappear through the tutor mechanism, and linguistic similarity need not imply an economically healthier society. No outcome was a pass/fail criterion except implementation integrity.', '', '## Phase-level results', '', '| Condition | Phase | Trade rate | First-pass success | Reward | Shortage | Remote fraction |', '|---|---|---:|---:|---:|---:|---:|']
    for condition, group in groups.items():
        for phase in group[0]['phases']:
            p=[r['phases'][phase] for r in group]
            means=[statistics.mean(x[k] for x in p) for k in ('trade_rate','first_success','mean_reward','shortage','remote_rate')]
            lines.append(f'| {condition} | {phase} | {means[0]:.3%} | {means[1]:.3%} | {means[2]:.5f} | {means[3]:.3%} | {means[4]:.3%} |')
    lines += ['', '## What changed across the contact timeline?', '']
    for condition,group in groups.items():
        early=statistics.mean(r['phases']['connected']['trade_rate'] for r in group)
        isolated=statistics.mean(r['phases']['fragmented']['trade_rate'] for r in group)
        late=statistics.mean(r['phases']['dense_contact']['trade_rate'] for r in group)
        shortages=statistics.mean(r['phases']['dense_contact']['shortage']-r['phases']['fragmented']['shortage'] for r in group)
        first_distance=statistics.mean(next(p['lexical_distance'] for p in r['trajectory'] if p['lexical_distance'] is not None) for r in group)
        final_distance=statistics.mean(r['final_lexical_distance'] for r in group)
        lines += [f'- **{condition}:** trade success averaged {early:.2%} during initial contact, {isolated:.2%} during fragmentation, and {late:.2%} during dense contact. Late-minus-fragmented shortage was {shortages*100:+.2f} percentage points. Mean lexical distance changed from the first recorded snapshot ({first_distance:.4f}) to {final_distance:.4f} at the end.']
    lines += ['', 'Phase differences are descriptive: time, learning, drought, and succession change alongside connectivity. There is no continuous-contact control in this study, so these comparisons alone cannot isolate the causal effect of fragmentation or reconnection.', '']
    lines += ['', '## Learned strategy use', '', '| Condition | Phase | Conventional | Accommodation | Clarification | Innovation |', '|---|---|---:|---:|---:|---:|']
    for condition,group in groups.items():
        for phase in ('connected','dense_contact'):
            shares=[statistics.mean(r['phases'][phase]['strategies'][a] for r in group) for a in STRATEGIES]
            lines.append(f'| {condition} | {phase} | '+' | '.join(f'{s:.2%}' for s in shares)+' |')
    lines += ['', '## End-state regional differences', '', '| Condition / seed | Regional utility (0 through 5) | Regional inherited openness |', '|---|---|---|']
    for r in results:
        lines.append(f'| {r["config"]["condition"]} / {r["config"]["seed"]} | '+', '.join(f'{v:.3f}' for v in r['final_region_utility'])+' | '+', '.join(f'{v:.3f}' for v in r['final_region_openness'])+' |')
    lines += ['', '## Final vocabulary examples', '',
        'These are the highest-weight regional words for grain, water, timber, ore, cloth, and medicine. They are arbitrary labels, not natural-language utterances. Full word distributions remain in the local summaries.', '',
        '| Condition / seed | Region | Grain | Water | Timber | Ore | Cloth | Medicine |',
        '|---|---:|---|---|---|---|---|---|']
    for r in results:
        for region,words in enumerate(r['dominant_words']):
            lines.append(f'| {r["config"]["condition"]} / {r["config"]["seed"]} | {region} | '+' | '.join(words)+' |')
    lines += ['', 'The uniform treatment uses effective openness 0.50 throughout; its inherited openness above is recorded state but has no behavioral effect. Regional utility is a final snapshot; trajectories and phase averages are more informative about sustained welfare.', '', '## Integrity and limitations', '',
        'Each SQLite transaction commits a round’s encounters, summary, and checkpoint together. The report independently counts event rows, checks per-round counts and checkpoint completion, verifies resource balance from production/consumption/discard flows, checks logged trades and rewards against summaries, inspects forbidden contact pairs, and runs SQLite quick_check. Audit details and the model source hash are in metrics.json.', '']
    for r in results:
        failures=[k for k,v in r['audit'].items() if not v]
        lines.append(f'- {r["config"]["condition"]}/{r["config"]["seed"]}: {"PASS" if not failures else "FAIL: "+", ".join(failures)}; {r["events"]:,} events; resource residual {r["resource_balance_error"]:.3g}.')
    lines += ['', 'There are no LLMs, grammar, identities, political institutions, migration, prices, credit, long-term planning, or observed human data in this version. Trade is one-for-one barter with a shared nonlinguistic representation of goods and pointing. Trust measures trading success, not human social trust. Single-word labels and a finite innovation space can converge by construction or accidental form collision. The language, economy, and openness rules were designed together and may strongly determine outcomes. A causal claim is therefore limited to interventions inside this program.', '',
        'Further tests should independently vary production geography, repair availability, innovation cost, tutor count, strategy exploration, and each attitude mechanism. Add an always-conventional policy and no-trade control before claiming reinforcement is necessary. Calibrate against empirical data before making a sociolinguistic or historical claim.', '',
        '## Artifacts and reproduction', '',
        'metrics.json contains every condition/seed summary, phase statistics, audit checks, and 200-round trajectories. trajectories.png shows individual seeds, not just a selected run. Raw SQLite ledgers remain on the experiment machine and are excluded from Git because of their size. Re-run with the command in the project README. The simulator source hash is recorded per run; a changed model cannot silently resume an old ledger.', '']
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes=plt.subplots(3,2,figsize=(13,12),constrained_layout=True)
        colors={'adaptive':'#187bcd','fixed':'#d56b20','uniform':'#6f42a8'}
        for ax,key,label in zip(axes.flat,('trade_rate','mean_reward','shortage','utility','lexical_distance','conventional'),('Trade success fraction','Mean net reward','Shortage fraction','Mean inventory utility','Regional lexical distance','Conventional strategy fraction')):
            for r in results:
                points=[p for p in r['trajectory'] if p[key] is not None]
                ax.plot([p['round'] for p in points],[p[key] for p in points],color=colors[r['config']['condition']],alpha=.65,lw=1,marker='.' if len(points)==1 else None,label=r['config']['condition'])
            for fraction in (.2,.65,.9,.98):ax.axvline(fraction*results[0]['config']['rounds'],color='gray',ls=':',lw=.7)
            ax.set(xlabel='Round',ylabel=label);ax.grid(alpha=.15)
        handles,labels=axes.flat[0].get_legend_handles_labels();unique=dict(zip(labels,handles))
        fig.legend(unique.values(),unique.keys(),loc='outside upper center',ncol=3)
        fig.suptitle('Lingua Franca — individual seed trajectories',y=1.04)
        fig.savefig(output/'trajectories.png',dpi=150,bbox_inches='tight');plt.close(fig)
        lines += ['![Individual-seed trajectories](trajectories.png)', '']
    except ImportError:
        lines += ['Plot unavailable: install the analysis extra to render trajectories.', '']
    (output/'report.md').write_text('\n'.join(lines))
    return passed


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raise SystemExit(0 if generate(a.root,a.output) else 1)

if __name__=='__main__':main()
