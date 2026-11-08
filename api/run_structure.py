from lab import *
import traceback
OUT=HOME/'structure-results.json';results=json.loads(OUT.read_text()) if OUT.exists() else {}
def run(name,fn):
 if name in results:return
 print('START',name,flush=True)
 try:results[name]=fn()
 except Exception as e:results[name]={'error':str(e),'traceback':traceback.format_exc()};print('ERROR',name,str(e)[:500],flush=True)
 atomic_json(OUT,results);print('END',name,json.dumps(results[name])[:1600],flush=True)
def require(r,statuses):
 assert r['http'] in statuses, {'http':r['http'],'data':r['data'],'label':r['label']};return r

def transition(c,label,order,newheads,*,create=(),withdraw=(),trunk=None):
 before=snapshot(c,label+'-before');oldstack=c['stack'];targettrunk=trunk or c['trunk']
 un=require(api(label+'-unstack','POST',f'repos/{REPO}/stacks/{oldstack}/unstack'),[200,204]);released=snapshot(c,label+'-released')
 residual=un.get('data');eligible=[x for x in before['prs'] if before['prs'][x]['state']=='open' and not before['prs'][x]['merged']]
 for letter in eligible:
  # All members are parked deliberately, even if a base already equals trunk.
  require(api(label+'-park-'+letter,'PATCH',f"repos/{REPO}/pulls/{c['prs'][letter]}",{'base':targettrunk}),[200])
 parked=snapshot(c,label+'-parked')
 for letter in eligible:assert parked['prs'][letter]['base']==targettrunk
 updates={};expected={}
 for letter,h in newheads.items():
  ref='refs/heads/'+h['ref'];updates[ref]=h['sha'];expected[ref]=before['remote_refs'].get(ref,'')
  updates['refs/tags/'+c['prefix']+'/authored/'+letter+'/'+label]=h['sha']
 if trunk:
  sha=git('rev-parse','refs/remotes/observed/'+c['name']+'/trunk2');updates['refs/heads/'+trunk]=sha;expected['refs/heads/'+trunk]=before['remote_refs'].get('refs/heads/'+trunk,'')
 pr=push(label+'-push',updates,expected);assert pr['exit']==0,pr
 for letter in create:
  h=newheads[letter];base=targettrunk if order.index(letter)==0 else newheads[order[order.index(letter)-1]]['ref']
  r=require(api(label+'-create-'+letter,'POST',f'repos/{REPO}/pulls',{'head':h['ref'],'base':base,'title':'Experiment '+label+': '+letter,'body':'Synthetic canonical-review structural fixture.\n\n'+NOTICE}),[201]);c['prs'][letter]=r['data']['number']
 for letter in withdraw:require(api(label+'-withdraw-'+letter,'PATCH',f"repos/{REPO}/pulls/{c['prs'][letter]}",{'state':'closed'}),[200])
 for j,letter in enumerate(order):
  base=targettrunk if j==0 else newheads[order[j-1]]['ref']
  require(api(label+'-final-base-'+letter,'PATCH',f"repos/{REPO}/pulls/{c['prs'][letter]}",{'base':base}),[200])
 reg=require(api(label+'-register','POST',f'repos/{REPO}/stacks',{'pull_requests':[c['prs'][x] for x in order]}),[201]) if len(order)>=2 else None
 c['heads'].update(newheads);c['stack']=reg['data']['number'] if reg else None;c['trunk']=targettrunk;save_case(c)
 after=snapshot(c,label+'-after');fetch_case(c,label)
 checks={}
 for letter in order:
  p=after['prs'][letter];checks[letter]={'same_pr':p['number']==c['prs'][letter],'same_node':letter not in before['prs'] or p['node_id']==before['prs'][letter]['node_id'],'open_unmerged':p['state']=='open' and not p['merged'],'head_matches':p['head_sha']==newheads[letter]['sha'],'base_matches':p['base']==(targettrunk if order.index(letter)==0 else newheads[order[order.index(letter)-1]]['ref'])}
  assert all(checks[letter].values()),checks
 return {'before':before,'unstack_http':un['http'],'residual':residual,'released':released,'parked':parked,'after':after,'checks':checks,'order':order,'stack_before':oldstack,'stack_after':c['stack']}

