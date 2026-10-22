import os
from dotenv import load_dotenv

# Ensure .env is loaded from the project root derived from this source file
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(ENV_PATH):
    load_dotenv(dotenv_path=ENV_PATH, override=False)

import pandas as pd
import streamlit as st

from core.api_client import (
    check_backend_health,
    get_api_base_url,
    get_dataset_metadata,
    query_dataset,
    upload_csv_file,
)

# Set page configuration
st.set_page_config(
    page_title="QueryPilot AI | Natural Language Data Analyst",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom modern CSS
st.markdown(
    """
    <style>
    /* Global layout & typography */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Header card */
    .hero-container {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(30, 41, 59, 0.7) 100%);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
    }
    .hero-title {
        font-size: 26px;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 14px;
        margin-top: 6px;
        margin-bottom: 0;
    }
    
    /* Metric pill */
    .metric-card {
        background: #1e293b;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 14px 18px;
        text-align: left;
    }
    .metric-label {
        color: #94a3b8;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .metric-value {
        color: #f8fafc;
        font-size: 20px;
        font-weight: 600;
    }
    
    /* Answer box */
    .answer-card {
        background: rgba(99, 102, 241, 0.08);
        border-left: 4px solid #6366f1;
        border-radius: 4px 8px 8px 4px;
        padding: 16px 20px;
        margin-top: 12px;
        margin-bottom: 16px;
    }
    .answer-title {
        color: #818cf8;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .answer-text {
        color: #f1f5f9;
        font-size: 16px;
        font-weight: 500;
        margin: 0;
    }
    
    /* Query history card */
    .history-card {
        background: #1e293b;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Session State
if "datasets" not in st.session_state:
    st.session_state.datasets = {}  # {dataset_id: metadata_dict}

if "active_dataset_id" not in st.session_state:
    st.session_state.active_dataset_id = None

if "history" not in st.session_state:
    st.session_state.history = {}  # {dataset_id: list_of_query_dicts}

api_base_url = get_api_base_url()
is_healthy, health_msg = check_backend_health(api_base_url)

# Top Bar / Hero
col_hero, col_status = st.columns([4, 1.2])
with col_hero:
    st.markdown(
        """
        <div class="hero-container">
            <h1 class="hero-title">⚡ QueryPilot AI</h1>
            <p class="hero-subtitle">Upload CSVs into isolated SQLite databases and query them in natural language powered by Google Gemini.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_status:
    if is_healthy:
        st.success(f"🟢 **API:** {health_msg}")
    else:
        st.error(f"🔴 **API:** {health_msg}")
    st.caption(f"Endpoint: `{api_base_url}`")

# --- SIDEBAR: Upload & Dataset Selector ---
with st.sidebar:
    st.subheader("📂 Datasets")
    
    # File Uploader
    uploaded_file = st.file_uploader(
        "Upload new CSV file",
        type=["csv"],
        help="Upload a CSV file up to 10 MB. QueryPilot will validate and create an isolated SQLite database.",
    )

    if uploaded_file is not None:
        upload_btn = st.button("🚀 Ingest Dataset", use_container_width=True)
        if upload_btn:
            with st.spinner("Validating and creating isolated SQLite dataset..."):
                file_bytes = uploaded_file.getvalue()
                success, data, err_msg = upload_csv_file(
                    file_bytes=file_bytes,
                    filename=uploaded_file.name,
                    base_url=api_base_url,
                )
                if success:
                    dataset_id = data["dataset_id"]
                    st.session_state.datasets[dataset_id] = data
                    st.session_state.active_dataset_id = dataset_id
                    if dataset_id not in st.session_state.history:
                        st.session_state.history[dataset_id] = []
                    st.success(f"Ingested '{data['filename']}' ({data['total_rows']:,} rows)!")
                    st.rerun()
                else:
                    st.error(err_msg or "Failed to upload file.")

    st.divider()

    # Dataset Selection
    if st.session_state.datasets:
        options = list(st.session_state.datasets.keys())
        labels = [
            f"{st.session_state.datasets[did]['filename']} ({st.session_state.datasets[did]['total_rows']} rows)"
            for did in options
        ]

        current_idx = 0
        if st.session_state.active_dataset_id in options:
            current_idx = options.index(st.session_state.active_dataset_id)

        selected_label = st.selectbox(
            "Select Active Dataset:",
            options=range(len(options)),
            format_func=lambda i: labels[i],
            index=current_idx,
        )
        st.session_state.active_dataset_id = options[selected_label]

        active_meta = st.session_state.datasets[st.session_state.active_dataset_id]

        # Dataset Quick Info
        st.markdown(f"**Dataset ID:** `{active_meta['dataset_id'][:12]}...`")
        st.markdown(f"**Table:** `{active_meta.get('table_name', 'uploaded_data')}`")
        
        # Column schema expander in sidebar
        with st.expander("📋 View Columns & Types"):
            for col in active_meta.get("columns", []):
                st.markdown(f"- **{col['name']}** `{col.get('sqlite_type', col.get('inferred_type'))}`")

        st.divider()
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.history[st.session_state.active_dataset_id] = []
            st.rerun()

    else:
        st.info("No datasets uploaded yet. Upload a CSV to get started!")

# --- MAIN WORKSPACE ---
if not st.session_state.active_dataset_id or st.session_state.active_dataset_id not in st.session_state.datasets:
    # Onboarding View
    st.markdown("### Welcome to QueryPilot AI!")
    st.write(
        """
        QueryPilot AI turns your raw CSV files into an interactive, natural-language SQL analysis dashboard:
        
        1. **Upload your dataset** using the sidebar on the left.
        2. **Automatic Validation**: The backend checks for header rows, uniqueness, formatting, and infers column types.
        3. **Isolated SQLite Store**: Each file is stored safely in its own dedicated SQLite database.
        4. **Ask Questions**: Ask questions in plain English. Google Gemini creates the SQL, SQLGlot verifies safety, and results appear instantly!
        """
    )
    st.info("👈 Upload a CSV file in the sidebar to begin.")

else:
    active_dataset = st.session_state.datasets[st.session_state.active_dataset_id]
    current_dataset_id = st.session_state.active_dataset_id

    # Overview Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Dataset File</div>
                <div class="metric-value">{active_dataset['filename']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Total Rows</div>
                <div class="metric-value">{active_dataset['total_rows']:,}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Columns</div>
                <div class="metric-value">{active_dataset['total_columns']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Target Table</div>
                <div class="metric-value">{active_dataset.get('table_name', 'uploaded_data')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    # Main Tabs
    tab_query, tab_preview, tab_history = st.tabs(["💬 Query Dataset", "👁️ Data Preview", "📜 History"])

    # TAB 1: Query Dataset
    with tab_query:
        st.subheader("Ask a question about your data")
        
        # Suggested questions chips
        col_chip1, col_chip2, col_chip3 = st.columns(3)
        sample_q = ""
        with col_chip1:
            if st.button("📊 Total rows count", use_container_width=True):
                sample_q = "How many total rows are in this dataset?"
        with col_chip2:
            first_col = active_dataset["columns"][0]["clean_name"] if active_dataset.get("columns") else "id"
            if st.button(f"🔝 Show top 5 records by {first_col}", use_container_width=True):
                sample_q = f"Show the first 5 records ordered by {first_col}"
        with col_chip3:
            if st.button("📋 Summarize all columns", use_container_width=True):
                sample_q = "Give me a summary of the top records in this table"

        # Question input form
        with st.form("query_form", clear_on_submit=False):
            question_input = st.text_input(
                "Enter your question in plain English:",
                value=sample_q,
                placeholder="e.g. Which product generated the highest revenue?",
            )
            submit_query = st.form_submit_button("⚡ Run Query", use_container_width=True)

        if submit_query:
            if not question_input or not question_input.strip():
                st.warning("Please enter a question before running the query.")
            else:
                with st.spinner("QueryPilot is analyzing schema & executing SQL with Gemini..."):
                    success, res_data, err_msg = query_dataset(
                        dataset_id=current_dataset_id,
                        question=question_input.strip(),
                        base_url=api_base_url,
                    )

                if success:
                    # Save to conversation history
                    if current_dataset_id not in st.session_state.history:
                        st.session_state.history[current_dataset_id] = []
                    
                    st.session_state.history[current_dataset_id].append({
                        "question": question_input.strip(),
                        "answer": res_data.get("answer", "Query executed successfully."),
                        "sql": res_data.get("sql", ""),
                        "columns": res_data.get("columns", []),
                        "rows": res_data.get("rows", []),
                        "row_count": res_data.get("row_count", 0),
                    })

                    # Display Answer
                    st.markdown(
                        f"""
                        <div class="answer-card">
                            <div class="answer-title">Answer</div>
                            <p class="answer-text">{res_data.get('answer', '')}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Display SQL
                    with st.expander("🔍 View Generated SQL", expanded=True):
                        st.code(res_data.get("sql", ""), language="sql")

                    # Display Results Table
                    cols = res_data.get("columns", [])
                    rows = res_data.get("rows", [])
                    row_count = res_data.get("row_count", len(rows))

                    st.markdown(f"**Results ({row_count} records):**")
                    if rows and cols:
                        df_result = pd.DataFrame(rows, columns=cols)
                        st.dataframe(df_result, use_container_width=True)
                    elif row_count == 0:
                        st.info("Query returned 0 matching records.")
                    else:
                        st.write("No tabular rows returned.")

                else:
                    st.error(f"❌ {err_msg or 'An error occurred during query execution.'}")

    # TAB 2: Data Preview
    with tab_preview:
        st.subheader("Data Preview (First 10 rows)")
        preview_records = active_dataset.get("preview_rows", [])
        if preview_records:
            df_preview = pd.DataFrame(preview_records)
            st.dataframe(df_preview, use_container_width=True)
        else:
            st.info("No preview rows available.")

        st.divider()
        st.subheader("Schema Details")
        cols_meta = active_dataset.get("columns", [])
        if cols_meta:
            schema_data = []
            for c in cols_meta:
                schema_data.append({
                    "Original Header": c.get("original_name", c.get("name")),
                    "SQL Column Name": c.get("clean_name", c.get("name")),
                    "Inferred Type": c.get("sqlite_type", c.get("inferred_type")),
                    "Sample Values": ", ".join(str(v) for v in c.get("sample_values", [])[:3]),
                })
            st.table(pd.DataFrame(schema_data))

    # TAB 3: History
    with tab_history:
        st.subheader("Conversation & Query History")
        hist = st.session_state.history.get(current_dataset_id, [])
        if not hist:
            st.info("No queries have been run on this dataset yet.")
        else:
            for i, item in enumerate(reversed(hist), 1):
                with st.expander(f"Q: {item['question']}", expanded=(i == 1)):
                    st.markdown(f"**Answer:** {item['answer']}")
                    st.code(item["sql"], language="sql")
                    if item.get("rows") and item.get("columns"):
                        df_hist = pd.DataFrame(item["rows"], columns=item["columns"])
                        st.dataframe(df_hist, use_container_width=True)
                    st.caption(f"{item.get('row_count', 0)} rows returned")
