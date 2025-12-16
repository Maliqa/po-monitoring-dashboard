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
    created_at TEXT
)
""")
conn.commit()

# ================= HELPERS =================
def calculate_status(expected_eta, actual_eta):
    today = date.today()
    if actual_eta:
        return "COMPLETED"
    if expected_eta and today > expected_eta:
        return "OVERDUE"
    return "OPEN"

def rupiah(val):
    return f"Rp {val:,.0f}".replace(",", ".")

def fetch_df():
    df = pd.read_sql("SELECT * FROM po", conn)
    if df.empty:
        return df

    for col in ["po_received_date", "expected_eta", "actual_eta", "created_at"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    df["year"] = df["po_received_date"].dt.year
    df["month"] = df["po_received_date"].dt.month

    df["status"] = df.apply(
        lambda r: calculate_status(
            r["expected_eta"].date() if pd.notnull(r["expected_eta"]) else None,
            r["actual_eta"].date() if pd.notnull(r["actual_eta"]) else None
        ),
        axis=1
    )
    return df

# ================= HEADER =================
if Path(LOGO_PATH).exists():
    st.image(LOGO_PATH, width=260)

st.title("PO Monitoring Dashboard")
st.caption("ISO 9001:2015 – Order, Delivery & Performance Monitoring System")

with st.expander("📌 Status Definition"):
    st.markdown("""
