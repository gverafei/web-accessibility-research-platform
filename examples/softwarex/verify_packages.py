"""Offline integrity/count verification; does not extract or execute content."""
import base64
import hashlib
import json
from pathlib import Path
import zipfile


def digest_stream(source):
    digest = hashlib.sha256()
    while chunk := source.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def verify(root):
    manifest = json.loads((root / 'MANIFEST.json').read_text())
    for record in manifest['packages']:
        path = root / record['file']
        assert path.parent == root and path.suffix == '.warp', 'Invalid inventory filename'
        with path.open('rb') as source:
            assert digest_stream(source) == record['sha256'], f'Package digest: {path.name}'
        assert path.stat().st_size == record['bytes'], f'Package size: {path.name}'
        with zipfile.ZipFile(path) as archive:
            if record['kind'] == 'remediation':
                payload = json.loads(archive.read('remediation.json'))
                assert payload['format'] == 'warp-remediations' and payload['version'] == 1
                assert len(payload['runs']) == record['count']
                files = payload['files']
            else:
                payload = json.loads(archive.read('experiment.json'))
                assert payload['format'] == 'warp-experiment' and payload['version'] in (3, 4)
                assert len(payload['results']) == record['count']
                files = [file for row in payload['results'] for file in row.get('artifacts', {}).values()]
            for file in files:
                if 'member' in file:
                    assert archive.getinfo(file['member']).file_size == file['size']
                    with archive.open(file['member']) as source:
                        assert digest_stream(source) == file['sha256']
                else:
                    base64.b64decode(file['base64'], validate=True)
        print(f'OK {path.name}: {record["count"]} {record["kind"]} records')


if __name__ == '__main__':
    verify(Path(__file__).resolve().parent)
