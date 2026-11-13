"""
tests/test_transactions.py
---------------------------
Tujuan  : Menguji semua fungsi transaction_service dan journal_service Fase 2.
          Setiap test menggunakan database in-memory sehingga tidak mengubah
          data produksi.
Input   : Panggil langsung fungsi service dengan data uji.
Output  : Semua jurnal harus seimbang, receivables harus terbentuk, dll.
Dipanggil oleh : pytest tests/ -v
"""

import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from services.journal_service import (
    validasi_jurnal_seimbang,
    ambil_semua_jurnal,
    ambil_jurnal_dengan_baris,
    hapus_jurnal,
    buat_pratinjau_jurnal,
)
from services.transaction_service import buat_baris_pratinjau


# ================================================================
# FIXTURES
# ================================================================

@pytest.fixture
def db_in_memory():
    """
    Buat database SQLite in-memory dengan schema minimal untuk testing.
    Setiap test mendapat database bersih.
    """
    koneksi = sqlite3.connect(":memory:")
    koneksi.row_factory = sqlite3.Row
    koneksi.executescript("""
        CREATE TABLE periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tahun INTEGER NOT NULL,
            bulan INTEGER NOT NULL,
            nama_bulan TEXT NOT NULL,
            status TEXT DEFAULT 'buka'
        );
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_akun TEXT UNIQUE NOT NULL,
            nama_akun TEXT NOT NULL,
            kategori TEXT NOT NULL,
            saldo_normal TEXT NOT NULL,
            is_kontra INTEGER DEFAULT 0,
            aktif INTEGER DEFAULT 1
        );
        CREATE TABLE journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id INTEGER NOT NULL,
            tanggal TEXT NOT NULL,
            no_bukti TEXT UNIQUE NOT NULL,
            journal_type TEXT NOT NULL,
            keterangan TEXT,
            komoditas TEXT DEFAULT 'cabai',
            pihak_terkait TEXT,
            FOREIGN KEY (period_id) REFERENCES periods(id)
        );
        CREATE TABLE journal_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            debit INTEGER DEFAULT 0,
            kredit INTEGER DEFAULT 0,
            keterangan TEXT,
            FOREIGN KEY (journal_entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE
        );
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            aktif INTEGER DEFAULT 1
        );
        CREATE TABLE receivables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER,
            customer_id INTEGER,
            no_faktur TEXT NOT NULL,
            tanggal_faktur TEXT NOT NULL,
            jatuh_tempo TEXT NOT NULL,
            jumlah INTEGER NOT NULL,
            jumlah_terbayar INTEGER DEFAULT 0,
            status TEXT DEFAULT 'belum_lunas'
        );
        CREATE TABLE parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kunci TEXT UNIQUE NOT NULL,
            nilai TEXT NOT NULL,
            satuan TEXT,
            catatan TEXT
        );
        CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_item TEXT,
            nama_item TEXT NOT NULL,
            satuan TEXT,
            tipe TEXT,
            komoditas TEXT,
            account_id INTEGER,
            aktif INTEGER DEFAULT 1
        );
        CREATE TABLE inventory_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            journal_entry_id INTEGER,
            tanggal TEXT NOT NULL,
            tipe_gerakan TEXT NOT NULL,
            qty REAL NOT NULL,
            harga_satuan INTEGER NOT NULL,
            total_nilai INTEGER NOT NULL,
            saldo_qty REAL,
            saldo_nilai INTEGER,
            harga_rata2 INTEGER,
            keterangan TEXT
        );

        -- Data awal
        INSERT INTO periods (tahun, bulan, nama_bulan, status) VALUES (2026, 10, 'Oktober 2026', 'buka');
        INSERT INTO accounts (kode_akun, nama_akun, kategori, saldo_normal)
            VALUES ('1101', 'Kas', 'Aset', 'Debit'),
                   ('1201', 'Piutang Usaha', 'Aset', 'Debit'),
                   ('1301', 'Persediaan Bahan', 'Aset', 'Debit'),
                   ('2101', 'Utang Usaha', 'Liabilitas', 'Kredit'),
                   ('3101', 'Modal Disetor', 'Ekuitas', 'Kredit'),
                   ('4101', 'Penjualan Cabai', 'Pendapatan', 'Kredit'),
                   ('5101', 'Beban Bahan Produksi', 'Beban Produksi', 'Debit'),
                   ('6101', 'Beban Listrik', 'Beban Operasional', 'Debit');
        INSERT INTO customers (nama) VALUES ('Pak Budi');
        INSERT INTO parameters (kunci, nilai) VALUES ('jatuh_tempo_piutang_hari', '7');
        INSERT INTO items (nama_item, satuan, tipe) VALUES ('Pupuk NPK', 'kg', 'bahan');
    """)
    return koneksi


