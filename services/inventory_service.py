"""
services/inventory_service.py
------------------------------
Tujuan  : Mengelola kartu persediaan dengan metode rata-rata bergerak.
          Setiap kali bahan masuk, harga rata-rata dihitung ulang.
Input   : item_id, qty, harga_satuan, tipe_gerakan (masuk/keluar).
Output  : Saldo persediaan terbaru.
Dipanggil oleh : services/transaction_service.py, views/06_kartu_persediaan.py

RUMUS RATA-RATA BERGERAK:
  Saat bahan MASUK:
    saldo_qty_baru  = saldo_qty_lama + qty_masuk
    saldo_nilai_baru = saldo_nilai_lama + (qty_masuk x harga_satuan)
    harga_rata2_baru = saldo_nilai_baru / saldo_qty_baru

  Saat bahan KELUAR:
    total_keluar = qty_keluar x harga_rata2 (pakai harga rata-rata saat ini)
    saldo_qty_baru  = saldo_qty_lama - qty_keluar
    saldo_nilai_baru = saldo_nilai_lama - total_keluar
    harga_rata2_baru = harga_rata2 (tidak berubah saat keluar)
"""

import pandas as pd
from database.connection import get_connection


def catat_gerakan_masuk(
    item_id: int,
    tanggal: str,
    qty: float,
    harga_satuan: int,
    keterangan: str = "",
    journal_entry_id: int | None = None,
) -> dict:
    """
    Mencatat bahan masuk ke kartu persediaan dan menghitung rata-rata bergerak.

    Returns:
        Dict berisi saldo terbaru: {saldo_qty, saldo_nilai, harga_rata2}.
    """
    koneksi = get_connection()
    try:
        # Ambil saldo terakhir item ini
        row = koneksi.execute("""
            SELECT saldo_qty, saldo_nilai, harga_rata2
            FROM inventory_movements
            WHERE item_id = ?
            ORDER BY id DESC LIMIT 1
        """, (item_id,)).fetchone()

        if row:
            saldo_qty_lama = float(row["saldo_qty"])
            saldo_nilai_lama = int(row["saldo_nilai"])
        else:
            saldo_qty_lama = 0.0
            saldo_nilai_lama = 0

        # Hitung saldo baru
        total_masuk = int(qty * harga_satuan)
        saldo_qty_baru = saldo_qty_lama + qty
        saldo_nilai_baru = saldo_nilai_lama + total_masuk

        # Harga rata-rata bergerak baru
        if saldo_qty_baru > 0:
            harga_rata2_baru = int(saldo_nilai_baru / saldo_qty_baru)
        else:
            harga_rata2_baru = harga_satuan

        # Simpan gerakan
        koneksi.execute("""
            INSERT INTO inventory_movements
                (item_id, journal_entry_id, tanggal, tipe_gerakan,
                 qty, harga_satuan, total_nilai,
                 saldo_qty, saldo_nilai, harga_rata2, keterangan)
            VALUES (?, ?, ?, 'masuk', ?, ?, ?, ?, ?, ?, ?)
        """, (item_id, journal_entry_id, tanggal,
              qty, harga_satuan, total_masuk,
              saldo_qty_baru, saldo_nilai_baru, harga_rata2_baru,
              keterangan))
        koneksi.commit()

        return {
            "saldo_qty": saldo_qty_baru,
            "saldo_nilai": saldo_nilai_baru,
            "harga_rata2": harga_rata2_baru,
        }
    finally:
        koneksi.close()


def catat_gerakan_keluar(
    item_id: int,
    tanggal: str,
    qty: float,
    keterangan: str = "",
    journal_entry_id: int | None = None,
) -> dict:
    """
    Mencatat bahan keluar dari kartu persediaan.
    Harga keluar = harga rata-rata saat ini (metode rata-rata bergerak).

    Raises:
        ValueError: Jika saldo tidak mencukupi.

    Returns:
        Dict berisi saldo terbaru: {saldo_qty, saldo_nilai, harga_rata2, total_keluar}.
    """
    koneksi = get_connection()
    try:
        # Ambil saldo terakhir
        row = koneksi.execute("""
            SELECT saldo_qty, saldo_nilai, harga_rata2
            FROM inventory_movements
            WHERE item_id = ?
            ORDER BY id DESC LIMIT 1
        """, (item_id,)).fetchone()

        if not row or float(row["saldo_qty"]) <= 0:
            raise ValueError("Saldo persediaan tidak mencukupi atau belum ada.")

        saldo_qty_lama = float(row["saldo_qty"])
        saldo_nilai_lama = int(row["saldo_nilai"])
        harga_rata2 = int(row["harga_rata2"])

        if qty > saldo_qty_lama:
            raise ValueError(
                f"Saldo tidak cukup. Tersedia: {saldo_qty_lama}, diminta: {qty}"
            )

        # Hitung nilai keluar
        total_keluar = int(qty * harga_rata2)
        saldo_qty_baru = saldo_qty_lama - qty
        saldo_nilai_baru = saldo_nilai_lama - total_keluar

        koneksi.execute("""
            INSERT INTO inventory_movements
                (item_id, journal_entry_id, tanggal, tipe_gerakan,
                 qty, harga_satuan, total_nilai,
                 saldo_qty, saldo_nilai, harga_rata2, keterangan)
            VALUES (?, ?, ?, 'keluar', ?, ?, ?, ?, ?, ?, ?)
        """, (item_id, journal_entry_id, tanggal,
              qty, harga_rata2, total_keluar,
              saldo_qty_baru, saldo_nilai_baru, harga_rata2,
              keterangan))
        koneksi.commit()

        return {
            "saldo_qty": saldo_qty_baru,
            "saldo_nilai": saldo_nilai_baru,
            "harga_rata2": harga_rata2,
            "total_keluar": total_keluar,
        }
    finally:
        koneksi.close()


def ambil_saldo_persediaan(item_id: int) -> dict:
    """
    Mengambil saldo persediaan terkini untuk satu item.

    Returns:
        Dict {saldo_qty, saldo_nilai, harga_rata2} atau semua 0 jika kosong.
    """
    koneksi = get_connection()
    row = koneksi.execute("""
        SELECT saldo_qty, saldo_nilai, harga_rata2
        FROM inventory_movements
        WHERE item_id = ?
        ORDER BY id DESC LIMIT 1
    """, (item_id,)).fetchone()
    koneksi.close()

    if row:
        return {
            "saldo_qty": float(row["saldo_qty"]),
            "saldo_nilai": int(row["saldo_nilai"]),
            "harga_rata2": int(row["harga_rata2"]),
        }
    return {"saldo_qty": 0.0, "saldo_nilai": 0, "harga_rata2": 0}


def ambil_kartu_persediaan(item_id: int) -> pd.DataFrame:
    """
    Mengambil seluruh riwayat gerakan persediaan untuk satu item.

    Returns:
        DataFrame: tanggal | tipe_gerakan | qty | harga_satuan |
                   total_nilai | saldo_qty | saldo_nilai | harga_rata2 | keterangan
    """
    koneksi = get_connection()
    df = pd.read_sql_query("""
        SELECT
            tanggal,
            tipe_gerakan,
            qty,
            harga_satuan,
            total_nilai,
            saldo_qty,
            saldo_nilai,
            harga_rata2,
            keterangan
        FROM inventory_movements
        WHERE item_id = ?
        ORDER BY id ASC
    """, koneksi, params=(item_id,))
    koneksi.close()
    return df
