import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Counter
import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO
import sys
import time
from collections import defaultdict
import hashlib
import requests
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Initialize session state for Loki configuration
if 'loki_config' not in st.session_state:
    st.session_state.loki_config = {
        'is_configured': False,
        'url': 'http://localhost:3100',
        'username': '',
        'password': '',
        'verify_ssl': True
    }

console = Console()

class EnhancedLogAnalyzer:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.console = Console()

    def extract_errors(self, log_content: str) -> List[Dict]:
        """Extract all errors from log content string."""
        # Split log content into individual error blocks
        error_blocks = re.split(r'(?=Traceback \(most recent call last\):)', log_content)
        error_blocks = [block.strip() for block in error_blocks if block.strip()]
        
        errors = []
        for block in error_blocks:
            # Extract error context for each block
            error_patterns = {
                'file_path': r'File "([^"]+)"',
                'line_number': r'line (\d+)',
                'error_type': r'([A-Za-z]+Error|Exception):',
                'error_message': r'([A-Za-z]+Error|Exception):\s*(.*)',
                'full_traceback': block
            }
            
            context = {}
            for key, pattern in error_patterns.items():
                if key == 'full_traceback':
                    context[key] = block
                else:
                    match = re.search(pattern, block)
                    if match:
                        # For error_message, we need to get both groups
                        if key == 'error_message' and match.group(2):
                            context[key] = f"{match.group(1)}: {match.group(2).strip()}"
                        else:
                            context[key] = match.group(1)
            
            if context.get('file_path') and context.get('line_number'):
                errors.append(context)
        
        return errors

    def group_similar_errors(self, errors: List[Dict]) -> Dict[str, List[Dict]]:
        """Group similar errors together based on error type and message pattern."""
        if not errors:
            return {}
            
        error_groups = defaultdict(list)
        
        for error in errors:
            # Create a signature for the error based on type and message pattern
            error_type = error.get('error_type', 'Unknown')
            error_message = error.get('error_message', '')
            
            # Extract the core part of the message without specific variables
            # This helps group similar errors with different variable values
            core_message = re.sub(r"'[^']*'", "'VARIABLE'", error_message)
            core_message = re.sub(r'"[^"]*"', '"VARIABLE"', core_message)
            core_message = re.sub(r'\b\d+\b', 'NUMBER', core_message)
            
            # Create a unique signature that represents this error pattern
            signature = f"{error_type}:{core_message}"
            signature_hash = hashlib.md5(signature.encode()).hexdigest()
            
            error_groups[signature_hash].append(error)
        
        return error_groups

    def analyze_error_patterns(self, error_groups: Dict[str, List[Dict]]) -> List[Dict]:
        """Analyze patterns in error groups to provide comprehensive insights."""
        pattern_insights = []
        
        for group_id, errors in error_groups.items():
            # Get a representative error for this group
            representative = errors[0]
            error_type = representative.get('error_type', 'Unknown')
            
            # Collect file paths and line numbers for this error type
            file_paths = [e.get('file_path', 'Unknown') for e in errors]
            line_numbers = [e.get('line_number', '0') for e in errors]
            
            # Get the most common files affected
            common_files = pd.Series(file_paths).value_counts().head(3).to_dict()
            
            # Create insight for this error group
            insight = {
                'group_id': group_id,
                'error_type': error_type,
                'count': len(errors),
                'representative_error': representative,
                'common_files': common_files,
                'errors': errors
            }
            
            pattern_insights.append(insight)
        
        # Sort insights by error count (most frequent first)
        pattern_insights.sort(key=lambda x: x['count'], reverse=True)
        
        return pattern_insights

    def get_comprehensive_analysis(self, error_patterns: List[Dict]) -> str:
        """Get comprehensive analysis of all error patterns."""
        if not error_patterns:
            return "No errors found to analyze."
            
        # Create a summary of all error patterns for the LLM to analyze
        error_summary = []
        for i, pattern in enumerate(error_patterns, 1):
            error_summary.append(f"Pattern {i}:")
            error_summary.append(f"- Error Type: {pattern['error_type']}")
            error_summary.append(f"- Occurrence Count: {pattern['count']}")
            error_summary.append(f"- Common Files Affected: {', '.join(list(pattern['common_files'].keys())[:3])}")
            error_summary.append(f"- Representative Error Message: {pattern['representative_error'].get('error_message', 'No message')}")
            error_summary.append(f"- Representative Traceback: {pattern['representative_error'].get('full_traceback', '')[:500]}...")
            error_summary.append("")
        
        error_summary_text = "\n".join(error_summary)
        
        analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert software error analyst skilled at identifying patterns across multiple errors.
            Analyze the following error patterns found in a log file and provide a comprehensive summary:
            
            1. Identify the root causes of each error pattern
            2. Explain potential connections between different error patterns
            3. Identify which errors are likely causing other errors (cascading failures)
            4. Prioritize which errors should be fixed first and why
            5. Provide a high-level plan for resolving all identified issues
            
            Be concise but thorough in your analysis. Focus on systemic issues rather than individual error instances."""),
            ("user", """
            Here are the error patterns identified in the log file:
            
            {error_summary}
            
            Please provide a comprehensive analysis of these error patterns:
            """)
        ])

        analysis_chain = (
            {"error_summary": lambda x: error_summary_text}
            | analysis_prompt
            | self.llm
            | StrOutputParser()
        )

        return analysis_chain.invoke({})

    def get_unified_fix_recommendations(self, error_patterns: List[Dict]) -> str:
        """Get unified fix recommendations for all error patterns."""
        if not error_patterns:
            return "No errors found to fix."
            
        # Create a summary of top error patterns for the LLM to fix
        top_patterns = error_patterns[:3]  # Focus on the top 3 most frequent patterns
        
        error_summary = []
        for i, pattern in enumerate(top_patterns, 1):
            representative = pattern['representative_error']
            error_summary.append(f"Pattern {i} (Occurs {pattern['count']} times):")
            error_summary.append(f"- Error Type: {pattern['error_type']}")
            error_summary.append(f"- Common Files: {', '.join(list(pattern['common_files'].keys())[:3])}")
            error_summary.append(f"- Representative Error Message: {representative.get('error_message', 'No message')}")
            error_summary.append(f"- Representative Traceback: {representative.get('full_traceback', '')[:500]}...")
            error_summary.append("")
        
        error_summary_text = "\n".join(error_summary)
        
        fix_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert software engineer specializing in fixing systemic bugs.
            Provide practical fix recommendations for the following error patterns:
            
            For each error pattern:
            1. Explain the root cause
            2. Provide a specific code-level fix recommendation
            3. Suggest preventive measures to avoid similar issues in the future
            
            Focus on offering solutions that address the underlying issues rather than just the symptoms.
            Provide actual code examples where appropriate."""),
            ("user", """
            Here are the top error patterns identified in the log file:
            
            {error_summary}
            
            Please provide unified fix recommendations:
            """)
        ])

        fix_chain = (
            {"error_summary": lambda x: error_summary_text}
            | fix_prompt
            | self.llm
            | StrOutputParser()
        )

        return fix_chain.invoke({})

    def find_file(self, file_path: str) -> Optional[str]:
        """Find file in the project structure."""
        # First try the exact path
        if os.path.exists(file_path):
            return file_path
            
        # If not found, search in the project directory
        project_root = os.getcwd()
        for root, _, files in os.walk(project_root):
            for file in files:
                if file == os.path.basename(file_path):
                    return os.path.join(root, file)
        return None

    def get_relevant_code(self, file_path: str, line_number: int, context_lines: int = 5) -> Dict:
        """Get relevant code around the error line."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            start = max(0, line_number - context_lines - 1)
            end = min(len(lines), line_number + context_lines)
            
            relevant_code = ''.join(lines[start:end])
            return {
                'code': relevant_code,
                'start_line': start,
                'end_line': end,
                'full_content': ''.join(lines)
            }
        except Exception as e:
            return {'error': f"Could not read file: {str(e)}"}

# --- Page Config ---
st.set_page_config(
    page_title="Enhanced Log Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Styling ---
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stAlert {
        margin-top: 1rem;
    }
    .metric-card {
        border: 1px solid #dedede;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .metric-label {
        font-size: 14px;
        color: #666;
    }
    .last-updated {
        font-size: 12px;
        color: #999;
    }
    </style>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
if 'analyzer' not in st.session_state:
    st.session_state.analyzer = EnhancedLogAnalyzer()
if 'errors' not in st.session_state:
    st.session_state.errors = []
if 'error_patterns' not in st.session_state:
    st.session_state.error_patterns = []
if 'comprehensive_analysis' not in st.session_state:
    st.session_state.comprehensive_analysis = ""
if 'fix_recommendations' not in st.session_state:
    st.session_state.fix_recommendations = ""

# --- Sidebar ---
st.sidebar.title("📊 Enhanced LogAnalytics")
st.sidebar.markdown("---")

# File Upload Section
uploaded_file = st.sidebar.file_uploader(
    "Upload Log File",
    type=['log', 'txt'],
    help="Upload a log file for comprehensive error analysis"
)

st.sidebar.markdown("---")

# Navigation
st.sidebar.subheader("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Dashboard", "Error Patterns", "Comprehensive Analysis", "Fix Recommendations", "Settings"]
)

# --- Helper Functions ---
def process_uploaded_file():
    """Process the uploaded log file and extract/analyze errors."""
    if uploaded_file is not None:
        try:
            # Read file content
            content = uploaded_file.getvalue().decode("utf-8")
            
            with st.spinner("Analyzing log file..."):
                # Extract individual errors
                extracted_errors = st.session_state.analyzer.extract_errors(content)
                st.session_state.errors = extracted_errors
                
                # Group similar errors
                error_groups = st.session_state.analyzer.group_similar_errors(extracted_errors)
                
                # Analyze error patterns
                error_patterns = st.session_state.analyzer.analyze_error_patterns(error_groups)
                st.session_state.error_patterns = error_patterns
                
                # Get comprehensive analysis
                if error_patterns:
                    with st.spinner("Generating comprehensive analysis..."):
                        st.session_state.comprehensive_analysis = st.session_state.analyzer.get_comprehensive_analysis(error_patterns)
                    
                    with st.spinner("Generating fix recommendations..."):
                        st.session_state.fix_recommendations = st.session_state.analyzer.get_unified_fix_recommendations(error_patterns)
                
                return True
        except Exception as e:
            st.error(f"Error processing log file: {str(e)}")
            return False
    return False

def create_error_distribution_chart(error_patterns):
    """Create a bar chart showing distribution of error types."""
    if not error_patterns:
        return None
    
    # Prepare data
    error_types = [pattern['error_type'] for pattern in error_patterns]
    error_counts = [pattern['count'] for pattern in error_patterns]
    
    # Create DataFrame
    df = pd.DataFrame({
        'Error Type': error_types,
        'Count': error_counts
    })
    
    # Create bar chart with Plotly
    fig = px.bar(
        df, 
        x='Error Type', 
        y='Count',
        title='Error Type Distribution',
        color='Error Type',
        text='Count'
    )
    
    fig.update_layout(
        xaxis_title='Error Type',
        yaxis_title='Occurrence Count',
        template='plotly_white'
    )
    
    return fig

def create_error_file_heatmap(error_patterns):
    """Create a heatmap showing which files have which errors."""
    if not error_patterns:
        return None
    
    # Collect data for heatmap
    data = []
    for pattern in error_patterns:
        error_type = pattern['error_type']
        for file, count in pattern['common_files'].items():
            # Get basename of file to make chart more readable
            file_basename = os.path.basename(file)
            data.append({
                'File': file_basename,
                'Error Type': error_type,
                'Count': count
            })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # If we have data, create pivot table for heatmap
    if not df.empty:
        pivot_df = df.pivot_table(
            index='File', 
            columns='Error Type', 
            values='Count',
            fill_value=0
        )
        
        # Create heatmap
        fig = px.imshow(
            pivot_df,
            labels=dict(x="Error Type", y="File Path", color="Error Count"),
            title="Error Distribution Across Files",
            color_continuous_scale='Viridis'
        )
        
        fig.update_layout(
            xaxis_title='Error Type',
            yaxis_title='File Path',
            template='plotly_white'
        )
        
        return fig
    
    return None

def create_error_network_chart(error_patterns):
    """Create a network chart showing relationships between files and errors."""
    # This is a placeholder - in a real implementation, we'd use networkx and plotly
    # to create an actual network visualization
    
    # For now, we'll create a simple scatter plot as a placeholder
    if not error_patterns:
        return None
    
    data = []
    for pattern in error_patterns:
        error_type = pattern['error_type']
        for file, count in pattern['common_files'].items():
            file_basename = os.path.basename(file)
            data.append({
                'File': file_basename,
                'Error Type': error_type,
                'Count': count,
                'Size': np.log1p(count) * 10  # Log scale for better visualization
            })
    
    df = pd.DataFrame(data)
    
    if not df.empty:
        fig = px.scatter(
            df,
            x='File',
            y='Error Type',
            size='Size',
            color='Error Type',
            title='Error Relationships',
            hover_data=['Count']
        )
        
        fig.update_layout(
            xaxis_title='File Path',
            yaxis_title='Error Type',
            template='plotly_white'
        )
        
        return fig
    
    return None

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
            try:
                headers = {'Content-Type': 'application/json'}
                auth = None
                if loki_username and loki_password:
                    auth = (loki_username, loki_password)
                
                response = requests.get(
                    f"{loki_url}/loki/api/v1/labels",
                    headers=headers,
                    auth=auth,
                    verify=verify_ssl
                )
                response.raise_for_status()
                st.session_state.loki_config['is_configured'] = True
                st.success("Successfully connected to Loki!")
            except Exception as e:
                st.error(f"Failed to connect to Loki: {str(e)}")

def fetch_and_process_loki_logs():
    """Fetch logs from Loki and process them like uploaded files."""
    if not st.session_state.loki_config.get('is_configured'):
        return False

    try:
        # Setup Loki request
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)  # Last 24 hours by default
        
        url = f"{st.session_state.loki_config['url']}/loki/api/v1/query_range"
        query = '{job=~".+"}'  # Match all jobs
        
        params = {
            'query': query,
            'start': int(start_time.timestamp() * 1e9),
            'end': int(end_time.timestamp() * 1e9),
            'limit': 5000
        }
        
        headers = {'Content-Type': 'application/json'}
        auth = None
        if st.session_state.loki_config.get('username') and st.session_state.loki_config.get('password'):
            auth = (st.session_state.loki_config['username'], st.session_state.loki_config['password'])
        
        response = requests.get(
            url,
            params=params,
            headers=headers,
            auth=auth,
            verify=st.session_state.loki_config['verify_ssl']
        )
        response.raise_for_status()
        data = response.json()
        
        # Convert Loki logs to the format expected by our analyzer
        log_content = []
        if 'data' in data and 'result' in data['data']:
            for stream in data['data']['result']:
                for value in stream['values']:
                    timestamp, message = value
                    log_content.append(message)
        
        # Join log messages with newlines to create a single string
        content = '\n'.join(log_content)
        
        # Process logs using existing analyzer
        with st.spinner("Analyzing Loki logs..."):
            # Extract individual errors
            extracted_errors = st.session_state.analyzer.extract_errors(content)
            st.session_state.errors = extracted_errors
            
            # Group similar errors
            error_groups = st.session_state.analyzer.group_similar_errors(extracted_errors)
            
            # Analyze error patterns
            error_patterns = st.session_state.analyzer.analyze_error_patterns(error_groups)
            st.session_state.error_patterns = error_patterns
            
            # Get comprehensive analysis
            if error_patterns:
                with st.spinner("Generating comprehensive analysis..."):
                    st.session_state.comprehensive_analysis = st.session_state.analyzer.get_comprehensive_analysis(error_patterns)
                
                with st.spinner("Generating fix recommendations..."):
                    st.session_state.fix_recommendations = st.session_state.analyzer.get_unified_fix_recommendations(error_patterns)
            
            return True
            
    except Exception as e:
        st.error(f"Error fetching logs from Loki: {str(e)}")
        return False

# --- Main Content ---
st.title(page)

if page == "Dashboard":
    # Check if Loki is configured
    if st.session_state.loki_config.get('is_configured'):
        # Add search and time range controls
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            search_query = st.text_input("Search logs...", key="search_input", placeholder="Search logs...")
        with col2:
            time_range = st.selectbox(
                "Time Range",
                ["Last 24 hours", "Last 7 days", "Last 30 days", "Custom"],
                key="time_range"
            )
        with col3:
            if st.button("Refresh"):
                st.session_state.file_processed = fetch_and_process_loki_logs()
                st.experimental_rerun()
        
        # Process Loki data if not already processed
        if 'file_processed' not in st.session_state or not st.session_state.file_processed:
            st.session_state.file_processed = fetch_and_process_loki_logs()
        
        if st.session_state.file_processed:
            st.success("Successfully analyzed Loki logs")
            
            # Display summary metrics in cards
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                error_count = len([log for log in st.session_state.errors if 'ERROR' in log.get('full_traceback', '').upper()])
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-value" style="color: #dc3545;">{error_count}</div>
                        <div class="metric-label">Errors</div>
                        <div class="last-updated">Last updated: {datetime.now().strftime('%H:%M:%S')}</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            with col2:
                warning_count = len([log for log in st.session_state.errors if 'WARNING' in log.get('full_traceback', '').upper()])
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-value" style="color: #ffc107;">{warning_count}</div>
                        <div class="metric-label">Warnings</div>
                        <div class="last-updated">Last updated: {datetime.now().strftime('%H:%M:%S')}</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            with col3:
                info_count = len([log for log in st.session_state.errors if 'INFO' in log.get('full_traceback', '').upper()])
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-value" style="color: #0d6efd;">{info_count}</div>
                        <div class="metric-label">Info</div>
                        <div class="last-updated">Last updated: {datetime.now().strftime('%H:%M:%S')}</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            with col4:
                resolved_count = 0  # This would need to be tracked separately
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-value" style="color: #198754;">{resolved_count}</div>
                        <div class="metric-label">Resolved</div>
                        <div class="last-updated">Last updated: {datetime.now().strftime('%H:%M:%S')}</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )

            # Recent Logs section
            st.subheader("Recent Logs")
            
            # Convert logs to DataFrame for display
            log_entries = []
            for error in st.session_state.errors:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # You might want to extract this from the log
                message = error.get('error_message', '')
                level = 'error' if 'ERROR' in error.get('full_traceback', '').upper() else \
                       'warning' if 'WARNING' in error.get('full_traceback', '').upper() else 'info'
                service = 'system'  # You might want to extract this from the log
                
                log_entries.append({
                    'Time': timestamp,
                    'Message': message,
                    'Level': level,
                    'Service': service
                })
            
            if log_entries:
                df = pd.DataFrame(log_entries)
                
                # Apply search filter if provided
                if search_query:
                    df = df[df['Message'].str.contains(search_query, case=False, na=False)]
                
                # Style the DataFrame
                def color_level(val):
                    colors = {
                        'error': 'color: #dc3545',
                        'warning': 'color: #ffc107',
                        'info': 'color: #0d6efd'
                    }
                    return colors.get(val.lower(), '')
                
                styled_df = df.style.applymap(color_level, subset=['Level'])
                
                # Display logs with custom styling
                st.dataframe(
                    styled_df,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No logs found for the selected time range.")

            # Error Summary section
            st.subheader("Error Summary")
            
            total_errors = len(st.session_state.errors)
            unique_patterns = len(st.session_state.error_patterns)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-value">{total_errors}</div>
                        <div class="metric-label">Total Errors</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            with col2:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-value">{unique_patterns}</div>
                        <div class="metric-label">Error Patterns</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            if st.session_state.error_patterns:
                with col3:
                    top_error = st.session_state.error_patterns[0]['error_type']
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-value">{top_error}</div>
                            <div class="metric-label">Most Common Error</div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                
                with col4:
                    unique_files = set()
                    for pattern in st.session_state.error_patterns:
                        for file in pattern['common_files'].keys():
                            unique_files.add(file)
                    
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-value">{len(unique_files)}</div>
                            <div class="metric-label">Affected Files</div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
            
            # Display visualizations
            st.subheader("Error Visualizations")
            
            # Error Distribution Chart
            error_chart = create_error_distribution_chart(st.session_state.error_patterns)
            if error_chart:
                st.plotly_chart(error_chart, use_container_width=True)
            
            # Error File Heatmap
            col1, col2 = st.columns(2)
            
            with col1:
                heatmap = create_error_file_heatmap(st.session_state.error_patterns)
                if heatmap:
                    st.plotly_chart(heatmap, use_container_width=True)
            
            with col2:
                network_chart = create_error_network_chart(st.session_state.error_patterns)
                if network_chart:
                    st.plotly_chart(network_chart, use_container_width=True)
    
    elif uploaded_file:
        # Existing file upload logic
        if 'file_processed' not in st.session_state or not st.session_state.file_processed:
            st.session_state.file_processed = process_uploaded_file()
        
        if st.session_state.file_processed:
            st.success(f"Analyzed log file: {uploaded_file.name}")
            
            # Display summary metrics
            st.subheader("Error Summary")
            
            total_errors = len(st.session_state.errors)
            unique_patterns = len(st.session_state.error_patterns)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-value">{total_errors}</div>
                        <div class="metric-label">Total Errors</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            with col2:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-value">{unique_patterns}</div>
                        <div class="metric-label">Error Patterns</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            if st.session_state.error_patterns:
                with col3:
                    top_error = st.session_state.error_patterns[0]['error_type']
                    top_count = st.session_state.error_patterns[0]['count']
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-value">{top_error}</div>
                            <div class="metric-label">Most Common Error</div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                
                with col4:
                    unique_files = set()
                    for pattern in st.session_state.error_patterns:
                        for file in pattern['common_files'].keys():
                            unique_files.add(file)
                    
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-value">{len(unique_files)}</div>
                            <div class="metric-label">Affected Files</div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
            
            # Display visualizations
            st.subheader("Error Visualizations")
            
            # Error Distribution Chart
            error_chart = create_error_distribution_chart(st.session_state.error_patterns)
            if error_chart:
                st.plotly_chart(error_chart, use_container_width=True)
            
            # Error File Heatmap
            col1, col2 = st.columns(2)
            
            with col1:
                heatmap = create_error_file_heatmap(st.session_state.error_patterns)
                if heatmap:
                    st.plotly_chart(heatmap, use_container_width=True)
            
            with col2:
                network_chart = create_error_network_chart(st.session_state.error_patterns)
                if network_chart:
                    st.plotly_chart(network_chart, use_container_width=True)
            
            # Quick insights
            if st.session_state.error_patterns:
                st.subheader("Quick Insights")
                
                # Display the top 3 error patterns
                for i, pattern in enumerate(st.session_state.error_patterns[:3], 1):
                    with st.expander(f"Error Pattern #{i}: {pattern['error_type']} ({pattern['count']} occurrences)"):
                        st.write(f"**Error Type:** {pattern['error_type']}")
                        st.write(f"**Occurrence Count:** {pattern['count']}")
                        st.write("**Common Files Affected:**")
                        for file, count in pattern['common_files'].items():
                            st.write(f"- {file} ({count} occurrences)")
                        st.write(f"**Representative Error Message:** {pattern['representative_error'].get('error_message', 'No message')}")
                
                # Add a button to navigate to comprehensive analysis
                if st.button("View Comprehensive Analysis"):
                    st.session_state.current_page = "Comprehensive Analysis"
                    st.experimental_rerun()
                
            # Add a refresh button
            if st.button("Refresh Analysis"):
                st.session_state.file_processed = False
                st.experimental_rerun()
    else:
        st.info("Please upload a log file using the sidebar to begin analysis.")
        
        # Display sample dashboard with dummy data
        st.subheader("Sample Dashboard Preview")
        st.image("https://via.placeholder.com/800x400?text=Sample+Error+Dashboard", use_column_width=True)

elif page == "Error Patterns":
    if not st.session_state.error_patterns:
        st.info("No error patterns to display. Please upload a log file first.")
    else:
        st.subheader("Identified Error Patterns")
        
        # Create tabs for different views
        tab1, tab2 = st.tabs(["Pattern Overview", "Detailed View"])
        
        with tab1:
            # Create a dataframe for the patterns
            pattern_data = []
            for i, pattern in enumerate(st.session_state.error_patterns):
                pattern_data.append({
                    "ID": i+1,
                    "Error Type": pattern['error_type'],
                    "Count": pattern['count'],
                    "Top File": list(pattern['common_files'].keys())[0] if pattern['common_files'] else "N/A",
                    "Error Message": pattern['representative_error'].get('error_message', 'No message')[:50] + "..."
                })
            
            pattern_df = pd.DataFrame(pattern_data)
            st.dataframe(pattern_df, use_container_width=True)
            
            # Display error distribution chart
            error_chart = create_error_distribution_chart(st.session_state.error_patterns)
            if error_chart:
                st.plotly_chart(error_chart, use_container_width=True)
        
        with tab2:
            # Select a pattern to view in detail
            pattern_options = {
                f"Pattern {i+1}: {pattern['error_type']} ({pattern['count']} occurrences)": i 
                for i, pattern in enumerate(st.session_state.error_patterns)
            }
            
            selected = st.selectbox(
                "Select a pattern to view in detail:",
                options=list(pattern_options.keys())
            )
            
            if selected:
                pattern_index = pattern_options[selected]
                pattern = st.session_state.error_patterns[pattern_index]
                
                # Display pattern details
                st.write(f"**Error Type:** {pattern['error_type']}")
                st.write(f"**Occurrence Count:** {pattern['count']}")
                
                # Show affected files
                st.write("**Affected Files:**")
                file_data = []
                for file, count in pattern['common_files'].items():
                    file_data.append({
                        "File Path": file,
                        "Error Count": count
                    })
                
                if file_data:
                    file_df = pd.DataFrame(file_data)
                    st.dataframe(file_df, use_container_width=True)
                
                # Show representative error
                st.write("**Representative Error:**")
                st.code(pattern['representative_error'].get('full_traceback', 'No traceback available'))
                
                # Show all errors in this pattern
                with st.expander("View All Errors in this Pattern"):
                    for i, error in enumerate(pattern['errors'], 1):
                        st.write(f"**Error {i}:**")
                        st.write(f"- File: {error.get('file_path', 'Unknown')}")
                        st.write(f"- Line: {error.get('line_number', 'Unknown')}")
                        st.write(f"- Message: {error.get('error_message', 'No message')}")

elif page == "Comprehensive Analysis":
    if not st.session_state.comprehensive_analysis:
        st.info("No analysis available. Please upload a log file first.")
    else:
        st.subheader("Comprehensive Error Analysis")
        
        # Display the comprehensive analysis
        st.markdown(st.session_state.comprehensive_analysis)
        
        # Add visualization of error relationships
        st.subheader("Error Pattern Relationships")
        
        # Display the heatmap
        heatmap = create_error_file_heatmap(st.session_state.error_patterns)
        if heatmap:
            st.plotly_chart(heatmap, use_container_width=True)
        
        # Call to action
        if st.button("View Fix Recommendations"):
            st.session_state.current_page = "Fix Recommendations"
            st.experimental_rerun()

elif page == "Fix Recommendations":
    if not st.session_state.fix_recommendations:
        st.info("No fix recommendations available. Please upload a log file first.")
    else:
        st.subheader("Unified Fix Recommendations")
        
        # Display the fix recommendations
        st.markdown(st.session_state.fix_recommendations)
        
        # Add implementation plan section
        st.subheader("Implementation Plan")
        
        # Create tabs for implementation steps
        tab1, tab2, tab3 = st.tabs(["Immediate Fixes", "Medium-term Fixes", "Long-term Prevention"])
        
        with tab1:
            st.write("### Immediate Fixes")
            st.write("Apply these fixes to resolve the most critical errors:")
            
            # This would ideally be populated from the fix recommendations
            # For now, we'll use placeholder content
            st.code("""
# Example fix for the most common error pattern
def fix_example():
    try:
        # Fixed implementation
        result = process_data(validated_input)
        return result
    except ValueError as e:
        logger.error(f"Data processing error: {e}")
        return None
            """, language="python")
            
            # Add "Copy to clipboard" button
            if st.button("Copy Fix to Clipboard"):
                st.success("Code copied to clipboard!")
        
        with tab2:
            st.write("### Medium-term Fixes")
            st.write("These fixes should be implemented in the next sprint:")
            
            # Medium-term fix suggestions
            st.write("1. Implement proper input validation across all endpoints")
            st.write("2. Add comprehensive error handling in core modules")
            st.write("3. Fix resource management issues")
        
        with tab3:
            st.write("### Long-term Prevention")
            st.write("Implement these practices to prevent similar issues:")
            
            # Long-term prevention suggestions
            st.write("1. Set up automated testing for error cases")
            st.write("2. Implement code reviews with focus on error handling")
            st.write("3. Add monitoring and alerting for runtime errors")

elif page == "Settings":
    show_settings()

# --- Footer ---
st.markdown("---")
st.caption("Enhanced Log Analytics Dashboard v1.0")