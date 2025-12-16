import streamlit as st
import sqlite3
from datetime import datetime, date
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ================= CONFIG =================
st.set_page_config(
    page_title="PO Monitoring Dashboard",
    page_icon="📊",
    layout="wide"
)

DB_PATH = "data/po_monitoring.db"
LOGO_PATH = "assets/cistech.png"

DIVISIONS = [
    "Industrial Cleaning",
    "Condition Monitoring"
]

SALES_ENGINEERS = [
    "RSM",
    "TNU",
    "MFA",
    "HSA",
    "HTA"
]

# ================= DATABASE =================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn = get_conn()
c = conn.cursor()

# ================= TABLE =================
c.execute("""
CREATE TABLE IF NOT EXISTS po (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT,
    division TEXT,
    quotation_no TEXT,
    po_no TEXT,
    po_received_date TEXT,
    expected_eta TEXT,
    actual_eta TEXT,
    top TEXT,
    payment_progress INTEGER,
    remarks TEXT,
    status TEXT,
    created_at TEXT,
    sales_engineer TEXT,
    po_amount REAL
)
""")
conn.commit()

# ================= SAFE MIGRATION =================
def add_column_if_not_exists(col, col_type):
    cols = [r[1] for r in c.execute("PRAGMA table_info(po)")]
    if col not in cols:
        c.execute(f"ALTER TABLE po ADD COLUMN {col} {col_type}")
        conn.commit()

add_column_if_not_exists("sales_engineer", "TEXT")
add_column_if_not_exists("po_amount", "REAL")

# ================= HELPER =================
def safe_date(val):
    if val is None or pd.isna(val):
        return None
    return val

# ================= BUSINESS LOGIC =================
def calculate_status(expected_eta, actual_eta):
    today = date.today()
    if actual_eta:
        return "COMPLETED"
    if today > expected_eta:
        return "OVERDUE"
    return "OPEN"

def fetch_df():
    df = pd.read_sql("SELECT * FROM po ORDER BY created_at DESC", conn)

    if df.empty:
        return df

    df["expected_eta"] = pd.to_datetime(df["expected_eta"], errors="coerce").dt.date
    df["actual_eta"] = pd.to_datetime(df["actual_eta"], errors="coerce").dt.date
    df["actual_eta"] = df["actual_eta"].apply(safe_date)

    df["status"] = df.apply(
        lambda x: calculate_status(x["expected_eta"], x["actual_eta"]),
        axis=1
    )

    for _, r in df.iterrows():
        c.execute(
            "UPDATE po SET status=? WHERE id=?",
            (r["status"], r["id"])
        )
    conn.commit()

    return df

# ================= HEADER =================
with st.container():
    if Path(LOGO_PATH).exists():
        st.image(LOGO_PATH, width=300)

    st.markdown(
        "<h2>PO Monitoring Dashboard</h2>",
        unsafe_allow_html=True
    )
    st.caption("ISO 9001:2015 – Order, Delivery & Performance Monitoring")

with st.expander("📌 Status Definition"):
    st.markdown("""
- **OPEN** → PO masih berjalan  
- **COMPLETED** → PO selesai (wajib Actual ETA)  
- **OVERDUE** → Melewati Expected ETA  
""")

tabs = st.tabs([
    "➕ Input PO",
    "📋 Data PO",
    "📈 Dashboard"
])

