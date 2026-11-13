"""
services/special_journal_service.py
--------------------------------------
Tujuan  : Menyediakan data 4 Jurnal Khusus dalam format kolom tradisional.
          Jurnal Khusus adalah jurnal dengan format kolom spesifik per jenis
          transaksi — bukan semua akun tampil per baris, tapi per KOLOM.

Input   : period_id (int atau None untuk semua periode)
Output  : DataFrame berformat kolom tradisional, siap ditampilkan di views/

Dipanggil oleh : views/05_jurnal_khusus.py

LOGIKA PIVOT:
  Setiap jurnal khusus = ambil journal_entries dengan journal_type tertentu,
  lalu pivot journal_lines menjadi kolom-kolom khusus menggunakan CASE WHEN.
  Contoh Cash Receipt: 1 baris = 1 transaksi, kolom = Kas (D), Piutang (K), dll.

CATATAN PENTING (dari brief):
  Dari observasi lapangan, semua pembelian dilakukan TUNAI.
  Jurnal Pembelian (kredit) praktis kosong untuk data asli.
  Seed data berisi 1-2 contoh sebagai simulasi untuk keperluan tugas.
"""

import pandas as pd
from database.connection import get_connection


# ================================================================
# 1. SALES JOURNAL (JURNAL PENJUALAN TEMPO)
# ================================================================

def ambil_jurnal_penjualan(period_id: int | None = None) -> pd.DataFrame:
    """
    Mengambil data Sales Journal (Jurnal Penjualan Tempo).

    Format kolom tradisional:
      Tanggal | No Faktur | Pelanggan | Jatuh Tempo | Ref | Piutang (D) | Penjualan (K)

    Sumber: journal_entries dengan journal_type = 'penjualan'
    JOIN receivables untuk mendapatkan tanggal jatuh tempo.

    Args:
        period_id : Filter per periode (None = semua periode).

    Returns:
        DataFrame kolom: tanggal, no_faktur, pelanggan, jatuh_tempo,
                         piutang_d, penjualan_k
    """
    kondisi = "WHERE je.journal_type = 'penjualan'"
    params: list = []

    if period_id is not None:
        kondisi += " AND je.period_id = ?"
        params.append(period_id)

    sql = f"""
        SELECT
            je.id           AS entry_id,
            je.tanggal,
            je.no_bukti     AS no_faktur,
            COALESCE(je.pihak_terkait, '-') AS pelanggan,
            COALESCE(r.tanggal_jatuh_tempo, '-')    AS jatuh_tempo,
            -- Piutang (D): debit ke akun piutang (12xx)
            SUM(CASE WHEN a.kode_akun LIKE '12%' AND jl.debit  > 0
                     THEN jl.debit  ELSE 0 END) AS piutang_d,
            -- Penjualan (K): kredit ke akun pendapatan (4xxx)
            SUM(CASE WHEN a.kode_akun LIKE '4%'  AND jl.kredit > 0
                     THEN jl.kredit ELSE 0 END) AS penjualan_k
        FROM journal_entries je
        JOIN journal_lines jl ON je.id = jl.journal_entry_id
        JOIN accounts a ON jl.account_id = a.id
        LEFT JOIN receivables r ON je.id = r.journal_entry_id
        {kondisi}
        GROUP BY je.id, je.tanggal, je.no_bukti, je.pihak_terkait, r.tanggal_jatuh_tempo
        ORDER BY je.tanggal, je.id
    """
    koneksi = get_connection()
    df = pd.read_sql_query(sql, koneksi, params=params if params else None)
    koneksi.close()
    return df


# ================================================================
# 2. PURCHASE JOURNAL (JURNAL PEMBELIAN KREDIT)
# ================================================================

