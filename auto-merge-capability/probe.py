#!/usr/bin/env python3
"""Journal a small held native-stack auto-merge experiment; never retry writes."""
import datetime,json,os,pathlib,subprocess,time,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parent;E=ROOT/'evidence';REPO='joshlf/gherrit-native-stack-experiments-2026-11-08';R='repos/'+REPO
CHECKOUT=ROOT/'checkout';STATE=ROOT/'state.json';J=ROOT/'journal.jsonl'
SEED='b031070c2fd06ad94ce5b31f7f04fe5eb24c36f8';CONTEXT='exp-auto-held';NOTICE="*Authored by an AI agent acting on joshlf's behalf.*"
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def event(value):
 with J.open('a') as f:f.write(json.dumps({'at':now(),**value})+'\n')
def run(name,cmd,cwd=ROOT,write=None,allowed=(0,)):
 if write is not None:
  old=[json.loads(x) for x in J.read_text().splitlines()] if J.exists() else []
  assert not any(x.get('name')==name and x.get('state')=='dispatch-intent' for x in old),'Reconcile previous dispatch before reusing '+name
  event({'name':name,'state':'dispatch-intent','command':cmd,'intent':write})
 start=now();r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True)
 (E/(name+'.stdout')).write_text(r.stdout);(E/(name+'.stderr')).write_text(r.stderr)
 dump(E/(name+'.meta.json'),{'command':cmd,'cwd':str(cwd),'start':start,'end':now(),'exit':r.returncode})
 if write is not None:event({'name':name,'state':'response-observed','exit':r.returncode})
 print(name,r.returncode,r.stdout[:160].strip(),r.stderr[:220].strip(),flush=True)
 assert r.returncode in allowed,'Unexpected outcome; reconcile before further write: '+name
 return r

def api(name,path,method='GET',body=None,allowed=(0,)):
 cmd=['gh','api','--method',method,'-H','Accept: application/vnd.github+json',path]
 if body is not None:
  p=E/(name+'.request.json');dump(p,body);cmd+=['--input',str(p)]
 return run(name,cmd,write={'method':method,'path':path,'body':body} if method!='GET' else None,allowed=allowed)
def git(name,*args,write=None):return run(name,['git','-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false',*args],cwd=CHECKOUT,write=write).stdout.strip()
def gql(name,query,variables,write=False,allowed=(0,)):
 p=E/(name+'.request.json');dump(p,{'query':query,'variables':variables})
 return run(name,['gh','api','graphql','--input',str(p)],write={'query':query,'variables':variables} if write else None,allowed=allowed)
def save(d):dump(STATE,d)
FIELDS='id number state merged mergedAt headRefOid baseRefName baseRefOid mergeStateStatus viewerCanEnableAutoMerge viewerCanDisableAutoMerge isInMergeQueue isMergeQueueEnabled autoMergeRequest { enabledAt mergeMethod enabledBy { login } } mergeQueueEntry { id }'
def graph(d,label):
 query='query($a:ID!,$b:ID!){ lower:node(id:$a){... on PullRequest {'+FIELDS+'}} upper:node(id:$b){... on PullRequest {'+FIELDS+'}} }'
 return json.loads(gql(label,query,{'a':d['prs']['lower']['node_id'],'b':d['prs']['upper']['node_id']}).stdout)['data']
def snapshot(d,label):
 data={'at':now(),'graph':graph(d,label+'-graphql'),'prs':{}}
 for p in ['lower','upper']:data['prs'][p]=json.loads(api(label+'-'+p+'-pr',R+'/pulls/'+str(d['prs'][p]['number'])).stdout)
 data['refs']=json.loads(api(label+'-refs',R+'/git/matching-refs/heads/exp/auto/').stdout)
 if 'stack' in d:data['stack']=json.loads(api(label+'-stack',R+'/stacks/'+str(d['stack']['number'])).stdout)
 dump(E/(label+'.snapshot.json'),data);return data

