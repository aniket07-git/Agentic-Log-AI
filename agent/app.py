import os
import re
from pathlib import Path
from typing import List, Dict, Optional
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
from io import StringIO
import sys
import time
import requests
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

console = Console()

# Loki configuration
LOKI_URL = os.getenv('LOKI_URL', 'http://localhost:3100')

def fetch_loki_logs(time_range_minutes=60):
    """Fetch logs from Loki for the specified time range."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=time_range_minutes)
    
    # Convert to nanoseconds (Loki uses nanosecond timestamps)
    start_ns = int(start_time.timestamp() * 1e9)
    end_ns = int(end_time.timestamp() * 1e9)
    
    query = '{job="simulated_system"}'
    url = f"{LOKI_URL}/loki/api/v1/query_range"
    
    params = {
        'query': query,
        'start': start_ns,
        'end': end_ns,
        'limit': 1000
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data and 'result' in data['data']:
            logs = []
            for stream in data['data']['result']:
                for value in stream['values']:
                    timestamp, message = value
                    logs.append({
                        'timestamp': datetime.fromtimestamp(int(timestamp) / 1e9),
                        'message': message
                    })
            return logs
        return []
    except Exception as e:
        st.error(f"Error fetching logs from Loki: {str(e)}")
        return []

class LogAnalyzer:
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
                        context[key] = match.group(1)
            
            if context.get('file_path') and context.get('line_number'):
                errors.append(context)
        
        return errors

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

    def apply_fix(self, file_path: str, original_content: str, fix_content: str, start_line: int, end_line: int) -> bool:
        """Apply the fix to the specific part of the file."""
        try:
            lines = original_content.split('\n')
            new_lines = lines[:start_line] + fix_content.split('\n') + lines[end_line:]
            with open(file_path, 'w') as f:
                f.write('\n'.join(new_lines))
            return True
        except Exception as e:
            console.print(f"[red]Error applying fix: {str(e)}[/red]")
            return False

    def get_error_analysis(self, error_context: Dict, code_context: Dict) -> str:
        """Get detailed analysis of the error."""
        analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert software engineer and debugger. 
            Analyze the following error and code context to provide a detailed explanation:
            1. What is the error and why did it occur?
            2. What is the root cause of this issue?
            3. What is the impact of this error?
            4. What are the potential consequences if not fixed?
            5. What are the best practices to prevent this type of error?
            
            Be specific and provide actionable insights. Use clear, non-technical language where possible."""),
            ("user", """
            Error Context:
            {error_context}
            
            Code Context:
            {code_context}
            
            Please provide a detailed analysis:
            """)
        ])

        analysis_chain = (
            {"error_context": lambda x: str(error_context), "code_context": lambda x: code_context['code']}
            | analysis_prompt
            | self.llm
            | StrOutputParser()
        )

        return analysis_chain.invoke({})

    def get_fix(self, error_context: Dict, code_context: Dict) -> str:
        """Get the best fix for the error."""
        fix_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert software engineer. 
            Based on the error and code context, provide the BEST fix for the code.
            Return ONLY the code that needs to be changed.
            No explanations, no markdown formatting, just the raw code.
            Include only the lines that need to be modified.
            Make sure the code is properly formatted and indented.
            Choose the most robust and maintainable solution."""),
            ("user", """
            Error Context:
            {error_context}
            
            Original Code:
            {code_context}
            
            Provide the best fix:
            """)
        ])

        fix_chain = (
            {"error_context": lambda x: str(error_context), "code_context": lambda x: code_context['code']}
            | fix_prompt
            | self.llm
            | StrOutputParser()
        )

        return fix_chain.invoke({})

# --- Page Config ---
st.set_page_config(
    page_title="Log Analytics Dashboard",
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
    </style>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
if 'analyzer' not in st.session_state:
    st.session_state.analyzer = LogAnalyzer()
if 'errors' not in st.session_state:
    st.session_state.errors = []
if 'selected_error_index' not in st.session_state:
    st.session_state.selected_error_index = None
if 'resolutions' not in st.session_state:
    st.session_state.resolutions = {}  # Store resolution status for each error

# --- Sidebar ---
st.sidebar.title("LogAnalytics")
st.sidebar.markdown("---")

# File Upload Section
uploaded_file = st.sidebar.file_uploader(
    "Upload Log File",
    type=['log', 'txt'],
    help="Upload a log file to analyze errors"
)

st.sidebar.markdown("---")

# Navigation
st.sidebar.subheader("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Dashboard", "Error Analysis", "Resolutions", "Loki Logs"]
)

# --- Helper Functions ---
def process_uploaded_file():
    """Process the uploaded log file and extract errors."""
    if uploaded_file is not None:
        try:
            # Read file content
            content = uploaded_file.getvalue().decode("utf-8")
            
            with st.spinner("Analyzing log file..."):
                # Extract errors using the analyzer
                extracted_errors = st.session_state.analyzer.extract_errors(content)
                
                # Store errors in session state
                st.session_state.errors = extracted_errors
                
                # Initialize resolution status for new errors
                for i, error in enumerate(extracted_errors):
                    if i not in st.session_state.resolutions:
                        st.session_state.resolutions[i] = {
                            'status': 'Pending',
                            'error': error
                        }
                
                return True
        except Exception as e:
            st.error(f"Error processing log file: {str(e)}")
            return False
    return False

def display_error_metrics():
    """Display error metrics in the dashboard."""
    total_errors = len(st.session_state.errors)
    resolved = sum(1 for res in st.session_state.resolutions.values() if res['status'] == 'Applied')
    pending = sum(1 for res in st.session_state.resolutions.values() if res['status'] == 'Pending')
    dismissed = sum(1 for res in st.session_state.resolutions.values() if res['status'] == 'Dismissed')
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Errors", total_errors)
    col2.metric("Resolved", resolved, f"{resolved/total_errors*100:.1f}%" if total_errors > 0 else "0%")
    col3.metric("Pending", pending)
    col4.metric("Dismissed", dismissed)

def display_error_table(errors: List[Dict]):
    """Display a table of errors with their details."""
    if not errors:
        st.info("No errors found in the log file.")
        return
    
    # Create a list of dictionaries for the dataframe
    error_data = []
    for i, error in enumerate(errors):
        status = st.session_state.resolutions.get(i, {}).get('status', 'Pending')
        error_data.append({
            "ID": i,
            "Status": status,
            "Type": error.get('error_type', 'Unknown'),
            "File": error.get('file_path', 'Unknown'),
            "Line": error.get('line_number', 'Unknown'),
            "Message": error.get('error_message', 'No message')
        })
    
    st.dataframe(error_data, use_container_width=True)

def get_error_details(error: Dict):
    """Get detailed analysis and fix for an error."""
    file_path = st.session_state.analyzer.find_file(error['file_path'])
    if not file_path:
        st.warning(f"Could not locate file: {error['file_path']}")
        return None, None, None
    
    try:
        code_context = st.session_state.analyzer.get_relevant_code(
            file_path,
            int(error['line_number'])
        )
        
        if 'error' in code_context:
            st.warning(f"Error getting code context: {code_context['error']}")
            return None, None, None
        
        with st.spinner("Generating analysis..."):
            analysis = st.session_state.analyzer.get_error_analysis(error, code_context)
        
        with st.spinner("Generating fix..."):
            fix = st.session_state.analyzer.get_fix(error, code_context)
        
        return code_context, analysis, fix
    except Exception as e:
        st.error(f"Error getting details: {str(e)}")
        return None, None, None

# --- Main Content ---
st.title(page)

if page == "Dashboard":
    if uploaded_file:
        if 'file_processed' not in st.session_state or not st.session_state.file_processed:
            st.session_state.file_processed = process_uploaded_file()
        
        if st.session_state.file_processed:
            st.success(f"Analyzed log file: {uploaded_file.name}")
            
            # Display metrics
            display_error_metrics()
            
            # Display error table
            st.subheader("Error Overview")
            display_error_table(st.session_state.errors)
            
            # Add a refresh button
            if st.button("Refresh Analysis"):
                st.session_state.file_processed = False
                st.experimental_rerun()
    else:
        st.info("Please upload a log file using the sidebar to begin analysis.")

elif page == "Error Analysis":
    if not st.session_state.errors:
        st.info("No errors to analyze. Please upload a log file first.")
    else:
        # Error selection
        error_options = {
            f"Error {i} ({err.get('error_type', 'Unknown')} in {os.path.basename(err.get('file_path', 'Unknown'))})": i 
            for i, err in enumerate(st.session_state.errors)
        }
        
        selected = st.selectbox(
            "Select an error to analyze:",
            options=list(error_options.keys())
        )
        
        if selected:
            error_index = error_options[selected]
            error = st.session_state.errors[error_index]
            
            # Display error details
            st.subheader("Error Details")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Type:** {error.get('error_type', 'Unknown')}")
                st.write(f"**File:** {error.get('file_path', 'Unknown')}")
            with col2:
                st.write(f"**Line:** {error.get('line_number', 'Unknown')}")
                st.write(f"**Status:** {st.session_state.resolutions.get(error_index, {}).get('status', 'Pending')}")
            
            # Show full traceback in expander
            with st.expander("Show Full Traceback"):
                st.code(error.get('full_traceback', 'No traceback available'))
            
            # Get and display detailed analysis
            code_context, analysis, fix = get_error_details(error)
            
            if code_context and analysis and fix:
                # Show relevant code
                st.subheader("Relevant Code")
                st.code(code_context['code'], language="python")
                
                # Show analysis
                st.subheader("AI Analysis")
                st.markdown(analysis)
                
                # Show fix
                st.subheader("Suggested Fix")
                st.code(fix, language="python")
                
                # Action buttons
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Apply Fix", key=f"apply_{error_index}"):
                        st.session_state.resolutions[error_index]['status'] = 'Applied'
                        st.success("Fix marked as applied!")
                with col2:
                    if st.button("Dismiss", key=f"dismiss_{error_index}"):
                        st.session_state.resolutions[error_index]['status'] = 'Dismissed'
                        st.info("Error marked as dismissed.")
                with col3:
                    if st.button("Reset Status", key=f"reset_{error_index}"):
                        st.session_state.resolutions[error_index]['status'] = 'Pending'
                        st.info("Status reset to pending.")

elif page == "Resolutions":
    if not st.session_state.errors:
        st.info("No errors to display. Please upload a log file first.")
    else:
        # Filter options
        status_filter = st.radio(
            "Filter by status:",
            ["All", "Pending", "Applied", "Dismissed"],
            horizontal=True
        )
        
        # Display resolutions table
        st.subheader("Resolution Status")
        
        resolution_data = []
        for i, res_info in st.session_state.resolutions.items():
            if status_filter == "All" or res_info['status'] == status_filter:
                error = res_info['error']
                resolution_data.append({
                    "ID": i,
                    "Status": res_info['status'],
                    "Type": error.get('error_type', 'Unknown'),
                    "File": error.get('file_path', 'Unknown'),
                    "Line": error.get('line_number', 'Unknown'),
                    "Message": error.get('error_message', 'No message')
                })
        
        if resolution_data:
            st.dataframe(resolution_data, use_container_width=True)
        else:
            st.info(f"No errors with status: {status_filter}")

elif page == "Loki Logs":
    st.title("Loki Logs")
    
    # Time range selector
    time_range = st.slider(
        "Select time range (minutes)",
        min_value=1,
        max_value=1440,  # 24 hours
        value=60,
        step=1
    )
    
    # Refresh button
    if st.button("Refresh Logs"):
        st.experimental_rerun()
    
    # Fetch and display logs
    logs = fetch_loki_logs(time_range)
    
    if logs:
        # Create a container for the logs
        log_container = st.container()
        
        # Display logs in reverse chronological order
        for log in reversed(logs):
            with log_container:
                st.text(f"{log['timestamp']}: {log['message']}")
    else:
        st.info("No logs found in the selected time range.")

# --- Footer ---
st.markdown("---")
st.caption("Log Analytics Dashboard v0.1")

# if __name__ == '__main__':
#     main() 