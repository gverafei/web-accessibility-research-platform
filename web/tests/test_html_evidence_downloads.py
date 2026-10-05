"""Read-only, experiment-scoped HTML evidence downloads and conditional links."""
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
from flask import render_template, session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
if 'database' not in sys.modules:
    stub = types.ModuleType('database')
    stub.init_db = lambda: None
    stub.get_connection = lambda: None
    sys.modules['database'] = stub

from main import app
from routes import experiments


class HtmlEvidenceDownloadTests(unittest.TestCase):
    def get_artifact(self, kind, result, allowed_root):
        conn = MagicMock()
        cursor = conn.cursor.return_value
        cursor.fetchone.return_value = result
        realpath = experiments.os.path.realpath
        with patch.object(experiments, 'get_connection', return_value=conn), \
                patch.object(experiments.os.path, 'realpath', side_effect=lambda path:
                             str(allowed_root) if path == '/results/raw' else realpath(path)), \
                patch('main.get_settings', return_value={}):
            response = app.test_client().get(f'/experiments/42/raw/7/{kind}')
            response.get_data()
            response.close()
        conn.commit.assert_not_called()
        conn.rollback.assert_not_called()
        return response, cursor

    def test_html_is_exact_attachment_with_html_filename_and_mime(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for kind, column in [('response', 'response_source_path'),
                                 ('rendered', 'source_snapshot_path')]:
                with self.subTest(kind=kind):
                    content = f'<html><script>test()</script><p>{kind} á</p></html>'.encode()
                    file = root / f'{kind}.html'
                    file.write_bytes(content)
                    response, cursor = self.get_artifact(kind, {column: str(file)}, root)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.get_data(), content)
                    self.assertEqual(response.mimetype, 'text/html')
                    self.assertIn('attachment;', response.headers['Content-Disposition'])
                    self.assertIn(f'experiment_42_result_7_{kind}.html',
                                  response.headers['Content-Disposition'])
                    self.assertIn('WHERE id = %s AND experiment_id = %s', cursor.execute.call_args.args[0])
                    self.assertEqual(cursor.execute.call_args.args[1], (7, 42))

    def test_existing_json_download_contract_is_unchanged(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'axe.json'
            file.write_text('{"violations": []}')
            response, _ = self.get_artifact('axe', {'axe_raw_path': str(file)}, root)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'application/json')
            self.assertIn('experiment_42_result_7_axe.json', response.headers['Content-Disposition'])

    def test_absent_result_or_file_cannot_produce_html_download(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for result in [None, {}, {'source_snapshot_path': str(root / 'missing.html')},
                           {'source_snapshot_path': str(root)}]:
                with self.subTest(result=result):
                    response, _ = self.get_artifact('rendered', result, root)
                    self.assertEqual(response.status_code, 302)
                    self.assertEqual(response.location, '/experiments/42')
                    self.assertNotIn('Content-Disposition', response.headers)

    def test_outside_root_and_symlink_escape_are_rejected(self):
        with TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / 'raw'
            root.mkdir()
            outside = base / 'private.html'
            outside.write_text('not captured evidence')
            link = root / 'link.html'
            link.symlink_to(outside)
            sibling = base / 'raw-other'
            sibling.mkdir()
            sibling_file = sibling / 'page.html'
            sibling_file.write_text('outside allowed root')
            for file in [outside, link, sibling_file]:
                response, _ = self.get_artifact('response', {'response_source_path': str(file)}, root)
                self.assertEqual(response.status_code, 302)
                self.assertNotIn(b'not captured evidence', response.get_data())

    def test_unknown_type_does_not_access_database(self):
        with patch.object(experiments, 'get_connection') as conn:
            response = app.test_client().get('/experiments/42/raw/7/unknown')
        self.assertEqual(response.status_code, 302)
        conn.assert_not_called()

    def test_buttons_are_conditional_and_share_json_styles_in_both_languages(self):
        for language in ('en', 'es'):
            for response_exists, rendered_exists in [(False, False), (True, False),
                                                      (False, True), (True, True)]:
                with app.test_request_context('/'), patch('main.get_settings', return_value={}):
                    session['language'] = language
                    html = render_template('_evaluation_evidence_downloads.html', experiment={'id': 42}, item={
                        'id': 7, 'response_source_path': 'response.html' if response_exists else None,
                        'source_snapshot_path': 'rendered.html' if rendered_exists else None})
                dom = BeautifulSoup(html, 'html.parser')
                self.assertEqual(bool(dom.select_one('a[href$="/response"]')), response_exists)
                self.assertEqual(bool(dom.select_one('a[href$="/rendered"]')), rendered_exists)
                for link in dom.select('a'):
                    self.assertEqual(link['class'], ['btn', 'btn-sm', 'btn-outline-dark'])
                if response_exists:
                    self.assertIn('HTML de respuesta' if language == 'es' else 'Response HTML', html)
                if rendered_exists:
                    self.assertIn('HTML renderizado' if language == 'es' else 'Rendered HTML', html)


if __name__ == '__main__':
    unittest.main()
