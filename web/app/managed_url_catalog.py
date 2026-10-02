"""Bounded server-side catalog paging. Never ship the complete catalog to the DOM."""
from math import ceil

SORT_COLUMNS = {'url': 'url', 'name': 'COALESCE(display_name,captured_url,page_title,url)',
                'axe': 'axe_violations', 'lighthouse': 'lighthouse_score',
                'category': 'site_category', 'evaluation': 'experiment_title',
                'date': 'COALESCE(evaluated_at,created_at)'}
RANKED = """WITH ranked AS (
    SELECT r.id,r.url,r.normalized_url,r.display_name,r.captured_url,r.page_title,
           r.screenshot_path,r.site_category,r.site_category_source,r.status,
           r.axe_wcag_violations AS axe_violations,r.lighthouse_score,r.evaluated_at,r.created_at,
           e.id experiment_id,e.title experiment_title,
           COUNT(*) OVER (PARTITION BY COALESCE(r.normalized_url,CONCAT('id:',r.id))) occurrence_count,
           ROW_NUMBER() OVER (
             PARTITION BY COALESCE(r.normalized_url,CONCAT('id:',r.id))
             ORDER BY COALESCE(r.evaluated_at,r.created_at) DESC,r.id DESC
           ) result_rank
    FROM experiment_results r JOIN experiments e ON e.id=r.experiment_id
    WHERE r.status='completed'
) """


def fetch_catalog_page(cursor, args):
    def integer(value, default):
        try: return int(value)
        except (TypeError, ValueError): return default
    size = integer(args.get('size'), 5)
    if size not in (5, 10, 25, 50, 100): size = 5
    page = max(1, integer(args.get('page'), 1))
    query = str(args.get('q') or '').strip()[:250]
    where = 'WHERE result_rank=1'
    params = []
    if query:
        where += " AND (url LIKE %s OR captured_url LIKE %s OR display_name LIKE %s OR page_title LIKE %s OR COALESCE(site_category,'Unclassified') LIKE %s OR experiment_title LIKE %s)"
        params = ['%' + query + '%'] * 6
    cursor.execute(RANKED + 'SELECT COUNT(*) total FROM ranked ' + where, tuple(params))
    total = int(cursor.fetchone()['total'])
    pages = max(1, ceil(total / size)); page = min(page, pages)
    key = args.get('sort') if args.get('sort') in SORT_COLUMNS else 'date'
    direction = 'ASC' if args.get('direction') == 'asc' else 'DESC'
    column = SORT_COLUMNS[key]
    cursor.execute(RANKED + f'SELECT * FROM ranked {where} ORDER BY ({column} IS NULL) ASC,{column} {direction},id DESC LIMIT %s OFFSET %s',
                   (*params, size, (page - 1) * size))
    rows = cursor.fetchall()
    cursor.execute(RANKED + "SELECT COUNT(*) total FROM ranked WHERE result_rank=1 AND status='completed' AND site_category IS NULL")
    missing = int(cursor.fetchone()['total'])
    return {'pages': rows, 'total': total, 'page': page, 'page_count': pages,
            'size': size, 'offset': (page - 1) * size, 'uncategorized_count': missing,
            'sort': key, 'direction': direction.lower()}
