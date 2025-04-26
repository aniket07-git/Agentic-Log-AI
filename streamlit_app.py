import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from loki_client import LokiClient

# Initialize Loki client
loki_client = LokiClient()

# Page config
st.set_page_config(
    page_title="LogAnalytics Dashboard",
    page_icon="📊",
    layout="wide"
)

# Title and description
st.title("LogAnalytics")

# Sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Select Page",
    ["Dashboard", "Log Explorer", "Error Analysis", "Sources", "Settings"],
    index=0
)

# Search and time range in the main area
col1, col2 = st.columns([3, 1])

with col1:
    search_query = st.text_input("Search logs...", "")

with col2:
    time_range = st.selectbox(
        "Time Range",
        ["Last 24 hours", "Last 7 days", "Last 30 days", "Custom"],
        index=0
    )

# Calculate time range
now = datetime.now()
if time_range == "Last 24 hours":
    start_time = now - timedelta(days=1)
elif time_range == "Last 7 days":
    start_time = now - timedelta(days=7)
elif time_range == "Last 30 days":
    start_time = now - timedelta(days=30)
else:
    col1, col2 = st.columns(2)
    with col1:
        start_time = st.date_input("Start date", now - timedelta(days=1))
    with col2:
        end_time = st.date_input("End date", now)

# Metrics cards
col1, col2, col3, col4 = st.columns(4)

# Get metrics from Loki
metrics = loki_client.get_metrics(start_time, now)

# Error count
with col1:
    st.markdown("""
        <div style='padding: 20px; background-color: #ffffff; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'>
            <h2 style='color: #ff4b4b; margin: 0; font-size: 36px;'>0</h2>
            <p style='margin: 0;'>Errors</p>
            <small style='color: #666;'>Last updated: {}</small>
        </div>
    """.format(now.strftime("%H:%M:%S")), unsafe_allow_html=True)

# Warning count
with col2:
    st.markdown("""
        <div style='padding: 20px; background-color: #ffffff; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'>
            <h2 style='color: #ffd700; margin: 0; font-size: 36px;'>0</h2>
            <p style='margin: 0;'>Warnings</p>
            <small style='color: #666;'>Last updated: {}</small>
        </div>
    """.format(now.strftime("%H:%M:%S")), unsafe_allow_html=True)

# Info count
with col3:
    st.markdown("""
        <div style='padding: 20px; background-color: #ffffff; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'>
            <h2 style='color: #2196f3; margin: 0; font-size: 36px;'>0</h2>
            <p style='margin: 0;'>Info</p>
            <small style='color: #666;'>Last updated: {}</small>
        </div>
    """.format(now.strftime("%H:%M:%S")), unsafe_allow_html=True)

# Resolved count
with col4:
    st.markdown("""
        <div style='padding: 20px; background-color: #ffffff; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'>
            <h2 style='color: #4caf50; margin: 0; font-size: 36px;'>0</h2>
            <p style='margin: 0;'>Resolved</p>
            <small style='color: #666;'>Last updated: {}</small>
        </div>
    """.format(now.strftime("%H:%M:%S")), unsafe_allow_html=True)

# Recent Error Analysis
st.subheader("Recent Error Analysis")

# Query Loki for recent errors
error_query = '{level="ERROR"}' if not search_query else '{level="ERROR"} |= "' + search_query + '"'
errors = loki_client.query_range(
    query=error_query,
    start=start_time,
    end=now,
    limit=100
)

if errors:
    error_df = pd.DataFrame(errors)
    st.dataframe(
        error_df[['timestamp', 'log', 'labels']],
        hide_index=True,
        use_container_width=True
    )
else:
    st.info("No errors found in the selected time range.")

# Recommended Resolutions
st.subheader("Recommended Resolutions")

# Add auto-refresh button
if st.button("Refresh"):
    st.experimental_rerun()

# Update requirements.txt
with open("requirements.txt", "a") as f:
    f.write("\nstreamlit>=1.24.0\npandas>=1.5.0\n") 