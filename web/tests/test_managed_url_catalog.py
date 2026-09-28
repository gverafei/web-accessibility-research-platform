import unittest
from managed_url_catalog import fetch_catalog_page


class Cursor:
    def __init__(self, total=1800):
        self.total=total; self.statements=[]; self.ones=iter(({'total':total},{'total':1800}))
    def execute(self, sql, params=None): self.statements.append((sql,params))
    def fetchone(self): return next(self.ones)
    def fetchall(self): return [{'id':1}]


class CatalogTests(unittest.TestCase):
    def test_only_acquired_pages_are_ranked(self):
        cursor=Cursor(); fetch_catalog_page(cursor,{})
        for sql, _ in cursor.statements:
            self.assertIn("WHERE r.status='completed'", sql)
            self.assertLess(sql.index("WHERE r.status='completed'"), sql.index('SELECT COUNT(*)') if 'SELECT COUNT(*)' in sql else sql.index('SELECT *'))

    def test_default_only_five_rows(self):
        cursor=Cursor(); result=fetch_catalog_page(cursor,{})
        self.assertEqual(result['size'],5); self.assertEqual(result['page_count'],360)
        self.assertEqual(cursor.statements[1][1],(5,0))
        self.assertIn('LIMIT %s OFFSET %s',cursor.statements[1][0])

    def test_filter_uses_parameters_and_runs_after_deduplication(self):
        cursor=Cursor(); result=fetch_catalog_page(cursor,{'q':"x' OR 1=1",'size':'10','page':'3'})
        self.assertEqual(cursor.statements[1][1][-2:],(10,20))
        self.assertNotIn("x' OR",cursor.statements[1][0])
        self.assertIn('WHERE result_rank=1 AND',cursor.statements[0][0])

    def test_untrusted_sort_and_sizes_are_bounded(self):
        cursor=Cursor(); result=fetch_catalog_page(cursor,{'sort':'id; DROP TABLE experiments','direction':'bad','size':'999999','page':'bad'})
        self.assertEqual(result['sort'],'date'); self.assertEqual(result['size'],5)
        self.assertNotIn('DROP TABLE',cursor.statements[1][0])

    def test_page_clamps_and_empty_catalog(self):
        result=fetch_catalog_page(Cursor(0),{'page':'999','size':'25'})
        self.assertEqual(result['page'],1); self.assertEqual(result['offset'],0)

    def test_sort_retains_nulls_last(self):
        cursor=Cursor(); fetch_catalog_page(cursor,{'sort':'axe','direction':'asc'})
        self.assertIn('(axe_violations IS NULL) ASC,axe_violations ASC',cursor.statements[1][0])

    def test_category_filter_includes_visible_unclassified_label(self):
        cursor=Cursor(); fetch_catalog_page(cursor,{'q':'Unclassified'})
        self.assertIn("COALESCE(site_category,'Unclassified') LIKE %s", cursor.statements[0][0])
        self.assertEqual(cursor.statements[0][1][4],'%Unclassified%')


if __name__=='__main__': unittest.main()
