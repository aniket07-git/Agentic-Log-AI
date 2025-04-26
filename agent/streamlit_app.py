import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
from log_analyser import LogAnalyzer
from typing import List, Dict
from collections import defaultdict
from components.error_resolution import show_error_resolution
from components.log_explorer import show_log_explorer
from components.sources import show_sources
from components.loki_client import LokiClient

# Initialize session state
if 'log_data' not in st.session_state:
    st.session_state.log_data = {
        'errors': 0,
        'warnings': 0,
        'info': 0,
        'resolved': 0,
        'error_analysis': [],
        'log_entries': [],
        'last_updated': datetime.now().strftime('%H:%M:%S'),
        'selected_error': None,
        'current_view': 'dashboard'
    }

if 'selected_time_range' not in st.session_state:
    st.session_state.selected_time_range = 'Last 24 hours'

if 'loki_config' not in st.session_state:
    st.session_state.loki_config = {
        'is_configured': False,
        'url': 'http://localhost:3100',
        'username': '',
        'password': '',
        'verify_ssl': True
    }

# Initialize LogAnalyzer
log_analyzer = LogAnalyzer()

# Configure page
st.set_page_config(
    page_title="LogAnalytics",
    page_icon="📊",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background-color: #f8f9fa;
    }
    .metric-card {
        background-color: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    .metric-label {
        color: #6c757d;
        font-size: 1rem;
    }
    .error-value { color: #dc3545; }
    .warning-value { color: #ffc107; }
    .info-value { color: #0d6efd; }
    .resolved-value { color: #198754; }
    .last-updated {
        font-size: 0.8rem;
        color: #6c757d;
        margin-top: 0.5rem;
    }
    .search-container {
        background-color: white;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    .section-header {
        font-size: 1.2rem;
        font-weight: 500;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def get_time_range_minutes(time_range: str) -> int:
    """Convert time range string to minutes."""
    if time_range == "Last 24 hours":
        return 24 * 60
    elif time_range == "Last 7 days":
        return 7 * 24 * 60
    elif time_range == "Last 30 days":
        return 30 * 24 * 60
    else:  # Default to last hour
        return 60

def fetch_loki_logs(time_range: str = "Last 24 hours") -> List[Dict]:
    """Fetch logs from Loki for the specified time range."""
    if not st.session_state.loki_config.get('is_configured'):
        return []

    end_time = datetime.utcnow()
    minutes = get_time_range_minutes(time_range)
    start_time = end_time - timedelta(minutes=minutes)
    
    # Convert to nanoseconds (Loki uses nanosecond timestamps)
    start_ns = int(start_time.timestamp() * 1e9)
    end_ns = int(end_time.timestamp() * 1e9)
    
    url = f"{st.session_state.loki_config['url']}/loki/api/v1/query_range"
    query = '{job="simulated_system"}'  # You can customize this query
    
    params = {
        'query': query,
        'start': start_ns,
        'end': end_ns,
        'limit': 1000
    }
    
    headers = {'Content-Type': 'application/json'}
    auth = None
    if st.session_state.loki_config.get('username') and st.session_state.loki_config.get('password'):
        auth = (st.session_state.loki_config['username'], st.session_state.loki_config['password'])
    
    try:
        response = requests.get(
            url, 
            params=params, 
            headers=headers,
            auth=auth,
            verify=st.session_state.loki_config['verify_ssl']
        )
        response.raise_for_status()
        data = response.json()
        
        logs = []
        if 'data' in data and 'result' in data['data']:
            for stream in data['data']['result']:
                for value in stream['values']:
                    timestamp, message = value
                    # Try to extract log level from message
                    level = 'info'
                    if 'ERROR' in message.upper():
                        level = 'error'
                    elif 'WARN' in message.upper():
                        level = 'warning'
                    
                    logs.append({
                        'timestamp': datetime.fromtimestamp(int(timestamp) / 1e9).strftime('%Y-%m-%d %H:%M:%S'),
                        'message': message,
                        'level': level,
                        'service': stream.get('stream', {}).get('job', 'unknown')
                    })
        return logs
    except Exception as e:
        st.error(f"Error fetching logs from Loki: {str(e)}")
        return []

def update_dashboard():
    """Update dashboard with latest log data from Loki."""
    logs = fetch_loki_logs(st.session_state.selected_time_range)
    
    # Update metrics
    st.session_state.log_data.update({
        'errors': sum(1 for log in logs if log['level'] == 'error'),
        'warnings': sum(1 for log in logs if log['level'] == 'warning'),
        'info': sum(1 for log in logs if log['level'] == 'info'),
        'resolved': 0,  # This would need to be tracked separately
        'log_entries': logs,
        'last_updated': datetime.now().strftime('%H:%M:%S')
    })

def show_settings():
    """Display and manage Loki configuration settings."""
    st.title("Settings")
    
    with st.form("loki_settings"):
        st.subheader("Loki Configuration")
        loki_url = st.text_input("Loki URL", value=st.session_state.loki_config.get('url', ''))
        loki_username = st.text_input("Username (optional)", value=st.session_state.loki_config.get('username', ''))
        loki_password = st.text_input("Password (optional)", type="password", value=st.session_state.loki_config.get('password', ''))
        verify_ssl = st.checkbox("Verify SSL", value=st.session_state.loki_config.get('verify_ssl', True))
        
        if st.form_submit_button("Save Configuration"):
            st.session_state.loki_config.update({
                'url': loki_url,
                'username': loki_username,
                'password': loki_password,
                'verify_ssl': verify_ssl
            })
            
            # Test connection
            client = LokiClient()
            if client.test_connection():
                st.session_state.loki_config['is_configured'] = True
                st.success("Successfully connected to Loki!")
            else:
                st.error("Failed to connect to Loki. Please check your configuration.")

def show_dashboard():
    """Display the main dashboard."""
    st.title("LogAnalytics")
    
    # Top bar with search and time range
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_query = st.text_input("Search logs...", key="search_input", placeholder="Search logs...")
    with col2:
        st.selectbox(
            "Time Range",
            ["Last 24 hours", "Last 7 days", "Last 30 days", "Custom"],
            key="time_range",
            on_change=update_dashboard
        )
    with col3:
        if st.button("Refresh"):
            update_dashboard()
            st.rerun()
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Errors</div>
            <div class="metric-value error-value">{}</div>
            <div class="last-updated">Last updated: {}</div>
        </div>
        """.format(st.session_state.log_data['errors'], st.session_state.log_data['last_updated']), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Warnings</div>
            <div class="metric-value warning-value">{}</div>
            <div class="last-updated">Last updated: {}</div>
        </div>
        """.format(st.session_state.log_data['warnings'], st.session_state.log_data['last_updated']), unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Info</div>
            <div class="metric-value info-value">{}</div>
            <div class="last-updated">Last updated: {}</div>
        </div>
        """.format(st.session_state.log_data['info'], st.session_state.log_data['last_updated']), unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Resolved</div>
            <div class="metric-value resolved-value">{}</div>
            <div class="last-updated">Last updated: {}</div>
        </div>
        """.format(st.session_state.log_data['resolved'], st.session_state.log_data['last_updated']), unsafe_allow_html=True)
    
    # Log Viewer
    st.subheader("Recent Logs")
    if st.session_state.log_data['log_entries']:
        # Convert logs to DataFrame for better display
        df = pd.DataFrame(st.session_state.log_data['log_entries'])
        
        # Apply search filter if provided
        if search_query:
            df = df[df['message'].str.contains(search_query, case=False, na=False)]
        
        # Style the DataFrame
        def color_level(val):
            colors = {
                'error': 'color: #dc3545',
                'warning': 'color: #ffc107',
                'info': 'color: #0d6efd'
            }
            return colors.get(val, '')
        
        styled_df = df.style.applymap(color_level, subset=['level'])
        
        # Display logs with custom styling
        st.dataframe(
            styled_df,
            column_config={
                "timestamp": "Time",
                "level": "Level",
                "message": "Message",
                "service": "Service"
            },
            hide_index=True
        )
    else:
        if not st.session_state.loki_config.get('is_configured'):
            st.warning("Please configure Loki connection in Settings to view logs.")
        else:
            st.info("No logs found for the selected time range.")
    
    # Analysis sections
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Recent Error Analysis")
        if not st.session_state.log_data['log_entries']:
            st.info("No recent errors to analyze")
    
    with col2:
        st.subheader("Recommended Resolutions")
        if not st.session_state.log_data['log_entries']:
            st.info("No recommendations available")

def main():
    # Sidebar navigation
    with st.sidebar:
        st.title("LogAnalytics")
        selected = st.radio(
            "Navigation",
            ["Dashboard", "Log Explorer", "Error Analysis", "Sources", "Settings"],
            index=0,
            key="nav"
        )
    
    # Main content
    if selected == "Dashboard":
        show_dashboard()
    elif selected == "Log Explorer":
        show_log_explorer(st.session_state.log_data['log_entries'])
    elif selected == "Error Analysis":
        if st.session_state.log_data['selected_error']:
            show_error_resolution(
                st.session_state.log_data['selected_error'],
                st.session_state.log_data['error_analysis'],
                {}
            )
    elif selected == "Sources":
        show_sources()
    elif selected == "Settings":
        show_settings()

if __name__ == "__main__":
    main() 