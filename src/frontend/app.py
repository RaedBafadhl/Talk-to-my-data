"""
Pillar 4.1 -- Streamlit Conversational Interface & API Integration
 
Provides an interactive ChatGPT-style conversational Business Intelligence UI
for business stakeholders at The Gadget Store.
"""
 
import uuid
import json
import requests
import pandas as pd
import streamlit as st
import os
import sys
from datetime import datetime, timezone
 
sys.path.append(os.path.dirname(__file__))
from charts import render_chart
 
FEEDBACK_LOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "logs", "feedback.log"
)
 
 
def log_feedback(question: str, summary: str, vote: str):
    """
    Appends a thumbs-up/down vote to a local log file.
    NOTE: stored locally in logs/feedback.log for now -- appropriate for this
    stage of the project. For a real deployed product with multiple users,
    this would move to a proper database so votes aren't lost between
    restarts and can be queried/aggregated across sessions.
    """
    os.makedirs(os.path.dirname(FEEDBACK_LOG_PATH), exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "summary": summary,
        "vote": vote,
    }
    with open(FEEDBACK_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
 
 
def build_excel_report() -> bytes:
    """
    Builds a real, formatted Excel report of the whole conversation -- one
    sheet per question, with a styled header, the question, the summary,
    a formatted data table, and the chart embedded as an image (when one
    exists). This replaces a plain CSV dump with something a stakeholder
    could actually open and present.
    """
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
 
    wb = Workbook()
    wb.remove(wb.active)  # drop the default blank sheet
 
    HEADER_FILL = PatternFill(start_color="2E6FF2", end_color="2E6FF2", fill_type="solid")
    HEADER_FONT = Font(color="FFFFFF", bold=True, size=12)
    TITLE_FONT = Font(bold=True, size=14, color="12173B")
    LABEL_FONT = Font(bold=True, size=11, color="12173B")
 
    sheet_num = 0
    pending_question = None
 
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            pending_question = msg["content"]
            continue
 
        resp = msg.get("response_data", {})
        if resp.get("status") != "ok" or not pending_question:
            continue
 
        sheet_num += 1
        ws = wb.create_sheet(title=f"Q{sheet_num}"[:31])
 
        ws["A1"] = "Talk-to-my-Data -- Report"
        ws["A1"].font = TITLE_FONT
        ws.merge_cells("A1:D1")
 
        ws["A3"] = "Question:"
        ws["A3"].font = LABEL_FONT
        ws["B3"] = pending_question
        ws.merge_cells("B3:D3")
 
        ws["A4"] = "Answer:"
        ws["A4"].font = LABEL_FONT
        ws["B4"] = resp.get("summary", "")
        ws.merge_cells("B4:D4")
        ws["B4"].alignment = Alignment(wrap_text=True)
 
        row_cursor = 6
        table = resp.get("table", [])
        if table:
            df = pd.DataFrame(table)
            for col_idx, col_name in enumerate(df.columns, start=1):
                cell = ws.cell(row=row_cursor, column=col_idx, value=str(col_name))
                cell.font = HEADER_FONT
                cell.fill = HEADER_FILL
            for r_idx, row in enumerate(df.itertuples(index=False), start=row_cursor + 1):
                for c_idx, value in enumerate(row, start=1):
                    ws.cell(row=r_idx, column=c_idx, value=value)
            for col_idx in range(1, len(df.columns) + 1):
                ws.column_dimensions[get_column_letter(col_idx)].width = 20
 
            chart_row = row_cursor + len(df) + 3
 
            # Embed the chart as an image, if one exists -- gracefully skip
            # if kaleido (needed for static image export) isn't installed.
            chart_config = resp.get("chart")
            if chart_config:
                try:
                    import plotly.graph_objects as go
                    from openpyxl.drawing.image import Image as XLImage
 
                    x_field = chart_config.get("x_field")
                    y_field = chart_config.get("y_field")
                    x_vals = [row.get(x_field) for row in table]
                    y_vals = [float(row.get(y_field, 0)) for row in table]
 
                    fig = go.Figure()
                    if chart_config.get("type") == "line":
                        fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="lines+markers", line=dict(color="#2E6FF2", width=3)))
                    else:
                        fig.add_trace(go.Bar(x=x_vals, y=y_vals, marker=dict(color="#2E6FF2")))
                    fig.update_layout(plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", width=600, height=350)
 
                    img_bytes = fig.to_image(format="png")
                    img_buffer = io.BytesIO(img_bytes)
                    xl_img = XLImage(img_buffer)
                    ws.add_image(xl_img, f"A{chart_row}")
                except Exception:
                    # kaleido not installed, or image export failed -- the
                    # report still works fine without the embedded chart.
                    pass
 
        pending_question = None
 
    if sheet_num == 0:
        ws = wb.create_sheet(title="No data")
        ws["A1"] = "No completed answers yet to export."
 
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
 
 
# -----------------------------------------------------------------------------
# Page Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Talk-to-my-Data (GenAI BI)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
# Primary accent: a clean, professional blue -- the standard identity color
# for enterprise BI tools (Tableau, Power BI, Looker), replacing the earlier
# coral for a better fit with "trustworthy business software."
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@600;700&family=Inter:wght@400;500;600&display=swap');
 
.stApp { background-color: #F4F7FF; }
 
section[data-testid="stSidebar"] { background-color: #1C2B5C; }
section[data-testid="stSidebar"] > div:first-child { padding-top: 2.1rem; display: flex; flex-direction: column; min-height: 100vh; }
.block-container { padding-top: 2.1rem; }
section[data-testid="stSidebar"] * { color: #CADCFC !important; }
section[data-testid="stSidebar"] .stButton button {
    background-color: #24366E;
    color: #FFFFFF !important;
    border: 1px solid #35478C;
    border-radius: 8px;
    text-align: left;
}
section[data-testid="stSidebar"] .stButton button:hover {
    background-color: #2E6FF2;
    border-color: #2E6FF2;
}
 
.main-title {
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 2.6rem;
    font-weight: 700;
    color: #12173B;
    letter-spacing: -1px;
}
.sub-title {
    font-family: 'Inter', sans-serif;
    font-size: 1.1rem;
    color: #6B7290;
    margin-bottom: 1.8rem;
}
 
.summary-box {
    background-color: #FFFFFF;
    border-left: 4px solid #2E6FF2;
    padding: 1.2rem 1.4rem;
    border-radius: 10px;
    font-family: 'Inter', sans-serif;
    font-size: 1.05rem;
    line-height: 1.6;
    color: #12173B;
    margin-bottom: 1rem;
    box-shadow: 0 2px 10px rgba(18,23,59,0.06);
}
.clarification-box {
    background-color: #FFFFFF;
    border-left: 4px solid #2DD4BF;
    padding: 1.2rem 1.4rem;
    border-radius: 10px;
    font-family: 'Inter', sans-serif;
    color: #12173B;
    margin-bottom: 1rem;
    box-shadow: 0 2px 10px rgba(18,23,59,0.06);
}
 
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(18,23,59,0.06);
}
 
.welcome-card {
    background-color: #FFFFFF;
    border-radius: 12px;
    padding: 1.3rem;
    box-shadow: 0 2px 10px rgba(18,23,59,0.06);
    height: 100px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
 
.feedback-panel {
    background-color: #EAF1FF;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    margin-top: 0.5rem;
    margin-bottom: 1rem;
}
.feedback-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    color: #6B7290;
    margin-bottom: 0.4rem;
}
</style>
""",
    unsafe_allow_html=True,
)
 
 
# -----------------------------------------------------------------------------
# "About this data" popup dialog
# -----------------------------------------------------------------------------
@st.dialog("About this data")
def show_about_data():
    st.markdown("##### Five connected tables")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Sales**")
        st.caption("Every transaction")
        st.markdown("**Products**")
        st.caption("Catalog, prices, categories")
        st.markdown("**Customers**")
        st.caption("Location, demographics")
    with c2:
        st.markdown("**Stores**")
        st.caption("67 locations + online")
        st.markdown("**Exchange Rates**")
        st.caption("Converts everything to USD")
 
    st.divider()
    st.markdown("##### Core KPIs tracked")
    st.markdown("- Revenue over time\n- Top products & categories\n- Average Order Value\n- Category sales share")
 
    st.divider()
    st.caption("Data covers 2016–2021. All figures are in USD.")
 
 
# -----------------------------------------------------------------------------
# Session State
# -----------------------------------------------------------------------------
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())[:8]
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_clarification" not in st.session_state:
    st.session_state.pending_clarification = False
if "last_question" not in st.session_state:
    st.session_state.last_question = ""
if "feedback_given" not in st.session_state:
    st.session_state.feedback_given = {}
 
 
# -----------------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
<div style="font-family: 'Source Serif 4', Georgia, serif; font-size: 1.6rem; font-weight: 700; color: #FFFFFF;">
    T<span style="color:#2E6FF2;">G</span>S
</div>
<div style="font-family: 'Inter', sans-serif; font-size: 0.85rem; color: #A7B3DE; margin-bottom: 1.2rem;">
    GenAI Business Intelligence Assistant
</div>
""",
        unsafe_allow_html=True,
    )
 
    st.divider()
 
    if st.button("ℹ️ About this data", use_container_width=True):
        show_about_data()
 
    if st.session_state.messages:
        st.download_button(
            "⬇️ Download Excel report",
            data=build_excel_report(),
            file_name="talk_to_my_data_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
 
    st.markdown('<div style="flex-grow: 1;"></div>', unsafe_allow_html=True)
    st.divider()
 
    if st.button("🗑️ Clear Conversation", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = str(uuid.uuid4())[:8]
        st.session_state.pending_clarification = False
        st.session_state.last_question = ""
        st.session_state.feedback_given = {}
        st.rerun()
 
    with st.expander("⚙️ Connection settings"):
        backend_url = st.text_input(
            "Backend API URL",
            value=os.getenv("BACKEND_API_URL", "http://127.0.0.1:8080/ask"),
        )
        health_url = backend_url.rsplit("/ask", 1)[0] + "/health"
        try:
            health_resp = requests.get(health_url, timeout=3)
            if health_resp.status_code == 200:
                st.success("Connected")
            else:
                st.warning("Degraded")
        except Exception:
            st.error("Offline -- start the backend")
 
    if "backend_url" not in dir():
        backend_url = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8080/ask")
 
 
 
 
# -----------------------------------------------------------------------------
# Main Header
# -----------------------------------------------------------------------------
st.markdown(
    """
<div style="margin-bottom: 0.3rem;">
    <div class="main-title">T<span style="color:#2E6FF2;">G</span>S</div>
</div>
<div class="sub-title">Faster decisions. Better results. Ask a question, in plain English.</div>
""",
    unsafe_allow_html=True,
)
 
selected_sample = None
 
# -----------------------------------------------------------------------------
# Welcome State
# -----------------------------------------------------------------------------
if not st.session_state.messages:
    welcome_questions = [
        ("📈", "What was total revenue in December 2019?"),
        ("🏆", "What are the top 5 product categories by revenue?"),
        ("💰", "What's our average order value?"),
    ]
    cols = st.columns(3)
    for col, (icon, q) in zip(cols, welcome_questions):
        with col:
            st.markdown(
                f"""
<div class="welcome-card">
    <div style="font-size: 1.4rem;">{icon}</div>
    <div style="font-family: 'Inter', sans-serif; font-size: 0.92rem; color: #12173B; font-weight: 500;">
        {q}
    </div>
</div>
""",
                unsafe_allow_html=True,
            )
            if st.button("Ask this", key=f"welcome_{q}", use_container_width=True):
                selected_sample = q
    st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)
 
 
# -----------------------------------------------------------------------------
# Render Chat History
# -----------------------------------------------------------------------------
for idx, msg in enumerate(st.session_state.messages):
    role = msg["role"]
    with st.chat_message(role):
        if role == "user":
            st.write(msg["content"])
        else:
            resp = msg.get("response_data", {})
            status = resp.get("status", "error")
 
            if status == "ok":
                if resp.get("summary"):
                    st.markdown(
                        f'<div class="summary-box">💡 <b>Summary:</b><br>{resp["summary"]}</div>',
                        unsafe_allow_html=True,
                    )
 
                table_data = resp.get("table", [])
                if table_data:
                    df = pd.DataFrame(table_data)
                    st.dataframe(df, use_container_width=True)
 
                chart_config = resp.get("chart")
                if chart_config and table_data:
                    render_chart(chart_config, table_data)
 
                if resp.get("sql"):
                    with st.expander("🔍 View Generated SQL Query"):
                        st.code(resp["sql"], language="sql")
 
                # Feedback -- clearly separated, own labeled section
                st.markdown('<div class="feedback-panel">', unsafe_allow_html=True)
                if idx not in st.session_state.feedback_given:
                    st.markdown('<div class="feedback-label">Was this helpful?</div>', unsafe_allow_html=True)
                    fcol1, fcol2, fcol3 = st.columns([1, 1, 8])
                    with fcol1:
                        if st.button("👍 Yes", key=f"up_{idx}"):
                            question_text = st.session_state.messages[idx - 1]["content"] if idx > 0 else ""
                            log_feedback(question_text, resp.get("summary", ""), "up")
                            st.session_state.feedback_given[idx] = "up"
                            st.rerun()
                    with fcol2:
                        if st.button("👎 No", key=f"down_{idx}"):
                            question_text = st.session_state.messages[idx - 1]["content"] if idx > 0 else ""
                            log_feedback(question_text, resp.get("summary", ""), "down")
                            st.session_state.feedback_given[idx] = "down"
                            st.rerun()
                else:
                    vote = st.session_state.feedback_given[idx]
                    st.caption("✅ Thanks for confirming this was correct." if vote == "up" else "📝 Thanks -- flagged for review.")
                st.markdown("</div>", unsafe_allow_html=True)
 
            elif status == "needs_clarification":
                clarify_q = resp.get(
                    "clarification_question", "The query requires clarification."
                )
                st.markdown(
                    f'<div class="clarification-box">❓ <b>Clarification Needed:</b><br>{clarify_q}</div>',
                    unsafe_allow_html=True,
                )
                st.caption("Please type your answer below to continue.")
 
            elif status == "error":
                err_msg = resp.get(
                    "message", "An error occurred while processing your request."
                )
                st.error(f"⚠️ {err_msg}")
 
 
# -----------------------------------------------------------------------------
# Handle New User Input
# -----------------------------------------------------------------------------
user_input = st.chat_input(
    "Type your business question here (e.g., What were total sales in 2025?)..."
)
 
if selected_sample:
    user_input = selected_sample
 
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)
 
    payload = {
        "question": user_input,
        "conversation_id": st.session_state.conversation_id,
        "clarification_answer": None,
    }
 
    if st.session_state.pending_clarification and st.session_state.last_question:
        payload["question"] = st.session_state.last_question
        payload["clarification_answer"] = user_input
        st.session_state.pending_clarification = False
    else:
        st.session_state.last_question = user_input
 
    with st.chat_message("assistant"):
        with st.spinner("Analyzing question, generating SQL & querying BigQuery..."):
            try:
                api_response = requests.post(
                    backend_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=90,
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
                    "message": "Backend request timed out (90s limit). Please check server health or retry.",
                }
            except Exception as e:
                data = {
                    "status": "error",
                    "message": f"Could not connect to backend API: {str(e)}",
                }
 
        if data.get("status") == "needs_clarification":
            st.session_state.pending_clarification = True
 
        st.session_state.messages.append(
            {"role": "assistant", "content": "", "response_data": data}
        )
        st.rerun()