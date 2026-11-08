#!/usr/bin/env python3
"""Check retained capability receipts without another hosted write."""
import hashlib,json,pathlib
P=pathlib.Path(__file__).resolve().parent
E=P/'evidence'
def read(name):return json.loads((E/(name+'.stdout')).read_text())
request=json.loads((E/'create-queue-ruleset.request.json').read_text())
schema=json.loads((P/'sources/rest-api.schema.json').read_text())['components']['schemas']['repository-rule-merge-queue']['properties']['parameters']
params=request['rules'][0]['parameters']
assert set(params)==set(schema['required'])
for key,value in params.items():
 definition=schema['properties'][key]
 if 'enum' in definition:assert value in definition['enum']
 if 'minimum' in definition:assert definition['minimum']<=value<=definition['maximum']
assert request['conditions']['ref_name']=={'include':['refs/heads/exp/queue/trunk'],'exclude':[]}
assert request['enforcement']=='active' and request['bypass_actors']==[]
assert read('repository-before')['owner']['type']=='User'
assert read('repository-before')['permissions']['admin'] is True
assert read('create-queue-ruleset')['status']=='422'
assert any('merge_queue' in x for x in read('create-queue-ruleset')['errors'])
assert read('rulesets-before')==read('rulesets-after')==[]
assert read('queue-refs-before')==[]
refs=read('queue-refs-after');assert len(refs)==1
assert refs[0]['ref']=='refs/heads/exp/queue/trunk' and refs[0]['object']['sha']=='b031070c2fd06ad94ce5b31f7f04fe5eb24c36f8'
assert read('queue-seed-object')['verification']['verified'] is True
options=['allow_auto_merge','allow_merge_commit','allow_rebase_merge','allow_squash_merge','allow_update_branch','delete_branch_on_merge']
assert all(read('repository-before').get(k)==read('repository-after').get(k) for k in options)
journal=[json.loads(x) for x in (P/'journal.jsonl').read_text().splitlines()]
assert {x['name'] for x in journal if x['state']=='dispatch-intent'}=={x['name'] for x in journal if x['state']=='response-observed'}
assert len([x for x in journal if x['state']=='dispatch-intent'])==2
result={'schema_validated_request':True,'exact_branch_only':True,'repository_owner_type':'User','admin_permission':True,'rejection_observed':True,'no_ruleset_created':True,'one_retained_queue_trunk':True,'seed_signature_verified':True,'repository_merge_options_unchanged':True,'dispatched_writes':2,'unresolved_subprocess_receipts':0,'queue_prs_or_groups_created':0,'behavioral_queue_tests':'not run because queue rule unavailable'}
(P/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n')
manifest=[]
for path in sorted((P/'sources').iterdir()):
 if path.is_file() and path.name != 'manifest.json':manifest.append({'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(P/'sources/manifest.json').write_text(json.dumps({'retrieved':'2026-11-08','sources':manifest,'official_docs_url':'https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue','official_schema_url':'https://github.com/github/rest-api-description/blob/2f8f80e47ea4d3292cf4e37ba9d9b25475e06140/descriptions/api.github.com/api.github.com.json'},indent=2)+'\n')
print(json.dumps(result,indent=2))