def safe_structures():
 c=fixture('structure',3);t=c['trunk_sha'];p=c['prefix'];a=c['heads']['A'];b=c['heads']['B'];cc=c['heads']['C']
 c2=commit('structure-C2',t,{'structure/C.txt':'C=1\n'});a2=commit('structure-A2',c2,{'structure/A.txt':'A=1\n'});b2=commit('structure-B2',a2,{'structure/B.txt':'B=1\n'})
 heads={'C':{'ref':cc['ref'],'sha':c2},'A':{'ref':a['ref'],'sha':a2},'B':{'ref':b['ref'],'sha':b2}}
 reorder=transition(c,'safe-reorder',['C','A','B'],heads)
 # The full final file set must equal the original top C, not the old B.
 assert git('rev-parse',b2+'^{tree}')==git('rev-parse',cc['sha']+'^{tree}')
 d=commit('structure-D1',c2,{'structure/D.txt':'D=1\n'});a3=commit('structure-A3',d,{'structure/A.txt':'A=1\n'});b3=commit('structure-B3',a3,{'structure/B.txt':'B=1\n'})
 heads2={'C':heads['C'],'D':{'ref':p+'/D','sha':d},'A':{'ref':a['ref'],'sha':a3},'B':{'ref':b['ref'],'sha':b3}}
 insertion=transition(c,'safe-insert',['C','D','A','B'],heads2,create=['D'])
 a4=commit('structure-A4',c2,{'structure/A.txt':'A=1\n'});b4=commit('structure-B4',a4,{'structure/B.txt':'B=1\n'})
 heads3={'C':heads['C'],'A':{'ref':a['ref'],'sha':a4},'B':{'ref':b['ref'],'sha':b4}}
 drop=transition(c,'safe-drop',['C','A','B'],heads3,withdraw=['D'])
 c5=commit('structure-C5',t,{'structure/C.txt':'C=1\n','structure/A.txt':'A=1\n'});b5=commit('structure-B5',c5,{'structure/B.txt':'B=1\n'})
 heads4={'C':{'ref':cc['ref'],'sha':c5},'B':{'ref':b['ref'],'sha':b5}}
 fold=transition(c,'safe-fold',['C','B'],heads4,withdraw=['A'])
 newt=commit('structure-trunk2',t,{'structure/trunk2.txt':'unrelated=1\n'})
 assert push('structure-trunk2-push',{'refs/heads/'+p+'/trunk2':newt})['exit']==0
 git('update-ref','refs/remotes/observed/structure/trunk2',newt)
 c6=commit('structure-C6',newt,{'structure/C.txt':'C=1\n','structure/A.txt':'A=1\n'});b6=commit('structure-B6',c6,{'structure/B.txt':'B=1\n'})
 heads5={'C':{'ref':cc['ref'],'sha':c6},'B':{'ref':b['ref'],'sha':b6}}
 trunk=transition(c,'safe-trunk',['C','B'],heads5,trunk=p+'/trunk2')
 return {'prs':c['prs'],'reorder':reorder,'insert':insertion,'drop':drop,'fold':fold,'trunk':trunk,'all_input_and_archive_refs_retained':True}

