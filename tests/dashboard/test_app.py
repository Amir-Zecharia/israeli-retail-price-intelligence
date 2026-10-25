from datetime import date
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from app.ui import PAGES, safe_csv
import pytest

@pytest.fixture(autouse=True)
def clear_cache():
    from app import data
    data.query.clear(); data.options.clear()
    yield
    data.query.clear(); data.options.clear()

OPTIONS = dict(samples=[dict(sample_id=1,name='פיילוט',version=1,selection_method='fixed')], chains=[dict(chain_id=1,chain_name='רשת א')],stores=[dict(store_id=1,chain_id=1,store_name='סניף א')],products=[dict(product_id=1,gtin='0123456789012',product_name='חלב',category='מזון')],baskets=[dict(basket_id=1,name='סל',version=1)],date_bounds=dict(start_date=date(2026,10,24),end_date=date(2026,10,24)))

def test_csv_formula_neutralization():
    data=safe_csv([{'name':'=SUM(A1)','barcode':'00123','price':-2}]).decode('utf-8-sig')
    assert "'=SUM" in data and '00123' in data and '-2' in data

def test_all_pages_empty_and_filters(monkeypatch):
    monkeypatch.setenv('READ_DATABASE_URL','test')
    calls=[]
    def query(name,**kwargs):
        calls.append((name,kwargs)); return []
    with patch('database.analytics.options',return_value=OPTIONS),patch('database.analytics.query',side_effect=query):
        at=AppTest.from_file(Path(__file__).resolve().parents[2]/'app/main.py',default_timeout=15).run()
        for page in PAGES:
            at.sidebar.radio[0].set_value(page).run()
            assert not at.exception
        at.sidebar.multiselect[0].set_value([]).run()
        assert calls[-1][1]['chain_ids']==[]
        assert calls[-1][1]['start_date']==date(2026,10,24)

def test_missing_configuration(monkeypatch):
    monkeypatch.delenv('READ_DATABASE_URL',raising=False)
    monkeypatch.delenv('DATABASE_URL',raising=False)
    at=AppTest.from_file(Path(__file__).resolve().parents[2]/'app/main.py',default_timeout=15).run()
    assert not at.exception
    assert at.info

def test_all_pages_populated_and_history(monkeypatch):
    monkeypatch.setenv('READ_DATABASE_URL','test')
    from database import analytics
    summary=dict(observed_records=2,observed_products=1,observed_stores=1,coverage=1,observed_dates=1,fixed_common_products=1)
    row=dict(observation_date=date(2026,10,24),product_id=1,product_name='חלב',product_name_snapshot='חלב',chain_name='רשת א',chain_name_snapshot='רשת א',store_id=1,store_name_snapshot='סניף א',price_ils=10,comparable_total=10,relative_price_level=1,gap_pct=0,mean_gap_pct=0,category='מזון',fixed_panel_eligible=True)
    with patch.object(analytics,'options',return_value=OPTIONS),patch.object(analytics,'query',side_effect=lambda name,**kw:[summary] if name=='overview' else [row]):
        at=AppTest.from_file(Path(__file__).resolve().parents[2]/'app/main.py',default_timeout=15).run()
        for page in PAGES:
            at.sidebar.radio[0].set_value(page).run()
            if page==PAGES[2]:
                at.sidebar.selectbox[2].select_index(1).run()
                assert any('One observation day' in v.value for v in at.info)
            assert not at.exception
            assert at.dataframe
            if page==PAGES[5]:
                text=' '.join(v.value for v in at.markdown)
                assert '**1 observed days**' in text
                assert '24/10/2026' not in text


