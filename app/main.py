"""Run with: python -m streamlit run app/main.py."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st
from app import data
from app.ui import PAGES, LABELS, display_value, display_cell, safe_csv, english_text, product_label, english_rows

st.set_page_config(page_title='IRPI | Retail Price Intelligence',page_icon='◈',layout='wide')
st.markdown('''<style>
/* Keep Streamlit's structural/off-canvas geometry LTR. English content uses LTR throughout. */
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stSidebar"]{direction:ltr}
[data-testid="stMainBlockContainer"],[data-testid="stSidebarUserContent"]{direction:ltr;text-align:left}
[data-testid="stAppDeployButton"]{display:none} .stApp{background:#f5f7fb;color:#172a43} h1,h2,h3{letter-spacing:-.035em}
[data-testid="stSidebar"]{background:#edf2f8;border-left:1px solid #dde5ef}
[data-testid="stMetric"]{background:white;border:1px solid #dfe6ef;padding:20px;border-radius:12px}
[data-testid="stMetricLabel"]{color:#53647c} [data-testid="stMetricValue"]{color:#173859}
[data-testid="stDataFrame"]{direction:ltr} .eyebrow{font-size:12px;color:#377e89;letter-spacing:.12em;font-weight:700}
.block-container{padding-top:2.5rem;padding-bottom:4rem;max-width:1500px}
@media(max-width:640px){.block-container{padding:1rem}.stPlotlyChart{min-width:0}}
</style>''',unsafe_allow_html=True)
st.sidebar.markdown('## ◈ IRPI')
st.sidebar.caption('Retail price intelligence • Israel')
if st.sidebar.button('Refresh data'):
    data.query.clear(); data.options.clear()
st.sidebar.caption('Results cached for up to 60 seconds')
page=st.sidebar.radio('Navigation',PAGES,label_visibility='collapsed')
st.markdown('<div class="eyebrow">ISRAELI RETAIL PRICE INTELLIGENCE</div>',unsafe_allow_html=True)
st.title(page)
st.caption('Observed prices, exact comparisons and transparent data quality')

def connection():
    dsn=os.getenv('READ_DATABASE_URL')
    if not dsn:
        try: dsn=st.secrets.get('READ_DATABASE_URL')
        except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError): pass
    return dsn

def load(name,**params):
    with st.spinner('Loading PostgreSQL results…'):
        try: return english_rows(data.query(name,dsn=dsn,**params),opts['products'])
        except Exception:
            st.error('Unable to load data. Check the database connection and read permissions.'); return []

def table(rows,key,columns=None):
    if not rows:
        st.info('No data matches this selection. Try different dates or filters.'); return
    shown=[{LABELS.get(k,k):display_cell(k,v) for k,v in row.items() if (columns is None and k in LABELS) or (columns is not None and k in columns)} for row in rows]
    st.dataframe(pd.DataFrame(shown),hide_index=True,width='stretch')
    st.download_button('Download CSV',safe_csv(rows),file_name=f'irpi-{key}.csv',mime='text/csv',key=f'csv_{key}')
    if len(rows)>=1000: st.warning('Results are limited to 1,000 records. Narrow the filters for complete detail.')

def chart(rows,x,y,color=None,kind='bar'):
    if not rows or any(x not in r or y not in r for r in rows): return
    # A comparison bar represents one observed day, never a sum over history.
    if kind=='bar' and all(r.get('observation_date') is not None for r in rows):
        latest=max(r['observation_date'] for r in rows)
        rows=[r for r in rows if r['observation_date']==latest]
        st.caption(f"Comparison chart: latest observed day in selection, {latest:%d/%m/%Y}. Tables and exports retain the full period.")
    if kind=='line' and len({r.get('observation_date') for r in rows})<2:
        st.info('One observation day is insufficient for a historical chart. Observations remain available in the table; charts appear after more genuine days accumulate.')
        return
    df=pd.DataFrame([{k:display_value(v) for k,v in r.items()} for r in rows])
    if df[y].isna().all(): return
    if color=='chain_name' and 'comparison_chain_name' in df:
        df['comparison_pair']=df['chain_name']+' vs '+df['comparison_chain_name']
        color='comparison_pair'
    if kind=='line': df=df.sort_values(x)
    fn=px.line if kind=='line' else px.bar
    args=dict(data_frame=df,x=x,y=y,color=color,labels=LABELS,color_discrete_sequence=['#167d9a','#f0a544','#6b71b8','#4ba889'])
    if kind=='line': args['markers']=True
    fig=fn(**args)
    if kind=='bar': fig.update_layout(barmode='group')
    fig.update_traces(hovertemplate='%{x}<br>%{y:.2f}<extra>%{fullData.name}</extra>')
    fig.update_layout(font=dict(family='Arial',size=13),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='white',legend_title_text='',margin=dict(l=20,r=20,t=20,b=20),height=370)
    st.plotly_chart(fig,width='stretch')

dsn=connection()
if not dsn:
    st.info('Set READ_DATABASE_URL to a read-only PostgreSQL connection. See docs/dashboard.md for setup.'); st.stop()
try:
    with st.spinner('Loading filter options…'): opts=data.options(dsn)
except Exception:
    st.error('Database unavailable. Check READ_DATABASE_URL and read permissions.'); st.stop()
if not opts['samples']:
    st.info('No sample has been published yet. Data appears after successful collection and publication.'); st.stop()
with st.sidebar:
    st.divider(); st.markdown('#### Filters')
    sample=st.selectbox('Sample',opts['samples'],format_func=lambda s:f"{english_text(s['name'], 'Sample '+str(s['sample_id']))} · v{s['version']}")
    bounds=opts.get('date_bounds') or {}; first=bounds.get('start_date') or date.today(); last=bounds.get('end_date') or first
    start=st.date_input('Start date',value=first); end=st.date_input('End date',value=last)
    chains=st.multiselect('Chains',opts['chains'],default=opts['chains'],format_func=lambda c:english_text(c['chain_name'], 'Chain '+str(c['chain_id'])))
    chain_ids=[c['chain_id'] for c in chains]
    available=[s for s in opts['stores'] if s['chain_id'] in chain_ids]
    stores=st.multiselect('Stores',available,default=available,format_func=lambda s:english_text(s['store_name'], 'Store '+str(s['store_id'])))
    category=st.selectbox('Category',['All categories']+sorted({p['category'] for p in opts['products'] if p.get('category')}),format_func=lambda value:english_text(value,'Untranslated category'))
    search=st.text_input('Search product name or GTIN',placeholder='For example Kinder or 729…')
    matches=[p for p in opts['products'] if not search or search.casefold() in f"{product_label(p)} {p.get('gtin','')}".casefold()]
    selected=st.selectbox('Product',[None]+matches,format_func=lambda p:'All products' if p is None else f"{product_label(p)} · {p.get('gtin') or 'No GTIN'}")
    if search and not matches: st.warning('No products found.'); st.stop()
    if search and selected is None: st.info('Select a product from the search results to apply the filter.'); st.stop()
    st.caption('Filters apply to the selected panel and period. Collection quality is reported for the whole sample.')
if start>end:
    st.warning('Start date must be on or before end date.'); st.stop()
params=dict(sample_id=sample['sample_id'],start_date=start,end_date=end,chain_ids=chain_ids,store_ids=[s['store_id'] for s in stores],category=None if category=='All categories' else category,product_id=selected['product_id'] if selected else None)
st.caption(f"Sample v{sample['version']} · {start:%d/%m/%Y} – {end:%d/%m/%Y} · Shelf prices in ILS · Collection dates in Israel")
overview=load('overview',**params)
summary=overview[0] if overview else {}
metrics=st.columns(4)
for col,label,key in zip(metrics,['Published observations','Observed products','Observed stores','Period coverage'],['observed_records','observed_products','observed_stores','coverage']):
    value=summary.get(key)
    col.metric(label,('—' if value is None else f'{float(value):.0%}' if key=='coverage' else str(value)))
st.caption(f"Observed days: {summary.get('observed_dates',0)} · Complete common products: {summary.get('fixed_common_products',0)} · Coverage = observations / (selected products × selected stores × calendar days)")
st.caption(f"Panel chains: {summary.get('monitored_chains',0)} · Panel products: {summary.get('tracked_products',0)} · Observed changes: {summary.get('observed_changes',0)} across {summary.get('observed_transitions',0)} observation pairs")
st.caption(f"Actual observation period: {summary.get('first_observation') or '—'} – {summary.get('last_observation') or '—'} · Last successful collection for sample: {display_value(summary.get('last_successful_collection')) or '—'}")
st.divider()
if page==PAGES[0]:
    st.subheader('Latest observed prices')
    st.caption('Latest observation through the end date, possibly before the start date. Age is relative to the selected cutoff and does not confirm a current shelf price.')
    rows=load('latest_prices',**params)
    table(rows,'latest', ['observation_date','product_name_snapshot','gtin','chain_name_snapshot','store_name_snapshot','price_ils','age_days','collected_at','source_updated_at'])
    st.subheader('Category price gaps')
    rows=load('category_pricing',**params); chart(rows,'category','mean_gap_pct','chain_name'); table(rows,'categories')
elif page==PAGES[1]:
    st.subheader('Identical products, observed on the same day')
    st.caption('Gap = first chain price minus comparison chain price. Each chain uses its selected-store median; percentage gap uses the comparison chain as denominator. Store selection stays fixed throughout the period.')
    rows=load('retailer_comparison',**params)
    complete=st.checkbox('Complete common-product panel only',value=True)
    if complete: rows=[r for r in rows if r.get('fixed_panel_eligible')]
    chart(rows,'product_name','gap_pct','chain_name'); table(rows,'retailers')
    st.subheader('Category details'); table(load('category_pricing',**params),'category_comparison')
elif page==PAGES[2]:
    st.subheader('Product price history')
    if not selected: st.info('Select a product in the filters to view its history.'); st.stop()
    rows=load('price_changes',**params)
    chart(rows,'observation_date','price_ils','chain_name_snapshot','line')
    st.caption('A change was detected between observations; its exact time is unknown. Missing days are never filled.')
    table(rows,'history',['observation_date','chain_name_snapshot','store_name_snapshot','price_ils','previous_price','change_ils','change_pct','gap_days','first_detected_change_date'])
elif page==PAGES[3]:
    st.subheader('Fixed basket with declared quantities')
    if not opts['baskets']: st.info('No sealed basket is available for this sample.'); st.stop()
    basket=st.selectbox('Basket version',opts['baskets'],format_func=lambda b:f"{english_text(b['name'], 'Basket '+str(b['basket_id']))} · v{b['version']}")
    st.caption('Comparable totals require 100% coverage. Observed subtotals are not complete basket prices. Product/category filters may reduce coverage without changing basket composition.')
    rows=load('basket_costs',**params,basket_id=basket['basket_id'])
    names={s['store_id']:english_text(s['store_name'], 'Store '+str(s['store_id'])) for s in opts['stores']}
    rows=[dict(r,store_name_snapshot=names.get(r['store_id'],str(r['store_id']))) for r in rows]
    chart(rows,'store_name_snapshot','comparable_total'); table(rows,'basket')
    chart(rows,'observation_date','comparable_total','store_name_snapshot','line')
elif page==PAGES[4]:
    st.subheader('Pricing profiles and volatility')
    st.caption('Relative price level: 1 = average across chains for matched products. Measures are descriptive and do not establish coordination, causation or a promotion.')
    if summary.get('observed_dates',0)<2: st.info('Insufficient history to assess changes or stability. At least two observations are needed; one transition does not establish a stable behavioral profile.')
    profiles=load('pricing_profiles',**params); chart(profiles,'chain_name','relative_price_level'); table(profiles,'profiles')
    st.info('Within-chain spread requires at least two stores on the same day. Missing values are not zero spread.')
    st.subheader('Change frequency and magnitude'); table(load('price_volatility',**params),'volatility')
    st.subheader('Flags for investigation')
    left,right=st.columns(2)
    absolute=left.number_input('Absolute change threshold (ILS)',min_value=0.1,value=2.0,step=0.5)
    relative=right.number_input('Relative change threshold (%)',min_value=0.1,value=20.0,step=1.0)
    st.caption('A large-change flag requires both thresholds. Double-threshold sensitivity is also shown. A flag does not establish an incorrect price.')
    table(load('price_anomalies',**params,absolute_threshold=absolute,relative_threshold=relative),'anomalies',['observation_date','product_name_snapshot','chain_name_snapshot','price_ils','change_ils','change_pct','gap_days','large_change','stricter_large_change','repeated_increase','branch_sample_size','branch_deviation_pct','large_branch_deviation','observed_pairs','highly_variable'])
else:
    st.subheader('Collection health')
    a,b=st.columns(2)
    a.metric('Latest sample attempt',{'complete':'Complete','partial':'Partial','failed':'Failed','running':'Running'}.get(summary.get('latest_attempt_status'),summary.get('latest_attempt_status') or '—'))
    b.metric('Last successful collection for sample',display_value(summary.get('last_successful_collection')) or '—')
    st.caption('These two metrics cover the whole sample across all dates. Quality tables cover the selected period and are not filtered by product or store.')
    table(load('ingestion_quality',**params),'quality',['observation_date','started_at','completed_at','status','records_received','records_accepted','records_rejected','partition_coverage','rejection_rate','issue_count','is_published'])
    st.subheader('Daily publication calendar'); table(load('missing_days',**params),'missing')
    st.subheader('How to interpret the data')
    st.markdown(f"Current selection: **{summary.get('observed_products',0)} products**, **{summary.get('observed_stores',0)} stores** in a panel of **{summary.get('monitored_chains',0)} chains**, across **{summary.get('observed_dates',0)} observed days**. Actual period: **{summary.get('first_observation') or '—'} – {summary.get('last_observation') or '—'}**.")
    st.markdown('This small convenience sample does not represent Israel, every store in a chain, or the consumer basket.\n\nSources: official price-transparency publications from **Shufersal** and **Carrefour**. Products are matched by verified exact GTIN identity, with no similar-product substitution. Prices refer to the exact item and reported store; they are not a checkout price guarantee.\n\nOnly a complete validated extraction becomes a daily publication. Partial and failed runs remain recorded. A later complete same-day run can replace the publication with correction provenance. Timestamps are stored in UTC and displayed in **Asia/Jerusalem**. Source update time, where available, is distinct from collection time.\n\nPostgreSQL computes analytics from published observations. Dashboard visits never fetch provider data. Missing days are not filled, prices are not invented, and no causal relationship or coordination is inferred.')
    with st.expander('Sample selection and technical documentation'):
        st.write(english_text(sample['selection_method']))
        st.markdown('Full documentation: docs/methodology.md, docs/source_feasibility.md, docs/sql_analysis.md and docs/data_dictionary.md. Hosted collection and public deployment require separate verification.')
st.divider(); st.caption('IRPI · Transparent research sample · Observational data · No commercial recommendation')
