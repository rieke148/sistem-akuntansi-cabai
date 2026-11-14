"""
tests/test_commodity_migration.py
----------------------------------
Memastikan database lama dapat dimigrasikan ke ruang lingkup komoditas cabai.
"""

import sqlite3

import pytest

from database.schema import migrasikan_komoditas_cabai_saja


@pytest.fixture
def database_lama(tmp_path, monkeypatch):
    """Membuat database uji dengan struktur dan data sebelum pembatasan komoditas."""
    db_path = tmp_path / "database_lama.db"

    def buka_koneksi():
        koneksi = sqlite3.connect(str(db_path))
        koneksi.row_factory = sqlite3.Row
        koneksi.execute("PRAGMA foreign_keys = ON")
        return koneksi

    koneksi = buka_koneksi()
    koneksi.executescript("""
        CREATE TABLE periods (
            id INTEGER PRIMARY KEY
        );

        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_akun TEXT NOT NULL UNIQUE,
            nama_akun TEXT NOT NULL,
            kategori TEXT NOT NULL,
            saldo_normal TEXT NOT NULL,
            is_kontra INTEGER NOT NULL DEFAULT 0,
            aktif INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id INTEGER NOT NULL REFERENCES periods(id),
            tanggal TEXT NOT NULL,
            no_bukti TEXT NOT NULL UNIQUE,
            journal_type TEXT NOT NULL
                CHECK (journal_type IN (
                    'penjualan', 'penerimaan_kas', 'pengeluaran_kas',
                    'pembelian', 'umum'
                )),
            keterangan TEXT NOT NULL,
            komoditas TEXT DEFAULT 'cabai'
                CHECK (komoditas IN ('cabai', 'tanaman_lain', 'umum')),
            pihak_terkait TEXT,
            dibuat_pada TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE journal_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER NOT NULL REFERENCES journal_entries(id),
            account_id INTEGER NOT NULL REFERENCES accounts(id),
            debit INTEGER NOT NULL DEFAULT 0,
            kredit INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE opening_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id INTEGER NOT NULL REFERENCES periods(id),
            account_id INTEGER NOT NULL REFERENCES accounts(id),
            saldo_debit INTEGER NOT NULL DEFAULT 0,
            saldo_kredit INTEGER NOT NULL DEFAULT 0,
            catatan TEXT,
            UNIQUE (period_id, account_id)
        );

        CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_item TEXT NOT NULL UNIQUE,
            nama_item TEXT NOT NULL,
            satuan TEXT NOT NULL,
            tipe TEXT NOT NULL CHECK (tipe IN ('bahan', 'hasil_panen')),
            komoditas TEXT NOT NULL DEFAULT 'cabai'
                CHECK (komoditas IN ('cabai', 'tanaman_lain')),
            account_id INTEGER REFERENCES accounts(id),
            aktif INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE inventory_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL REFERENCES items(id)
        );

        CREATE TABLE employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            tipe_pekerja TEXT NOT NULL DEFAULT 'tetap'
                CHECK (tipe_pekerja IN ('tetap', 'tambahan')),
            upah_harian INTEGER NOT NULL,
            komoditas TEXT NOT NULL DEFAULT 'cabai'
                CHECK (komoditas IN ('cabai', 'tanaman_lain')),
            aktif INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            period_id INTEGER NOT NULL REFERENCES periods(id)
        );

        CREATE TABLE blok_lahan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_blok TEXT NOT NULL UNIQUE,
            jumlah_pohon INTEGER NOT NULL DEFAULT 1000,
            tanggal_tanam TEXT,
            komoditas TEXT NOT NULL DEFAULT 'cabai',
            luas_m2 REAL,
            jarak_tanam_cm REAL DEFAULT 100,
            keterangan TEXT,
            aktif INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE receivables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER NOT NULL REFERENCES journal_entries(id)
        );

        INSERT INTO periods (id) VALUES (1);

        INSERT INTO accounts
            (id, kode_akun, nama_akun, kategori, saldo_normal)
        VALUES
            (1, '4101', 'Penjualan Cabai Rawit', 'Pendapatan', 'Kredit'),
            (2, '4102', 'Akun Pendapatan Lama A', 'Pendapatan', 'Kredit'),
            (3, '4103', 'Akun Pendapatan Lama B', 'Pendapatan', 'Kredit');

        INSERT INTO journal_entries
            (id, period_id, tanggal, no_bukti, journal_type, keterangan, komoditas)
        VALUES
            (1, 1, '2026-10-01', 'PJ-001', 'penjualan', 'Transaksi lama', 'tanaman_lain'),
            (2, 1, '2026-10-02', 'KK-001', 'pengeluaran_kas', 'Biaya umum', 'umum');

        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit)
        VALUES (1, 2, 0, 100), (2, 3, 0, 50);

        INSERT INTO opening_balances
            (period_id, account_id, saldo_debit, saldo_kredit, catatan)
        VALUES
            (1, 1, 100, 0, 'Saldo akun cabai'),
            (1, 2, 20, 0, 'Saldo akun lama A'),
            (1, 3, 0, 30, 'Saldo akun lama B');

        INSERT INTO items (id, kode_item, nama_item, satuan, tipe, komoditas)
        VALUES (1, 'BHN-OLD', 'Item Lama', 'kg', 'bahan', 'tanaman_lain');

        INSERT INTO inventory_movements (item_id) VALUES (1);

        INSERT INTO employees (id, nama, upah_harian, komoditas)
        VALUES (1, 'Pekerja Uji', 90000, 'tanaman_lain');

        INSERT INTO attendance (employee_id, period_id) VALUES (1, 1);

        INSERT INTO blok_lahan (id, kode_blok, komoditas)
        VALUES (1, 'A', 'tanaman_lain');

        INSERT INTO receivables (journal_entry_id) VALUES (1);
    """)
    koneksi.commit()
    koneksi.close()

    monkeypatch.setattr("database.schema.get_connection", buka_koneksi)
    return buka_koneksi


