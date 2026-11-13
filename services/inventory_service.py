"""
services/inventory_service.py
------------------------------
Tujuan  : Mengelola kartu persediaan dengan metode perpetual dan rata-rata bergerak.
Input   : Item, tanggal, kuantitas, dan harga per satuan.
Output  : Mutasi stok, nilai HPP, serta saldo kuantitas dan nilai persediaan.
Dipanggil oleh : services/transaction_service.py, views/06_kartu_persediaan.py,
                 dan views/01_master_data.py.

RUMUS RATA-RATA BERGERAK:
  Saat masuk: (nilai saldo lama + nilai masuk) / (qty saldo lama + qty masuk)
  Saat keluar: HPP = qty keluar x harga rata-rata terakhir.
"""

import math
import pandas as pd
from database.connection import get_connection


def ambil_daftar_item_persediaan() -> list[dict]:
    """Mengambil daftar item aktif beserta akun persediaannya."""
    koneksi = get_connection()
    try:
        rows = koneksi.execute("""
            SELECT id, kode_item, nama_item, satuan, tipe, account_id
            FROM items WHERE aktif = 1 ORDER BY tipe, kode_item
        """).fetchall()
        return [dict(row) for row in rows]
    finally:
        koneksi.close()


def hitung_nilai_keluar(item_id: int, qty: float) -> dict:
    """Menghitung HPP dan saldo tanpa menyimpan mutasi (untuk pratinjau jurnal)."""
    if qty <= 0:
        raise ValueError("Kuantitas keluar harus lebih besar dari nol.")

    saldo = ambil_saldo_persediaan(item_id)
    saldo_qty = saldo["saldo_qty"]
    if saldo_qty <= 0:
        raise ValueError(
            "Stok persediaan belum tersedia. Masukkan saldo awal atau catat panen terlebih dahulu."
        )
    if qty - saldo_qty > 1e-9:
        raise ValueError(
            f"Stok tidak mencukupi. Tersedia {saldo_qty:g}, sedangkan dibutuhkan {qty:g}."
        )

    # Jika seluruh stok keluar, gunakan seluruh nilai saldo untuk menghindari sisa pembulatan.
    total_keluar = (
        saldo["saldo_nilai"]
        if math.isclose(qty, saldo_qty, rel_tol=0, abs_tol=1e-9)
        else int(qty * saldo["harga_rata2"])
    )
    return {
        "saldo_qty": saldo_qty,
        "saldo_nilai": saldo["saldo_nilai"],
        "harga_rata2": saldo["harga_rata2"],
        "total_keluar": int(total_keluar),
    }


