import html
import json
import uuid
from datetime import date, datetime, timedelta

import pandas as pd
import psycopg
import streamlit as st
from psycopg.rows import dict_row


# ==========================================================
# PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="Project Delivery Hub",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    DATABASE_URL = st.secrets["DATABASE_URL"]
except (KeyError, FileNotFoundError):
    st.error("DATABASE_URL is missing from .streamlit/secrets.toml.")
    st.stop()


# ==========================================================
# CONSTANTS
# ==========================================================

WORK_COLUMNS = [
    "ID", "Workstream", "Work Item", "Owner", "Team",
    "Start Date", "Due Date", "Status", "Progress (%)", "Weight (%)",
]

MILESTONE_COLUMNS = ["Milestone", "Due Date", "Owner", "Status"]
RAID_COLUMNS = ["Type", "Description", "Owner", "Priority", "Status", "Due Date"]
DATE_COLUMNS = ["Start Date", "Due Date"]
NUMERIC_COLUMNS = ["Progress (%)", "Weight (%)"]

RECORD_TYPES = {
    "work": ("work_items", WORK_COLUMNS),
    "milestones": ("milestones", MILESTONE_COLUMNS),
    "raid": ("raid", RAID_COLUMNS),
}

PROJECT_TYPES = [
    "Infrastructure", "Software", "Cloud", "Database",
    "Cybersecurity", "Network", "Digital Transformation", "Other",
]

WORK_STATUSES = ["Not Started", "In Progress", "Blocked", "Completed"]
MILESTONE_STATUSES = ["Not Started", "In Progress", "Delayed", "Completed"]
RAID_TYPES = ["Risk", "Assumption", "Issue", "Dependency"]
RAID_PRIORITIES = ["Low", "Medium", "High", "Critical"]
RAID_STATUSES = ["Open", "In Progress", "Resolved", "Closed"]

NAV_OPTIONS = ["Portfolio", "Project Workspace", "Reports", "Settings"]

NAV_TILES = [
    [
        ("Portfolio", "▦", "All projects"),
        ("Project Workspace", "▤", "Tasks & delivery"),
    ],
    [
        ("Reports", "▥", "Performance"),
        ("Settings", "⚙", "Configuration"),
    ],
]

TEMPLATES = {
    "Blank Project": [],
    "Infrastructure Modernisation": [
        ("Planning", "Project initiation and scope definition", 10),
        ("Assessment", "Current environment assessment", 15),
        ("Design", "Target architecture and solution design", 15),
        ("Preparation", "Environment readiness preparation", 15),
        ("Implementation", "Implementation and rollout", 25),
        ("Testing", "Technical and functional testing", 10),
        ("Handover", "Operational handover and documentation", 5),
        ("Closure", "Project closure and lessons learned", 5),
    ],
    "Software Deployment": [
        ("Planning", "Requirements and project planning", 10),
        ("Design", "Solution and technical design", 15),
        ("Development", "Development and configuration", 25),
        ("Testing", "Testing and defect resolution", 20),
        ("Release", "Deployment and release execution", 15),
        ("Handover", "Documentation and operational handover", 10),
        ("Closure", "Project closure", 5),
    ],
    "Cloud Migration": [
        ("Planning", "Scope and migration planning", 10),
        ("Assessment", "Cloud readiness assessment", 15),
        ("Design", "Cloud architecture design", 15),
        ("Preparation", "Cloud environment preparation", 15),
        ("Migration", "Workload migration", 25),
        ("Validation", "Post-migration validation", 10),
        ("Handover", "Operational handover", 5),
        ("Closure", "Project closure", 5),
    ],
}


# ==========================================================
# DESIGN
# ==========================================================