- **OPEN** → PO masih berjalan  
- **COMPLETED** → PO selesai  
- **OVERDUE** → Lewat Expected ETA  
""")

tabs = st.tabs(["➕ Input PO", "📋 Data PO", "📊 Dashboard"])

# ================= TAB 1 : INPUT =================
with tabs[0]:
    st.subheader("➕ Input Purchase Order")

    with st.form("po_form"):
        c1, c2 = st.columns(2)

        with c1:
            customer_name = st.text_input("Customer Name")
            sales_engineer = st.selectbox("Sales Engineer", SALES_ENGINEERS)
            division = st.selectbox("Division", DIVISIONS)
            quotation_no = st.text_input("Quotation Number")
            po_no = st.text_input("PO Number")

        with c2:
            po_received_date = st.date_input("PO Received Date", value=date.today())
            expected_eta = st.date_input("Expected ETA")
            actual_eta = st.date_input("Actual ETA", value=None)
            top = st.text_input("Term of Payment (TOP)")
            nominal_po = st.number_input("Nominal PO", min_value=0, step=1_000_000)

        payment_progress = st.slider("Payment Progress (%)", 0, 100, 0)
        remarks = st.text_area("Remarks")

        if st.form_submit_button("💾 Save PO"):
            c.execute("""
                INSERT INTO po (
                    customer_name, sales_engineer, division, quotation_no, po_no,
                    po_received_date, expected_eta, actual_eta, top,
                    nominal_po, payment_progress, remarks, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                customer_name, sales_engineer, division, quotation_no, po_no,
                po_received_date.isoformat(),
                expected_eta.isoformat() if expected_eta else None,
                actual_eta.isoformat() if actual_eta else None,
                top, nominal_po, payment_progress, remarks,
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
        # ===== FILTER & SEARCH =====
        f1, f2, f3, f4 = st.columns(4)

        with f1:
            f_sales = st.selectbox("Sales Engineer", ["All"] + SALES_ENGINEERS)
        with f2:
            f_status = st.selectbox("Status PO", ["All"] + STATUS_LIST)
        with f3:
            f_month = st.selectbox("Month", ["All"] + list(range(1, 13)))
        with f4:
            f_year = st.selectbox("Year", sorted(df["year"].dropna().unique()), index=len(df["year"].dropna().unique()) - 1)

        search = st.text_input("🔍 Search (Customer / PO No)")

        if f_sales != "All":
            df = df[df["sales_engineer"] == f_sales]
        if f_status != "All":
            df = df[df["status"] == f_status]
        if f_month != "All":
            df = df[df["month"] == f_month]
        df = df[df["year"] == f_year]

        if search:
            df = df[
                df["customer_name"].str.contains(search, case=False, na=False) |
                df["po_no"].str.contains(search, case=False, na=False)
            ]

        # ===== CARD VIEW =====
        for _, r in df.iterrows():
            with st.container(border=True):
                st.markdown(f"### 🏢 {r['customer_name']}")
                st.caption(f"PO No: {r['po_no']} | Status: {r['status']}")

                a, b = st.columns(2)
                with a:
                    st.markdown(f"""
- **Division:** {r['division']}
- **Quotation No:** {r['quotation_no']}
- **PO Received Date:** {r['po_received_date'].date()}
- **Expected ETA:** {r['expected_eta'].date() if pd.notnull(r['expected_eta']) else "-"}
- **Actual ETA:** {r['actual_eta'].date() if pd.notnull(r['actual_eta']) else "-"}
""")
                with b:
                    st.markdown(f"""
- **TOP:** {r['top']}
- **Nominal PO:** {rupiah(r['nominal_po'])}
- **Payment Progress:** {r['payment_progress']}%
- **Remarks:** {r['remarks'] or "-"}
""")

                # ===== EDIT =====
                with st.expander("✏️ Edit PO"):
                    with st.form(f"edit_{r['id']}"):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_customer = st.text_input("Customer", r["customer_name"])
                            e_sales = st.selectbox("Sales Engineer", SALES_ENGINEERS, index=SALES_ENGINEERS.index(r["sales_engineer"]))
                            e_div = st.selectbox("Division", DIVISIONS, index=DIVISIONS.index(r["division"]))
                            e_quote = st.text_input("Quotation No", r["quotation_no"])
                            e_po = st.text_input("PO No", r["po_no"])
                        with ec2:
                            e_prd = st.date_input("PO Received Date", r["po_received_date"].date())
                            e_eta = st.date_input("Expected ETA", r["expected_eta"].date())
                            e_act = st.date_input("Actual ETA", r["actual_eta"].date() if pd.notnull(r["actual_eta"]) else None)
                            e_top = st.text_input("TOP", r["top"])
                            e_nom = st.number_input("Nominal PO", value=int(r["nominal_po"]), step=1_000_000)

                        e_prog = st.slider("Payment Progress", 0, 100, r["payment_progress"])
                        e_rem = st.text_area("Remarks", r["remarks"] or "")

                        if st.form_submit_button("💾 Update PO"):
                            c.execute("""
                                UPDATE po SET
                                    customer_name=?, sales_engineer=?, division=?, quotation_no=?, po_no=?,
                                    po_received_date=?, expected_eta=?, actual_eta=?, top=?,
                                    nominal_po=?, payment_progress=?, remarks=?
                                WHERE id=?
                            """, (
                                e_customer, e_sales, e_div, e_quote, e_po,
                                e_prd.isoformat(),
                                e_eta.isoformat() if e_eta else None,
                                e_act.isoformat() if e_act else None,
                                e_top, e_nom, e_prog, e_rem, r["id"]
                            ))
                            conn.commit()
                            st.success("✅ PO updated")
                            st.rerun()

                # ===== DELETE =====
                with st.expander("🗑 Delete PO"):
                    confirm = st.checkbox("Saya yakin ingin menghapus PO ini", key=f"chk_{r['id']}")
                    if confirm:
                        if st.button("❌ Hapus Permanen", key=f"del_{r['id']}"):
                            c.execute("DELETE FROM po WHERE id=?", (r["id"],))
                            conn.commit()
                            st.warning("PO dihapus")
                            st.rerun()

# ================= TAB 3 : DASHBOARD =================
with tabs[2]:
    st.subheader("📊 Dashboard")
    df = fetch_df()
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("OPEN", rupiah(df[df["status"]=="OPEN"]["nominal_po"].sum()))
        c2.metric("COMPLETED", rupiah(df[df["status"]=="COMPLETED"]["nominal_po"].sum()))
        c3.metric("OVERDUE", rupiah(df[df["status"]=="OVERDUE"]["nominal_po"].sum()))