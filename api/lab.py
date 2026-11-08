"""Small, recorded native GitHub experiment operations; never retry uncertain writes."""
from pathlib import Path
import subprocess,json,time,datetime,os,re,hashlib
REPO='joshlf/gherrit-native-stack-experiments-2026-11-08'
ROOT=Path(__file__).resolve().parents[1]
HOME=ROOT/'api'; EVIDENCE=HOME/'evidence'; EVIDENCE.mkdir(exist_ok=True)
GIT=HOME/'git'; STATE=HOME/'resources.json'
NOTICE="*Authored by an AI agent acting on joshlf's behalf.*"
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def safe(label):
 assert re.fullmatch('[a-zA-Z0-9_.-]+',label),label
 return label
def atomic_json(p,data):
 p=Path(p);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');os.replace(tmp,p)
def command(args,*,cwd=None,input=None,env=None):
 return subprocess.run(args,cwd=cwd,input=input,capture_output=True,text=True,env=env)
def api(label,method,path,payload=None,*,fresh=False,cooldown=1):
 safe(label)
 if fresh:
  original=label;generation=1
  while (EVIDENCE/(label+'.intent.json')).exists():
   generation+=1;label=original+'-read-'+str(generation)
 prefix=EVIDENCE/label;meta=Path(str(prefix)+'.meta.json')
 if meta.exists() and not fresh:
  old=json.loads(meta.read_text());assert old['method']==method and old['path']==path and old.get('payload')==payload
  return old
 intent=Path(str(prefix)+'.intent.json')
 if intent.exists() and not fresh:raise RuntimeError('Unresolved prior dispatch: '+label)
 record={'label':label,'method':method,'path':path,'payload':payload,'start':now(),'monotonic_start':time.monotonic()}
 atomic_json(intent,record)
 args=['gh','api','--include','-H','X-GitHub-Api-Version: 2026-03-10','-X',method,path]
 if payload is not None:
  p=Path(str(prefix)+'.request.json');p.write_text(json.dumps(payload));args+=['--input',str(p)]
 r=command(args);record['end']=now();record['monotonic_end']=time.monotonic();record['exit']=r.returncode
 Path(str(prefix)+'.response.txt').write_text(r.stdout);Path(str(prefix)+'.stderr.txt').write_text(r.stderr)
 match=re.search(r'^HTTP/\S+\s+(\d+)',r.stdout);record['http']=int(match.group(1)) if match else None
 parts=re.split(r'\r?\n\r?\n',r.stdout,maxsplit=1);raw=parts[1] if len(parts)>1 else ''
 try:record['data']=json.loads(raw) if raw.strip() else None
 except json.JSONDecodeError:record['data']=None;record['parse_error']=raw[:500]
 atomic_json(meta,record)
 if method not in ('GET','HEAD') and cooldown:time.sleep(cooldown)
 return record
def git(*args,input=None,env=None,check=True):
 r=command(['git','-C',str(GIT),*args],input=input,env=env)
 if check and r.returncode:raise RuntimeError('git '+str(args)+' '+r.stderr)
 return r.stdout.strip() if check else r
