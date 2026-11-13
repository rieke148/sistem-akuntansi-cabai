"""
tests/test_special_journals.py
--------------------------------
Tujuan  : Menguji 4 fungsi special_journal_service (Fase 3).
          Setiap test menggunakan database in-memory sehingga tidak
          mengubah data produksi.
Input   : Panggil langsung fungsi service dengan mock database.
Output  : Semua fungsi harus mengembalikan DataFrame dengan kolom yang benar.
Dipanggil oleh : pytest tests/ -v
"""

import pytest
import sqlite3
import pandas as pd
from unittest.mock import patch
from services.special_journal_service import (
    ambil_jurnal_penjualan,
    ambil_jurnal_pembelian,
    ambil_jurnal_penerimaan_kas,
    ambil_jurnal_pengeluaran_kas,
    hitung_total_kolom,
)


# ================================================================
# FIXTURE: Database in-memory dengan data minimal
# ================================================================

@pytest.fixture
def db_jurnal():
    """
    Buat database in-memory dengan schema + data contoh untuk 4 jurnal khusus.
    Data contoh mencakup 1 transaksi dari masing-masing journal_type.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE periods (
            id INTEGER PRIMARY KEY,
            tahun INTEGER, bulan INTEGER,
            nama_bulan TEXT, status TEXT DEFAULT 'buka'
        );
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            kode_akun TEXT UNIQUE, nama_akun TEXT,
            kategori TEXT, saldo_normal TEXT, is_kontra INTEGER DEFAULT 0, aktif INTEGER DEFAULT 1
        );
        CREATE TABLE journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id INTEGER, tanggal TEXT, no_bukti TEXT UNIQUE,
            journal_type TEXT, keterangan TEXT,
            komoditas TEXT DEFAULT 'cabai', pihak_terkait TEXT
        );
        CREATE TABLE journal_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER, account_id INTEGER,
            debit INTEGER DEFAULT 0, kredit INTEGER DEFAULT 0, keterangan TEXT
        );
        CREATE TABLE receivables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER, customer_id INTEGER,
            no_faktur TEXT, tanggal_faktur TEXT, tanggal_jatuh_tempo TEXT,
            jumlah INTEGER, jumlah_terbayar INTEGER DEFAULT 0,
            status TEXT DEFAULT 'belum_lunas'
        );

        -- Periode
        INSERT INTO periods VALUES (1, 2026, 10, 'Oktober 2026', 'buka');

        -- Akun COA minimal
        INSERT INTO accounts (id, kode_akun, nama_akun, kategori, saldo_normal)
        VALUES
            (1,  '1101', 'Kas',               'Aset',             'Debit'),
            (2,  '1201', 'Piutang Usaha',      'Aset',             'Debit'),
            (3,  '1301', 'Persediaan Bahan',   'Aset',             'Debit'),
            (4,  '2101', 'Utang Usaha',        'Liabilitas',       'Kredit'),
            (5,  '3101', 'Modal Disetor',      'Ekuitas',          'Kredit'),
            (6,  '4101', 'Penjualan Cabai',    'Pendapatan',       'Kredit'),
            (7,  '5101', 'Beban Upah',         'Beban Produksi',   'Debit'),
            (8,  '6101', 'Beban Listrik',      'Beban Operasional','Debit');

        -- 1. Penjualan Tempo (Sales Journal) — Rp600.000
        INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan, pihak_terkait)
        VALUES (1, '2026-10-05', 'JL-OKT26-001', 'penjualan', 'Jual tempo ke Restoran A', 'Restoran A');
        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit)
        VALUES (1, 2, 600000, 0), (1, 6, 0, 600000);
        INSERT INTO receivables (journal_entry_id, customer_id, no_faktur, tanggal_faktur, tanggal_jatuh_tempo, jumlah)
        VALUES (1, 1, 'JL-OKT26-001', '2026-10-05', '2026-10-12', 600000);

        -- 2. Pembelian Kredit (Purchase Journal) — Rp200.000
        INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan, pihak_terkait)
        VALUES (1, '2026-10-06', 'PB-OKT26-001', 'pembelian', 'Beli kredit pupuk', 'Toko Sido Panen');
        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit)
        VALUES (2, 3, 200000, 0), (2, 4, 0, 200000);

        -- 3. Penerimaan Kas — penjualan tunai Rp900.000
        INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan, pihak_terkait)
        VALUES (1, '2026-10-07', 'KM-OKT26-001', 'penerimaan_kas', 'Jual tunai ke Supermarket B', 'Supermarket B');
        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit)
        VALUES (3, 1, 900000, 0), (3, 6, 0, 900000);

        -- 4. Penerimaan Kas — pelunasan piutang Rp600.000
        INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan, pihak_terkait)
        VALUES (1, '2026-10-12', 'KM-OKT26-002', 'penerimaan_kas', 'Pelunasan piutang Restoran A', 'Restoran A');
        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit)
        VALUES (4, 1, 600000, 0), (4, 2, 0, 600000);

        -- 5. Penerimaan Kas — setoran modal Rp5.000.000
        INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan)
        VALUES (1, '2026-10-01', 'KM-OKT26-000', 'penerimaan_kas', 'Setoran modal awal');
        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit)
        VALUES (5, 1, 5000000, 0), (5, 5, 0, 5000000);

        -- 6. Pengeluaran Kas — beli bahan Rp300.000
        INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan, pihak_terkait)
        VALUES (1, '2026-10-08', 'KK-OKT26-001', 'pengeluaran_kas', 'Beli pupuk tunai', 'Toko Sido Panen');
        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit)
        VALUES (6, 3, 300000, 0), (6, 1, 0, 300000);

        -- 7. Pengeluaran Kas — bayar upah Rp450.000
        INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan)
        VALUES (1, '2026-10-15', 'KK-OKT26-002', 'pengeluaran_kas', 'Bayar upah pekerja');
        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit)
        VALUES (7, 7, 450000, 0), (7, 1, 0, 450000);

        -- 8. Pengeluaran Kas — bayar listrik Rp150.000
        INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan)
        VALUES (1, '2026-10-20', 'KK-OKT26-003', 'pengeluaran_kas', 'Bayar listrik Oktober');
        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit)
        VALUES (8, 8, 150000, 0), (8, 1, 0, 150000);
    """)
    return conn


