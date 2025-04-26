import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import requests
import os
from log_analyser import LogAnalyzer
from typing import List, Dict, Optional
import re
from collections import defaultdict
import random

# Initialize session state
if 'log_data' not in st.session_state:
    st.session_state.log_data = {
        'errors': 0,
        'warnings': 0,
        'info': 0,
        'resolved': 0,
        'error_analysis': [],
        'log_entries': [],
        'log_volume_data': [],
        'error_details': {},
        'selected_error': None,  # Store selected error for detailed view
        'selected_resolution': None,  # Store selected resolution for detailed view
        'current_view': 'dashboard'  # Track current view: 'dashboard', 'analysis', 'resolution'
    }

if 'selected_time_range' not in st.session_state:
    st.session_state.selected_time_range = 'Last 24 hours'

# Initialize LogAnalyzer
log_analyzer = LogAnalyzer()

# Configure page
st.set_page_config(
    page_title="LogAnalytics Dashboard",
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
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .error-card {
        background-color: #fff1f0;
        border: 1px solid #ffccc7;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 15px;
    }
    .resolution-card {
        background-color: white;
        border: 1px solid #e8e8e8;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 15px;
    }
    .confidence-tag {
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        float: right;
    }
    .high-confidence {
        background-color: #e6f7ff;
        color: #0050b3;
    }
    .medium-confidence {
        background-color: #e6f4ff;
        color: #1890ff;
    }
    .low-confidence {
        background-color: #fff7e6;
        color: #fa8c16;
    }
    .occurrence-tag {
        background-color: #f5f5f5;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        color: #595959;
    }
    .service-tag {
        background-color: #f5f5f5;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        margin-right: 8px;
    }
    .timestamp {
        color: #8c8c8c;
        font-size: 12px;
    }
    .view-link {
        color: #1890ff;
        text-decoration: none;
        font-size: 14px;
    }
    .code-block {
        background-color: #2d2d2d;
        color: #fff;
        padding: 15px;
        border-radius: 5px;
        font-family: monospace;
        margin: 10px 0;
    }
    .button-row {
        display: flex;
        gap: 10px;
        margin-top: 15px;
    }
    .apply-button {
        background-color: #1890ff;
        color: white;
        border: none;
        padding: 5px 15px;
        border-radius: 5px;
        cursor: pointer;
    }
    .dismiss-button {
        background-color: transparent;
        color: #595959;
        border: none;
        padding: 5px 15px;
        cursor: pointer;
    }
    .analysis-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 15px;
        border-left: 4px solid #0d6efd;
    }
    .service-tag {
        background-color: #e9ecef;
        padding: 5px 10px;
        border-radius: 15px;
        margin-right: 10px;
        display: inline-block;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

def fetch_loki_logs(query: str, time_range: str) -> List[Dict]:
    """Fetch logs from Loki."""
    LOKI_URL = os.getenv('LOKI_URL', 'http://localhost:3100')
    url = f"{LOKI_URL}/loki/api/v1/query_range"
    
    # Calculate time range
    end_time = datetime.utcnow()
    if time_range == 'Last 24 hours':
        start_time = end_time - timedelta(hours=24)
    elif time_range == 'Last 7 days':
        start_time = end_time - timedelta(days=7)
    elif time_range == 'Last 30 days':
        start_time = end_time - timedelta(days=30)
    else:
        start_time = end_time - timedelta(hours=1)
    
    params = {
        'query': query,
        'start': start_time.isoformat() + 'Z',
        'end': end_time.isoformat() + 'Z',
        'limit': 1000
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        logs = []
        for stream in data.get('data', {}).get('result', []):
            for value in stream.get('values', []):
                timestamp = datetime.fromtimestamp(float(value[0])/1e9)
                message = value[1]
                
                # Extract log level and service from message
                level_match = re.search(r'(ERROR|WARNING|INFO|DEBUG|CRITICAL)', message)
                service_match = re.search(r'services\.(\w+)', message)
                
                log_entry = {
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'message': message,
                    'level': level_match.group(1).lower() if level_match else 'info',
                    'service': service_match.group(1) if service_match else 'unknown'
                }
                
                # Extract error details if it's an error
                if log_entry['level'] in ['error', 'critical']:
                    error_details = extract_error_details(message)
                    log_entry.update(error_details)
                
                logs.append(log_entry)
        
        return logs
    except Exception as e:
        st.error(f"Error fetching logs: {str(e)}")
        return []

def extract_error_details(message: str) -> Dict:
    """Extract detailed information from error messages."""
    details = {
        'error_type': 'Unknown Error',
        'error_message': message,
        'process_id': None,
        'confidence': 'LOW'
    }
    
    # Extract process ID
    process_match = re.search(r'process (\d+)', message)
    if process_match:
        details['process_id'] = process_match.group(1)
    
    # Extract error type
    if 'TimeoutError' in message:
        details['error_type'] = 'Connection Timeout'
        details['confidence'] = 'HIGH'
    elif 'TypeError' in message:
        details['error_type'] = 'Type Error'
        details['confidence'] = 'MEDIUM'
    elif 'AttributeError' in message:
        details['error_type'] = 'Attribute Error'
        details['confidence'] = 'MEDIUM'
    
    # Extract specific error message
    error_msg_match = re.search(r'Error: (.+?)(?:\n|$)', message)
    if error_msg_match:
        details['error_message'] = error_msg_match.group(1)
    
    return details

def analyze_errors(logs: List[Dict]) -> Dict:
    """Analyze errors and generate insights."""
    error_analysis = defaultdict(lambda: {
        'count': 0,
        'services': set(),
        'last_seen': None,
        'error_messages': set(),
        'confidence': 'LOW'
    })
    
    for log in logs:
        if log['level'] in ['error', 'critical']:
            error_type = log.get('error_type', 'Unknown Error')
            error_analysis[error_type]['count'] += 1
            error_analysis[error_type]['services'].add(log.get('service', 'unknown'))
            error_analysis[error_type]['error_messages'].add(log.get('error_message', ''))
            
            timestamp = datetime.strptime(log['timestamp'], '%Y-%m-%d %H:%M:%S')
            if not error_analysis[error_type]['last_seen'] or timestamp > error_analysis[error_type]['last_seen']:
                error_analysis[error_type]['last_seen'] = timestamp
    
    return dict(error_analysis)

def get_resolution_suggestions(error_type: str, error_details: Dict) -> List[Dict]:
    """Get resolution suggestions for specific error types."""
    suggestions = []
    
    if 'TimeoutError' in error_type:
        suggestions.append({
            'message': 'Review network connectivity and endpoint configuration',
            'code_change': '// Implement retry mechanism with exponential backoff\nretry_count = 3\nwhile retry_count > 0:\n    try:\n        response = make_request()\n        break\n    except TimeoutError:\n        retry_count -= 1\n        time.sleep(2 ** (3 - retry_count))',
            'confidence': 'HIGH'
        })
    elif 'TypeError' in error_type:
        suggestions.append({
            'message': 'Check type compatibility and null checks',
            'code_change': '// Add type checking and null guards\nif value is not None and isinstance(value, expected_type):\n    process_value(value)\nelse:\n    handle_invalid_value()',
            'confidence': 'MEDIUM'
        })
    elif 'process' in error_type.lower():
        suggestions.append({
            'message': 'Review the error logs and code to identify the specific cause.',
            'code_change': '// Code change requires more investigation',
            'confidence': 'MEDIUM'
        })
    
    return suggestions

def update_dashboard():
    """Update dashboard with latest data."""
    query = '{job="simulated_system"}'
    logs = fetch_loki_logs(query, st.session_state.selected_time_range)
    
    if logs:
        # Basic metrics
        error_count = sum(1 for log in logs if log['level'] in ['error', 'critical'])
        warning_count = sum(1 for log in logs if log['level'] == 'warning')
        info_count = sum(1 for log in logs if log['level'] == 'info')
        
        # Analyze errors
        error_analysis = analyze_errors(logs)
        
        # Update session state
        st.session_state.log_data.update({
            'errors': error_count,
            'warnings': warning_count,
            'info': info_count,
            'error_analysis': error_analysis,
            'log_entries': logs,
            'log_volume_data': get_log_volume_data(logs)
        })

def get_log_volume_data(logs: List[Dict]) -> List[Dict]:
    """Calculate log volume trends."""
    volume_data = []
    time_groups = defaultdict(lambda: {'error': 0, 'warning': 0, 'info': 0})
    
    for log in logs:
        hour_key = log['timestamp'][:13]  # Group by hour
        level = log['level']
        if level in ['error', 'critical']:
            time_groups[hour_key]['error'] += 1
        elif level == 'warning':
            time_groups[hour_key]['warning'] += 1
        else:
            time_groups[hour_key]['info'] += 1
    
    for timestamp, counts in sorted(time_groups.items()):
        volume_data.append({
            'timestamp': timestamp,
            'error_count': counts['error'],
            'warning_count': counts['warning'],
            'info_count': counts['info']
        })
    
    return volume_data

def show_error_analysis_page(error_type: str, details: Dict):
    """Show detailed error analysis page."""
    st.title(f"Error Analysis: {error_type}")
    st.markdown(f"<span class='occurrence-tag' style='font-size: 16px;'>{details['count']} occurrences</span>", unsafe_allow_html=True)
    
    # Get comprehensive analysis from LogAnalyzer
    error_logs = [log for log in st.session_state.log_data['log_entries'] 
                 if log.get('error_type') == error_type]
    
    analysis_context = {
        'total_errors': len(error_logs),
        'error_by_type': {error_type: error_logs},
        'error_by_file': defaultdict(list),
        'file_contents': {},
        'full_log': '\n'.join(log['message'] for log in error_logs)
    }
    
    ai_analysis = log_analyzer.get_comprehensive_fix(error_logs, analysis_context)
    
    # Display Analysis Sections in two columns
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Error Pattern Analysis")
        
        # Error Type
        st.subheader("Error Type")
        st.write(error_type)
        
        # Services Affected
        st.subheader("Services Affected")
        for service in details['services']:
            st.markdown(f"<span class='service-tag'>{service}</span>", unsafe_allow_html=True)
        
        # Error Messages
        st.subheader("Error Messages")
        for msg in details['error_messages']:
            st.markdown(f"""
            <div style='background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 10px;'>
                {msg}
            </div>
            """, unsafe_allow_html=True)
        
        # Timeline
        st.subheader("Timeline")
        st.write(f"First seen: {details['last_seen'].strftime('%Y-%m-%d %H:%M:%S')}")
        st.write(f"Frequency: {details['count']} occurrences")
        
        # AI Analysis
        st.header("AI Analysis")
        if ai_analysis:
            # Root Cause Analysis
            st.subheader("Root Cause Analysis")
            st.markdown(f"""
            <div class='analysis-card'>
                {ai_analysis.get('root_cause', 'Analysis not available')}
            </div>
            """, unsafe_allow_html=True)
            
            # Impact Assessment
            st.subheader("Impact Assessment")
            st.markdown(f"""
            <div class='analysis-card'>
                {ai_analysis.get('impact', 'Analysis not available')}
            </div>
            """, unsafe_allow_html=True)
            
            # Prevention Strategies
            st.subheader("Prevention Strategies")
            st.markdown(f"""
            <div class='analysis-card'>
                {ai_analysis.get('prevention', 'Analysis not available')}
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.header("Impact Analysis")
        
        # Severity
        st.subheader("Severity")
        severity = 'High' if details['count'] > 10 else 'Medium' if details['count'] > 5 else 'Low'
        severity_color = '#dc3545' if severity == 'High' else '#ffc107' if severity == 'Medium' else '#0dcaf0'
        st.markdown(f"""
        <div style='background-color: {severity_color}20; color: {severity_color}; 
                    padding: 10px; border-radius: 5px; display: inline-block;'>
            {severity}
        </div>
        """, unsafe_allow_html=True)
        
        # Affected Components
        st.subheader("Affected Components")
        for component in details['services']:
            st.markdown(f"""
            <div style='background-color: #f8f9fa; padding: 10px; 
                      border-radius: 5px; margin-bottom: 5px;'>
                {component}
            </div>
            """, unsafe_allow_html=True)
        
        # Error Trend
        st.subheader("Error Trend")
        error_trend = pd.DataFrame({
            'timestamp': [details['last_seen'] - timedelta(hours=i) for i in range(24)],
            'count': [random.randint(0, 3) for _ in range(24)]  # Simulated data
        })
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=error_trend['timestamp'],
            y=error_trend['count'],
            mode='lines',
            name='Error Count',
            line=dict(color='#dc3545')
        ))
        fig.update_layout(
            height=200,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor='#eee')
        )
        st.plotly_chart(fig, use_container_width=True)

    # Show error occurrences in a table
    st.header("Error Occurrences")
    if error_logs:
        df = pd.DataFrame(error_logs)
        df = df[['timestamp', 'service', 'message']]  # Select relevant columns
        st.dataframe(df, use_container_width=True)
    
    # Show resolution suggestions
    st.header("Recommended Resolutions")
    suggestions = get_resolution_suggestions(error_type, details)
    for suggestion in suggestions:
        st.markdown(f"""
        <div class="resolution-card">
            <div style="margin-bottom: 10px;">
                <span style="font-weight: 500;">Suggested Fix</span>
                <span class="confidence-tag {suggestion['confidence'].lower()}-confidence">
                    {suggestion['confidence']} Confidence
                </span>
            </div>
            <div style="color: #595959; margin-bottom: 10px;">
                {suggestion['message']}
            </div>
            <div class="code-block">
                {suggestion['code_change']}
            </div>
            <div class="button-row">
                <button class="apply-button">Apply Fix</button>
                <button class="dismiss-button">Dismiss</button>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Back button
    if st.button("← Back to Dashboard"):
        st.session_state.log_data['current_view'] = 'dashboard'
        st.session_state.log_data['selected_error'] = None
        st.rerun()

def show_resolution_page(error_type: str, resolution: Dict):
    """Show detailed resolution page."""
    st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 20px;">
            <h2 style="margin: 0;">Resolution: {error_type}</h2>
            <span class="confidence-tag {resolution['confidence'].lower()}-confidence" style="margin-left: 15px;">
                {resolution['confidence']} Confidence
            </span>
        </div>
    """, unsafe_allow_html=True)

    # Resolution Details
    st.subheader("Problem Description")
    st.markdown(resolution['message'])

    # Code Changes
    st.subheader("Suggested Code Changes")
    st.code(resolution['code_change'], language='python')

    # Implementation Steps
    st.subheader("Implementation Steps")
    st.markdown("""
    1. Review the suggested code changes
    2. Test the changes in a development environment
    3. Monitor for any side effects
    4. Deploy to production if tests pass
    """)

    # Additional Context
    st.subheader("Additional Context")
    st.markdown("""
    - This fix addresses the root cause of the error
    - Implementation time: 30-60 minutes
    - Risk level: Medium
    """)

    # Action Buttons
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("Apply Fix"):
            # Here you would implement the actual fix application
            st.success("Fix applied successfully!")
    with col2:
        if st.button("Dismiss"):
            st.session_state.log_data['current_view'] = 'dashboard'
            st.session_state.log_data['selected_resolution'] = None
            st.rerun()
    
    # Back button
    if st.button("← Back to Dashboard"):
        st.session_state.log_data['current_view'] = 'dashboard'
        st.session_state.log_data['selected_resolution'] = None
        st.rerun()

# Sidebar
with st.sidebar:
    st.title("LogAnalytics")
    
    # Navigation
    selected = st.radio(
        "Navigation",
        ["Dashboard", "Log Explorer", "Error Analysis", "Resolutions", "Sources", "Settings"],
        index=0
    )
    
    # Configuration section in sidebar
    if selected in ["Sources", "Settings"]:
        st.header("CONFIGURATION")
        
        # Loki Configuration
        if selected == "Sources":
            with st.form("loki_config"):
                st.subheader("Loki Configuration")
                loki_url = st.text_input("Loki URL", value=os.getenv('LOKI_URL', 'http://localhost:3100'))
                username = st.text_input("Username (optional)")
                password = st.text_input("Password (optional)", type="password")
                
                if st.form_submit_button("Save Configuration"):
                    os.environ['LOKI_URL'] = loki_url
                    if username:
                        os.environ['LOKI_USERNAME'] = username
                    if password:
                        os.environ['LOKI_PASSWORD'] = password
                    st.success("Configuration saved!")

# Main content
if selected == "Dashboard":
    if st.session_state.log_data['current_view'] == 'analysis' and st.session_state.log_data['selected_error']:
        # Show detailed analysis page
        error_type = st.session_state.log_data['selected_error']
        details = st.session_state.log_data['error_analysis'][error_type]
        show_error_analysis_page(error_type, details)
    
    elif st.session_state.log_data['current_view'] == 'resolution' and st.session_state.log_data['selected_resolution']:
        # Show resolution page
        error_type = st.session_state.log_data['selected_resolution']['error_type']
        resolution = st.session_state.log_data['selected_resolution']['resolution']
        show_resolution_page(error_type, resolution)
    
    else:
        # Regular dashboard view
        # Header with search and time range
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.text_input("Search", placeholder="Search logs...")
        with col2:
            time_range = st.selectbox(
                "Time Range",
                ["Last 24 hours", "Last 7 days", "Last 30 days", "Custom"],
                key="time_range"
            )
        with col3:
            col3_1, col3_2 = st.columns(2)
            with col3_1:
                if st.button("Refresh", key="refresh_button"):
                    update_dashboard()
            with col3_2:
                st.button("Filter", key="filter_button")

        # Update dashboard data
        update_dashboard()

        # Metrics
        metrics_cols = st.columns(4)
        with metrics_cols[0]:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Errors</h3>
                <h2 style="color: #dc3545;">{st.session_state.log_data['errors']}</h2>
                <p>Last updated: {datetime.now().strftime('%H:%M:%S')}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with metrics_cols[1]:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Warnings</h3>
                <h2 style="color: #ffc107;">{st.session_state.log_data['warnings']}</h2>
                <p>Last updated: {datetime.now().strftime('%H:%M:%S')}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with metrics_cols[2]:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Info</h3>
                <h2 style="color: #0d6efd;">{st.session_state.log_data['info']}</h2>
                <p>Last updated: {datetime.now().strftime('%H:%M:%S')}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with metrics_cols[3]:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Resolved</h3>
                <h2 style="color: #198754;">{st.session_state.log_data['resolved']}</h2>
                <p>Last updated: {datetime.now().strftime('%H:%M:%S')}</p>
            </div>
            """, unsafe_allow_html=True)

        # Log Volume Trends
        st.subheader("Log Volume Trends")
        
        if st.session_state.log_data['log_volume_data']:
            df = pd.DataFrame(st.session_state.log_data['log_volume_data'])
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['error_count'],
                name='Errors',
                line=dict(color='#dc3545'),
                fill='tonexty'
            ))
            
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['warning_count'],
                name='Warnings',
                line=dict(color='#ffc107'),
                fill='tonexty'
            ))
            
            fig.update_layout(
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                margin=dict(l=0, r=0, t=30, b=0),
                yaxis_title=None,
                xaxis_title=None,
                height=300,
                plot_bgcolor='white'
            )
            
            st.plotly_chart(fig, use_container_width=True)

        # Error Analysis and Resolutions
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="margin: 0;">Recent Error Analysis</h3>
                <a href="#" class="view-link">View All</a>
            </div>
            """, unsafe_allow_html=True)
            
            if st.session_state.log_data['error_analysis']:
                for error_type, details in st.session_state.log_data['error_analysis'].items():
                    st.markdown(f"""
                    <div class="error-card">
                        <div style="margin-bottom: 10px;">
                            <span style="font-weight: 500;">{error_type}</span>
                            <span class="occurrence-tag">{details['count']} occurrences</span>
                        </div>
                        <div style="color: #595959; margin-bottom: 10px;">
                            {next(iter(details['error_messages']))}
                        </div>
                        <div>
                            <span class="service-tag">{next(iter(details['services']))}</span>
                            <span class="timestamp">about {(datetime.now() - details['last_seen']).seconds // 3600} hours ago</span>
                        </div>
                        <div style="margin-top: 10px;">
                            <a href="#" onclick="handle_view_analysis('{error_type}')" class="view-link">View Analysis</a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Handle View Analysis click
                    if st.button(f"View Analysis: {error_type}", key=f"view_analysis_{error_type}"):
                        st.session_state.log_data['current_view'] = 'analysis'
                        st.session_state.log_data['selected_error'] = error_type
                        st.rerun()
        
        with col2:
            st.markdown("""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="margin: 0;">Recommended Resolutions</h3>
                <a href="#" class="view-link">View All</a>
            </div>
            """, unsafe_allow_html=True)
            
            if st.session_state.log_data['error_analysis']:
                for error_type, details in st.session_state.log_data['error_analysis'].items():
                    suggestions = get_resolution_suggestions(error_type, details)
                    for suggestion in suggestions:
                        st.markdown(f"""
                        <div class="resolution-card">
                            <div style="margin-bottom: 10px;">
                                <span style="font-weight: 500;">{error_type}</span>
                                <span class="confidence-tag {suggestion['confidence'].lower()}-confidence">
                                    {suggestion['confidence']} Confidence
                                </span>
                            </div>
                            <div style="color: #595959; margin-bottom: 10px;">
                                {suggestion['message']}
                            </div>
                            <div class="code-block">
                                {suggestion['code_change']}
                            </div>
                            <div class="button-row">
                                <button class="apply-button" onclick="handle_view_resolution('{error_type}')">Apply Fix</button>
                                <button class="dismiss-button">Dismiss</button>
                                <span style="margin-left: auto; color: #8c8c8c;">
                                    Based on {details['count']} error occurrences
                                </span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Handle View Resolution click
                        if st.button(f"View Resolution: {error_type}", key=f"view_resolution_{error_type}"):
                            st.session_state.log_data['current_view'] = 'resolution'
                            st.session_state.log_data['selected_resolution'] = {
                                'error_type': error_type,
                                'resolution': suggestion
                            }
                            st.rerun()

elif selected == "Log Explorer":
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
                update_dashboard()
        with col4_2:
            st.download_button(
                "Export",
                data=json.dumps(st.session_state.log_data['log_entries'], indent=2),
                file_name="logs.json",
                mime="application/json"
            )

    # Log entries table
    if st.session_state.log_data['log_entries']:
        df = pd.DataFrame(st.session_state.log_data['log_entries'])
        
        # Apply filters
        if search_query:
            df = df[df['message'].str.contains(search_query, case=False)]
        if log_level != "All Levels":
            df = df[df['level'] == log_level.lower()]
        if source != "All Sources":
            df = df[df['service'] == source.lower()]
        
        st.dataframe(df)

elif selected == "Error Analysis":
    st.title("Error Analysis")
    
    if st.session_state.log_data['error_analysis']:
        for error_type, details in st.session_state.log_data['error_analysis'].items():
            st.markdown(f"""
            <div class="error-card">
                <div style="margin-bottom: 10px;">
                    <span style="font-weight: 500;">{error_type}</span>
                    <span class="occurrence-tag">{details['count']} occurrences</span>
                </div>
                <div style="color: #595959; margin-bottom: 10px;">
                    {next(iter(details['error_messages']))}
                </div>
                <div>
                    <span class="service-tag">{', '.join(details['services'])}</span>
                    <span class="timestamp">Last seen: {details['last_seen'].strftime('%Y-%m-%d %H:%M')}</span>
                </div>
                <div style="margin-top: 10px;">
                    <a href="#" class="view-link">View Details</a>
                </div>
            </div>
            """, unsafe_allow_html=True)

def main():
    pass

if __name__ == "__main__":
    main() 