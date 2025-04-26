import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pandas as pd

def show_error_resolution(error_type: str, details: dict, ai_analysis: dict):
    """Display detailed error resolution page with AI analysis."""
    st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 20px;">
            <h2 style="margin: 0;">Resolution: {error_type}</h2>
            <span class="confidence-tag {details.get('confidence', 'medium').lower()}-confidence" style="margin-left: 15px;">
                {details.get('confidence', 'MEDIUM')} Confidence
            </span>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Error Pattern Analysis")
        
        # Error Type and Services
        st.subheader("Error Type")
        st.write(error_type)
        
        st.subheader("Services Affected")
        for service in details.get('services', []):
            st.markdown(f"<span class='service-tag'>{service}</span>", unsafe_allow_html=True)
        
        # Error Messages
        st.subheader("Error Messages")
        for msg in details.get('error_messages', []):
            st.markdown(f"""
            <div style='background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 10px;'>
                {msg}
            </div>
            """, unsafe_allow_html=True)
        
        # AI Analysis
        if ai_analysis:
            st.header("AI Analysis")
            
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
            
            # Code Fix
            if ai_analysis.get('code_fix'):
                st.subheader("Suggested Code Fix")
                st.code(ai_analysis['code_fix'], language='python')
    
    with col2:
        st.header("Impact Analysis")
        
        # Severity
        st.subheader("Severity")
        severity = 'High' if details.get('count', 0) > 10 else 'Medium' if details.get('count', 0) > 5 else 'Low'
        severity_color = '#dc3545' if severity == 'High' else '#ffc107' if severity == 'Medium' else '#0dcaf0'
        st.markdown(f"""
        <div style='background-color: {severity_color}20; color: {severity_color}; 
                    padding: 10px; border-radius: 5px; display: inline-block;'>
            {severity}
        </div>
        """, unsafe_allow_html=True)
        
        # Error Trend
        st.subheader("Error Trend")
        error_trend = pd.DataFrame({
            'timestamp': [datetime.now() - timedelta(hours=i) for i in range(24)],
            'count': details.get('trend_data', [0] * 24)
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

    # Action Buttons
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("Apply Fix"):
            st.success("Fix applied successfully!")
    with col2:
        if st.button("Dismiss"):
            st.session_state.current_view = 'dashboard'
            st.session_state.selected_error = None
            st.rerun() 