# ================================================================
# TEST: SALES JOURNAL
# ================================================================

class TestJurnalPenjualan:
    """Uji ambil_jurnal_penjualan."""

    def test_kolom_lengkap(self, db_jurnal):
        """Harus menghasilkan DataFrame dengan kolom yang benar."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_penjualan()
        kolom_wajib = ["tanggal", "no_faktur", "pelanggan", "jatuh_tempo", "piutang_d", "penjualan_k"]
        for kol in kolom_wajib:
            assert kol in df.columns, f"Kolom '{kol}' tidak ditemukan"

    def test_data_benar(self, db_jurnal):
        """Harus mengambil 1 transaksi dengan nilai benar."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_penjualan()
        assert len(df) == 1
        assert int(df.iloc[0]["piutang_d"]) == 600_000
        assert int(df.iloc[0]["penjualan_k"]) == 600_000
        assert df.iloc[0]["pelanggan"] == "Restoran A"

    def test_filter_periode(self, db_jurnal):
        """Filter periode 1 harus mengembalikan data, periode 99 harus kosong."""
        # Test periode 1 (ada data)
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df_ada = ambil_jurnal_penjualan(period_id=1)
        assert len(df_ada) == 1

        # Buat koneksi baru untuk test periode 99
        import sqlite3 as _sqlite3
        conn2 = _sqlite3.connect(":memory:")
        conn2.row_factory = _sqlite3.Row
        conn2.executescript("""
            CREATE TABLE journal_entries (
                id INTEGER PRIMARY KEY, period_id INTEGER, tanggal TEXT,
                no_bukti TEXT, journal_type TEXT, keterangan TEXT,
                komoditas TEXT, pihak_terkait TEXT
            );
            CREATE TABLE journal_lines (
                id INTEGER PRIMARY KEY, journal_entry_id INTEGER,
                account_id INTEGER, debit INTEGER DEFAULT 0, kredit INTEGER DEFAULT 0, keterangan TEXT
            );
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY, kode_akun TEXT, nama_akun TEXT,
                kategori TEXT, saldo_normal TEXT, is_kontra INTEGER DEFAULT 0, aktif INTEGER DEFAULT 1
            );
            CREATE TABLE receivables (
                id INTEGER PRIMARY KEY, journal_entry_id INTEGER, customer_id INTEGER,
                no_faktur TEXT, tanggal_faktur TEXT, tanggal_jatuh_tempo TEXT,
                jumlah INTEGER, jumlah_terbayar INTEGER DEFAULT 0, status TEXT
            );
        """)
        with patch("services.special_journal_service.get_connection", return_value=conn2):
            df_kosong = ambil_jurnal_penjualan(period_id=99)
        conn2.close()
        assert len(df_kosong) == 0

    def test_jurnal_seimbang(self, db_jurnal):
        """Piutang (D) harus == Penjualan (K)."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_penjualan()
        assert df["piutang_d"].sum() == df["penjualan_k"].sum()


# ================================================================
# TEST: PURCHASE JOURNAL
# ================================================================

class TestJurnalPembelian:
    """Uji ambil_jurnal_pembelian."""

    def test_kolom_lengkap(self, db_jurnal):
        """Harus menghasilkan DataFrame dengan kolom yang benar."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_pembelian()
        for kol in ["tanggal", "no_faktur", "supplier", "persediaan_d", "utang_k"]:
            assert kol in df.columns

    def test_data_benar(self, db_jurnal):
        """Harus mengambil 1 transaksi pembelian kredit."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_pembelian()
        assert len(df) == 1
        assert int(df.iloc[0]["persediaan_d"]) == 200_000
        assert int(df.iloc[0]["utang_k"]) == 200_000

    def test_jurnal_seimbang(self, db_jurnal):
        """Persediaan (D) harus == Utang (K)."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_pembelian()
        assert df["persediaan_d"].sum() == df["utang_k"].sum()


