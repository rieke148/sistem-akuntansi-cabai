"""
services/subsidiary_service.py
--------------------------------
Tujuan  : Mengelola Buku Besar Pembantu (sub-ledger).
          3 jenis BB Pembantu:
          1. Piutang per pelanggan (dengan umur piutang / aging)
          2. Persediaan per item (dari inventory_movements — rata-rata bergerak)
          3. Aset Tetap (harga perolehan, akumulasi penyusutan, nilai buku)
Input   : customer_id, item_id, atau tanpa filter (semua)
Output  : DataFrame BB Pembantu sesuai jenis.
Dipanggil oleh : views/08_buku_besar_pembantu.py

KONSEP BUKU BESAR PEMBANTU:
  BB Pembantu merupakan rincian (sub-ledger) dari akun kontrol di Buku Besar.
  - BB Piutang → rincian akun 1201 (Piutang Usaha)
  - BB Persediaan → rincian akun 1301-1307 (Persediaan berbagai item)
  - BB Aset Tetap → rincian akun 1401+ (Aset Tetap berbagai jenis)
  Total BB Pembantu HARUS sama dengan saldo akun kontrol di Buku Besar.
"""

import pandas as pd
from database.connection import get_connection
from services.inventory_service import ambil_kartu_persediaan
from services.depreciation_service import hitung_penyusutan_bulanan


def ambil_bb_piutang(customer_id: int | None = None) -> pd.DataFrame:
    """
    Mengembalikan status piutang per faktur per pelanggan.

    Termasuk kolom 'umur_hari' (jumlah hari dari tanggal_faktur sampai hari ini)
    untuk analisis umur piutang (aging analysis).

    Args:
        customer_id : Filter per pelanggan. None = semua pelanggan.

    Returns:
        DataFrame: no_faktur | pelanggan | tanggal_faktur | tanggal_jatuh_tempo |
                   jumlah | jumlah_terbayar | sisa_piutang | status | umur_hari

    Keterangan kolom:
        umur_hari    : Jumlah hari sejak faktur diterbitkan
        sisa_piutang : jumlah - jumlah_terbayar (belum lunas)
    """
    koneksi = get_connection()
    try:
        if customer_id is not None:
            rows = koneksi.execute(
                """
                SELECT
                    r.id,
                    r.no_faktur,
                    c.nama AS pelanggan,
                    r.tanggal_faktur,
                    r.tanggal_jatuh_tempo AS tanggal_jatuh_tempo,
                    r.jumlah AS jumlah,
                    r.jumlah_terbayar,
                    (r.jumlah - r.jumlah_terbayar) AS sisa_piutang,
                    r.status,
                    CAST(julianday('now') - julianday(r.tanggal_faktur) AS INTEGER)
                        AS umur_hari
                FROM receivables r
                LEFT JOIN customers c ON r.customer_id = c.id
                WHERE r.customer_id = ?
                ORDER BY r.tanggal_jatuh_tempo ASC
                """,
                (customer_id,)
            ).fetchall()
        else:
            rows = koneksi.execute(
                """
                SELECT
                    r.id,
                    r.no_faktur,
                    c.nama AS pelanggan,
                    r.tanggal_faktur,
                    r.tanggal_jatuh_tempo AS tanggal_jatuh_tempo,
                    r.jumlah AS jumlah,
                    r.jumlah_terbayar,
                    (r.jumlah - r.jumlah_terbayar) AS sisa_piutang,
                    r.status,
                    CAST(julianday('now') - julianday(r.tanggal_faktur) AS INTEGER)
                        AS umur_hari
                FROM receivables r
                LEFT JOIN customers c ON r.customer_id = c.id
                ORDER BY r.tanggal_jatuh_tempo ASC
                """,
            ).fetchall()
    finally:
        koneksi.close()

    if not rows:
        return pd.DataFrame(columns=[
            "no_faktur", "pelanggan", "tanggal_faktur",
            "tanggal_jatuh_tempo", "jumlah", "jumlah_terbayar",
            "sisa_piutang", "status", "umur_hari",
        ])

    return pd.DataFrame([dict(r) for r in rows])


