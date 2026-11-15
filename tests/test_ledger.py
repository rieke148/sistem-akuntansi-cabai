"""
tests/test_ledger.py
----------------------
Tujuan  : Pengujian otomatis untuk ledger_service dan subsidiary_service.
Input   : Database in-memory dengan data uji.
Output  : Laporan pytest yang menunjukkan semua test lulus.
Dipanggil oleh : pytest (dari direktori root proyek)

Mencakup pengujian:
1. ambil_buku_besar() — saldo berjalan benar untuk akun Debit & Kredit
2. ambil_saldo_akun() — total saldo akhir akun
3. ambil_semua_saldo_akun() — dict semua akun
4. ambil_bb_piutang() — rincian piutang per faktur/pelanggan
5. ambil_bb_utang() — ringkasan utang usaha per supplier
"""

import sqlite3
from unittest.mock import patch

# ============================================================
# HELPER: Setup database in-memory untuk testing
# ============================================================

def _buat_db_uji() -> sqlite3.Connection:
    """
    Membuat database SQLite in-memory dengan skema minimal untuk testing.
    Berisi tabel yang diperlukan untuk buku besar umum, piutang, dan utang.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Tabel akun
    cur.execute("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            kode_akun TEXT,
            nama_akun TEXT,
            saldo_normal TEXT,  -- 'Debit' atau 'Kredit'
            is_kontra INTEGER DEFAULT 0
        )
    """)

    # Tabel periode
    cur.execute("""
        CREATE TABLE periods (
            id INTEGER PRIMARY KEY,
            tahun INTEGER,
            bulan INTEGER,
            nama_bulan TEXT,
            status TEXT DEFAULT 'buka'
        )
    """)

    # Saldo awal
    cur.execute("""
        CREATE TABLE opening_balances (
            id INTEGER PRIMARY KEY,
            period_id INTEGER,
            account_id INTEGER,
            saldo_debit INTEGER DEFAULT 0,
            saldo_kredit INTEGER DEFAULT 0,
            catatan TEXT
        )
    """)

    # Jurnal entri
    cur.execute("""
        CREATE TABLE journal_entries (
            id INTEGER PRIMARY KEY,
            period_id INTEGER,
            tanggal TEXT,
            no_bukti TEXT,
            keterangan TEXT,
            journal_type TEXT,
            pihak_terkait TEXT
        )
    """)

    # Baris jurnal
    cur.execute("""
        CREATE TABLE journal_lines (
            id INTEGER PRIMARY KEY,
            journal_entry_id INTEGER,
            account_id INTEGER,
            debit INTEGER DEFAULT 0,
            kredit INTEGER DEFAULT 0
        )
    """)

    # Pelanggan
    cur.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            nama TEXT,
            aktif INTEGER DEFAULT 1
        )
    """)

    # Piutang
    cur.execute("""
        CREATE TABLE receivables (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            no_faktur TEXT,
            tanggal_faktur TEXT,
            tanggal_jatuh_tempo TEXT,
            jumlah INTEGER,
            jumlah_terbayar INTEGER DEFAULT 0,
            status TEXT DEFAULT 'belum_lunas'
        )
    """)


    conn.commit()
    return conn


def _isi_data_dasar(conn: sqlite3.Connection) -> None:
    """Mengisi data dasar yang dibutuhkan oleh semua test."""
    cur = conn.cursor()

    # Akun: 1 Debit (Kas), 1 Kredit (Penjualan)
    cur.execute("INSERT INTO accounts VALUES (1, '1101', 'Kas', 'Debit', 0)")
    cur.execute("INSERT INTO accounts VALUES (2, '4101', 'Penjualan', 'Kredit', 0)")
    cur.execute("INSERT INTO accounts VALUES (3, '1201', 'Piutang Usaha', 'Debit', 0)")

    # Periode
    cur.execute("INSERT INTO periods VALUES (1, 2026, 10, 'Oktober', 'buka')")
    cur.execute("INSERT INTO periods VALUES (2, 2026, 11, 'November', 'buka')")

    # Saldo awal Kas = Rp500.000.000 (periode 1)
    cur.execute("INSERT INTO opening_balances VALUES (1, 1, 1, 500000000, 0, 'Saldo awal kas')")
    # Saldo awal Penjualan = Rp0
    cur.execute("INSERT INTO opening_balances VALUES (2, 1, 2, 0, 0, '')")

    # Jurnal: Penjualan Rp10.000.000 (periode 1)
    cur.execute("""
        INSERT INTO journal_entries VALUES
        (1, 1, '2026-10-05', 'JU-001', 'Penjualan cabai tunai', 'penjualan', 'CV. Maju')
    """)
    cur.execute("INSERT INTO journal_lines VALUES (1, 1, 1, 10000000, 0)")    # Kas Debit
    cur.execute("INSERT INTO journal_lines VALUES (2, 1, 2, 0, 10000000)")    # Penjualan Kredit

    # Jurnal: Penerimaan kas Rp5.000.000 (periode 1)
    cur.execute("""
        INSERT INTO journal_entries VALUES
        (2, 1, '2026-10-10', 'JU-002', 'Penjualan cabai tunai kedua', 'penjualan', 'Pasar Induk')
    """)
    cur.execute("INSERT INTO journal_lines VALUES (3, 2, 1, 5000000, 0)")     # Kas Debit
    cur.execute("INSERT INTO journal_lines VALUES (4, 2, 2, 0, 5000000)")     # Penjualan Kredit

    conn.commit()


# ============================================================
# TEST: ledger_service.ambil_buku_besar()
# ============================================================

class TestAmbilBukuBesar:
    """Test untuk fungsi ambil_buku_besar()."""

    def test_kolom_df_lengkap(self):
        """DataFrame hasil ambil_buku_besar() harus punya kolom yang benar."""
        from services.ledger_service import ambil_buku_besar
        conn = _buat_db_uji()
        _isi_data_dasar(conn)

        with patch("services.ledger_service.get_connection", return_value=conn):
            df = ambil_buku_besar(account_id=1, period_id=1)

        assert set(df.columns) == {"tanggal", "no_bukti", "keterangan", "debit", "kredit", "saldo"}
        conn.close()

    def test_saldo_berjalan_akun_debit(self):
        """
        Akun Debit (Kas):
        Saldo Awal = Rp500.000.000
        Debit 10.000.000 → saldo = 510.000.000
        Debit 5.000.000  → saldo = 515.000.000
        """
        from services.ledger_service import ambil_buku_besar
        conn = _buat_db_uji()
        _isi_data_dasar(conn)

        with patch("services.ledger_service.get_connection", return_value=conn):
            df = ambil_buku_besar(account_id=1, period_id=1, sertakan_saldo_awal=True)

        # Harus ada 3 baris: saldo awal + 2 transaksi
        assert len(df) == 3

        # Saldo akhir = 500.000.000 + 10.000.000 + 5.000.000
        saldo_akhir = int(df.iloc[-1]["saldo"])
        assert saldo_akhir == 515_000_000, f"Expected 515000000, got {saldo_akhir}"
        conn.close()

    def test_saldo_berjalan_akun_kredit(self):
        """
        Akun Kredit (Penjualan):
        Saldo Awal = 0
        Kredit 10.000.000 → saldo = 10.000.000
        Kredit 5.000.000  → saldo = 15.000.000
        """
        from services.ledger_service import ambil_buku_besar
        conn = _buat_db_uji()
        _isi_data_dasar(conn)

        with patch("services.ledger_service.get_connection", return_value=conn):
            df = ambil_buku_besar(account_id=2, period_id=1, sertakan_saldo_awal=True)

        # Saldo akhir penjualan = 15.000.000
        saldo_akhir = int(df.iloc[-1]["saldo"])
        assert saldo_akhir == 15_000_000, f"Expected 15000000, got {saldo_akhir}"
        conn.close()

    def test_tanpa_saldo_awal(self):
        """Jika sertakan_saldo_awal=False, tidak ada baris 'Saldo Awal'."""
        from services.ledger_service import ambil_buku_besar
        conn = _buat_db_uji()
        _isi_data_dasar(conn)

        with patch("services.ledger_service.get_connection", return_value=conn):
            df = ambil_buku_besar(account_id=1, period_id=1, sertakan_saldo_awal=False)

        # Hanya 2 baris transaksi
        assert len(df) == 2
        assert "Saldo Awal" not in df["keterangan"].values
        conn.close()

    def test_filter_semua_periode(self):
        """Filter None = semua periode — mengambil semua transaksi."""
        from services.ledger_service import ambil_buku_besar
        conn = _buat_db_uji()
        _isi_data_dasar(conn)

        # Tambah transaksi periode 2
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO journal_entries VALUES
            (3, 2, '2026-11-01', 'JU-003', 'Penjualan November', 'penjualan', 'CV. Maju')
        """)
        cur.execute("INSERT INTO journal_lines VALUES (5, 3, 1, 3000000, 0)")
        cur.execute("INSERT INTO journal_lines VALUES (6, 3, 2, 0, 3000000)")
        conn.commit()

        with patch("services.ledger_service.get_connection", return_value=conn):
            df = ambil_buku_besar(account_id=2, period_id=None, sertakan_saldo_awal=True)

        # 1 baris saldo awal + 3 transaksi (2 Oktober + 1 November)
        assert len(df) == 4
        conn.close()

    def test_akun_tidak_ada_kembalikan_df_kosong(self):
        """Account ID yang tidak ada harus mengembalikan DataFrame kosong."""
        from services.ledger_service import ambil_buku_besar
        conn = _buat_db_uji()

        with patch("services.ledger_service.get_connection", return_value=conn):
            df = ambil_buku_besar(account_id=9999)

        assert df.empty
        conn.close()


