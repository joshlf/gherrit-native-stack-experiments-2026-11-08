#!/usr/bin/env python3
import concurrent.futures, datetime, hashlib, json, pathlib, re, subprocess, threading, time
ROOT=pathlib.Path(__file__).resolve().parent
HOME=ROOT/'concurrent-history';E=HOME/'evidence';J=HOME/'journal.jsonl'
REPO='joshlf/gherrit-native-stack-experiments-2026-11-08'
PR='repos/'+REPO+'/pulls/10'
COMMENT='repos/'+REPO+'/issues/comments/6728278369'
NOTICE="*Authored by an AI agent acting on joshlf's behalf.*"
LOCK=threading.Lock()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def digest(text):return hashlib.sha256(text.encode()).hexdigest()
def event(value):
 with LOCK:
  with J.open('a') as f:f.write(json.dumps({'at':now(),**value})+'\n')
def api(name,path,method='GET',body=None,barrier=None):
 command=['gh','api','--include','--method',method,'-H','Accept: application/vnd.github+json',path]
 if body is not None:
  request=E/(name+'.request.json');dump(request,body);command+=['--input',str(request)]
 if method!='GET':
  with LOCK:prior=[json.loads(x) for x in J.read_text().splitlines()] if J.exists() else []
  assert not any(x.get('name')==name and x['state']=='dispatch-intent' for x in prior),'Reconcile before reusing dispatch identity'
  event({'name':name,'state':'dispatch-intent','method':method,'path':path,'body':body})
 if barrier is not None:barrier.wait()
 start=time.monotonic();started=now()
 result=subprocess.run(command,capture_output=True,text=True)
 end=time.monotonic()
 (E/(name+'.response.txt')).write_text(result.stdout);(E/(name+'.stderr')).write_text(result.stderr)
 status=re.search(r'^HTTP/\S+\s+(\d+)',result.stdout,re.M)
 meta={'command':command,'started':started,'finished':now(),'monotonic_start':start,'monotonic_end':end,'exit':result.returncode,'http':int(status.group(1)) if status else None}
 dump(E/(name+'.meta.json'),meta)
 if method!='GET':event({'name':name,'state':'response-observed','exit':result.returncode,'http':meta['http']})
 print(name,result.returncode,meta['http'],flush=True)
 assert result.returncode==0 and meta['http']==200,'Reconcile unexpected or unknown write outcome; never retry blindly'
 payload=json.loads(re.split(r'\r?\n\r?\n',result.stdout,maxsplit=1)[1]);dump(E/(name+'.payload.json'),payload)
 return payload,meta

def main():
 HOME.mkdir(exist_ok=True);E.mkdir(exist_ok=True)
 assert not J.exists(),'Fresh bounded experiment only; do not replay writes'
 original_body=json.loads((ROOT/'evidence/history-human-body-edit.stdout').read_text())['body']
 original_comment=json.loads((ROOT/'evidence/history-create-replacement.stdout').read_text())['body']
 before_body,_=api('initial-pr-read',PR);before_comment,_=api('initial-comment-read',COMMENT)
 assert before_body['body']==original_body,'Unexpected PR prose: stop before mutation'
 assert before_comment['body']==original_comment,'Unexpected generated prose: stop before mutation'
 assert original_body.count(NOTICE)==original_comment.count(NOTICE)==1
 body_a='Synthetic programmed body actor A: concurrent independent artifact update.\n\n'+NOTICE
 comment_a=original_comment+'\nSynthetic programmed history actor A: concurrent independent artifact update.\n'
 barrier=threading.Barrier(3)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  body_future=pool.submit(api,'parallel-pr-body',PR,'PATCH',{'body':body_a},barrier)
  history_future=pool.submit(api,'parallel-history-comment',COMMENT,'PATCH',{'body':comment_a},barrier)
  barrier.wait()
  body_receipt,body_meta=body_future.result();comment_receipt,comment_meta=history_future.result()
 overlap=max(body_meta['monotonic_start'],comment_meta['monotonic_start'])<min(body_meta['monotonic_end'],comment_meta['monotonic_end'])
 assert overlap,'Client PATCH subprocess intervals must overlap for this case'
 assert body_receipt['body']==body_a and comment_receipt['body']==comment_a
 independent_body,_=api('parallel-pr-readback',PR);independent_comment,_=api('parallel-comment-readback',COMMENT)
 assert independent_body['body']==body_a and independent_comment['body']==comment_a
 assert independent_comment['id']==before_comment['id']==6728278369
 stale_read,_=api('stale-writer-initial-read',PR)
 assert stale_read['body']==body_a
 newer_body='Synthetic programmed body actor B: this newer concurrent sentinel should survive a coordinated update.\n\n'+NOTICE
 api('intervening-newer-body',PR,'PATCH',{'body':newer_body})
 newer_read,_=api('intervening-newer-readback',PR);assert newer_read['body']==newer_body
 stale_patch=stale_read['body']+'\nSynthetic stale writer S: derived from actor A before actor B wrote.\n'
 api('stale-whole-body-write',PR,'PATCH',{'body':stale_patch})
 overwritten,_=api('stale-overwrite-readback',PR)
 assert overwritten['body']==stale_patch and 'body actor B' not in overwritten['body']
 retained_history,_=api('history-after-stale-body-control',COMMENT)
 assert retained_history['body']==comment_a
 fresh_body,_=api('restore-fresh-pr-read',PR);fresh_comment,_=api('restore-fresh-comment-read',COMMENT)
 assert fresh_body['body']==stale_patch and fresh_comment['body']==comment_a,'Unexpected later text: stop before restoration'
 event({'name':'restoration-policy','state':'quiescent-programmed-actors','decision':'Both parallel actors joined; stale control finished; fresh values match this experiment. Restore only the captured synthetic payloads. This is not an API compare-and-swap guarantee.'})
 api('restore-synthetic-pr-body',PR,'PATCH',{'body':original_body})
 api('restore-generated-comment',COMMENT,'PATCH',{'body':original_comment})
 final_body,_=api('final-pr-read',PR);final_comment,_=api('final-comment-read',COMMENT)
 assert final_body['body']==original_body and final_comment['body']==original_comment
 summary={'repository':REPO,'pr':10,'history_comment_id':6728278369,'actors':'same authenticated account, programmed subprocesses','parallel_client_intervals_overlap':overlap,'parallel_body_patch_http':body_meta['http'],'parallel_comment_patch_http':comment_meta['http'],'both_independent_artifact_updates_preserved':True,'stale_whole_body_overwrote_newer_synthetic_text':True,'history_unchanged_by_stale_body_control':True,'original_synthetic_body_restored':True,'original_generated_comment_restored':True,'final_pr_body_sha256':digest(final_body['body']),'final_comment_body_sha256':digest(final_comment['body']),'original_pr_body_sha256':digest(original_body),'original_comment_body_sha256':digest(original_comment),'known_patch_effects':6,'unknown_outcomes_retried':0,'settings_changes':0,'limits':['Client subprocess intervals overlapped; server linearization or HTTP arrival order was not observed.','Same-account programmed actors; no human usability or cross-role permission claim.','No conditional-write or API CAS protocol was used or established.','Fresh reads guarded a quiescent synthetic restoration; they do not exclude arbitrary concurrent writers.']}
 dump(HOME/'RESULTS.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
