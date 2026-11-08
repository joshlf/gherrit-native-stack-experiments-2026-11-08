from lab import *
import traceback,concurrent.futures,threading
OUT=HOME/'race-results.json';results=json.loads(OUT.read_text()) if OUT.exists() else {}
def run(name,fn):
 if name in results:return
 print('START',name,flush=True)
 try:results[name]=fn()
 except Exception as e:results[name]={'error':str(e),'traceback':traceback.format_exc()};print('ERROR',name,str(e)[:500],flush=True)
 atomic_json(OUT,results);print('END',name,json.dumps(results[name])[:1500],flush=True)
def terminal(r):return r['polls'][-1].get('data') if r.get('polls') else r['request'].get('data')
def require(r,expected):assert r['http'] in expected,{'http':r['http'],'data':r['data'],'label':r['label']};return r

def atomic_git():
 c=fixture('atomic-control',2);before=snapshot(c,'atomic-before');t=c['trunk_sha']
 a2=commit('atomic-A2',t,{'atomic-control/A.txt':'A=2\n'});b2=commit('atomic-B2',a2,{'atomic-control/B.txt':'B=2\n'})
 updates={'refs/heads/'+c['heads']['A']['ref']:a2,'refs/heads/'+c['heads']['B']['ref']:b2,'refs/tags/'+c['prefix']+'/authored/A/v2':a2,'refs/tags/'+c['prefix']+'/authored/B/v2':b2}
 expected={'refs/heads/'+c['heads']['A']['ref']:c['heads']['A']['sha'],'refs/heads/'+c['heads']['B']['ref']:''}
 rejected=push('atomic-stale-rejected',updates,expected);assert rejected['exit']!=0
 after=snapshot(c,'atomic-after-rejection');assert before['remote_refs']==after['remote_refs'],'Atomic ref vector changed after rejection'
 # Deliberately remove --atomic for one recorded disposable control.
 args=['push']+['--force-with-lease='+ref+':'+expected.get(ref,'') for ref in updates]+['origin']+[sha+':'+ref for ref,sha in updates.items()]
 intent=EVIDENCE/'nonatomic-control.intent.json';assert not intent.exists(),'Do not repeat negative control'
 atomic_json(intent,{'at':now(),'args':args});r=git(*args,check=False);atomic_json(EVIDENCE/'nonatomic-control.result.json',{'at':now(),'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 partial=snapshot(c,'nonatomic-after');a_ref='refs/heads/'+c['heads']['A']['ref'];b_ref='refs/heads/'+c['heads']['B']['ref']
 checks={'failed_status':r.returncode!=0,'A_moved':partial['remote_refs'][a_ref]==a2,'B_unchanged':partial['remote_refs'][b_ref]==c['heads']['B']['sha'],'archive_B_exists_despite_B_not_published':partial['remote_refs'].get('refs/tags/'+c['prefix']+'/authored/B/v2')==b2}
 assert all(checks.values()),checks
 repair=push('atomic-explicit-repair',{'refs/heads/'+c['heads']['B']['ref']:b2,'refs/tags/'+c['prefix']+'/authored/B/v3':b2},{b_ref:c['heads']['B']['sha']});assert repair['exit']==0
 final=snapshot(c,'atomic-repaired');return {'before':before,'atomic_reject_exit':rejected['exit'],'after_atomic':after,'nonatomic_checks':checks,'partial':partial,'final':final}

def selected_and_options():
 c=fixture('race-selected',2);before=snapshot(c,'race-selected-before');b2=commit('race-selected-B2',c['heads']['A']['sha'],{'race-selected/B.txt':'B=2\n'})
 payload={'merge_method':'squash','merge_action':'direct_merge','sha':c['heads']['B']['sha']}
 req=api('race-selected-request','PUT',f"repos/{REPO}/pulls/{c['prs']['B']}/merge-async",payload,cooldown=0)
 competing=api('race-selected-different-options','PUT',f"repos/{REPO}/pulls/{c['prs']['B']}/merge-async",dict(payload,merge_method='rebase'),cooldown=0)
 pushr=push('race-selected-head-change',{'refs/heads/'+c['heads']['B']['ref']:b2,'refs/tags/'+c['prefix']+'/authored/B/v2':b2},{'refs/heads/'+c['heads']['B']['ref']:c['heads']['B']['sha']})
 r=poll_merge(c,'B','race-selected-original',req);after=snapshot(c,'race-selected-after');fetch_case(c,'race-selected')
 return {'before':before,'original_request':req,'different_options_response':competing,'push':pushr,'original_result':r,'after':after,'note':'Observed race order only; terminal status timing is not an execution fence.'}

def downstack_change():
 c=fixture('race-downstack',3);before=snapshot(c,'race-downstack-before');a2=commit('race-downstack-A2',c['trunk_sha'],{'race-downstack/A.txt':'A=1\ndownstack-new=1\n'})
 req=api('race-downstack-request','PUT',f"repos/{REPO}/pulls/{c['prs']['C']}/merge-async",{'merge_method':'squash','merge_action':'direct_merge','sha':c['heads']['C']['sha']},cooldown=0)
 pushr=push('race-downstack-A-change',{'refs/heads/'+c['heads']['A']['ref']:a2,'refs/tags/'+c['prefix']+'/authored/A/v2':a2},{'refs/heads/'+c['heads']['A']['ref']:c['heads']['A']['sha']})
 r=poll_merge(c,'C','race-downstack-result',req);after=snapshot(c,'race-downstack-after');fetch_case(c,'race-downstack')
 trunk=after['remote_refs']['refs/heads/'+c['trunk']];text=git('show',trunk+':race-downstack/A.txt')
 return {'before':before,'request':req,'downstack_push':pushr,'result':r,'after':after,'landed_A_text':text,'note':'Selected C SHA was fixed; this case deliberately changed only A. A successful unchanged C lease is not a vector lease.'}

def unstack_overlap():
 c=fixture('race-unstack',3);before=snapshot(c,'race-unstack-before')
 req=api('race-unstack-merge-request','PUT',f"repos/{REPO}/pulls/{c['prs']['A']}/merge-async",{'merge_method':'squash','merge_action':'direct_merge','sha':c['heads']['A']['sha']},cooldown=0)
 un=api('race-unstack-during-merge','POST',f"repos/{REPO}/stacks/{c['stack']}/unstack",cooldown=0)
 during=snapshot(c,'race-unstack-during');r=poll_merge(c,'A','race-unstack-result',req)
 time.sleep(3);after=snapshot(c,'race-unstack-after')
 return {'before':before,'request':req,'unstack':un,'during':during,'result':r,'after':after}

def closed_middle():
 c=load_case('capabilities');reg=require(api('closed-middle-register','POST',f'repos/{REPO}/stacks',{'pull_requests':list(c['prs'].values())}),[201]);c['stack']=reg['data']['number'];save_case(c)
 require(api('closed-middle-close','PATCH',f"repos/{REPO}/pulls/{c['prs']['B']}",{'state':'closed'}),[200]);before=snapshot(c,'closed-middle-before')
 r=merge(c,'C','closed-middle-land-upper',sha=before['prs']['C']['head_sha']);after=snapshot(c,'closed-middle-after')
 reopen=api('closed-middle-reopen','PATCH',f"repos/{REPO}/pulls/{c['prs']['B']}",{'state':'open'})
 return {'before':before,'attempt':r,'after':after,'reopen_http':reopen['http'],'reopen':reopen['data']}

def observer():
 c=fixture('observer',4);before=snapshot(c,'observer-before')
 # A late rule failure is a separate all-prefix admission control.
 protection={'required_status_checks':{'strict':False,'contexts':['experiment/native-gate']},'enforce_admins':True,'required_pull_request_reviews':None,'restrictions':None}
 require(api('observer-protection','PUT',f"repos/{REPO}/branches/{c['trunk']}/protection",protection),[200])
 merge_shas={}
 for letter in ['A','B','C']:
  pr=require(api('observer-source-'+letter,'GET',f"repos/{REPO}/pulls/{c['prs'][letter]}",fresh=True),[200])['data'];merge_shas[letter]=pr.get('merge_commit_sha')
  for kind,sha in [('head',c['heads'][letter]['sha']),('testmerge',merge_shas[letter])]:
   if sha:require(api('observer-status-'+letter+'-'+kind,'POST',f'repos/{REPO}/statuses/{sha}',{'state':'failure' if letter=='C' else 'success','context':'experiment/native-gate','description':'Synthetic whole-prefix rule control'}),[201])
 failed=merge(c,'C','observer-rule-failure',sha=c['heads']['C']['sha']);failedstate=snapshot(c,'observer-rule-failure-after')
 if any(p['merged'] for p in failedstate['prs'].values()):return {'unexpected_partial_rule_failure':True,'request':failed,'after':failedstate}
 for kind,sha in [('head',c['heads']['C']['sha']),('testmerge',merge_shas['C'])]:
  if sha:require(api('observer-success-C-'+kind,'POST',f'repos/{REPO}/statuses/{sha}',{'state':'success','context':'experiment/native-gate','description':'Release synthetic whole-prefix gate'}),[201])
 # Keep the fixture protection: the positive phase releases only C's known
 # failing status rather than bypassing or removing the required gate.
 req=api('observer-merge-request','PUT',f"repos/{REPO}/pulls/{c['prs']['C']}/merge-async",{'merge_method':'squash','merge_action':'direct_merge','sha':c['heads']['C']['sha']},cooldown=0)
 uuid=(req.get('data') or {}).get('details',{}).get('uuid');assert uuid,req
 # A new disjoint ref is a bounded noninterference control, not proof of future scope.
 fresh=commit('observer-disjoint',c['trunk_sha'],{'disjoint.txt':'independent=1\n'})
 disjoint=push('observer-disjoint-push',{'refs/heads/exp/api/disjoint/work':fresh})
 samples=[];terminal_at=None;start=time.monotonic()
 for j in range(18):
  if terminal_at is not None and time.monotonic()-terminal_at>6:break
  jobs=[('poll',f"repos/{REPO}/pulls/{c['prs']['C']}/merge-async/{uuid}")]+[(x,f"repos/{REPO}/pulls/{c['prs'][x]}") for x in c['prs']]
  with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
   futs={pool.submit(api,'observer-s'+str(j)+'-'+x,'GET',path,fresh=True):x for x,path in jobs};row={}
   for f in concurrent.futures.as_completed(futs):
    x=futs[f];v=f.result();d=v.get('data') or {};row[x]={'start':v['start'],'end':v['end'],'http':v['http'],'data':d if x=='poll' else {k:d.get(k) for k in ['number','state','merged','merged_at','base','head','stack']}}
  row['refs_at']=now();row['refs']=git('ls-remote','origin','refs/heads/'+c['prefix']+'/*','refs/heads/exp/api/disjoint/work');samples.append(row)
  if row['poll']['data'].get('status')!='pending' and terminal_at is None:terminal_at=time.monotonic()
  if time.monotonic()-start>35:break
  time.sleep(.25)
 final=snapshot(c,'observer-after');fetch_case(c,'observer');atomic_json(EVIDENCE/'observer-detailed-samples.json',samples)
 return {'before':before,'rule_failure':failed,'rule_failure_state':failedstate,'request':req,'disjoint_push':disjoint,'disjoint_expected':fresh,'samples':samples,'after':final,'elapsed':time.monotonic()-start,'note':'Endpoint intervals overlap; read cohorts are not atomic snapshots. Bounded observation cannot prove no later writes.'}

run('atomic-git',atomic_git)
run('selected-head-and-409',selected_and_options)
run('unselected-downstack-change',downstack_change)
run('unstack-during-prefix',unstack_overlap)
run('closed-middle',closed_middle)
run('observer-and-rule-failure',observer)
print('RACES DONE',flush=True)
