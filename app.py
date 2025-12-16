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

# ================= PATH =================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "po_monitoring.db"
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

c.execute("""
CREATE TABLE IF NOT EXISTS po (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    sales_engineer TEXT NOT NULL,
    division TEXT,
    quotation_no TEXT,
    po_no TEXT NOT NULL,
    po_received_date TEXT,
    expected_eta TEXT,
    actual_eta TEXT,
    nominal_po REAL DEFAULT 0,
    top TEXT,
    payment_progress INTEGER DEFAULT 0,
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

def calculate_status(expected_eta, actual_eta):
    today = date.today()
    if actual_eta:
        return "COMPLETED"
    if expected_eta and today > expected_eta:
        return "OVERDUE"
    return "OPEN"

def fetch_df():
    df = pd.read_sql("SELECT * FROM po ORDER BY created_at DESC", conn)

    if df.empty:
        return df

    df["po_received_date"] = pd.to_datetime(
        df["po_received_date"], errors="coerce"
    )

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

    # sync status ke DB
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
        st.image(LOGO_PATH, width=260)

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
    "📊 Dashboard"
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
        actual_eta = st.date_input(
            "Actual ETA (isi jika sudah selesai)",
            value=None
        )

        nominal_po = st.number_input(
            "Nominal PO (Rp)",
            min_value=0.0,
            step=1_000_000.0,
            format="%.0f"
        )

        top = st.text_input("Term of Payment (TOP)")
        payment_progress = st.slider(
            "Payment Progress (%)", 0, 100, 0
        )
        remarks = st.text_area("Remarks")

        if st.form_submit_button("💾 Save PO"):
            if not customer_name or not po_no:
                st.error("Customer Name & PO Number wajib diisi")
            else:
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
                    nominal_po,
                    top,
                    payment_progress,
                    remarks,
                    status,
                    created_at
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
                """, (
                    customer_name,
                    sales_engineer,
                    division,
                    quotation_no,
                    po_no,
                    po_received_date.isoformat(),
                    expected_eta.isoformat(),
                    actual_eta.isoformat() if actual_eta else None,
                    nominal_po,
                    top,
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
        st.stop()

    years_available = sorted(
        df["po_received_date"].dt.year.dropna().unique().tolist()
    )

    current_year = date.today().year
    default_year_index = (
        years_available.index(current_year)
        if current_year in years_available
        else 0
    )

    st.markdown("### 🔎 Reporting Filter")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        sales_filter = st.selectbox(
            "Sales Engineer",
            ["All"] + SALES_ENGINEERS
        )

    with col2:
        status_filter = st.selectbox(
            "Status PO",
            ["All", "OPEN", "COMPLETED", "OVERDUE"]
        )

    with col3:
        month_filter = st.selectbox(
            "Month",
            ["All"] + list(range(1, 13))
        )

    with col4:
        year_filter = st.selectbox(
            "Year",
            years_available,
            index=default_year_index
        )

    df_f = df.copy()

    if sales_filter != "All":
        df_f = df_f[df_f["sales_engineer"] == sales_filter]

    if status_filter != "All":
        df_f = df_f[df_f["status"] == status_filter]

    if month_filter != "All":
        df_f = df_f[df_f["po_received_date"].dt.month == month_filter]

    df_f = df_f[df_f["po_received_date"].dt.year == year_filter]

    st.markdown("### 📌 KPI Summary")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total OPEN PO Value",
        f"Rp {df_f[df_f['status']=='OPEN']['nominal_po'].sum():,.0f}"
    )

    col2.metric(
        "Total COMPLETED PO Value",
        f"Rp {df_f[df_f['status']=='COMPLETED']['nominal_po'].sum():,.0f}"
    )

    col3.metric(
        "Total OVERDUE PO Value",
        f"Rp {df_f[df_f['status']=='OVERDUE']['nominal_po'].sum():,.0f}"
    )

    st.markdown("### 📄 PO List")

    for _, row in df_f.iterrows():
        with st.expander(
            f"🏢 {row['customer_name']} | {row['po_no']} | {row['status']}"
        ):
            st.markdown(f"""
**Sales Engineer:** {row['sales_engineer']}  
**Division:** {row['division']}  
**Quotation:** {row['quotation_no']}  
**PO Date:** {row['po_received_date'].date()}  
**Expected ETA:** {row['expected_eta']}  
**Actual ETA:** {row['actual_eta'] if row['actual_eta'] else '-'}  
**Nominal PO:** Rp {row['nominal_po']:,.0f}  
**TOP:** {row['top']}  
**Payment:** {row['payment_progress']}%  
**Remarks:** {row['remarks'] if row['remarks'] else '-'}
""")

            # ================= EDIT & DELETE =================
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

                new_nominal_po = st.number_input(
                    "Nominal PO (Rp)",
                    min_value=0.0,
                    value=float(row["nominal_po"]),
                    step=1_000_000.0,
                    key=f"nom_{row['id']}"
                )

                new_payment = st.slider(
                    "Payment Progress (%)",
                    0, 100,
                    int(row["payment_progress"]),
                    key=f"pay_{row['id']}"
                )

                new_remarks = st.text_area(
                    "Remarks",
                    value=row["remarks"] if row["remarks"] else "",
                    key=f"rem_{row['id']}"
                )

                col_upd, col_del = st.columns(2)

                # ===== UPDATE =====
                with col_upd:
                    if st.button("💾 Update PO", key=f"upd_{row['id']}"):
                        new_status = calculate_status(
                            new_expected_eta,
                            new_actual_eta
                        )

                        c.execute("""
                        UPDATE po SET
                            expected_eta=?,
                            actual_eta=?,
                            nominal_po=?,
                            payment_progress=?,
                            remarks=?,
                            status=?
                        WHERE id=?
                        """, (
                            new_expected_eta.isoformat(),
                            new_actual_eta.isoformat() if new_actual_eta else None,
                            new_nominal_po,
                            new_payment,
                            new_remarks,
                            new_status,
                            row["id"]
                        ))
                        conn.commit()
                        st.success("✅ PO berhasil diupdate")
                        st.rerun()

                # ===== DELETE =====
                with col_del:
                    confirm = st.checkbox(
                        f"Saya yakin ingin menghapus PO {row['po_no']}",
                        key=f"chk_{row['id']}"
                    )
                    if confirm:
                        if st.button("🗑 Delete PO", key=f"del_{row['id']}"):
                            c.execute(
                                "DELETE FROM po WHERE id=?",
                                (row["id"],)
                            )
                            conn.commit()
                            st.warning("🗑 PO berhasil dihapus")
                            st.rerun()


# ================= TAB 3 : DASHBOARD =================
with tabs[2]:
    st.subheader("📊 Revenue by Sales Engineer")

    df = fetch_df()

    if df.empty:
        st.info("Tidak ada data")
        st.stop()

    revenue_sales = (
        df.groupby("sales_engineer")["nominal_po"]
        .sum()
        .reset_index()
    )

    fig, ax = plt.subplots()
    ax.bar(
        revenue_sales["sales_engineer"],
        revenue_sales["nominal_po"]
    )
    ax.set_ylabel("Revenue (Rp)")
    ax.set_xlabel("Sales Engineer")
    ax.set_title("Revenue by Sales Engineer")
    plt.xticks(rotation=30)

    st.pyplot(fig)
