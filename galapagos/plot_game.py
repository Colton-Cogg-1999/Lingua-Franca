"""Optional static, exportable research plots (requires the analysis extra)."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import mean, stdev


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('--ablations', type=Path)
    args = parser.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    data = [json.loads(line) for line in (args.run / 'metrics.jsonl').read_text().splitlines()]
    data = [item for item in data if item['overall']['count']]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), layout='constrained')
    for group, metric, label in [('overall', 'first_success', 'All encounters: first attempt'),
                                  ('cross_island', 'first_success', 'Cross-island: first attempt'),
                                  ('overall', 'final_success', 'All encounters: after repair')]:
        axes[0].plot([d['round'] for d in data], [d[group][metric] for d in data], label=label)
    axes[0].set(title='Communication succeeds before and after repair', xlabel='Round', ylabel='Successful fraction', ylim=(0, 1.03))
    axes[0].legend(fontsize=8, loc='lower right')
    axes[1].plot([d['round'] for d in data], [d['mean_lexical_distance'] for d in data], color='#9b4d19')
    axes[1].set(title='Community vocabularies change through exposure', xlabel='Round', ylabel='Mean lexical total variation distance', ylim=(0, 1.03))
    fig.suptitle('Galapagos — synthetic communication game, one seeded run', fontsize=14)
    fig.savefig(args.run / 'results.png', dpi=180)
    fig.savefig(args.run / 'results.svg')
    plt.close(fig)
    if args.ablations:
        groups = defaultdict(list)
        for line in (args.ablations / 'trajectories.jsonl').read_text().splitlines():
            row = json.loads(line)
            value = row['cross_island']['first_success']
            if value is not None:
                groups[(row['scenario'], row['round'])].append(value)
        fig, ax = plt.subplots(figsize=(8, 4.8), layout='constrained')
        for scenario in sorted({key[0] for key in groups}):
            rounds = sorted(r for name, r in groups if name == scenario)
            centers = [mean(groups[(scenario, r)]) for r in rounds]
            spreads = [stdev(groups[(scenario, r)]) if len(groups[(scenario, r)]) > 1 else 0 for r in rounds]
            ax.plot(rounds, centers, label=scenario.replace('_', ' '), linestyle='--' if scenario == 'no_repair' else '-')
            ax.fill_between(rounds, [max(0, m-s) for m, s in zip(centers, spreads)],
                            [min(1, m+s) for m, s in zip(centers, spreads)], alpha=0.12)
        ax.set(title='Does repair cause lasting cross-community acquisition?', xlabel='Round',
               ylabel='Cross-island first-attempt success', ylim=(-0.02, 1.02))
        ax.legend(title='Mean ± one sample SD across seeds')
        fig.savefig(args.ablations / 'comparison.png', dpi=180)
        fig.savefig(args.ablations / 'comparison.svg')


if __name__ == '__main__':
    main()