def test_live_readonly_pages(monkeypatch):
    import os
    import pytest
    dsn=os.getenv('DASHBOARD_TEST_DATABASE_URL')
    if not dsn: pytest.skip('Optional genuine local read-only database smoke test')
    monkeypatch.setenv('READ_DATABASE_URL',dsn)
    at=AppTest.from_file(Path(__file__).resolve().parents[2]/'app/main.py',default_timeout=20).run()
    for page in PAGES:
        at.sidebar.radio[0].set_value(page).run()
        if page==PAGES[2]: at.sidebar.selectbox[2].select_index(1).run()
        assert not at.exception
        assert not at.error
        assert at.dataframe
        assert_english_render(at)

def test_search_selection_and_invalid_dates(monkeypatch):
    monkeypatch.setenv('READ_DATABASE_URL','test')
    calls=[]
    def query(name,**kwargs): calls.append(kwargs); return []
    with patch('database.analytics.options',return_value=OPTIONS),patch('database.analytics.query',side_effect=query):
        at=AppTest.from_file(Path(__file__).resolve().parents[2]/'app/main.py',default_timeout=15).run()
        at.sidebar.text_input[0].set_value('012345').run()
        assert any('Select a product' in v.value for v in at.info)
        at.sidebar.selectbox[2].select_index(1).run()
        assert calls[-1]['product_id']==1
        at.sidebar.date_input[0].set_value(date(2026,10,25)).run()
        assert any('Start date' in v.value for v in at.warning)
        assert not at.exception


def test_database_error_is_sanitized(monkeypatch):
    monkeypatch.setenv('READ_DATABASE_URL','test')
    with patch('database.analytics.options',side_effect=RuntimeError('password=do-not-display')):
        at=AppTest.from_file(Path(__file__).resolve().parents[2]/'app/main.py').run()
        assert at.error and not at.exception
        assert all('do-not-display' not in v.value for v in at.error)


def test_currency_display_has_two_decimal_places():
    from decimal import Decimal
    from app.ui import display_cell
    assert display_cell('gap_ils',1.6999999999999986)=='1.70'
    assert display_cell('price_ils',Decimal('12'))=='12.00'
    assert display_cell('comparable_total',None) is None
    assert display_cell('observed_products',11)==11
    assert display_cell('gap_pct',1.6999999999999986)=='1.70%'
    assert display_cell('coverage',Decimal('0.75'))=='75.0%'


def test_comparison_bars_use_latest_day_without_summing_history(monkeypatch):
    import streamlit as st
    monkeypatch.setenv('READ_DATABASE_URL','test')
    options=dict(OPTIONS,date_bounds=dict(start_date=date(2026,10,24),end_date=date(2026,10,25)))
    rows=[dict(observation_date=day,product_id=1,product_name='חלב',chain_name='א',comparison_chain_name='ב',store_id=1,category='מזון',gap_pct=value,mean_gap_pct=value,comparable_total=value,price_ils=value,fixed_panel_eligible=True) for day,value in [(date(2026,10,24),100),(date(2026,10,25),7)]]
    summary=dict(observed_dates=2,observed_records=2)
    with patch('database.analytics.options',return_value=options),patch('database.analytics.query',side_effect=lambda name,**kw:[summary] if name=='overview' else rows),patch.object(st,'plotly_chart') as plot:
        at=AppTest.from_file(Path(__file__).resolve().parents[2]/'app/main.py',default_timeout=15).run()
        for page in (PAGES[0],PAGES[1],PAGES[3]):
            plot.reset_mock()
            at.sidebar.radio[0].set_value(page).run()
            assert not at.exception
            bars=[call.args[0] for call in plot.call_args_list if call.args[0].data[0].type=='bar']
            assert bars
            for fig in bars:
                assert [float(value) for trace in fig.data for value in trace.y]==[7]
            assert any('25/10/2026' in v.value for v in at.caption)
            assert len(at.dataframe[-1].value)==2


