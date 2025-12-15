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

DB_PATH = "po_monitoring.db"
LOGO_PATH = "assets/cistech.png"

DIVISIONS = [
    "Industrial Cleaning",
    "Condition Monitoring"
]

# ================= DATABASE =================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn = get_conn()
c = conn.cursor()

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
    created_at TEXT
)
""")
conn.commit()

# ================= HELPER =================
def safe_date(val):
    if val is None or pd.isna(val):
        return None
    return val

# ================= BUSINESS LOGIC =================
def calculate_status(expected_eta, actual_eta):
    today = date.today()
    if actual_eta is not None:
        return "COMPLETED"
    if today > expected_eta:
        return "OVERDUE"
    return "OPEN"

def fetch_df():
    df = pd.read_sql("SELECT * FROM po ORDER BY created_at DESC", conn)

    if df.empty:
        return df

    df["expected_eta"] = pd.to_datetime(
        df["expected_eta"], errors="coerce"
    ).dt.date

    df["actual_eta"] = pd.to_datetime(
        df["actual_eta"], errors="coerce"
    ).dt.date

    df["actual_eta"] = df["actual_eta"].apply(safe_date)

    df["status"] = df.apply(
        lambda x: calculate_status(
            x["expected_eta"], x["actual_eta"]
        ),
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
        st.image(LOGO_PATH, width=360)

    st.markdown(
        "<h2 style='margin-top:10px;'>PO Monitoring Dashboard</h2>",
        unsafe_allow_html=True
    )

    st.caption(
        "ISO 9001:2015 – Order, Delivery & Performance Monitoring System"
    )

with st.expander("📌 Status Definition", expanded=False):
    st.markdown("""
**OPEN** – PO masih berjalan  
**COMPLETED** – PO selesai & wajib Actual ETA  
**OVERDUE** – Melewati Expected ETA
""")

tabs = st.tabs([
    "➕ Input PO",
    "📋 Data PO",
    "📈 Dashboard"
])

# ================= TAB 1 =================
with tabs[0]:
    st.subheader("➕ Input Purchase Order")

    with st.form("po_form"):
        customer_name = st.text_input("Customer Name")
        division = st.selectbox("Division", DIVISIONS)
        quotation_no = st.text_input("Quotation Number")
        po_no = st.text_input("PO Number")

        po_received_date = st.date_input("PO Received Date")
        expected_eta = st.date_input("Expected ETA")
        actual_eta = st.date_input(
            "Actual ETA (jika sudah selesai)",
            value=None
        )

        top = st.text_input("Term of Payment (TOP)")
        payment_progress = st.slider(
            "Payment Progress (%)", 0, 100, 0
        )
        remarks = st.text_area("Remarks")

        if st.form_submit_button("💾 Save PO"):
            status = calculate_status(expected_eta, actual_eta)
            c.execute("""
            INSERT INTO po VALUES (
                NULL,?,?,?,?,?,?,?,?,?,?,?,?
            )
            """, (
                customer_name,
                division,
                quotation_no,
                po_no,
                po_received_date.isoformat(),
                expected_eta.isoformat(),
                actual_eta.isoformat() if actual_eta else None,
                top,
                payment_progress,
                remarks,
                status,
                datetime.now().isoformat()
            ))
            conn.commit()
            st.success("✅ PO berhasil disimpan")

# ================= TAB 2 =================
with tabs[1]:
    st.subheader("📋 Data Purchase Order")

    df = fetch_df()

    search = st.text_input("🔍 Search (Customer / PO)").lower()
    if search:
        df = df[
            df["customer_name"].str.lower().str.contains(search) |
            df["po_no"].str.lower().str.contains(search)
        ]

    for _, row in df.iterrows():
        with st.container():
            # ===== SUMMARY =====
            st.markdown(f"### 🏢 {row['customer_name']}")
            st.caption(
                f"PO Number: {row['po_no']} | Status: {row['status']}"
            )

            # ===== DETAIL =====
            with st.expander("📄 Detail PO"):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown(f"""
**Division:** {row['division']}  
**Quotation No:** {row['quotation_no']}  
**PO Received Date:** {row['po_received_date']}  
**Expected ETA:** {row['expected_eta']}  
""")

                with col2:
                    st.markdown(f"""
**Actual ETA:** {row['actual_eta'] if row['actual_eta'] else "-"}  
**TOP:** {row['top']}  
**Payment Progress:** {row['payment_progress']}%  
""")

                st.markdown(
                    f"**Remarks:** {row['remarks'] or '-'}"
                )

            # ===== EDIT & DELETE =====
            with st.expander("✏️ Edit / 🗑 Delete PO"):
                new_expected_eta = st.date_input(
                    "Expected ETA",
                    value=safe_date(row["expected_eta"]),
                    key=f"exp_{row['id']}"
                )

                new_actual_eta = st.date_input(
                    "Actual ETA (wajib untuk COMPLETED)",
                    value=safe_date(row["actual_eta"]),
                    key=f"act_{row['id']}"
                )

                new_top = st.text_input(
                    "TOP",
                    row["top"],
                    key=f"top_{row['id']}"
                )

                new_payment = st.slider(
                    "Payment Progress (%)",
                    0, 100,
                    row["payment_progress"],
                    key=f"pay_{row['id']}"
                )

                new_remarks = st.text_area(
                    "Remarks",
                    row["remarks"],
                    key=f"rem_{row['id']}"
                )

                if st.button("💾 Update PO", key=f"upd_{row['id']}"):
                    new_status = calculate_status(
                        new_expected_eta,
                        new_actual_eta
                    )

                    c.execute("""
                    UPDATE po SET
                        expected_eta=?,
                        actual_eta=?,
                        top=?,
                        payment_progress=?,
                        remarks=?,
                        status=?
                    WHERE id=?
                    """, (
                        new_expected_eta.isoformat(),
                        new_actual_eta.isoformat()
                        if new_actual_eta else None,
                        new_top,
                        new_payment,
                        new_remarks,
                        new_status,
                        row["id"]
                    ))
                    conn.commit()
                    st.success("✅ PO berhasil diupdate")
                    st.rerun()

                st.divider()

                confirm = st.checkbox(
                    f"Saya yakin ingin menghapus PO ID {row['id']}",
                    key=f"chk_{row['id']}"
                )
                if confirm:
                    if st.button("🗑 DELETE PO", key=f"del_{row['id']}"):
                        c.execute(
                            "DELETE FROM po WHERE id=?",
                            (row["id"],)
                        )
                        conn.commit()
                        st.warning("🗑 PO berhasil dihapus")
                        st.rerun()

            st.divider()

# ================= TAB 3 =================
with tabs[2]:
    st.subheader("📈 Dashboard")

    df = fetch_df()
    if not df.empty:
        fig, ax = plt.subplots()
        df["status"].value_counts().plot(kind="bar", ax=ax)
        st.pyplot(fig)
