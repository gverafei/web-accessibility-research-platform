"""Reproduce paired summaries from the paired measurement table (requires numpy)."""
import csv,json,sys
from collections import defaultdict,Counter
import numpy as np

def describe(values):
    a = np.asarray(values, dtype=float)
    return {'n': len(a), 'mean': float(a.mean()), 'median': float(np.median(a)),
            'q1': float(np.quantile(a, .25)), 'q3': float(np.quantile(a, .75)),
            'min': float(a.min()), 'max': float(a.max())}

def compare(rows, before, after):
    if not rows:
        return {'n': 0}
    a = np.array([[r[before + '_axe'], r[after + '_axe'],
                   r[before + '_lh'], r[after + '_lh']] for r in rows], float)
    groups = defaultdict(list)
    for r, vector in zip(rows, a):
        groups[r['stratum']].append(vector)
    rng = np.random.default_rng(20261111)
    bootstrap = np.zeros((20000, 2))
    for key in sorted(groups):
        group = np.array(groups[key])
        differences = np.column_stack((group[:, 0] - group[:, 1], group[:, 3] - group[:, 2]))
        indices = rng.integers(0, len(group), size=(20000, len(group)))
        bootstrap += differences[indices].sum(axis=1) / len(rows)
    initial = (a[:, 0] <= 3) & (a[:, 2] >= 94)
    final = (a[:, 1] <= 3) & (a[:, 3] >= 94)
    worse_axe = a[:, 1] > a[:, 0]
    worse_lh = a[:, 3] < a[:, 2]
    return {'n': len(rows), 'before_axe': describe(a[:, 0]),
            'after_axe': describe(a[:, 1]), 'before_lh': describe(a[:, 2]),
            'after_lh': describe(a[:, 3]),
            'axe_reduction': describe(a[:, 0] - a[:, 1]),
            'lh_gain': describe(a[:, 3] - a[:, 2]),
            'axe_reduction_ci95': np.quantile(bootstrap[:, 0], [.025, .975]).tolist(),
            'lh_gain_ci95': np.quantile(bootstrap[:, 1], [.025, .975]).tolist(),
            'axe_worse': int(worse_axe.sum()), 'lh_worse': int(worse_lh.sum()),
            'both_worse': int((worse_axe & worse_lh).sum()),
            'either_worse': int((worse_axe | worse_lh).sum()),
            'initial_target_met': int(initial.sum()), 'final_target_met': int(final.sum()),
            'initial_still_met': int((initial & final).sum()),
            'initial_lost': int((initial & ~final).sum()),
            'initial_outside_targets': int((~initial).sum()),
            'newly_target_met': int((~initial & final).sum())}

if __name__=='__main__':
    with open(sys.argv[1],newline='') as file: source=list(csv.DictReader(file))
    assert len(source)==125 and len({r['pair_id'] for r in source})==125
    assert len(Counter(r['stratum'] for r in source))==5
    assert set(Counter(r['stratum'] for r in source).values())=={25}
    rows=[]
    for r in source:
        item={'stratum':r['stratum']}
        for role in ['original','candidate']:
            for metric in ['axe','lighthouse']:
                value=int(r[f'local_{role}_{metric}'])
                assert value>=0 and (metric=='axe' or value<=100)
                item[f'local_{role}_{"lh" if metric=="lighthouse" else metric}']=value
        rows.append(item)
    transition_counts = Counter()
    for pair in source:
        statuses = []
        for protocol in ('submitted', 'local'):
            increases = int(pair[f'{protocol}_candidate_axe']) > int(pair[f'{protocol}_original_axe'])
            decreases = int(pair[f'{protocol}_candidate_lighthouse']) < int(pair[f'{protocol}_original_lighthouse'])
            regression = increases or decreases
            assert regression == bool(int(pair[f'{protocol}_regression']))
            statuses.append(regression)
        transition_counts[tuple(statuses)] += 1
    reconciliation = {
        'both': transition_counts[True, True],
        'submitted_only': transition_counts[True, False],
        'matched_only': transition_counts[False, True],
        'neither': transition_counts[False, False],
    }
    print(json.dumps({'regression_transitions':reconciliation,'matched_local':compare(rows,'local_original','local_candidate'),
        'strata':{key:compare([r for r in rows if r['stratum']==key], 'local_original','local_candidate')
            for key in dict.fromkeys(r['stratum'] for r in rows)}},indent=2))
