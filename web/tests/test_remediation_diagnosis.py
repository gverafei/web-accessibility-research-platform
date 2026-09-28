import unittest
from remediation_diagnosis import diagnosis_needed,diagnosis_prompt,grounded_diagnosis
from remediation_approaches import APPROACHES


class PatchDiagnosisTests(unittest.TestCase):
    def test_all_patch_levels_are_diagnosed_but_not_initial_one_shot(self):
        for step in range(1,6): self.assertFalse(diagnosis_needed(False,False))
        self.assertTrue(diagnosis_needed(False,False,stagnant=True))
        self.assertTrue(diagnosis_needed(False,False,ambiguous=True))
        self.assertTrue(diagnosis_needed(False,False,policy='always'))
        self.assertFalse(diagnosis_needed(False,False,stagnant=True,policy='disabled'))
        self.assertFalse(diagnosis_needed(False,True))
        self.assertFalse(diagnosis_needed(True,False))
        self.assertFalse(diagnosis_needed(False,False,local_model=True))
        with self.assertRaises(ValueError): diagnosis_needed(False,False,policy='unknown')

    def test_each_prompt_contains_its_actual_permissions(self):
        for approach in APPROACHES[:3]:
            prompt=diagnosis_prompt('<button>Original</button>',[],[],'',approach)
            self.assertIn(approach.instruction,prompt)
            self.assertIn('NOT acceptance review',prompt)
        prompt=diagnosis_prompt('x'*30000,[],[],'',APPROACHES[1],True)
        self.assertIn('"context_abbreviated": true',prompt)
        self.assertIn('regenerated page',prompt)

    def test_unsupported_or_stale_recommendations_are_excluded(self):
        def finding(selector,evidence='Original',specialty='semantics'):
            return dict(specialty=specialty,selector=selector,evidence=evidence,recommendation='Use meaningful button name',rule='')
        proposal={'summary':'Focused diagnosis','findings':[finding('#go'),finding('#missing'),finding('#go','invented quote'),finding('#go',specialty='unknown')]}
        result=grounded_diagnosis(proposal,'<button id="go">Original</button>',[])
        self.assertEqual(len(result['findings']),1)
        self.assertEqual(len(result['rejected']),3)
        self.assertFalse(result['acceptance_gate'])

    def test_measured_rule_requires_matching_selector(self):
        proposal={'findings':[dict(specialty='visual',selector='#go',rule='color-contrast',evidence='Measured low contrast',recommendation='Change local foreground')]}
        source='<button id="go">Original</button>'
        self.assertEqual(len(grounded_diagnosis(proposal,source,[{'rule':'color-contrast','nodes':[{'target':['#go']}]}])['findings']),1)
        self.assertEqual(len(grounded_diagnosis(proposal,source,[{'rule':'color-contrast','nodes':[{'target':['#other']}]}])['findings']),0)
        with self.assertRaises(ValueError): grounded_diagnosis({'findings':'wrong'},source,[])

    def test_no_optional_specialist_review_remains(self):
        from pathlib import Path
        import remediation_jobs
        source=Path(remediation_jobs.__file__).read_text()
        self.assertNotIn('def specialist_reviews',source)
        self.assertNotIn('pinned_reviewer',source)
        self.assertIn('diagnosis_needed(single_shot,initial_regeneration,reconstruct,local_generator,',source)

    def test_regeneration_refinement_compares_candidate_and_source_captures(self):
        from pathlib import Path
        import remediation_jobs
        source=Path(remediation_jobs.__file__).read_text()
        self.assertIn('candidate_capture=screenshot_message(best_screenshot_path)',source)
        self.assertIn('source_capture=screenshot_message(run.get("source_screenshot_path"))',source)
        self.assertIn('the first attached capture is the best regenerated page',source)
        self.assertIn('The second, when present, is the immutable original capture',source)
