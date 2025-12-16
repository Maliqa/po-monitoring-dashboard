import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from pathlib import Path
import matplotlib.pyplot as plt

# ================= CONFIG =================
st.set_page_config(
    page_title="PO Monitoring Dashboard",
    page_icon="📊",
    layout="wide"
)

DB_PATH = "data/po_monitoring.db"
LOGO_PATH = "assets/cistech.png"

DIVISIONS = ["Industrial Cleaning", "Condition Monitoring"]
SALES_ENGINEERS = ["RSM", "TNU", "MFA", "HSA", "HTA"]
STATUS_LIST = ["OPEN", "COMPLETED", "OVERDUE"]

Path("data").mkdir(exist_ok=True)

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
    top TEXT,
    nominal_po INTEGER,
    payment_progress INTEGER,
    remarks TEXT,
    status TEXT,
    created_at TEXT
)
""")
conn.commit()

# ================= HELPERS =================
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

    # ⬇️ JANGAN pakai .dt.date
    df["po_received_date"] = pd.to_datetime(df["po_received_date"])
    df["expected_eta"] = pd.to_datetime(df["expected_eta"])
    df["actual_eta"] = pd.to_datetime(df["actual_eta"], errors="coerce")
    df["created_at"] = pd.to_datetime(df["created_at"])

    # Aman pakai .dt sekarang
    df["year"] = df["po_received_date"].dt.year
    df["month"] = df["po_received_date"].dt.month

    df["status"] = df.apply(
        lambda x: calculate_status(
            x["expected_eta"].date(),
            x["actual_eta"].date() if pd.notna(x["actual_eta"]) else None
        ),
        axis=1
    )

    return df

def rupiah(val):
    return f"Rp {int(val):,}".replace(",", ".")

# ================= HEADER =================
if Path(LOGO_PATH).exists():
    st.image(LOGO_PATH, width=260)

st.title("PO Monitoring Dashboard")
st.caption("ISO 9001:2015 – Order, Delivery & Performance Monitoring System")

with st.expander("📌 Status Definition"):
    st.markdown("""
- **OPEN** → PO masih berjalan  
- **COMPLETED** → PO selesai (Actual ETA wajib)  
- **OVERDUE** → Lewat Expected ETA
""")

tabs = st.tabs(["➕ Input PO", "📋 Data PO", "📊 Dashboard"])

# ================= TAB 1 : INPUT =================
with tabs[0]:
    st.subheader("➕ Input Purchase Order")

    with st.form("po_form"):
        col1, col2 = st.columns(2)

        with col1:
            customer_name = st.text_input("Customer Name")
            sales_engineer = st.selectbox("Sales Engineer", SALES_ENGINEERS)
            division = st.selectbox("Division", DIVISIONS)
            quotation_no = st.text_input("Quotation Number")
            po_no = st.text_input("PO Number")

        with col2:
            po_received_date = st.date_input("PO Received Date")
            expected_eta = st.date_input("Expected ETA")
            actual_eta = st.date_input("Actual ETA", value=None)
            top = st.text_input("Term of Payment (TOP)")
            nominal_po = st.number_input("Nominal PO", min_value=0, step=1_000_000)

        payment_progress = st.slider("Payment Progress (%)", 0, 100, 0)
        remarks = st.text_area("Remarks")

        if st.form_submit_button("💾 Save PO"):
            status = calculate_status(expected_eta, actual_eta)

            c.execute("""
                INSERT INTO po (
                    customer_name,
                    sales_engineer,
                    division,
                    quotation_no,
                    po_no,
                    po_received_date,
                    expected_eta,
                    actual_eta,
                    top,
                    nominal_po,
                    payment_progress,
                    remarks,
                    status,
                    created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                customer_name,
                sales_engineer,
                division,
                quotation_no,
                po_no,
                po_received_date.isoformat(),
                expected_eta.isoformat(),
                actual_eta.isoformat() if actual_eta else None,
                top,
                nominal_po,
                payment_progress,
                remarks,
                status,
                datetime.now().isoformat()
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
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            f_sales = st.selectbox("Sales Engineer", ["All"] + SALES_ENGINEERS)
        with f2:
            f_status = st.selectbox("Status PO", ["All"] + STATUS_LIST)
        with f3:
            f_month = st.selectbox("Month", ["All"] + list(range(1, 13)))
        with f4:
            f_year = st.selectbox("Year", sorted(df["year"].unique()), index=len(df["year"].unique()) - 1)

        if f_sales != "All":
            df = df[df["sales_engineer"] == f_sales]
        if f_status != "All":
            df = df[df["status"] == f_status]
        if f_month != "All":
            df = df[df["month"] == f_month]
        df = df[df["year"] == f_year]

        for _, r in df.iterrows():
            with st.container(border=True):
                st.markdown(f"### 🏢 {r['customer_name']}")
                st.caption(f"PO No: {r['po_no']} | Status: {r['status']}")

                colA, colB = st.columns(2)
                with colA:
                    st.markdown(f"""
- **Division:** {r['division']}
- **Quotation No:** {r['quotation_no']}
- **PO Received Date:** {r['po_received_date']}
- **Expected ETA:** {r['expected_eta']}
- **Actual ETA:** {r['actual_eta'] or "-"}
""")
                with colB:
                    st.markdown(f"""
- **TOP:** {r['top']}
- **Nominal PO:** {rupiah(r['nominal_po'])}
- **Payment Progress:** {r['payment_progress']}%
- **Remarks:** {r['remarks'] or "-"}
""")

# ================= TAB 3 : DASHBOARD =================
with tabs[2]:
    st.subheader("📊 Dashboard")

    df = fetch_df()
    if df.empty:
        st.info("Belum ada data")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OPEN PO", rupiah(df[df["status"] == "OPEN"]["nominal_po"].sum()))
        c2.metric("Total COMPLETED PO", rupiah(df[df["status"] == "COMPLETED"]["nominal_po"].sum()))
        c3.metric("Total OVERDUE PO", rupiah(df[df["status"] == "OVERDUE"]["nominal_po"].sum()))

        rev = df.groupby("sales_engineer")["nominal_po"].sum()
        fig, ax = plt.subplots()
        rev.plot(kind="bar", ax=ax)
        ax.set_ylabel("Revenue")
        st.pyplot(fig)