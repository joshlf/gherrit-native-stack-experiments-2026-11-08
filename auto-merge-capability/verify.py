#!/usr/bin/env python3
"""Verify retained native auto-merge rejection and repository-option restoration."""
import json,pathlib,subprocess
P=pathlib.Path(__file__).resolve().parent;E=P/'evidence'
def raw(name):return json.loads((E/(name+'.stdout')).read_text())
def plain(name):return json.loads((E/name).read_text())
def refs(snapshot):return {x['ref']:x['object']['sha'] for x in snapshot['refs']}
s=json.loads((P/'state.json').read_text())
assert plain('repository-original.json')['allow_auto_merge'] is False
assert plain('enable-flag.response.json')['allow_auto_merge'] is True
assert raw('flag-enabled-preflight')['allow_auto_merge'] is True
assert plain('restore-flag.response.json')['allow_auto_merge'] is False
assert plain('repository-restored.json')['allow_auto_merge'] is False
protection=raw('protect-exact-trunk')
assert protection['enforce_admins']['enabled'] is True
assert protection['required_status_checks']['contexts']==['exp-auto-held']
assert plain('protect-exact-trunk.request.json')['required_status_checks']['strict'] is False
before=plain('held-before-arm.snapshot.json');after=plain('after-arm.snapshot.json');final=plain('cleanup-final.snapshot.json')
assert refs(before)==refs(after)==refs(final)
assert before['stack']['number']==after['stack']['number']==final['stack']['number']==82
assert [p['number'] for p in final['stack']['pull_requests']]==[80,81]
for pos in ['lower','upper']:
 for snapshot in [before,after,final]:
  g=snapshot['graph'][pos]
  assert g['state']=='OPEN' and not g['merged'] and g['autoMergeRequest'] is None
  assert not g['isInMergeQueue'] and g['mergeQueueEntry'] is None
  assert g['headRefOid']==s['heads'][pos]['sha']
 assert before['graph'][pos]['mergeStateStatus']=='BLOCKED'
 assert before['graph'][pos]['viewerCanEnableAutoMerge'] is True
 checks=raw('required-checks-'+pos)
 assert checks==[{'bucket':'pending','link':'','name':'exp-auto-held','state':'PENDING'}]
 result=subprocess.run(['git','-C',str(P/'checkout'),'show','-s','--format=fuller',s['heads'][pos]['sha']],text=True,capture_output=True);assert result.returncode==0
 (E/('commit-'+pos+'-fuller.txt')).write_text(result.stdout)
 assert "Author:     Josh Liebow-Feeser <hello@joshlf.com>" in result.stdout
 assert result.stdout.count("Agent-authored-by: AI agent acting on joshlf's behalf")==1
rejection=raw('enable-native-auto-merge')
assert rejection['data']['enablePullRequestAutoMerge'] is None
assert any(x['type']=='UNPROCESSABLE' and x['message']=='Auto-merge is not supported for stacked pull requests.' for x in rejection['errors'])
request=plain('enable-native-auto-merge.request.json')
assert request['variables']['head']==s['heads']['lower']['sha']
assert request['variables']['body']=="Agent-authored-by: AI agent acting on joshlf's behalf"
journal=[json.loads(x) for x in (P/'journal.jsonl').read_text().splitlines()]
intents={x['name'] for x in journal if x['state']=='dispatch-intent'}
receipts={x['name'] for x in journal if x['state']=='response-observed'}
assert intents==receipts
assert not any(name.startswith('release-status-') or name.startswith('disable-auto-merge-') for name in intents)
assert s['unlanded_armed_after_cleanup']==[]
options=['allow_auto_merge','allow_merge_commit','allow_rebase_merge','allow_squash_merge','allow_update_branch','delete_branch_on_merge']
assert all(plain('repository-original.json').get(k)==plain('repository-restored.json').get(k) for k in options)
summary={'native_auto_merge_outcome':'explicitly rejected as unsupported for stacked pull requests','prs':[80,81],'stack':82,'selected_pr':80,'required_status_context':'exp-auto-held','both_members_blocked_before_request':True,'graphql_viewerCanEnableAutoMerge_reported':True,'mutation_rejected_despite_viewer_boolean':True,'repo_flag_original':False,'repo_flag_temporarily_enabled':True,'repo_flag_restored_value':False,'restoration_verified':True,'armed_requests_after_cleanup':[],'refs_unchanged_by_arm_attempt':True,'status_release_not_run':True,'landing_or_queue_behavior':'untested because request rejected','all_dispatched_effects_have_recorded_subprocess_responses':True,'refs':refs(final)}
(P/'RESULTS.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
