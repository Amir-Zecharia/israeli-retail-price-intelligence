"""Run: python -m pipeline.extract.probe --output artifacts/source_probe.json."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from .official import PORTALS, MAX_BYTES, listing, parse_prices, shared_products


def fetch(client, url, audit):
    # Two attempts max; 429/403 are terminal and no access restrictions are bypassed.
    for attempt in range(2):
        audit['requests'] += 1
        try:
            with client.stream('GET',url) as response:
                response.raise_for_status()
                body=bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body)>MAX_BYTES:
                        raise ValueError('response exceeds byte ceiling')
                return bytes(body)
        except (httpx.TimeoutException,httpx.NetworkError):
            if attempt: raise
            time.sleep(2)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='artifacts/source_probe.json')
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    result=dict(collected_at=now.isoformat(),environment='github_actions' if os.getenv('GITHUB_ACTIONS')=='true' else 'local',
        runner_url=(f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}" if os.getenv('GITHUB_RUN_ID') else None),
        source='official',chains=[],requests=0,records=[],cross_chain=[],gate_passed=False)
    rows=[]
    with httpx.Client(timeout=httpx.Timeout(30),follow_redirects=True,headers={'User-Agent':'IRPI-source-feasibility/0.1'}) as client:
        for chain,portal in PORTALS.items():
            evidence=dict(chain=chain,listing_url=portal,status='failed')
            try:
                page=fetch(client,portal,result).decode('utf-8-sig')
                name,url=listing(chain,page)
                content=fetch(client,url,result)
                parsed,rejected=parse_prices(content,chain,now)
                if not parsed: raise ValueError('no valid records')
                rows.extend(parsed)
                evidence.update(status='parsed',filename=name,sha256=hashlib.sha256(content).hexdigest(),
                    records_received=len(parsed)+rejected,records_accepted=len(parsed),records_rejected=rejected,
                    chain_id=parsed[0]['chain_id'],store_id=parsed[0]['store_id'])
            except Exception as exc:
                # Never include exception text: HTTP exceptions may contain signed URLs.
                evidence['error_type']=type(exc).__name__
                if isinstance(exc,httpx.HTTPStatusError): evidence['http_status']=exc.response.status_code
            result['chains'].append(evidence)
    matches=shared_products(rows)
    result['shared_candidates_count']=len(matches)
    result['cross_chain']=matches[:20]
    result['records']=[r for chain in PORTALS for r in [x for x in rows if x['chain']==chain][:3]]
    result['technical_probe_passed']=all(c['status']=='parsed' for c in result['chains']) and bool(matches)
    result['gate_blockers']=[f"{c['chain']}: {c.get('error_type','no valid records')}"
                             for c in result['chains'] if c['status'] != 'parsed']
    if not matches:
        result['gate_blockers'].append('No exact cross-chain GTIN/package candidates found.')
    if result['environment'] != 'github_actions':
        result['gate_blockers'].append('GitHub-hosted collection has not been verified by this local run.')
    result['gate_blockers'].append('Record sample identity review and source-use methodology separately before production selection.')
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('environment','requests','chains','shared_candidates_count','technical_probe_passed')},ensure_ascii=False))
    return 0 if result['technical_probe_passed'] else 1

if __name__=='__main__': raise SystemExit(main())
