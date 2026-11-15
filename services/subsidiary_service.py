"""
services/subsidiary_service.py
--------------------------------
Tujuan  : Mengelola Buku Besar Pembantu Piutang Usaha dan Utang Usaha.
          2 jenis BB Pembantu:
          1. Piutang per pelanggan (dengan umur piutang / aging)
          2. Utang Usaha per supplier/transaksi
Input   : customer_id untuk filter piutang atau tanpa filter.
Output  : DataFrame Buku Besar Pembantu Piutang dan Utang Usaha.
Dipanggil oleh : views/08_buku_besar_pembantu.py

KONSEP BUKU BESAR PEMBANTU:
  BB Pembantu merupakan rincian (sub-ledger) dari akun kontrol di Buku Besar.
  - BB Piutang → rincian akun 1201 (Piutang Usaha) per pelanggan
  - BB Utang → rincian akun 2101 (Utang Usaha) per supplier/transaksi
  Rincian BB Pembantu digunakan untuk menelusuri saldo akun kontrol di Buku Besar.
"""

import pandas as pd
from database.connection import get_connection


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
