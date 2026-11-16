"""
tests/test_inventory_account_migration.py
-----------------------------------------
Memastikan enam akun bahan lama disatukan ke 1301 tanpa menggabungkan
akun Persediaan Cabai (1307) atau menghapus rincian kartu stok per item.
"""

import sqlite3

from database.schema import migrasikan_akun_persediaan_bahan_produksi


def _database_lama(tmp_path, monkeypatch):
    db_path = tmp_path / "akun_persediaan_lama.db"

    def buka_koneksi():
        koneksi = sqlite3.connect(str(db_path))
        koneksi.row_factory = sqlite3.Row
        koneksi.execute("PRAGMA foreign_keys = ON")
        return koneksi

    koneksi = buka_koneksi()
    koneksi.executescript("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_akun TEXT NOT NULL UNIQUE,
            nama_akun TEXT NOT NULL,
            kategori TEXT NOT NULL,
            saldo_normal TEXT NOT NULL,
            is_kontra INTEGER NOT NULL DEFAULT 0,
            aktif INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE periods (id INTEGER PRIMARY KEY);
        CREATE TABLE journal_entries (id INTEGER PRIMARY KEY);
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
            kode_item TEXT NOT NULL,
            nama_item TEXT NOT NULL,
            satuan TEXT NOT NULL,
            tipe TEXT NOT NULL,
            account_id INTEGER REFERENCES accounts(id)
        );

        INSERT INTO accounts
            (id, kode_akun, nama_akun, kategori, saldo_normal)
        VALUES
            (1, '1301', 'Persediaan Bibit Cabai', 'Aset', 'Debit'),
            (2, '1302', 'Persediaan Pupuk', 'Aset', 'Debit'),
            (3, '1303', 'Persediaan Pupuk NPK', 'Aset', 'Debit'),
            (4, '1304', 'Persediaan Pestisida', 'Aset', 'Debit'),
            (5, '1305', 'Persediaan Plastik Mulsa', 'Aset', 'Debit'),
            (6, '1306', 'Persediaan Bambu', 'Aset', 'Debit'),
            (7, '1307', 'Persediaan Cabai Rawit (kg)', 'Aset', 'Debit');

        INSERT INTO periods (id) VALUES (1), (2);
        INSERT INTO journal_entries (id) VALUES (1), (2), (3), (4), (5), (6), (7);

        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit)
        VALUES
            (1, 1, 100, 0), (2, 2, 200, 0), (3, 3, 0, 10),
            (4, 4, 50, 0), (5, 5, 25, 0), (6, 6, 75, 0),
            (7, 7, 500, 0);

        INSERT INTO opening_balances
            (period_id, account_id, saldo_debit, saldo_kredit, catatan)
        VALUES
            (1, 1, 100, 0, 'Saldo bibit'),
            (1, 2, 200, 0, 'Saldo pupuk'),
            (1, 3, 0, 10, 'Saldo NPK'),
            (1, 4, 50, 0, 'Saldo pestisida'),
            (1, 7, 500, 0, 'Saldo cabai'),
            (2, 5, 25, 0, 'Saldo mulsa'),
            (2, 6, 75, 0, 'Saldo bambu');

        INSERT INTO items
            (id, kode_item, nama_item, satuan, tipe, account_id)
        VALUES
            (1, 'BHN-001', 'Bibit', 'batang', 'bahan', 1),
            (2, 'BHN-002', 'Pupuk awal tanam', 'karung', 'bahan', 2),
            (3, 'BHN-003', 'Pupuk NPK', 'paket', 'bahan', 3),
            (4, 'BHN-004', 'Pestisida', 'paket', 'bahan', 4),
            (5, 'BHN-005', 'Plastik mulsa', 'roll', 'bahan', 5),
            (6, 'BHN-006', 'Bambu', 'batang', 'bahan', 6),
            (7, 'HSL-001', 'Cabai', 'kg', 'hasil_panen', 7);
    """)
    koneksi.commit()
    koneksi.close()
    monkeypatch.setattr("database.schema.get_connection", buka_koneksi)
    return buka_koneksi


def test_migrasi_menyatukan_enam_akun_bahan_dan_mempertahankan_cabai(tmp_path, monkeypatch):
    buka_koneksi = _database_lama(tmp_path, monkeypatch)

    migrasikan_akun_persediaan_bahan_produksi()

    koneksi = buka_koneksi()
    akun = koneksi.execute(
        "SELECT kode_akun, nama_akun FROM accounts ORDER BY kode_akun"
    ).fetchall()
    assert [(r["kode_akun"], r["nama_akun"]) for r in akun] == [
        ("1301", "Persediaan Bahan Produksi"),
        ("1307", "Persediaan Cabai"),
    ]

    # Seluruh mutasi jurnal bahan dipindahkan ke 1301; jurnal cabai tetap di 1307.
    jumlah_baris = koneksi.execute(
        "SELECT COUNT(*) FROM journal_lines"
    ).fetchone()[0]
    akun_jurnal = koneksi.execute(
        "SELECT DISTINCT a.kode_akun FROM journal_lines jl "
        "JOIN accounts a ON a.id = jl.account_id ORDER BY a.kode_akun"
    ).fetchall()
    assert jumlah_baris == 7
    assert {r["kode_akun"] for r in akun_jurnal} == {"1301", "1307"}

    # Saldo awal bahan dijumlahkan per periode, sedangkan saldo cabai tetap terpisah.
    saldo = koneksi.execute("""
        SELECT a.kode_akun, ob.period_id, ob.saldo_debit, ob.saldo_kredit
        FROM opening_balances ob
        JOIN accounts a ON a.id = ob.account_id
        ORDER BY a.kode_akun, ob.period_id
    """).fetchall()
    hasil_saldo = [
        (r["kode_akun"], r["period_id"], r["saldo_debit"], r["saldo_kredit"])
        for r in saldo
    ]
    assert hasil_saldo == [
        ("1301", 1, 350, 10),
        ("1301", 2, 100, 0),
        ("1307", 1, 500, 0),
    ]

    item = koneksi.execute("""
        SELECT i.tipe, a.kode_akun
        FROM items i JOIN accounts a ON a.id = i.account_id
        ORDER BY i.id
    """).fetchall()
    assert [r["kode_akun"] for r in item] == [
        "1301", "1301", "1301", "1301", "1301", "1301", "1307"
    ]
    assert koneksi.execute("PRAGMA foreign_key_check").fetchall() == []
    koneksi.close()


def test_migrasi_akun_persediaan_aman_dijalankan_ulang(tmp_path, monkeypatch):
    buka_koneksi = _database_lama(tmp_path, monkeypatch)

    migrasikan_akun_persediaan_bahan_produksi()
    migrasikan_akun_persediaan_bahan_produksi()

    koneksi = buka_koneksi()
    saldo = koneksi.execute("""
        SELECT saldo_debit, saldo_kredit
        FROM opening_balances ob
        JOIN accounts a ON a.id = ob.account_id
        WHERE a.kode_akun = '1301' AND ob.period_id = 1
    """).fetchone()
    assert (saldo["saldo_debit"], saldo["saldo_kredit"]) == (350, 10)
    assert koneksi.execute(
        "SELECT COUNT(*) FROM accounts WHERE kode_akun BETWEEN '1301' AND '1306'"
    ).fetchone()[0] == 1
    koneksi.close()
