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
from database.schema import (
    buat_semua_tabel,
    migrasikan_komoditas_cabai_saja,
    migrasikan_akun_persediaan_bahan_produksi,
    pastikan_akun_hpp_penjualan_tersedia,
    migrasikan_coa_baru,
    migrasikan_persediaan_barang_dagang_saja,
)
from database.seed import jalankan_seed
from theme import NAMA_APLIKASI, NAMA_PERUSAHAAN, WARNA_PRIMER
from services import auth_service
from services.permission_service import pengguna_aktif, keluar_pengguna, punya_izin


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
    migrasikan_akun_persediaan_bahan_produksi()
    # Migrasi COA lama ke COA baru (coa_cabai_baru.csv)
    migrasikan_coa_baru()
    # Arsipkan item bahan lama; seluruh jurnal dan mutasi historis tetap dipertahankan.
    migrasikan_persediaan_barang_dagang_saja()

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
        pastikan_akun_hpp_penjualan_tersedia()
        return True  # seed baru dijalankan

    # Database lama mungkin belum memiliki akun HPP penjualan cabai.
    pastikan_akun_hpp_penjualan_tersedia()
    return False  # sudah ada data


# Jalankan inisialisasi
seed_baru = inisialisasi_database()

# Siapkan role, permission, dan tabel akun setelah database akuntansi siap.
@st.cache_resource(show_spinner=False)
def _inisialisasi_otorisasi() -> bool:
    """Siapkan role dan permission satu kali per proses aplikasi."""
    auth_service.inisialisasi_otorisasi()
    return True


_inisialisasi_otorisasi()

# Tampilkan notifikasi jika baru di-seed
if seed_baru:
    st.toast(
        "🌱 Data contoh berhasil dimuat! "
        "Ganti saldo awal & data bertanda '⚠️ CONTOH' dengan data asli.",
    )


# ---------------------------------------------------------------
# DEFINISI HALAMAN (st.Page — untuk st.navigation)
# ---------------------------------------------------------------
# CATATAN: Semua file halaman ada di folder views/ (BUKAN pages/).
#          Ini sesuai aturan brief: dilarang membuat folder pages/.

halaman_dashboard = st.Page(
    "views/00_dashboard.py",
    title="Dashboard",
    icon="📊",
    default=True,
)

# --- Master Data ---
halaman_master_data = st.Page(
    "views/01_master_data.py",
    title="Master Data",
    icon="🗂️",
)

# --- Input ---
halaman_transaksi = st.Page(
    "views/02_input_transaksi.py",
    title="Input Transaksi",
    icon="✍️",
)
halaman_penggajian = st.Page(
    "views/03_penggajian.py",
    title="Penggajian",
    icon="💼",
)

# --- Jurnal ---
halaman_jurnal_umum = st.Page(
    "views/04_jurnal_umum.py",
    title="Jurnal Umum",
    icon="📓",
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
    icon="📘",
)
halaman_bb_pembantu = st.Page(
    "views/08_buku_besar_pembantu.py",
    title="BB Pembantu",
    icon="🔎",
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
    icon="📋",
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

halaman_manajemen_pengguna = st.Page(
    "views/15_manajemen_pengguna.py",
    title="Manajemen Pengguna",
    icon="👥",
)


# ---------------------------------------------------------------
# LOGIN, SESSION, DAN OTORISASI
# ---------------------------------------------------------------
user_aktif = pengguna_aktif()
if not user_aktif:
    from views.login import tampilkan as tampilkan_login
    tampilkan_login()
    st.stop()

with st.sidebar:
    with st.container(border=True):
        st.markdown(f"## 🌶️ {NAMA_APLIKASI}")
        st.caption("FINANCE & FARM OPERATIONS")
        st.caption(NAMA_PERUSAHAAN)
    st.divider()
    st.caption("PENGGUNA AKTIF")
    st.markdown(f"**{user_aktif['full_name']}**")
    st.caption(f"Peran · {user_aktif['role_name']}")
    if st.button("Keluar", use_container_width=True, key="auth_logout"):
        audit_berhasil = keluar_pengguna(int(user_aktif["id"]))
        if not audit_berhasil:
            st.toast("Sesi ditutup, tetapi catatan logout gagal disimpan.", icon="⚠️")
        st.rerun()

# ---------------------------------------------------------------
# NAVIGASI BERDASARKAN PERMISSION
# ---------------------------------------------------------------
# Permission dari database menjadi sumber keputusan navigasi.
# Setiap halaman tetap memiliki pemeriksaan izin internal sebagai lapisan kedua.
grup_halaman = {
    "BERANDA": [
        ("dashboard.view", halaman_dashboard),
    ],
    "MASTER DATA": [
        ("master_data.view", halaman_master_data),
    ],
    "OPERASIONAL": [
        ("transactions.view", halaman_transaksi),
        ("payroll.manage", halaman_penggajian),
        ("payroll.summary.view", halaman_penggajian),
    ],
    "JURNAL": [
        ("journals.view", halaman_jurnal_umum),
        ("journals.view", halaman_jurnal_khusus),
    ],
    "BUKU BESAR": [
        ("inventory.view", halaman_kartu_persediaan),
        ("ledger.view", halaman_buku_besar),
        ("ledger.view", halaman_bb_pembantu),
    ],
    "LAPORAN": [
        ("reports.view", halaman_neraca_saldo),
        ("reports.manage", halaman_penyesuaian),
        ("reports.view", halaman_neraca_lajur),
        ("reports.view", halaman_laporan_keuangan),
        ("closing.manage", halaman_jurnal_penutup),
    ],
    "ADMINISTRASI": [
        ("backup.access", halaman_backup),
        ("users.manage", halaman_manajemen_pengguna),
    ],
}

navigasi_role = {}
for nama_grup, daftar_halaman in grup_halaman.items():
    halaman_diizinkan = []
    for permission_code, halaman in daftar_halaman:
        # Halaman Penggajian dapat dibuka oleh pengelola maupun pembaca ringkasan.
        if punya_izin(permission_code) and halaman not in halaman_diizinkan:
            halaman_diizinkan.append(halaman)
    if halaman_diizinkan:
        navigasi_role[nama_grup] = halaman_diizinkan

if not navigasi_role:
    st.error("Akun Anda belum memiliki hak akses ke halaman aplikasi mana pun.")
    st.stop()

navigasi = st.navigation(navigasi_role, position="sidebar")
navigasi.run()
