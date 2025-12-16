import streamlit as st
import sqlite3
from datetime import datetime, date
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ================= PAGE CONFIG =================
st.set_page_config(
    page_title="PO Monitoring Dashboard",
    page_icon="📊",
    layout="wide"
)

# ================= CSS (COMPACT UI) =================
st.markdown("""
<style>
.block-container {padding: 1.5rem 2rem;}
input, textarea {font-size: 0.85rem !important;}
label {font-size: 0.8rem !important;}
div[data-testid="stVerticalBlock"] > div {gap: 0.45rem;}
button {padding: 0.35rem 0.9rem !important; font-size: 0.85rem;}
</style>
""", unsafe_allow_html=True)

# ================= CONSTANT =================
DB_DIR = "data"
DB_PATH = f"{DB_DIR}/po_monitoring.db"
LOGO_PATH = "assets/cistech.png"

SALES_ENGINEERS = ["RSM", "TNU", "MFA", "HSA", "HTA"]
DIVISIONS = ["Condition Monitoring", "Industrial Cleaning"]

Path(DB_DIR).mkdir(exist_ok=True)

# ================= DATABASE =================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn = get_conn()
c = conn.cursor()

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
    nominal_po INTEGER,
    top TEXT,
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

def fetch_df():
    df = pd.read_sql("SELECT * FROM po", conn)

    if df.empty:
        return df

    df["po_received_date"] = pd.to_datetime(df["po_received_date"]).dt.date
    df["expected_eta"] = pd.to_datetime(df["expected_eta"]).dt.date
    df["actual_eta"] = pd.to_datetime(df["actual_eta"], errors="coerce").dt.date

    df["status"] = df.apply(
        lambda x: calculate_status(x["expected_eta"], x["actual_eta"]),
        axis=1
    )

    return df

def rupiah(val):
    return f"Rp {val:,.0f}".replace(",", ".")

# ================= HEADER =================
with st.container():
    if Path(LOGO_PATH).exists():
        st.image(LOGO_PATH, width=260)

    st.markdown("## PO Monitoring Dashboard")
    st.caption("ISO 9001:2015 – Order, Delivery & Performance Monitoring System")

with st.expander("📌 Status Definition"):
    st.markdown("""
**OPEN** – PO masih berjalan  
**COMPLETED** – PO selesai & wajib Actual ETA  
**OVERDUE** – Melewati Expected ETA
""")

tabs = st.tabs(["➕ Input PO", "📋 Data PO", "📊 Dashboard"])

# ================= TAB 1 : INPUT =================
with tabs[0]:
    st.subheader("➕ Input Purchase Order")

    with st.form("po_form", clear_on_submit=True):

        col1, col2 = st.columns(2)

        with col1:
            customer_name = st.text_input("Customer Name")
            sales_engineer = st.selectbox("Sales Engineer", SALES_ENGINEERS)
            division = st.selectbox("Division", DIVISIONS)
            quotation_no = st.text_input("Quotation Number")

        with col2:
            po_no = st.text_input("PO Number")
            po_received_date = st.date_input("PO Received Date")
            expected_eta = st.date_input("Expected ETA")
            actual_eta = st.date_input("Actual ETA (Completed)", value=None)

        st.markdown("##### Financial")
        col3, col4 = st.columns(2)

        with col3:
            nominal_po = st.number_input(
                "PO Value (Rp)", min_value=0, step=1_000_000
            )

        with col4:
            payment_progress = st.slider("Payment Progress (%)", 0, 100, 0)

        top = st.text_input("Term of Payment (TOP)")
        remarks = st.text_area("Remarks", height=70)

        submit = st.form_submit_button("💾 Save PO")

        if submit:
            status = calculate_status(expected_eta, actual_eta)
            c.execute("""
            INSERT INTO po VALUES (
                NULL,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
            """, (
                customer_name, sales_engineer, division,
                quotation_no, po_no,
                po_received_date.isoformat(),
                expected_eta.isoformat(),
                actual_eta.isoformat() if actual_eta else None,
                int(nominal_po), top, payment_progress,
                remarks, status, datetime.now().isoformat()
            ))
            conn.commit()
            st.success("✅ PO berhasil disimpan")

# ================= TAB 2 : DATA =================
with tabs[1]:
    st.subheader("📋 Data Purchase Order")

    df = fetch_df()

    if df.empty:
        st.info("Belum ada data PO")
    else:
        for _, row in df.iterrows():
            with st.expander(f"🏢 {row['customer_name']} | {row['po_no']} | {row['status']}"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write("Sales :", row["sales_engineer"])
                    st.write("Division :", row["division"])
                    st.write("Quotation :", row["quotation_no"])

                with col2:
                    st.write("PO Date :", row["po_received_date"])
                    st.write("Expected ETA :", row["expected_eta"])
                    st.write("Actual ETA :", row["actual_eta"] or "-")

                with col3:
                    st.write("PO Value :", rupiah(row["nominal_po"]))
                    st.progress(row["payment_progress"])
                    st.caption(f"Payment {row['payment_progress']}%")

                st.write("Remarks :", row["remarks"] or "-")

                col_edit, col_del = st.columns(2)

                with col_edit:
                    if st.button("✏️ Edit", key=f"e{row['id']}"):
                        st.session_state["edit_id"] = row["id"]

                with col_del:
                    if st.button("🗑 Delete", key=f"d{row['id']}"):
                        c.execute("DELETE FROM po WHERE id=?", (row["id"],))
                        conn.commit()
                        st.rerun()

# ================= TAB 3 : DASHBOARD =================
with tabs[2]:
    st.subheader("📊 KPI & Analytics")

    df = fetch_df()
    current_year = date.today().year

    # ===== FILTER =====
    colf1, colf2, colf3, colf4 = st.columns(4)

    with colf1:
        f_sales = st.selectbox("Sales Engineer", ["All"] + SALES_ENGINEERS)

    with colf2:
        f_status = st.selectbox("Status PO", ["All", "OPEN", "COMPLETED", "OVERDUE"])

    with colf3:
        f_month = st.selectbox("Month", ["All"] + list(range(1, 13)))

    with colf4:
        f_year = st.selectbox("Year", sorted(df["po_received_date"].apply(lambda x: x.year).unique()), index=0)

    # Apply filters
    if f_sales != "All":
        df = df[df["sales_engineer"] == f_sales]

    if f_status != "All":
        df = df[df["status"] == f_status]

    if f_month != "All":
        df = df[df["po_received_date"].apply(lambda x: x.month) == f_month]

    df = df[df["po_received_date"].apply(lambda x: x.year) == f_year]

    # ===== KPI =====
    open_val = df[df["status"] == "OPEN"]["nominal_po"].sum()
    comp_val = df[df["status"] == "COMPLETED"]["nominal_po"].sum()
    over_val = df[df["status"] == "OVERDUE"]["nominal_po"].sum()

    colk1, colk2, colk3 = st.columns(3)
    colk1.metric("Total OPEN PO Value", rupiah(open_val))
    colk2.metric("Total COMPLETED PO Value", rupiah(comp_val))
    colk3.metric("Total OVERDUE PO Value", rupiah(over_val))

    # ===== CHART =====
    st.markdown("### 📊 Revenue per Sales")
    rev = df[df["status"] == "COMPLETED"].groupby("sales_engineer")["nominal_po"].sum()

    if not rev.empty:
        fig, ax = plt.subplots()
        rev.plot(kind="bar", ax=ax)
        ax.set_ylabel("Revenue (Rp)")
        st.pyplot(fig)
    else:
        st.info("Belum ada revenue COMPLETED")