def ambil_jurnal_pembelian(period_id: int | None = None) -> pd.DataFrame:
    """
    Mengambil data Purchase Journal (Jurnal Pembelian Kredit).

    Format kolom tradisional:
      Tanggal | No Faktur | Supplier | Ref | Persediaan (D) | Utang Usaha (K)

    Catatan: Dari observasi, semua pembelian dilakukan TUNAI.
    Jurnal ini praktis kosong untuk data asli; berisi data simulasi saja.

    Args:
        period_id : Filter per periode (None = semua periode).

    Returns:
        DataFrame kolom: tanggal, no_faktur, supplier, persediaan_d, utang_k
    """
    kondisi = "WHERE je.journal_type = 'pembelian'"
    params: list = []

    if period_id is not None:
        kondisi += " AND je.period_id = ?"
        params.append(period_id)

    sql = f"""
        SELECT
            je.id           AS entry_id,
            je.tanggal,
            je.no_bukti     AS no_faktur,
            COALESCE(je.pihak_terkait, '-') AS supplier,
            -- Persediaan (D): debit ke akun persediaan bahan (13xx)
            SUM(CASE WHEN a.kode_akun LIKE '13%' AND jl.debit  > 0
                     THEN jl.debit  ELSE 0 END) AS persediaan_d,
            -- Utang Usaha (K): kredit ke akun utang usaha (2101)
            SUM(CASE WHEN a.kode_akun = '2101'   AND jl.kredit > 0
                     THEN jl.kredit ELSE 0 END) AS utang_k
        FROM journal_entries je
        JOIN journal_lines jl ON je.id = jl.journal_entry_id
        JOIN accounts a ON jl.account_id = a.id
        {kondisi}
        GROUP BY je.id, je.tanggal, je.no_bukti, je.pihak_terkait
        ORDER BY je.tanggal, je.id
    """
    koneksi = get_connection()
    df = pd.read_sql_query(sql, koneksi, params=params if params else None)
    koneksi.close()
    return df


# ================================================================
# 3. CASH RECEIPT JOURNAL (JURNAL PENERIMAAN KAS)
# ================================================================

def ambil_jurnal_penerimaan_kas(period_id: int | None = None) -> pd.DataFrame:
    """
    Mengambil data Cash Receipt Journal (Jurnal Penerimaan Kas).

    Format kolom tradisional:
      Tanggal | No Bukti | Keterangan | Pihak Terkait | Ref |
      Kas (D) | Piutang (K) | Penjualan (K) | Lain-lain (K)

    Pivot kolom:
      kas_d       = debit ke Kas/Bank (110x)
      piutang_k   = kredit ke Piutang Usaha (12xx) → pelunasan piutang
      penjualan_k = kredit ke Penjualan/Pendapatan (4xxx)
      lain_lain_k = kredit ke akun lain (mis. Modal Disetor)

    Validasi: kas_d == piutang_k + penjualan_k + lain_lain_k (per baris)

    Args:
        period_id : Filter per periode (None = semua periode).
    """
    kondisi = "WHERE je.journal_type = 'penerimaan_kas'"
    params: list = []

    if period_id is not None:
        kondisi += " AND je.period_id = ?"
        params.append(period_id)

    sql = f"""
        SELECT
            je.id           AS entry_id,
            je.tanggal,
            je.no_bukti,
            je.keterangan,
            COALESCE(je.pihak_terkait, '-') AS pihak_terkait,
            -- Kas (D): debit ke kas atau bank (110x)
            SUM(CASE WHEN a.kode_akun LIKE '110%' AND jl.debit  > 0
                     THEN jl.debit  ELSE 0 END) AS kas_d,
            -- Piutang (K): kredit ke piutang usaha (pelunasan dari pelanggan)
            SUM(CASE WHEN a.kode_akun LIKE '12%'  AND jl.kredit > 0
                     THEN jl.kredit ELSE 0 END) AS piutang_k,
            -- Penjualan (K): kredit ke akun pendapatan (4xxx)
            SUM(CASE WHEN a.kode_akun LIKE '4%'   AND jl.kredit > 0
                     THEN jl.kredit ELSE 0 END) AS penjualan_k,
            -- Lain-lain (K): kredit ke akun selain piutang dan penjualan
            SUM(CASE WHEN a.kode_akun NOT LIKE '110%'
                          AND a.kode_akun NOT LIKE '12%'
                          AND a.kode_akun NOT LIKE '4%'
                          AND jl.kredit > 0
                     THEN jl.kredit ELSE 0 END) AS lain_lain_k
        FROM journal_entries je
        JOIN journal_lines jl ON je.id = jl.journal_entry_id
        JOIN accounts a ON jl.account_id = a.id
        {kondisi}
        GROUP BY je.id, je.tanggal, je.no_bukti, je.keterangan, je.pihak_terkait
        ORDER BY je.tanggal, je.id
    """
    koneksi = get_connection()
    df = pd.read_sql_query(sql, koneksi, params=params if params else None)
    koneksi.close()
    return df


# ================================================================
# 4. CASH PAYMENT JOURNAL (JURNAL PENGELUARAN KAS)
# ================================================================

