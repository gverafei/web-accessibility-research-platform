import unittest
from remediation_selection import candidate_rank, rollback_feedback
from remediation_jobs import candidate_gate_distance


class SelectionTests(unittest.TestCase):
    def test_targets_remain_first_and_do_not_become_a_hidden_content_gate(self):
        self.assertLess(candidate_rank(0,{'text_percent':80},0,5),candidate_rank(1,{'text_percent':100},100,5))

    def test_born_does_not_prefer_original_visual_similarity(self):
        self.assertEqual(candidate_rank(2,{},10,5),candidate_rank(2,{},99,5))
        self.assertEqual(candidate_rank(2,{},10,4),candidate_rank(2,{},99,4))
        self.assertLess(candidate_rank(2,{},99,2),candidate_rank(2,{},10,2))

    def test_content_regression_cannot_win_a_visual_tie(self):
        self.assertLess(candidate_rank(2,{'images_percent':100},10,2),candidate_rank(2,{'images_percent':70},99,2))

    def test_ties_are_stable_and_unknown_visual_values_are_safe(self):
        self.assertEqual(candidate_rank(2,{},None,5),candidate_rank(2,{},float('nan'),5))
        ranks=[candidate_rank(2,{},10,5),candidate_rank(2,{},99,5)]
        self.assertEqual(min(range(len(ranks)),key=lambda i:ranks[i]),0)

    def test_optional_wave_target_participates_in_selection(self):
        self.assertEqual(candidate_gate_distance(0,100,3,94,aim=7,min_aim=9),2)
        self.assertEqual(candidate_gate_distance(0,100,3,94,aim=9,min_aim=9),0)
        self.assertEqual(candidate_gate_distance(0,100,3,94,aim=None,min_aim=9),float('inf'))
        self.assertEqual(candidate_gate_distance(0,100,3,94),0)

    def test_rollback_retains_why_the_latest_plan_was_rejected(self):
        css='a { color: #0d6efd !important; }'
        feedback=rollback_feedback('Restore the missing search and original destinations.',
                                   [{'action':'append_css','css':css}],3,1)
        self.assertIn(css,feedback)
        self.assertIn('Do not repeat',feedback)
        self.assertIn('NOT the rejected page',feedback)
        self.assertIn('"rejected_gate_distance": 3',feedback)
        self.assertIn('"retained_gate_distance": 1',feedback)
        self.assertIn('Restore the missing search',feedback)
        from pathlib import Path
        import remediation_jobs
        source=Path(remediation_jobs.__file__).read_text()
        self.assertIn("feedback=rollback_feedback(best_feedback,patch_result['applied'],quality,best_quality)",source)

    def test_rollback_memory_is_bounded_and_explicitly_abbreviated(self):
        operations=[{'action':'replace_element','selector':'#'+str(i),'html':'x'*100000} for i in range(60)]
        feedback=rollback_feedback('Current measured feedback.',operations,3,1)
        self.assertLess(len(feedback),3400)
        self.assertIn('truncated_fields',feedback)
        self.assertIn('additional_changes_not_summarized',feedback)
        self.assertNotIn('x'*1000,feedback)
        next_feedback=rollback_feedback('Current measured feedback.',[{'action':'append_css','css':'#current {color:black}'}],2,1)
        self.assertNotIn('truncated_fields',next_feedback)
        self.assertNotIn('x'*100,next_feedback)