# ================================================================
# TEST: CASH RECEIPT JOURNAL
# ================================================================

class TestJurnalPenerimaanKas:
    """Uji ambil_jurnal_penerimaan_kas."""

    def test_kolom_lengkap(self, db_jurnal):
        """Harus menghasilkan DataFrame dengan kolom yang benar."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_penerimaan_kas()
        for kol in ["tanggal", "no_bukti", "keterangan", "kas_d", "piutang_k", "penjualan_k", "lain_lain_k"]:
            assert kol in df.columns

    def test_jumlah_transaksi(self, db_jurnal):
        """Harus mengambil 3 transaksi penerimaan kas (tunai, piutang, setoran)."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_penerimaan_kas()
        assert len(df) == 3

    def test_pivot_penjualan_tunai(self, db_jurnal):
        """Transaksi penjualan tunai: kas_d > 0, penjualan_k > 0, piutang_k = 0."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_penerimaan_kas()
        baris_tunai = df[df["no_bukti"] == "KM-OKT26-001"].iloc[0]
        assert int(baris_tunai["kas_d"]) == 900_000
        assert int(baris_tunai["penjualan_k"]) == 900_000
        assert int(baris_tunai["piutang_k"]) == 0

    def test_pivot_pelunasan_piutang(self, db_jurnal):
        """Transaksi pelunasan piutang: kas_d > 0, piutang_k > 0, penjualan_k = 0."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_penerimaan_kas()
        baris_piutang = df[df["no_bukti"] == "KM-OKT26-002"].iloc[0]
        assert int(baris_piutang["kas_d"]) == 600_000
        assert int(baris_piutang["piutang_k"]) == 600_000
        assert int(baris_piutang["penjualan_k"]) == 0

    def test_pivot_setoran_modal(self, db_jurnal):
        """Transaksi setoran modal: kas_d > 0, lain_lain_k > 0."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_penerimaan_kas()
        baris_modal = df[df["no_bukti"] == "KM-OKT26-000"].iloc[0]
        assert int(baris_modal["kas_d"]) == 5_000_000
        assert int(baris_modal["lain_lain_k"]) == 5_000_000
        assert int(baris_modal["penjualan_k"]) == 0

    def test_total_kas_seimbang(self, db_jurnal):
        """Total Kas (D) == Total semua kolom Kredit."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_penerimaan_kas()
        total_kas = int(df["kas_d"].sum())
        total_kredit = int(df["piutang_k"].sum() + df["penjualan_k"].sum() + df["lain_lain_k"].sum())
        assert total_kas == total_kredit, (
            f"Total Kas (D) = {total_kas} ≠ Total Kredit = {total_kredit}"
        )


