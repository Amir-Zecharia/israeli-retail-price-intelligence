"""Presentation helpers only; analytical calculations belong in PostgreSQL."""
import csv
import io
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

PAGES=('Market Overview','Retailer Comparison','Product Price History','Basket Comparison','Pricing Behavior','Data Quality & Methodology')
LABELS={'observation_date': 'Observation date', 'product_name': 'Product name', 'product_name_snapshot': 'Product name snapshot', 'chain_name': 'Chain name', 'chain_name_snapshot': 'Chain name snapshot', 'store_name_snapshot': 'Store name snapshot', 'comparison_chain_name': 'Comparison chain name', 'price_ils': 'Price (ILS)', 'median_price': 'Median price', 'comparison_price': 'Comparison price', 'gap_ils': 'Gap (ILS)', 'gap_pct': 'Gap (%)', 'gtin': 'GTIN', 'category': 'Category', 'category_name_snapshot': 'Category name snapshot', 'coverage': 'Coverage', 'observed_products': 'Observed products', 'selected_products': 'Selected products', 'observed_dates': 'Observed dates', 'relative_price_level': 'Relative price level', 'change_frequency': 'Change frequency', 'branch_spread_ils': 'Branch spread (ILS)', 'typical_movement_pct': 'Typical movement (%)', 'comparable_total': 'Complete basket (ILS)', 'observed_subtotal': 'Observed subtotal (ILS)', 'required_products': 'Required products', 'missing_product_ids': 'Missing product ids', 'previous_price': 'Previous price', 'change_ils': 'Change (ILS)', 'change_pct': 'Change (%)', 'gap_days': 'Gap days', 'observed_pairs': 'Observed pairs', 'observation_count': 'Observation count', 'change_count': 'Change count', 'consecutive_pairs': 'Consecutive pairs', 'status': 'Status', 'records_received': 'Records received', 'records_accepted': 'Records accepted', 'records_rejected': 'Records rejected', 'started_at': 'Started at', 'completed_at': 'Completed at', 'is_published': 'Is published', 'issue_count': 'Issue count', 'partition_coverage': 'Partition coverage', 'rejection_rate': 'Rejection rate', 'missing_publication': 'Missing publication', 'age_days': 'Age days', 'collected_at': 'Collected at (Israel)', 'source_updated_at': 'Source updated at (Israel)', 'matched_products': 'Matched products', 'fixed_panel_products': 'Fixed panel products', 'mean_gap_ils': 'Mean gap (ILS)', 'mean_gap_pct': 'Mean gap (%)', 'median_gap_pct': 'Median gap (%)', 'branch_coverage': 'Branch coverage', 'observed_stores': 'Observed stores', 'expected_stores': 'Expected stores', 'fixed_panel_eligible': 'Fixed panel eligible', 'maximum_gap_days': 'Maximum gap days', 'large_change': 'Large change', 'stricter_large_change': 'Stricter large change', 'repeated_increase': 'Repeated increase', 'branch_sample_size': 'Branch sample size', 'large_branch_deviation': 'Large branch deviation', 'highly_variable': 'Highly variable', 'branch_deviation_pct': 'Branch deviation (%)', 'chain_comparable_total': 'Chain comparable total', 'chain_store_coverage': 'Chain store coverage', 'basket_name': 'Basket name', 'version': 'Version', 'complete_stores': 'Complete stores', 'panel_stores': 'Panel stores', 'first_detected_change_date': 'First detected change date', 'typical_change_pct': 'Typical change (%)', 'maximum_change_pct': 'Maximum change (%)', 'minimum_change_pct': 'Minimum change (%)', 'consecutive_change_frequency': 'Consecutive change frequency'}

def display_value(value):
    if isinstance(value,datetime):
        return value.astimezone(ZoneInfo('Asia/Jerusalem')).strftime('%d/%m/%Y %H:%M %Z')
    if isinstance(value,Decimal): return float(value)
    if isinstance(value,(list,dict)): return english_text(str(value))
    if isinstance(value,str): return english_text(value)
    return value

