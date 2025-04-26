import streamlit as st
import pandas as pd
from datetime import datetime

def show_log_explorer(logs: list):
    """Display the log explorer interface."""
    st.title("Log Explorer")
    
    # Search and filters
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    with col1:
        search_query = st.text_input("Search logs...", key="log_explorer_search")
    with col2:
        log_level = st.selectbox("Log Level", ["All Levels", "ERROR", "WARNING", "INFO", "DEBUG"])
    with col3:
        source = st.selectbox("Source", ["All Sources", "auth-service", "api-service", "worker-service"])
    with col4:
        col4_1, col4_2 = st.columns(2)
        with col4_1:
            if st.button("Refresh", key="log_explorer_refresh"):
                st.rerun()
        with col4_2:
            st.download_button(
                "Export",
                data=pd.DataFrame(logs).to_csv(index=False),
                file_name="logs.csv",
                mime="text/csv"
            )

    # Apply filters
    filtered_logs = logs
    if search_query:
        filtered_logs = [log for log in filtered_logs if search_query.lower() in log['message'].lower()]
    if log_level != "All Levels":
        filtered_logs = [log for log in filtered_logs if log['level'].upper() == log_level]
    if source != "All Sources":
        filtered_logs = [log for log in filtered_logs if log['service'] == source.lower()]

    # Display logs in a table
    if filtered_logs:
        df = pd.DataFrame(filtered_logs)
        df = df[['timestamp', 'level', 'service', 'message']]
        df.columns = ['Timestamp', 'Level', 'Service', 'Message']
        
        # Style the dataframe
        def highlight_level(val):
            if val == 'ERROR':
                return 'background-color: #ffebee; color: #c62828'
            elif val == 'WARNING':
                return 'background-color: #fff3e0; color: #ef6c00'
            elif val == 'INFO':
                return 'background-color: #e3f2fd; color: #1565c0'
            return ''
        
        styled_df = df.style.applymap(highlight_level, subset=['Level'])
        st.dataframe(styled_df, use_container_width=True)
    else:
        st.info("No logs found matching the filters.") 