def test_migrasi_mempertahankan_transaksi_dan_menggabungkan_akun(database_lama):
    migrasikan_komoditas_cabai_saja()

    koneksi = database_lama()
    akun = koneksi.execute(
        "SELECT kode_akun FROM accounts ORDER BY kode_akun"
    ).fetchall()
    baris_jurnal = koneksi.execute(
        "SELECT DISTINCT account_id FROM journal_lines"
    ).fetchall()
    saldo = koneksi.execute(
        "SELECT saldo_debit, saldo_kredit FROM opening_balances WHERE account_id = 1"
    ).fetchone()
    entries = koneksi.execute(
        "SELECT id, komoditas FROM journal_entries ORDER BY id"
    ).fetchall()
    assert {row["kode_akun"] for row in akun} == {"4101"}
    assert {row["account_id"] for row in baris_jurnal} == {1}
    assert (saldo["saldo_debit"], saldo["saldo_kredit"]) == (120, 30)
    assert [row["komoditas"] for row in entries] == ["cabai", "umum"]
    assert koneksi.execute("PRAGMA foreign_key_check").fetchall() == []
    koneksi.close()


def test_migrasi_mengubah_master_data_menjadi_cabai(database_lama):
    migrasikan_komoditas_cabai_saja()

    koneksi = database_lama()
    assert koneksi.execute("SELECT komoditas FROM items").fetchone()[0] == "cabai"
    assert koneksi.execute("SELECT komoditas FROM employees").fetchone()[0] == "cabai"
    assert koneksi.execute("SELECT komoditas FROM blok_lahan").fetchone()[0] == "cabai"
    koneksi.close()


def test_skema_baru_menolak_komoditas_selain_cabai(database_lama):
    migrasikan_komoditas_cabai_saja()

    koneksi = database_lama()
    with pytest.raises(sqlite3.IntegrityError):
        koneksi.execute(
            "INSERT INTO items (kode_item, nama_item, satuan, tipe, komoditas) "
            "VALUES ('BHN-X', 'Item Uji', 'kg', 'bahan', 'tanaman_lain')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        koneksi.execute(
            "INSERT INTO employees (nama, upah_harian, komoditas) "
            "VALUES ('Pekerja Baru', 90000, 'tanaman_lain')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        koneksi.execute(
            "INSERT INTO blok_lahan (kode_blok, komoditas) VALUES ('B', 'tanaman_lain')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        koneksi.execute(
            "INSERT INTO journal_entries "
            "(period_id, tanggal, no_bukti, journal_type, keterangan, komoditas) "
            "VALUES (1, '2026-10-03', 'PJ-002', 'penjualan', 'Uji', 'tanaman_lain')"
        )
    koneksi.rollback()
    koneksi.close()
