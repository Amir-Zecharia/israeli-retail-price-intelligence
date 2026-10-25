"""Short-lived caches keyed by full DSN and all analytical parameters."""
import streamlit as st
from database import analytics

@st.cache_data(ttl=60,show_spinner=False,max_entries=128)
def query(name,dsn,**params):
    return analytics.query(name,dsn=dsn,**params)

@st.cache_data(ttl=60,show_spinner=False,max_entries=16)
def options(dsn):
    return analytics.options(dsn)