APP_CSS = """
<style>
:root {
    --bg: #080b0d;
    --surface: #111719;
    --surface-2: #182123;
    --surface-3: #202b2d;
    --border: #2b393b;
    --text: #f5f8f8;
    --muted: #a7b5b5;
    --teal: #20c7b5;
    --teal-deep: #087f78;
    --teal-soft: #123b39;
    --highlight: #a78bfa;
    --highlight-soft: #30264a;
}
.stApp {
    background: var(--bg);
    color: var(--text);
}
[data-testid="stAppViewContainer"] { background: var(--bg); }
[data-testid="stHeader"] {
    background: rgba(8,11,13,.96);
    border-bottom: 1px solid var(--border);
}
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}
h1, h2, h3, h4, h5, h6,
.stMarkdown, p, label, span, small, li {
    color: var(--text);
}
.stCaption, [data-testid="stCaptionContainer"] {
    color: var(--muted) !important;
}
.hero {
    background: linear-gradient(120deg, #101718 0%, #142b2b 100%);
    border: 1px solid #28514e;
    padding: 28px 30px;
    border-radius: 16px;
    color: var(--text);
    margin-bottom: 24px;
    box-shadow: 0 12px 32px rgba(0,0,0,.22);
}
.hero h1 { color: #ffffff !important; font-size: 31px; margin-bottom: 6px; }
.hero p { color: #b9d6d2 !important; margin-bottom: 0; }
.section-heading {
    font-size: 21px;
    font-weight: 750;
    color: #ffffff;
    margin-top: 15px;
    margin-bottom: 12px;
}
div[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 17px;
    border-radius: 13px;
    box-shadow: 0 4px 14px rgba(0,0,0,.18);
}
div[data-testid="stMetricLabel"],
div[data-testid="stMetricLabel"] * { color: var(--muted) !important; }
div[data-testid="stMetricValue"],
div[data-testid="stMetricValue"] * { color: #ffffff !important; }
div[data-testid="stMetricDelta"] { color: var(--teal) !important; }

div[data-testid="stForm"],
[data-testid="stExpander"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 13px;
}
div[data-testid="stForm"] { padding: 18px; }
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p { color: var(--text) !important; }
.project-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--teal);
    border-radius: 14px;
    padding: 18px;
    min-height: 150px;
}
.project-card h3 { color: #ffffff !important; }
.muted { color: var(--muted) !important; font-size: 13px; }

[data-testid="stSidebar"] {
    background: #0b1011;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] > div:first-child { background: #0b1011; }
[data-testid="stSidebar"] * { color: var(--text); }
.sidebar-brand {
    display: flex; align-items: center; gap: 11px;
    padding: 8px 2px 18px;
}
.sidebar-brand-icon {
    width: 38px; height: 38px; display: flex;
    align-items: center; justify-content: center;
    border-radius: 11px;
    background: linear-gradient(135deg, var(--teal), #087f78);
    color: #061211 !important;
    font-size: 23px; font-weight: 800;
}
.sidebar-brand-name { font-size: 14px; font-weight: 800; letter-spacing: 1.1px; }
.sidebar-brand-caption { color: var(--muted) !important; font-size: 11px; margin-top: 2px; }
.sidebar-section-label {
    color: #8fa5a3 !important; font-size: 10px; font-weight: 800;
    letter-spacing: 1.3px; margin: 8px 0 10px 2px;
}
[data-testid="stSidebar"] button {
    min-height: 67px; white-space: pre-wrap; text-align: left;
    line-height: 1.35; border-radius: 11px;
    font-size: 13px; font-weight: 650;
}
[data-testid="stSidebar"] button[kind="primary"],
.stButton button[kind="primary"],
.stFormSubmitButton button[kind="primary"] {
    background: var(--teal) !important;
    border: 1px solid var(--teal) !important;
    color: #041413 !important;
    font-weight: 750 !important;
}
[data-testid="stSidebar"] button[kind="secondary"],
.stButton button[kind="secondary"] {
    background: #172021 !important;
    border: 1px solid var(--border) !important;
    color: #f4f8f8 !important;
}
[data-testid="stSidebar"] button[kind="secondary"]:hover,
.stButton button[kind="secondary"]:hover {
    background: #20302f !important;
    border-color: var(--teal) !important;
    color: #ffffff !important;
}
.active-project-card {
    background: linear-gradient(145deg, #142221, #101819);
    border: 1px solid #28514e;
    border-radius: 12px;
    padding: 13px;
    margin-top: 10px;
}
.active-project-name { font-size: 13px; font-weight: 750; overflow-wrap: anywhere; color: #fff; }
.active-project-type { color: var(--muted) !important; font-size: 11px; margin-top: 5px; }
.project-progress-meta {
    display: flex; justify-content: space-between;
    color: #c3d0cf; font-size: 10px; margin-top: 14px; margin-bottom: 6px;
}
.project-progress-meta strong { color: var(--teal) !important; }
.project-progress-track { width: 100%; height: 6px; border-radius: 10px; background: #344342; overflow: hidden; }
.project-progress-fill { height: 100%; border-radius: 10px; background: linear-gradient(90deg, #087f78, var(--teal)); }

.stTextInput label, .stTextArea label, .stSelectbox label,
.stDateInput label, .stNumberInput label, .stMultiSelect label,
.stRadio label, .stCheckbox label, .stSlider label,
[data-testid="stWidgetLabel"] p {
    color: #eaf1f0 !important;
    font-weight: 600;
}
.stTextInput input, .stTextArea textarea,
.stNumberInput input,
[data-testid="stDateInput"] input {
    background: #11191a !important;
    color: #ffffff !important;
    border: 1px solid #405251 !important;
    border-radius: 9px !important;
    caret-color: var(--teal);
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {
    color: #91a19f !important;
}
.stTextInput input:focus, .stTextArea textarea:focus,
.stNumberInput input:focus, [data-testid="stDateInput"] input:focus {
    border-color: var(--teal) !important;
    box-shadow: 0 0 0 1px var(--teal) !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    background: #11191a !important;
    border-color: #405251 !important;
    color: #ffffff !important;
    border-radius: 9px !important;
}
[data-testid="stSelectbox"] *,
[data-testid="stMultiSelect"] * { color: #ffffff !important; }
[data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"] {
    background: #182123 !important;
    border: 1px solid var(--border) !important;
}
[role="option"] { color: #ffffff !important; }
[role="option"]:hover { background: #23413e !important; }
.stDateInput button, .stTimeInput button { color: var(--teal) !important; }

.stTabs [data-baseweb="tab-list"] {
    background: #11191a;
    border-bottom: 1px solid var(--border);
    gap: 5px;
}
.stTabs [data-baseweb="tab"] { color: #bdc9c8 !important; }
.stTabs [aria-selected="true"] {
    color: var(--teal) !important;
    border-bottom-color: var(--teal) !important;
}
.stDataFrame, [data-testid="stDataFrame"],
[data-testid="stTable"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
}
[data-testid="stDataEditor"] {
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
}
[data-testid="stProgress"] > div > div {
    background: var(--teal) !important;
}
.stAlert {
    background: #151f20;
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 10px;
}
[data-testid="stAlert"] p { color: #f2f7f6 !important; }
[data-testid="stAlert"][kind="info"] { border-left: 4px solid var(--teal); }
[data-testid="stAlert"][kind="warning"] { border-left: 4px solid var(--highlight); }
[data-testid="stAlert"][kind="success"] { border-left: 4px solid #55d6a4; }
[data-testid="stAlert"][kind="error"] { border-left: 4px solid #fb7185; }

button, [role="button"] { transition: all .16s ease-in-out; }
button:focus-visible, [role="button"]:focus-visible {
    outline: 2px solid var(--highlight) !important;
    outline-offset: 2px;
}
hr { border-color: var(--border) !important; }
a { color: var(--teal) !important; }
[data-testid="stDownloadButton"] button {
    background: var(--teal) !important;
    color: #041413 !important;
    border: 1px solid var(--teal) !important;
}
</style>
"""

