"""SQL acceptance: genuine PostgreSQL, synthetic fixtures isolated to test database."""
import os,uuid
from datetime import date
from decimal import Decimal
import pytest
from database.connection import connect,migrate
from database.analytics import query,NAMES

@pytest.fixture
def panel():
    dsn=os.getenv('TEST_DATABASE_URL')
    if not dsn: pytest.skip('real PostgreSQL required')
    migrate(dsn)
    with connect(dsn) as c:
        suffix=uuid.uuid4().hex
        source=c.execute('INSERT INTO sources(name,attribution) VALUES(%s,%s) RETURNING source_id',(suffix,'fixture')).fetchone()[0]
        sample=c.execute('INSERT INTO samples(name,version,selection_method) VALUES(%s,1,%s) RETURNING sample_id',(suffix,'fixed synthetic panel')).fetchone()[0]
        stores=[]
        for i in range(3):
            chain=c.execute('INSERT INTO retail_chains(source_id,source_chain_identifier,chain_name) VALUES(%s,%s,%s) RETURNING chain_id',(source,str(i//2),str(i//2))).fetchone()[0] if i!=1 else chain
            store=c.execute('INSERT INTO stores(chain_id,source_store_identifier,store_name) VALUES(%s,%s,%s) RETURNING store_id',(chain,str(i),str(i))).fetchone()[0]
            stores.append(store)
            c.execute('INSERT INTO sample_stores VALUES(%s,%s)',(sample,store))
        products=[]
        for i in range(2):
            p=c.execute("INSERT INTO products(product_name,gtin) VALUES(%s,%s) RETURNING product_id",('CURRENT SHOULD NOT APPEAR',str(uuid.uuid4().int % 10**14).zfill(14))).fetchone()[0]
            products.append(p);c.execute('INSERT INTO sample_products VALUES(%s,%s)',(sample,p))
        basket=c.execute('INSERT INTO baskets(name,version) VALUES(%s,1) RETURNING basket_id',(suffix,)).fetchone()[0]
        for p,q in zip(products,[2,3]): c.execute('INSERT INTO basket_items VALUES(%s,%s,%s)',(basket,p,q))
        c.execute('UPDATE baskets SET sealed=true WHERE basket_id=%s',(basket,))
        # Jan 2 absent: LAG must report gap 2, never synthesize an observation.
        for day,prices in [(1,[(10,20),(14,20),(12,24)]),(3,[(12,20),(14,20),(12,None)]),(4,[(14,20),(14,20),(12,24)])]:
            run=c.execute("INSERT INTO ingestion_runs(sample_id,observation_date,revision,expected_partitions) VALUES(%s,%s,1,3) RETURNING ingestion_run_id",(sample,date(2026,1,day))).fetchone()[0]
            count=0
            for store,vals in zip(stores,prices):
                for p,price in zip(products,vals):
                    if price is None: continue
                    c.execute('INSERT INTO price_observations(ingestion_run_id,store_id,product_id,price_ils,product_name_snapshot,store_name_snapshot,chain_name_snapshot,category_name_snapshot) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(run,store,p,price,'Historic product','Historic store','Historic chain','Historic category' if p==products[0] else 'Other category'));count+=1
            c.execute("UPDATE ingestion_runs SET status='complete',completed_at=now(),fetched_partitions=3,records_received=%s,records_accepted=%s WHERE ingestion_run_id=%s",(count,count,run))
            c.execute('INSERT INTO daily_publications VALUES(%s,%s,%s)',(sample,date(2026,1,day),run))
    return dict(dsn=dsn,sample_id=sample),stores,products,basket

def test_all_queries_and_historic_labels(panel):
    args,stores,products,basket=panel
    for name in NAMES:
        rows=query(name,**args)
        assert rows,name
        assert 'CURRENT SHOULD NOT APPEAR' not in str(rows)

def test_changes_gaps_and_insufficient_history(panel):
    args,stores,products,_=panel
    rows=query('price_changes',**args,product_id=products[0],store_ids=[stores[0]])
    assert [(r['price_ils'],r['change_ils'],r['gap_days']) for r in rows]==[(14,2,1),(12,2,2),(10,None,None)]
    assert rows[0]['first_detected_change_date']==date(2026,1,3)
    rows=query('price_volatility',**args,product_id=products[0],store_ids=[stores[0]])
    assert rows[0]['change_frequency']==1 and rows[0]['observed_pairs']==2
    assert rows[0]['consecutive_pairs']==1 and rows[0]['maximum_gap_days']==2
    one=query('price_volatility',**args,start_date=date(2026,1,1),end_date=date(2026,1,1))
    assert all(r['change_frequency'] is None for r in one)

def test_basket_quantity_missing_and_dates(panel):
    args,stores,products,basket=panel
    rows=query('basket_costs',**args,basket_id=basket)
    first=next(r for r in rows if r['store_id']==stores[0] and r['observation_date']==date(2026,1,1))
    assert first['comparable_total']==80
    partial=next(r for r in rows if r['store_id']==stores[2] and r['observation_date']==date(2026,1,3))
    assert partial['coverage']==Decimal('.5') and partial['observed_subtotal']==24
    assert partial['comparable_total'] is None and partial['missing_product_ids']==[products[1]]
    assert len(rows)==9

def test_paired_medians_and_fixed_common_panel(panel):
    args,stores,products,_=panel
    rows=query('retailer_comparison',**args)
    a=next(r for r in rows if r['product_id']==products[0] and r['observation_date']==date(2026,1,1))
    assert a['median_price']==12 and a['comparison_price']==12 and a['gap_ils']==0
    assert a['fixed_panel_eligible'] is True
    assert a['price_rank']==a['comparison_price_rank']==1
    assert all(not r['fixed_panel_eligible'] for r in rows if r['product_id']==products[1])
    assert query('latest_prices',**args,end_date=date(2025,12,31))==[]
    assert query('retailer_comparison',**args,chain_ids=[])==[]

def test_threshold_sensitivity_and_reader(panel):
    args,_,_,_=panel
    rows=query('price_anomalies',**args)
    assert any(r['large_change'] for r in rows)
    assert not any(r['stricter_large_change'] for r in rows)
    assert any(r['repeated_increase'] for r in rows)
    with connect(args['dsn']) as c:
        c.execute('SET ROLE irpi_reader')
        assert c.execute('SELECT count(*) FROM published_price_changes').fetchone()[0]>0

def test_quality_overview_missing_calendar_and_reader_service(panel,monkeypatch):
    from contextlib import contextmanager
    import database.analytics as service
    args,stores,products,_=panel
    overview=query('overview',**args)[0]
    assert overview['observed_records']==17 and overview['observed_changes']==2
    assert float(overview['coverage'])==pytest.approx(17/24)
    assert overview['fixed_common_products']==1
    days=query('missing_days',**args)
    assert [(r['observation_date'].day,r['missing_publication']) for r in days]==[(1,False),(2,True),(3,False),(4,False)]
    # Exercise actual service queries with PostgreSQL enforcing reader privileges.
    original=service.connect
    @contextmanager
    def reader(*a,**kw):
        with original(*a,**kw) as c:
            c.execute('SET ROLE irpi_reader')
            yield c
    monkeypatch.setattr(service,'connect',reader)
    for name in service.NAMES: assert service.query(name,**args)
    assert service.options(args['dsn'])['samples']

def test_category_manifest_denominator_and_missing_products(panel):
    args,stores,products,_=panel
    # One product is recategorized in the reference table; historic snapshot must win.
    with connect(args['dsn']) as c:
        cat=c.execute('INSERT INTO categories(category_name) VALUES(%s) RETURNING category_id',('Reference-only-'+uuid.uuid4().hex,)).fetchone()[0]
        c.execute('UPDATE products SET category_id=%s WHERE product_id=%s',(cat,products[0]))
    historic=query('overview',**args,category='Historic category')[0]
    assert historic['tracked_products']==1
    assert float(historic['coverage'])==pytest.approx(9/12)
    empty=query('overview',**args,category='No such category')[0]
    assert empty['tracked_products']==0 and empty['coverage'] is None
    # In the Jan3 slice product2 misses a chain, but remains in declared denominator.
    single=query('overview',**args,category='Other category',start_date=date(2026,1,3),end_date=date(2026,1,3))[0]
    assert single['tracked_products']==1 and float(single['coverage'])==pytest.approx(2/3)
