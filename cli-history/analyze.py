#!/usr/bin/env python3
"""Verify assertions against retained remote observations, not process status alone."""
import hashlib, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent
E = ROOT / 'evidence'
def raw(name): return (E / (name + '.stdout')).read_text()
def get(name): return json.loads(raw(name))
def exit_code(name): return json.loads((E / (name + '.json')).read_text())['exit']
def projection(pr, readiness=True, base=True):
    value = {k: pr[k] for k in ['id', 'node_id', 'number', 'state', 'title', 'body', 'auto_merge']}
    value['head'] = {k: pr['head'][k] for k in ['ref','sha']}
    if readiness: value['draft'] = pr['draft']
    if base: value['base'] = {k: pr['base'][k] for k in ['ref','sha']}
    return value
checks = {}
for n in [1,2]:
    a,b = get('before-url-link-pr-' + str(n)), get('after-url-link-pr-' + str(n))
    assert projection(a) == projection(b)
    assert a.get('stack') is None and b['stack']['number'] == 7
checks['canonical_url_membership_only_observed'] = raw('before-url-link-remote-refs') == raw('after-url-link-remote-refs')
assert checks['canonical_url_membership_only_observed']
a,b=get('before-base-link-pr-4'),get('after-base-link-pr-4')
assert a['base']['ref']=='main' and b['base']['ref']=='exp/cli/c'
assert projection(a,base=False)==projection(b,base=False)
checks['canonical_url_base_repair_observed']=True
assert raw('numeric-sink-before') == raw('numeric-sink-after-url') == ''
assert raw('numeric-sink-after-numbers').split()[0] == 'refs/heads/1'
checks['numeric_local_branch_pushed_before_pr_lookup']=True
assert exit_code('subprocess-lost-success')==1
assert 'refs/heads/3' not in raw('lost-signal-sink-before') and 'refs/heads/3' in raw('lost-signal-sink-after')
assert raw('before-subprocess-failure-remote-refs')==raw('after-subprocess-failure-remote-refs')
checks['injected_subprocess_failure_after_local_push']=True
for n in [3,4]:
    assert projection(get('before-reorder-link-pr-'+str(n)))==projection(get('after-reorder-link-pr-'+str(n)))
    a,b=get('before-open-reorder-link-pr-'+str(n)),get('after-open-reorder-link-pr-'+str(n))
    assert a['draft'] is True and b['draft'] is False
    assert projection(a,readiness=False)==projection(b,readiness=False)
    assert a['stack']['number']==b['stack']['number']==8
assert exit_code('reorder-link-rejected')==exit_code('open-reorder-link-rejected')==5
checks['reorder_base_changes_rejected_by_host']=True
checks['failed_reorder_with_open_persisted_readiness']=True
trace=(E/'broad-submit-origin.git-trace').read_text()
line=next(x for x in trace.splitlines() if 'built-in: git push origin ' in x)
assert '--atomic' in line and 'refs/heads/exp/cli/b:refs/heads/exp/cli/b' in line and 'refs/tags/' not in line
assert 'refs/tags/exp/cli/archive/submit-v2' in raw('after-broad-submit-local-refs')
assert 'refs/tags/exp/cli/archive/submit-v2' not in raw('after-broad-submit-remote-refs')
assert get('after-broad-submit-pr-2')['head']['sha']=='7238c801660d738d3403e1bff2ab5dd5b331b382'
checks['broad_submit_atomic_branch_only_archive_absent']=True
created,updated,replacement=get('history-create-comment'),get('history-update-comment'),get('history-create-replacement')
assert created['id']==updated['id'] and replacement['id']!=created['id']
assert get('history-get-deleted')['status']=='404' and get('history-find-after-loss')==[]
marker='<!-- gherrit-history:v1 artifact=cli-history-2026-11-08 -->'
assert len([c for c in get('history-list-reattached') if marker in c['body']])==1
assert get('history-after-v2-pr-10')['body']==get('history-after-reattach-pr-10')['body']==get('history-human-body-edit')['body']
for n in [1,2]:
    files={x['filename'] for x in get('history-exact-v'+str(n)+'-api-compare')['files']}
    assert files=={'history-change.txt'}
assert {x['filename'] for x in get('history-tips-v1-v2-api-compare')['files']}=={'history-change.txt','history-trunk-drift.txt'}
checks['history_update_preserved_comment_id_and_body_edit']=True
checks['history_loss_required_new_comment_identity']=True
checks['exact_patches_exclude_parent_drift_tip_comparison_includes_it']=True
sizes=json.loads((ROOT/'bounded-comment-size-results.json').read_text())
assert sizes['requests']==6
assert next(x for x in sizes['observations'] if x['case']=='history-cap-ascii262144')['exit']==0
assert next(x for x in sizes['observations'] if x['case']=='history-cap-ascii262145')['exit']==1
for label, req_label in [('history-cap-reconcile-read','history-cap-update-65537'),('history-cap-ascii262144-get','history-cap-ascii262144'),('history-cap-utf8-get','history-cap-utf8-262144bytes')]:
    sent=json.loads((E/(req_label+'.request.json')).read_text())['body']
    observed=get(label)['body']; assert sent==observed
checks['ascii_262144_accepted_262145_rejected_exact_hashes']=True
pin=json.loads((ROOT/'pin-result.json').read_text())
assert pin['viewerCanPin_reported'] and not pin['available_for_pr_comment']
assert pin['post_state']['isPinned'] is False
checks['pin_schema_and_permission_boolean_do_not_establish_pr_support']=True
for comment in [created,updated,replacement,get('history-cap-final-restore')]:
    assert comment['body'].count("*Authored by an AI agent acting on joshlf's behalf.*")==1
checks['retained_prose_has_one_authorship_disclosure']=True
journal=[json.loads(x) for x in (ROOT/'journal.jsonl').read_text().splitlines()]
intents={x['name'] for x in journal if x['state']=='dispatch-intent'}
receipts={x['name'] for x in journal if x['state']=='response-observed'}
assert intents==receipts
checks['every_dispatched_operation_has_a_recorded_subprocess_response']=True
result={'checks':checks, 'all_passed':all(checks.values()), 'resources':{'prs':[1,2,3,4,10], 'stacks':[7,8], 'history_comment_current_id':replacement['id'], 'history_comment_deleted_id':created['id'], 'history_comment_url':replacement['html_url'], 'size_probe_comment_id':get('history-cap-create-65536')['id']}, 'broad_submit_push_argv_trace':line, 'limits':['Subprocess receipts are not cross-resource transactions or a provider completion proof.','Same repository-owner actor; no second-role permission test.','Independent body edit was simulated by this agent.','API listing and rendered HTML are not evidence of reviewer findability or comprehension.','No server-wide Unicode rule inferred from the bounded ASCII and UTF-8 cases.']}
(ROOT/'RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