st.markdown(APP_CSS, unsafe_allow_html=True)


# ==========================================================
# POSTGRESQL DATABASE
# ==========================================================

def get_connection():
    """Return a new PostgreSQL connection."""
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=15,
        prepare_threshold=None,
    )


@st.cache_resource(show_spinner="Connecting to PostgreSQL...")
def initialize_database():
    """Create the application tables and indexes if they do not exist."""

    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                project_type TEXT,
                objective TEXT,
                start_date DATE,
                end_date DATE,
                template TEXT,
                status TEXT DEFAULT 'Active',
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_records (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id)
                    ON DELETE CASCADE,
                record_type TEXT NOT NULL,
                record_key TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                payload JSONB NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_records
            ON project_records(project_id, record_type)
        """)

    return True


initialize_database()


# ==========================================================
# DATABASE HELPERS
# ==========================================================

def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def get_all_projects(include_archived=True):
    query = "SELECT * FROM projects"

    if not include_archived:
        query += " WHERE status = 'Active'"

    query += " ORDER BY updated_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query).fetchall()

    return [dict(row) for row in rows]


def create_project_record(project):
    now = now_iso()

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO projects (
                id, name, project_type, objective,
                start_date, end_date, template, status,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            project["id"],
            project["name"],
            project["type"],
            project["objective"],
            project["start_date"],
            project["end_date"],
            project["template"],
            "Active",
            now,
            now,
        ))

    st.cache_data.clear()


def update_project_status(project_id, status):
    with get_connection() as conn:
        conn.execute("""
            UPDATE projects
            SET status = %s, updated_at = %s
            WHERE id = %s
        """, (status, now_iso(), project_id))

    st.cache_data.clear()


def serialize_value(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if hasattr(value, "item"):
        return value.item()

    return value


def dataframe_to_records(dataframe):
    return [
        {
            key: serialize_value(value)
            for key, value in record.items()
        }
        for record in dataframe.to_dict(orient="records")
    ]


def save_project_records(project_id, record_type, dataframe):
    """Replace one record category atomically."""

    rows = []

    for index, record in enumerate(dataframe_to_records(dataframe)):
        record_key = str(
            record.get("ID")
            or record.get("Milestone")
            or record.get("Description")
            or uuid.uuid4()
        )

        rows.append((
            project_id,
            record_type,
            record_key,
            index,
            json.dumps(record),
        ))

    with get_connection() as conn:
        conn.execute("""
            DELETE FROM project_records
            WHERE project_id = %s AND record_type = %s
        """, (project_id, record_type))

        if rows:
            with conn.cursor() as cur:
                cur.executemany("""
                    INSERT INTO project_records (
                        project_id, record_type, record_key,
                        sort_order, payload
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                """, rows)

        conn.execute("""
            UPDATE projects SET updated_at = %s WHERE id = %s
        """, (now_iso(), project_id))

    st.cache_data.clear()


def records_to_dataframe(records, columns):
    dataframe = pd.DataFrame(records, columns=columns)

    for column in DATE_COLUMNS:
        if column in dataframe.columns:
            dataframe[column] = pd.to_datetime(
                dataframe[column], errors="coerce"
            )

    for column in NUMERIC_COLUMNS:
        if column in dataframe.columns:
            dataframe[column] = pd.to_numeric(
                dataframe[column], errors="coerce"
            )

    return dataframe


def load_all_project_records(project_id):
    grouped = {
        record_type: []
        for record_type in RECORD_TYPES
    }

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT record_type, payload
            FROM project_records
            WHERE project_id = %s
            ORDER BY sort_order
        """, (project_id,)).fetchall()

    for row in rows:
        if row["record_type"] in grouped:
            payload = row["payload"]

            if isinstance(payload, str):
                payload = json.loads(payload)

            grouped[row["record_type"]].append(payload)

    return {
        record_type: records_to_dataframe(
            grouped[record_type], columns
        )
        for record_type, (_, columns) in RECORD_TYPES.items()
    }


