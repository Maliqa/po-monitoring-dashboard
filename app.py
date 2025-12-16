import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime
from pathlib import Path
import matplotlib.pyplot as plt

# ================= CONFIG =================
st.set_page_config(
    page_title="PO Monitoring Dashboard",
    page_icon="📊",
    layout="wide"
)

DB_DIR = "data"
DB_PATH = f"{DB_DIR}/po_monitoring.db"
LOGO_PATH = "assets/cistech.png"

DIVISIONS = ["Industrial Cleaning", "Condition Monitoring"]
SALES_ENGINEERS = ["RSM", "TNU", "MFA", "HSA", "HTA"]

CURRENT_YEAR = date.today().year

# ================= UI STYLE =================
st.markdown("""
<style>
html, body { font-size: 14px; }
input, textarea { padding: 6px !important; }
.section-title { font-size: 18px; font-weight: 600; margin-bottom: 6px; }
.kpi-box {
    padding: 12px;
    border-radius: 8px;
    background: #111827;
    border: 1px solid #1f2937;
}
.po-card {
    padding: 12px;
    border-radius: 10px;
    border: 1px solid #1f2937;
    background: #0f172a;
    margin-bottom: 10px;
}
.muted { color: #9ca3af; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

# ================= DATABASE =================
Path(DB_DIR).mkdir(exist_ok=True)

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn = get_conn()
c = conn.cursor()

# === CREATE TABLE (SAFE) ===
c.execute("""
CREATE TABLE IF NOT EXISTS po (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT,
    sales_engineer TEXT,
    division TEXT,
    quotation_no TEXT,
    po_no TEXT,
    po_received_date TEXT,
    expected_eta TEXT,
    actual_eta TEXT,
    top TEXT,
    nominal_po REAL,
    payment_progress INTEGER,
    remarks TEXT,
    status TEXT,
    created_at TEXT
)
""")
conn.commit()

# ================= BUSINESS LOGIC =================
def calculate_status(expected_eta, actual_eta):
    today = date.today()
    if actual_eta:
        return "COMPLETED"
    if today > expected_eta:
        return "OVERDUE"
    return "OPEN"

def load_data():
    df = pd.read_sql("SELECT * FROM po ORDER BY created_at DESC", conn)
    if df.empty:
        df["year"] = []
        df["month"] = []
        return df

    df["po_received_date"] = pd.to_datetime(df["po_received_date"]).dt.date
    df["expected_eta"] = pd.to_datetime(df["expected_eta"]).dt.date
    df["actual_eta"] = pd.to_datetime(df["actual_eta"], errors="coerce").dt.date
    df["year"] = pd.to_datetime(df["po_received_date"]).dt.year
    df["month"] = pd.to_datetime(df["po_received_date"]).dt.month

    df["status"] = df.apply(
        lambda x: calculate_status(x["expected_eta"], x["actual_eta"]),
        axis=1
    )

    return df

# ================= HEADER =================
if Path(LOGO_PATH).exists():
    st.image(LOGO_PATH, width=300)

st.markdown("## PO Monitoring Dashboard")
st.caption("ISO 9001:2015 – Order, Delivery & Performance Monitoring System")

tabs = st.tabs(["➕ Input PO", "📋 Data PO", "📊 Dashboard"])

# ================= TAB 1: INPUT =================
with tabs[0]:
    st.markdown('<div class="section-title">➕ Input Purchase Order</div>', unsafe_allow_html=True)

    with st.form("input_po"):
        c1, c2, c3 = st.columns(3)

        with c1:
            customer_name = st.text_input("Customer Name")
            sales_engineer = st.selectbox("Sales Engineer", SALES_ENGINEERS)
            division = st.selectbox("Division", DIVISIONS)

        with c2:
            quotation_no = st.text_input("Quotation Number")
            po_no = st.text_input("PO Number")
            nominal_po = st.number_input("Nominal PO (Rp)", min_value=0.0, step=1_000_000.0)

        with c3:
            po_received_date = st.date_input("PO Received Date", value=date.today())
            expected_eta = st.date_input("Expected ETA")
            actual_eta = st.date_input("Actual ETA", value=None)

        top = st.text_input("Term of Payment (TOP)")
        payment_progress = st.slider("Payment Progress (%)", 0, 100, 0)
        remarks = st.text_area("Remarks", height=80)

        if st.form_submit_button("💾 Save PO"):
            status = calculate_status(expected_eta, actual_eta)

            c.execute("""
            INSERT INTO po (
                customer_name, sales_engineer, division,
                quotation_no, po_no, po_received_date,
                expected_eta, actual_eta, top,
                nominal_po, payment_progress,
                remarks, status, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                customer_name, sales_engineer, division,
                quotation_no, po_no, po_received_date.isoformat(),
                expected_eta.isoformat(),
                actual_eta.isoformat() if actual_eta else None,
                top, nominal_po, payment_progress,
                remarks, status, datetime.now().isoformat()
            ))
            conn.commit()
            st.success("✅ PO berhasil disimpan")
            st.rerun()

