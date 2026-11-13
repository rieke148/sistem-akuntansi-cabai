"""
tests/test_trial_balance.py
-----------------------------
Tujuan  : Pengujian otomatis untuk trial_balance_service, payroll_service,
          dan adjusting_service.
Input   : Database file sementara (tmp_path fixture dari pytest).
Output  : Laporan pytest (semua test harus lulus).
Dipanggil oleh : pytest (dari direktori root proyek)

Mencakup pengujian:
1. hitung_neraca_saldo() — kolom benar, saldo akun benar, validasi seimbang
2. validasi_neraca_saldo_seimbang() — benar/tidak seimbang
3. hitung_upah_pekerja() — perhitungan upah
4. ambil_rekap_absensi() — struktur DataFrame dan total hari
5. adjusting_service — amortisasi, akrual, cek sudah ada

CATATAN TEKNIS:
  sqlite3.Connection.close adalah read-only di Python 3.14+, sehingga
  trick conn.close = lambda: None tidak bisa dipakai.
  Solusi: gunakan file DB sementara (tmp_path) agar setiap get_connection()
  yang baru tetap membaca data yang sama.
"""

import sqlite3
import pytest
import pandas as pd
from unittest.mock import patch


# ============================================================
# HELPER: Setup database file sementara untuk testing
# ============================================================