def unsafe_reorder():
 c=fixture('unsafe-reorder',2);before=snapshot(c,'unsafe-before');t=c['trunk_sha']
 un=require(api('unsafe-unstack','POST',f"repos/{REPO}/stacks/{c['stack']}/unstack"),[200,204])
 b2=commit('unsafe-B2',t,{'unsafe-reorder/B.txt':'B=1\n'});a2=commit('unsafe-A2',b2,{'unsafe-reorder/A.txt':'A=1\n'})
 # Deliberately omit parking: B still targets A when A begins containing B.
 updates={'refs/heads/'+c['heads']['A']['ref']:a2,'refs/heads/'+c['heads']['B']['ref']:b2,'refs/tags/'+c['prefix']+'/authored/A/v2':a2,'refs/tags/'+c['prefix']+'/authored/B/v2':b2}
 expected={'refs/heads/'+c['heads'][x]['ref']:c['heads'][x]['sha'] for x in ['A','B']}
 pushed=push('unsafe-heads',updates,expected);assert pushed['exit']==0,pushed
 timeline=[]
 for j in range(3):
  time.sleep(3 if j==0 else 5)
  after=snapshot(c,'unsafe-after-heads-'+str(j));timeline.append(after)
  if after['prs']['B']['state']=='closed':break
 repair=api('unsafe-repair-base','PATCH',f"repos/{REPO}/pulls/{c['prs']['B']}",{'base':c['trunk']})
 reopen=None
 if after['prs']['B']['state']=='closed':reopen=api('unsafe-reopen-control','PATCH',f"repos/{REPO}/pulls/{c['prs']['B']}",{'state':'open'})
 return {'before':before,'unstack_http':un['http'],'after':after,'timeline':timeline,'repair_http':repair['http'],'repair_response':repair['data'],'reopen_http':reopen['http'] if reopen else None,'reopen_response':reopen['data'] if reopen else None}

def completed_extension():
 c=load_case('merge-squash');old=json.loads((HOME/'basic-results.json').read_text())['merge-squash']['continuation']
 for letter in ['D','E']:
  sha=json.loads((EVIDENCE/('complete-'+letter+'.commit.json')).read_text())['sha'];c['heads'][letter]={'ref':c['prefix']+'/'+letter,'sha':sha};c['prs'][letter]=old[letter]
 save_case(c);before=snapshot(c,'complete-follow-before')
 add=require(api('complete-follow-append-E','POST',f"repos/{REPO}/stacks/{c['stack']}/add",{'pull_requests':[c['prs']['E']]}),[200])
 r=merge(c,'D','complete-follow-land-D',sha=c['heads']['D']['sha']);after=snapshot(c,'complete-follow-after-land-D');fetch_case(c,'complete-follow-D')
 un=api('complete-follow-release','POST',f"repos/{REPO}/stacks/{c['stack']}/unstack");released=snapshot(c,'complete-follow-released')
 eligible=[x for x in ['D','E'] if released['prs'][x]['state']=='open' and not released['prs'][x]['merged']]
 for i,x in enumerate(eligible):require(api('complete-follow-base-'+x,'PATCH',f"repos/{REPO}/pulls/{c['prs'][x]}",{'base':c['trunk'] if i==0 else c['heads'][eligible[i-1]]['ref']}),[200])
 if len(eligible)==1:
  letter=eligible[0];phead=released['prs'][letter]['head_sha'];f=commit('complete-F',phead,{'complete/F.txt':'F=1\n'});ref=c['prefix']+'/F'
  assert push('complete-F-push',{'refs/heads/'+ref:f,'refs/tags/'+c['prefix']+'/authored/F/v1':f})['exit']==0
  pr=require(api('complete-F-pr','POST',f'repos/{REPO}/pulls',{'head':ref,'base':c['heads'][letter]['ref'],'title':'Experiment residual history: F','body':'Synthetic regrouping after partial unstack.\n\n'+NOTICE}),[201])
  c['heads']['F']={'ref':ref,'sha':f};c['prs']['F']=pr['data']['number'];eligible.append('F')
 new=api('complete-follow-new-group','POST',f'repos/{REPO}/stacks',{'pull_requests':[c['prs'][x] for x in eligible]})
 result={'before':before,'append_E_http':add['http'],'merge_D':r,'after_merge_D':after,'unstack_http':un['http'],'released':released,'eligible':eligible,'new_group_http':new['http'],'new_group':new['data']}
 if new['http']==201:c['stack']=new['data']['number'];save_case(c);result['new_state']=snapshot(c,'complete-follow-new-state')
 return result
run('safe-structures',safe_structures)
run('unsafe-reorder',unsafe_reorder)
run('completed-extension',completed_extension)
print('STRUCTURE DONE',flush=True)