# ================= TAB 2: DATA =================
with tabs[1]:
    st.markdown('<div class="section-title">📋 Data Purchase Order</div>', unsafe_allow_html=True)

    df = load_data()

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        fsales = st.selectbox("Sales Engineer", ["All"] + SALES_ENGINEERS)
    with f2:
        fstatus = st.selectbox("Status", ["All", "OPEN", "COMPLETED", "OVERDUE"])
    with f3:
        fmonth = st.selectbox("Month", ["All"] + list(range(1, 13)))
    with f4:
        fyear = st.selectbox("Year", sorted(df["year"].unique()) if not df.empty else [CURRENT_YEAR],
                              index=0)

    if fsales != "All":
        df = df[df["sales_engineer"] == fsales]
    if fstatus != "All":
        df = df[df["status"] == fstatus]
    if fmonth != "All":
        df = df[df["month"] == fmonth]
    df = df[df["year"] == fyear]

    for _, row in df.iterrows():
        st.markdown(f"""
        <div class="po-card">
            <b>{row['customer_name']}</b><br>
            <span class="muted">
                PO: {row['po_no']} | {row['sales_engineer']} | {row['status']}
            </span><br>
            <b>Rp {row['nominal_po']:,.0f}</b>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("📄 Detail & Edit"):
            c1, c2 = st.columns(2)
            with c1:
                new_expected = st.date_input("Expected ETA", row["expected_eta"], key=f"e{row['id']}")
                new_actual = st.date_input("Actual ETA", row["actual_eta"], key=f"a{row['id']}")
            with c2:
                new_payment = st.slider("Payment %", 0, 100, row["payment_progress"], key=f"p{row['id']}")
                new_remarks = st.text_area("Remarks", row["remarks"], key=f"r{row['id']}")

            if st.button("💾 Update", key=f"u{row['id']}"):
                new_status = calculate_status(new_expected, new_actual)
                c.execute("""
                UPDATE po SET
                    expected_eta=?, actual_eta=?,
                    payment_progress=?, remarks=?, status=?
                WHERE id=?
                """, (
                    new_expected.isoformat(),
                    new_actual.isoformat() if new_actual else None,
                    new_payment, new_remarks, new_status, row["id"]
                ))
                conn.commit()
                st.rerun()

            if st.button("🗑 Delete", key=f"d{row['id']}"):
                c.execute("DELETE FROM po WHERE id=?", (row["id"],))
                conn.commit()
                st.rerun()

# ================= TAB 3: DASHBOARD =================
with tabs[2]:
    st.markdown('<div class="section-title">📊 KPI Summary</div>', unsafe_allow_html=True)

    df = load_data()
    df = df[df["year"] == CURRENT_YEAR]

    open_val = df[df["status"] == "OPEN"]["nominal_po"].sum()
    completed_val = df[df["status"] == "COMPLETED"]["nominal_po"].sum()
    overdue_val = df[df["status"] == "OVERDUE"]["nominal_po"].sum()

    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='kpi-box'><b>OPEN</b><br>Rp {open_val:,.0f}</div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='kpi-box'><b>COMPLETED</b><br>Rp {completed_val:,.0f}</div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='kpi-box'><b>OVERDUE</b><br>Rp {overdue_val:,.0f}</div>", unsafe_allow_html=True)

    st.markdown("### Revenue per Sales Engineer")
    fig, ax = plt.subplots()
    df.groupby("sales_engineer")["nominal_po"].sum().plot(kind="bar", ax=ax)
    st.pyplot(fig)