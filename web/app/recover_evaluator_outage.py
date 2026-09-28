"""Restore Tranco candidates consumed by a known evaluator outage.

Dry run by default. Run inside the worker container with an explicit experiment
ID and the database-local timestamp at which the evaluator exited.
"""

import argparse
import json
import os

import mysql.connector


def connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "accessibility_experiments"),
        user=os.getenv("DB_USER", "access_user"),
        password=os.getenv("DB_PASSWORD", "access_pass"),
    )


def recover(experiment_id, cutoff, apply=False):
    conn = connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM experiments WHERE id=%s FOR UPDATE", (experiment_id,))
        experiment = cursor.fetchone()
        if not experiment or experiment["status"] != "paused" or experiment["source_type"] != "tranco":
            raise ValueError("The specified Tranco experiment must be paused.")
        cursor.execute("SELECT * FROM tranco_samples WHERE experiment_id=%s FOR UPDATE", (experiment_id,))
        sample = cursor.fetchone()
        if not sample:
            raise ValueError("Sampling manifest missing.")
        candidates = sample["candidates"]
        if isinstance(candidates, str):
            candidates = json.loads(candidates)
        by_url = {item["url"]: item for item in candidates}
        if len(by_url) != len(candidates):
            raise ValueError("Candidate URLs are not unique.")

        cursor.execute(
            """SELECT id,url FROM tranco_attempts
               WHERE experiment_id=%s AND started_at >= %s
                 AND error_message LIKE 'Evaluator service interruption after 3 attempts:%%'""",
            (experiment_id, cutoff),
        )
        outage_attempts = cursor.fetchall()
        outage_urls = {item["url"] for item in outage_attempts}
        if not outage_urls:
            raise ValueError("No matching evaluator interruption attempts.")
        cursor.execute(
            """SELECT id,url FROM experiment_results
               WHERE experiment_id=%s AND created_at >= %s
                 AND error_message LIKE 'Evaluator service interruption after 3 attempts:%%'""",
            (experiment_id, cutoff),
        )
        outage_results = cursor.fetchall()
        if len(outage_results) != len(outage_attempts):
            raise ValueError("Outage results and attempts do not match; recovery may already be applied.")

        urls = [url.strip() for url in experiment["urls"].splitlines() if url.strip()]
        if len(urls) != len(set(urls)):
            raise ValueError("Active experiment URLs are not unique.")
        replacement_map = {}
        restored = 0
        suffix_urls = set()
        for root in candidates:
            if root.get("role") not in {"selected", "excluded_failed"} or root.get("replaces"):
                continue
            chain = []
            seen = set()
            node = root
            while node:
                if node["url"] in seen:
                    raise ValueError("Replacement chain contains a cycle.")
                seen.add(node["url"])
                chain.append(node)
                node = by_url.get(node.get("replaced_by"))
            first_outage = next((i for i, item in enumerate(chain) if item["url"] in outage_urls), None)
            if first_outage is None:
                continue
            restored_node = chain[first_outage]
            terminal = chain[-1]
            if terminal["url"] not in urls:
                raise ValueError(f"Active chain endpoint missing: {terminal['url']}")
            replacement_map[terminal["url"]] = restored_node["url"]
            suffix_urls.update(item["url"] for item in chain[first_outage:])
            for item in chain[first_outage + 1:]:
                item["role"] = "reserve"
                for key in ("replaces", "replaced_by", "exclusion_reason", "exclusion_category",
                            "last_failure_message", "retry_count"):
                    item.pop(key, None)
            restored_node["role"] = "selected" if first_outage == 0 else "selected_replacement"
            for key in ("replaced_by", "exclusion_reason", "exclusion_category",
                        "last_failure_message", "retry_count"):
                restored_node.pop(key, None)
            restored += 1

        if not restored:
            raise ValueError("No active replacement chains match the outage.")
        if not outage_urls.issubset(suffix_urls):
            raise ValueError(f"Unaccounted outage URLs: {len(outage_urls - suffix_urls)}")
        cursor.execute(
            """SELECT url FROM experiment_results
               WHERE experiment_id=%s AND status='completed'""", (experiment_id,)
        )
        completed = {row["url"] for row in cursor.fetchall()}
        if completed & suffix_urls:
            raise ValueError("A candidate in an outage suffix has completed evidence; refusing rollback.")
        if len(replacement_map) != restored:
            raise ValueError("Restored sample slots do not match active URL replacements.")
        new_urls = [replacement_map.get(url, url) for url in urls]
        active = [item for item in candidates if item.get("role") in {"selected", "selected_replacement"}]
        if len(active) != len(new_urls) or {item["url"] for item in active} != set(new_urls):
            raise ValueError("Active candidates and experiment URLs do not match.")

        report = {
            "experiment_id": experiment_id,
            "outage_attempts": len(outage_attempts),
            "outage_results": len(outage_results),
            "restored_sample_slots": restored,
            "active_urls": len(new_urls),
            "completed_results_preserved": len(completed),
        }
        if apply:
            cursor.execute(
                """UPDATE tranco_attempts SET status='interrupted',
                   error_category='service_interruption'
                   WHERE experiment_id=%s AND started_at >= %s
                     AND error_message LIKE 'Evaluator service interruption after 3 attempts:%%'""",
                (experiment_id, cutoff),
            )
            cursor.execute(
                """DELETE FROM experiment_results WHERE experiment_id=%s AND created_at >= %s
                   AND error_message LIKE 'Evaluator service interruption after 3 attempts:%%'""",
                (experiment_id, cutoff),
            )
            cursor.execute("UPDATE tranco_samples SET candidates=%s WHERE experiment_id=%s",
                           (json.dumps(candidates), experiment_id))
            cursor.execute("UPDATE experiments SET urls=%s WHERE id=%s",
                           ("\n".join(new_urls), experiment_id))
            conn.commit()
        else:
            conn.rollback()
        return report
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment_id", type=int)
    parser.add_argument("cutoff", help="database-local timestamp, YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(recover(args.experiment_id, args.cutoff, args.apply), indent=2))
