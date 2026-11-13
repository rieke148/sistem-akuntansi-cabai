"""
theme.py
--------
Tujuan  : Menyimpan semua konstanta warna dan gaya terpusat.
          Jika ingin ganti warna, cukup ubah di sini — tidak perlu
          cari satu-persatu di seluruh kode.
Dipanggil oleh : app.py, utils/ui_components.py, semua file views/
"""

# ---------------------------------------------------------------
# PALET WARNA UTAMA (hijau pertanian)
# ---------------------------------------------------------------
WARNA_PRIMER = "#2E7D32"        # hijau tua — tombol utama, header
WARNA_SEKUNDER = "#66BB6A"      # hijau muda — aksen, badge positif
WARNA_LATAR = "#F9FBF9"         # putih kehijauan — latar halaman
WARNA_LATAR2 = "#E8F5E9"        # hijau sangat muda — sidebar/kartu
WARNA_TEKS = "#1B2E1C"          # hijau sangat gelap — teks utama

# ---------------------------------------------------------------
# WARNA STATUS
# ---------------------------------------------------------------
WARNA_SUKSES = "#2E7D32"        # hijau — jurnal seimbang, lunas
WARNA_PERINGATAN = "#F57F17"    # kuning-oranye — mendekati jatuh tempo
WARNA_BAHAYA = "#C62828"        # merah — tidak seimbang, overdue
WARNA_INFO = "#1565C0"          # biru — informasi netral

# ---------------------------------------------------------------
# WARNA GRAFIK (urutan untuk plotly)
# ---------------------------------------------------------------
PALET_GRAFIK = [
    "#2E7D32",  # hijau tua
    "#66BB6A",  # hijau muda
    "#F57F17",  # oranye
    "#1565C0",  # biru
    "#C62828",  # merah
    "#6A1B9A",  # ungu
]

# ---------------------------------------------------------------
# NAMA PERUSAHAAN (agar mudah diubah tanpa ganti banyak file)
# ---------------------------------------------------------------
NAMA_PERUSAHAAN = "PT Sari Subur Langgeng Jaya Hidroponik Farm"
NAMA_APLIKASI = "Sistem Akuntansi Cabai"
VERSI_APLIKASI = "1.0.0"
