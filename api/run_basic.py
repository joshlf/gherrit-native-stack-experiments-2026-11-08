from lab import *
import traceback
OUT=HOME/'basic-results.json'
results=json.loads(OUT.read_text()) if OUT.exists() else {}
def run(name,fn):
 if name in results:return
 print('START',name,flush=True)
 try:results[name]=fn()
 except Exception as e:results[name]={'error':str(e),'traceback':traceback.format_exc()};print('ERROR',name,str(e)[:300],flush=True)
 atomic_json(OUT,results);print('END',name,json.dumps(results[name])[:1500],flush=True)
def capabilities():
 c=fixture('capabilities',count=1,register=False)
 singleton=api('caps-singleton','POST',f'repos/{REPO}/stacks',{'pull_requests':[c['prs']['A']]})
 parent=c['heads']['A'];b=commit('caps-B',parent['sha'],{'capabilities/B.txt':'B=1\n'})
 ref=c['prefix']+'/B';p=push('caps-B-push',{'refs/heads/'+ref:b,'refs/tags/'+c['prefix']+'/authored/B/v1':b});assert p['exit']==0
 pr=api('caps-B-pr','POST',f'repos/{REPO}/pulls',{'head':ref,'base':parent['ref'],'title':'Experiment capabilities: B','body':'Synthetic append fixture.\n\n'+NOTICE});assert pr['http']==201,pr
 c['heads']['B']={'ref':ref,'sha':b};c['prs']['B']=pr['data']['number'];save_case(c)
 reg=api('caps-register','POST',f'repos/{REPO}/stacks',{'pull_requests':list(c['prs'].values())});assert reg['http']==201,reg
 c['stack']=reg['data']['number'];save_case(c)
 duplicate=api('caps-duplicate-create','POST',f'repos/{REPO}/stacks',{'pull_requests':list(c['prs'].values())})
 cc=commit('caps-C',b,{'capabilities/C.txt':'C=1\n'});refc=c['prefix']+'/C'
 assert push('caps-C-push',{'refs/heads/'+refc:cc,'refs/tags/'+c['prefix']+'/authored/C/v1':cc})['exit']==0
 prc=api('caps-C-pr','POST',f'repos/{REPO}/pulls',{'head':refc,'base':ref,'title':'Experiment capabilities: C','body':'Synthetic append fixture.\n\n'+NOTICE});assert prc['http']==201
 c['heads']['C']={'ref':refc,'sha':cc};c['prs']['C']=prc['data']['number'];save_case(c)
 add=api('caps-append','POST',f"repos/{REPO}/stacks/{c['stack']}/add",{'pull_requests':[c['prs']['C']]})
 adddup=api('caps-append-duplicate','POST',f"repos/{REPO}/stacks/{c['stack']}/add",{'pull_requests':[c['prs']['C']]})
 closed=api('caps-close-middle','PATCH',f"repos/{REPO}/pulls/{c['prs']['B']}",{'state':'closed'})
 s1=snapshot(c,'caps-closed')
 reopened=api('caps-reopen-middle','PATCH',f"repos/{REPO}/pulls/{c['prs']['B']}",{'state':'open'})
 s2=snapshot(c,'caps-reopened')
 un=api('caps-unstack','POST',f"repos/{REPO}/stacks/{c['stack']}/unstack")
 s3=snapshot(c,'caps-unstacked')
 again=api('caps-unstack-again-controlled','POST',f"repos/{REPO}/stacks/{c['stack']}/unstack")
 return {'prs':c['prs'],'stack':c['stack'],'single_create_http':singleton['http'],'duplicate_create_http':duplicate['http'],'append_http':add['http'],'append_duplicate_http':adddup['http'],'closed_http':closed['http'],'closed_state':s1['prs']['B'],'reopen_http':reopened['http'],'reopened_state':s2['prs']['B'],'unstack_http':un['http'],'unstack_again_http':again['http'],'post_unstack_pr_states':s3['prs'],'post_unstack_resource':s3['stack']}
