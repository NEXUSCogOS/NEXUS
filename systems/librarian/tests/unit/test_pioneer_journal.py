import json
from pathlib import Path
import pytest
from pioneer import pioneer_journal as j

def test_append_and_hash_chain(tmp_path,monkeypatch):
 journal=tmp_path/'events.jsonl';monkeypatch.setattr(j,'JOURNAL',journal);monkeypatch.setattr(j,'SNAPSHOT',tmp_path/'index.json')
 one=j.append_event('THOUGHT','A test thought')
 two=j.append_event('FAILURE','A test failure',evidence_refs=['fixture://failure'],optimization_proposals=['change control'])
 assert two['previous_event_sha256']==one['event_sha256']
 assert j.validate_chain(journal)[0]

def test_tampering_is_detected(tmp_path,monkeypatch):
 journal=tmp_path/'events.jsonl';monkeypatch.setattr(j,'JOURNAL',journal);monkeypatch.setattr(j,'SNAPSHOT',tmp_path/'index.json');j.append_event('THOUGHT','original')
 event=json.loads(journal.read_text());event['statement']='tampered';journal.write_text(json.dumps(event)+'\n')
 assert not j.validate_chain(journal)[0]

def test_feedback_requires_evidence_and_never_auto_executes(tmp_path,monkeypatch):
 journal=tmp_path/'events.jsonl';feedback=tmp_path/'feedback.jsonl';monkeypatch.setattr(j,'JOURNAL',journal);monkeypatch.setattr(j,'SNAPSHOT',tmp_path/'index.json');monkeypatch.setattr(j,'FEEDBACK',feedback)
 event=j.append_event('OPTIMIZATION','Improve retrieval',evidence_refs=['report://1'],optimization_proposals=['benchmark candidate'])
 item=j.promote(event['event_id'],'evidence reviewed','reviewer')
 assert item['status']=='PENDING_ENGINEERING_REVIEW'
 assert item['ingestion_policy']=='CONSIDER_ONLY_DO_NOT_AUTO_EXECUTE'
 assert j.promote(event['event_id'],'reviewed again','reviewer')['feedback_id']==item['feedback_id']
 assert len(feedback.read_text().splitlines())==1
 no_evidence=j.append_event('FAILURE','unsupported failure claim')
 with pytest.raises(ValueError):j.promote(no_evidence['event_id'],'no evidence','reviewer')

def test_snapshot_is_compact_and_chain_anchored(tmp_path,monkeypatch):
 journal=tmp_path/'events.jsonl';snapshot=tmp_path/'index.json';monkeypatch.setattr(j,'JOURNAL',journal);monkeypatch.setattr(j,'SNAPSHOT',snapshot)
 event=j.append_event('LESSON','Measured lesson')
 index=json.loads(snapshot.read_text())
 assert index['status']=='PASS'
 assert index['event_count']==1
 assert index['last_event_sha256']==event['event_sha256']