def ambil_jurnal_pengeluaran_kas(period_id: int | None = None) -> pd.DataFrame:
    """
    Mengambil data Cash Payment Journal (Jurnal Pengeluaran Kas).

    Format kolom tradisional:
      Tanggal | No Bukti | Keterangan | Pihak Terkait | Ref |
      Kas (K) | Persediaan (D) | Beban Upah (D) | Beban Ops (D) | Lain-lain (D)

    Pivot kolom:
      kas_k           = kredit ke Kas/Bank (110x) → uang keluar
      persediaan_d    = debit ke Persediaan bahan (13xx) → beli bahan tunai
      beban_upah_d    = debit ke Beban Upah (5101)
      beban_produksi_d= debit ke Beban Produksi lain (5xxx selain upah)
      beban_ops_d     = debit ke Beban Operasional (6xxx: listrik, BBM, traktor)
      lain_lain_d     = debit ke akun lain (mis. aset tetap saat beli aset)

    Validasi: kas_k == sum semua kolom debit (per baris)

    Args:
        period_id : Filter per periode (None = semua periode).
    """
    kondisi = "WHERE je.journal_type = 'pengeluaran_kas'"
    params: list = []

    if period_id is not None:
        kondisi += " AND je.period_id = ?"
        params.append(period_id)

    sql = f"""
        SELECT
            je.id           AS entry_id,
            je.tanggal,
            je.no_bukti,
            je.keterangan,
            COALESCE(je.pihak_terkait, '-') AS pihak_terkait,
            -- Kas (K): kredit ke kas — uang keluar
            SUM(CASE WHEN a.kode_akun LIKE '110%' AND jl.kredit > 0
                     THEN jl.kredit ELSE 0 END) AS kas_k,
            -- Persediaan (D): debit ke persediaan bahan (beli tunai)
            SUM(CASE WHEN a.kode_akun LIKE '13%'  AND jl.debit  > 0
                     THEN jl.debit  ELSE 0 END) AS persediaan_d,
            -- Beban Upah (D): debit ke akun upah/gaji (5101)
            SUM(CASE WHEN a.kode_akun = '5101'    AND jl.debit  > 0
                     THEN jl.debit  ELSE 0 END) AS beban_upah_d,
            -- Beban Produksi Lain (D): debit ke beban produksi selain upah (5102-5107)
            SUM(CASE WHEN a.kode_akun LIKE '5%'
                          AND a.kode_akun != '5101'
                          AND jl.debit  > 0
                     THEN jl.debit  ELSE 0 END) AS beban_produksi_d,
            -- Beban Operasional (D): listrik, BBM, sewa traktor (6xxx)
            SUM(CASE WHEN a.kode_akun LIKE '6%'   AND jl.debit  > 0
                     THEN jl.debit  ELSE 0 END) AS beban_ops_d,
            -- Lain-lain (D): akun lain seperti aset tetap saat beli aset
            SUM(CASE WHEN a.kode_akun NOT LIKE '110%'
                          AND a.kode_akun NOT LIKE '13%'
                          AND a.kode_akun NOT LIKE '5%'
                          AND a.kode_akun NOT LIKE '6%'
                          AND jl.debit  > 0
                     THEN jl.debit  ELSE 0 END) AS lain_lain_d
        FROM journal_entries je
        JOIN journal_lines jl ON je.id = jl.journal_entry_id
        JOIN accounts a ON jl.account_id = a.id
        {kondisi}
        GROUP BY je.id, je.tanggal, je.no_bukti, je.keterangan, je.pihak_terkait
        ORDER BY je.tanggal, je.id
    """
    koneksi = get_connection()
    df = pd.read_sql_query(sql, koneksi, params=params if params else None)
    koneksi.close()
    return df


# ================================================================
# HELPER: HITUNG TOTAL KOLOM
# ================================================================

def hitung_total_kolom(df: pd.DataFrame, kolom_angka: list[str]) -> dict:
    """
    Menghitung total setiap kolom numerik dari DataFrame jurnal khusus.

    Args:
        df          : DataFrame hasil ambil_jurnal_xxx().
        kolom_angka : Daftar nama kolom yang berisi angka (mis. ['kas_d', 'penjualan_k']).

    Returns:
        Dict {nama_kolom: total_integer}.
    """
    return {col: int(df[col].sum()) for col in kolom_angka if col in df.columns}
