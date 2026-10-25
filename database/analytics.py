"""Bounded parameterized PostgreSQL analytics over published revisions only."""
from datetime import date
from pathlib import Path
from psycopg.rows import dict_row
from database.connection import connect
SQL = Path(__file__).with_suffix('')
NAMES = frozenset(p.stem for p in SQL.glob('*.sql'))

def options(dsn=None):
    with connect(dsn, row_factory=dict_row) as conn:
        return {
            'samples': conn.execute('SELECT sample_id,name,version,selection_method FROM samples ORDER BY sample_id').fetchall(),
            'chains': conn.execute('SELECT chain_id,chain_name FROM retail_chains ORDER BY chain_id').fetchall(),
            'stores': conn.execute('SELECT store_id,chain_id,store_name FROM stores ORDER BY store_id').fetchall(),
            'products': conn.execute('SELECT DISTINCT ON (product_id) product_id,gtin,product_name_snapshot product_name,category_name_snapshot category FROM published_prices ORDER BY product_id,observation_date DESC,observation_id DESC').fetchall(),
            'baskets': conn.execute('SELECT basket_id,name,version FROM baskets WHERE sealed ORDER BY basket_id').fetchall(),
            'date_bounds': conn.execute('SELECT min(observation_date) start_date,max(observation_date) end_date FROM daily_publications').fetchone(),
        }

def query(name, *, dsn=None, sample_id=None, start_date=None, end_date=None,
          product_id=None, category=None, chain_ids=None, store_ids=None, basket_id=None,
          absolute_threshold=2, relative_threshold=20, limit=1000):
    """Date bounds are inclusive. Empty ID lists select no rows; None means all.

    Latest prices searches history through cutoff, other analyses use the supplied
    period only. Temporal deltas therefore need two observations inside the period.
    """
    if name not in NAMES:
        raise ValueError('Unknown analysis')
    if not isinstance(limit,int) or not 1 <= limit <= 10000:
        raise ValueError('limit must be between 1 and 10000')
    if absolute_threshold <= 0 or relative_threshold <= 0:
        raise ValueError('Anomaly thresholds must be positive')
    with connect(dsn, row_factory=dict_row) as conn:
        if sample_id is None:
            row=conn.execute('SELECT sample_id FROM daily_publications ORDER BY observation_date DESC,sample_id DESC LIMIT 1').fetchone()
            if not row: return []
            sample_id=row['sample_id']
        bounds=conn.execute('SELECT min(observation_date) first,max(observation_date) last FROM daily_publications WHERE sample_id=%s',(sample_id,)).fetchone()
        start_date=start_date or bounds['first'] or date.today()
        end_date=end_date or bounds['last'] or date.today()
        if name=='latest_prices': start_date=date.min
        params=dict(sample_id=sample_id,start_date=start_date,end_date=end_date,product_id=product_id,
                    category=category,chain_ids=chain_ids,store_ids=store_ids,basket_id=basket_id,
                    absolute_threshold=absolute_threshold,relative_threshold=relative_threshold,limit=limit)
        return conn.execute((SQL/f'{name}.sql').read_text(),params).fetchall()