def ambil_ringkasan_piutang_per_pelanggan() -> pd.DataFrame:
    """
    Merangkum piutang per pelanggan: total sisa piutang dan jumlah faktur aktif.

    Returns:
        DataFrame: pelanggan | total_piutang | jumlah_faktur | faktur_jatuh_tempo

    Dipakai untuk tampilan ringkasan di tab BB Piutang.
    """
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            """
            SELECT
                c.id AS customer_id,
                c.nama AS pelanggan,
                COUNT(r.id) AS jumlah_faktur,
                SUM(r.jumlah - r.jumlah_terbayar) AS total_piutang,
                SUM(CASE
                    WHEN date('now') > r.tanggal_jatuh_tempo AND r.status != 'lunas'
                    THEN 1 ELSE 0
                END) AS faktur_jatuh_tempo
            FROM receivables r
            JOIN customers c ON r.customer_id = c.id
            WHERE r.status != 'lunas'
            GROUP BY r.customer_id, c.nama
            ORDER BY total_piutang DESC
            """
        ).fetchall()
    finally:
        koneksi.close()

    if not rows:
        return pd.DataFrame(columns=[
            "customer_id", "pelanggan", "jumlah_faktur",
            "total_piutang", "faktur_jatuh_tempo"
        ])

    return pd.DataFrame([dict(r) for r in rows])


def ambil_bb_persediaan(item_id: int | None = None) -> pd.DataFrame:
    """
    Mengembalikan kartu persediaan per item dengan format BB Pembantu.
    Memanfaatkan inventory_service.ambil_kartu_persediaan() yang sudah ada.

    Args:
        item_id : ID item. Jika None, kembalikan DataFrame kosong.

    Returns:
        DataFrame: tanggal | keterangan | masuk_qty | masuk_nilai |
                   keluar_qty | keluar_nilai | saldo_qty | saldo_nilai | harga_rata2

    Kolom dijelaskan:
        masuk_qty   : Jumlah masuk (0 jika tipe_gerakan = 'keluar')
        masuk_nilai : Nilai masuk dalam Rupiah
        keluar_qty  : Jumlah keluar (0 jika tipe_gerakan = 'masuk')
        keluar_nilai: Nilai keluar dalam Rupiah
        saldo_qty   : Saldo kuantitas kumulatif
        saldo_nilai : Saldo nilai kumulatif
        harga_rata2 : Harga rata-rata bergerak saat itu
    """
    if item_id is None:
        return pd.DataFrame(columns=[
            "tanggal", "keterangan", "masuk_qty", "masuk_nilai",
            "keluar_qty", "keluar_nilai", "saldo_qty", "saldo_nilai", "harga_rata2",
        ])

    # Panggil fungsi inventory_service yang sudah ada
    df_mentah = ambil_kartu_persediaan(item_id)

    if df_mentah.empty:
        return pd.DataFrame(columns=[
            "tanggal", "keterangan", "masuk_qty", "masuk_nilai",
            "keluar_qty", "keluar_nilai", "saldo_qty", "saldo_nilai", "harga_rata2",
        ])

    # Konversi format: pisahkan masuk dan keluar ke kolom terpisah
    baris_format = []
    for _, row in df_mentah.iterrows():
        tipe = row.get("tipe_gerakan", "masuk")
        qty = float(row.get("qty", 0))
        total_nilai = int(row.get("total_nilai", 0))

        if tipe == "masuk":
            masuk_qty, masuk_nilai = qty, total_nilai
            keluar_qty, keluar_nilai = 0.0, 0
        else:
            masuk_qty, masuk_nilai = 0.0, 0
            keluar_qty, keluar_nilai = qty, total_nilai

        baris_format.append({
            "tanggal": row.get("tanggal", ""),
            "keterangan": row.get("keterangan", ""),
            "masuk_qty": masuk_qty,
            "masuk_nilai": masuk_nilai,
            "keluar_qty": keluar_qty,
            "keluar_nilai": keluar_nilai,
            "saldo_qty": float(row.get("saldo_qty", 0)),
            "saldo_nilai": int(row.get("saldo_nilai", 0)),
            "harga_rata2": int(row.get("harga_rata2", 0)),
        })

    return pd.DataFrame(baris_format)


