"""Regression tests for receivable payment links and journal deletion."""

import sqlite3


def _db_piutang(tmp_path, monkeypatch):
    db_path = tmp_path / "piutang_payment.db"

    def buka_koneksi():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    conn = buka_koneksi()
    conn.executescript("""
        CREATE TABLE periods (
            id INTEGER PRIMARY KEY,
            tahun INTEGER NOT NULL,
            bulan INTEGER NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            kode_akun TEXT NOT NULL,
            kategori TEXT NOT NULL
        );
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            nama TEXT NOT NULL
        );
        CREATE TABLE journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id INTEGER NOT NULL REFERENCES periods(id),
            tanggal TEXT NOT NULL,
            no_bukti TEXT NOT NULL UNIQUE,
            journal_type TEXT NOT NULL,
            keterangan TEXT NOT NULL,
            komoditas TEXT DEFAULT 'cabai',
            pihak_terkait TEXT
        );
        CREATE TABLE journal_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
            account_id INTEGER NOT NULL REFERENCES accounts(id),
            debit INTEGER NOT NULL DEFAULT 0,
            kredit INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE receivables (
            id INTEGER PRIMARY KEY,
            journal_entry_id INTEGER NOT NULL REFERENCES journal_entries(id),
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            no_faktur TEXT NOT NULL,
            tanggal_faktur TEXT NOT NULL,
            tanggal_jatuh_tempo TEXT NOT NULL,
            jumlah INTEGER NOT NULL,
            jumlah_terbayar INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL
        );
        CREATE TABLE receivable_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receivable_id INTEGER NOT NULL REFERENCES receivables(id) ON DELETE CASCADE,
            journal_entry_id INTEGER NOT NULL UNIQUE REFERENCES journal_entries(id) ON DELETE CASCADE,
            jumlah_bayar INTEGER NOT NULL CHECK (jumlah_bayar > 0)
        );
        INSERT INTO periods VALUES (1, 2026, 1, 'buka');
        INSERT INTO accounts VALUES (1, '1110', 'Aset'), (2, '1120', 'Aset');
        INSERT INTO customers VALUES (1, 'Pelanggan Uji');
        INSERT INTO journal_entries
            (id, period_id, tanggal, no_bukti, journal_type, keterangan)
        VALUES (10, 1, '2026-01-01', 'JL-001', 'penjualan', 'Penjualan tempo');
        INSERT INTO receivables
            (id, journal_entry_id, customer_id, no_faktur, tanggal_faktur,
             tanggal_jatuh_tempo, jumlah, jumlah_terbayar, status)
        VALUES (1, 10, 1, 'JL-001', '2026-01-01', '2026-01-08', 100000, 0, 'belum_lunas');
    """)
    conn.commit()
    conn.close()

    monkeypatch.setattr("services.transaction_service.get_connection", buka_koneksi)
    monkeypatch.setattr("services.journal_service.get_connection", buka_koneksi)

    nomor = {"nilai": 0}

    def nomor_bukti(prefix, periode):
        nomor["nilai"] += 1
        return f"{prefix}-{periode}-{nomor['nilai']:03d}"

    def simpan_jurnal(period_id, tanggal, no_bukti, journal_type, keterangan,
                      baris, komoditas="cabai", pihak_terkait=None):
        conn = buka_koneksi()
        try:
            cur = conn.execute("""
                INSERT INTO journal_entries
                    (period_id, tanggal, no_bukti, journal_type, keterangan, komoditas, pihak_terkait)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (period_id, tanggal, no_bukti, journal_type, keterangan, komoditas, pihak_terkait))
            entry_id = cur.lastrowid
            for line in baris:
                conn.execute("""
                    INSERT INTO journal_lines
                        (journal_entry_id, account_id, debit, kredit)
                    VALUES (?, ?, ?, ?)
                """, (entry_id, line["account_id"], line["debit"], line["kredit"]))
            conn.commit()
            return entry_id
        finally:
            conn.close()

    monkeypatch.setattr("services.transaction_service._label_periode", lambda _: "JAN26")
    monkeypatch.setattr("services.transaction_service.generate_nomor_bukti", nomor_bukti)
    monkeypatch.setattr("services.transaction_service.simpan_jurnal", simpan_jurnal)
    return buka_koneksi


def test_hapus_jurnal_pembayaran_memulihkan_saldo_piutang_dan_status(tmp_path, monkeypatch):
    buka_koneksi = _db_piutang(tmp_path, monkeypatch)

    from services.transaction_service import catat_penerimaan_piutang
    from services.journal_service import hapus_jurnal

    pembayaran_pertama = catat_penerimaan_piutang(
        1, 1, "2026-01-02", 40000, 1, 2
    )
    pembayaran_kedua = catat_penerimaan_piutang(
        1, 1, "2026-01-03", 60000, 1, 2
    )

    conn = buka_koneksi()
    row = conn.execute(
        "SELECT jumlah_terbayar, status FROM receivables WHERE id = 1"
    ).fetchone()
    conn.close()
    assert tuple(row) == (100000, "lunas")

    hapus_jurnal(pembayaran_pertama)

    conn = buka_koneksi()
    try:
        row = conn.execute(
            "SELECT jumlah_terbayar, status FROM receivables WHERE id = 1"
        ).fetchone()
        assert tuple(row) == (60000, "sebagian")
        assert conn.execute(
            "SELECT COUNT(*) FROM receivable_payments WHERE journal_entry_id = ?",
            (pembayaran_pertama,),
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM receivable_payments WHERE journal_entry_id = ?",
            (pembayaran_kedua,),
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_status_piutang_sebagian_setelah_pembayaran_pertama(tmp_path, monkeypatch):
    buka_koneksi = _db_piutang(tmp_path, monkeypatch)

    from services.transaction_service import catat_penerimaan_piutang

    catat_penerimaan_piutang(1, 1, "2026-01-02", 25000, 1, 2)

    conn = buka_koneksi()
    try:
        row = conn.execute(
            "SELECT jumlah_terbayar, status FROM receivables WHERE id = 1"
        ).fetchone()
        assert tuple(row) == (25000, "sebagian")
        assert conn.execute("SELECT COUNT(*) FROM receivable_payments").fetchone()[0] == 1
    finally:
        conn.close()