def merge_case(method):
 c=fixture('merge-'+method,3)
 before=snapshot(c,'merge-'+method+'-before')
 # The legacy synchronous endpoint is a deliberate negative control.
 sync=api('merge-'+method+'-sync-negative','PUT',f"repos/{REPO}/pulls/{c['prs']['A']}/merge",{'merge_method':method,'sha':c['heads']['A']['sha']})
 if sync['http']==200:
  return {'unexpected_sync_merge':True,'sync':sync,'after':snapshot(c,'merge-'+method+'-sync-actual')}
 r=merge(c,'A','merge-'+method+'-prefix',method=method)
 timeline=[];start=time.monotonic()
 for j in range(4):
  if j:time.sleep(2 if j<3 else 5)
  snap=snapshot(c,'merge-'+method+'-after-'+str(j));timeline.append({'elapsed':time.monotonic()-start,'snapshot':snap})
 final=timeline[-1]['snapshot'];fetch_case(c,'merge-'+method+'-prefix')
 commits={}
 for letter,p in final['prs'].items():
  sha=p['head_sha'];g=api('merge-'+method+'-commit-'+letter,'GET',f'repos/{REPO}/git/commits/{sha}',fresh=True)
  if g['http']==200:
   d=g['data'];commits[letter]={'sha':sha,'tree':d['tree']['sha'],'parents':[v['sha'] for v in d['parents']],'author':d['author'],'committer':d['committer'],'verification':d.get('verification')}
 trunksha=final['remote_refs'].get('refs/heads/'+c['trunk']);trunkfiles=git('ls-tree','-r','--name-only',trunksha) if trunksha else None
 complete=merge(c,'C','merge-'+method+'-complete',method=method,sha=final['prs']['C']['head_sha'])
 final2=snapshot(c,'merge-'+method+'-complete-after');fetch_case(c,'merge-'+method+'-complete')
 mergedtrunk=final2['remote_refs'].get('refs/heads/'+c['trunk']);allfiles=git('ls-tree','-r','--name-only',mergedtrunk) if mergedtrunk else None
 verification=api('merge-'+method+'-trunk-commit','GET',f'repos/{REPO}/git/commits/{mergedtrunk}',fresh=True) if mergedtrunk else None
 complete_unstack=api('merge-'+method+'-complete-unstack','POST',f"repos/{REPO}/stacks/{c['stack']}/unstack")
 result={'prs':c['prs'],'stack':c['stack'],'legacy_sync_http':sync['http'],'prefix_request':r,'timeline':timeline,'prefix_trunk_files':trunkfiles,'suffix_commit_metadata':commits,'complete_request':complete,'complete_state':final2,'complete_trunk_files':allfiles,'complete_unstack_http':complete_unstack['http'],'trunk_verification':verification['data'].get('verification') if verification and verification['http']==200 else None,'trunk_sha':mergedtrunk}
 # A completed group cannot accept a newly authored follow-up; preserve old history.
 if method=='squash' and final2['prs']['C']['merged']:
  dsha=commit('complete-D',mergedtrunk,{'complete/D.txt':'D=1\n'});dref=c['prefix']+'/D'
  assert push('complete-D-push',{'refs/heads/'+dref:dsha,'refs/tags/'+c['prefix']+'/authored/D/v1':dsha})['exit']==0
  pd=api('complete-D-pr','POST',f'repos/{REPO}/pulls',{'head':dref,'base':c['heads']['C']['ref'],'title':'Experiment complete group: D','body':'Synthetic complete-group continuation.\n\n'+NOTICE});assert pd['http']==201,pd
  ap=api('complete-append-rejected','POST',f"repos/{REPO}/stacks/{c['stack']}/add",{'pull_requests':[pd['data']['number']]})
  ret=api('complete-D-to-trunk','PATCH',f"repos/{REPO}/pulls/{pd['data']['number']}",{'base':c['trunk']})
  esha=commit('complete-E',dsha,{'complete/E.txt':'E=1\n'});eref=c['prefix']+'/E'
  assert push('complete-E-push',{'refs/heads/'+eref:esha,'refs/tags/'+c['prefix']+'/authored/E/v1':esha})['exit']==0
  pe=api('complete-E-pr','POST',f'repos/{REPO}/pulls',{'head':eref,'base':dref,'title':'Experiment complete group: E','body':'Synthetic new-group continuation.\n\n'+NOTICE});assert pe['http']==201
  new=api('complete-new-group','POST',f'repos/{REPO}/stacks',{'pull_requests':[pd['data']['number'],pe['data']['number']]})
  result['continuation']={'D':pd['data']['number'],'E':pe['data']['number'],'append_old_http':ap['http'],'append_old_response':ap['data'],'retarget_http':ret['http'],'new_group_http':new['http'],'new_group':new['data']}
 return result
run('capabilities',capabilities)
for method in ['merge','squash','rebase']:run('merge-'+method,lambda m=method:merge_case(m))
print('BASIC DONE',str(OUT),flush=True)
