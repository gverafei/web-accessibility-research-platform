"""Synchronize approved W3C ACT passed/failed HTML examples into local Qdrant."""
import datetime
import hashlib
import io
import json
import uuid
import zipfile

import requests

from remediation_rag import COLLECTION, QDRANT_URL, VECTOR_SIZE, embed


INDEX_URL = "https://www.w3.org/WAI/content-assets/wcag-act-rules/testcases.json"
ARCHIVE_URL = "https://github.com/w3c/wcag-act-rules/archive/refs/heads/main.zip"


def build_case(item, archive, prefix, snapshot_sha256):
    if item.get("expected") not in {"passed", "failed"} or not item.get("approved"):
        return None
    archive_path = prefix + "content-assets/wcag-act-rules/" + item["relativePath"]
    try:
        code = archive.read(archive_path).decode("utf-8", errors="replace").strip()
    except KeyError:
        return None
    requirements = sorted(key for key, value in (item.get("ruleAccessibilityRequirements") or {}).items() if isinstance(value, dict))
    search_text = " ".join([item.get("ruleName", ""), item.get("testcaseTitle", ""), item.get("expected", ""), " ".join(requirements), code])
    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, item["url"]))
    return {"id": point_id, "vector": embed(search_text), "payload": {"source":"W3C ACT Rules","source_index":INDEX_URL,"snapshot_sha256":snapshot_sha256,"license":"https://act-rules.github.io/pages/license/","retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"rule_id":item.get("ruleId"),"rule_name":item.get("ruleName"),"rule_page":item.get("rulePage"),"testcase_id":item.get("testcaseId"),"title":item.get("testcaseTitle"),"expected":item.get("expected"),"requirements":requirements,"code":code,"example_url":item.get("url")}}


def main():
    downloaded = requests.get(ARCHIVE_URL, timeout=180)
    downloaded.raise_for_status()
    snapshot_sha256 = hashlib.sha256(downloaded.content).hexdigest()
    archive = zipfile.ZipFile(io.BytesIO(downloaded.content))
    prefix = archive.namelist()[0].split("/", 1)[0] + "/"
    cases = json.loads(archive.read(prefix + "content-assets/wcag-act-rules/testcases.json")).get("testcases") or []
    requests.delete(f"{QDRANT_URL}/collections/{COLLECTION}", timeout=30)
    requests.put(f"{QDRANT_URL}/collections/{COLLECTION}", json={"vectors":{"size":VECTOR_SIZE,"distance":"Cosine"}}, timeout=30).raise_for_status()
    points = []
    for item in cases:
        point = build_case(item, archive, prefix, snapshot_sha256)
        if point:
            points.append(point)
            if len(points) == 64:
                requests.put(f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true", json={"points":points}, timeout=60).raise_for_status()
                points = []
    if points:
        requests.put(f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true", json={"points":points}, timeout=60).raise_for_status()
    from remediation_rag_supplement import sync
    sync()
    info = requests.get(f"{QDRANT_URL}/collections/{COLLECTION}", timeout=10).json()["result"]
    print(json.dumps({"collection":COLLECTION,"points":info.get("points_count"),"source":INDEX_URL,"snapshot":ARCHIVE_URL,"snapshot_sha256":snapshot_sha256}))


if __name__ == "__main__":
    main()
