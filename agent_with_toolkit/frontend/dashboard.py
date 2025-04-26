import streamlit as st
import json
import os
import sys
from datetime import datetime, timedelta

# Add the parent directory to sys.path to import from parent directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import agent functionality
from agent import analyze_logs

# Set page configuration
st.set_page_config(
    page_title="Error Analysis Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom CSS
def apply_custom_css():
    st.markdown("""
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background-color: #f5f7fa;
        }
        .dashboard-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
            margin-bottom: 20px;
        }
        .dashboard-title {
            font-size: 24px;
            font-weight: 600;
            color: #333;
        }
        .search-bar {
            padding: 8px 15px;
            border-radius: 20px;
            border: 1px solid #ddd;
            width: 300px;
        }
        .user-info {
            display: flex;
            align-items: center;
        }
        .section-container {
            display: flex;
            gap: 20px;
        }
        .section {
            flex: 1;
            background-color: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .section-title {
            font-size: 18px;
            font-weight: 600;
            color: #333;
        }
        .view-all-link {
            color: #0066cc;
            text-decoration: none;
            font-size: 14px;
        }
        .error-card {
            background-color: #fff1f0;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            border-left: 3px solid #ff4d4f;
        }
        .error-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 5px;
        }
        .error-description {
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }
        .service-tag {
            display: inline-block;
            background-color: #f0f0f0;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            margin-right: 10px;
        }
        .time-info {
            display: inline-block;
            color: #666;
            font-size: 12px;
        }
        .occurrence-tag {
            float: right;
            background-color: #f0f0f0;
            padding: 4px 10px;
            border-radius: 15px;
            font-size: 12px;
            color: #666;
        }
        .view-analysis-btn {
            display: flex;
            align-items: center;
            color: #0066cc;
            font-size: 14px;
            cursor: pointer;
            margin-top: 10px;
        }
        .resolution-card {
            background-color: white;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            border: 1px solid #eee;
        }
        .confidence-tag {
            float: right;
            padding: 4px 10px;
            border-radius: 15px;
            font-size: 12px;
        }
        .high-confidence {
            background-color: #e6f7ef;
            color: #52c41a;
        }
        .medium-confidence {
            background-color: #e6f7ff;
            color: #1890ff;
        }
        .low-confidence {
            background-color: #fff7e6;
            color: #fa8c16;
        }
        .code-block {
            background-color: #333;
            color: #fff;
            padding: 10px;
            border-radius: 5px;
            font-family: monospace;
            margin: 10px 0;
        }
        .action-buttons {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .apply-fix-btn {
            background-color: #0066cc;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 5px 15px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .dismiss-btn {
            background-color: transparent;
            color: #666;
            border: none;
            border-radius: 5px;
            padding: 5px 15px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .occurrence-info {
            color: #666;
            font-size: 12px;
            text-align: right;
        }
        .analyze-btn {
            background-color: #0066cc;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 10px 20px;
            cursor: pointer;
            font-weight: bold;
            margin-bottom: 20px;
        }
        
        /* Hide default Streamlit elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display:none;}
        
        /* Adjust header styling */
        .stApp > header {
            background-color: white;
            border-bottom: 1px solid #eee;
        }
    </style>
    """, unsafe_allow_html=True)

apply_custom_css()

# Load the JSON data
@st.cache_data
def load_error_data():
    try:
        # Find the most recent JSON file with error_analysis prefix
        json_files = [f for f in os.listdir(parent_dir) if f.startswith('error_analysis_') and f.endswith('.json')]
        if not json_files:
            return []
            
        latest_file = max(json_files)
        json_path = os.path.join(parent_dir, latest_file)
        
        with open(json_path, 'r') as f:
            data = json.load(f)
            
        # Handle the data based on its structure
        if isinstance(data, list):
            # Data is already a list of errors, return it directly
            return data
        elif isinstance(data, dict):
            # If result is in the format {"json_object": "..."}, extract it
            if "json_object" in data:
                json_str = data["json_object"]
                # If json_object is a string, parse it
                if isinstance(json_str, str):
                    parsed_data = json.loads(json_str)
                    if isinstance(parsed_data, list):
                        return parsed_data
                    elif isinstance(parsed_data, dict):
                        # Flatten dictionary structure
                        errors = []
                        for log_file, error_list in parsed_data.items():
                            if isinstance(error_list, list):
                                for error in error_list:
                                    errors.append(error)
                            else:
                                errors.append(error_list)
                        return errors
                else:
                    # json_object is not a string but a parsed object
                    return data["json_object"]
            else:
                # Flatten dictionary structure
                errors = []
                for log_file, error_list in data.items():
                    if isinstance(error_list, list):
                        for error in error_list:
                            errors.append(error)
                    else:
                        errors.append(error_list)
                return errors
    except Exception as e:
        st.error(f"Error loading JSON file: {e}")
        return []

# Initialize session state
if 'errors' not in st.session_state:
    st.session_state.errors = load_error_data()
    
if 'analyzing' not in st.session_state:
    st.session_state.analyzing = False
    
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False

# Function to trigger log analysis
def run_analysis():
    st.session_state.analyzing = True
    try:
        with st.spinner('Analyzing logs... This may take a few minutes.'):
            result = analyze_logs()
            st.session_state.errors = load_error_data()  # Reload after analysis
            st.session_state.analyzing = False
            st.session_state.analysis_complete = True
            return True
    except Exception as e:
        st.error(f"Error during analysis: {str(e)}")
        st.session_state.analyzing = False
        return False

# Custom header
st.markdown("""
<div class="dashboard-header">
    <div class="dashboard-title">Error Analysis Dashboard</div>
    <div style="display: flex; align-items: center; gap: 20px;">
        <input class="search-bar" type="text" placeholder="Search logs..." disabled>
        <div class="user-info">
            Admin User
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Add run analysis button
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button('Run Error Analysis', key='analyze_button'):
        run_analysis()
    
    if st.session_state.analyzing:
        st.info('Analysis in progress... This may take a few minutes.')
        
    if st.session_state.analysis_complete and not st.session_state.analyzing:
        st.success('Analysis complete! Dashboard updated with latest results.')

# Get errors from session state
errors = st.session_state.errors

# Group errors by type
error_counts = {}
for error in errors:
    error_type = error["error_type"]
    if error_type in error_counts:
        error_counts[error_type] += 1
    else:
        error_counts[error_type] = 1

# Create two-column layout
left_col, right_col = st.columns(2)

# Left Column: Recent Error Analysis
with left_col:
    st.markdown("""
    <div class="section-header">
        <div class="section-title">Recent Error Analysis</div>
        <a href="#" class="view-all-link">View All</a>
    </div>
    """, unsafe_allow_html=True)
    
    if not errors:
        st.info("No errors found. Run the analysis to detect errors in logs.")
    
    # Show first 3 errors or fewer if there are less than 3
    for i, error in enumerate(errors[:min(3, len(errors))]):
        error_type = error["error_type"]
        error_message = error["error_message"]
        file_location = os.path.basename(error["file_location"])
        line_number = error["line_number"]
        error_explanation = error["error_explanation"]
        
        # Determine service type based on file location
        if "db_connector" in error["file_location"]:
            service = "auth-service"
        elif "network_client" in error["file_location"]:
            service = "api-service"
        elif "payment_service" in error["file_location"]:
            service = "payment-service"
        elif "user_service" in error["file_location"]:
            service = "user-service"
        else:
            service = "core-service"
            
        # Get number of occurrences
        occurrences = error_counts.get(error_type, 1)
        
        # Calculate relative time (in a real app this would use actual timestamps)
        time_info = "about 3 hours ago"
            
        st.markdown(f"""
        <div class="error-card">
            <div class="error-title">{error_type}: {error_message}</div>
            <div class="occurrence-tag">{occurrences} occurrences</div>
            <div class="error-description">{error_explanation}</div>
            <div>
                <span class="service-tag">{service}</span>
                <span class="time-info">• {time_info}</span>
            </div>
            <div class="view-analysis-btn">
                <span>▶ View Analysis</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# Right Column: Recommended Resolutions
with right_col:
    st.markdown("""
    <div class="section-header">
        <div class="section-title">Recommended Resolutions</div>
        <a href="#" class="view-all-link">View All</a>
    </div>
    """, unsafe_allow_html=True)
    
    if not errors:
        st.info("No resolutions available yet. Run the analysis first.")
    
    # Show resolutions for first 3 errors or fewer if there are less than 3
    for i, error in enumerate(errors[:min(3, len(errors))]):
        error_type = error["error_type"]
        confidence = error.get("confidence", "MEDIUM")
        confidence_class = "high-confidence" if confidence == "HIGH" else "medium-confidence" if confidence == "MEDIUM" else "low-confidence"
        file_location = os.path.basename(error["file_location"])
        code_suggestion = error["code_suggestion"]
        
        # Calculate occurrences
        occurrences = error_counts.get(error_type, 1)
        
        st.markdown(f"""
        <div class="resolution-card">
            <div class="error-title">{error_type} in {file_location}</div>
            <div class="confidence-tag {confidence_class}">{confidence} Confidence</div>
            <div class="error-description">Fix recommended for line {error['line_number']}</div>
            
            <div>
                <div style="font-weight: 600; margin-top: 10px; margin-bottom: 5px;">Suggested Code Change:</div>
                <div class="code-block">{code_suggestion}</div>
            </div>
            
            <div class="action-buttons">
                <button class="apply-fix-btn">
                    <span>✓</span> Apply Fix
                </button>
                <button class="dismiss-btn">
                    <span>✗</span> Dismiss
                </button>
            </div>
            <div class="occurrence-info">Based on {occurrences} error occurrences</div>
        </div>
        """, unsafe_allow_html=True)

# Add footer
st.markdown("---")
st.markdown("<p style='text-align: center; color: #666;'>Error Analysis Dashboard - Powered by AI Agent</p>", unsafe_allow_html=True)