# ================================================================
# TEST: VALIDASI JURNAL SEIMBANG
# ================================================================

class TestValidasiJurnal:
    """Uji fungsi validasi keseimbangan jurnal."""

    def test_jurnal_seimbang_lulus(self):
        """Jurnal dengan debit == kredit harus lolos tanpa error."""
        baris = [
            {"debit": 1_000_000, "kredit": 0},
            {"debit": 0, "kredit": 1_000_000},
        ]
        total_d, total_k = validasi_jurnal_seimbang(baris)
        assert total_d == total_k == 1_000_000

    def test_jurnal_tidak_seimbang_error(self):
        """Jurnal dengan debit != kredit harus raise ValueError."""
        baris = [
            {"debit": 1_000_000, "kredit": 0},
            {"debit": 0, "kredit": 500_000},  # kurang kredit
        ]
        with pytest.raises(ValueError, match="tidak seimbang"):
            validasi_jurnal_seimbang(baris)

    def test_jurnal_multi_baris_seimbang(self):
        """Jurnal dengan banyak baris harus tetap seimbang."""
        baris = [
            {"debit": 500_000, "kredit": 0},
            {"debit": 300_000, "kredit": 0},
            {"debit": 0, "kredit": 800_000},
        ]
        total_d, total_k = validasi_jurnal_seimbang(baris)
        assert total_d == total_k == 800_000

    def test_jurnal_nol_seimbang(self):
        """Jurnal dengan semua nilai 0 harus seimbang."""
        baris = [{"debit": 0, "kredit": 0}]
        total_d, total_k = validasi_jurnal_seimbang(baris)
        assert total_d == total_k == 0


# ================================================================
# TEST: PRATINJAU JURNAL
# ================================================================

class TestPratinjauJurnal:
    """Uji fungsi pratinjau (tanpa simpan)."""

    def test_buat_pratinjau_format_benar(self):
        """Pratinjau harus menghasilkan dict dengan kolom Akun, Debit, Kredit."""
        nama_akun_map = {
            1: {"kode_akun": "1101", "nama_akun": "Kas"},
            6: {"kode_akun": "4101", "nama_akun": "Penjualan"},
        }
        baris = [
            {"account_id": 1, "debit": 500_000, "kredit": 0},
            {"account_id": 6, "debit": 0, "kredit": 500_000},
        ]
        hasil = buat_pratinjau_jurnal(baris, nama_akun_map)
        assert len(hasil) == 2
        assert hasil[0]["Akun"] == "1101 - Kas"
        assert hasil[0]["Debit"] == 500_000
        assert hasil[1]["Kredit"] == 500_000

    def test_pratinjau_akun_tidak_dikenal(self):
        """Akun yang tidak ada di map harus tetap tampil dengan '?'."""
        nama_akun_map = {}
        baris = [{"account_id": 999, "debit": 100_000, "kredit": 0}]
        hasil = buat_pratinjau_jurnal(baris, nama_akun_map)
        assert "?" in hasil[0]["Akun"]


# ================================================================
# TEST: SIMPAN DAN AMBIL JURNAL (dengan mock DB)
# ================================================================

class TestAmbilJurnal:
    """Uji fungsi ambil_semua_jurnal dan ambil_jurnal_dengan_baris."""

    def test_ambil_jurnal_kembalikan_dataframe(self, db_in_memory):
        """ambil_semua_jurnal harus kembalikan DataFrame (meski kosong)."""
        with patch("services.journal_service.get_connection", return_value=db_in_memory):
            df = ambil_semua_jurnal()
        assert hasattr(df, "columns")  # adalah DataFrame

    def test_ambil_jurnal_dengan_baris_tidak_ada(self, db_in_memory):
        """Entry yang tidak ada harus kembalikan dict kosong."""
        with patch("services.journal_service.get_connection", return_value=db_in_memory):
            hasil = ambil_jurnal_dengan_baris(99999)
        assert hasil["header"] == {}
        assert hasil["baris"] == []

    def test_simpan_dan_ambil_jurnal(self, db_in_memory):
        """Jurnal yang disimpan harus bisa diambil kembali."""
        # Simpan langsung via SQL tanpa menutup koneksi
        db_in_memory.execute("""
            INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan)
            VALUES (1, '2026-10-15', 'TEST-001', 'penerimaan_kas', 'Test jurnal')
        """)
        db_in_memory.commit()
        entry_id = db_in_memory.execute(
            "SELECT id FROM journal_entries WHERE no_bukti = 'TEST-001'"
        ).fetchone()["id"]
        db_in_memory.execute(
            "INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit) VALUES (?, 1, 1000000, 0)",
            (entry_id,)
        )
        db_in_memory.execute(
            "INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit) VALUES (?, 6, 0, 1000000)",
            (entry_id,)
        )
        db_in_memory.commit()

        with patch("services.journal_service.get_connection", return_value=db_in_memory):
            hasil = ambil_jurnal_dengan_baris(entry_id)
        assert hasil["header"]["no_bukti"] == "TEST-001"
        assert len(hasil["baris"]) == 2