def catat_gerakan_masuk(
    item_id: int,
    tanggal: str,
    qty: float,
    harga_satuan: int,
    keterangan: str = "",
    journal_entry_id: int | None = None,
) -> dict:
    """Mencatat barang masuk dan menghitung ulang harga rata-rata bergerak."""
    if qty <= 0:
        raise ValueError("Kuantitas masuk harus lebih besar dari nol.")
    if harga_satuan < 0:
        raise ValueError("Harga satuan tidak boleh negatif.")

    koneksi = get_connection()
    try:
        row = koneksi.execute("""
            SELECT tanggal, saldo_qty, saldo_nilai
            FROM inventory_movements
            WHERE item_id = ? ORDER BY id DESC LIMIT 1
        """, (item_id,)).fetchone()

        if row and tanggal < row["tanggal"]:
            raise ValueError(
                f"Tanggal mutasi {tanggal} lebih awal dari mutasi terakhir {row['tanggal']}. "
                "Catat mutasi per item secara kronologis agar rata-rata bergerak tetap akurat."
            )
        qty_lama = float(row["saldo_qty"]) if row else 0.0
        nilai_lama = int(row["saldo_nilai"]) if row else 0
        total_masuk = int(qty * harga_satuan)
        qty_baru = qty_lama + qty
        nilai_baru = nilai_lama + total_masuk
        harga_rata2_baru = int(nilai_baru / qty_baru)

        koneksi.execute("""
            INSERT INTO inventory_movements
                (item_id, journal_entry_id, tanggal, tipe_gerakan,
                 qty, harga_satuan, total_nilai,
                 saldo_qty, saldo_nilai, harga_rata2, keterangan)
            VALUES (?, ?, ?, 'masuk', ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_id, journal_entry_id, tanggal, qty, harga_satuan,
            total_masuk, qty_baru, nilai_baru, harga_rata2_baru, keterangan,
        ))
        koneksi.commit()
        return {
            "saldo_qty": qty_baru,
            "saldo_nilai": nilai_baru,
            "harga_rata2": harga_rata2_baru,
        }
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()


def catat_gerakan_keluar(
    item_id: int,
    tanggal: str,
    qty: float,
    keterangan: str = "",
    journal_entry_id: int | None = None,
) -> dict:
    """Mencatat barang keluar dan mengurangi nilai persediaan secara perpetual."""
    if qty <= 0:
        raise ValueError("Kuantitas keluar harus lebih besar dari nol.")

    koneksi = get_connection()
    try:
        row = koneksi.execute("""
            SELECT tanggal, saldo_qty, saldo_nilai, harga_rata2
            FROM inventory_movements
            WHERE item_id = ? ORDER BY id DESC LIMIT 1
        """, (item_id,)).fetchone()

        if not row or float(row["saldo_qty"]) <= 0:
            raise ValueError(
                "Stok persediaan belum tersedia. Masukkan saldo awal atau catat panen terlebih dahulu."
            )

        if tanggal < row["tanggal"]:
            raise ValueError(
                f"Tanggal mutasi {tanggal} lebih awal dari mutasi terakhir {row['tanggal']}. "
                "Catat mutasi per item secara kronologis agar rata-rata bergerak tetap akurat."
            )
        qty_lama = float(row["saldo_qty"])
        nilai_lama = int(row["saldo_nilai"])
        harga_rata2 = int(row["harga_rata2"])
        if qty - qty_lama > 1e-9:
            raise ValueError(
                f"Stok tidak mencukupi. Tersedia {qty_lama:g}, sedangkan dibutuhkan {qty:g}."
            )

        if math.isclose(qty, qty_lama, rel_tol=0, abs_tol=1e-9):
            nilai_keluar = nilai_lama
            qty_baru = 0.0
            nilai_baru = 0
            harga_rata2_baru = 0
        else:
            nilai_keluar = int(qty * harga_rata2)
            qty_baru = qty_lama - qty
            nilai_baru = max(0, nilai_lama - nilai_keluar)
            harga_rata2_baru = harga_rata2

        koneksi.execute("""
            INSERT INTO inventory_movements
                (item_id, journal_entry_id, tanggal, tipe_gerakan,
                 qty, harga_satuan, total_nilai,
                 saldo_qty, saldo_nilai, harga_rata2, keterangan)
            VALUES (?, ?, ?, 'keluar', ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_id, journal_entry_id, tanggal, qty, harga_rata2,
            nilai_keluar, qty_baru, nilai_baru, harga_rata2_baru, keterangan,
        ))
        koneksi.commit()
        return {
            "saldo_qty": qty_baru,
            "saldo_nilai": nilai_baru,
            "harga_rata2": harga_rata2_baru,
            "total_keluar": nilai_keluar,
        }
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()