def init():
 if not (GIT/'.git').exists():
  r=command(['git','clone','--single-branch','--branch','main','https://github.com/'+REPO+'.git',str(GIT)])
  (EVIDENCE/'clone.stdout').write_text(r.stdout);(EVIDENCE/'clone.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
  git('config','core.hooksPath',str(ROOT/'empty-hooks'));git('config','user.name','Josh Liebow-Feeser');git('config','user.email','hello@joshlf.com')
 return git('rev-parse','refs/remotes/origin/main')
def commit(label,parent,files,subject=None):
 safe(label);p=EVIDENCE/(label+'.commit.json')
 if p.exists():return json.loads(p.read_text())['sha']
 index=HOME/(label+'.index');env=dict(os.environ,GIT_INDEX_FILE=str(index))
 git('read-tree',parent,env=env)
 for path,value in files.items():
  assert not path.startswith('/') and '..' not in Path(path).parts
  if value is None:git('update-index','--force-remove','--',path,env=env)
  else:
   blob=git('hash-object','-w','--stdin',input=value)
   git('update-index','--add','--cacheinfo','100644,'+blob+','+path,env=env)
 tree=git('write-tree',env=env)
 message=(subject or 'Record synthetic '+label)+'\n\nAgent-authored-by: AI agent acting on joshlf\'s behalf\n'
 sha=git('commit-tree',tree,'-p',parent,input=message)
 git('update-ref','refs/experiment-inputs/'+label,sha)
 atomic_json(p,{'sha':sha,'tree':tree,'parent':parent,'files':files,'message':message})
 return sha
def push(label,updates,expected=None,option=None):
 safe(label);p=EVIDENCE/(label+'.push.json')
 if p.exists():return json.loads(p.read_text())
 intent=EVIDENCE/(label+'.push-intent.json')
 if intent.exists():raise RuntimeError('Unresolved Git dispatch '+label)
 expected=expected or {};args=['push','--atomic']
 for ref in updates:
  assert ref.startswith(('refs/heads/exp/api/','refs/tags/exp/api/'))
  args+=['--force-with-lease='+ref+':'+expected.get(ref,'')]
 if option:args+=['-o',option]
 args+=['origin'];args += [sha+':'+ref for ref,sha in updates.items()]
 record={'start':now(),'updates':updates,'expected':expected,'args':args}
 atomic_json(intent,record);r=git(*args,check=False);record.update(end=now(),exit=r.returncode,stdout=r.stdout,stderr=r.stderr);atomic_json(p,record)
 return record
def save_case(case):
 state=json.loads(STATE.read_text()) if STATE.exists() else {};state[case['name']]=case;atomic_json(STATE,state)
def load_case(name):return json.loads(STATE.read_text()).get(name) if STATE.exists() else None
def fixture(name,count=3,register=True):
 case=load_case(name)
 if not case:
  seed=init();prefix='exp/api/'+name;trunk=prefix+'/trunk';trunksha=commit(name+'-trunk',seed,{name+'/base.txt':'base=0\n'})
  heads={};updates={'refs/heads/'+trunk:trunksha};parent=trunksha
  for letter in 'ABCDE'[:count]:
   sha=commit(name+'-'+letter,parent,{name+'/'+letter+'.txt':letter+'=1\n'})
   heads[letter]={'ref':prefix+'/'+letter,'sha':sha};updates['refs/heads/'+heads[letter]['ref']]=sha;updates['refs/tags/'+prefix+'/authored/'+letter+'/v1']=sha;parent=sha
  pushed=push(name+'-initial',updates);assert pushed['exit']==0,pushed
  case={'name':name,'prefix':prefix,'trunk':trunk,'trunk_sha':trunksha,'heads':heads,'prs':{},'created':now()};save_case(case)
 parentref=case['trunk']
 for letter,h in case['heads'].items():
  if letter not in case['prs']:
   r=api(name+'-pr-'+letter,'POST',f'repos/{REPO}/pulls',{'head':h['ref'],'base':parentref,'title':'Experiment '+name+': '+letter,'body':'Synthetic native-stack fixture '+name+' / '+letter+'.\n\n'+NOTICE})
   assert r['http']==201,r;case['prs'][letter]=r['data']['number'];save_case(case)
  parentref=h['ref']
 if register and not case.get('stack'):
  r=api(name+'-register','POST',f'repos/{REPO}/stacks',{'pull_requests':list(case['prs'].values())});assert r['http']==201,r
  case['stack']=r['data']['number'];save_case(case)
 return case
def snapshot(case,label):
 original=label;generation=1
 while (EVIDENCE/(label+'.snapshot.json')).exists():
  generation+=1;label=original+'-sample-'+str(generation)
 data={'at':now(),'label':label,'prs':{},'stack':None,'remote_refs':{}}
 for letter,number in case['prs'].items():
  r=api(label+'-pr-'+letter,'GET',f'repos/{REPO}/pulls/{number}',fresh=True)
  if r['http']==200:
   p=r['data'];data['prs'][letter]={'number':number,'state':p['state'],'merged':p['merged'],'merged_at':p['merged_at'],'base':p['base']['ref'],'base_sha':p['base']['sha'],'head':p['head']['ref'],'head_sha':p['head']['sha'],'draft':p['draft'],'stack':p.get('stack'),'node_id':p['node_id'],'mergeable':p.get('mergeable'),'mergeable_state':p.get('mergeable_state')}
 if case.get('stack'):
  r=api(label+'-stack','GET',f"repos/{REPO}/stacks/{case['stack']}",fresh=True);data['stack']={'http':r['http'],'data':r['data']}
 raw=git('ls-remote','origin','refs/heads/'+case['prefix']+'/*','refs/tags/'+case['prefix']+'/*')
 for line in raw.splitlines():
  sha,ref=line.split('\t');data['remote_refs'][ref]=sha
 atomic_json(EVIDENCE/(label+'.snapshot.json'),data);return data
def poll_merge(case,letter,label,request,timeout=45):
 data=request.get('data') or {};details=data.get('details',{});uuid=details.get('uuid');polls=[]
 if request.get('http')==409:
  expected=request.get('payload') or {}
  assert all(details.get(k)==expected.get(k) for k in ['merge_method','merge_action']), '409 names another intent'
  assert details.get('expected_head_sha')==expected.get('sha'), '409 names another selected head'
 if not uuid:return {'request':request,'polls':polls}
 start=time.monotonic()
 for i in range(30):
  r=api(label+'-poll-'+str(i),'GET',f"repos/{REPO}/pulls/{case['prs'][letter]}/merge-async/{uuid}",fresh=True);polls.append(r)
  if r.get('data',{}).get('status')!='pending':break
  if time.monotonic()-start>timeout:break
  time.sleep(1)
 return {'request':request,'polls':polls,'elapsed':time.monotonic()-start}
def merge(case,letter,label,method='squash',action='direct_merge',sha=None):
 p={'merge_method':method,'merge_action':action,'sha':sha or case['heads'][letter]['sha']}
 r=api(label+'-request','PUT',f"repos/{REPO}/pulls/{case['prs'][letter]}/merge-async",p)
 return poll_merge(case,letter,label,r)
def fetch_case(case,label):
 r=git('fetch','origin','+refs/heads/'+case['prefix']+'/*:refs/remotes/observed/'+case['name']+'/*',check=False)
 atomic_json(EVIDENCE/(label+'.fetch.json'),{'at':now(),'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr});return r.returncode