# ================================================================
# TEST: HAPUS JURNAL
# ================================================================

class TestHapusJurnal:
    """Uji fungsi hapus_jurnal."""

    def test_hapus_jurnal_periode_buka(self, db_in_memory):
        """Jurnal pada periode buka harus bisa dihapus (tidak raise error)."""
        # Buat entry langsung via SQL
        db_in_memory.execute("""
            INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan)
            VALUES (1, '2026-10-15', 'HAPUS-001', 'umum', 'Test hapus')
        """)
        db_in_memory.commit()
        entry_id = db_in_memory.execute(
            "SELECT id FROM journal_entries WHERE no_bukti = 'HAPUS-001'"
        ).fetchone()["id"]

        # hapus_jurnal harus berhasil tanpa raise exception
        with patch("services.journal_service.get_connection", return_value=db_in_memory):
            # Jika tidak raise, hapus berhasil
            try:
                hapus_jurnal(entry_id)
                hapus_berhasil = True
            except Exception:
                hapus_berhasil = False

        assert hapus_berhasil, "hapus_jurnal seharusnya berhasil pada periode buka"

    def test_hapus_jurnal_periode_tutup(self, db_in_memory):
        """Jurnal pada periode tutup harus raise PermissionError."""
        # Tutup periode
        db_in_memory.execute("UPDATE periods SET status = 'tutup' WHERE id = 1")
        db_in_memory.commit()

        with patch("services.journal_service.get_connection", return_value=db_in_memory):
            from services.journal_service import simpan_jurnal
            # Karena periode sudah tutup, simpan_jurnal tetap bisa (tidak ada validasi periode di sana)
            # tapi kita perlu entry yang ada dulu — tambahkan langsung
            db_in_memory.execute("""
                INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan)
                VALUES (1, '2026-10-15', 'TUTUP-001', 'umum', 'Test periode tutup')
            """)
            db_in_memory.commit()
            entry_id = db_in_memory.execute(
                "SELECT id FROM journal_entries WHERE no_bukti = 'TUTUP-001'"
            ).fetchone()["id"]

            with pytest.raises(PermissionError):
                hapus_jurnal(entry_id)

    def test_hapus_jurnal_tidak_ada(self, db_in_memory):
        """Entry yang tidak ada harus raise ValueError."""
        with patch("services.journal_service.get_connection", return_value=db_in_memory):
            with pytest.raises(ValueError):
                hapus_jurnal(99999)


# ================================================================
# TEST: BARIS PRATINJAU (buat_baris_pratinjau)
# ================================================================

class TestBuatBarisPratinjau:
    """Uji fungsi buat_baris_pratinjau di transaction_service."""

    def test_pratinjau_menghasilkan_dataframe(self, db_in_memory):
        """buat_baris_pratinjau harus menghasilkan DataFrame."""
        import pandas as pd
        with patch("services.transaction_service.get_connection", return_value=db_in_memory):
            baris = [
                {"account_id": 1, "debit": 2_000_000, "kredit": 0},
                {"account_id": 6, "debit": 0, "kredit": 2_000_000},
            ]
            df = buat_baris_pratinjau(baris, [1, 6])
        assert isinstance(df, pd.DataFrame)
        assert "Akun" in df.columns
        assert "Debit" in df.columns
        assert "Kredit" in df.columns

    def test_pratinjau_total_baris_terakhir(self, db_in_memory):
        """Baris terakhir pratinjau harus berisi total."""
        with patch("services.transaction_service.get_connection", return_value=db_in_memory):
            baris = [
                {"account_id": 1, "debit": 1_500_000, "kredit": 0},
                {"account_id": 6, "debit": 0, "kredit": 1_500_000},
            ]
            df = buat_baris_pratinjau(baris, [1, 6])

        baris_total = df[df["Akun"] == "**TOTAL**"]
        assert not baris_total.empty
        assert int(baris_total.iloc[0]["Debit"]) == 1_500_000
        assert int(baris_total.iloc[0]["Kredit"]) == 1_500_000