# ============================================================
# TEST: ledger_service.ambil_saldo_akun()
# ============================================================

class TestAmbilSaldoAkun:
    """Test untuk fungsi ambil_saldo_akun()."""

    def test_saldo_akun_debit(self):
        """
        Kas: Saldo awal 500jt + debit 10jt + debit 5jt = 515jt
        """
        from services.ledger_service import ambil_saldo_akun
        conn = _buat_db_uji()
        _isi_data_dasar(conn)

        with patch("services.ledger_service.get_connection", return_value=conn):
            saldo = ambil_saldo_akun(account_id=1, period_id=1)

        assert saldo == 515_000_000, f"Expected 515000000, got {saldo}"
        conn.close()

    def test_saldo_akun_kredit(self):
        """
        Penjualan: Saldo awal 0 + kredit 10jt + kredit 5jt = 15jt
        """
        from services.ledger_service import ambil_saldo_akun
        conn = _buat_db_uji()
        _isi_data_dasar(conn)

        with patch("services.ledger_service.get_connection", return_value=conn):
            saldo = ambil_saldo_akun(account_id=2, period_id=1)

        assert saldo == 15_000_000, f"Expected 15000000, got {saldo}"
        conn.close()

    def test_saldo_akun_tidak_ada_return_nol(self):
        """Account ID yang tidak ada harus mengembalikan 0."""
        from services.ledger_service import ambil_saldo_akun
        conn = _buat_db_uji()

        with patch("services.ledger_service.get_connection", return_value=conn):
            saldo = ambil_saldo_akun(account_id=9999)

        assert saldo == 0
        conn.close()

    def test_saldo_tipe_int(self):
        """Hasil harus berupa integer."""
        from services.ledger_service import ambil_saldo_akun
        conn = _buat_db_uji()
        _isi_data_dasar(conn)

        with patch("services.ledger_service.get_connection", return_value=conn):
            saldo = ambil_saldo_akun(account_id=1, period_id=1)

        assert isinstance(saldo, int)
        conn.close()


