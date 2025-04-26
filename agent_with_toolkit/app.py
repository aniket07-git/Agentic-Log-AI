import streamlit as st
from agent import analyze_logs

# Streamlit page setup
st.title("🔍 Log Analytics Dashboard")

data = analyze_logs()

error_data = data["json_object"]

# Display each error and resolution inside a visually appealing card with proper spacing and background color
for error in error_data:
    with st.container():
        # Add a light background color and padding for each card
        st.markdown(
            """
            <style>
            .error-card {
                background-color: #f9f9f9;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 10px;
                box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
                max-width: 75%; /* Set the card width to 3/4 of the window size */
                margin-left: auto;
                margin-right: auto;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="error-card">', unsafe_allow_html=True)

        st.markdown("### ⚠ Error Report")
        col1, col2 = st.columns([1, 1])

        # Left column: Error Analysis
        with col1:
            st.subheader(f"{error['error_type']} - {error['error_message']}")
            st.write(f"📂 Log Level:** {error['log_level']}")
            st.write(f"📌 File Location:** {error['file_location']}, Line {error['line_number']}")
            st.write(f"📝 Explanation:** {error['error_explanation']}")
            st.write("⚡ Related Code:")
            st.code(error["related_code"], language="python")
            st.write("🔧 Recommended Fixes:")
            for idx, fix in enumerate(error["fixes"]):
                st.write(f"- {fix}")

        # Right column: Recommended Resolution
        with col2:
            st.subheader("🛠 Resolution")
            st.code(error["code_suggestion"], language="python")

        # Buttons for applying fixes or dismissing errors
        col3, col4 = st.columns(2)
        with col3:
            if st.button("✅ Apply Fix", key=f"apply_{error['error_type']}_{error['line_number']}"):
                st.success("Code fixed successfully!")
        with col4:
            if st.button("❌ Dismiss", key=f"dismiss_{error['error_type']}_{error['line_number']}"):
                st.warning("Dismissed successfully!")

        st.markdown('</div>', unsafe_allow_html=True)

st.write("📌 End of Error Logs")
