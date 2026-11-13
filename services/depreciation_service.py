"""
services/depreciation_service.py
----------------------------------
Tujuan  : Menghitung penyusutan aset tetap (metode garis lurus) dan
          amortisasi perlengkapan (plastik mulsa, umur 1,5 tahun).
Input   : fixed_asset_id atau semua aset aktif, periode.
Output  : Nominal penyusutan per bulan, jurnal penyesuaian otomatis.
Dipanggil oleh : services/adjusting_service.py, views/10_ayat_penyesuaian.py

RUMUS PENYUSUTAN GARIS LURUS:
  Penyusutan per bulan = (Harga Perolehan - Nilai Residu) / (Umur Ekonomis x 12)

  Contoh: Bangunan Rp120.000.000, residu Rp12.000.000, umur 20 tahun:
  Penyusutan/bulan = (120.000.000 - 12.000.000) / (20 x 12)
                   = 108.000.000 / 240
                   = Rp450.000/bulan

CATATAN:
  - Tanah TIDAK disusutkan (is_disusutkan = 0).
  - Umur ekonomis dan nilai residu adalah INPUT MANUAL user di Master Data.
  - Jangan hardcode angka penyusutan.
"""

import pandas as pd
from database.connection import get_connection


def hitung_penyusutan_bulanan(asset_id: int) -> dict:
    """
    Menghitung penyusutan per bulan untuk satu aset tetap.

    Args:
        asset_id : ID aset tetap dari tabel fixed_assets.

    Returns:
        Dict berisi:
        {
          nama_aset, harga_perolehan, nilai_residu,
          umur_ekonomis_tahun, penyusutan_per_bulan,
          dasar_penyusutan  (harga - residu),
          is_disusutkan,
        }

    Raises:
        ValueError: Jika aset tidak ditemukan.
    """
    koneksi = get_connection()
    row = koneksi.execute("""
        SELECT nama_aset, harga_perolehan, nilai_residu,
               umur_ekonomis_tahun, is_disusutkan, jumlah_unit
        FROM fixed_assets
        WHERE id = ?
    """, (asset_id,)).fetchone()
    koneksi.close()

    if not row:
        raise ValueError(f"Aset ID {asset_id} tidak ditemukan.")

    # Tanah tidak disusutkan
    if not row["is_disusutkan"]:
        return {
            "nama_aset": row["nama_aset"],
            "harga_perolehan": int(row["harga_perolehan"]) * int(row["jumlah_unit"]),
            "nilai_residu": 0,
            "umur_ekonomis_tahun": 0,
            "dasar_penyusutan": 0,
            "penyusutan_per_bulan": 0,
            "is_disusutkan": False,
        }

    # Hitung total harga (harga satuan x jumlah unit)
    harga_total = int(row["harga_perolehan"]) * int(row["jumlah_unit"])
    residu_total = int(row["nilai_residu"]) * int(row["jumlah_unit"])
    dasar = harga_total - residu_total
    umur_bulan = int(row["umur_ekonomis_tahun"]) * 12

    # Rumus garis lurus: dasar / umur dalam bulan
    if umur_bulan > 0:
        penyusutan_per_bulan = dasar // umur_bulan  # pembagian integer (Rupiah bulat)
    else:
        penyusutan_per_bulan = 0

    return {
        "nama_aset": row["nama_aset"],
        "harga_perolehan": harga_total,
        "nilai_residu": residu_total,
        "umur_ekonomis_tahun": int(row["umur_ekonomis_tahun"]),
        "dasar_penyusutan": dasar,
        "penyusutan_per_bulan": penyusutan_per_bulan,
        "is_disusutkan": True,
    }


def hitung_semua_penyusutan() -> pd.DataFrame:
    """
    Menghitung penyusutan semua aset aktif yang perlu disusutkan.

    Returns:
        DataFrame: kode_aset | nama_aset | harga_perolehan | nilai_residu |
                   dasar | umur_tahun | penyusutan_per_bulan | akun_beban | akun_akumulasi
    """
    koneksi = get_connection()
    rows = koneksi.execute("""
        SELECT fa.id, fa.kode_aset, fa.nama_aset, fa.harga_perolehan,
               fa.nilai_residu, fa.umur_ekonomis_tahun, fa.jumlah_unit,
               fa.is_disusutkan, a_beban.kode_akun as kode_beban,
               a_akum.kode_akun as kode_akum
        FROM fixed_assets fa
        LEFT JOIN accounts a_beban ON fa.account_id = a_beban.id
        LEFT JOIN accounts a_akum ON fa.account_akum_id = a_akum.id
        WHERE fa.aktif = 1
    """).fetchall()
    koneksi.close()

    hasil = []
    for row in rows:
        detail = hitung_penyusutan_bulanan(row["id"])
        hasil.append({
            "kode_aset": row["kode_aset"],
            "nama_aset": row["nama_aset"],
            "harga_perolehan": detail["harga_perolehan"],
            "nilai_residu": detail["nilai_residu"],
            "dasar_penyusutan": detail["dasar_penyusutan"],
            "umur_ekonomis_tahun": detail["umur_ekonomis_tahun"],
            "penyusutan_per_bulan": detail["penyusutan_per_bulan"],
            "is_disusutkan": detail["is_disusutkan"],
        })

    return pd.DataFrame(hasil)


def hitung_amortisasi_mulsa_bulanan(
    harga_per_blok: int = 400_000,
    jumlah_blok: int = 5,
    umur_tahun: float = 1.5,
) -> int:
    """
    Menghitung amortisasi plastik mulsa per bulan.

    Args:
        harga_per_blok : Harga plastik mulsa per blok (Rp400.000 dari observasi).
        jumlah_blok    : Jumlah blok yang memakai mulsa.
        umur_tahun     : Masa pakai mulsa (1,5 tahun = 18 bulan).

    Returns:
        Amortisasi per bulan dalam Rupiah (integer).

    Rumus:
        Total harga = Rp400.000 x 5 blok = Rp2.000.000
        Amortisasi/bulan = Rp2.000.000 / 18 = Rp111.111/bulan
    """
    total_harga = harga_per_blok * jumlah_blok
    umur_bulan = int(umur_tahun * 12)
    if umur_bulan > 0:
        return total_harga // umur_bulan
    return 0
