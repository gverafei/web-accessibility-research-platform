"""Reproduce SoftwareX Table 7 and Figure 5 from the Example 2 package."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
from statistics import mean
import zipfile


def summarize(package):
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read('remediation.json'))
    groups = defaultdict(list)
    seen = set()
    for entry in manifest['runs']:
        pair = entry['paired_measurement']
        run = entry['data']
        if run['id'] in seen:
            raise ValueError('Duplicate remediation run')
        seen.add(run['id'])
        groups[pair['cohort']].append(pair)
    labels = ['Global top 500', 'Very high popularity', 'High popularity',
              'Medium popularity', 'Popularity tail']
    if set(groups) != set(labels) or any(len(group) != 25 for group in groups.values()):
        raise ValueError('Expected five groups of 25 pairs in SoftwareX Example 2')
    rows = []
    for label in labels:
        pairs = groups[label]
        row = {'label': label}
        for field, role in [('baseline', 'original'), ('candidate', 'candidate')]:
            row[field] = {'n': len(pairs),
                          'axe': mean(p[role]['axe_wcag_violations'] for p in pairs),
                          'lighthouse': mean(p[role]['lighthouse_score'] for p in pairs)}
        row['axe_improvement'] = mean(p['original']['axe_wcag_violations'] -
                                      p['candidate']['axe_wcag_violations'] for p in pairs)
        row['lighthouse_improvement'] = mean(p['candidate']['lighthouse_score'] -
                                             p['original']['lighthouse_score'] for p in pairs)
        row['targets_met'] = sum(p['candidate']['axe_wcag_violations'] <= 3 and
                                 p['candidate']['lighthouse_score'] >= 94 for p in pairs)
        rows.append(row)
    return rows


def render_figure(rows, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap, to_rgba
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,
        'axes.spines.right':False,'axes.edgecolor':'#bcc8d5','axes.labelcolor':'#243449',
        'xtick.color':'#425266','ytick.color':'#425266','savefig.dpi':1000})
    BLUE, GREEN = '#245d95', '#2a844c'
    LABELS = ['Top 500', 'Very high', 'High', 'Medium', 'Tail']
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), layout='constrained')
    x = np.arange(5)
    for axis, field, label in [(axes[0, 0], 'axe', 'Mean WCAG Axe instances/page'),
                                (axes[0, 1], 'lighthouse', 'Mean Lighthouse accessibility score')]:
        for offset, condition, name, color in [(-.18, 'baseline', 'Original', BLUE), (.18, 'candidate', 'Candidate', GREEN)]:
            values = [r[condition][field] for r in rows]
            container = axis.bar(x + offset, values, width=.35,
                     facecolor=to_rgba(color, .24), edgecolor=color, linewidth=1.5, label=name)
            axis.bar_label(container, labels=[f'{value:.2f}' for value in values],
                           padding=3, fontsize=9, rotation=60, color='#243449')
        axis.set_xticks(x, LABELS); axis.set_ylabel(label)
        axis.set_axisbelow(True); axis.grid(axis='y', color='#d9e0e8', linewidth=.7)
        axis.legend(frameon=False, fontsize=10, loc='lower left',
                    bbox_to_anchor=(.14, 1.04), ncol=2, borderaxespad=0)
    axes[0, 0].set_ylim(0, max(r[c]['axe'] for r in rows for c in ('baseline', 'candidate')) * 1.22)
    axes[0, 1].set_ylim(0, 120)
    axis = axes[1, 0]
    raw = np.array([[r['axe_improvement'], r['lighthouse_improvement']] for r in rows])
    # Each column has its own units, as in the report matrix; colors are scaled
    # per metric and the exact, unscaled values are printed in every cell.
    normalized = raw / np.maximum(np.abs(raw).max(axis=0), 1)
    change_colors = LinearSegmentedColormap.from_list(
        'paired_change', ['#d9a278', '#ffffff', '#80add5'])
    axis.imshow(normalized, cmap=change_colors, vmin=-1, vmax=1, aspect='auto')
    axis.set_yticks(x, LABELS)
    axis.set_xticks([0, 1], ['Axe fewer instances/page', 'Lighthouse score gain'], fontsize=10)
    for i in range(5):
        for j in range(2):
            axis.text(j, i, f'{raw[i, j]:+.2f}', ha='center', va='center', color='#243449')
    axis = axes[1, 1]
    counts = [row['targets_met'] for row in rows]
    accepted_bars = axis.bar(x, counts, width=.66, facecolor=to_rgba(GREEN,.24), edgecolor=GREEN, linewidth=1.5, label='Targets met')
    amber = '#b87b18'
    warning_bars = axis.bar(x, [25-count for count in counts], bottom=counts, width=.66,
             facecolor=to_rgba(amber,.24), edgecolor=amber, linewidth=1.5, label='Targets not met')
    for container in (accepted_bars, warning_bars):
        axis.bar_label(container, fmt='%d', label_type='center', fontsize=11, color='#243449')
    axis.set_xticks(x, LABELS); axis.set_ylim(0, 33); axis.set_ylabel('Candidates')
    axis.legend(frameon=False, fontsize=10, loc='lower left',
                bbox_to_anchor=(.14, 1.00), ncol=2, borderaxespad=0)
    axis.set_axisbelow(True); axis.grid(axis='y',color='#d9e0e8',linewidth=.7)
    for axis, letter in zip(axes.flat, 'ABCD'):
        axis.text(0, 1.03, letter, transform=axis.transAxes, fontsize=12, weight='normal')
    fig.savefig(output, dpi=1000, bbox_inches='tight', facecolor='white')
    plt.close(fig)




if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('.'))
    args = parser.parse_args()
    rows = summarize(args.package)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / 'table7.csv').open('w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Stratum', 'Pairs', 'Original Axe', 'Candidate Axe',
                         'Original Lighthouse', 'Candidate Lighthouse'])
        for row in rows:
            writer.writerow([row['label'], row['baseline']['n'],
                             *(f"{row[state][metric]:.2f}" for metric in ('axe', 'lighthouse')
                               for state in ('baseline', 'candidate'))])
    render_figure(rows, args.output_dir / 'figure5.png')