def load_project(project_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = %s",
            (project_id,),
        ).fetchone()

    if row is None:
        return None

    project = dict(row)

    if isinstance(project["start_date"], datetime):
        project["start_date"] = project["start_date"].date()

    if isinstance(project["end_date"], datetime):
        project["end_date"] = project["end_date"].date()

    return project


# ==========================================================
# SESSION STATE
# ==========================================================

def empty_state():
    return {
        "active_project_id": None,
        "project": None,
        "work_items": pd.DataFrame(columns=WORK_COLUMNS),
        "milestones": pd.DataFrame(columns=MILESTONE_COLUMNS),
        "raid": pd.DataFrame(columns=RAID_COLUMNS),
    }


for key, value in {
    **empty_state(),
    "page_request": None,
    "main_navigation": "Portfolio",
    "editor_version": 0,
    "flash": None,
}.items():
    st.session_state.setdefault(key, value)


def activate_project(project_id):
    project = load_project(project_id)

    if project is None:
        return

    records = load_all_project_records(project_id)

    st.session_state.active_project_id = project_id
    st.session_state.project = project

    for record_type, (state_key, _) in RECORD_TYPES.items():
        st.session_state[state_key] = records[record_type]


def clear_active_project():
    for key, value in empty_state().items():
        st.session_state[key] = value


# ==========================================================
# METRICS AND HEALTH CALCULATIONS
# ==========================================================

def count_overdue(dataframe, today):
    if dataframe.empty or "Due Date" not in dataframe.columns:
        return 0

    due_dates = pd.to_datetime(
        dataframe["Due Date"], errors="coerce"
    )

    return int((
        (due_dates < today)
        & (dataframe["Status"] != "Completed")
    ).sum())


def weighted_progress(dataframe):
    progress = pd.to_numeric(
        dataframe["Progress (%)"], errors="coerce"
    ).fillna(0).clip(0, 100)

    weights = pd.to_numeric(
        dataframe["Weight (%)"], errors="coerce"
    ).fillna(0).clip(0, 100)

    total_weight = weights.sum()

    if total_weight <= 0:
        return 0.0

    return float(
        (progress * weights).sum() / total_weight
    )


@st.cache_data(show_spinner=False)
def _compute_metrics(project_id, updated_at, today_iso):
    records = load_all_project_records(project_id)

    work = records["work"]
    milestones = records["milestones"]
    raid = records["raid"]

    today = pd.Timestamp(today_iso)

    if work.empty:
        total_items = 0
        completed_items = 0
        overdue_work = 0
        overall_progress = 0.0
    else:
        total_items = len(work)
        completed_items = int(
            (work["Status"] == "Completed").sum()
        )
        overall_progress = weighted_progress(work)
        overdue_work = count_overdue(work, today)

    open_risks = 0

    if not raid.empty:
        open_risks = int((
            (raid["Type"] == "Risk")
            & (~raid["Status"].isin(["Resolved", "Closed"]))
        ).sum())

    return {
        "total_items": total_items,
        "completed_items": completed_items,
        "progress": overall_progress,
        "overdue_work": overdue_work,
        "overdue_milestones": count_overdue(milestones, today),
        "open_risks": open_risks,
        "milestone_count": len(milestones),
    }


def get_project_metrics(project):
    return _compute_metrics(
        project["id"],
        str(project.get("updated_at")),
        date.today().isoformat(),
    )


# ==========================================================
# PROJECT CREATION
# ==========================================================

def new_work_id():
    return f"WI-{uuid.uuid4().hex[:8].upper()}"


def create_new_project(
    name, project_type, objective, start_date, duration, template_name
):
    end_date = start_date + timedelta(weeks=int(duration))
    project_id = str(uuid.uuid4())

    create_project_record({
        "id": project_id,
        "name": name.strip(),
        "type": project_type,
        "objective": objective,
        "start_date": start_date,
        "end_date": end_date,
        "template": template_name,
    })

    work_df = pd.DataFrame([
        {
            "ID": new_work_id(),
            "Workstream": workstream,
            "Work Item": description,
            "Owner": "Unassigned",
            "Team": "Unassigned",
            "Start Date": start_date,
            "Due Date": end_date,
            "Status": "Not Started",
            "Progress (%)": 0,
            "Weight (%)": weight,
        }
        for workstream, description, weight in TEMPLATES[template_name]
    ], columns=WORK_COLUMNS)

    milestones_df = pd.DataFrame([
        {
            "Milestone": "Project Kick-off",
            "Due Date": start_date,
            "Owner": "Project Manager",
            "Status": "Not Started",
        },
        {
            "Milestone": "Project Completion",
            "Due Date": end_date,
            "Owner": "Project Manager",
            "Status": "Not Started",
        },
    ], columns=MILESTONE_COLUMNS)

    save_project_records(project_id, "work", work_df)
    save_project_records(project_id, "milestones", milestones_df)
    save_project_records(
        project_id, "raid", pd.DataFrame(columns=RAID_COLUMNS)
    )

    activate_project(project_id)


