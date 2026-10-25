"""Bounded public official-feed reader; no cookies, login, proxy or bypass.

Portal discovery patterns independently implemented from their public listings.
Do not log Shufersal's signed download URL: store only its public listing URL.
"""
from __future__ import annotations

import gzip
import html
import io
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote
from zoneinfo import ZoneInfo
from xml.etree import ElementTree as ET

PORTALS = {
    'shufersal': 'https://prices.shufersal.co.il/FileObject/UpdateCategory?catID=2&storeId=0&page=1',
    'carrefour': 'https://prices.carrefour.co.il/',
}
MAX_BYTES = 32 * 1024 * 1024


def gtin14(code: str) -> str | None:
    if not code.isascii() or not code.isdigit() or len(code) not in (8, 12, 13, 14):
        return None
    if code.startswith(('20','21','22','23','24','25','26','27','28','29')):
        return None  # restricted-circulation / variable-weight prefixes
    total = sum(int(c) * (3 if i % 2 == 0 else 1) for i,c in enumerate(reversed(code[:-1])))
    return code.zfill(14) if (10-total%10)%10 == int(code[-1]) else None


def listing(chain: str, text: str) -> tuple[str, str]:
    if chain == 'shufersal':
        urls = [html.unescape(s) for s in re.findall(r'href="(https://[^"]+?\.gz[^"]*)"',text)]
        pairs = [(u.split('?')[0].rsplit('/',1)[-1],u) for u in urls]
    elif chain == 'carrefour':
        day = re.search(r"const path\s*=\s*'(\d{8})'",text)
        files = re.search(r'const files\s*=\s*(\[.*?\])',text,re.S)
        if not day or not files:
            raise ValueError('official listing format not recognized')
        pairs = [(r['name'].strip(), f"https://prices.carrefour.co.il/{day[1]}/{quote(r['name'].strip())}") for r in json.loads(files[1])]
    else:
        raise ValueError('unknown chain')
    pattern = r'PriceFull\d+-\d+-(?:\d+-\d{8}-\d{6}|\d+)\.gz'
    pairs = [(n,u) for n,u in pairs if re.fullmatch(pattern,n)]
    if not pairs:
        raise ValueError('no PriceFull file on bounded listing page')
    def newest(pair):
        fields = pair[0].removesuffix('.gz').split('-')
        timestamp = ''.join(fields[-2:]) if len(fields) == 5 else fields[-1]
        return timestamp, pair[0]
    return max(pairs, key=newest)


def unpack(content: bytes) -> bytes:
    if len(content) > MAX_BYTES:
        raise ValueError('compressed file exceeds byte ceiling')
    if content.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as f:
            content = f.read(MAX_BYTES+1)
    if len(content)>MAX_BYTES:
        raise ValueError('XML exceeds byte ceiling')
    if b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():
        raise ValueError('DTD and entities are not accepted')
    return content


def parse_prices(content: bytes, chain: str, collected_at: datetime) -> tuple[list[dict],int]:
    root = ET.fromstring(unpack(content))
    # Some publishers namespace XML; normalize element names only.
    for element in root.iter():
        element.tag = element.tag.rsplit('}',1)[-1].lower()
    def field(node, key):
        return (node.findtext(key.lower()) or '').strip()
    chain_id, store_id = field(root,'ChainId'),field(root,'StoreId')
    if not chain_id or not store_id:
        raise ValueError('missing file chain/store identifier')
    rows, rejected = [],0
    for item in root.iter('item'):
        code,name = field(item,'ItemCode'),field(item,'ItemName')
        try:
            price = Decimal(field(item,'ItemPrice'))
            if not code or not name or not price.is_finite() or price<=0:
                raise ValueError('invalid required item value')
            raw_time = field(item,'PriceUpdateDate') or field(item,'PriceUpdateTime')
            source_time = None
            if raw_time:
                timestamp = datetime.fromisoformat(raw_time)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=ZoneInfo('Asia/Jerusalem'))
                source_time = timestamp.astimezone(timezone.utc).isoformat()
            weighted = field(item,'bIsWeighted') or field(item,'IsWeighted')
            is_packaged = weighted.lower() in ('0','false') and field(item,'ItemType')=='1'
            rows.append(dict(source='official',chain=chain,chain_id=chain_id,store_id=store_id,
                product_id=code,product_name=name,price_ils=str(price),
                gtin=gtin14(code) if is_packaged else None,
                quantity=field(item,'Quantity'),unit=field(item,'UnitQty'),
                manufacturer=field(item,'ManufacturerName') or field(item,'ManufactureName'),
                source_updated_at=source_time,collected_at=collected_at.astimezone(timezone.utc).isoformat()))
        except (ValueError, InvalidOperation):
            rejected += 1
    return rows,rejected


def shared_products(rows: list[dict]) -> list[dict]:
    groups = {}
    for row in rows:
        if row['gtin']:
            groups.setdefault(row['gtin'],[]).append(row)
    shared = []
    for code,group in sorted(groups.items()):
        if len({r['chain_id'] for r in group})<2:
            continue
        # Check digit is necessary, not sufficient: require matching package fields.
        if not all(r['quantity'] and r['unit'] for r in group):
            continue
        if len({(r['quantity'],r['unit']) for r in group})!=1:
            continue
        shared.append(dict(gtin=code, identity_status='exact_gtin_package_match_pending_manual_review', records=group))
    return shared