# ============================================================
# TEST: ledger_service.ambil_semua_saldo_akun()
# ============================================================

class TestAmbilSemuaSaldoAkun:
    """Test untuk fungsi ambil_semua_saldo_akun()."""

    def _buat_db_file(self, tmp_path_str: str) -> str:
        """
        Membuat database SQLite file sementara untuk test ambil_semua_saldo_akun.
        Diperlukan karena fungsi ini memanggil ambil_saldo_akun() berulang kali,
        masing-masing memanggil get_connection() — in-memory DB akan tertutup
        setelah panggilan pertama menggunakan finally: conn.close().
        Solusi: pakai file DB agar koneksi baru tetap membaca data yang sama.
        """
        import os
        db_path = tmp_path_str
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Buat skema
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY, kode_akun TEXT, nama_akun TEXT,
                saldo_normal TEXT, is_kontra INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE periods (
                id INTEGER PRIMARY KEY, tahun INTEGER, bulan INTEGER,
                nama_bulan TEXT, status TEXT DEFAULT 'buka'
            )
        """)
        cur.execute("""
            CREATE TABLE opening_balances (
                id INTEGER PRIMARY KEY, period_id INTEGER, account_id INTEGER,
                saldo_debit INTEGER DEFAULT 0, saldo_kredit INTEGER DEFAULT 0, catatan TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE journal_entries (
                id INTEGER PRIMARY KEY, period_id INTEGER, tanggal TEXT,
                no_bukti TEXT, keterangan TEXT, journal_type TEXT, pihak_terkait TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE journal_lines (
                id INTEGER PRIMARY KEY, journal_entry_id INTEGER,
                account_id INTEGER, debit INTEGER DEFAULT 0, kredit INTEGER DEFAULT 0
            )
        """)

        # Isi data dasar
        cur.execute("INSERT INTO accounts VALUES (1, '1101', 'Kas', 'Debit', 0)")
        cur.execute("INSERT INTO accounts VALUES (2, '4101', 'Penjualan', 'Kredit', 0)")
        cur.execute("INSERT INTO accounts VALUES (3, '1201', 'Piutang Usaha', 'Debit', 0)")
        cur.execute("INSERT INTO periods VALUES (1, 2026, 10, 'Oktober', 'buka')")
        cur.execute("INSERT INTO opening_balances VALUES (1, 1, 1, 500000000, 0, 'Saldo awal kas')")
        cur.execute("INSERT INTO opening_balances VALUES (2, 1, 2, 0, 0, '')")
        cur.execute("""
            INSERT INTO journal_entries VALUES
            (1, 1, '2026-10-05', 'JU-001', 'Penjualan cabai', 'penjualan', 'CV. Maju')
        """)
        cur.execute("INSERT INTO journal_lines VALUES (1, 1, 1, 10000000, 0)")
        cur.execute("INSERT INTO journal_lines VALUES (2, 1, 2, 0, 10000000)")
        cur.execute("""
            INSERT INTO journal_entries VALUES
            (2, 1, '2026-10-10', 'JU-002', 'Penjualan kedua', 'penjualan', 'Pasar Induk')
        """)
        cur.execute("INSERT INTO journal_lines VALUES (3, 2, 1, 5000000, 0)")
        cur.execute("INSERT INTO journal_lines VALUES (4, 2, 2, 0, 5000000)")
        conn.commit()
        conn.close()
        return db_path

    def test_kembalikan_dict(self, tmp_path):
        """Hasil harus berupa dict."""
        import os
        from database.connection import get_connection as real_get_conn
        from services.ledger_service import ambil_semua_saldo_akun

        db_path = self._buat_db_file(str(tmp_path / "test_semua.db"))

        def mock_conn():
            c = sqlite3.connect(db_path)
            c.row_factory = sqlite3.Row
            return c

        with patch("services.ledger_service.get_connection", side_effect=mock_conn):
            hasil = ambil_semua_saldo_akun(period_id=1)

        assert isinstance(hasil, dict)

    def test_dict_berisi_semua_akun(self, tmp_path):
        """Dict harus berisi key untuk setiap akun yang ada di tabel accounts."""
        from services.ledger_service import ambil_semua_saldo_akun

        db_path = self._buat_db_file(str(tmp_path / "test_semua2.db"))

        def mock_conn():
            c = sqlite3.connect(db_path)
            c.row_factory = sqlite3.Row
            return c

        with patch("services.ledger_service.get_connection", side_effect=mock_conn):
            hasil = ambil_semua_saldo_akun(period_id=1)

        # 3 akun: Kas (1), Penjualan (2), Piutang (3)
        assert 1 in hasil
        assert 2 in hasil
        assert 3 in hasil

    def test_nilai_saldo_akun_benar(self, tmp_path):
        """Saldo masing-masing akun harus benar."""
        from services.ledger_service import ambil_semua_saldo_akun

        db_path = self._buat_db_file(str(tmp_path / "test_semua3.db"))

        def mock_conn():
            c = sqlite3.connect(db_path)
            c.row_factory = sqlite3.Row
            return c

        with patch("services.ledger_service.get_connection", side_effect=mock_conn):
            hasil = ambil_semua_saldo_akun(period_id=1)

        # Kas: 515jt, Penjualan: 15jt, Piutang: 0 (tidak ada transaksi piutang)
        assert hasil[1] == 515_000_000
        assert hasil[2] == 15_000_000
        assert hasil[3] == 0


# ============================================================
# TEST: subsidiary_service.ambil_bb_piutang()
# ============================================================

class TestAmbilBbPiutang:
    """Test untuk fungsi ambil_bb_piutang()."""

    def _buat_data_piutang(self, conn: sqlite3.Connection) -> None:
        """Tambah data pelanggan dan piutang untuk testing."""
        cur = conn.cursor()
        cur.execute("INSERT INTO customers VALUES (1, 'CV. Maju Jaya', 1)")
        cur.execute("""
            INSERT INTO receivables VALUES
            (1, 1, 'INV-001', '2026-10-01', '2026-10-31', 10000000, 2000000, 'belum_lunas')
        """)
        cur.execute("""
            INSERT INTO receivables VALUES
            (2, 1, 'INV-002', '2026-10-15', '2026-11-14', 5000000, 5000000, 'lunas')
        """)
        conn.commit()

    def test_kolom_df_lengkap(self):
        """DataFrame harus memiliki kolom yang diharapkan."""
        from services.subsidiary_service import ambil_bb_piutang
        conn = _buat_db_uji()
        self._buat_data_piutang(conn)

        with patch("services.subsidiary_service.get_connection", return_value=conn):
            df = ambil_bb_piutang()

        kolom_wajib = {"no_faktur", "pelanggan", "tanggal_faktur",
                       "tanggal_jatuh_tempo", "jumlah", "jumlah_terbayar",
                       "sisa_piutang", "status", "umur_hari"}
        assert kolom_wajib.issubset(set(df.columns))
        conn.close()

    def test_sisa_piutang_dihitung_benar(self):
        """sisa_piutang = jumlah - jumlah_terbayar."""
        from services.subsidiary_service import ambil_bb_piutang
        conn = _buat_db_uji()
        self._buat_data_piutang(conn)

        with patch("services.subsidiary_service.get_connection", return_value=conn):
            df = ambil_bb_piutang()

        # INV-001: 10jt - 2jt = 8jt sisa
        inv_001 = df[df["no_faktur"] == "INV-001"].iloc[0]
        assert int(inv_001["sisa_piutang"]) == 8_000_000
        conn.close()

    def test_filter_per_pelanggan(self):
        """Filter per customer_id harus mengembalikan data pelanggan itu saja."""
        from services.subsidiary_service import ambil_bb_piutang
        conn = _buat_db_uji()
        self._buat_data_piutang(conn)

        # Tambah pelanggan kedua
        cur = conn.cursor()
        cur.execute("INSERT INTO customers VALUES (2, 'UD. Segar', 1)")
        cur.execute("""
            INSERT INTO receivables VALUES
            (3, 2, 'INV-003', '2026-10-20', '2026-11-20', 3000000, 0, 'belum_lunas')
        """)
        conn.commit()

        with patch("services.subsidiary_service.get_connection", return_value=conn):
            df = ambil_bb_piutang(customer_id=2)

        # Hanya INV-003
        assert len(df) == 1
        assert df.iloc[0]["no_faktur"] == "INV-003"
        conn.close()

    def test_tanpa_data_kembalikan_df_kosong(self):
        """Tanpa data piutang, harus mengembalikan DataFrame kosong (bukan error)."""
        from services.subsidiary_service import ambil_bb_piutang
        conn = _buat_db_uji()

        with patch("services.subsidiary_service.get_connection", return_value=conn):
            df = ambil_bb_piutang()

        assert df.empty
        conn.close()


# ============================================================
# TEST: subsidiary_service.ambil_bb_utang()
# ============================================================

class TestAmbilBbUtang:
    """Test untuk fungsi ambil_bb_utang()."""

    def test_ringkasan_utang_dikelompokkan_per_supplier(self):
        """Kredit ke akun 2101 dijumlahkan untuk setiap supplier."""
        from services.subsidiary_service import ambil_bb_utang

        conn = _buat_db_uji()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO accounts VALUES (4, '2101', 'Utang Usaha', 'Kredit', 0)"
        )
        cur.execute("""
            INSERT INTO journal_entries VALUES
            (3, 1, '2026-10-15', 'PB-001', 'Pembelian kredit', 'pembelian', 'PT. Pupuk Sejahtera')
        """)
        cur.execute("""
            INSERT INTO journal_entries VALUES
            (4, 1, '2026-10-20', 'PB-002', 'Pembelian kredit', 'pembelian', 'PT. Pupuk Sejahtera')
        """)
        cur.execute("""
            INSERT INTO journal_entries VALUES
            (5, 1, '2026-10-22', 'PB-003', 'Pembelian kredit', 'pembelian', 'UD. Tani Makmur')
        """)
        cur.executemany(
            """
            INSERT INTO journal_lines
                (id, journal_entry_id, account_id, debit, kredit)
            VALUES (?, ?, 4, 0, ?)
            """,
            [
                (5, 3, 1_500_000),
                (6, 4, 500_000),
                (7, 5, 750_000),
            ],
        )
        conn.commit()

        with patch("services.subsidiary_service.get_connection", return_value=conn):
            df = ambil_bb_utang()

        utang = {
            row["supplier"]: (
                int(row["total_utang"]),
                int(row["jumlah_transaksi"]),
            )
            for _, row in df.iterrows()
        }
        assert utang["PT. Pupuk Sejahtera"] == (2_000_000, 2)
        assert utang["UD. Tani Makmur"] == (750_000, 1)
        conn.close()

    def test_tanpa_akun_utang_mengembalikan_df_kosong(self):
        """Jika akun 2101 belum tersedia, hasil tetap DataFrame kosong."""
        from services.subsidiary_service import ambil_bb_utang

        conn = _buat_db_uji()
        with patch("services.subsidiary_service.get_connection", return_value=conn):
            df = ambil_bb_utang()

        assert df.empty
        conn.close()