def catat_saldo_awal_persediaan(
    period_id: int,
    item_id: int,
    qty: float,
    harga_satuan: int,
) -> int:
    """
    Mencatat saldo awal kuantitas dan nilai satu item.

    Nilai akun persediaan pada opening_balances otomatis diselaraskan dengan
    jumlah nilai saldo awal semua item yang memakai akun tersebut.
    Saldo awal hanya dapat dimasukkan sebelum transaksi item dicatat.
    """
    if qty < 0 or harga_satuan < 0:
        raise ValueError("Kuantitas dan harga satuan saldo awal tidak boleh negatif.")

    koneksi = get_connection()
    try:
        periode = koneksi.execute(
            "SELECT tahun, bulan, status FROM periods WHERE id = ?", (period_id,)
        ).fetchone()
        if not periode:
            raise ValueError("Periode saldo awal tidak ditemukan.")
        if periode["status"] == "tutup":
            raise ValueError("Periode sudah ditutup dan tidak dapat diubah.")

        item = koneksi.execute("""
            SELECT id, nama_item, satuan, account_id
            FROM items WHERE id = ? AND aktif = 1
        """, (item_id,)).fetchone()
        if not item:
            raise ValueError("Item persediaan tidak ditemukan atau sudah nonaktif.")
        if not item["account_id"]:
            raise ValueError("Item belum dihubungkan dengan akun persediaan di Master Data.")

        tanggal_awal = f"{int(periode['tahun']):04d}-{int(periode['bulan']):02d}-01"
        mutasi_transaksi = koneksi.execute("""
            SELECT COUNT(*) AS jumlah
            FROM inventory_movements
            WHERE item_id = ? AND tipe_gerakan != 'saldo_awal'
        """, (item_id,)).fetchone()["jumlah"]
        if mutasi_transaksi:
            raise ValueError(
                "Saldo awal item ini tidak dapat diubah karena transaksi persediaan sudah tercatat."
            )

        nilai_awal = int(qty * harga_satuan)
        existing = koneksi.execute("""
            SELECT id FROM inventory_movements
            WHERE item_id = ? AND tipe_gerakan = 'saldo_awal'
        """, (item_id,)).fetchone()

        if qty == 0:
            if existing:
                koneksi.execute(
                    "DELETE FROM inventory_movements WHERE id = ?", (existing["id"],)
                )
        elif existing:
            koneksi.execute("""
                UPDATE inventory_movements
                SET tanggal = ?, qty = ?, harga_satuan = ?, total_nilai = ?,
                    saldo_qty = ?, saldo_nilai = ?, harga_rata2 = ?,
                    keterangan = 'Saldo awal persediaan'
                WHERE id = ?
            """, (
                tanggal_awal, qty, harga_satuan, nilai_awal, qty, nilai_awal,
                int(nilai_awal / qty), existing["id"],
            ))
        else:
            koneksi.execute("""
                INSERT INTO inventory_movements
                    (item_id, tanggal, tipe_gerakan, qty, harga_satuan,
                     total_nilai, saldo_qty, saldo_nilai, harga_rata2, keterangan)
                VALUES (?, ?, 'saldo_awal', ?, ?, ?, ?, ?, ?, 'Saldo awal persediaan')
            """, (
                item_id, tanggal_awal, qty, harga_satuan, nilai_awal,
                qty, nilai_awal, int(nilai_awal / qty) if qty else 0,
            ))

        total_akun = koneksi.execute("""
            SELECT COALESCE(SUM(im.total_nilai), 0) AS total
            FROM inventory_movements im
            JOIN items i ON i.id = im.item_id
            WHERE i.account_id = ?
              AND im.tipe_gerakan = 'saldo_awal'
              AND im.tanggal = ?
        """, (item["account_id"], tanggal_awal)).fetchone()["total"]

        koneksi.execute("""
            INSERT INTO opening_balances
                (period_id, account_id, saldo_debit, saldo_kredit, catatan)
            VALUES (?, ?, ?, 0, 'Otomatis dari saldo awal kuantitas persediaan')
            ON CONFLICT(period_id, account_id) DO UPDATE SET
                saldo_debit = excluded.saldo_debit,
                saldo_kredit = 0,
                catatan = excluded.catatan
        """, (period_id, item["account_id"], int(total_akun)))
        koneksi.commit()
        return int(total_akun)
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()


def ambil_saldo_persediaan(item_id: int) -> dict:
    """Mengambil saldo terakhir satu item, atau nol jika belum ada mutasi."""
    koneksi = get_connection()
    try:
        row = koneksi.execute("""
            SELECT saldo_qty, saldo_nilai, harga_rata2
            FROM inventory_movements
            WHERE item_id = ? ORDER BY id DESC LIMIT 1
        """, (item_id,)).fetchone()
    finally:
        koneksi.close()

    if row:
        return {
            "saldo_qty": float(row["saldo_qty"]),
            "saldo_nilai": int(row["saldo_nilai"]),
            "harga_rata2": int(row["harga_rata2"]),
        }
    return {"saldo_qty": 0.0, "saldo_nilai": 0, "harga_rata2": 0}


def ambil_kartu_persediaan(item_id: int) -> pd.DataFrame:
    """Mengambil seluruh riwayat gerakan persediaan satu item secara kronologis."""
    koneksi = get_connection()
    try:
        return pd.read_sql_query("""
            SELECT tanggal, tipe_gerakan, qty, harga_satuan, total_nilai,
                   saldo_qty, saldo_nilai, harga_rata2, keterangan
            FROM inventory_movements
            WHERE item_id = ?
            ORDER BY tanggal ASC, id ASC
        """, koneksi, params=(item_id,))
    finally:
        koneksi.close()
