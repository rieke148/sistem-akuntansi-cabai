"""Regression tests for journal deletion and perpetual inventory recalculation."""

import sqlite3
import pytest


def _db_persediaan(tmp_path, monkeypatch, qty_keluar=50):
    db_path = tmp_path / "hapus_jurnal_persediaan.db"

    def buka_koneksi():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    conn = buka_koneksi()
    conn.executescript("""
        CREATE TABLE periods (
            id INTEGER PRIMARY KEY,
            status TEXT NOT NULL
        );
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            kode_akun TEXT NOT NULL,
            nama_akun TEXT NOT NULL,
            kategori TEXT NOT NULL
        );
        CREATE TABLE journal_entries (
            id INTEGER PRIMARY KEY,
            period_id INTEGER NOT NULL REFERENCES periods(id),
            no_bukti TEXT NOT NULL
        );
        CREATE TABLE journal_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
            account_id INTEGER NOT NULL REFERENCES accounts(id),
            debit INTEGER NOT NULL DEFAULT 0,
            kredit INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            account_id INTEGER NOT NULL REFERENCES accounts(id)
        );
        CREATE TABLE inventory_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL REFERENCES items(id),
            journal_entry_id INTEGER REFERENCES journal_entries(id),
            tanggal TEXT NOT NULL,
            tipe_gerakan TEXT NOT NULL,
            qty REAL NOT NULL,
            harga_satuan INTEGER NOT NULL,
            total_nilai INTEGER NOT NULL,
            saldo_qty REAL NOT NULL,
            saldo_nilai INTEGER NOT NULL,
            harga_rata2 INTEGER NOT NULL
        );
        INSERT INTO periods VALUES (1, 'buka');
        INSERT INTO accounts VALUES
            (1, '1140', 'Persediaan', 'Aset'),
            (2, '5110', 'Harga Pokok Penjualan', 'HPP'),
            (3, '1110', 'Kas', 'Aset');
        INSERT INTO items VALUES (1, 1);
        INSERT INTO journal_entries VALUES
            (1, 1, 'PB-001'),
            (2, 1, 'PB-002'),
            (3, 1, 'JU-003');
        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit) VALUES
            (1, 1, 1000000, 0), (1, 3, 0, 1000000),
            (2, 1, 2000000, 0), (2, 3, 0, 2000000),
            (3, 2, 750000, 0), (3, 1, 0, 750000);
        INSERT INTO inventory_movements
            (item_id, journal_entry_id, tanggal, tipe_gerakan, qty,
             harga_satuan, total_nilai, saldo_qty, saldo_nilai, harga_rata2)
        VALUES
            (1, 1, '2026-01-01', 'masuk', 100, 10000, 1000000, 100, 1000000, 10000),
            (1, 2, '2026-01-02', 'masuk', 100, 20000, 2000000, 200, 3000000, 15000),
            (1, 3, '2026-01-03', 'keluar', ?, 15000, ?, 200-?, 3000000-?, 15000);
    """, (qty_keluar, qty_keluar * 15000, qty_keluar, qty_keluar * 15000))
    conn.commit()
    conn.close()
    monkeypatch.setattr("services.journal_service.get_connection", buka_koneksi)
    return buka_koneksi


def test_hapus_pembelian_menghitung_ulang_hpp_jurnal_penjualan(tmp_path, monkeypatch):
    buka_koneksi = _db_persediaan(tmp_path, monkeypatch, qty_keluar=50)

    from services.journal_service import hapus_jurnal

    hapus_jurnal(1)

    conn = buka_koneksi()
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM journal_entries WHERE id = 1"
        ).fetchone()[0] == 0

        movement = conn.execute("""
            SELECT qty, harga_satuan, total_nilai, saldo_qty, saldo_nilai, harga_rata2
            FROM inventory_movements WHERE journal_entry_id = 3
        """).fetchone()
        assert tuple(movement) == (50, 20000, 1000000, 50, 1000000, 20000)

        lines = conn.execute("""
            SELECT a.kode_akun, jl.debit, jl.kredit
            FROM journal_lines jl JOIN accounts a ON a.id = jl.account_id
            WHERE jl.journal_entry_id = 3 ORDER BY a.kode_akun
        """).fetchall()
        assert [(r["kode_akun"], r["debit"], r["kredit"]) for r in lines] == [
            ("1140", 0, 1000000),
            ("5110", 1000000, 0),
        ]
    finally:
        conn.close()


def test_hapus_pembelian_dibatalkan_jika_membuat_stok_negatif(tmp_path, monkeypatch):
    buka_koneksi = _db_persediaan(tmp_path, monkeypatch, qty_keluar=150)

    from services.journal_service import hapus_jurnal

    with pytest.raises(ValueError, match="stok item.*negatif"):
        hapus_jurnal(1)

    conn = buka_koneksi()
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM journal_entries WHERE id = 1"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM inventory_movements WHERE journal_entry_id = 1"
        ).fetchone()[0] == 1
    finally:
        conn.close()
