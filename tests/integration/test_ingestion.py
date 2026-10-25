import json,os,uuid
from datetime import datetime,timezone
from pathlib import Path
import pytest
from database.connection import connect
from pipeline.ingest import ingest

@pytest.fixture
def setup():
    dsn=os.getenv('TEST_DATABASE_URL')
    if not dsn: pytest.skip('real PostgreSQL required')
    m=json.loads(Path('config/pilot_v1.json').read_text()); m['name']='test-'+str(uuid.uuid4())
    return dsn,m

def fake(store,client,now,audit):
    m=json.loads(Path('config/pilot_v1.json').read_text())
    return dict(store=store,rows=[dict(p,product_id=p['gtin'],price_ils='4.50',source_updated_at=now.isoformat()) for p in m['products']],sha256='a'*64,collected_at=now.isoformat(),filename='test-only',parse_rejected=0)

def test_replay_and_partial_preserve_complete_publication(setup):
    dsn,m=setup
    first=ingest(m,dsn,fake); second=ingest(m,dsn,fake)
    assert first['accepted']==second['accepted']==22
    assert second['revision']==2
    def partial(s,*a):
        if s['chain']=='carrefour': raise ValueError('intentional fixture failure')
        return fake(s,*a)
    third=ingest(m,dsn,partial)
    assert third['status']=='partial'
    with connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM published_prices WHERE ingestion_run_id=%s',(second['ingestion_run_id'],)).fetchone()[0]==22
        assert conn.execute('SELECT count(*) FROM price_observations WHERE ingestion_run_id=%s',(first['ingestion_run_id'],)).fetchone()[0]==22
        assert conn.execute('SELECT records_received=records_accepted+records_rejected+records_duplicate FROM ingestion_runs WHERE ingestion_run_id=%s',(third['ingestion_run_id'],)).fetchone()[0]

def test_storage_failure_rolls_back_all_observations(setup):
    dsn,m=setup
    first=ingest(m,dsn,fake)
    def bad(s,*a):
        p=fake(s,*a)
        if s['chain']=='carrefour': p['sha256']='invalid'
        return p
    with pytest.raises(Exception): ingest(m,dsn,bad)
    with connect(dsn) as conn:
        rows=conn.execute('SELECT status,records_accepted FROM ingestion_runs r JOIN samples s USING(sample_id) WHERE s.name=%s ORDER BY revision',(m['name'],)).fetchall()
        assert rows==[('complete',22),('failed',0)]
        assert conn.execute('SELECT count(*) FROM published_prices WHERE ingestion_run_id=%s',(first['ingestion_run_id'],)).fetchone()[0]==22

def test_interrupted_run_is_abandoned_under_exclusive_lock(setup):
    dsn,m=setup
    first=ingest(m,dsn,fake)
    with connect(dsn) as conn:
        sample=conn.execute('SELECT sample_id FROM samples WHERE name=%s',(m['name'],)).fetchone()[0]
        stranded=conn.execute('INSERT INTO ingestion_runs(sample_id,observation_date,revision,expected_partitions) VALUES (%s,%s,2,2) RETURNING ingestion_run_id',(sample,first['observation_date'])).fetchone()[0]
    third=ingest(m,dsn,fake)
    assert third['revision']==3
    with connect(dsn) as conn:
        status,completed=conn.execute('SELECT status,completed_at FROM ingestion_runs WHERE ingestion_run_id=%s',(stranded,)).fetchone()
        assert status=='abandoned' and completed is not None

def test_source_codes_map_to_stable_canonical_products(setup):
    dsn,m=setup
    result=ingest(m,dsn,fake)
    with connect(dsn) as conn:
        count=conn.execute('SELECT count(*) FROM published_prices p JOIN source_products sp ON sp.chain_id=p.chain_id AND sp.source_product_identifier=p.source_product_identifier AND sp.product_id=p.product_id WHERE p.ingestion_run_id=%s',(result['ingestion_run_id'],)).fetchone()[0]
        assert count==22

def test_concurrent_attempts_serialize_daily_publication(setup):
    from concurrent.futures import ThreadPoolExecutor
    dsn,m=setup
    with ThreadPoolExecutor(max_workers=2) as workers:
        attempts=list(workers.map(lambda _: ingest(m,dsn,fake), range(2)))
    assert sorted(r['revision'] for r in attempts)==[1,2]
    with connect(dsn) as conn:
        assert conn.execute('SELECT count(*) FROM published_prices p JOIN samples s USING(sample_id) WHERE s.name=%s',(m['name'],)).fetchone()[0]==22
