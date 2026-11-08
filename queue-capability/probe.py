#!/usr/bin/env python3
"""Journal a single exact-branch merge-queue capability request."""
import datetime,hashlib,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parent
E=ROOT/'evidence'
REPO='joshlf/gherrit-native-stack-experiments-2026-11-08'
JOURNAL=ROOT/'journal.jsonl'
TRUNK='refs/heads/exp/queue/trunk'
SEED='b031070c2fd06ad94ce5b31f7f04fe5eb24c36f8'
NAME='queue-capability-2026-11-08'
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(path,value): path.write_text(json.dumps(value,indent=2)+'\n')
def event(value):
 with JOURNAL.open('a') as f:f.write(json.dumps({'time':now(),**value})+'\n')
def api(name,path,method='GET',body=None,allowed=(0,)):
 cmd=['gh','api','--method',method,'-H','Accept: application/vnd.github+json',path]
 if body is not None:
  request=E/(name+'.request.json');dump(request,body);cmd+=['--input',str(request)]
 if method!='GET':
  prior=[json.loads(x) for x in JOURNAL.read_text().splitlines()] if JOURNAL.exists() else []
  assert not any(x.get('name')==name and x['state']=='dispatch-intent' for x in prior),'Reconcile before reusing an intent'
  event({'name':name,'state':'dispatch-intent','method':method,'path':path,'body':body})
 started=now();r=subprocess.run(cmd,capture_output=True,text=True)
 (E/(name+'.stdout')).write_text(r.stdout);(E/(name+'.stderr')).write_text(r.stderr)
 dump(E/(name+'.meta.json'),{'command':cmd,'started':started,'finished':now(),'exit':r.returncode})
 if method!='GET':event({'name':name,'state':'response-observed','exit':r.returncode})
 print(name,r.returncode,r.stdout[:350],r.stderr[:350],flush=True)
 assert r.returncode in allowed,'Unexpected outcome; reconcile actual state before any further write'
 return r

def main():
 repo=json.loads(api('repository-before','repos/'+REPO).stdout)
 assert repo['full_name']==REPO and repo['owner']['type']=='User' and not repo['private']
 rules_before=json.loads(api('rulesets-before',f'repos/{REPO}/rulesets?includes_parents=true&per_page=100').stdout)
 assert not any(r['name']==NAME for r in rules_before)
 refs_before=json.loads(api('queue-refs-before',f'repos/{REPO}/git/matching-refs/heads/exp/queue/').stdout)
 assert refs_before==[]
 api('queue-seed-object',f'repos/{REPO}/git/commits/{SEED}')
 api('create-queue-trunk',f'repos/{REPO}/git/refs','POST',{'ref':TRUNK,'sha':SEED})
 rule={'name':NAME,'target':'branch','enforcement':'active','bypass_actors':[],
       'conditions':{'ref_name':{'include':[TRUNK],'exclude':[]}},
       'rules':[{'type':'merge_queue','parameters':{'check_response_timeout_minutes':5,'grouping_strategy':'ALLGREEN','max_entries_to_build':1,'max_entries_to_merge':2,'merge_method':'SQUASH','min_entries_to_merge':2,'min_entries_to_merge_wait_minutes':1}}]}
 # Validate the exact merge-queue fields against the retained primary schema before dispatch.
 schema=json.loads((ROOT/'sources/rest-api.schema.json').read_text())['components']['schemas']['repository-rule-merge-queue']['properties']['parameters']
 params=rule['rules'][0]['parameters'];assert set(params)==set(schema['required'])
 for key,value in params.items():
  definition=schema['properties'][key]
  if 'enum' in definition:assert value in definition['enum']
  if 'minimum' in definition:assert definition['minimum']<=value<=definition['maximum']
 r=api('create-queue-ruleset',f'repos/{REPO}/rulesets','POST',rule,allowed=(0,1))
 after=json.loads(api('rulesets-after',f'repos/{REPO}/rulesets?includes_parents=true&per_page=100').stdout)
 api('queue-trunk-after',f'repos/{REPO}/git/ref/heads/exp/queue/trunk')
 api('queue-refs-after',f'repos/{REPO}/git/matching-refs/heads/exp/queue/')
 api('repository-after','repos/'+REPO)
 result={'repository':REPO,'owner_type':repo['owner']['type'],'public':not repo['private'],'trunk':TRUNK,'seed':SEED,'ruleset_request_name':NAME,'ruleset_command_exit':r.returncode,'ruleset_response':json.loads(r.stdout),'matching_rulesets_after':[x for x in after if x['name']==NAME],'next_step':'inspect capability result; no PR/group/queue dispatch until rule availability is established','no_global_options_changed':True}
 dump(ROOT/'CAPABILITY.json',result)
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