def test_single_day_time_chart_is_not_rendered(monkeypatch):
    import streamlit as st
    monkeypatch.setenv('READ_DATABASE_URL','test')
    row=dict(observation_date=date(2026,10,24),store_id=1,price_ils=10,comparable_total=10,chain_name_snapshot='א')
    with patch('database.analytics.options',return_value=OPTIONS),patch('database.analytics.query',side_effect=lambda name,**kw:[dict(observed_dates=1)] if name=='overview' else [row]),patch.object(st,'plotly_chart') as plot:
        at=AppTest.from_file(Path(__file__).resolve().parents[2]/'app/main.py',default_timeout=15).run()
        for page in (PAGES[2],PAGES[3]):
            at.sidebar.radio[0].set_value(page).run()
            if page==PAGES[2]: at.sidebar.selectbox[2].select_index(1).run()
            plot.reset_mock(); at.run()
            assert not at.exception
            assert not [call for call in plot.call_args_list if call.args[0].data[0].type=='scatter']
            assert any('One observation day' in v.value for v in at.info)


def assert_english_render(at):
    from app.ui import has_hebrew
    for kind in ('title','header','subheader','caption','markdown','info','warning','error','metric','text_input','selectbox','multiselect','radio','checkbox','button','number_input','date_input'):
        for item in getattr(at,kind):
            for field in ('label','value','options','placeholder'):
                value=getattr(item,field,None)
                # Widget values can contain source dictionaries internally; only
                # their formatted options, labels and text are public UI.
                if isinstance(value,str): assert not has_hebrew(value),(kind,field,value)
                if field=='options' and value:
                    assert not has_hebrew(str(value)),(kind,field,value)
    for item in at.dataframe:
        assert not has_hebrew(item.value.to_string())


def test_rendered_labels_and_exports_are_english(monkeypatch):
    from app.ui import english_rows,has_hebrew,product_label
    monkeypatch.setenv('READ_DATABASE_URL','test')
    raw=dict(product_id=1,gtin='00000040084107',product_name='ביצת קינדר',product_name_snapshot='ביצת קינדר',chain_name='שופרסל',chain_name_snapshot='שופרסל',store_name_snapshot='סניף לא מתורגם',store_id=1,category='מזון ארוז',observation_date=date(2026,10,24),price_ils=10,gap_pct=1,mean_gap_pct=1,comparable_total=10,relative_price_level=1,fixed_panel_eligible=True)
    assert product_label(raw)=='Kinder Surprise egg 20 g'
    translated=english_rows([raw])
    assert not has_hebrew(str(translated))
    assert not has_hebrew(safe_csv([raw]).decode('utf-8-sig'))
    assert raw['product_name']=='ביצת קינדר'
    with patch('database.analytics.options',return_value=OPTIONS),patch('database.analytics.query',side_effect=lambda name,**kw:[dict(observed_dates=1)] if name=='overview' else [raw]):
        at=AppTest.from_file(Path(__file__).resolve().parents[2]/'app/main.py',default_timeout=15).run()
        for page in PAGES:
            at.sidebar.radio[0].set_value(page).run()
            if page==PAGES[2]: at.sidebar.selectbox[2].select_index(1).run()
            assert not at.exception
            assert_english_render(at)


def test_english_export_preserves_measurement_identity_and_values():
    import csv, io
    from decimal import Decimal
    from app.ui import english_rows
    raw = dict(gtin='00000040084107', quantity_snapshot=Decimal('20.00'), unit_snapshot='גרם', unit='מיליליטר', price_ils=Decimal('8.50'))
    translated = english_rows([raw])[0]
    assert translated['unit_snapshot']=='g' and translated['unit']=='ml'
    for key in ('gtin','quantity_snapshot','price_ils'): assert translated[key]==raw[key]
    exported=list(csv.DictReader(io.StringIO(safe_csv([raw]).decode('utf-8-sig'))))[0]
    assert exported['unit_snapshot']=='g' and exported['unit']=='ml'
    assert exported['GTIN']=='00000040084107'
    assert Decimal(exported['quantity_snapshot'])==Decimal('20.00')
    assert Decimal(exported['Price (ILS)'])==Decimal('8.50')
    assert raw['unit_snapshot']=='גרם'
