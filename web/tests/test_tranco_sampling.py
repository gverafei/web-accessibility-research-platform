import io
import sys
import unittest
import zipfile
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from tranco_sampling import (
    TRANCO_STRATA, TrancoImportError,
    classify_failure, extend_ordered_reserves,
    expand_stratified_sample, fetch_latest_standard_list, parse_tranco, plan_failed_replacements,
    plan_failed_retries, sample_tranco,
)


class TrancoSamplingTests(unittest.TestCase):

    def test_expansion_preserves_existing_urls_and_adds_balanced_slots(self):
        ranking = [
            (rank, f"site{rank}.example")
            for rank in (1, 2, 3, 4, 1001, 1002, 1003, 1004, 10001, 10002, 10003, 10004,
                         100001, 100002, 100003, 100004,
                         500001, 500002, 500003, 500004)
        ]
        counts = {label: 1 for label, _name, _lower, _upper in TRANCO_STRATA}
        candidates, strata = sample_tranco(ranking, "94XL2", "seed", counts, counts)
        current = [item["url"] for item in candidates if item["role"] == "selected"]
        urls, expanded, metadata = expand_stratified_sample(
            ranking, "94XL2", "seed", candidates, strata, current, 2, 2
        )
        self.assertEqual(urls[:5], current)
        self.assertEqual(len(urls), 10)
        self.assertTrue(all(item["selected_count"] == 2 for item in metadata))
        self.assertTrue(all(sum(1 for row in expanded if row["stratum"] == item["label"] and row["role"] == "reserve") >= 2 for item in metadata))
    def test_fetch_latest_pins_id_before_downloading_exact_list(self):
        class Response:
            def __init__(self, text="", content=b""):
                self.text, self.content = text, content

            def raise_for_status(self):
                return None

        class Session:
            calls = []

            @classmethod
            def get(cls, url, timeout):
                cls.calls.append((url, timeout))
                if url.endswith("top-1m-id"):
                    return Response(text="94XL2")
                return Response(content=b"1,example.com\n")

        content, filename, list_id = fetch_latest_standard_list(Session)
        self.assertEqual(list_id, "94XL2")
        self.assertEqual(filename, "tranco_94XL2.csv")
        self.assertEqual(content, b"1,example.com\n")
        self.assertTrue(Session.calls[1][0].endswith("/download/94XL2/1000000"))

    def test_parses_original_style_zip(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("top-1m.csv", "1,example.com\n2,example.org\n")
        ranking, metadata = parse_tranco(buffer.getvalue(), "tranco.zip")
        self.assertEqual(ranking, [(1, "example.com"), (2, "example.org")])
        self.assertEqual(metadata["frame_size"], 2)
        self.assertEqual(len(metadata["list_sha256"]), 64)

    def test_rejects_duplicate_domains(self):
        with self.assertRaisesRegex(TrancoImportError, "Duplicate or invalid domain"):
            parse_tranco(b"1,example.com\n2,example.com\n", "tranco.csv")

    def test_sampling_is_deterministic_and_stratified(self):
        ranking = []
        for lower, upper in (
            (1, 1000), (1001, 10_000), (10_001, 100_000),
            (100_001, 500_000), (500_001, 1_000_000),
        ):
            for rank in range(lower, min(lower + 5, upper + 1)):
                ranking.append((rank, f"site-{rank}.example"))
        first, strata = sample_tranco(ranking, "ZWQ8N", "study-seed", 2, 2)
        second, _ = sample_tranco(ranking, "ZWQ8N", "study-seed", 2, 2)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 20)
        self.assertEqual(sum(item["role"] == "selected" for item in first), 10)
        self.assertEqual([item["selected_count"] for item in strata], [2] * 5)
        self.assertEqual(strata[0]["display_name"], "Global top 1,000")

    def test_failed_site_uses_next_reserve_in_same_stratum(self):
        candidates = [
            {"url": "https://failed.example/", "stratum": "top", "role": "selected"},
            {"url": "https://other.example/", "stratum": "other", "role": "selected"},
            {"url": "https://second.example/", "stratum": "top", "role": "reserve", "selection_order": 2},
            {"url": "https://first.example/", "stratum": "top", "role": "reserve", "selection_order": 1},
        ]
        replacements = plan_failed_replacements(candidates, {"https://failed.example/"})
        self.assertEqual(len(replacements), 1)
        self.assertEqual(replacements[0][1]["url"], "https://first.example/")

    def test_exhausted_reserves_extend_the_same_deterministic_sequence(self):
        ranking = [(rank, f"site-{rank}.example") for rank in range(1, 21)]
        candidates, _ = sample_tranco(
            ranking, "94XL2", "study", {"rank_1_1000": 2}, {"rank_1_1000": 1}
        )
        existing = {item["domain"] for item in candidates}
        added = extend_ordered_reserves(
            ranking, "94XL2", "study", candidates, {"rank_1_1000"}, batch_size=5
        )
        self.assertEqual(len(added), 5)
        self.assertFalse(existing.intersection(item["domain"] for item in added))
        self.assertEqual([item["selection_order"] for item in added], [3, 4, 5, 6, 7])

    def test_sampling_allows_independent_group_sizes_and_disabled_groups(self):
        ranking = []
        for lower in (1, 1001, 10_001, 100_001, 500_001):
            ranking.extend(
                (rank, f"site-{rank}.example") for rank in range(lower, lower + 8)
            )
        counts = {
            "rank_1_1000": 3,
            "rank_1001_10000": 0,
            "rank_10001_100000": 2,
            "rank_100001_500000": 0,
            "rank_500001_1000000": 1,
        }
        reserves = {label: (2 if count else 0) for label, count in counts.items()}
        candidates, strata = sample_tranco(ranking, "94XL2", "custom", counts, reserves)
        self.assertEqual(sum(item["role"] == "selected" for item in candidates), 6)
        self.assertEqual([item["selected_count"] for item in strata], [3, 0, 2, 0, 1])
        self.assertFalse(any(
            item["stratum"] in {"rank_1001_10000", "rank_100001_500000"}
            for item in candidates
        ))

    def test_sampling_requires_at_least_one_enabled_group(self):
        counts = {label: 0 for label, _name, _lower, _upper in TRANCO_STRATA}
        with self.assertRaisesRegex(TrancoImportError, "at least one site"):
            sample_tranco([], "94XL2", "custom", counts, counts)

    def test_only_active_candidates_receive_one_controlled_retry(self):
        candidates = [
            {"url": "https://new.example/", "role": "selected"},
            {"url": "https://retried.example/", "role": "selected", "retry_count": 1},
            {"url": "https://replacement.example/", "role": "selected_replacement"},
            {"url": "https://reserve.example/", "role": "reserve"},
        ]
        retries = plan_failed_retries(candidates, {
            "https://new.example/", "https://retried.example/",
            "https://replacement.example/", "https://reserve.example/",
        })
        self.assertEqual(
            [candidate["url"] for candidate in retries],
            ["https://new.example/", "https://replacement.example/"],
        )

    def test_failure_classification_uses_operational_categories(self):
        self.assertEqual(classify_failure("Navigation timed out after 30s"), "timeout")
        self.assertEqual(classify_failure("net::ERR_NAME_NOT_RESOLVED"), "dns_resolution")
        self.assertEqual(classify_failure("HTTP 403 access denied"), "access_restricted")

    def test_entire_top_500_is_allowed_and_leaves_no_reserves(self):
        ranking = [(rank, f"site-{rank}.example") for rank in range(1, 501)]
        counts = {"rank_1_1000": 500}
        candidates, strata = sample_tranco(ranking, "94XL2", "study-seed", counts, counts)
        self.assertEqual(len(candidates), 500)
        self.assertTrue(all(item["role"] == "selected" for item in candidates))
        self.assertEqual(strata[0]["selected_count"], 500)
        self.assertEqual(strata[0]["reserve_count"], 0)

    def test_researcher_allocation_can_exceed_old_per_group_and_total_caps(self):
        sizes = [200, 250, 300, 450, 600]
        ranking = []
        counts = {}
        for (label, _name, lower, _upper), count in zip(TRANCO_STRATA, sizes):
            counts[label] = count
            ranking.extend((rank, f"site-{rank}.example")
                           for rank in range(lower, lower + count + 25))
        candidates, strata = sample_tranco(ranking, "94XL2", "study-seed", counts, counts)
        self.assertEqual([item["selected_count"] for item in strata], sizes)
        self.assertEqual(sum(item["role"] == "selected" for item in candidates), 1800)
        self.assertEqual([item["reserve_count"] for item in strata], [25] * 5)
        self.assertEqual(len({item["domain"] for item in candidates}), len(candidates))
        self.assertEqual((candidates, strata),
                         sample_tranco(ranking, "94XL2", "study-seed", counts, counts))

    def test_target_cannot_exceed_actual_available_domains(self):
        ranking = [(1, "one.example"), (2, "two.example")]
        with self.assertRaisesRegex(TrancoImportError, "only 2 domains"):
            sample_tranco(ranking, "94XL2", "study-seed", {"rank_1_1000": 3}, 0)

    def test_counts_require_nonnegative_whole_numbers(self):
        for count in (-1, 1.5, True, "2"):
            with self.subTest(count=count), self.assertRaisesRegex(TrancoImportError, "whole numbers"):
                sample_tranco([], "94XL2", "study-seed", {"rank_1_1000": count}, 0)
        with self.assertRaisesRegex(TrancoImportError, "nonnegative"):
            sample_tranco([], "94XL2", "study-seed", {"rank_1_1000": 1}, -1)

    def test_expansion_can_exceed_old_top_cap_and_preserves_existing_urls(self):
        ranking = [(rank, f"site-{rank}.example") for rank in range(1, 501)]
        candidates, strata = sample_tranco(ranking, "94XL2", "study", {"rank_1_1000": 100}, 0)
        # Expansion applies to enabled groups of this one-stratum collection.
        strata = [strata[0]]
        current = [item["url"] for item in candidates if item["role"] == "selected"]
        urls, candidates, strata = expand_stratified_sample(
            ranking, "94XL2", "study", candidates, strata, current, 300, 300
        )
        self.assertEqual(urls[:100], current)
        self.assertEqual(len(urls), 300)
        self.assertEqual(strata[0]["reserve_count"], 200)
        self.assertEqual(expand_stratified_sample(
            ranking, "94XL2", "study", candidates, strata, urls, 300, 300
        )[0], urls)

    def test_custom_design_uses_its_own_rank_boundaries_and_reserve_order(self):
        definitions = (("top", "Top", 1, 4), ("tail", "Tail", 5, 12))
        ranking = [(rank, f"site-{rank}.example") for rank in range(1, 13)]
        candidates, strata = sample_tranco(
            ranking, "94XL2", "new-study", {"top": 2, "tail": 3},
            {"top": 1, "tail": 2}, strata_definitions=definitions,
        )
        self.assertEqual([item["selected_count"] for item in strata], [2, 3])
        self.assertEqual(sum(item["role"] == "selected" for item in candidates), 5)
        self.assertTrue(all(item["rank"] <= 4 for item in candidates if item["stratum"] == "top"))
        added = extend_ordered_reserves(
            ranking, "94XL2", "new-study", candidates, {"tail"},
            batch_size=1, strata_definitions=definitions,
        )
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["stratum"], "tail")


if __name__ == "__main__":
    unittest.main()
