#!/usr/bin/env python3
"""Idempotent, fail-closed resource optimization and measurement for PIONEER."""
from __future__ import annotations
import hashlib,json,sqlite3,sys,time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];P=Path(__file__).resolve().parent
ACADEMIC=ROOT/'data/academic_corpus.db';LIBRARIAN=ROOT/'data/librarian.db'
REPORT=P/'PIONEER_RESOURCE_OPTIMIZATION.json';INVENTORY=P/'PIONEER_CONTENT_INVENTORY.json'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def integrity(conn):return conn.execute('PRAGMA integrity_check').fetchone()[0]
def database_stats(path):
 with sqlite3.connect(path) as c:
  return {'bytes':path.stat().st_size,'sha256':sha(path),'integrity':integrity(c),'page_count':c.execute('PRAGMA page_count').fetchone()[0],'freelist_count':c.execute('PRAGMA freelist_count').fetchone()[0]}
def migrate_academic():
 with sqlite3.connect(ACADEMIC) as c:
  c.executescript('''
  CREATE INDEX IF NOT EXISTS idx_academic_content_hash ON academic_sources(content_hash);
  CREATE INDEX IF NOT EXISTS idx_academic_canonical_url ON academic_sources(canonical_url);
  CREATE INDEX IF NOT EXISTS idx_academic_publication_date ON academic_sources(publication_date);
  CREATE INDEX IF NOT EXISTS idx_academic_verification ON academic_sources(verification_status);
  CREATE INDEX IF NOT EXISTS idx_citation_from ON citation_edges(source_from);
  CREATE INDEX IF NOT EXISTS idx_citation_to ON citation_edges(source_to);
  CREATE INDEX IF NOT EXISTS idx_citation_verified ON citation_edges(verified);
  CREATE VIRTUAL TABLE IF NOT EXISTS academic_sources_fts USING fts5(source_id UNINDEXED,title,retrievable_text,tokenize='unicode61 remove_diacritics 2');
  CREATE TRIGGER IF NOT EXISTS academic_sources_fts_ai AFTER INSERT ON academic_sources BEGIN
   INSERT INTO academic_sources_fts(source_id,title,retrievable_text) VALUES(new.source_id,new.title,new.retrievable_text);
  END;
  CREATE TRIGGER IF NOT EXISTS academic_sources_fts_ad AFTER DELETE ON academic_sources BEGIN
   DELETE FROM academic_sources_fts WHERE source_id=old.source_id;
  END;
  CREATE TRIGGER IF NOT EXISTS academic_sources_fts_au AFTER UPDATE OF title,retrievable_text ON academic_sources BEGIN
   DELETE FROM academic_sources_fts WHERE source_id=old.source_id;
   INSERT INTO academic_sources_fts(source_id,title,retrievable_text) VALUES(new.source_id,new.title,new.retrievable_text);
  END;
  ''')
  source_rows=c.execute('SELECT source_id,title,retrievable_text FROM academic_sources ORDER BY source_id').fetchall()
  fts_rows=c.execute('SELECT source_id,title,retrievable_text FROM academic_sources_fts ORDER BY source_id').fetchall()
  if source_rows!=fts_rows:
   c.execute('DELETE FROM academic_sources_fts')
   c.executemany('INSERT INTO academic_sources_fts(source_id,title,retrievable_text) VALUES(?,?,?)',source_rows)
  c.execute('PRAGMA optimize')
  if integrity(c)!='ok':raise RuntimeError('academic database integrity failure')
def migrate_librarian():
 with sqlite3.connect(LIBRARIAN) as c:
  for sql in ('CREATE INDEX IF NOT EXISTS idx_sources_updated ON sources(updated_at)','CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents(updated_at)','CREATE INDEX IF NOT EXISTS idx_chunk_map_versions ON chunk_map(parser_version,chunker_version)','CREATE INDEX IF NOT EXISTS idx_ingestion_created ON ingestion_log(created_at)'):
   c.execute(sql)
  c.execute('PRAGMA optimize')
  if integrity(c)!='ok':raise RuntimeError('retrieval database integrity failure')
def benchmark():
 sys.path.insert(0,str(ROOT));from academic.store import AcademicStore
 from academic.retrieval import search
 store=AcademicStore(ACADEMIC);queries=['agent memory architecture','multi agent governance','retrieval augmented generation','software engineering agents']
 results=[]
 for q in queries:
  terms=sorted(set(q.lower().split()));start=time.perf_counter_ns();legacy=[]
  for row in store.all_sources():
   text=(row['retrievable_text'] or '').lower();matched=[t for t in terms if t in text]
   if len(matched)>=2:legacy.append((row['source_id'],sum(text.count(t) for t in matched)))
  legacy=[x[0] for x in sorted(legacy,key=lambda x:(-x[1],x[0]))[:10]];legacy_ns=time.perf_counter_ns()-start
  start=time.perf_counter_ns();indexed=[h.source_id for h in search(store,q)];indexed_ns=time.perf_counter_ns()-start
  results.append({'query':q,'legacy_ns':legacy_ns,'indexed_ns':indexed_ns,'equivalent':legacy==indexed,'result_count':len(indexed)})
 return results
def content_inventory():
 path=ROOT/'data/content/_corpus_chunks.json';payload=json.loads(path.read_text()) if path.exists() else {}
 encoded=sum(len(v.encode('utf-8')) for v in payload.values());valid=sum(hashlib.sha256(v.strip().encode('utf-8')).hexdigest()==k for k,v in payload.items())
 out={'status':'PASS' if valid==len(payload) else 'FAIL','store_path':str(path),'addressing':'SHA256_CONTENT_ADDRESSED','unique_objects':len(payload),'verified_hashes':valid,'logical_utf8_bytes':encoded,'duplication_policy':'ONE_OBJECT_PER_CONTENT_HASH'}
 INVENTORY.write_text(json.dumps(out,sort_keys=True,indent=2)+'\n');return out
def main():
 before={'academic':database_stats(ACADEMIC),'retrieval':database_stats(LIBRARIAN)}
 migrate_academic();migrate_librarian();tests=benchmark();inventory=content_inventory()
 from pioneer.pioneer_journal import build_snapshot
 build_snapshot();after={'academic':database_stats(ACADEMIC),'retrieval':database_stats(LIBRARIAN)}
 checks={'database_integrity':all(x['integrity']=='ok' for x in after.values()),'retrieval_equivalence':all(x['equivalent'] for x in tests),'content_address_integrity':inventory['status']=='PASS','academic_fts_count_matches':False}
 with sqlite3.connect(ACADEMIC) as c:checks['academic_fts_count_matches']=c.execute('select count(*) from academic_sources').fetchone()[0]==c.execute('select count(*) from academic_sources_fts').fetchone()[0]
 out={'status':'PASS' if all(checks.values()) else 'FAIL','generated_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'before':before,'after':after,'benchmark':tests,'interpretation':'Timing is diagnostic only; semantic equivalence and integrity are certification gates. Small-corpus timings do not establish general performance gains.'}
 REPORT.write_text(json.dumps(out,sort_keys=True,indent=2)+'\n');print(json.dumps(out,indent=2));return 0 if out['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
