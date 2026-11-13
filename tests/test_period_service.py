"""
tests/test_period_service.py
----------------------------
Tujuan  : Menguji fungsi-fungsi pada services/period_service.py.
          Memastikan pembuatan periode dasar multi-tahun, auto-create periode,
          dan preset periode (bulan ini, bulan lalu, data observasi) berfungsi presisi.
"""

import sqlite3
import pytest
from unittest.mock import patch
from services.period_service import (
    nama_bulan_tahun,
    pastikan_periode_dasar_tersedia,
    ambil_semua_periode,
    ambil_info_periode,
    ambil_atau_buat_periode,
    ambil_id_periode_observasi,
    ambil_id_periode_bulan_ini,
    ambil_id_periode_bulan_lalu,
)


@pytest.fixture
def mock_db_periods(tmp_path):
    """Fixture database terisolasi untuk pengujian periode."""
    db_file = tmp_path / "test_periods.db"

    def get_conn():
        c = sqlite3.connect(str(db_file))
        c.row_factory = sqlite3.Row
        return c

    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tahun INTEGER NOT NULL,
            bulan INTEGER NOT NULL,
            nama_bulan TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'buka' CHECK (status IN ('buka', 'tutup')),
            UNIQUE (tahun, bulan)
        )
    """)
    conn.commit()
    conn.close()

    with patch("services.period_service.get_connection", side_effect=get_conn):
        yield get_conn


def test_nama_bulan_tahun():
    """Memastikan konversi bulan dan tahun menghasilkan teks Bahasa Indonesia yang tepat."""
    assert nama_bulan_tahun(1, 2026) == "Januari 2026"
    assert nama_bulan_tahun(10, 2026) == "Oktober 2026"
    assert nama_bulan_tahun(12, 2025) == "Desember 2025"


def test_pastikan_periode_dasar_tersedia(mock_db_periods):
    """Memastikan periode 2025-2027 terisi lengkap 36 bulan."""
    pastikan_periode_dasar_tersedia()
    semua = ambil_semua_periode()
    assert len(semua) == 36
    # Pastikan tahun 2025, 2026, 2027 ada
    tahun_ada = {p["tahun"] for p in semua}
    assert tahun_ada == {2025, 2026, 2027}


def test_ambil_atau_buat_periode(mock_db_periods):
    """Memastikan fungsi membuat periode baru jika belum ada dan mengambilnya jika sudah ada."""
    p_baru = ambil_atau_buat_periode(2028, 5)
    assert p_baru["tahun"] == 2028
    assert p_baru["bulan"] == 5
    assert p_baru["nama_bulan"] == "Mei 2028"
    assert p_baru["status"] == "buka"

    # Panggil ulang harus mengembalikan ID yang sama
    p_sama = ambil_atau_buat_periode(2028, 5)
    assert p_sama["id"] == p_baru["id"]


def test_ambil_info_periode(mock_db_periods):
    """Memastikan detail periode dapat diambil berdasarkan ID."""
    p = ambil_atau_buat_periode(2026, 10)
    info = ambil_info_periode(p["id"])
    assert info is not None
    assert info["tahun"] == 2026
    assert info["bulan"] == 10
    assert info["nama_bulan"] == "Oktober 2026"


def test_presets_periode(mock_db_periods):
    """Memastikan helper preset periode mengembalikan ID valid."""
    obs_id = ambil_id_periode_observasi()
    assert obs_id > 0
    info_obs = ambil_info_periode(obs_id)
    assert info_obs["tahun"] == 2026 and info_obs["bulan"] == 10

    ini_id = ambil_id_periode_bulan_ini()
    assert ini_id > 0

    lalu_id = ambil_id_periode_bulan_lalu()
    assert lalu_id > 0
