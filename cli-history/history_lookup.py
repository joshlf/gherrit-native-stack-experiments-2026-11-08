#!/usr/bin/env python3
"""Read-only history identity policy, checked against real and adversarial snapshots."""
import copy, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent
E = ROOT / 'evidence'
def read(name): return json.loads((E/(name+'.stdout')).read_text())

def resolve(binding, direct, listed):
    def belongs(comment):
        return (comment['user']['id'] == binding['expected_author_id']
                and comment['issue_url'] == binding['expected_issue_url']
                and binding['marker'] in comment['body'])
    if direct is not None:
        if direct['id'] != binding['current_comment_id'] or not belongs(direct):
            return {'state': 'identity-mismatch', 'identity_admitted': False}
        return {'state': 'attached', 'comment_id': direct['id'], 'identity_admitted': True}
    marked = [c for c in listed if binding['marker'] in c['body']]
    if any(not belongs(c) for c in marked):
        return {'state': 'marker-conflict', 'identity_admitted': False}
    if len(marked) > 1:
        return {'state': 'ambiguous', 'identity_admitted': False}
    if marked:
        return {'state': 'reattachment-candidate', 'comment_id': marked[0]['id'], 'identity_admitted': False}
    return {'state': 'missing', 'identity_admitted': False}

if __name__ == '__main__':
    binding=json.loads((ROOT/'history-binding.json').read_text())
    original, current = read('history-create-comment'), read('history-create-replacement')
    binding.update(expected_author_id=original['user']['id'], expected_author_login=original['user']['login'], expected_issue_url=original['issue_url'])
    (ROOT/'history-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
    observations={}
    observations['current_direct']=resolve(binding,current,[])
    assert observations['current_direct']['state']=='attached'
    observations['deleted_and_absent']=resolve(binding,None,read('history-find-after-loss'))
    assert observations['deleted_and_absent']['state']=='missing'
    observations['listed_candidate']=resolve(binding,None,[current])
    assert observations['listed_candidate']['state']=='reattachment-candidate' and not observations['listed_candidate']['identity_admitted']
    duplicate=copy.deepcopy(current); duplicate['id']+=1
    observations['duplicate_marker']=resolve(binding,None,[current,duplicate])
    assert observations['duplicate_marker']['state']=='ambiguous'
    forged=copy.deepcopy(current); forged['user']['id']+=1
    observations['foreign_actor_marker']=resolve(binding,None,[forged])
    assert observations['foreign_actor_marker']['state']=='marker-conflict'
    edited=copy.deepcopy(current); edited['body']='human removed the marker'
    observations['direct_identity_edit']=resolve(binding,edited,[])
    assert observations['direct_identity_edit']['state']=='identity-mismatch'
    moved=copy.deepcopy(current); moved['issue_url']+='/different'
    observations['direct_wrong_pr']=resolve(binding,moved,[])
    assert observations['direct_wrong_pr']['state']=='identity-mismatch'
    assert all(not v['identity_admitted'] for k,v in observations.items() if k!='current_direct')
    result={'observations':observations,'scope':'read-only local prototype; adversarial rows are synthetic snapshots, not extra GitHub writes','policy':'Identity admission alone grants no mutation authority or freshness guarantee. Known ID must retain artifact marker, bound author and PR. Lost ID listing produces evidence/candidates, never automatic replacement or permission to overwrite. Duplicate/foreign markers stop. Any reattachment requires a recorded decision and pending-write reconciliation.'}
    (ROOT/'history-identity-policy-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