# ==========================================================
# UI HELPERS
# ==========================================================

def esc(value):
    return html.escape(str(value)) if value is not None else ""


def ensure_columns(dataframe, columns):
    dataframe = dataframe.copy()

    for column in columns:
        if column not in dataframe.columns:
            dataframe[column] = None

    return dataframe[columns].copy()


def prepare_editor_dataframe(dataframe, date_columns):
    """
    Convert date columns to pandas datetime dtype before passing
    the DataFrame to Streamlit's DateColumn editor.
    """
    dataframe = dataframe.copy()

    for column in date_columns:
        if column in dataframe.columns:
            dataframe[column] = pd.to_datetime(
                dataframe[column],
                errors="coerce",
            )

    return dataframe


def editor_key(prefix, project_id):
    return (
        f"{prefix}_{project_id}_"
        f"{st.session_state.editor_version}"
    )


def finish_save(message):
    """Bump the editor version and show the message after the rerun."""
    st.session_state.editor_version += 1
    st.session_state.flash = message
    st.rerun()


# ==========================================================
# SIDEBAR
# ==========================================================

def render_sidebar(projects):
    sidebar = st.sidebar

    sidebar.markdown("""
        <div class="sidebar-brand">
            <div class="sidebar-brand-icon">▦</div>
            <div>
                <div class="sidebar-brand-name">PROJECT HUB</div>
                <div class="sidebar-brand-caption">Delivery workspace</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if st.session_state.page_request in NAV_OPTIONS:
        st.session_state.main_navigation = st.session_state.page_request
        st.session_state.page_request = None

    sidebar.markdown(
        '<div class="sidebar-section-label">WORKSPACE</div>',
        unsafe_allow_html=True,
    )

    for nav_row in NAV_TILES:
        nav_cols = sidebar.columns(2, gap="small")

        for column, (page, glyph, subtitle) in zip(nav_cols, nav_row):
            with column:
                selected = st.session_state.main_navigation == page

                if st.button(
                    f"{glyph}  {page}",
                    key=f"nav_tile_{page.lower().replace(' ', '_')}",
                    type="primary" if selected else "secondary",
                    use_container_width=True,
                    help=subtitle,
                ):
                    st.session_state.main_navigation = page
                    st.rerun()

    sidebar.divider()

    sidebar.markdown(
        '<div class="sidebar-section-label">ACTIVE PROJECT</div>',
        unsafe_allow_html=True,
    )

    if projects:
        project_ids = [p["id"] for p in projects]

        labels = {
            p["id"]: f'{p["name"]} · {p["status"]}'
            for p in projects
        }

        current_index = 0

        if st.session_state.active_project_id in project_ids:
            current_index = project_ids.index(
                st.session_state.active_project_id
            )

        selected_id = sidebar.selectbox(
            "Choose project",
            project_ids,
            index=current_index,
            format_func=lambda x: labels.get(x, x),
            label_visibility="collapsed",
        )

        if selected_id != st.session_state.active_project_id:
            activate_project(selected_id)
            st.rerun()

        active_project = next(
            p for p in projects if p["id"] == selected_id
        )

        progress_value = max(
            0,
            min(100, get_project_metrics(active_project)["progress"]),
        )

        sidebar.markdown(f"""
            <div class="active-project-card">
                <div class="active-project-name">
                    {esc(active_project["name"])}
                </div>
                <div class="active-project-type">
                    {esc(active_project["project_type"])}
                    · {esc(active_project["status"])}
                </div>
                <div class="project-progress-meta">
                    <span>Delivery progress</span>
                    <strong>{progress_value:.0f}%</strong>
                </div>
                <div class="project-progress-track">
                    <div class="project-progress-fill"
                         style="width:{progress_value}%"></div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    else:
        sidebar.info("No projects created yet.")

    render_create_project_form()


def render_create_project_form():
    with st.sidebar.expander("＋ Create a project", expanded=False):
        with st.form("create_project_form", clear_on_submit=True):
            project_name = st.text_input("Project name")
            project_type = st.selectbox("Project type", PROJECT_TYPES)
            template_name = st.selectbox(
                "Starting template", list(TEMPLATES)
            )
            objective = st.text_area("Project objective")
            start_date = st.date_input("Start date", value=date.today())

            duration = st.number_input(
                "Duration (weeks)",
                min_value=1,
                max_value=260,
                value=12,
            )

            submitted = st.form_submit_button(
                "Create project",
                use_container_width=True,
            )

        if submitted:
            if not project_name.strip():
                st.error("Enter a project name.")
            else:
                create_new_project(
                    project_name,
                    project_type,
                    objective,
                    start_date,
                    duration,
                    template_name,
                )

                st.session_state.page_request = "Project Workspace"
                st.session_state.flash = "Project created successfully."
                st.rerun()


# ==========================================================
# COMMON HEADER
# ==========================================================

def render_header():
    st.markdown("""
        <div class="hero">
            <h1>Project Delivery Hub</h1>
            <p>Plan with clarity. Execute with control. Deliver with confidence.</p>
        </div>
    """, unsafe_allow_html=True)


def render_flash():
    """Show a one-off message left by an action that triggered a rerun."""
    message = st.session_state.get("flash")

    if message:
        st.success(message)
        st.session_state.flash = None


# ==========================================================
# PORTFOLIO
# ==========================================================

def render_portfolio(all_projects):
    st.markdown(
        '<div class="section-heading">Portfolio overview</div>',
        unsafe_allow_html=True,
    )

    metrics_by_id = {
        p["id"]: get_project_metrics(p)
        for p in all_projects
    }

    active_projects = [
        p for p in all_projects if p["status"] == "Active"
    ]

    archived_projects = [
        p for p in all_projects if p["status"] == "Archived"
    ]

    total_overdue = sum(
        metrics_by_id[p["id"]]["overdue_work"]
        + metrics_by_id[p["id"]]["overdue_milestones"]
        for p in active_projects
    )

    total_risks = sum(
        metrics_by_id[p["id"]]["open_risks"]
        for p in active_projects
    )

    m1, m2, m3, m4 = st.columns(4)

    m1.metric("Total projects", len(all_projects))
    m2.metric("Active projects", len(active_projects))
    m3.metric("Overdue items", total_overdue)
    m4.metric("Open risks", total_risks)

    st.divider()

    left, right = st.columns([3, 1])

    with left:
        st.subheader("Your projects")

    with right:
        portfolio_filter = st.selectbox(
            "Filter", ["All", "Active", "Archived"]
        )

    filtered_projects = {
        "All": all_projects,
        "Active": active_projects,
        "Archived": archived_projects,
    }[portfolio_filter]

    if not filtered_projects:
        st.info(
            "No projects found. Create your first project from the sidebar."
        )

    for start in range(0, len(filtered_projects), 2):
        cols = st.columns(2)

        for column, project_item in zip(
            cols, filtered_projects[start:start + 2]
        ):
            metrics = metrics_by_id[project_item["id"]]

            objective_html = (
                esc(project_item["objective"]).replace("\n", "<br>")
                or "No objective provided."
            )

            with column:
                st.markdown(f"""
                    <div class="project-card">
                        <h3>{esc(project_item['name'])}</h3>
                        <p class="muted">
                            {esc(project_item['project_type'])}
                            · {esc(project_item['status'])}
                        </p>
                        <p>{objective_html}</p>
                    </div>
                """, unsafe_allow_html=True)

                st.progress(min(metrics["progress"] / 100, 1.0))

                a, b, c = st.columns(3)

                a.metric("Progress", f"{metrics['progress']:.0f}%")
                b.metric("Overdue", metrics["overdue_work"])
                c.metric("Open risks", metrics["open_risks"])

                if st.button(
                    "Open project",
                    key=f"open_{project_item['id']}",
                    use_container_width=True,
                ):
                    activate_project(project_item["id"])
                    st.session_state.page_request = "Project Workspace"
                    st.rerun()

    if all_projects:
        st.divider()
        st.subheader("Portfolio register")

        st.dataframe(
            pd.DataFrame([
                {
                    "Project": p["name"],
                    "Type": p["project_type"],
                    "Start date": p["start_date"],
                    "Target completion": p["end_date"],
                    "Status": p["status"],
                }
                for p in filtered_projects
            ]),
            use_container_width=True,
            hide_index=True,
        )


# ==========================================================
# WORKSPACE OVERVIEW
# ==========================================================

def render_overview_tab(metrics):
    st.subheader("Delivery overview")

    work = st.session_state.work_items.copy()

    if work.empty:
        st.info("No work items have been created.")
    else:
        for column in ["Progress (%)", "Weight (%)"]:
            work[column] = pd.to_numeric(
                work[column], errors="coerce"
            ).fillna(0)

        stream_rows = []

        for stream, group in work.groupby(
            "Workstream", dropna=False
        ):
            weight_total = group["Weight (%)"].sum()

            stream_progress = (
                (group["Progress (%)"] * group["Weight (%)"]).sum()
                / weight_total
                if weight_total > 0 else 0
            )

            stream_rows.append({
                "Workstream": stream,
                "Items": len(group),
                "Progress": round(stream_progress, 1),
            })

        st.dataframe(
            pd.DataFrame(stream_rows),
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Work status distribution")

        st.bar_chart(
            work["Status"].fillna("Unassigned").value_counts()
        )

    st.subheader("Delivery alerts")

    alerts = []

    if metrics["overdue_work"]:
        alerts.append(
            f'{metrics["overdue_work"]} work items are overdue.'
        )

    if metrics["overdue_milestones"]:
        alerts.append(
            f'{metrics["overdue_milestones"]} milestones are overdue.'
        )

    if metrics["open_risks"]:
        alerts.append(
            f'{metrics["open_risks"]} risks remain open.'
        )

    if alerts:
        for alert in alerts:
            st.warning(alert)
    else:
        st.success(
            "No overdue work or open risks detected by the current checks."
        )

    st.caption(
        "These indicators are rule-based portfolio checks, "
        "not predictive project-health assessments."
    )


# ==========================================================
# WORK MANAGEMENT
# ==========================================================

def render_work_tab(project):
    st.subheader("Work item register")

    work_for_editor = prepare_editor_dataframe(
        st.session_state.work_items,
        ["Start Date", "Due Date"],
    )

    edited_work = st.data_editor(
        work_for_editor,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        disabled=["ID"],
        key=editor_key("work_editor", project["id"]),
        column_config={
            "Start Date": st.column_config.DateColumn("Start date"),
            "Due Date": st.column_config.DateColumn("Due date"),
            "Status": st.column_config.SelectboxColumn(
                "Status", options=WORK_STATUSES
            ),
            "Progress (%)": st.column_config.NumberColumn(
                "Progress (%)", min_value=0, max_value=100, step=5
            ),
            "Weight (%)": st.column_config.NumberColumn(
                "Weight (%)", min_value=0, max_value=100, step=5
            ),
        },
    )

    if not st.button(
        "Save work items",
        key=f"save_work_{project['id']}",
        type="primary",
    ):
        return

    edited_work = ensure_columns(
        edited_work, WORK_COLUMNS
    ).dropna(how="all").reset_index(drop=True)

    for column in ["Progress (%)", "Weight (%)"]:
        edited_work[column] = pd.to_numeric(
            edited_work[column], errors="coerce"
        ).fillna(0).clip(0, 100)

    if edited_work["Weight (%)"].sum() > 100:
        st.error("Total work-item weight cannot exceed 100%.")
        return

    edited_work["Status"] = edited_work["Status"].fillna("Not Started")
    edited_work.loc[
        edited_work["Status"] == "Completed", "Progress (%)"
    ] = 100

    start = pd.to_datetime(
        edited_work["Start Date"], errors="coerce"
    )
    due = pd.to_datetime(
        edited_work["Due Date"], errors="coerce"
    )

    if (due < start).any():
        st.error("Due date cannot be before start date.")
        return

    missing_id = (
        edited_work["ID"].isna()
        | (edited_work["ID"].astype(str).str.strip() == "")
    )

    if missing_id.any():
        edited_work.loc[missing_id, "ID"] = [
            new_work_id()
            for _ in range(int(missing_id.sum()))
        ]

    if edited_work["ID"].duplicated().any():
        st.error("Work item IDs must be unique.")
        return

    st.session_state.work_items = edited_work.copy()

    save_project_records(
        project["id"], "work", edited_work
    )

    finish_save("Work items saved successfully.")


# ==========================================================
# MILESTONE AND RAID REGISTERS
# ==========================================================

def render_register_tab(
    project,
    *,
    title,
    caption,
    record_type,
    state_key,
    columns,
    column_config,
    editor_prefix,
    button_label,
    success_message,
    button_key,
):
    st.subheader(title)

    if caption:
        st.caption(caption)

    date_columns = [
        column for column in columns
        if column in DATE_COLUMNS
    ]

    data_for_editor = prepare_editor_dataframe(
        st.session_state[state_key],
        date_columns,
    )

    edited = st.data_editor(
        data_for_editor,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=editor_key(editor_prefix, project["id"]),
        column_config=column_config,
    )

    if st.button(
        button_label,
        key=f"{button_key}_{project['id']}",
        type="primary",
    ):
        cleaned = ensure_columns(
            edited, columns
        ).dropna(how="all").reset_index(drop=True)

        st.session_state[state_key] = cleaned

        save_project_records(
            project["id"], record_type, cleaned
        )

        finish_save(success_message)


# ==========================================================
# PROJECT WORKSPACE
# ==========================================================

def render_workspace():
    project = st.session_state.project

    if project is None:
        st.info(
            "Select a project from the sidebar or create a new project."
        )
        return

    st.subheader(project["name"])

    st.caption(
        f"{project['project_type']} · "
        f"{project['status']} · "
        f"Template: {project['template']}"
    )

    if project["objective"]:
        st.write("**Objective:**", project["objective"])

    metrics = get_project_metrics(project)

    a, b, c, d = st.columns(4)

    a.metric("Progress", f"{metrics['progress']:.1f}%")

    b.metric(
        "Work completed",
        f"{metrics['completed_items']}/{metrics['total_items']}",
    )

    c.metric("Overdue work", metrics["overdue_work"])
    d.metric("Open risks", metrics["open_risks"])

    st.progress(min(metrics["progress"] / 100, 1.0))

    st.caption(
        f"Start: {project['start_date']} | "
        f"Target completion: {project['end_date']}"
    )

    if project["status"] == "Active":
        if st.button("Archive project"):
            update_project_status(project["id"], "Archived")
            activate_project(project["id"])
            st.session_state.flash = (
                "Project archived. Its records are retained."
            )
            st.rerun()

    elif st.button("Restore project"):
        update_project_status(project["id"], "Active")
        activate_project(project["id"])
        st.session_state.flash = "Project restored."
        st.rerun()

    st.divider()

    tab_overview, tab_work, tab_milestones, tab_raid = st.tabs([
        "Overview",
        "Work management",
        "Milestones",
        "RAID register",
    ])

    with tab_overview:
        render_overview_tab(metrics)

    with tab_work:
        render_work_tab(project)

    with tab_milestones:
        render_register_tab(
            project,
            title="Project milestones",
            caption=None,
            record_type="milestones",
            state_key="milestones",
            columns=MILESTONE_COLUMNS,
            column_config={
                "Due Date": st.column_config.DateColumn("Due date"),
                "Status": st.column_config.SelectboxColumn(
                    "Status", options=MILESTONE_STATUSES
                ),
            },
            editor_prefix="milestone_editor",
            button_label="Save milestones",
            success_message="Milestones saved successfully.",
            button_key="save_milestones",
        )

    with tab_raid:
        render_register_tab(
            project,
            title="RAID register",
            caption="Manage Risks, Assumptions, Issues and Dependencies.",
            record_type="raid",
            state_key="raid",
            columns=RAID_COLUMNS,
            column_config={
                "Type": st.column_config.SelectboxColumn(
                    "Type", options=RAID_TYPES
                ),
                "Priority": st.column_config.SelectboxColumn(
                    "Priority", options=RAID_PRIORITIES
                ),
                "Status": st.column_config.SelectboxColumn(
                    "Status", options=RAID_STATUSES
                ),
                "Due Date": st.column_config.DateColumn("Due date"),
            },
            editor_prefix="raid_editor",
            button_label="Save RAID register",
            success_message="RAID register saved successfully.",
            button_key="save_raid",
        )


# ==========================================================
# REPORTS
# ==========================================================

def render_reports(all_projects):
    st.subheader("Portfolio reports")

    if not all_projects:
        st.info("Create a project before generating reports.")
        return

    report_rows = []

    for project_item in all_projects:
        metrics = get_project_metrics(project_item)

        report_rows.append({
            "Project": project_item["name"],
            "Type": project_item["project_type"],
            "Status": project_item["status"],
            "Start date": project_item["start_date"],
            "Target completion": project_item["end_date"],
            "Progress (%)": round(metrics["progress"], 1),
            "Total work items": metrics["total_items"],
            "Completed work items": metrics["completed_items"],
            "Overdue work items": metrics["overdue_work"],
            "Overdue milestones": metrics["overdue_milestones"],
            "Open risks": metrics["open_risks"],
        })

    report_df = pd.DataFrame(report_rows)

    st.dataframe(
        report_df,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Download portfolio report (CSV)",
        data=report_df.to_csv(index=False).encode("utf-8"),
        file_name="project_delivery_hub_report.csv",
        mime="text/csv",
        type="primary",
    )

    st.caption(
        "This report is generated from your Supabase PostgreSQL database."
    )


# ==========================================================
# SETTINGS
# ==========================================================

def render_settings():
    st.subheader("Workspace settings")

    st.markdown("### Application information")

    st.write("**Application:** Project Delivery Hub")
    st.write("**Version:** PostgreSQL cloud prototype")
    st.write("**Storage:** Supabase PostgreSQL")

    st.divider()

    st.markdown("### Available project templates")

    for name, items in TEMPLATES.items():
        with st.expander(name):
            if items:
                st.dataframe(
                    pd.DataFrame(
                        items,
                        columns=[
                            "Workstream",
                            "Work item",
                            "Weight (%)",
                        ],
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption("Starts with an empty work register.")

    st.divider()

    st.markdown("### Data and storage")

    st.info(
        "New project data is stored in your Supabase PostgreSQL database. "
        "Your previous SQLite database is not used by this application."
    )

    st.caption(
        "This prototype does not yet include multi-user authentication, "
        "role-based access control or automated backups."
    )


# ==========================================================
# MAIN APPLICATION
# ==========================================================

def main():
    projects = get_all_projects()

    render_sidebar(projects)
    render_header()
    render_flash()

    page = st.session_state.main_navigation

    if page == "Portfolio":
        render_portfolio(projects)

    elif page == "Project Workspace":
        render_workspace()

    elif page == "Reports":
        render_reports(projects)

    elif page == "Settings":
        render_settings()

    st.divider()

    st.caption(
        "Project Delivery Hub | PostgreSQL cloud prototype"
    )


try:
    main()

except psycopg.Error as error:
    st.error(
        "A PostgreSQL database operation failed. "
        "Please check your Supabase connection and database configuration."
    )
    st.exception(error)

except Exception as error:
    st.error("The application encountered an unexpected error.")
    st.exception(error)