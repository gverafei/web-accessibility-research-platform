import unittest
from pathlib import Path

from routes.comparisons import comparison_analysis, split_source_refs


class ComparisonAnalysisTests(unittest.TestCase):
    def test_member_pagination_preserves_all_rows_and_removes_notes_editor(self):
        template = (Path(__file__).resolve().parents[1] / 'app/templates/comparison_detail.html').read_text()
        self.assertIn('[5,10,20,25,50,100,250,500]', template)
        self.assertIn('id="comparisonPagination"', template)
        self.assertIn('id="comparisonFilter"', template)
        self.assertIn('type="search"', template)
        self.assertIn('placeholder="{{ _(\'Filter pages\') }}"', template)
        self.assertIn('Groups are optional.") }}</p></div>\n<section class="card', template)
        css = (Path(__file__).resolve().parents[1] / 'app/static/css/style.css').read_text()
        self.assertIn('#comparisonFilter{font-size:.78rem;min-height:30px;padding-right:.65rem}', css)
        self.assertIn('#comparisonPagination select{font-size:.78rem}', css)
        self.assertIn('{% if size == 5 %} selected', template)
        self.assertNotIn('{% if size == 25 %} selected', template)
        between = template.split('id="comparisonPagination"', 1)[1].split('id="comparisonMembers"', 1)[0]
        self.assertNotIn('Edits are saved', between)
        self.assertGreater(template.index('Edits are saved'), template.index('id="comparisonMembers"'))
        self.assertIn('{% for member in members %}', template)
        self.assertIn("filename='js/comparison_pagination.js'", template)
        self.assertNotIn("setting('notes'", template)
        self.assertIn("member_ids:[...body.rows]", template)

    def test_paired_tables_and_charts_use_wcag_not_combined(self):
        original = self.row(1, 'Original', axe=1205, lighthouse=78, pair_key='site', is_baseline=True)
        candidate = self.row(2, 'Remediated', axe=1183, lighthouse=96, pair_key='site')
        original['axe_wcag_violations'] = 23
        candidate['axe_wcag_violations'] = 1
        analysis = comparison_analysis([original, candidate])
        self.assertEqual(analysis['deltas'][0]['axe_improvement'], 22)
        self.assertEqual(analysis['deltas'][0]['baseline_axe'], 23)
        self.assertEqual(analysis['deltas'][0]['candidate_axe'], 1)
        self.assertEqual(next(row for row in analysis['summaries'] if row['label']=='Remediated')['axe'], 1)
        self.assertEqual(original['axe_violations'], 1205)

    def test_source_refs_separate_evaluations_and_remediations(self):
        results, remediations = split_source_refs([
            "result:12", "remediation:8", "result:12", "invalid", "remediation:nope",
        ])
        self.assertEqual(results, [12])
        self.assertEqual(remediations, [8])

    def row(self, identifier, group, **values):
        return {
            "id": identifier, "display_name": f"page-{identifier}",
            "group_label": group, "pair_key": values.pop("pair_key", None),
            "group_label_2": values.pop("group_2", None),
            "is_baseline": values.pop("is_baseline", False),
            "axe_violations": values.pop("axe", None),
            "lighthouse_score": values.pop("lighthouse", None),
            "wave_errors": values.pop("wave", None),
            "wave_contrast_errors": values.pop("wave_contrast", None),
            "wave_alerts": values.pop("wave_alerts", None),
            "wave_features": values.pop("wave_features", None),
            "semantic_findings_count": values.pop("llm", None),
            "semantic_total_tokens": values.pop("tokens", None),
        }

    def test_optional_metrics_use_metric_specific_complete_cases(self):
        analysis = comparison_analysis([
            self.row(1, "Original", axe=10, lighthouse=70, wave=4),
            self.row(2, "Generated", axe=3, lighthouse=95),
        ])
        self.assertTrue(analysis["availability"]["axe"]["comparable"])
        self.assertEqual(analysis["availability"]["wave"]["observations"], 1)
        self.assertFalse(analysis["availability"]["wave"]["comparable"])
        generated = next(row for row in analysis["summaries"] if row["label"] == "Generated")
        self.assertIsNone(generated["wave"])

    def test_paired_improvement_requires_both_metric_values(self):
        analysis = comparison_analysis([
            self.row(1, "Original", axe=10, lighthouse=70, wave=5,
                     pair_key="site-1", is_baseline=True),
            self.row(2, "Generated", axe=4, lighthouse=90,
                     pair_key="site-1"),
        ])
        delta = analysis["deltas"][0]
        self.assertEqual(delta["axe_improvement"], 6)
        self.assertEqual(delta["lighthouse_improvement"], 20)
        self.assertIsNone(delta["wave_improvement"])

    def test_multiple_pair_keys_use_their_own_originals(self):
        analysis = comparison_analysis([
            self.row(1, "Top", axe=20, lighthouse=60, pair_key="a", is_baseline=True),
            self.row(2, "Top", axe=5, lighthouse=90, pair_key="a"),
            self.row(3, "Tail", axe=8, lighthouse=80, pair_key="b", is_baseline=True),
            self.row(4, "Tail", axe=2, lighthouse=85, pair_key="b"),
        ])
        self.assertEqual([(row["pair_key"], row["axe_improvement"]) for row in analysis["deltas"]],
                         [("a", 15), ("b", 6)])
        self.assertEqual(analysis["availability"]["axe"]["paired"], 2)
        self.assertEqual({row["label"] for row in analysis["summaries"]}, {"Top", "Tail"})

    def test_multi_pair_report_compares_original_and_candidate_groups(self):
        analysis = comparison_analysis([
            self.row(1, "Original", axe=20, lighthouse=60, pair_key="a", is_baseline=True),
            self.row(2, "Remediated", axe=5, lighthouse=90, pair_key="a"),
            self.row(3, "Original", axe=8, lighthouse=80, pair_key="b", is_baseline=True),
            self.row(4, "Remediated", axe=2, lighthouse=85, pair_key="b"),
        ])
        means = {row["label"]: row["axe"] for row in analysis["summaries"]}
        self.assertEqual(means, {"Original": 14, "Remediated": 3.5})

    def test_cohort_charts_keep_original_and_remediated_within_each_stratum(self):
        analysis = comparison_analysis([
            self.row(1, "Original", group_2="Top", axe=20, lighthouse=60,
                     pair_key="a", is_baseline=True),
            self.row(2, "Remediated", group_2="Top", axe=5, lighthouse=90, pair_key="a"),
            self.row(3, "Original", group_2="Tail", axe=8, lighthouse=80,
                     pair_key="b", is_baseline=True),
            self.row(4, "Remediated", group_2="Tail", axe=2, lighthouse=85, pair_key="b"),
        ])
        cohorts = {row["label"]: row["conditions"] for row in analysis["cohort_summary"]}
        self.assertEqual(analysis["cohort_conditions"], ["Original", "Remediated"])
        self.assertEqual(cohorts["Top"]["Original"]["axe"], 20)
        self.assertEqual(cohorts["Top"]["Remediated"]["axe"], 5)
        self.assertEqual(cohorts["Tail"]["Original"]["lighthouse"], 80)
        self.assertEqual(cohorts["Tail"]["Remediated"]["lighthouse"], 85)

    def test_paired_distributions_use_cohorts_without_duplicate_condition_total(self):
        analysis = comparison_analysis([
            self.row(1, "Original", group_2="Global top 500", axe=20, lighthouse=60,
                     pair_key="a", is_baseline=True),
            self.row(2, "Remediated", group_2="Global top 500", axe=5, lighthouse=90,
                     pair_key="a"),
            self.row(3, "Original", group_2="Popularity tail", axe=8, lighthouse=80,
                     pair_key="b", is_baseline=True),
            self.row(4, "Remediated", group_2="Popularity tail", axe=2, lighthouse=85,
                     pair_key="b"),
        ])
        self.assertEqual(
            [row["label"] for row in analysis["improvement_boxes"]],
            ["Global top 500", "Popularity tail"],
        )
        self.assertEqual(analysis["cohort_matrix"][0]["axe_improvement"], 15)
        self.assertEqual(analysis["cohort_matrix"][0]["lighthouse_improvement"], 30)
        self.assertEqual(analysis["cohort_matrix"][1]["axe_improvement"], 6)

    def test_all_zero_metric_has_safe_heatmap_scale(self):
        analysis = comparison_analysis([
            self.row(1, "A", axe=0, lighthouse=100),
            self.row(2, "B", axe=0, lighthouse=90),
        ])
        self.assertEqual(analysis["heat_max"]["axe_violations"], 1)

    def test_ungrouped_comparison_uses_one_all_pages_group(self):
        analysis = comparison_analysis([
            self.row(1, "", axe=10, lighthouse=70, pair_key="page-1", is_baseline=True),
            self.row(2, "", axe=2, lighthouse=95, pair_key="page-1"),
        ])
        self.assertEqual(analysis["summaries"][0]["label"], "All pages")
        self.assertEqual(analysis["deltas"][0]["axe_improvement"], 8)
        self.assertEqual(analysis["improvement_boxes"][0]["label"], "All pages")

    def test_ungrouped_candidates_are_excluded_when_groups_exist(self):
        analysis = comparison_analysis([
            self.row(1, "", axe=10, lighthouse=70, is_baseline=True),
            self.row(2, "GPT", axe=2, lighthouse=95),
            self.row(3, "", axe=4, lighthouse=90),
        ])
        self.assertEqual([row["candidate"] for row in analysis["deltas"]], ["page-2"])

    def test_large_ungrouped_comparison_requires_groups(self):
        rows = [self.row(1, "", axe=10, lighthouse=70, is_baseline=True)]
        rows.extend(self.row(index, "", axe=index, lighthouse=80) for index in range(2, 23))
        analysis = comparison_analysis(rows)
        self.assertTrue(analysis["requires_grouping"])
        self.assertFalse(analysis["show_individual_charts"])
        self.assertEqual(analysis["deltas"], [])


if __name__ == "__main__":
    unittest.main()
