"""
database/connection.py
----------------------
Tujuan  : Membuat dan mengelola koneksi ke database SQLite.
          Semua file lain yang butuh database harus impor fungsi
          `get_connection()` dari sini — JANGAN buka koneksi sendiri.
Input   : Tidak ada (path database sudah ditentukan di dalam file ini).
Output  : Objek koneksi sqlite3.Connection.
Dipanggil oleh : database/schema.py, database/seed.py,
                 semua file services/
"""

import sqlite3
import os
from pathlib import Path


# ---------------------------------------------------------------
# PATH DATABASE
# ---------------------------------------------------------------
# File .db disimpan di folder yang sama dengan connection.py ini.
# Di Streamlit Cloud, filesystem tidak permanen — gunakan fitur
# Backup/Restore (views/14_backup_export.py) untuk menyimpan data.
_FOLDER_DATABASE = Path(__file__).parent          # folder database/
NAMA_FILE_DB = "akuntansi_cabai.db"               # nama file SQLite
PATH_DATABASE = _FOLDER_DATABASE / NAMA_FILE_DB   # path lengkap


def get_connection() -> sqlite3.Connection:
    """
    Membuka (atau membuat) koneksi ke database SQLite.

    - check_same_thread=False diperlukan agar Streamlit (multi-thread)
      bisa pakai koneksi yang sama.
    - detect_types: agar tipe DATE dan DECIMAL tersimpan dengan benar.
    - row_factory=sqlite3.Row: agar hasil query bisa diakses seperti dict
      (mis. row["nama_akun"]) selain seperti tuple.
    """
    koneksi = sqlite3.connect(
        PATH_DATABASE,
        check_same_thread=False,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    # row_factory memungkinkan akses kolom dengan nama, bukan hanya index
    koneksi.row_factory = sqlite3.Row

    # Aktifkan foreign key — SQLite tidak aktifkan ini secara default
    koneksi.execute("PRAGMA foreign_keys = ON")

    return koneksi


def tutup_connection(koneksi: sqlite3.Connection) -> None:
    """Menutup koneksi database dengan aman."""
    if koneksi:
        koneksi.close()


def db_sudah_ada() -> bool:
    """
    Mengecek apakah file database sudah ada DAN sudah berisi tabel.
    Dipakai di app.py untuk memutuskan apakah perlu seed data.
    """
    if not PATH_DATABASE.exists():
        return False
    # Cek apakah tabel 'accounts' sudah dibuat
    try:
        koneksi = get_connection()
        cursor = koneksi.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'"
        )
        ada = cursor.fetchone() is not None
        tutup_connection(koneksi)
        return ada
    except Exception:
        return False
