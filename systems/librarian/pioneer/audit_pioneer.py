#!/usr/bin/env python3
"""Fail-closed audit of the canonical PIONEER scientific system."""
import hashlib,json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];P=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def count(db,table):
 c=sqlite3.connect(f'file:{db}?mode=ro',uri=True);n=c.execute(f'select count(*) from "{table}"').fetchone()[0];c.close();return n
def main():
 sys.path.insert(0,str(ROOT));from runtime.experiment_registry import load_and_validate_registry,validate_reference_views
 checks={};details={}
 try:r=load_and_validate_registry();validate_reference_views(r);checks['experiment_registry_valid']=True
 except Exception as e:checks['experiment_registry_valid']=False;details['registry_error']=f'{type(e).__name__}: {e}';r={'experiments':[]}
 checks['all_experiments_preregistered_and_blocked']=len(r['experiments'])==6 and all(x['result_status']=='BLOCKED' and x['final_verdict']=='PENDING' for x in r['experiments'])
 link=load(ROOT/'research_assistant/PIONEER_LINK.json');system=load(P/'PIONEER_SYSTEM.json');checks['research_assistant_reference_only']=link['system_id']==system['system_id'] and link['duplication_policy']=='REFERENCE_ONLY_DO_NOT_COPY_CANONICAL_RECORDS'
 literature=ROOT/'data/academic_corpus.db';retrieval=ROOT/'data/librarian.db';details['academic_sources']=count(literature,'academic_sources');details['citation_edges']=count(literature,'citation_edges');details['retrieval_sources']=count(retrieval,'sources');details['retrieval_documents']=count(retrieval,'documents');details['ingestion_events']=count(retrieval,'ingestion_log')
 checks['corpus_populated']=details['academic_sources']>0 and details['retrieval_sources']>0 and details['retrieval_documents']>0
 ds=load(P/'PIONEER_DATASET_REGISTER.json')['datasets'][0];mp=Path(ds['manifest_path']);checks['nso_dataset_manifest_identity']=mp.is_file() and sha(mp)==ds['manifest_sha256'];checks['nso_dataset_operational_certified']=checks['nso_dataset_manifest_identity'] and load(mp)['operational_corpus_status']=='CERTIFIED'
 pubs=load(P/'PIONEER_PUBLICATION_REGISTER.json')['outputs'];checks['publication_claims_fail_closed']=all(x['status']=='NOT_STARTED_EVIDENCE_GATES_BLOCKED' for x in pubs)
 from pioneer.pioneer_journal import validate_chain,read_events,FEEDBACK
 chain_ok,chain_detail=validate_chain();events=read_events();checks['learning_journal_chain_valid']=chain_ok;details['journal_chain']=chain_detail;details['journal_events']=len(events)
 feedback=[json.loads(x) for x in FEEDBACK.read_text().splitlines() if x.strip()] if FEEDBACK.exists() else [];checks['engineering_feedback_fail_closed']=all(x['status']=='PENDING_ENGINEERING_REVIEW' and x['ingestion_policy']=='CONSIDER_ONLY_DO_NOT_AUTO_EXECUTE' for x in feedback);details['pending_engineering_feedback']=len(feedback)
 optimization=load(P/'PIONEER_RESOURCE_OPTIMIZATION.json');inventory=load(P/'PIONEER_CONTENT_INVENTORY.json');policy=load(P/'PIONEER_STORAGE_POLICY.json');snapshot=load(P/'journal/index.json');test_status=load(P/'PIONEER_TEST_STATUS.json')
 checks['resource_optimization_valid']=optimization['status']=='PASS' and all(optimization['checks'].values())
 checks['content_inventory_valid']=inventory['status']=='PASS' and inventory['unique_objects']==inventory['verified_hashes']
 checks['canonical_storage_policy_enforced']=policy['canonical_root']==str(ROOT) and policy['single_writer_policy']=='ONLY_CANONICAL_ROOT_ACCEPTS_OPERATIONAL_WRITES'
 checks['journal_snapshot_anchored']=snapshot['status']=='PASS' and snapshot['event_count']==len(events) and snapshot['last_event_sha256']==(events[-1]['event_sha256'] if events else 'GENESIS')
 checks['full_test_suite_last_observed_pass']=test_status['status']=='PASS' and test_status['failed']==0
 details['test_suite']=test_status
 out={'status':'PASS_WITH_BLOCKED_RESEARCH' if all(checks.values()) else 'FAIL','scientific_truth_status':'INFRASTRUCTURE_VALIDATED_EXPERIMENTAL_CLAIMS_NOT_YET_ESTABLISHED','checks':checks,'details':details,'experiments':{'total':len(r['experiments']),'blocked':sum(x.get('result_status')=='BLOCKED' for x in r['experiments'])},'publications':{'project_paper':'NOT_STARTED','white_paper':'NOT_STARTED'},'legacy_surfaces':'REFERENCE_ONLY_NOT_SYNCHRONIZED_CANONICAL_STORES'}
 (P/'PIONEER_AUDIT.json').write_text(json.dumps(out,sort_keys=True,indent=2)+'\n');print(json.dumps(out,indent=2));return 0 if not any(v is False for v in checks.values()) else 2
if __name__=='__main__':sys.exit(main())
