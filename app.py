import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
import os
import matplotlib.pyplot as plt

# ================= CONFIG =================
st.set_page_config(
    page_title="PO Monitoring Dashboard",
    layout="wide",
    page_icon="📊"
)

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "po_monitoring.db")
os.makedirs(DB_DIR, exist_ok=True)

SALES_ENGINEERS = ["RSM", "TNU", "MFA", "HSA", "HTA"]
DIVISIONS = ["Condition Monitoring", "Industrial Cleaning"]
STATUS_OPTIONS = ["OPEN", "COMPLETED", "OVERDUE"]

# ================= DATABASE =================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn = get_conn()
c = conn.cursor()

# === SAFE SCHEMA (FINAL) ===
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
    nominal_po REAL DEFAULT 0,
    payment_progress INTEGER DEFAULT 0,
    remarks TEXT,
    status TEXT,
    created_at TEXT
)
""")
conn.commit()

# ================= HELPERS =================
def rupiah(x):
    return f"Rp {int(x):,}".replace(",", ".")

def load_df():
    df = pd.read_sql("SELECT * FROM po", conn)
    if df.empty:
        return df

    for col in ["po_received_date", "expected_eta", "actual_eta", "created_at"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    df["nominal_po"] = pd.to_numeric(df["nominal_po"], errors="coerce").fillna(0)
    df["payment_progress"] = pd.to_numeric(df["payment_progress"], errors="coerce").fillna(0)

    df["year"] = df["po_received_date"].dt.year
    df["month"] = df["po_received_date"].dt.month

    return df

# ================= HEADER =================
st.markdown("## 🏢 **PO Monitoring Dashboard – CISTECH**")
st.caption("ISO 9001:2015 – Order, Delivery & Performance Monitoring System")
st.divider()

tab_input, tab_data, tab_dash = st.tabs(["➕ Input PO", "📄 Data PO", "📊 Dashboard"])

# =================================================
# ================= INPUT PO ======================
# =================================================
with tab_input:
    st.subheader("➕ Input Purchase Order")

    with st.form("form_po", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            customer = st.text_input("Customer Name")
            sales = st.selectbox("Sales Engineer", SALES_ENGINEERS)
            division = st.selectbox("Division", DIVISIONS)

        with c2:
            quotation = st.text_input("Quotation Number")
            po_no = st.text_input("PO Number")
            po_date = st.date_input("PO Received Date", date.today())

        with c3:
            expected_eta = st.date_input("Expected ETA", date.today())
            actual_eta = st.date_input("Actual ETA", value=None)
            nominal = st.number_input("Nominal PO", min_value=0, step=1_000_000)

        payment = st.slider("Payment Progress (%)", 0, 100, 0)
        remarks = st.text_area("Remarks", height=80)

        submitted = st.form_submit_button("💾 Save PO")

        if submitted:
            status = "OPEN"
            if actual_eta:
                status = "COMPLETED"
            elif expected_eta < date.today():
                status = "OVERDUE"

            c.execute("""
            INSERT INTO po (
                customer_name, sales_engineer, division,
                quotation_no, po_no,
                po_received_date, expected_eta, actual_eta,
                nominal_po, payment_progress, remarks,
                status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                customer, sales, division,
                quotation, po_no,
                po_date.isoformat(),
                expected_eta.isoformat(),
                actual_eta.isoformat() if actual_eta else None,
                nominal, payment, remarks,
                status, datetime.now().isoformat()
            ))
            conn.commit()
            st.success("✅ PO berhasil disimpan")

# =================================================
# ================= DATA PO =======================
# =================================================
with tab_data:
    st.subheader("📄 Data Purchase Order")

    df = load_df()
    if df.empty:
        st.info("Belum ada data PO")
    else:
        current_year = date.today().year

        f1, f2, f3, f4 = st.columns(4)
        with f1:
            f_sales = st.selectbox("Sales Engineer", ["All"] + SALES_ENGINEERS)
        with f2:
            f_status = st.selectbox("Status", ["All"] + STATUS_OPTIONS)
        with f3:
            f_month = st.selectbox("Month", ["All"] + list(range(1, 13)))
        with f4:
            f_year = st.selectbox("Year", sorted(df["year"].dropna().unique()), index=list(sorted(df["year"].dropna().unique())).index(current_year) if current_year in df["year"].values else 0)

        if f_sales != "All":
            df = df[df["sales_engineer"] == f_sales]
        if f_status != "All":
            df = df[df["status"] == f_status]
        if f_month != "All":
            df = df[df["month"] == f_month]
        df = df[df["year"] == f_year]

        for _, row in df.iterrows():
            with st.expander(f"📄 {row['customer_name']} | {row['po_no']} | {row['status']}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Sales**: {row['sales_engineer']}")
                c2.write(f"**Nominal**: {rupiah(row['nominal_po'])}")
                c3.write(f"**Payment**: {row['payment_progress']}%")

                st.write(f"**Remarks**: {row['remarks']}")

                # ===== EDIT =====
                with st.form(f"edit_{row['id']}"):
                    new_payment = st.slider("Update Payment (%)", 0, 100, int(row["payment_progress"]))
                    new_actual = st.date_input("Actual ETA", row["actual_eta"])
                    save = st.form_submit_button("✏️ Update")

                    if save:
                        new_status = "COMPLETED" if new_actual else row["status"]
                        c.execute("""
                        UPDATE po
                        SET payment_progress=?, actual_eta=?, status=?
                        WHERE id=?
                        """, (
                            new_payment,
                            new_actual.isoformat() if new_actual else None,
                            new_status,
                            row["id"]
                        ))
                        conn.commit()
                        st.success("✅ Updated")

                # ===== DELETE =====
                if st.button("🗑️ Delete PO", key=f"del_{row['id']}"):
                    c.execute("DELETE FROM po WHERE id=?", (row["id"],))
                    conn.commit()
                    st.warning("🗑️ PO deleted")
                    st.experimental_rerun()

# =================================================
# ================= DASHBOARD =====================
# =================================================
with tab_dash:
    st.subheader("📊 Executive Dashboard")

    df = load_df()
    if df.empty:
        st.info("Belum ada data")
    else:
        open_val = df[df["status"] == "OPEN"]["nominal_po"].sum()
        done_val = df[df["status"] == "COMPLETED"]["nominal_po"].sum()
        overdue_val = df[df["status"] == "OVERDUE"]["nominal_po"].sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total OPEN PO Value", rupiah(open_val))
        c2.metric("Total COMPLETED PO Value", rupiah(done_val))
        c3.metric("Total OVERDUE PO Value", rupiah(overdue_val))

        st.divider()

        st.subheader("📈 Revenue per Sales Engineer")
        rev = df.groupby("sales_engineer")["nominal_po"].sum()

        fig, ax = plt.subplots()
        rev.plot(kind="bar", ax=ax)
        ax.set_ylabel("Revenue")
        st.pyplot(fig)