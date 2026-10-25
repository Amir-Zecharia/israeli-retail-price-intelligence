"""Fixed-panel extraction and atomic, revision-preserving daily publication."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import hashlib,html,json,re,uuid
from pathlib import Path
from zoneinfo import ZoneInfo
import httpx
from psycopg.types.json import Jsonb
from database.connection import connect
from pipeline.extract.official import listing,parse_prices,gtin14
from pipeline.extract.probe import fetch


def normalize(records, products):
    panel={p['gtin']:p for p in products}
    counts=dict(received=0,accepted=0,rejected=0,duplicate=0)
    selected={}; blocked=set(); issues=[]
    for raw in records:
        key=raw.get('gtin')
        if key not in panel:
            continue
        counts['received']+=1
        try:
            p=panel[key]; price=Decimal(raw['price_ils'])
            if gtin14(key)!=key or not price.is_finite() or not 0<price<10000000 or not raw.get('product_name'):
                raise ValueError('invalid value')
            if Decimal(raw['quantity'])!=Decimal(p['quantity']) or raw['unit']!=p['unit']:
                raise ValueError('package mismatch')
            row=dict(raw,price_ils=price)
            if key in blocked:
                raise ValueError('conflicting identity')
            if key in selected:
                old=selected[key]
                if old['price_ils']==price and old.get('source_updated_at')==row.get('source_updated_at'):
                    counts['duplicate']+=1
                    continue
                del selected[key]; counts['accepted']-=1; counts['rejected']+=1; blocked.add(key)
                raise ValueError('conflicting duplicate')
            selected[key]=row; counts['accepted']+=1
        except (ValueError,KeyError,InvalidOperation):
            counts['rejected']+=1
            issues.append(dict(type='invalid_or_conflicting_record',gtin=key))
    return list(selected.values()),counts,issues


def fixed_listing(store,page):
    """Choose latest file ONLY within the immutable filename partition."""
    chain=store['chain']; wanted=store['filename_store_id']
    if chain=='shufersal':
        urls=[html.unescape(u) for u in re.findall(r'href="(https://[^"]+?\.gz[^"]*)"',page)]
        urls=[u for u in urls if re.fullmatch(r'PriceFull'+store['chain_id']+r'-\d+-'+wanted+r'-\d{8}-\d{6}\.gz',u.split('?')[0].rsplit('/',1)[-1])]
        if not urls: raise ValueError('fixed source partition unavailable')
        return listing(chain,''.join(f'<a href="{html.escape(u)}">' for u in urls))
    files=re.search(r'const files\s*=\s*(\[.*?\])',page,re.S)
    if not files: raise ValueError('manifest unavailable')
    entries=[r for r in json.loads(files[1]) if re.fullmatch(r'PriceFull'+store['chain_id']+r'-\d+-'+wanted+r'-\d{8}-\d{6}\.gz',r['name'].strip())]
    if not entries: raise ValueError('fixed source partition unavailable')
    return listing(chain,page[:files.start(1)]+json.dumps(entries)+page[files.end(1):])


def extract_partition(store,client,now,audit):
    page=fetch(client,store['listing_url'],audit).decode('utf-8-sig')
    name,url=fixed_listing(store,page)
    body=fetch(client,url,audit)
    rows,rejected=parse_prices(body,store['chain'],now)
    if not rows or any(r['chain_id']!=store['chain_id'] or r['store_id']!=store['store_id'] for r in rows):
        raise ValueError('XML identity differs from fixed manifest')
    return dict(store=store,rows=rows,parse_rejected=rejected,filename=name,sha256=hashlib.sha256(body).hexdigest(),collected_at=now.isoformat())


def seed(conn,manifest):
    sid=conn.execute("INSERT INTO sources(name,attribution) VALUES ('official','Official retailer price-transparency publications; Shufersal and Carrefour') ON CONFLICT(name) DO UPDATE SET attribution=excluded.attribution RETURNING source_id").fetchone()[0]
    stores={}; products={}
    for s in manifest['stores']:
        cid=conn.execute('INSERT INTO retail_chains(source_id,source_chain_identifier,chain_name) VALUES (%s,%s,%s) ON CONFLICT(source_id,source_chain_identifier) DO UPDATE SET chain_name=excluded.chain_name RETURNING chain_id',(sid,s['chain_id'],s['chain_name'])).fetchone()[0]
        stores[(s['chain_id'],s['store_id'])]=conn.execute('INSERT INTO stores(chain_id,source_store_identifier,store_name) VALUES (%s,%s,%s) ON CONFLICT(chain_id,source_store_identifier) DO UPDATE SET store_name=excluded.store_name RETURNING store_id',(cid,s['store_id'],s['store_name'])).fetchone()[0]
    for p in manifest['products']:
        cat=conn.execute('INSERT INTO categories(category_name) VALUES (%s) ON CONFLICT(category_name) DO UPDATE SET category_name=excluded.category_name RETURNING category_id',(p['category'],)).fetchone()[0]
        products[p['gtin']]=conn.execute('INSERT INTO products(gtin,product_name,manufacturer,category_id,quantity,unit) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(gtin) DO UPDATE SET product_name=excluded.product_name RETURNING product_id',(p['gtin'],p['product_name'],p.get('manufacturer'),cat,p['quantity'],p['unit'])).fetchone()[0]
    existing=conn.execute('SELECT sample_id,selection_method FROM samples WHERE name=%s AND version=%s',(manifest['name'],manifest['version'])).fetchone()
    fingerprint=hashlib.sha256(json.dumps(manifest,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    method=manifest['selection_method']+' manifest_sha256='+fingerprint
    if existing:
        sample=existing[0]
        if existing[1]!=method: raise ValueError('sample version already exists with different manifest')
    else:
        sample=conn.execute('INSERT INTO samples(name,version,selection_method) VALUES (%s,%s,%s) RETURNING sample_id',(manifest['name'],manifest['version'],method)).fetchone()[0]
        for store in stores.values(): conn.execute('INSERT INTO sample_stores VALUES (%s,%s)',(sample,store))
        for product in products.values(): conn.execute('INSERT INTO sample_products VALUES (%s,%s)',(sample,product))
    basket=conn.execute('SELECT basket_id FROM baskets WHERE name=%s AND version=%s',(manifest['name'],manifest['version'])).fetchone()
    if not basket:
        bid=conn.execute('INSERT INTO baskets(name,version,description) VALUES (%s,%s,%s) RETURNING basket_id',(manifest['name'],manifest['version'],method)).fetchone()[0]
        for p in manifest['products']: conn.execute('INSERT INTO basket_items VALUES (%s,%s,%s)',(bid,products[p['gtin']],p.get('basket_quantity','1')))
        conn.execute('UPDATE baskets SET sealed=true WHERE basket_id=%s',(bid,))
    return sample,stores,products


def ingest(manifest,dsn=None,extractor=extract_partition,now=None):
    now=now or datetime.now(timezone.utc)
    day=now.astimezone(ZoneInfo('Asia/Jerusalem')).date(); rid=uuid.uuid4(); audit={'requests':0}
    # Hold a session lock over allocation, extraction and publication to serialize reruns.
    with connect(dsn,autocommit=True) as conn:
        conn.execute('SELECT pg_advisory_lock(718291003)')
        try:
            with conn.transaction():
                sample,stores,products=seed(conn,manifest)
                conn.execute("UPDATE ingestion_runs SET status='abandoned',completed_at=now(),error_message='Recovered interrupted attempt after acquiring exclusive ingestion lock' WHERE sample_id=%s AND status='started'",(sample,))
                revision=conn.execute('SELECT coalesce(max(revision),0)+1 FROM ingestion_runs WHERE sample_id=%s AND observation_date=%s',(sample,day)).fetchone()[0]
                conn.execute('INSERT INTO ingestion_runs(ingestion_run_id,sample_id,observation_date,revision,expected_partitions,manifest,started_at) VALUES (%s,%s,%s,%s,%s,%s,%s)',(rid,sample,day,revision,len(stores),Jsonb(manifest),now))
            counts=Counter(); partitions=[]; issues=[]
            with httpx.Client(timeout=30,follow_redirects=True,headers={'User-Agent':'IRPI-fixed-pilot/1.0'}) as client:
                for store in manifest['stores']:
                    try:
                        part=extractor(store,client,now,audit)
                        rows,c,i=normalize(part['rows'],manifest['products']); counts.update(c)
                        issues.extend(i)
                        if part.get('parse_rejected'): issues.append(dict(type='source_parse_rejected',count=part['parse_rejected']))
                        part['rows']=rows; partitions.append(part)
                    except Exception as exc:
                        issues.append(dict(type='partition_failed',chain=store['chain'],error_type=type(exc).__name__))
            status='complete' if len(partitions)==len(stores) and not any(i['type'] in ('partition_failed','source_parse_rejected','invalid_or_conflicting_record') for i in issues) else ('partial' if partitions else 'failed')
            try:
                with conn.transaction():
                    for part in partitions:
                        store=part['store']; store_id=stores[(store['chain_id'],store['store_id'])]
                        fileid=conn.execute('INSERT INTO source_files(ingestion_run_id,store_id,source_url,sha256,collected_at) VALUES (%s,%s,%s,%s,%s) RETURNING source_file_id',(rid,store_id,store['listing_url'],part['sha256'],part['collected_at'])).fetchone()[0]
                        for row in part['rows']:
                            p=next(p for p in manifest['products'] if p['gtin']==row['gtin'])
                            chain_id=conn.execute('SELECT chain_id FROM stores WHERE store_id=%s',(store_id,)).fetchone()[0]
                            conn.execute('INSERT INTO source_products(chain_id,source_product_identifier,product_id,mapping_method) VALUES (%s,%s,%s,%s) ON CONFLICT(chain_id,source_product_identifier) DO NOTHING',(chain_id,row['product_id'],products[row['gtin']],'reviewed_exact_gtin_package'))
                            mapped=conn.execute('SELECT product_id FROM source_products WHERE chain_id=%s AND source_product_identifier=%s',(chain_id,row['product_id'])).fetchone()[0]
                            if mapped!=products[row['gtin']]: raise ValueError('source product identity mapping changed')
                            conn.execute('INSERT INTO price_observations(ingestion_run_id,store_id,product_id,price_ils,collected_at,source_updated_at,source_file_id,source_product_identifier,product_name_snapshot,store_name_snapshot,chain_name_snapshot,category_name_snapshot,quantity_snapshot,unit_snapshot) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(rid,store_id,products[row['gtin']],row['price_ils'],part['collected_at'],row.get('source_updated_at'),fileid,row.get('product_id'),row['product_name'],store['store_name'],store['chain_name'],p['category'],p['quantity'],p['unit']))
                    for issue in issues: conn.execute('INSERT INTO data_quality_issues(ingestion_run_id,severity,issue_type,details) VALUES (%s,%s,%s,%s)',(rid,'error',issue['type'],Jsonb(issue)))
                    provenance=[{k:v for k,v in p.items() if k not in ('rows','store')} for p in partitions]
                    conn.execute('UPDATE ingestion_runs SET status=%s,completed_at=now(),fetched_partitions=%s,records_received=%s,records_accepted=%s,records_rejected=%s,records_duplicate=%s,manifest=%s WHERE ingestion_run_id=%s',(status,len(partitions),counts['received'],counts['accepted'],counts['rejected'],counts['duplicate'],Jsonb(dict(sample=manifest,files=provenance,requests=audit['requests'])),rid))
                    if status=='complete': conn.execute('INSERT INTO daily_publications VALUES (%s,%s,%s) ON CONFLICT(sample_id,observation_date) DO UPDATE SET ingestion_run_id=excluded.ingestion_run_id',(sample,day,rid))
            except Exception as exc:
                conn.execute("UPDATE ingestion_runs SET status='failed',completed_at=now(),error_message=%s WHERE ingestion_run_id=%s",('transaction rollback: '+type(exc).__name__,rid))
                raise
            return dict(ingestion_run_id=str(rid),status=status,revision=revision,observation_date=str(day),partitions=len(partitions),**dict(counts),issues=len(issues))
        finally: conn.execute('SELECT pg_advisory_unlock(718291003)')


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--manifest',default='config/pilot_v1.json'); args=parser.parse_args()
    result=ingest(json.loads(Path(args.manifest).read_text()))
    print(json.dumps(result)); return 0 if result['status']=='complete' else 1

if __name__=='__main__': raise SystemExit(main())
