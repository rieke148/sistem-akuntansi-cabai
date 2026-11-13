"""
services/period_service.py
--------------------------
Tujuan  : Mengelola logika periode akuntansi secara terpusat.
          Mendukung auto-generate periode, pencarian, preset periode
          (bulan ini, bulan lalu, tahun ini, tahun lalu, periode observasi),
          serta pembuatan periode baru secara dinamis.
Input   : tahun, bulan, period_id, status.
Output  : Data periode (dict atau list of dict).
Dipanggil oleh : utils/ui_components.py, views/*.py, services/*.py
"""

import sqlite3
from datetime import date
from database.connection import get_connection

NAMA_BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]


def nama_bulan_tahun(bulan: int, tahun: int) -> str:
    """Mengembalikan format nama bulan dan tahun dalam Bahasa Indonesia."""
    if 1 <= bulan <= 12:
        return f"{NAMA_BULAN[bulan - 1]} {tahun}"
    return f"Bulan {bulan} {tahun}"


def pastikan_periode_dasar_tersedia() -> None:
    """
    Memastikan periode untuk tahun 2025, 2026, dan 2027 tersedia di database.
    Aman dipanggil berulang kali (tidak akan menduplikasi periode yang sudah ada).
    """
    koneksi = get_connection()
    try:
        cursor = koneksi.cursor()
        # Periode 2025, 2026, 2027
        for thn in [2025, 2026, 2027]:
            for bln in range(1, 13):
                nama = nama_bulan_tahun(bln, thn)
                cursor.execute("""
                    INSERT OR IGNORE INTO periods (tahun, bulan, nama_bulan, status)
                    VALUES (?, ?, ?, 'buka')
                """, (thn, bln, nama))
        koneksi.commit()
    finally:
        koneksi.close()


def ambil_semua_periode(hanya_buka: bool = False, urutan_terbaru: bool = True) -> list[dict]:
    """
    Mengambil semua periode dari database.

    Args:
        hanya_buka     : Jika True, hanya ambil periode berstatus 'buka'.
        urutan_terbaru : Jika True, urutkan dari tahun dan bulan terbaru ke terlama.

    Returns:
        List of dict berisi data periode.
    """
    pastikan_periode_dasar_tersedia()
    koneksi = get_connection()
    try:
        where_clause = "WHERE status = 'buka'" if hanya_buka else ""
        order_clause = "ORDER BY tahun DESC, bulan DESC" if urutan_terbaru else "ORDER BY tahun ASC, bulan ASC"
        query = f"SELECT id, tahun, bulan, nama_bulan, status FROM periods {where_clause} {order_clause}"
        rows = koneksi.execute(query).fetchall()
        return [dict(r) for r in rows]
    finally:
        koneksi.close()


def ambil_info_periode(period_id: int) -> dict | None:
    """Mengambil detail satu periode berdasarkan ID."""
    koneksi = get_connection()
    try:
        row = koneksi.execute(
            "SELECT id, tahun, bulan, nama_bulan, status FROM periods WHERE id = ?",
            (period_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        koneksi.close()


def ambil_atau_buat_periode(tahun: int, bulan: int, status: str = "buka") -> dict:
    """
    Mencari periode berdasarkan tahun dan bulan.
    Jika belum ada di database, otomatis dibuat dengan status yang diberikan.

    Returns:
        Dict data periode: {'id', 'tahun', 'bulan', 'nama_bulan', 'status'}.
    """
    koneksi = get_connection()
    try:
        row = koneksi.execute(
            "SELECT id, tahun, bulan, nama_bulan, status FROM periods WHERE tahun = ? AND bulan = ?",
            (tahun, bulan)
        ).fetchone()
        if row:
            return dict(row)

        nama = nama_bulan_tahun(bulan, tahun)
        cursor = koneksi.cursor()
        cursor.execute(
            "INSERT INTO periods (tahun, bulan, nama_bulan, status) VALUES (?, ?, ?, ?)",
            (tahun, bulan, nama, status)
        )
        koneksi.commit()
        new_id = cursor.lastrowid
        return {
            "id": new_id,
            "tahun": tahun,
            "bulan": bulan,
            "nama_bulan": nama,
            "status": status,
        }
    finally:
        koneksi.close()


def ambil_id_periode_observasi() -> int:
    """
    Mengambil ID periode data observasi (Oktober 2026).
    Jika belum ada, otomatis dibuat.
    """
    p = ambil_atau_buat_periode(2026, 10)
    return p["id"]


def ambil_id_periode_bulan_ini() -> int:
    """
    Mengambil ID periode untuk bulan dan tahun saat ini.
    Jika belum ada, otomatis dibuat.
    """
    today = date.today()
    p = ambil_atau_buat_periode(today.year, today.month)
    return p["id"]


def ambil_id_periode_bulan_lalu() -> int:
    """
    Mengambil ID periode untuk 1 bulan sebelum hari ini.
    Jika belum ada, otomatis dibuat.
    """
    today = date.today()
    if today.month == 1:
        thn = today.year - 1
        bln = 12
    else:
        thn = today.year
        bln = today.month - 1
    p = ambil_atau_buat_periode(thn, bln)
    return p["id"]
