"""
services/dashboard_service.py
------------------------------
Tujuan  : Menyediakan data ringkasan untuk halaman Dashboard.
          Semua fungsi mengambil data dari database dan mengembalikan
          nilai/dict/DataFrame — tanpa import streamlit.
Input   : period_id (ID periode aktif)
Output  : dict / int / list untuk ditampilkan di views/00_dashboard.py
Dipanggil oleh : views/00_dashboard.py

CATATAN: Semua nominal uang sebagai integer Rupiah (bukan float).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from database.connection import get_connection


# ---------------------------------------------------------------
# RINGKASAN KAS & BANK
# ---------------------------------------------------------------
def ambil_saldo_kas_bank(period_id: int) -> dict[str, int]:
    """
    Mengembalikan saldo Kas (1101) dan Bank BRI (1102) dari
    neraca saldo periode ini (saldo_debit - saldo_kredit dari journal_lines).

    Returns:
        dict dengan keys: 'kas', 'bank', 'total'
    """
    sql = """
        SELECT a.kode_akun,
               SUM(jl.debit) - SUM(jl.kredit) AS saldo
        FROM journal_lines jl
        JOIN journal_entries je ON jl.journal_entry_id = je.id
        JOIN accounts a ON jl.account_id = a.id
        WHERE je.period_id = ?
          AND a.kode_akun IN ('1101', '1102')
        GROUP BY a.kode_akun
    """
    conn = get_connection()
    rows = conn.execute(sql, (period_id,)).fetchall()

    # Saldo awal dari opening_balances
    sql_ob = """
        SELECT a.kode_akun,
               ob.saldo_debit - ob.saldo_kredit AS saldo
        FROM opening_balances ob
        JOIN accounts a ON ob.account_id = a.id
        WHERE ob.period_id = ?
          AND a.kode_akun IN ('1101', '1102')
    """
    rows_ob = conn.execute(sql_ob, (period_id,)).fetchall()

    # Gabungkan: saldo awal + mutasi
    peta: dict[str, int] = {}
    for r in rows_ob:
        peta[r["kode_akun"]] = int(r["saldo"] or 0)
    for r in rows:
        peta[r["kode_akun"]] = peta.get(r["kode_akun"], 0) + int(r["saldo"] or 0)

    kas = peta.get("1101", 0)
    bank = peta.get("1102", 0)
    return {"kas": kas, "bank": bank, "total": kas + bank}


# ---------------------------------------------------------------
# PIUTANG OVERDUE
# ---------------------------------------------------------------
def ambil_piutang_overdue(hari_ini: date | None = None) -> list[dict]:
    """
    Mengembalikan daftar faktur piutang yang sudah jatuh tempo dan belum lunas.

    Returns:
        List dict: no_faktur, pelanggan, jumlah, jatuh_tempo, hari_telat
    """
    if hari_ini is None:
        hari_ini = date.today()

    sql = """
        SELECT r.no_faktur,
               COALESCE(c.nama, je.pihak_terkait, 'Tidak Diketahui') AS pelanggan,
               r.jumlah - r.jumlah_terbayar AS sisa_piutang,
               r.tanggal_jatuh_tempo,
               CAST(julianday(?) - julianday(r.tanggal_jatuh_tempo) AS INTEGER) AS hari_telat
        FROM receivables r
        LEFT JOIN customers c ON r.customer_id = c.id
        LEFT JOIN journal_entries je ON r.journal_entry_id = je.id
        WHERE r.status IN ('belum_lunas', 'sebagian')
          AND r.tanggal_jatuh_tempo < ?
        ORDER BY r.tanggal_jatuh_tempo
    """
    conn = get_connection()
    rows = conn.execute(sql, (str(hari_ini), str(hari_ini))).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------
# RINGKASAN PENJUALAN VS BEBAN PERIODE INI
# ---------------------------------------------------------------
def ambil_ringkasan_penjualan_beban(period_id: int) -> dict[str, int]:
    """
    Menghitung penjualan, HPP Penjualan (akun 5108), dan total beban produksi.

    Laba kotor dihitung sebagai penjualan dikurangi HPP Penjualan saja;
    beban produksi lainnya tetap disajikan terpisah.

    Returns:
        dict: 'penjualan', 'hpp_penjualan', 'laba_kotor',
              'beban', 'beban_produksi_lain', 'laba_setelah_beban_produksi'
    """
    sql = """
        SELECT
            SUM(CASE WHEN a.kode_akun LIKE '4%' AND jl.kredit > 0
                     THEN jl.kredit ELSE 0 END) AS penjualan,
            SUM(CASE WHEN a.kode_akun LIKE '5%' AND jl.debit > 0
                     THEN jl.debit ELSE 0 END) AS beban,
            SUM(CASE WHEN a.kode_akun = '5108' AND jl.debit > 0
                     THEN jl.debit ELSE 0 END) AS hpp_penjualan
        FROM journal_lines jl
        JOIN journal_entries je ON jl.journal_entry_id = je.id
        JOIN accounts a ON jl.account_id = a.id
        WHERE je.period_id = ?
          AND je.no_bukti NOT LIKE 'JP-%'
    """
    conn = get_connection()
    try:
        row = conn.execute(sql, (period_id,)).fetchone()
    finally:
        conn.close()

    penjualan = int(row["penjualan"] or 0)
    beban = int(row["beban"] or 0)
    hpp_penjualan = int(row["hpp_penjualan"] or 0)
    beban_produksi_lain = beban - hpp_penjualan
    return {
        "penjualan": penjualan,
        "hpp_penjualan": hpp_penjualan,
        "laba_kotor": penjualan - hpp_penjualan,
        "beban": beban,
        "beban_produksi_lain": beban_produksi_lain,
        "laba_setelah_beban_produksi": penjualan - beban,
    }


# ---------------------------------------------------------------
# STOK PERSEDIAAN TERKINI
# ---------------------------------------------------------------
def ambil_stok_persediaan() -> list[dict]:
    """
    Mengembalikan saldo stok terakhir per item dari inventory_movements.
    Mengambil baris terakhir (ID terbesar) per item.

    Returns:
        List dict: kode_item, nama_item, satuan, saldo_qty, saldo_nilai
    """
    sql = """
        SELECT i.kode_item, i.nama_item, i.satuan,
               im.saldo_qty, im.saldo_nilai
        FROM inventory_movements im
        JOIN items i ON im.item_id = i.id
        WHERE im.id = (
            SELECT MAX(im2.id)
            FROM inventory_movements im2
            WHERE im2.item_id = im.item_id
        )
        ORDER BY i.kode_item
    """
    conn = get_connection()
    rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------
# RINGKASAN JURNAL PERIODE
# ---------------------------------------------------------------
def ambil_ringkasan_jurnal(period_id: int) -> dict[str, int]:
    """
    Menghitung jumlah transaksi per jenis jurnal periode ini.

    Returns:
        dict: total_transaksi, penjualan, pembelian, penerimaan_kas, pengeluaran_kas, umum
    """
    sql = """
        SELECT journal_type, COUNT(*) AS jumlah
        FROM journal_entries
        WHERE period_id = ?
          AND no_bukti NOT LIKE 'PA-%'
          AND no_bukti NOT LIKE 'JP-%'
        GROUP BY journal_type
    """
    conn = get_connection()
    rows = conn.execute(sql, (period_id,)).fetchall()
    peta = {r["journal_type"]: int(r["jumlah"]) for r in rows}
    total = sum(peta.values())
    return {
        "total_transaksi": total,
        "penjualan": peta.get("penjualan", 0),
        "pembelian": peta.get("pembelian", 0),
        "penerimaan_kas": peta.get("penerimaan_kas", 0),
        "pengeluaran_kas": peta.get("pengeluaran_kas", 0),
        "umum": peta.get("umum", 0),
    }


# ---------------------------------------------------------------
# PROGRESS SIKLUS AKUNTANSI
# ---------------------------------------------------------------
def cek_progress_siklus(period_id: int) -> dict[str, bool]:
    """
    Memeriksa apakah setiap tahapan siklus akuntansi sudah dilakukan
    untuk periode ini.

    Returns:
        dict bool: ada_transaksi, ada_penyesuaian, ada_penutup, periode_tutup
    """
    conn = get_connection()

    # Apakah ada transaksi (jurnal selain penyesuaian/penutup)?
    baris_transaksi = conn.execute(
        """SELECT COUNT(*) AS n FROM journal_entries
           WHERE period_id = ? AND no_bukti NOT LIKE 'PA-%' AND no_bukti NOT LIKE 'JP-%'""",
        (period_id,),
    ).fetchone()
    ada_transaksi = int(baris_transaksi["n"]) > 0

    # Apakah ada ayat penyesuaian?
    baris_pa = conn.execute(
        "SELECT COUNT(*) AS n FROM journal_entries WHERE period_id = ? AND no_bukti LIKE 'PA-%'",
        (period_id,),
    ).fetchone()
    ada_penyesuaian = int(baris_pa["n"]) > 0

    # Apakah ada jurnal penutup?
    baris_jp = conn.execute(
        "SELECT COUNT(*) AS n FROM journal_entries WHERE period_id = ? AND no_bukti LIKE 'JP-%'",
        (period_id,),
    ).fetchone()
    ada_penutup = int(baris_jp["n"]) > 0

    # Status periode
    baris_periode = conn.execute(
        "SELECT status FROM periods WHERE id = ?", (period_id,)
    ).fetchone()
    periode_tutup = baris_periode is not None and baris_periode["status"] == "tutup"

    return {
        "ada_transaksi": ada_transaksi,
        "ada_penyesuaian": ada_penyesuaian,
        "ada_penutup": ada_penutup,
        "periode_tutup": periode_tutup,
    }


# ---------------------------------------------------------------
# DATA GRAFIK: PENJUALAN PER KOMODITAS
# ---------------------------------------------------------------
def ambil_penjualan_per_komoditas(period_id: int) -> pd.DataFrame:
    """
    Menghitung total penjualan (kredit ke akun 4xxx) per komoditas.

    Returns:
        DataFrame kolom: komoditas, penjualan
    """
    sql = """
        SELECT je.komoditas,
               SUM(jl.kredit) AS penjualan
        FROM journal_lines jl
        JOIN journal_entries je ON jl.journal_entry_id = je.id
        JOIN accounts a ON jl.account_id = a.id
        WHERE je.period_id = ?
          AND je.journal_type = 'penjualan'
          AND a.kode_akun LIKE '4%'
          AND jl.kredit > 0
        GROUP BY je.komoditas
        ORDER BY penjualan DESC
    """
    conn = get_connection()
    rows = conn.execute(sql, (period_id,)).fetchall()
    if not rows:
        return pd.DataFrame(columns=["komoditas", "penjualan"])
    df = pd.DataFrame([dict(r) for r in rows])
    df["penjualan"] = df["penjualan"].astype(int)
    return df


# ---------------------------------------------------------------
# PERIODE AKTIF
# ---------------------------------------------------------------
def ambil_period_id_aktif() -> int | None:
    """
    Mengembalikan ID periode yang berstatus 'buka' terbaru.
    Returns None jika tidak ada periode aktif.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM periods WHERE status = 'buka' ORDER BY tahun DESC, bulan DESC LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


def ambil_info_periode(period_id: int) -> dict | None:
    """
    Mengembalikan info periode (tahun, bulan, nama_bulan, status).
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT id, tahun, bulan, nama_bulan, status FROM periods WHERE id = ?",
        (period_id,),
    ).fetchone()
    return dict(row) if row else None
