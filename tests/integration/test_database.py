"""Acceptance tests against a disposable real PostgreSQL database."""
import os
from pathlib import Path
import pytest
import psycopg

@pytest.fixture
def db():
    dsn = os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('TEST_DATABASE_URL must identify a disposable PostgreSQL database')
    from database.connection import migrate, connect
    migrate(dsn)
    with connect(dsn) as conn:
        with conn.transaction(force_rollback=True):
            yield conn


def test_schema_migration_exists():
    assert list(Path('database/migrations').glob('*.sql')), 'Reproducible schema migration required'


def test_migration_idempotent(db):
    from database.connection import migrate
    migrate(os.environ['TEST_DATABASE_URL'])
    assert db.execute('SELECT count(*) FROM schema_migrations').fetchone()[0] >= 1
    assert db.execute('SHOW timezone').fetchone()[0] == 'UTC'


def seed(db):
    source = db.execute("INSERT INTO sources(name, attribution) VALUES ('test','fixture only') RETURNING source_id").fetchone()[0]
    chain = db.execute("INSERT INTO retail_chains(source_id,source_chain_identifier,chain_name) VALUES (%s,'1','Test') RETURNING chain_id", (source,)).fetchone()[0]
    store = db.execute("INSERT INTO stores(chain_id,source_store_identifier,store_name) VALUES (%s,'1','Branch') RETURNING store_id",(chain,)).fetchone()[0]
    product = db.execute("INSERT INTO products(gtin,product_name) VALUES ('00012345678905','Product') RETURNING product_id").fetchone()[0]
    sample = db.execute("INSERT INTO samples(name,version,selection_method) VALUES ('Test',1,'fixture') RETURNING sample_id").fetchone()[0]
    db.execute('INSERT INTO sample_stores VALUES (%s,%s)', (sample,store))
    db.execute('INSERT INTO sample_products VALUES (%s,%s)', (sample,product))
    run = db.execute("INSERT INTO ingestion_runs(sample_id,observation_date,revision,expected_partitions) VALUES (%s,'2026-10-24',1,1) RETURNING ingestion_run_id",(sample,)).fetchone()[0]
    return source,chain,store,product,sample,run


def test_namespaces_and_price_constraints(db):
    source,chain,store,product,sample,run = seed(db)
    other = db.execute("INSERT INTO retail_chains(source_id,source_chain_identifier,chain_name) VALUES (%s,'2','Other') RETURNING chain_id",(source,)).fetchone()[0]
    db.execute("INSERT INTO stores(chain_id,source_store_identifier,store_name) VALUES (%s,'1','Other branch')",(other,))
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute("INSERT INTO price_observations(ingestion_run_id,store_id,product_id,price_ils,product_name_snapshot,store_name_snapshot,chain_name_snapshot) VALUES (%s,%s,%s,0,'p','s','c')", (run,store,product))
    assert db.execute('SELECT gtin FROM products WHERE product_id=%s',(product,)).fetchone()[0] == '00012345678905'
    with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
        db.execute("INSERT INTO stores(chain_id,source_store_identifier,store_name) VALUES (%s,'1','duplicate')",(chain,))


def test_publication_guard_and_history(db):
    _,_,store,product,sample,run = seed(db)
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute("INSERT INTO daily_publications VALUES (%s,'2026-10-24',%s)",(sample,run))
    db.execute("INSERT INTO price_observations(ingestion_run_id,store_id,product_id,price_ils,product_name_snapshot,store_name_snapshot,chain_name_snapshot) VALUES (%s,%s,%s,9.99,'Old name','Branch','Chain')",(run,store,product))
    db.execute("UPDATE ingestion_runs SET status='complete',completed_at=now(),records_received=1,records_accepted=1,fetched_partitions=1 WHERE ingestion_run_id=%s",(run,))
    db.execute("INSERT INTO daily_publications VALUES (%s,'2026-10-24',%s)",(sample,run))
    db.execute("UPDATE products SET product_name='New name' WHERE product_id=%s",(product,))
    assert db.execute('SELECT product_name_snapshot FROM published_prices WHERE ingestion_run_id=%s',(run,)).fetchone()[0] == 'Old name'
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute('UPDATE price_observations SET price_ils=10 WHERE ingestion_run_id=%s',(run,))
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute("UPDATE ingestion_runs SET status='failed' WHERE ingestion_run_id=%s",(run,))


def test_reader_and_ingestor_permissions(db):
    assert db.execute("SELECT has_table_privilege('irpi_reader','published_prices','SELECT')").fetchone()[0]
    assert not db.execute("SELECT has_table_privilege('irpi_reader','ingestion_runs','SELECT')").fetchone()[0]
    assert not db.execute("SELECT has_table_privilege('irpi_reader','price_observations','INSERT')").fetchone()[0]
    assert db.execute("SELECT has_table_privilege('irpi_ingestor','price_observations','INSERT')").fetchone()[0]
    assert not db.execute("SELECT has_table_privilege('irpi_ingestor','schema_migrations','UPDATE')").fetchone()[0]


def test_sample_membership_and_frozen_manifest(db):
    _,_,store,product,sample,run=seed(db)
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute('DELETE FROM sample_products WHERE sample_id=%s',(sample,))
    other=db.execute("INSERT INTO products(gtin,product_name) VALUES ('00012345678912','Outside panel') RETURNING product_id").fetchone()[0]
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute("INSERT INTO price_observations(ingestion_run_id,store_id,product_id,price_ils,product_name_snapshot,store_name_snapshot,chain_name_snapshot) VALUES (%s,%s,%s,1,'p','s','c')",(run,store,other))


def test_timestamp_is_an_instant(db):
    row=db.execute("SELECT '2026-10-24T00:30:00+03:00'::timestamptz").fetchone()[0]
    assert row.isoformat() == '2026-10-23T21:30:00+00:00'


def test_basket_version_freezes_after_seal(db):
    _,_,_,product,_,_=seed(db)
    basket=db.execute("INSERT INTO baskets(name,version) VALUES ('Fixed',1) RETURNING basket_id").fetchone()[0]
    db.execute('INSERT INTO basket_items VALUES (%s,%s,2)',(basket,product))
    db.execute('UPDATE baskets SET sealed=true WHERE basket_id=%s',(basket,))
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute('UPDATE basket_items SET quantity=3 WHERE basket_id=%s',(basket,))
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute('UPDATE baskets SET sealed=false WHERE basket_id=%s',(basket,))
