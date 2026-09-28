"""Pinned, cached framework assets embedded in delivered born documents.

No browser-side CDN dependency. Download failures are explicit, before model
generation; arbitrary model URLs are never fetched by this loader.
"""
from pathlib import Path
import hashlib
import requests
from bs4 import BeautifulSoup

VERSION='5.3.8'
ASSETS={'css':f'https://cdn.jsdelivr.net/npm/bootstrap@{VERSION}/dist/css/bootstrap.min.css',
        'javascript':f'https://cdn.jsdelivr.net/npm/bootstrap@{VERSION}/dist/js/bootstrap.bundle.min.js'}


def framework_assets(root):
    cache=Path(root)/'frameworks'/f'bootstrap-{VERSION}'
    cache.mkdir(parents=True,exist_ok=True)
    result={}
    for kind,url in ASSETS.items():
        path=cache/(kind+'.txt')
        if not path.is_file():
            response=requests.get(url,timeout=15)
            response.raise_for_status()
            text=response.text
            if not 1000<len(text)<500000 or 'Bootstrap' not in text[:500]:
                raise ValueError('Pinned framework download did not contain the expected Bootstrap asset')
            temporary=path.with_suffix('.tmp')
            temporary.write_text(text,encoding='utf-8'); temporary.replace(path)
        result[kind]=path.read_text(encoding='utf-8')
    return result


def embed_framework(document,assets):
    soup=BeautifulSoup(document,'html.parser')
    if not soup.head: raise ValueError('Born document needs a head for owned framework assets')
    for node in soup.select('link[href],script[src],[data-warp-framework]'):
        if node.has_attr('data-warp-framework') or '/bootstrap@' in (node.get('href') or node.get('src') or ''):
            node.decompose()
    style=soup.new_tag('style'); style['data-warp-framework']=f'bootstrap-{VERSION}'
    style.string=assets['css']; soup.head.insert(0,style)
    script=soup.new_tag('script'); script['data-warp-framework']=f'bootstrap-{VERSION}'
    script.string=assets['javascript']; (soup.body or soup).append(script)
    return str(soup)


def framework_evidence(assets):
    return {'name':'Bootstrap','version':VERSION,'delivery':'embedded cached assets; no browser-side CDN fetch',
            'sha256':{kind:hashlib.sha256(text.encode()).hexdigest() for kind,text in assets.items()}}
