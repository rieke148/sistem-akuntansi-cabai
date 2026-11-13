"""
app.py
------
Tujuan  : Pintu masuk utama aplikasi Sistem Akuntansi Cabai.
          Menginisialisasi database, menjalankan seed data (jika perlu),
          dan mengatur navigasi antar halaman dengan st.navigation.
Input   : Tidak ada (dijalankan oleh Streamlit: `streamlit run app.py`).
Output  : Aplikasi web Streamlit yang bisa diakses di browser.
Dipanggil oleh : Streamlit runtime (bukan file Python lain).

CARA MENJALANKAN:
  Aktifkan virtual environment:
    Windows: venv\\Scripts\\activate
  Lalu jalankan:
    streamlit run app.py
"""

import streamlit as st
from database.connection import db_sudah_ada
from database.schema import buat_semua_tabel, migrasikan_komoditas_cabai_saja
from database.seed import jalankan_seed
from theme import NAMA_APLIKASI, NAMA_PERUSAHAAN, WARNA_PRIMER


# ---------------------------------------------------------------
# KONFIGURASI HALAMAN (harus dipanggil PERTAMA sebelum st lain)
# ---------------------------------------------------------------
st.set_page_config(
    page_title=NAMA_APLIKASI,
    page_icon="🌶️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": f"**{NAMA_APLIKASI}**\n{NAMA_PERUSAHAAN}\n\nSistem Informasi Siklus Akuntansi",
    },
)


# ---------------------------------------------------------------
# INISIALISASI DATABASE (sekali saat startup)
# ---------------------------------------------------------------
@st.cache_resource  # cache_resource agar hanya jalan sekali per sesi
def inisialisasi_database() -> bool:
    """
    Memastikan tabel sudah ada dan seed data sudah diisi.
    Mengembalikan True jika seed baru dijalankan.
    """
    # Langkah 1: Buat semua tabel (aman jika sudah ada — IF NOT EXISTS)
    buat_semua_tabel()
    migrasikan_komoditas_cabai_saja()

    # Pastikan periode dasar (2025-2027) tersedia
    from services.period_service import pastikan_periode_dasar_tersedia
    pastikan_periode_dasar_tersedia()

    # Langkah 2: Jika tabel accounts kosong, jalankan seed
    from database.connection import get_connection
    koneksi = get_connection()
    cursor = koneksi.cursor()
    jumlah_akun = cursor.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    koneksi.close()

    if jumlah_akun == 0:
        # Database kosong → isi dengan data contoh
        jalankan_seed()
        return True  # seed baru dijalankan
    return False  # sudah ada data


# Jalankan inisialisasi
seed_baru = inisialisasi_database()

# Tampilkan notifikasi jika baru di-seed
if seed_baru:
    st.toast(
        "🌱 Data contoh berhasil dimuat! "
        "Ganti saldo awal & data bertanda '⚠️ CONTOH' dengan data asli.",
        icon="✅",
    )


# ---------------------------------------------------------------
# DEFINISI HALAMAN (st.Page — untuk st.navigation)
# ---------------------------------------------------------------
# CATATAN: Semua file halaman ada di folder views/ (BUKAN pages/).
#          Ini sesuai aturan brief: dilarang membuat folder pages/.

halaman_dashboard = st.Page(
    "views/00_dashboard.py",
    title="Dashboard",
    icon="🏠",
    default=True,
)

# --- Master Data ---
halaman_master_data = st.Page(
    "views/01_master_data.py",
    title="Master Data",
    icon="🗄️",
)

# --- Input ---
halaman_transaksi = st.Page(
    "views/02_input_transaksi.py",
    title="Input Transaksi",
    icon="✏️",
)
halaman_penggajian = st.Page(
    "views/03_penggajian.py",
    title="Penggajian",
    icon="💰",
)

# --- Jurnal ---
halaman_jurnal_umum = st.Page(
    "views/04_jurnal_umum.py",
    title="Jurnal Umum",
    icon="📔",
)
halaman_jurnal_khusus = st.Page(
    "views/05_jurnal_khusus.py",
    title="Jurnal Khusus",
    icon="📚",
)

# --- Buku Besar ---
halaman_kartu_persediaan = st.Page(
    "views/06_kartu_persediaan.py",
    title="Kartu Persediaan",
    icon="📦",
)
halaman_buku_besar = st.Page(
    "views/07_buku_besar.py",
    title="Buku Besar",
    icon="📖",
)
halaman_bb_pembantu = st.Page(
    "views/08_buku_besar_pembantu.py",
    title="BB Pembantu",
    icon="🔖",
)

# --- Laporan ---
halaman_neraca_saldo = st.Page(
    "views/09_neraca_saldo.py",
    title="Neraca Saldo",
    icon="⚖️",
)
halaman_penyesuaian = st.Page(
    "views/10_ayat_penyesuaian.py",
    title="Ayat Penyesuaian",
    icon="📝",
)
halaman_neraca_lajur = st.Page(
    "views/11_neraca_lajur.py",
    title="Neraca Lajur",
    icon="📊",
)
halaman_laporan_keuangan = st.Page(
    "views/12_laporan_keuangan.py",
    title="Laporan Keuangan",
    icon="📈",
)
halaman_jurnal_penutup = st.Page(
    "views/13_jurnal_penutup.py",
    title="Jurnal Penutup",
    icon="🔒",
)

# --- Utilitas ---
halaman_backup = st.Page(
    "views/14_backup_export.py",
    title="Backup & Export",
    icon="💾",
)


# ---------------------------------------------------------------
# NAVIGASI (st.navigation — pengganti st.sidebar.radio versi baru)
# ---------------------------------------------------------------
# Grup navigasi mengikuti urutan siklus akuntansi
navigasi = st.navigation(
    {
        "🏠 Beranda": [halaman_dashboard],
        "🗄️ Setup": [halaman_master_data],
        "✏️ Input": [halaman_transaksi, halaman_penggajian],
        "📔 Jurnal": [halaman_jurnal_umum, halaman_jurnal_khusus],
        "📖 Buku Besar": [
            halaman_kartu_persediaan,
            halaman_buku_besar,
            halaman_bb_pembantu,
        ],
        "📊 Laporan": [
            halaman_neraca_saldo,
            halaman_penyesuaian,
            halaman_neraca_lajur,
            halaman_laporan_keuangan,
            halaman_jurnal_penutup,
        ],
        "💾 Utilitas": [halaman_backup],
    },
    position="sidebar",
)

# Jalankan halaman yang dipilih
navigasi.run()
