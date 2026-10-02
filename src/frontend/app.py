"""
Pillar 4.1 -- Streamlit Conversational Interface & API Integration

Provides an interactive ChatGPT-style conversational Business Intelligence UI
for business stakeholders at The Gadget Store:
1. Natural language chat interface with session history.
2. Integrates with FastAPI backend POST /ask endpoint (Pillar 3).
3. Renders Executive Summaries, Interactive Data Tables, Dynamic Plotly Charts,
   and Expandable SQL Debug blocks.
4. Handles clarification questions and backend error states seamlessly.
"""

import uuid
import requests
import pandas as pd
import streamlit as st
import os
import sys

sys.path.append(os.path.dirname(__file__))
from charts import render_chart

# -----------------------------------------------------------------------------
# Page Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Talk-to-my-Data (GenAI BI)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Modern Custom CSS
st.markdown(
    """
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #64748b;
        margin-bottom: 1.5rem;
    }
    .summary-box {
        background-color: #f0f9ff;
        border-left: 5px solid #0284c7;
        padding: 1.2rem;
        border-radius: 0.5rem;
        font-size: 1.05rem;
        line-height: 1.6;
        color: #0c4a6e;
        margin-bottom: 1rem;
    }
    .clarification-box {
        background-color: #fffbe6;
        border-left: 5px solid #faad14;
        padding: 1.2rem;
        border-radius: 0.5rem;
        color: #873800;
        margin-bottom: 1rem;
    }
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        font-size: 0.8rem;
        font-weight: 600;
        border-radius: 9999px;
        text-transform: uppercase;
    }
    .badge-ok { background-color: #dcfce7; color: #166534; }
    .badge-clarify { background-color: #fef3c7; color: #92400e; }
    .badge-error { background-color: #fee2e2; color: #991b1b; }
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------------------
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())[:8]

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_clarification" not in st.session_state:
    st.session_state.pending_clarification = False

if "last_question" not in st.session_state:
    st.session_state.last_question = ""


# -----------------------------------------------------------------------------
# Sidebar Controls & Settings
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/data-configuration.png", width=64)
    st.title("Talk-to-my-Data")
    st.caption("GenAI Business Intelligence Assistant")

    st.divider()

    # Backend Connection Config
    backend_url = st.text_input(
        "Backend API URL",
        value=os.getenv("BACKEND_API_URL", "http://127.0.0.1:8080/ask"),
        help="FastAPI endpoint URL (POST /ask)",
    )

    # Health Status Check
    health_url = backend_url.rsplit("/ask", 1)[0] + "/health"
    try:
        health_resp = requests.get(health_url, timeout=3)
        if health_resp.status_code == 200:
            st.success("🟢 Backend Connected")
        else:
            st.warning("🟡 Backend Status Degraded")
    except Exception:
        st.error("🔴 Backend Offline (Start FastAPI on 8080)")

    st.divider()

    st.markdown("### 💡 Sample Questions")
    sample_questions = [
        "What were total headphone sales in 2025?",
        "What are our top 5 product categories by revenue?",
        "How many stores opened after 2015?",
        "What's our average order value?",
        "What were sales last month?",
    ]

    selected_sample = None
    for q in sample_questions:
        if st.button(q, key=f"btn_{q}"):
            selected_sample = q

    st.divider()

    if st.button("🗑️ Clear Conversation", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = str(uuid.uuid4())[:8]
        st.session_state.pending_clarification = False
        st.session_state.last_question = ""
        st.rerun()

    st.caption(f"Session ID: `{st.session_state.conversation_id}`")


# -----------------------------------------------------------------------------
# Main Header
# -----------------------------------------------------------------------------
st.markdown(
    '<div class="main-title">📊 Talk-to-my-Data (GenAI BI)</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-title">Ask business questions in plain English to query the global electronics retail warehouse instantly.</div>',
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Render Chat History
# -----------------------------------------------------------------------------
for msg in st.session_state.messages:
    role = msg["role"]
    with st.chat_message(role):
        if role == "user":
            st.write(msg["content"])
        else:
            resp = msg.get("response_data", {})
            status = resp.get("status", "error")

            if status == "ok":
                # Executive Narrative Summary
                if resp.get("summary"):
                    st.markdown(
                        f'<div class="summary-box">💡 <b>Executive Summary:</b><br>{resp["summary"]}</div>',
                        unsafe_allow_html=True,
                    )

                # Data Table
                table_data = resp.get("table", [])
                if table_data:
                    st.markdown("#### 📋 Data Results")
                    df = pd.DataFrame(table_data)
                    st.dataframe(df, use_container_width=True)

                # Dynamic Chart Visualization (Pillar 4.2)
                chart_config = resp.get("chart")
                if chart_config and table_data:
                    render_chart(chart_config, table_data)

                # Expandable SQL Query Accordion
                if resp.get("sql"):
                    with st.expander("🔍 View Generated SQL Query"):
                        st.code(resp["sql"], language="sql")

            elif status == "needs_clarification":
                clarify_q = resp.get(
                    "clarification_question", "The query requires clarification."
                )
                st.markdown(
                    f'<div class="clarification-box">❓ <b>Clarification Needed:</b><br>{clarify_q}</div>',
                    unsafe_allow_html=True,
                )
                st.info("💡 Please type your answer below to continue your request.")

            elif status == "error":
                err_msg = resp.get(
                    "message", "An error occurred while processing your request."
                )
                st.error(f"⚠️ **Error:** {err_msg}")


# -----------------------------------------------------------------------------
# Handle New User Input
# -----------------------------------------------------------------------------
user_input = st.chat_input(
    "Type your business question here (e.g., What were total sales in 2025?)..."
)

# If user clicked a sample question button, override user_input
if selected_sample:
    user_input = selected_sample

if user_input:
    # 1. Display User Message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # 2. Prepare API Request Payload
    payload = {
        "question": user_input,
        "conversation_id": st.session_state.conversation_id,
        "clarification_answer": None,
    }

    # If answering a previous clarification question
    if st.session_state.pending_clarification and st.session_state.last_question:
        payload["question"] = st.session_state.last_question
        payload["clarification_answer"] = user_input
        st.session_state.pending_clarification = False
    else:
        st.session_state.last_question = user_input

    # 3. Call Backend API
    with st.chat_message("assistant"):
        with st.spinner(
            "Analyzing question, generating SQL & querying BigQuery warehouse..."
        ):
            try:
                api_response = requests.post(
                    backend_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=90,  # 15s timeout contract rule
                )
                if api_response.status_code == 200:
                    data = api_response.json()
                else:
                    data = {
                        "status": "error",
                        "message": f"Server returned HTTP {api_response.status_code}: {api_response.text}",
                    }
            except requests.exceptions.Timeout:
                data = {
                    "status": "error",
                    "message": "Backend request timed out (15s limit). Please check server health or retry.",
                }
            except Exception as e:
                data = {
                    "status": "error",
                    "message": f"Could not connect to backend API: {str(e)}",
                }

        # Track clarification state
        if data.get("status") == "needs_clarification":
            st.session_state.pending_clarification = True

        # Append assistant response to history
        st.session_state.messages.append(
            {"role": "assistant", "content": "", "response_data": data}
        )

        st.rerun()