def _buat_db_file(path: str) -> str:
    """
    Buat database SQLite file sementara dengan skema dan data minimal.
    Mengembalikan path file DB yang bisa dipakai oleh mock get_connection.
    """
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Skema tabel
    cur.executescript("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY, kode_akun TEXT, nama_akun TEXT,
            kategori TEXT, saldo_normal TEXT,
            is_kontra INTEGER DEFAULT 0, aktif INTEGER DEFAULT 1
        );
        CREATE TABLE periods (
            id INTEGER PRIMARY KEY, tahun INTEGER, bulan INTEGER,
            nama_bulan TEXT, status TEXT DEFAULT 'buka'
        );
        CREATE TABLE opening_balances (
            id INTEGER PRIMARY KEY, period_id INTEGER, account_id INTEGER,
            saldo_debit INTEGER DEFAULT 0, saldo_kredit INTEGER DEFAULT 0, catatan TEXT,
            UNIQUE(period_id, account_id)
        );
        CREATE TABLE journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, period_id INTEGER,
            tanggal TEXT, no_bukti TEXT UNIQUE, journal_type TEXT,
            keterangan TEXT, komoditas TEXT DEFAULT 'cabai', pihak_terkait TEXT,
            dibuat_pada TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE journal_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT, journal_entry_id INTEGER,
            account_id INTEGER, debit INTEGER DEFAULT 0, kredit INTEGER DEFAULT 0,
            keterangan TEXT,
            CHECK((debit > 0 AND kredit = 0) OR (kredit > 0 AND debit = 0))
        );
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY, nama TEXT, tipe_pekerja TEXT,
            upah_harian INTEGER, komoditas TEXT DEFAULT 'cabai', aktif INTEGER DEFAULT 1
        );
        CREATE TABLE attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id INTEGER,
            period_id INTEGER, periode_bayar TEXT,
            hari_kerja INTEGER DEFAULT 0, total_upah INTEGER DEFAULT 0,
            sudah_dibayar INTEGER DEFAULT 0, journal_entry_id INTEGER
        );
        CREATE TABLE fixed_assets (
            id INTEGER PRIMARY KEY, kode_aset TEXT, nama_aset TEXT, kategori_aset TEXT,
            tanggal_perolehan TEXT, harga_perolehan INTEGER,
            nilai_residu INTEGER DEFAULT 0, umur_ekonomis_tahun INTEGER DEFAULT 1,
            jumlah_unit INTEGER DEFAULT 1, is_disusutkan INTEGER DEFAULT 1,
            account_id INTEGER, account_akum_id INTEGER, aktif INTEGER DEFAULT 1, keterangan TEXT
        );
    """)

    # Data dasar
    cur.executescript("""
        INSERT INTO accounts VALUES (1, '1101', 'Kas', 'Aset', 'Debit', 0, 1);
        INSERT INTO accounts VALUES (2, '4101', 'Penjualan', 'Pendapatan', 'Kredit', 0, 1);
        INSERT INTO accounts VALUES (3, '5105', 'Beban Upah', 'Beban Produksi', 'Debit', 0, 1);
        INSERT INTO accounts VALUES (4, '2201', 'Utang Gaji', 'Liabilitas', 'Kredit', 0, 1);
        INSERT INTO accounts VALUES (5, '1502K', 'Akum Penyusutan Bangunan', 'Aset', 'Kredit', 1, 1);

        INSERT INTO periods VALUES (1, 2026, 10, 'Oktober 2026', 'buka');

        INSERT INTO opening_balances VALUES (1, 1, 1, 500000000, 0, '');
        INSERT INTO opening_balances VALUES (2, 1, 2, 0, 0, '');

        INSERT INTO journal_entries(id, period_id, tanggal, no_bukti, journal_type, keterangan)
        VALUES (1, 1, '2026-10-05', 'JU-001', 'penjualan', 'Penjualan cabai');
        INSERT INTO journal_lines(journal_entry_id, account_id, debit, kredit)
        VALUES (1, 1, 10000000, 0);
        INSERT INTO journal_lines(journal_entry_id, account_id, debit, kredit)
        VALUES (1, 2, 0, 10000000);

        INSERT INTO employees VALUES (1, 'Ahmad Suparto', 'tetap', 90000, 'cabai', 1);
        INSERT INTO employees VALUES (2, 'Budi Santoso', 'tetap', 90000, 'cabai', 1);
    """)

    conn.commit()
    conn.close()
    return path


def _make_conn_factory(db_path: str):
    """Membuat factory function yang mengembalikan koneksi baru ke file DB."""
    def factory():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c
    return factory


# ============================================================
# TEST: trial_balance_service.hitung_neraca_saldo()
# ============================================================

class TestHitungNeracaSaldo:
    """Test untuk fungsi hitung_neraca_saldo()."""

    def test_kolom_df_lengkap(self, tmp_path):
        """DataFrame hasil harus punya kolom yang benar."""
        from services.trial_balance_service import hitung_neraca_saldo
        db = _buat_db_file(str(tmp_path / "ns1.db"))
        factory = _make_conn_factory(db)

        with patch("services.trial_balance_service.get_connection", side_effect=factory):
            df = hitung_neraca_saldo(period_id=1)

        assert set(df.columns) == {"kode_akun", "nama_akun", "kategori", "saldo_normal", "debit", "kredit"}

    def test_saldo_kas_benar(self, tmp_path):
        """
        Kas: saldo awal Rp500jt + debit Rp10jt dari penjualan = Rp510jt
        → tampil di kolom debit (saldo normal Debit)
        """
        from services.trial_balance_service import hitung_neraca_saldo
        db = _buat_db_file(str(tmp_path / "ns2.db"))
        factory = _make_conn_factory(db)

        with patch("services.trial_balance_service.get_connection", side_effect=factory):
            df = hitung_neraca_saldo(period_id=1)

        baris_kas = df[df["kode_akun"] == "1101"]
        assert not baris_kas.empty
        assert int(baris_kas.iloc[0]["debit"]) == 510_000_000
        assert int(baris_kas.iloc[0]["kredit"]) == 0

    def test_saldo_penjualan_benar(self, tmp_path):
        """
        Penjualan: saldo awal 0 + kredit Rp10jt = Rp10jt
        → tampil di kolom kredit (saldo normal Kredit)
        """
        from services.trial_balance_service import hitung_neraca_saldo
        db = _buat_db_file(str(tmp_path / "ns3.db"))
        factory = _make_conn_factory(db)

        with patch("services.trial_balance_service.get_connection", side_effect=factory):
            df = hitung_neraca_saldo(period_id=1)

        baris_penjualan = df[df["kode_akun"] == "4101"]
        assert not baris_penjualan.empty
        assert int(baris_penjualan.iloc[0]["kredit"]) == 10_000_000
        assert int(baris_penjualan.iloc[0]["debit"]) == 0

    def test_neraca_seimbang(self, tmp_path):
        """
        Total kolom debit == total kolom kredit (neraca seimbang).
        Perlu saldo awal yang seimbang:
          Kas Rp500jt (Debit) ↔ Modal Disetor Rp500jt (Kredit)
          Penjualan Rp10jt (Kredit) ↔ Kas Rp10jt (Debit, dari jurnal)
        """
        from services.trial_balance_service import hitung_neraca_saldo, validasi_neraca_saldo_seimbang
        db = _buat_db_file(str(tmp_path / "ns4.db"))

        # Tambah akun Modal Disetor dan saldo awal yang seimbang
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO accounts VALUES (6, '3101', 'Modal Disetor', 'Ekuitas', 'Kredit', 0, 1)")
        # Saldo awal: Kas Dr 500jt ↔ Modal Kr 500jt
        conn.execute("INSERT INTO opening_balances VALUES (3, 1, 6, 0, 500000000, 'Modal awal')")
        conn.commit()
        conn.close()

        factory = _make_conn_factory(db)

        with patch("services.trial_balance_service.get_connection", side_effect=factory):
            df = hitung_neraca_saldo(period_id=1)

        seimbang, total_debit, total_kredit = validasi_neraca_saldo_seimbang(df)
        assert seimbang, f"Tidak seimbang: debit={total_debit}, kredit={total_kredit}"
        assert total_debit == total_kredit

    def test_filter_penyesuaian_dikecualikan(self, tmp_path):
        """
        Jurnal dengan no_bukti 'PA-...' harus dikecualikan dari NS sebelum penyesuaian.
        """
        from services.trial_balance_service import hitung_neraca_saldo
        db = _buat_db_file(str(tmp_path / "ns5.db"))

        # Tambah jurnal penyesuaian ke DB
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        conn.execute("""
            INSERT INTO journal_entries(id, period_id, tanggal, no_bukti, journal_type, keterangan)
            VALUES (10, 1, '2026-10-31', 'PA-PENYUSUTAN-1-1', 'umum', 'Penyesuaian penyusutan')
        """)
        conn.execute("INSERT INTO journal_lines(journal_entry_id, account_id, debit, kredit) VALUES (10, 3, 500000, 0)")
        conn.execute("INSERT INTO journal_lines(journal_entry_id, account_id, debit, kredit) VALUES (10, 5, 0, 500000)")
        conn.commit()
        conn.close()

        factory = _make_conn_factory(db)

        with patch("services.trial_balance_service.get_connection", side_effect=factory):
            df_sebelum = hitung_neraca_saldo(period_id=1, termasuk_penyesuaian=False)

        with patch("services.trial_balance_service.get_connection", side_effect=factory):
            df_sesudah = hitung_neraca_saldo(period_id=1, termasuk_penyesuaian=True)

        # Beban Upah (5105) tidak boleh ada di NS sebelum penyesuaian
        beban_sebelum = df_sebelum[df_sebelum["kode_akun"] == "5105"]
        beban_sesudah = df_sesudah[df_sesudah["kode_akun"] == "5105"]

        assert beban_sebelum.empty or int(beban_sebelum.iloc[0]["debit"]) == 0
        assert not beban_sesudah.empty and int(beban_sesudah.iloc[0]["debit"]) == 500_000

    def test_akun_dengan_saldo_nol_tidak_ditampilkan(self, tmp_path):
        """Akun yang belum pernah dipakai (saldo 0 total) tidak muncul di NS."""
        from services.trial_balance_service import hitung_neraca_saldo
        db = _buat_db_file(str(tmp_path / "ns6.db"))
        factory = _make_conn_factory(db)

        with patch("services.trial_balance_service.get_connection", side_effect=factory):
            df = hitung_neraca_saldo(period_id=1)

        # Akun 2201 (Utang Gaji) belum pernah dipakai → tidak muncul
        baris_utang = df[df["kode_akun"] == "2201"]
        assert baris_utang.empty


# ============================================================
# TEST: trial_balance_service.validasi_neraca_saldo_seimbang()
# ============================================================

class TestValidasiNeracaSaldo:
    """Test untuk fungsi validasi_neraca_saldo_seimbang()."""

    def test_df_seimbang(self):
        """DataFrame dengan total debit == kredit harus return seimbang=True."""
        from services.trial_balance_service import validasi_neraca_saldo_seimbang

        df = pd.DataFrame([
            {"kode_akun": "1101", "debit": 500_000_000, "kredit": 0},
            {"kode_akun": "3101", "debit": 0, "kredit": 500_000_000},
        ])
        seimbang, total_d, total_k = validasi_neraca_saldo_seimbang(df)
        assert seimbang is True
        assert total_d == 500_000_000
        assert total_k == 500_000_000

    def test_df_tidak_seimbang(self):
        """DataFrame dengan total debit != kredit harus return seimbang=False."""
        from services.trial_balance_service import validasi_neraca_saldo_seimbang

        df = pd.DataFrame([
            {"kode_akun": "1101", "debit": 500_000_000, "kredit": 0},
            {"kode_akun": "3101", "debit": 0, "kredit": 400_000_000},
        ])
        seimbang, total_d, total_k = validasi_neraca_saldo_seimbang(df)
        assert seimbang is False
        assert total_d != total_k

    def test_df_kosong(self):
        """DataFrame kosong harus return seimbang=True dengan semua nol."""
        from services.trial_balance_service import validasi_neraca_saldo_seimbang

        df = pd.DataFrame(columns=["kode_akun", "debit", "kredit"])
        seimbang, total_d, total_k = validasi_neraca_saldo_seimbang(df)
        assert seimbang is True
        assert total_d == 0
        assert total_k == 0


# ============================================================
# TEST: payroll_service.hitung_upah_pekerja()
# ============================================================

class TestHitungUpahPekerja:
    """Test untuk fungsi hitung_upah_pekerja()."""

    def test_upah_pekerja_tetap(self, tmp_path):
        """Pekerja tetap: 14 hari × Rp90.000 = Rp1.260.000."""
        from services.payroll_service import hitung_upah_pekerja
        db = _buat_db_file(str(tmp_path / "pay1.db"))
        factory = _make_conn_factory(db)

        with patch("services.payroll_service.get_connection", side_effect=factory):
            hasil = hitung_upah_pekerja(employee_id=1, hari_kerja=14)

        assert hasil["total_upah"] == 14 * 90_000
        assert hasil["hari_kerja"] == 14
        assert hasil["upah_harian"] == 90_000
        assert hasil["tipe_pekerja"] == "tetap"

    def test_upah_nol_hari(self, tmp_path):
        """0 hari kerja → total upah = 0."""
        from services.payroll_service import hitung_upah_pekerja
        db = _buat_db_file(str(tmp_path / "pay2.db"))
        factory = _make_conn_factory(db)

        with patch("services.payroll_service.get_connection", side_effect=factory):
            hasil = hitung_upah_pekerja(employee_id=1, hari_kerja=0)

        assert hasil["total_upah"] == 0

    def test_pekerja_tidak_ada_error(self, tmp_path):
        """Pekerja ID yang tidak ada harus raise ValueError."""
        from services.payroll_service import hitung_upah_pekerja
        db = _buat_db_file(str(tmp_path / "pay3.db"))
        factory = _make_conn_factory(db)

        with patch("services.payroll_service.get_connection", side_effect=factory):
            with pytest.raises(ValueError, match="tidak ditemukan"):
                hitung_upah_pekerja(employee_id=9999, hari_kerja=10)

    def test_upah_tambahan_lebih_tinggi(self, tmp_path):
        """Pekerja tambahan: Rp120.000/hari > Rp90.000/hari."""
        from services.payroll_service import hitung_upah_pekerja
        db = _buat_db_file(str(tmp_path / "pay4.db"))

        # Tambah pekerja tambahan
        conn = sqlite3.connect(db)
        conn.execute("""
            INSERT INTO employees VALUES (10, 'Tenaga Tambahan', 'tambahan', 120000, 'cabai', 1)
        """)
        conn.commit()
        conn.close()

        factory = _make_conn_factory(db)

        with patch("services.payroll_service.get_connection", side_effect=factory):
            hasil = hitung_upah_pekerja(employee_id=10, hari_kerja=10)

        assert hasil["total_upah"] == 10 * 120_000
        assert hasil["upah_harian"] == 120_000


# ============================================================
# TEST: payroll_service.ambil_rekap_absensi()
# ============================================================

class TestAmbilRekapAbsensi:
    """Test untuk fungsi ambil_rekap_absensi()."""

    def test_struktur_df(self, tmp_path):
        """DataFrame hasil harus punya kolom yang benar."""
        from services.payroll_service import ambil_rekap_absensi
        db = _buat_db_file(str(tmp_path / "rek1.db"))
        factory = _make_conn_factory(db)

        with patch("services.payroll_service.get_connection", side_effect=factory):
            df = ambil_rekap_absensi(period_id=1)

        kolom_wajib = {"nama", "tipe_pekerja", "hari_minggu1", "hari_minggu2",
                       "total_hari", "upah_harian", "total_upah"}
        assert kolom_wajib.issubset(set(df.columns))

    def test_rekap_berisi_semua_pekerja(self, tmp_path):
        """Rekap harus berisi semua pekerja aktif meskipun belum ada absensi."""
        from services.payroll_service import ambil_rekap_absensi
        db = _buat_db_file(str(tmp_path / "rek2.db"))
        factory = _make_conn_factory(db)

        with patch("services.payroll_service.get_connection", side_effect=factory):
            df = ambil_rekap_absensi(period_id=1)

        # 2 pekerja dari data dasar
        assert len(df) == 2

    def test_total_hari_dihitung_benar(self, tmp_path):
        """total_hari = hari_minggu1 + hari_minggu2."""
        from services.payroll_service import ambil_rekap_absensi
        db = _buat_db_file(str(tmp_path / "rek3.db"))

        # Tambah absensi
        conn = sqlite3.connect(db)
        conn.execute("""
            INSERT INTO attendance(employee_id, period_id, periode_bayar, hari_kerja, total_upah, sudah_dibayar)
            VALUES (1, 1, 'minggu1', 10, 900000, 1)
        """)
        conn.execute("""
            INSERT INTO attendance(employee_id, period_id, periode_bayar, hari_kerja, total_upah, sudah_dibayar)
            VALUES (1, 1, 'minggu2', 12, 1080000, 0)
        """)
        conn.commit()
        conn.close()

        factory = _make_conn_factory(db)

        with patch("services.payroll_service.get_connection", side_effect=factory):
            df = ambil_rekap_absensi(period_id=1)

        baris_ahmad = df[df["nama"] == "Ahmad Suparto"].iloc[0]
        assert int(baris_ahmad["hari_minggu1"]) == 10
        assert int(baris_ahmad["hari_minggu2"]) == 12
        assert int(baris_ahmad["total_hari"]) == 22
        assert int(baris_ahmad["total_upah"]) == 22 * 90_000


# ============================================================
# TEST: adjusting_service
# ============================================================

class TestAdjustingService:
    """Test untuk fungsi-fungsi di adjusting_service."""

    def test_buat_penyesuaian_akrual_upah_nol(self):
        """Akrual upah dengan jumlah = 0 harus return 0 (tidak ada jurnal dibuat)."""
        from services.adjusting_service import buat_penyesuaian_akrual_upah

        # Fungsi langsung return 0 jika jumlah_akrual <= 0 (sebelum panggil get_connection)
        hasil = buat_penyesuaian_akrual_upah(
            period_id=1, tanggal="2026-10-31",
            akun_beban_upah_id=3, akun_utang_gaji_id=4,
            jumlah_akrual=0,
        )
        assert hasil == 0

    def test_amortisasi_mulsa_kalkulasi(self):
        """
        Pembuktian rumus amortisasi:
        5 blok × Rp400.000 = Rp2.000.000 total
        Rp2.000.000 ÷ 18 bulan = Rp111.111 (pembulatan bawah integer)
        """
        from services.depreciation_service import hitung_amortisasi_mulsa_bulanan

        hasil = hitung_amortisasi_mulsa_bulanan(400_000, 5, 1.5)
        assert hasil == 111_111  # 2.000.000 // 18

    def test_amortisasi_mulsa_berbeda_parameter(self):
        """Amortisasi dengan 3 blok saja: 3 × 400.000 = 1.200.000 ÷ 18 = 66.666."""
        from services.depreciation_service import hitung_amortisasi_mulsa_bulanan

        hasil = hitung_amortisasi_mulsa_bulanan(400_000, 3, 1.5)
        assert hasil == 66_666  # 1.200.000 // 18

    def test_amortisasi_mulsa_1_blok(self):
        """1 blok × Rp400.000 ÷ 18 = Rp22.222."""
        from services.depreciation_service import hitung_amortisasi_mulsa_bulanan

        hasil = hitung_amortisasi_mulsa_bulanan(400_000, 1, 1.5)
        assert hasil == 22_222  # 400.000 // 18

    def test_ambil_ringkasan_penyesuaian_kosong(self, tmp_path):
        """Tanpa jurnal penyesuaian, harus return DataFrame kosong."""
        from services.adjusting_service import ambil_ringkasan_penyesuaian
        db = _buat_db_file(str(tmp_path / "adj1.db"))
        factory = _make_conn_factory(db)

        with patch("services.adjusting_service.get_connection", side_effect=factory):
            df = ambil_ringkasan_penyesuaian(period_id=1)

        assert df.empty

    def test_cek_penyesuaian_sudah_ada_false(self, tmp_path):
        """cek_penyesuaian_sudah_ada harus return False jika belum ada."""
        from services.adjusting_service import cek_penyesuaian_sudah_ada
        db = _buat_db_file(str(tmp_path / "adj2.db"))
        factory = _make_conn_factory(db)

        with patch("services.adjusting_service.get_connection", side_effect=factory):
            hasil = cek_penyesuaian_sudah_ada(period_id=1, jenis="mulsa")

        assert hasil is False

    def test_cek_penyesuaian_sudah_ada_true(self, tmp_path):
        """cek_penyesuaian_sudah_ada harus return True jika sudah ada."""
        from services.adjusting_service import cek_penyesuaian_sudah_ada
        db = _buat_db_file(str(tmp_path / "adj3.db"))

        # Tambah jurnal penyesuaian mulsa
        conn = sqlite3.connect(db)
        conn.execute("""
            INSERT INTO journal_entries(period_id, tanggal, no_bukti, journal_type, keterangan)
            VALUES (1, '2026-10-31', 'PA-MULSA-1', 'umum', 'Amortisasi mulsa')
        """)
        conn.commit()
        conn.close()

        factory = _make_conn_factory(db)

        with patch("services.adjusting_service.get_connection", side_effect=factory):
            hasil = cek_penyesuaian_sudah_ada(period_id=1, jenis="mulsa")

        assert hasil is True

    def test_ambil_ringkasan_penyesuaian_ada_data(self, tmp_path):
        """Jika ada jurnal PA-, harus muncul di ringkasan."""
        from services.adjusting_service import ambil_ringkasan_penyesuaian
        db = _buat_db_file(str(tmp_path / "adj4.db"))

        conn = sqlite3.connect(db)
        conn.execute("""
            INSERT INTO journal_entries(id, period_id, tanggal, no_bukti, journal_type, keterangan)
            VALUES (99, 1, '2026-10-31', 'PA-MULSA-1', 'umum', 'Amortisasi mulsa')
        """)
        conn.execute("INSERT INTO journal_lines(journal_entry_id, account_id, debit, kredit) VALUES (99, 3, 111111, 0)")
        conn.execute("INSERT INTO journal_lines(journal_entry_id, account_id, debit, kredit) VALUES (99, 5, 0, 111111)")
        conn.commit()
        conn.close()

        factory = _make_conn_factory(db)

        with patch("services.adjusting_service.get_connection", side_effect=factory):
            df = ambil_ringkasan_penyesuaian(period_id=1)

        assert len(df) == 1
        assert df.iloc[0]["no_bukti"] == "PA-MULSA-1"
        assert int(df.iloc[0]["total_debit"]) == 111_111
