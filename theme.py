"""
theme.py
--------
Tujuan  : Menyimpan palet warna dan identitas visual aplikasi.
          Seluruh warna UI mengambil konstanta dari file ini.
Dipanggil oleh : app.py, utils/ui_components.py, dan halaman views/.
"""

# Palet Enterprise: emerald sebagai aksen, slate sebagai warna netral.
WARNA_PRIMER = "#147D64"
WARNA_SEKUNDER = "#D6A84B"
WARNA_LATAR = "#F7F9FC"
WARNA_LATAR2 = "#EEF3F7"
WARNA_TEKS = "#182230"
WARNA_NAVIGASI = "#172536"
WARNA_PERMUKAAN = "#FFFFFF"
WARNA_GARIS = "#DCE4EC"

# Warna status yang konsisten pada seluruh halaman.
WARNA_SUKSES = "#16845B"
WARNA_PERINGATAN = "#C58A1B"
WARNA_BAHAYA = "#C44747"
WARNA_INFO = "#3976B8"

# Palet grafik dengan kontras yang cukup untuk laporan keuangan.
PALET_GRAFIK = [
    "#147D64",
    "#3976B8",
    "#D6A84B",
    "#7A69A8",
    "#C76D4D",
    "#60758A",
]

NAMA_PERUSAHAAN = "PT Sari Subur Langgeng Jaya Hidroponik Farm"
NAMA_APLIKASI = "Sistem Akuntansi Cabai"
VERSI_APLIKASI = "1.1.0"
