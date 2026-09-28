"""One selection policy for refinement rollback and final publication.

This is a lexicographic engineering objective, not a global improvement score
or additional acceptance threshold. Born designs are not rewarded for copying
the original screenshot.
"""
import math
import json


POLICY='automated targets, then protected content; visual tie-break only for repair steps 1-3'


def candidate_rank(distance,retention,visual,step):
    def bounded(value):
        try: number=float(value)
        except (TypeError,ValueError): return 0.0
        return min(100.0,max(0.0,number)) if math.isfinite(number) else 0.0
    retention=retention or {}
    values=[bounded(retention.get(key,100.0)) for key in ('text_percent','links_percent','images_percent','dynamic_images_percent')]
    return (distance,-min(values),-values[0],-bounded(visual) if step<=3 else 0.0)


def rollback_feedback(best_feedback, applied_operations, candidate_distance, best_distance):
    """Keep rejection memory, not full prompts or stale rejected-page markup."""
    changes=[]; remaining=2400
    fields=('action','selector','name','value','css','javascript','html')
    for operation in applied_operations:
        change={field:str(operation[field])[:240] for field in fields if field in operation}
        truncated=[field for field in fields if field in operation and len(str(operation[field]))>240]
        if truncated: change['truncated_fields']=truncated
        encoded=json.dumps(change,ensure_ascii=False)
        if len(encoded)>remaining: break
        changes.append(change); remaining-=len(encoded)
    evidence={'rejected_gate_distance':candidate_distance,'retained_gate_distance':best_distance,
              'applied_changes':changes,'additional_changes_not_summarized':len(applied_operations)-len(changes)}
    return ('The previous attempt was rolled back. The current HTML and findings describe the retained best page, NOT the rejected page. '
            'Do not repeat these rejected changes; choose a different, narrowly scoped repair and continue recovering pending content/tasks. '
            'Rejected-attempt summary (long fields are explicitly abbreviated): '+json.dumps(evidence,ensure_ascii=False)
            +'\nPending feedback for the retained best page:\n'+best_feedback)
