"""Restore optional measurements made on both saved states of a remediation run."""
from collections import Counter
from datetime import datetime, timezone


def validate_measurements(payload, sources, file_digests):
    study_sizes = Counter()
    for entry in payload['runs']:
        if 'paired_measurement' not in entry:
            continue
        pair = entry['paired_measurement']
        if not isinstance(pair, dict):
            raise ValueError('Invalid paired measurement.')
        for key in ('study', 'cohort'):
            limit = 160 if key == 'study' else 80
            if not isinstance(pair.get(key), str) or not pair[key].strip() or len(pair[key]) > limit:
                raise ValueError('Invalid paired measurement label.')
        study_sizes[pair['study']] += 2
        if study_sizes[pair['study']] > 1000:
            raise ValueError('Too many observations for a paired comparison.')
        run = entry['data']
        source = sources[run['source_result_id']]
        candidate = next((row for row in entry['iterations'] if row['id'] == run.get('accepted_iteration_id')), None)
        if not candidate:
            raise ValueError('Paired measurement requires a retained candidate.')
        for role, owner, path in [('original', f"source:{source['id']}", source['source_snapshot_path']),
                                  ('candidate', f"run:{run['id']}", candidate['output_path'])]:
            state = pair.get(role)
            if not isinstance(state, dict) or state.get('sha256') != file_digests[(owner, path)]:
                raise ValueError('Paired measurement does not match the stored HTML.')
            for field, maximum in [('axe_wcag_violations', 2147483647), ('lighthouse_score', 100)]:
                value = state.get(field)
                if type(value) is not int or not 0 <= value <= maximum:
                    raise ValueError('Invalid paired accessibility measurement.')
            for tool in ('axe', 'lighthouse'):
                value = state.get(tool + '_at')
                if not isinstance(value, str) or not datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo:
                    raise ValueError('An audit timestamp with a timezone is required.')


def restore_pair(cursor, studies, pair, source, run_id, iteration_id, candidate_url, imported_at):
    title = pair['study']
    if title not in studies:
        cursor.execute('INSERT INTO comparison_studies (title,created_at,updated_at) VALUES (%s,%s,%s)',
                       (title, imported_at, imported_at))
        studies[title] = cursor.lastrowid
    for role in ('original', 'candidate'):
        state = pair[role]
        baseline = role == 'original'
        measured_at = max(datetime.fromisoformat(state[t + '_at'].replace('Z', '+00:00'))
                          for t in ('axe', 'lighthouse')).astimezone(timezone.utc).replace(tzinfo=None)
        cursor.execute("""INSERT INTO comparison_members
            (comparison_id, source_remediation_run_id, source_remediation_iteration_id,
             locator, display_name, group_label, group_label_2, pair_key, is_baseline,
             evaluated_at, axe_wcag_violations, lighthouse_score, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (studies[title], None if baseline else run_id, None if baseline else iteration_id,
             source['url'] if baseline else candidate_url, source['url'][:255], role.capitalize(),
             pair['cohort'], f'run-{run_id}', baseline, measured_at, state['axe_wcag_violations'],
             state['lighthouse_score'], imported_at))
