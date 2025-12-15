# 📊 PO Monitoring Dashboard – CISTECH

PO Monitoring Dashboard adalah aplikasi berbasis **Streamlit + SQLite** untuk memantau Purchase Order (PO) sesuai prinsip **ISO 9001:2015** (Order, Delivery & Performance Monitoring).

Aplikasi ini mendukung:
- CRUD Purchase Order
- Status otomatis (OPEN / COMPLETED / OVERDUE)
- Search PO & Customer
- Dashboard grafik
- Deployment via Docker & Docker Compose

---

## 🚀 Fitur Utama

- ➕ Input Purchase Order
- ✏️ Edit & 🗑 Delete PO
- 🔍 Search berdasarkan Customer / PO Number
- 📌 Status otomatis:
  - **OPEN** → PO berjalan, belum lewat ETA
  - **COMPLETED** → PO selesai (wajib Actual ETA)
  - **OVERDUE** → Melewati Expected ETA
- 📈 Dashboard monitoring
- 🐳 Siap deploy dengan Docker

---

## 🧱 Teknologi

- Python 3.12
- Streamlit
- SQLite
- Docker
- Docker Compose

---

## 📂 Struktur Project

```text
po-monitoring-dashboard/
├── app.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── assets/
│   └── cistech.png
├── data/                # SQLite volume (runtime)
└── README.md