# ================================================================
# TEST: CASH PAYMENT JOURNAL
# ================================================================

class TestJurnalPengeluaranKas:
    """Uji ambil_jurnal_pengeluaran_kas."""

    def test_kolom_lengkap(self, db_jurnal):
        """Harus menghasilkan DataFrame dengan kolom yang benar."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_pengeluaran_kas()
        for kol in ["tanggal", "no_bukti", "kas_k", "persediaan_d", "beban_upah_d", "beban_ops_d"]:
            assert kol in df.columns

    def test_jumlah_transaksi(self, db_jurnal):
        """Harus mengambil 3 transaksi pengeluaran kas."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_pengeluaran_kas()
        assert len(df) == 3

    def test_pivot_beli_bahan(self, db_jurnal):
        """Beli bahan tunai: kas_k > 0, persediaan_d > 0, upah = 0."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_pengeluaran_kas()
        baris = df[df["no_bukti"] == "KK-OKT26-001"].iloc[0]
        assert int(baris["kas_k"]) == 300_000
        assert int(baris["persediaan_d"]) == 300_000
        assert int(baris["beban_upah_d"]) == 0

    def test_pivot_bayar_upah(self, db_jurnal):
        """Bayar upah: kas_k > 0, beban_upah_d > 0, persediaan = 0."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_pengeluaran_kas()
        baris = df[df["no_bukti"] == "KK-OKT26-002"].iloc[0]
        assert int(baris["kas_k"]) == 450_000
        assert int(baris["beban_upah_d"]) == 450_000
        assert int(baris["persediaan_d"]) == 0

    def test_pivot_bayar_listrik(self, db_jurnal):
        """Bayar listrik: kas_k > 0, beban_ops_d > 0."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_pengeluaran_kas()
        baris = df[df["no_bukti"] == "KK-OKT26-003"].iloc[0]
        assert int(baris["kas_k"]) == 150_000
        assert int(baris["beban_ops_d"]) == 150_000

    def test_total_kas_seimbang(self, db_jurnal):
        """Total Kas (K) == Total semua kolom Debit."""
        with patch("services.special_journal_service.get_connection", return_value=db_jurnal):
            df = ambil_jurnal_pengeluaran_kas()
        total_kas = int(df["kas_k"].sum())
        total_debit = int(
            df["persediaan_d"].sum()
            + df["beban_upah_d"].sum()
            + df["beban_produksi_d"].sum()
            + df["beban_ops_d"].sum()
            + df["lain_lain_d"].sum()
        )
        assert total_kas == total_debit, (
            f"Total Kas (K) = {total_kas} ≠ Total Debit = {total_debit}"
        )


# ================================================================
# TEST: HELPER hitung_total_kolom
# ================================================================

class TestHitungTotalKolom:
    """Uji fungsi helper hitung_total_kolom."""

    def test_hitung_total_benar(self):
        """Total kolom harus dihitung dengan benar."""
        import pandas as pd
        df = pd.DataFrame({
            "kas_d": [100_000, 200_000, 50_000],
            "penjualan_k": [100_000, 200_000, 50_000],
            "nama": ["A", "B", "C"],
        })
        total = hitung_total_kolom(df, ["kas_d", "penjualan_k"])
        assert total["kas_d"] == 350_000
        assert total["penjualan_k"] == 350_000

    def test_kolom_tidak_ada_diabaikan(self):
        """Kolom yang tidak ada di DataFrame tidak boleh menyebabkan error."""
        import pandas as pd
        df = pd.DataFrame({"kas_d": [100_000]})
        total = hitung_total_kolom(df, ["kas_d", "kolom_tidak_ada"])
        assert "kas_d" in total
        assert "kolom_tidak_ada" not in total
