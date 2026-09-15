#!/usr/bin/env python3
"""Append-only, hash-chained PIONEER learning journal and Engineering feedback queue."""
from __future__ import annotations
import argparse,hashlib,json,os,tempfile
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parent; JOURNAL=ROOT/'journal/events.jsonl'; FEEDBACK=ROOT/'engineering_feedback/pending.jsonl'; SNAPSHOT=ROOT/'journal/index.json'
TYPES={'THOUGHT','REASONING','DECISION','SUCCESS','FAILURE','ACADEMIC_COMPARISON','OPTIMIZATION','LESSON'}
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def read_events(path=None):
 path=Path(path) if path is not None else JOURNAL
 if not path.exists():return []
 return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def validate_chain(path=None):
 path=Path(path) if path is not None else JOURNAL
 events=read_events(path);prev='GENESIS'
 for i,e in enumerate(events,1):
  recorded=e.get('event_sha256');body={k:v for k,v in e.items() if k!='event_sha256'}
  if e.get('previous_event_sha256')!=prev or digest(body)!=recorded:return False,f'chain failure at event {i}'
  prev=recorded
 return True,f'{len(events)} events verified'
def build_snapshot(path=None,output=None):
 path=Path(path) if path is not None else JOURNAL;output=Path(output) if output is not None else SNAPSHOT
 ok,detail=validate_chain(path);events=read_events(path)
 snapshot={'status':'PASS' if ok else 'FAIL','detail':detail,'event_count':len(events),'last_event_sha256':events[-1]['event_sha256'] if events else 'GENESIS','counts_by_type':{t:sum(e['event_type']==t for e in events) for t in sorted(TYPES)}}
 output.parent.mkdir(parents=True,exist_ok=True);tmp=output.with_suffix('.tmp');tmp.write_text(json.dumps(snapshot,sort_keys=True,indent=2)+'\n');os.replace(tmp,output)
 return snapshot
def append_event(event_type,statement,reasoning='',actor='USER',evidence_refs=None,academic_comparisons=None,system_implications=None,optimization_proposals=None,uncertainty='UNKNOWN'):
 if event_type not in TYPES:raise ValueError('invalid event_type')
 if not statement.strip():raise ValueError('statement is required')
 ok,msg=validate_chain()
 if not ok:raise RuntimeError(msg)
 existing=read_events();prev=existing[-1]['event_sha256'] if existing else 'GENESIS'
 event={'event_id':f'PIONEER-EVENT-{uuid4()}','timestamp_utc':datetime.now(timezone.utc).isoformat(),'event_type':event_type,'actor':actor,'statement':statement,'reasoning':reasoning or 'NOT_PROVIDED','evidence_refs':evidence_refs or [],'uncertainty':uncertainty,'academic_comparisons':academic_comparisons or [],'system_implications':system_implications or [],'optimization_proposals':optimization_proposals or [],'review_status':'EVIDENCE_LINKED' if evidence_refs else 'UNREVIEWED','previous_event_sha256':prev}
 event['event_sha256']=digest(event);JOURNAL.parent.mkdir(parents=True,exist_ok=True)
 with JOURNAL.open('a',encoding='utf-8') as f:f.write(json.dumps(event,sort_keys=True,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
 build_snapshot()
 return event
def promote(event_id,rationale,reviewer):
 events=read_events();event=next((x for x in events if x['event_id']==event_id),None)
 if not event:raise ValueError('unknown event_id')
 if event['event_type'] not in {'FAILURE','SUCCESS','DECISION','OPTIMIZATION','LESSON','ACADEMIC_COMPARISON'}:raise ValueError('event type is not promotable')
 if not event['evidence_refs']:raise ValueError('promotion requires evidence_refs')
 fingerprint=digest({'source_event_sha256':event['event_sha256'],'recommendations':event['optimization_proposals']})
 if FEEDBACK.exists():
  for line in FEEDBACK.read_text().splitlines():
   if line.strip():
    existing=json.loads(line)
    existing_fingerprint=existing.get('recommendation_fingerprint') or digest({'source_event_sha256':existing.get('source_event_sha256'),'recommendations':existing.get('recommendations',[])})
    if existing_fingerprint==fingerprint:return existing
 item={'feedback_id':f'PIONEER-FEEDBACK-{uuid4()}','source_event_id':event_id,'source_event_sha256':event['event_sha256'],'recommendation_fingerprint':fingerprint,'created_at_utc':datetime.now(timezone.utc).isoformat(),'reviewer':reviewer,'rationale':rationale,'recommendations':event['optimization_proposals'],'status':'PENDING_ENGINEERING_REVIEW','ingestion_policy':'CONSIDER_ONLY_DO_NOT_AUTO_EXECUTE'}
 FEEDBACK.parent.mkdir(parents=True,exist_ok=True)
 with FEEDBACK.open('a',encoding='utf-8') as f:f.write(json.dumps(item,sort_keys=True,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
 return item
def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True)
 a=s.add_parser('add');a.add_argument('--type',required=True,choices=sorted(TYPES));a.add_argument('--statement',required=True);a.add_argument('--reasoning',default='');a.add_argument('--actor',default='USER');a.add_argument('--uncertainty',default='UNKNOWN',choices=['UNKNOWN','LOW','MEDIUM','HIGH']);a.add_argument('--evidence',action='append',default=[]);a.add_argument('--comparison',action='append',default=[]);a.add_argument('--implication',action='append',default=[]);a.add_argument('--optimization',action='append',default=[])
 s.add_parser('verify');pr=s.add_parser('promote');pr.add_argument('--event-id',required=True);pr.add_argument('--rationale',required=True);pr.add_argument('--reviewer',required=True)
 x=p.parse_args()
 if x.cmd=='verify':ok,msg=validate_chain();print(json.dumps({'status':'PASS' if ok else 'FAIL','detail':msg}));return 0 if ok else 2
 if x.cmd=='promote':print(json.dumps(promote(x.event_id,x.rationale,x.reviewer),indent=2));return 0
 print(json.dumps(append_event(x.type,x.statement,x.reasoning,x.actor,x.evidence,x.comparison,x.implication,x.optimization,x.uncertainty),indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
