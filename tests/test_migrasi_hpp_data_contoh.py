import sqlite3

import pytest

from scripts.migrasi_hpp_data_contoh import (
    MARKER_SALDO_AWAL_NOV,
    hitung_saldo_awal_november,
)


def _buat_db_carry_forward():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            kode_akun TEXT NOT NULL,
            kategori TEXT NOT NULL,
            aktif INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE opening_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            saldo_debit INTEGER NOT NULL DEFAULT 0,
            saldo_kredit INTEGER NOT NULL DEFAULT 0,
            catatan TEXT
        );
        CREATE TABLE journal_entries (
            id INTEGER PRIMARY KEY,
            tanggal TEXT NOT NULL
        );
        CREATE TABLE journal_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            debit INTEGER NOT NULL DEFAULT 0,
            kredit INTEGER NOT NULL DEFAULT 0
        );

        INSERT INTO accounts VALUES
            (1, '1101', 'Aset', 1),
            (2, '1307', 'Aset', 1),
            (3, '2101', 'Liabilitas', 1),
            (4, '3101', 'Ekuitas', 1),
            (5, '3201', 'Ekuitas', 1),
            (6, '3301', 'Ekuitas', 1),
            (7, '4101', 'Pendapatan', 1),
            (8, '4901', 'Pendapatan', 1),
            (9, '5108', 'Beban Produksi', 1),
            (10, '6101', 'Beban Operasional', 1);

        INSERT INTO opening_balances
            (period_id, account_id, saldo_debit, saldo_kredit, catatan)
        VALUES
            (1, 1, 100, 0, 'Saldo awal kas Oktober'),
            (1, 2, 1000, 0, 'Saldo awal stok Oktober'),
            (1, 4, 0, 1100, 'Modal awal Oktober');

        INSERT INTO journal_entries VALUES
            (101, '2026-10-10'),
            (102, '2026-10-15'),
            (103, '2026-10-20');
        INSERT INTO journal_lines
            (journal_entry_id, account_id, debit, kredit)
        VALUES
            (101, 1, 300, 0),
            (101, 7, 0, 300),
            (102, 1, 40, 0),
            (102, 7, 0, 40),
            (103, 10, 50, 0),
            (103, 1, 0, 50);
    """)
    return conn


def _hitung(conn):
    return hitung_saldo_awal_november(
        conn=conn,
        period_oktober_id=1,
        period_november_id=2,
        akun_inv_id=2,
        akun_hpp_id=9,
        akun_penjualan_id=7,
        akun_lain_id=8,
        sales=[{"id": 101, "tanggal": "2026-10-10"}],
        hpp_to_add=[{"entry_id": 101, "hpp": 100}],
        legacy=[{
            "tanggal": "2026-10-15",
            "debit": 0,
            "kredit": 40,
        }],
        nilai_persediaan_awal_november=900,
    )


def test_saldo_awal_november_membawa_akun_permanen_dan_menutup_laba_rugi():
    conn = _buat_db_carry_forward()
    try:
        hasil = _hitung(conn)

        saldo = {
            row["account_id"]: (row["saldo_debit"], row["saldo_kredit"])
            for row in hasil["rows"]
        }

        # Kas: 100 + 300 + 40 - 50; persediaan: 1.000 - HPP 100.
        assert saldo[1] == (390, 0)
        assert saldo[2] == (900, 0)
        assert saldo[4] == (0, 1100)
        # Laba Oktober = pendapatan 340 - HPP 100 - beban 50 = 190.
        assert saldo[5] == (0, 190)
        assert 7 not in saldo
        assert 8 not in saldo
        assert 9 not in saldo
        assert 10 not in saldo
        assert hasil["laba_bersih_oktober"] == 190
        assert hasil["total_debit"] == hasil["total_kredit"] == 1290
        assert hasil["rows_to_insert"] == hasil["rows"]
    finally:
        conn.close()


def test_saldo_awal_november_migrasi_idempoten():
    conn = _buat_db_carry_forward()
    try:
        pertama = _hitung(conn)
        conn.executemany(
            """
            INSERT INTO opening_balances
                (period_id,account_id,saldo_debit,saldo_kredit,catatan)
            VALUES (2,?,?,?,?,?)
            """.replace("VALUES (2,?,?,?,?,?)", "VALUES (2,?,?,?,?)"),
            [
                (
                    row["account_id"],
                    row["saldo_debit"],
                    row["saldo_kredit"],
                    MARKER_SALDO_AWAL_NOV,
                )
                for row in pertama["rows"]
            ],
        )
        kedua = _hitung(conn)
        assert kedua["rows_to_insert"] == []
        assert kedua["rows"] == pertama["rows"]
    finally:
        conn.close()


def test_saldo_awal_november_menolak_saldo_manual_yang_sudah_ada():
    conn = _buat_db_carry_forward()
    try:
        conn.execute(
            """
            INSERT INTO opening_balances
                (period_id,account_id,saldo_debit,saldo_kredit,catatan)
            VALUES (2,1,1,0,'Input manual')
            """
        )
        with pytest.raises(ValueError, match="bukan hasil migrasi ini"):
            _hitung(conn)
    finally:
        conn.close()