def ambil_bb_aset_tetap() -> pd.DataFrame:
    """
    Mengembalikan daftar aset tetap dengan akumulasi penyusutan dan nilai buku.

    Akumulasi penyusutan = penyusutan per bulan × jumlah bulan sejak perolehan.
    Nilai buku = Harga Perolehan - Akumulasi Penyusutan.
    Tanah (is_disusutkan=0) → akumulasi_penyusutan = 0, nilai_buku = harga_perolehan.

    Returns:
        DataFrame: kode_aset | nama_aset | kategori_aset | tanggal_perolehan |
                   harga_perolehan | akumulasi_penyusutan | nilai_buku |
                   umur_ekonomis_tahun | nilai_residu | is_disusutkan

    Rumus:
        jumlah_bulan = months since tanggal_perolehan until now
        akumulasi = penyusutan_per_bulan × jumlah_bulan
        (dibatasi maksimum = dasar_penyusutan = harga - residu)
    """
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            """
            SELECT
                fa.id,
                fa.kode_aset,
                fa.nama_aset,
                fa.kategori_aset,
                fa.tanggal_perolehan,
                fa.harga_perolehan * fa.jumlah_unit AS harga_perolehan,
                fa.nilai_residu * fa.jumlah_unit AS nilai_residu,
                fa.umur_ekonomis_tahun,
                fa.jumlah_unit,
                fa.is_disusutkan,
                fa.tanggal_perolehan AS tgl_awal
            FROM fixed_assets fa
            WHERE fa.aktif = 1
            ORDER BY fa.kode_aset
            """
        ).fetchall()
    finally:
        koneksi.close()

    if not rows:
        return pd.DataFrame(columns=[
            "kode_aset", "nama_aset", "kategori_aset", "tanggal_perolehan",
            "harga_perolehan", "akumulasi_penyusutan", "nilai_buku",
            "umur_ekonomis_tahun", "nilai_residu", "is_disusutkan"
        ])

    hasil = []
    for row in rows:
        asset_id = row["id"]
        harga = int(row["harga_perolehan"])
        residu = int(row["nilai_residu"])
        is_disusutkan = bool(row["is_disusutkan"])
        tgl_perolehan = row["tanggal_perolehan"]

        if not is_disusutkan:
            # Tanah: tidak ada penyusutan
            akumulasi = 0
            nilai_buku = harga
        else:
            # Hitung jumlah bulan sejak tanggal perolehan
            detail = hitung_penyusutan_bulanan(asset_id)
            penyusutan_per_bulan = detail["penyusutan_per_bulan"]

            # Hitung bulan antara tanggal_perolehan dan sekarang
            from datetime import date
            try:
                tgl_awal = date.fromisoformat(tgl_perolehan)
                hari_ini = date.today()
                # Hitung selisih bulan
                jumlah_bulan = (hari_ini.year - tgl_awal.year) * 12 + \
                               (hari_ini.month - tgl_awal.month)
                jumlah_bulan = max(0, jumlah_bulan)
            except (ValueError, TypeError):
                jumlah_bulan = 0

            # Akumulasi tidak boleh melebihi dasar penyusutan (harga - residu)
            dasar = harga - residu
            akumulasi = min(penyusutan_per_bulan * jumlah_bulan, dasar)
            nilai_buku = harga - akumulasi

        hasil.append({
            "kode_aset": row["kode_aset"],
            "nama_aset": row["nama_aset"],
            "kategori_aset": row["kategori_aset"],
            "tanggal_perolehan": tgl_perolehan,
            "harga_perolehan": harga,
            "akumulasi_penyusutan": akumulasi,
            "nilai_buku": nilai_buku,
            "umur_ekonomis_tahun": int(row["umur_ekonomis_tahun"] or 0),
            "nilai_residu": residu,
            "is_disusutkan": is_disusutkan,
        })

    return pd.DataFrame(hasil)


def ambil_bb_utang() -> pd.DataFrame:
    """
    Mengembalikan ringkasan utang usaha dari jurnal pembelian kredit.
    Utang = pembelian yang dibayar kredit (belum lunas).

    Catatan: Berdasarkan observasi di lapangan, sebagian besar pembelian
    dilakukan secara tunai. Data ini menampilkan entri kredit dari jurnal.

    Returns:
        DataFrame: supplier | total_utang | keterangan
    """
    koneksi = get_connection()
    try:
        # Cari akun Utang Usaha (kode 2101)
        akun_utang = koneksi.execute(
            "SELECT id FROM accounts WHERE kode_akun = '2101'"
        ).fetchone()

        if not akun_utang:
            return pd.DataFrame(columns=["supplier", "total_utang", "keterangan"])

        akun_utang_id = akun_utang["id"]

        # Ambil total kredit ke akun Utang Usaha per pihak terkait (supplier)
        rows = koneksi.execute(
            """
            SELECT
                COALESCE(je.pihak_terkait, 'Tidak Diketahui') AS supplier,
                SUM(jl.kredit) AS total_utang,
                COUNT(DISTINCT je.id) AS jumlah_transaksi
            FROM journal_lines jl
            JOIN journal_entries je ON jl.journal_entry_id = je.id
            WHERE jl.account_id = ?
              AND jl.kredit > 0
            GROUP BY je.pihak_terkait
            ORDER BY total_utang DESC
            """,
            (akun_utang_id,)
        ).fetchall()
    finally:
        koneksi.close()

    if not rows:
        return pd.DataFrame(columns=["supplier", "total_utang", "jumlah_transaksi"])

    return pd.DataFrame([dict(r) for r in rows])