def setup():
 assert not STATE.exists(),'Use recorded state for recovery; do not recreate'
 assert json.loads(api('flag-enabled-preflight',R).stdout)['allow_auto_merge'] is True
 assert json.loads(api('namespace-preflight',R+'/git/matching-refs/heads/exp/auto/').stdout)==[]
 run('clone',['git','-c','core.hooksPath=/dev/null','clone','https://github.com/'+REPO+'.git',str(CHECKOUT)],write={'local_clone':str(CHECKOUT)})
 git('local-name','config','--local','user.name','Josh Liebow-Feeser',write={'local_config':'user.name'})
 git('local-email','config','--local','user.email','hello@joshlf.com',write={'local_config':'user.email'})
 git('local-hooks','config','--local','core.hooksPath','/dev/null',write={'local_config':'core.hooksPath'})
 git('trunk-branch','branch','exp/auto/trunk',SEED,write={'local_branch':'exp/auto/trunk'})
 d={'seed':SEED,'heads':{},'prs':{},'held_targets':[]};save(d)
 parent='exp/auto/trunk'
 for p in ['lower','upper']:
  branch='exp/auto/'+p;git('checkout-'+p,'checkout','-b',branch,parent,write={'local_branch':branch})
  file='auto-'+p+'.txt';(CHECKOUT/file).write_text('Synthetic auto-merge '+p+' layer.\n')
  git('stage-'+p,'add',file,write={'index_path':file})
  git('commit-'+p,'commit','-m',"Record synthetic auto-merge "+p+" layer\n\nAgent-authored-by: AI agent acting on joshlf's behalf",write={'commit_branch':branch})
  d['heads'][p]={'ref':branch,'sha':git('sha-'+p,'rev-parse','HEAD')};save(d);parent=branch
 refs=['refs/heads/exp/auto/'+p+':refs/heads/exp/auto/'+p for p in ['trunk','lower','upper']]
 git('push-fixture','push','--atomic',*['--force-with-lease='+s.split(':')[1]+':' for s in refs],'origin',*refs,write={'absent_refs':refs})
 endpoint=R+'/branches/'+urllib.parse.quote('exp/auto/trunk',safe='')+'/protection'
 protection={'required_status_checks':{'strict':False,'contexts':[CONTEXT]},'enforce_admins':True,'required_pull_request_reviews':None,'restrictions':None}
 api('protect-exact-trunk',endpoint,'PUT',protection);d['protection_endpoint']=endpoint;save(d)
 for p in ['lower','upper']:
  sha=d['heads'][p]['sha'];api('hold-head-'+p,R+'/statuses/'+sha,'POST',{'state':'pending','context':CONTEXT,'description':'Synthetic hold before native auto-merge probe'})
  d['held_targets'].append(sha);save(d)
 parent='exp/auto/trunk'
 for p in ['lower','upper']:
  pr=json.loads(api('create-pr-'+p,R+'/pulls','POST',{'head':d['heads'][p]['ref'],'base':parent,'title':'Auto-merge experiment '+p,'body':'Synthetic held native auto-merge capability probe.\n\n'+NOTICE,'draft':False}).stdout)
  d['prs'][p]={'number':pr['number'],'node_id':pr['node_id']};save(d);parent=d['heads'][p]['ref']
 d['stack']=json.loads(api('register-stack',R+'/stacks','POST',{'pull_requests':[d['prs'][p]['number'] for p in ['lower','upper']]}).stdout);save(d)
 before=snapshot(d,'before-arm')
 for p in ['lower','upper']:
  pr=before['prs'][p]
  if pr.get('merge_commit_sha') and pr['merge_commit_sha'] not in d['held_targets']:
   target=pr['merge_commit_sha'];api('hold-testmerge-'+p,R+'/statuses/'+target,'POST',{'state':'pending','context':CONTEXT,'description':'Synthetic hold on observed test-merge revision'})
   d['held_targets'].append(target);save(d)
  run('required-checks-'+p,['gh','pr','checks',str(pr['number']),'--repo',REPO,'--required','--json','name,state,bucket,link'],allowed=(0,1,8))
 held=snapshot(d,'held-before-arm')
 assert all(not v['merged'] and v['autoMergeRequest'] is None for v in held['graph'].values())
 assert held['graph']['lower']['mergeStateStatus']=='BLOCKED','Held check must actually block selected PR before arming'
 return d

def arm_and_observe(d):
 query='mutation($id:ID!,$head:GitObjectID!,$body:String!){ enablePullRequestAutoMerge(input:{pullRequestId:$id,expectedHeadOid:$head,mergeMethod:SQUASH,commitBody:$body,clientMutationId:"native-auto-capability"}) { clientMutationId pullRequest { '+FIELDS+' } } }'
 started=time.monotonic();receipt=gql('enable-native-auto-merge',query,{'id':d['prs']['lower']['node_id'],'head':d['heads']['lower']['sha'],'body':"Agent-authored-by: AI agent acting on joshlf's behalf"},write=True,allowed=(0,1))
 d['enable_response']=json.loads(receipt.stdout);d['enable_exit']=receipt.returncode;save(d)
 armed=snapshot(d,'after-arm');d['after_arm_graph']=armed['graph'];save(d)
 request=armed['graph']['lower']['autoMergeRequest']
 if request is None:
  d['outcome']='rejected or no armed request; exact response retained';save(d);return
 assert not armed['graph']['lower']['merged'],'Hold should prevent immediate landing'
 d['outcome']='armed while required checks held';save(d)
 for index,target in enumerate(d['held_targets']):
  api('release-status-'+str(index),R+'/statuses/'+target,'POST',{'state':'success','context':CONTEXT,'description':'Release synthetic native auto-merge hold'})
 polls=[]
 while time.monotonic()-started<45:
  sample={'at':now(),'elapsed':time.monotonic()-started,'graph':graph(d,'observe-'+str(len(polls)))}
  sample['refs']=json.loads(api('observe-'+str(len(polls))+'-refs',R+'/git/matching-refs/heads/exp/auto/').stdout)
  polls.append(sample);d['polls']=polls;save(d)
  if sample['graph']['lower']['merged']:
   d['outcome']='selected lower prefix landed after status release';save(d);break
  time.sleep(min(3,max(0,45-(time.monotonic()-started))))
 snapshot(d,'after-observation')

def cleanup(d):
 if not all(p in d.get('prs',{}) for p in ['lower','upper']):return
 observed=graph(d,'cleanup-before')
 for p in ['lower','upper']:
  if observed[p]['autoMergeRequest'] is not None and not observed[p]['merged']:
   q='mutation($id:ID!){ disablePullRequestAutoMerge(input:{pullRequestId:$id,clientMutationId:"native-auto-cleanup-'+p+'"}){clientMutationId pullRequest { id state autoMergeRequest { enabledAt } }}}'
   gql('disable-auto-merge-'+p,q,{'id':d['prs'][p]['node_id']},write=True,allowed=(0,1))
 final=snapshot(d,'cleanup-final');d['cleanup_graph']=final['graph'];d['unlanded_armed_after_cleanup']=[p for p,v in final['graph'].items() if not v['merged'] and v['autoMergeRequest'] is not None];save(d)
 assert not d['unlanded_armed_after_cleanup'],'Unlanded auto-merge remains armed; operator reconciliation required'

if __name__=='__main__':
 d={}
 try:
  d=setup();arm_and_observe(d)
 finally:
  if STATE.exists():cleanup(json.loads(STATE.read_text()))
