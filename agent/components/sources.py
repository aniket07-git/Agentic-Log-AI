import streamlit as st
import os
from typing import List, Dict
from .loki_client import LokiClient
import json
from datetime import datetime
import re
import pandas as pd

def save_loki_config(url: str, username: str = None, password: str = None, verify_ssl: bool = True):
    """Save Loki configuration to environment variables and session state."""
    # Save to environment variables
    os.environ['LOKI_URL'] = url
    if username:
        os.environ['LOKI_USERNAME'] = username
    if password:
        os.environ['LOKI_PASSWORD'] = password
    os.environ['LOKI_VERIFY_SSL'] = str(verify_ssl).lower()
    
    # Save to session state
    if 'loki_config' not in st.session_state:
        st.session_state.loki_config = {}
    st.session_state.loki_config.update({
        'url': url,
        'username': username,
        'verify_ssl': verify_ssl,
        'is_configured': True
    })

def test_loki_connection() -> bool:
    """Test connection to Loki server."""
    client = LokiClient()
    return client.test_connection()

def process_uploaded_logs(uploaded_file) -> List[Dict]:
    """Process uploaded log file."""
    try:
        content = uploaded_file.read()
        if uploaded_file.type == "application/json":
            logs = json.loads(content)
        else:  # Assume text file with one log per line
            logs = []
            for line in content.decode().split('\n'):
                if line.strip():
                    # Extract timestamp, level, and message using regex
                    timestamp_match = re.search(r'\[(.*?)\]', line)
                    level_match = re.search(r'(ERROR|WARNING|INFO|DEBUG|CRITICAL)', line)
                    service_match = re.search(r'services\.(\w+)', line)
                    
                    log_entry = {
                        'timestamp': timestamp_match.group(1) if timestamp_match else datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'message': line.strip(),
                        'level': level_match.group(1).lower() if level_match else 'info',
                        'service': service_match.group(1) if service_match else 'unknown'
                    }
                    logs.append(log_entry)
        return logs
    except Exception as e:
        st.error(f"Error processing log file: {str(e)}")
        return []

def show_sources():
    """Display the sources configuration page."""
    st.title("Log Sources")
    
    # Loki Configuration
    st.header("Loki Configuration")
    
    # Connection status indicator
    if 'loki_config' in st.session_state and st.session_state.loki_config.get('is_configured'):
        if test_loki_connection():
            st.success("✅ Connected to Loki")
        else:
            st.error("❌ Failed to connect to Loki")
    
    with st.form("loki_config"):
        col1, col2 = st.columns([3, 1])
        with col1:
            loki_url = st.text_input(
                "Loki URL",
                value=os.getenv('LOKI_URL', 'http://localhost:3100'),
                help="The URL of your Loki server (e.g., http://localhost:3100)"
            )
        with col2:
            verify_ssl = st.checkbox(
                "Verify SSL",
                value=os.getenv('LOKI_VERIFY_SSL', 'true').lower() == 'true',
                help="Enable SSL certificate verification"
            )
        
        # Authentication
        st.subheader("Authentication (Optional)")
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input(
                "Username",
                value=os.getenv('LOKI_USERNAME', ''),
                help="Basic auth username (optional)"
            )
        with col2:
            password = st.text_input(
                "Password",
                type="password",
                help="Basic auth password (optional)"
            )
        
        # Query settings
        st.subheader("Query Settings")
        default_query = st.text_input(
            "Default Query",
            value='{job="application"}',
            help="Default Loki query to fetch logs"
        )
        
        if st.form_submit_button("Save & Test Connection"):
            save_loki_config(loki_url, username, password, verify_ssl)
            
            if test_loki_connection():
                st.success("Successfully connected to Loki!")
                
                # Test query
                try:
                    client = LokiClient()
                    logs = client.fetch_logs("Last 24 hours", default_query)
                    if logs:
                        st.success(f"Successfully fetched {len(logs)} logs")
                        # Update the dashboard state with the fetched logs
                        st.session_state.log_data['log_entries'] = logs
                        # Update metrics
                        error_count = sum(1 for log in logs if log['level'] in ['error', 'critical'])
                        warning_count = sum(1 for log in logs if log['level'] == 'warning')
                        info_count = sum(1 for log in logs if log['level'] == 'info')
                        st.session_state.log_data.update({
                            'errors': error_count,
                            'warnings': warning_count,
                            'info': info_count
                        })
                    else:
                        st.warning("No logs found with the default query")
                except Exception as e:
                    st.error(f"Error fetching logs: {str(e)}")
            else:
                st.error("Failed to connect to Loki. Please check your configuration.")
    
    # Manual Log Upload
    st.header("Manual Log Upload")
    
    # File upload instructions
    st.markdown("""
    Upload your log files in one of the following formats:
    1. JSON format:
    ```json
    [
        {
            "timestamp": "2024-02-20 10:30:00",
            "level": "ERROR",
            "message": "Error message here",
            "service": "auth-service"
        }
    ]
    ```
    2. Text format (one log per line):
    ```
    [2024-02-20 10:30:00] ERROR services.auth-service: Error message here
    ```
    """)
    
    uploaded_file = st.file_uploader(
        "Upload log file",
        type=['txt', 'json', 'log'],
        help="Upload a log file in JSON or text format"
    )
    
    if uploaded_file:
        logs = process_uploaded_logs(uploaded_file)
        if logs:
            st.session_state.log_data['log_entries'] = logs
            st.success(f"Successfully processed {len(logs)} log entries")
            
            # Show preview
            st.subheader("Log Preview")
            preview_df = pd.DataFrame(logs[:5])
            st.dataframe(preview_df, use_container_width=True) 