def safe_csv(rows):
    rows=english_rows(rows)
    stream=io.StringIO(); keys=list(rows[0]) if rows else []
    writer=csv.writer(stream); writer.writerow([LABELS.get(k,k) for k in keys])
    for row in rows:
        values=[]
        for key in keys:
            value=display_value(row.get(key))
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r')): value="'"+value
            values.append(value)
        writer.writerow(values)
    return stream.getvalue().encode('utf-8-sig')


CURRENCY_FIELDS = frozenset({
    'price_ils','median_price','comparison_price','gap_ils','mean_gap_ils',
    'branch_spread_ils','comparable_total','observed_subtotal','previous_price',
    'change_ils','chain_comparable_total',
})
RATIO_FIELDS = frozenset({
    'coverage','branch_coverage','chain_store_coverage','partition_coverage',
    'rejection_rate','change_frequency','consecutive_change_frequency',
})

def display_cell(key,value):
    """Format presentation cells without modifying SQL values or raw exports."""
    if value is None: return None
    if isinstance(value,(int,float,Decimal)) and not isinstance(value,bool):
        if key in CURRENCY_FIELDS: return f'{value:,.2f}'
        if key in RATIO_FIELDS: return f'{value:.1%}'
        if key.endswith('_pct'): return f'{value:,.2f}%'
        if key=='relative_price_level': return f'{value:.3f}'
    return display_value(value)


# Display-only labels reviewed against the pilot GTIN/package manifest.
# Source records and SQL filters retain their original identifiers and text.
PRODUCT_LABELS = {
'00000040084107':'Kinder Surprise egg 20 g',
'00000054051157':'Alpro chocolate soy dessert 4-pack, 500 g',
'00000072917329':'Egozi chocolate bar 45 g',
'00000072917367':'Elite Taami bar 40 g',
'00000072940754':'Milky vanilla dessert 170 ml',
'00000080042563':'Mutti tomato puree 700 g',
'00000080052760':'Kinder Bueno 2 × 21.5 g',
'00000080176800':'Nutella spread 750 g',
'00000080177609':'Kinder chocolate fingers 50 g',
'00000080177616':'Kinder chocolate fingers 100 g',
'00000080310891':'Kinder Joy egg 20 g',
}
TEXT_LABELS = {
'\u05d2\u05e8\u05dd':'g',
'\u05de\u05d9\u05dc\u05d9\u05dc\u05d9\u05d8\u05e8':'ml',
'\u05e9\u05d5\u05e4\u05e8\u05e1\u05dc':'Shufersal',
'\u05e7\u05e8\u05e4\u05d5\u05e8':'Carrefour',
'\u05de\u05d6\u05d5\u05df \u05d0\u05e8\u05d5\u05d6':'Packaged food',
'\u05d7\u05dc\u05d1 \u05d5\u05ea\u05d7\u05dc\u05d9\u05e4\u05d9\u05dd':'Dairy and alternatives',
}

def has_hebrew(text):
    return any('\u0590' <= c <= '\u05ff' for c in str(text))

def english_text(value,fallback='Label unavailable in English'):
    if not isinstance(value,str): return value
    if value in TEXT_LABELS: return TEXT_LABELS[value]
    for original,english in TEXT_LABELS.items():
        if value.startswith(original+' — '):
            identifier=value.rsplit(' ',1)[-1]
            return f'{english} — source store {identifier}' if identifier.isascii() else english
    return fallback if has_hebrew(value) else value

def product_label(product):
    gtin=str(product.get('gtin') or '')
    return PRODUCT_LABELS.get(gtin.zfill(14),english_text(product.get('product_name',''),f'Product {gtin or product.get("product_id","unknown")}'))

def english_rows(rows,products=()):
    lookup={p['product_id']:p for p in products}
    result=[]
    for original in rows:
        row=dict(original)
        product=lookup.get(row.get('product_id'),row)
        for key,value in row.items():
            if key in ('product_name','product_name_snapshot'):
                row[key]=product_label(dict(product,product_name=value))
            elif key in ('store_name','store_name_snapshot'):
                row[key]=english_text(value,f'Store {row.get("source_store_identifier") or row.get("store_id","unknown")}')
            elif key=='basket_name': row[key]=english_text(value,f'Basket {row.get("basket_id","unknown")}')
            elif isinstance(value,str): row[key]=english_text(value)
        result.append(row)
    return result