# ================= TAB 1 : INPUT =================
with tabs[0]:
    st.subheader("➕ Input Purchase Order")

    with st.form("po_form"):
        customer_name = st.text_input("Customer Name")
        sales_engineer = st.selectbox("Sales Engineer", SALES_ENGINEERS)
        division = st.selectbox("Division", DIVISIONS)
        quotation_no = st.text_input("Quotation Number")
        po_no = st.text_input("PO Number")

        po_received_date = st.date_input("PO Received Date")
        expected_eta = st.date_input("Expected ETA")
        actual_eta = st.date_input("Actual ETA (jika sudah selesai)", value=None)

        po_amount = st.number_input(
            "Nominal PO (Rp)",
            min_value=0.0,
            step=1_000_000.0,
            format="%.0f"
        )

        top = st.text_input("Term of Payment (TOP)")
        payment_progress = st.slider("Payment Progress (%)", 0, 100, 0)
        remarks = st.text_area("Remarks")

        if st.form_submit_button("💾 Save PO"):
            if not customer_name or not po_no:
                st.error("Customer Name & PO Number wajib diisi")
            else:
                status = calculate_status(expected_eta, actual_eta)
                c.execute("""
                INSERT INTO po (
                    customer_name, division, quotation_no, po_no,
                    po_received_date, expected_eta, actual_eta,
                    top, payment_progress, remarks, status,
                    created_at, sales_engineer, po_amount
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    customer_name, division, quotation_no, po_no,
                    po_received_date.isoformat(),
                    expected_eta.isoformat(),
                    actual_eta.isoformat() if actual_eta else None,
                    top, payment_progress, remarks,
                    status, datetime.now().isoformat(),
                    sales_engineer, po_amount
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
        col1, col2 = st.columns(2)
        search = col1.text_input("🔍 Search Customer / PO").lower()
        sales_filter = col2.selectbox(
            "Filter Sales Engineer",
            ["All"] + sorted(df["sales_engineer"].dropna().unique())
        )

        if search:
            df = df[
                df["customer_name"].str.lower().str.contains(search) |
                df["po_no"].str.lower().str.contains(search)
            ]

        if sales_filter != "All":
            df = df[df["sales_engineer"] == sales_filter]

        for _, row in df.iterrows():
            with st.container():
                st.markdown(f"### 🏢 {row['customer_name']}")
                st.caption(
                    f"PO: {row['po_no']} | Sales: {row['sales_engineer']} | Status: {row['status']}"
                )

                with st.expander("📄 Detail PO"):
                    colA, colB = st.columns(2)

                    with colA:
                        st.markdown(f"""
**Division:** {row['division']}  
**Quotation:** {row['quotation_no']}  
**PO Date:** {row['po_received_date']}  
**Expected ETA:** {row['expected_eta']}  
""")

                    with colB:
                        st.markdown(f"""
**Actual ETA:** {row['actual_eta'] or '-'}  
**Nominal PO:** Rp {row['po_amount']:,.0f}  
**TOP:** {row['top']}  
**Payment:** {row['payment_progress']}%  
""")

                    st.markdown(f"**Remarks:** {row['remarks'] or '-'}")

                with st.expander("✏️ Edit / 🗑 Delete"):
                    new_sales = st.selectbox(
                        "Sales Engineer",
                        SALES_ENGINEERS,
                        index=SALES_ENGINEERS.index(row["sales_engineer"])
                        if row["sales_engineer"] in SALES_ENGINEERS else 0,
                        key=f"sales_{row['id']}"
                    )

                    new_amount = st.number_input(
                        "Nominal PO (Rp)",
                        value=row["po_amount"] or 0.0,
                        step=1_000_000.0,
                        format="%.0f",
                        key=f"amt_{row['id']}"
                    )

                    new_expected = st.date_input(
                        "Expected ETA",
                        value=safe_date(row["expected_eta"]),
                        key=f"exp_{row['id']}"
                    )

                    new_actual = st.date_input(
                        "Actual ETA",
                        value=safe_date(row["actual_eta"]),
                        key=f"act_{row['id']}"
                    )

                    new_top = st.text_input("TOP", row["top"], key=f"top_{row['id']}")
                    new_payment = st.slider(
                        "Payment Progress (%)",
                        0, 100, row["payment_progress"],
                        key=f"pay_{row['id']}"
                    )
                    new_remarks = st.text_area(
                        "Remarks", row["remarks"], key=f"rem_{row['id']}"
                    )

                    if st.button("💾 Update", key=f"upd_{row['id']}"):
                        new_status = calculate_status(new_expected, new_actual)
                        c.execute("""
                        UPDATE po SET
                            expected_eta=?, actual_eta=?, top=?,
                            payment_progress=?, remarks=?, status=?,
                            sales_engineer=?, po_amount=?
                        WHERE id=?
                        """, (
                            new_expected.isoformat(),
                            new_actual.isoformat() if new_actual else None,
                            new_top, new_payment, new_remarks,
                            new_status, new_sales, new_amount,
                            row["id"]
                        ))
                        conn.commit()
                        st.success("PO berhasil diupdate")
                        st.rerun()

                    if st.checkbox(
                        f"Hapus PO ID {row['id']}",
                        key=f"del_chk_{row['id']}"
                    ):
                        if st.button("🗑 DELETE", key=f"del_{row['id']}"):
                            c.execute("DELETE FROM po WHERE id=?", (row["id"],))
                            conn.commit()
                            st.warning("PO dihapus")
                            st.rerun()

                st.divider()

# ================= TAB 3 : DASHBOARD =================
with tabs[2]:
    st.subheader("📈 Dashboard")

    df = fetch_df()
    if not df.empty:
        col1, col2 = st.columns(2)

        with col1:
            fig, ax = plt.subplots()
            df["status"].value_counts().plot(kind="bar", ax=ax)
            ax.set_ylabel("Jumlah PO")
            st.pyplot(fig)

        with col2:
            fig2, ax2 = plt.subplots()
            df.groupby("sales_engineer")["po_amount"].sum().plot(
                kind="bar", ax=ax2, title="Total Nominal PO per Sales"
            )
            ax2.set_ylabel("Nominal (Rp)")
            st.pyplot(fig2)
