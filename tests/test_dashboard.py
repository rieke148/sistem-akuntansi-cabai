"""
tests/test_dashboard.py
------------------------
Tujuan  : Pytest untuk services/dashboard_service.py (Fase 7).
Input   : Database SQLite sementara via tmp_path fixture.
Output  : Semua fungsi dashboard mengembalikan tipe dan nilai yang benar.
Dipanggil oleh : pytest
"""

import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import date

from services.dashboard_service import (
    ambil_saldo_kas_bank,
    ambil_piutang_overdue,
    ambil_ringkasan_penjualan_beban,
    ambil_stok_persediaan,
    ambil_ringkasan_jurnal,
    cek_progress_siklus,
    ambil_penjualan_per_komoditas,
    ambil_period_id_aktif,
    ambil_info_periode,
)


# ---------------------------------------------------------------------------
# Fixture: database sementara
# ---------------------------------------------------------------------------

def _buat_schema(koneksi: sqlite3.Connection) -> None:
    """Membuat skema minimal yang dibutuhkan dashboard_service."""
    koneksi.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS accounts (
            id           INTEGER PRIMARY KEY,
            kode_akun    TEXT NOT NULL UNIQUE,
            nama_akun    TEXT NOT NULL,
            kategori     TEXT NOT NULL,
            saldo_normal TEXT NOT NULL DEFAULT 'Debit',
            is_kontra    INTEGER NOT NULL DEFAULT 0,
            aktif        INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS periods (
            id         INTEGER PRIMARY KEY,
            tahun      INTEGER NOT NULL,
            bulan      INTEGER NOT NULL,
            nama_bulan TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'buka'
        );

        CREATE TABLE IF NOT EXISTS journal_entries (
            id            INTEGER PRIMARY KEY,
            period_id     INTEGER NOT NULL REFERENCES periods(id),
            tanggal       TEXT NOT NULL,
            no_bukti      TEXT NOT NULL,
            journal_type  TEXT NOT NULL
                CHECK (journal_type IN ('penjualan','penerimaan_kas','pengeluaran_kas','pembelian','umum')),
            keterangan    TEXT,
            komoditas     TEXT NOT NULL DEFAULT 'umum'
                CHECK (komoditas IN ('cabai','umum')),
            pihak_terkait TEXT,
            dibuat_pada   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS journal_lines (
            id               INTEGER PRIMARY KEY,
            journal_entry_id INTEGER NOT NULL REFERENCES journal_entries(id),
            account_id       INTEGER NOT NULL REFERENCES accounts(id),
            debit            INTEGER NOT NULL DEFAULT 0,
            kredit           INTEGER NOT NULL DEFAULT 0,
            keterangan       TEXT
        );

        CREATE TABLE IF NOT EXISTS opening_balances (
            id          INTEGER PRIMARY KEY,
            period_id   INTEGER NOT NULL REFERENCES periods(id),
            account_id  INTEGER NOT NULL REFERENCES accounts(id),
            saldo_debit INTEGER NOT NULL DEFAULT 0,
            saldo_kredit INTEGER NOT NULL DEFAULT 0,
            catatan     TEXT
        );

        CREATE TABLE IF NOT EXISTS customers (
            id      INTEGER PRIMARY KEY,
            nama    TEXT NOT NULL,
            tipe    TEXT DEFAULT 'reguler',
            telepon TEXT,
            alamat  TEXT,
            aktif   INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS receivables (
            id                INTEGER PRIMARY KEY,
            journal_entry_id  INTEGER NOT NULL REFERENCES journal_entries(id),
            customer_id       INTEGER REFERENCES customers(id),
            no_faktur         TEXT,
            tanggal_faktur    TEXT,
            tanggal_jatuh_tempo TEXT,
            jumlah            INTEGER NOT NULL DEFAULT 0,
            jumlah_terbayar   INTEGER NOT NULL DEFAULT 0,
            status            TEXT NOT NULL DEFAULT 'belum_lunas'
                CHECK (status IN ('belum_lunas','sebagian','lunas'))
        );

        CREATE TABLE IF NOT EXISTS items (
            id        INTEGER PRIMARY KEY,
            kode_item TEXT NOT NULL UNIQUE,
            nama_item TEXT NOT NULL,
            satuan    TEXT NOT NULL,
            tipe      TEXT NOT NULL,
            komoditas TEXT NOT NULL DEFAULT 'cabai',
            account_id INTEGER,
            aktif     INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS inventory_movements (
            id             INTEGER PRIMARY KEY,
            item_id        INTEGER NOT NULL REFERENCES items(id),
            journal_entry_id INTEGER REFERENCES journal_entries(id),
            tanggal        TEXT NOT NULL,
            tipe_gerakan   TEXT NOT NULL,
            qty            REAL NOT NULL DEFAULT 0,
            harga_satuan   INTEGER NOT NULL DEFAULT 0,
            total_nilai    INTEGER NOT NULL DEFAULT 0,
            saldo_qty      REAL NOT NULL DEFAULT 0,
            saldo_nilai    INTEGER NOT NULL DEFAULT 0,
            harga_rata2    INTEGER NOT NULL DEFAULT 0,
            keterangan     TEXT
        );
    """)


def _isi_data_contoh(koneksi: sqlite3.Connection) -> int:
    """Mengisi data contoh minimal. Mengembalikan period_id."""
    # Akun
    koneksi.executemany(
        "INSERT INTO accounts (kode_akun, nama_akun, kategori, saldo_normal) VALUES (?,?,?,?)",
        [
            ("1101", "Kas Tunai", "Aset Lancar", "Debit"),
            ("1102", "Bank BRI", "Aset Lancar", "Debit"),
            ("1201", "Piutang Usaha", "Aset Lancar", "Debit"),
            ("4101", "Penjualan Cabai", "Pendapatan", "Kredit"),
            ("5101", "Beban Pupuk", "Beban Produksi", "Debit"),
        ],
    )

    # Periode
    koneksi.execute(
        "INSERT INTO periods (tahun, bulan, nama_bulan, status) VALUES (2026, 10, 'Oktober', 'buka')"
    )
    period_id = koneksi.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Saldo awal kas
    akun_kas_id = koneksi.execute("SELECT id FROM accounts WHERE kode_akun='1101'").fetchone()[0]
    akun_bank_id = koneksi.execute("SELECT id FROM accounts WHERE kode_akun='1102'").fetchone()[0]
    koneksi.executemany(
        "INSERT INTO opening_balances (period_id, account_id, saldo_debit, saldo_kredit) VALUES (?,?,?,?)",
        [
            (period_id, akun_kas_id, 5_000_000, 0),
            (period_id, akun_bank_id, 10_000_000, 0),
        ],
    )

    # Transaksi penjualan
    akun_jual_id = koneksi.execute("SELECT id FROM accounts WHERE kode_akun='4101'").fetchone()[0]
    koneksi.execute(
        """INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan, komoditas)
           VALUES (?, '2026-10-05', 'PJ-001', 'penjualan', 'Penjualan cabai', 'cabai')""",
        (period_id,),
    )
    je_id = koneksi.execute("SELECT last_insert_rowid()").fetchone()[0]
    koneksi.executemany(
        "INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit) VALUES (?,?,?,?)",
        [
            (je_id, akun_kas_id, 2_000_000, 0),
            (je_id, akun_jual_id, 0, 2_000_000),
        ],
    )

    # Transaksi beban
    akun_beban_id = koneksi.execute("SELECT id FROM accounts WHERE kode_akun='5101'").fetchone()[0]
    koneksi.execute(
        """INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan, komoditas)
           VALUES (?, '2026-10-10', 'PK-001', 'pengeluaran_kas', 'Beli pupuk', 'cabai')""",
        (period_id,),
    )
    je_id2 = koneksi.execute("SELECT last_insert_rowid()").fetchone()[0]
    koneksi.executemany(
        "INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit) VALUES (?,?,?,?)",
        [
            (je_id2, akun_beban_id, 500_000, 0),
            (je_id2, akun_kas_id, 0, 500_000),
        ],
    )

    # Penyesuaian
    koneksi.execute(
        """INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan, komoditas)
           VALUES (?, '2026-10-31', 'PA-001', 'umum', 'Penyesuaian', 'umum')""",
        (period_id,),
    )

    # Customer & piutang overdue
    koneksi.execute("INSERT INTO customers (nama, tipe) VALUES ('Pak Budi', 'reguler')")
    cust_id = koneksi.execute("SELECT last_insert_rowid()").fetchone()[0]
    akun_piutang_id = koneksi.execute("SELECT id FROM accounts WHERE kode_akun='1201'").fetchone()[0]

    koneksi.execute(
        """INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan, komoditas, pihak_terkait)
           VALUES (?, '2026-10-01', 'PJ-002', 'penjualan', 'Jual tempo', 'cabai', 'Pak Budi')""",
        (period_id,),
    )
    je_tempo_id = koneksi.execute("SELECT last_insert_rowid()").fetchone()[0]
    koneksi.executemany(
        "INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit) VALUES (?,?,?,?)",
        [
            (je_tempo_id, akun_piutang_id, 3_000_000, 0),
            (je_tempo_id, akun_jual_id, 0, 3_000_000),
        ],
    )
    koneksi.execute(
        """INSERT INTO receivables
           (journal_entry_id, customer_id, no_faktur, tanggal_faktur, tanggal_jatuh_tempo, jumlah, jumlah_terbayar, status)
           VALUES (?, ?, 'F-001', '2026-10-01', '2026-10-08', 3000000, 0, 'belum_lunas')""",
        (je_tempo_id, cust_id),
    )

    # Item & inventory
    koneksi.execute(
        "INSERT INTO items (kode_item, nama_item, satuan, tipe, komoditas) VALUES ('PUP-01','Pupuk NPK','kg','bahan','cabai')"
    )
    item_id = koneksi.execute("SELECT last_insert_rowid()").fetchone()[0]
    koneksi.execute(
        """INSERT INTO inventory_movements
           (item_id, tanggal, tipe_gerakan, qty, harga_satuan, total_nilai, saldo_qty, saldo_nilai, harga_rata2)
           VALUES (?, '2026-10-01', 'masuk', 100, 5000, 500000, 100, 500000, 5000)""",
        (item_id,),
    )

    koneksi.commit()
    return period_id


@pytest.fixture()
def db(tmp_path: Path):
    """Fixture: database SQLite sementara dengan data contoh."""
    path_db = tmp_path / "test_dashboard.db"
    koneksi = sqlite3.connect(str(path_db))
    koneksi.row_factory = sqlite3.Row
    _buat_schema(koneksi)
    period_id = _isi_data_contoh(koneksi)

    def factory():
        conn = sqlite3.connect(str(path_db))
        conn.row_factory = sqlite3.Row
        return conn

    with patch("services.dashboard_service.get_connection", side_effect=factory):
        yield period_id

    koneksi.close()


# ---------------------------------------------------------------------------
# TEST: ambil_saldo_kas_bank
# ---------------------------------------------------------------------------

class TestAmbilSaldoKasBank:
    def test_mengembalikan_dict_dengan_key_yang_benar(self, db):
        result = ambil_saldo_kas_bank(db)
        assert "kas" in result
        assert "bank" in result
        assert "total" in result

    def test_saldo_kas_termasuk_saldo_awal(self, db):
        """Kas awal 5jt + kredit 500rb dari beli pupuk = 5jt - 500rb + 2jt penjualan = 6.5jt"""
        result = ambil_saldo_kas_bank(db)
        # Kas: saldo_awal 5jt + debit_mutasi 2jt - kredit_mutasi 500rb = 6.5jt
        assert result["kas"] == 6_500_000

    def test_saldo_bank_dari_saldo_awal(self, db):
        result = ambil_saldo_kas_bank(db)
        assert result["bank"] == 10_000_000

    def test_total_adalah_kas_plus_bank(self, db):
        result = ambil_saldo_kas_bank(db)
        assert result["total"] == result["kas"] + result["bank"]

    def test_semua_nilai_integer(self, db):
        result = ambil_saldo_kas_bank(db)
        for key in ["kas", "bank", "total"]:
            assert isinstance(result[key], int), f"{key} harus int"


# ---------------------------------------------------------------------------
# TEST: ambil_piutang_overdue
# ---------------------------------------------------------------------------

class TestAmbilPiutangOverdue:
    def test_mengembalikan_list(self, db):
        result = ambil_piutang_overdue(hari_ini=date(2026, 11, 1))
        assert isinstance(result, list)

    def test_piutang_overdue_terdeteksi(self, db):
        """Piutang jatuh tempo 2026-10-08, cek di 2026-11-01 → overdue"""
        result = ambil_piutang_overdue(hari_ini=date(2026, 11, 1))
        assert len(result) == 1
        assert result[0]["no_faktur"] == "F-001"

    def test_piutang_belum_jatuh_tempo_tidak_muncul(self, db):
        """Cek di 2026-10-07 → belum jatuh tempo"""
        result = ambil_piutang_overdue(hari_ini=date(2026, 10, 7))
        assert len(result) == 0

    def test_field_lengkap(self, db):
        result = ambil_piutang_overdue(hari_ini=date(2026, 11, 1))
        assert len(result) == 1
        baris = result[0]
        for key in ["no_faktur", "pelanggan", "sisa_piutang", "tanggal_jatuh_tempo", "hari_telat"]:
            assert key in baris, f"Key '{key}' tidak ada"

    def test_sisa_piutang_benar(self, db):
        result = ambil_piutang_overdue(hari_ini=date(2026, 11, 1))
        assert result[0]["sisa_piutang"] == 3_000_000


# ---------------------------------------------------------------------------
# TEST: ambil_ringkasan_penjualan_beban
# ---------------------------------------------------------------------------

class TestRingkasanPenjualanBeban:
    def test_mengembalikan_dict(self, db):
        result = ambil_ringkasan_penjualan_beban(db)
        assert isinstance(result, dict)
        for key in ["penjualan", "beban", "laba_kotor"]:
            assert key in result

    def test_penjualan_benar(self, db):
        """2 transaksi penjualan: 2jt tunai + 3jt tempo = 5jt"""
        result = ambil_ringkasan_penjualan_beban(db)
        assert result["penjualan"] == 5_000_000

    def test_beban_benar(self, db):
        """1 transaksi beban: 500rb"""
        result = ambil_ringkasan_penjualan_beban(db)
        assert result["beban"] == 500_000

    def test_laba_kotor_benar(self, db):
        result = ambil_ringkasan_penjualan_beban(db)
        assert result["laba_kotor"] == result["penjualan"] - result["beban"]

    def test_semua_nilai_integer(self, db):
        result = ambil_ringkasan_penjualan_beban(db)
        for key in ["penjualan", "beban", "laba_kotor"]:
            assert isinstance(result[key], int)


# ---------------------------------------------------------------------------
# TEST: ambil_stok_persediaan
# ---------------------------------------------------------------------------

class TestAmbilStokPersediaan:
    def test_mengembalikan_list(self, db):
        result = ambil_stok_persediaan()
        assert isinstance(result, list)

    def test_ada_satu_item(self, db):
        result = ambil_stok_persediaan()
        assert len(result) == 1

    def test_field_lengkap(self, db):
        result = ambil_stok_persediaan()
        baris = result[0]
        for key in ["kode_item", "nama_item", "satuan", "saldo_qty", "saldo_nilai"]:
            assert key in baris

    def test_saldo_benar(self, db):
        result = ambil_stok_persediaan()
        assert result[0]["saldo_qty"] == 100
        assert result[0]["saldo_nilai"] == 500_000


# ---------------------------------------------------------------------------
# TEST: ambil_ringkasan_jurnal
# ---------------------------------------------------------------------------

class TestAmbilRingkasanJurnal:
    def test_mengembalikan_dict(self, db):
        result = ambil_ringkasan_jurnal(db)
        assert isinstance(result, dict)

    def test_total_transaksi(self, db):
        """Data contoh: 1 penjualan tunai + 1 pengeluaran + 1 penjualan tempo = 3 transaksi
           (penyesuaian PA-001 dikecualikan)"""
        result = ambil_ringkasan_jurnal(db)
        assert result["total_transaksi"] == 3

    def test_jumlah_per_jenis(self, db):
        result = ambil_ringkasan_jurnal(db)
        assert result["penjualan"] == 2
        assert result["pengeluaran_kas"] == 1

    def test_jurnal_penyesuaian_tidak_terhitung(self, db):
        """PA- tidak masuk ringkasan"""
        result = ambil_ringkasan_jurnal(db)
        assert result["umum"] == 0  # PA-001 dikecualikan


# ---------------------------------------------------------------------------
# TEST: cek_progress_siklus
# ---------------------------------------------------------------------------

class TestCekProgressSiklus:
    def test_mengembalikan_dict_bool(self, db):
        result = cek_progress_siklus(db)
        assert isinstance(result, dict)
        for key in ["ada_transaksi", "ada_penyesuaian", "ada_penutup", "periode_tutup"]:
            assert key in result
            assert isinstance(result[key], bool)

    def test_ada_transaksi_benar(self, db):
        result = cek_progress_siklus(db)
        assert result["ada_transaksi"] is True

    def test_ada_penyesuaian_benar(self, db):
        result = cek_progress_siklus(db)
        assert result["ada_penyesuaian"] is True

    def test_belum_ada_penutup(self, db):
        result = cek_progress_siklus(db)
        assert result["ada_penutup"] is False

    def test_periode_masih_buka(self, db):
        result = cek_progress_siklus(db)
        assert result["periode_tutup"] is False


# ---------------------------------------------------------------------------
# TEST: ambil_penjualan_per_komoditas
# ---------------------------------------------------------------------------

class TestAmbilPenjualanPerKomoditas:
    def test_mengembalikan_dataframe(self, db):
        import pandas as pd
        result = ambil_penjualan_per_komoditas(db)
        assert isinstance(result, pd.DataFrame)

    def test_kolom_ada(self, db):
        result = ambil_penjualan_per_komoditas(db)
        if not result.empty:
            assert "komoditas" in result.columns
            assert "penjualan" in result.columns

    def test_penjualan_cabai(self, db):
        result = ambil_penjualan_per_komoditas(db)
        assert not result.empty
        cabai_row = result[result["komoditas"] == "cabai"]
        assert not cabai_row.empty
        # 2jt + 3jt penjualan cabai
        assert int(cabai_row["penjualan"].iloc[0]) == 5_000_000


# ---------------------------------------------------------------------------
# TEST: ambil_period_id_aktif & ambil_info_periode
# ---------------------------------------------------------------------------

class TestPeriodeHelpers:
    def test_period_id_aktif_ditemukan(self, db):
        result = ambil_period_id_aktif()
        assert result is not None
        assert isinstance(result, int)

    def test_ambil_info_periode(self, db):
        result = ambil_info_periode(db)
        assert result is not None
        assert result["nama_bulan"] == "Oktober"
        assert result["tahun"] == 2026
        assert result["status"] == "buka"

    def test_ambil_info_periode_tidak_ada(self, db):
        result = ambil_info_periode(999)
        assert result is None
