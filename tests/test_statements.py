"""
tests/test_statements.py
--------------------------
Tujuan  : Pytest untuk logika akuntansi Fase 6:
          - Neraca Lajur (worksheet_service)
          - Laporan Keuangan (statements_service)
          - Jurnal Penutup (closing_service)

Pola yang dipakai (terbukti berhasil di Python 3.14):
  - Gunakan tmp_path untuk database sementara
  - Gunakan side_effect=factory untuk mock get_connection
  - JANGAN assign conn.close = lambda: None (read-only di Py 3.14)
"""

import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch

from services.worksheet_service import (
    buat_neraca_lajur,
    hitung_laba_rugi_dari_lajur,
    validasi_neraca_lajur,
    _hitung_saldo_kolom,
    _pisahkan_lr_neraca,
)
from services.statements_service import (
    susun_laporan_laba_rugi,
    susun_laporan_perubahan_ekuitas,
    susun_neraca,
)
from services.closing_service import (
    preview_jurnal_penutup,
    buat_jurnal_penutup,
    hitung_neraca_saldo_setelah_penutup,
    cek_jurnal_penutup_sudah_ada,
    tutup_periode,
)


# ---------------------------------------------------------------------------
# Fixture: database sementara dengan data minimal
# ---------------------------------------------------------------------------

def _buat_schema(koneksi: sqlite3.Connection) -> None:
    """Membuat tabel yang dibutuhkan oleh semua service."""
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
            no_bukti      TEXT NOT NULL UNIQUE,
            journal_type  TEXT NOT NULL DEFAULT 'umum',
            keterangan    TEXT,
            komoditas     TEXT DEFAULT 'cabai',
            pihak_terkait TEXT
        );

        CREATE TABLE IF NOT EXISTS journal_lines (
            id               INTEGER PRIMARY KEY,
            journal_entry_id INTEGER NOT NULL REFERENCES journal_entries(id),
            account_id       INTEGER NOT NULL REFERENCES accounts(id),
            debit            INTEGER NOT NULL DEFAULT 0,
            kredit           INTEGER NOT NULL DEFAULT 0,
            keterangan       TEXT,
            CHECK (debit >= 0 AND kredit >= 0)
        );

        CREATE TABLE IF NOT EXISTS opening_balances (
            id          INTEGER PRIMARY KEY,
            period_id   INTEGER NOT NULL REFERENCES periods(id),
            account_id  INTEGER NOT NULL REFERENCES accounts(id),
            saldo_debit INTEGER NOT NULL DEFAULT 0,
            saldo_kredit INTEGER NOT NULL DEFAULT 0,
            catatan     TEXT
        );
    """)
    koneksi.commit()


def _isi_data_contoh(koneksi: sqlite3.Connection) -> None:
    """
    Mengisi data contoh minimal untuk pengujian:
    - 1 periode
    - Akun: Kas, Piutang, Modal Disetor, Laba Ditahan, Ikhtisar L/R,
            Penjualan, Beban Upah, Beban Penyusutan
    - Opening balance: Kas 500jt (D), Modal Disetor 500jt (K)
    - Jurnal biasa: penjualan Rp10jt tunai
    - Jurnal penyesuaian (PA-): penyusutan Rp1jt
    """
    koneksi.executescript("""
        -- Akun
        INSERT INTO accounts (id, kode_akun, nama_akun, kategori, saldo_normal) VALUES
            (1,  '1101', 'Kas',                   'Aset',              'Debit'),
            (2,  '1201', 'Piutang Usaha',          'Aset',              'Debit'),
            (3,  '1501', 'Peralatan',              'Aset',              'Debit'),
            (4,  '1501K','Akumulasi Penyusutan',   'Aset',              'Kredit'),
            (5,  '2101', 'Utang Usaha',            'Liabilitas',        'Kredit'),
            (6,  '3101', 'Modal Disetor',          'Ekuitas',           'Kredit'),
            (7,  '3201', 'Laba Ditahan',           'Ekuitas',           'Kredit'),
            (8,  '3301', 'Ikhtisar Laba Rugi',     'Ekuitas',           'Kredit'),
            (9,  '4101', 'Penjualan',              'Pendapatan',        'Kredit'),
            (10, '5106', 'Beban Penyusutan',       'Beban Produksi',    'Debit'),
            (11, '6101', 'Beban Administrasi',     'Beban Operasional', 'Debit');

        -- Periode
        INSERT INTO periods (id, tahun, bulan, nama_bulan, status) VALUES
            (1, 2026, 10, 'Oktober', 'buka');

        -- Saldo awal: Kas 500jt (D), Modal Disetor 500jt (K)
        INSERT INTO opening_balances (period_id, account_id, saldo_debit, saldo_kredit) VALUES
            (1, 1, 500000000, 0),    -- Kas 500jt debit
            (1, 6, 0, 500000000);   -- Modal Disetor 500jt kredit

        -- Jurnal biasa: penjualan tunai Rp10jt
        INSERT INTO journal_entries (id, period_id, tanggal, no_bukti, journal_type, keterangan)
            VALUES (1, 1, '2026-10-05', 'PNK-001', 'penerimaan_kas', 'Penjualan tunai cabai');
        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit) VALUES
            (1, 1, 10000000, 0),    -- Kas +10jt
            (1, 9, 0, 10000000);   -- Penjualan +10jt

        -- Jurnal penyesuaian PA-: penyusutan Rp1jt
        INSERT INTO journal_entries (id, period_id, tanggal, no_bukti, journal_type, keterangan)
            VALUES (2, 1, '2026-10-31', 'PA-PENYUSUTAN-3-1', 'umum', 'Penyesuaian penyusutan peralatan');
        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit) VALUES
            (2, 10, 1000000, 0),    -- Beban Penyusutan +1jt
            (2, 4,  0, 1000000);   -- Akumulasi Penyusutan +1jt
    """)
    koneksi.commit()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Membuat database sementara dengan data contoh."""
    path = tmp_path / "test_statements.db"
    koneksi = sqlite3.connect(str(path))
    koneksi.row_factory = sqlite3.Row
    _buat_schema(koneksi)
    _isi_data_contoh(koneksi)
    koneksi.close()
    return path


@pytest.fixture
def mock_db(db_path: Path):
    """
    Mock get_connection() agar mengembalikan koneksi ke database sementara.
    Gunakan side_effect=factory agar setiap pemanggilan get_connection()
    mendapat koneksi baru (penting untuk service yang close() koneksi).
    """
    def factory():
        koneksi = sqlite3.connect(str(db_path))
        koneksi.row_factory = sqlite3.Row
        return koneksi

    targets = [
        "services.worksheet_service.get_connection",
        "services.trial_balance_service.get_connection",
        "services.statements_service.get_connection",
        "services.closing_service.get_connection",
        "services.journal_service.get_connection",
    ]

    patchers = [patch(t, side_effect=factory) for t in targets]
    mocks = [p.start() for p in patchers]
    yield mocks
    for p in patchers:
        p.stop()


# ---------------------------------------------------------------------------
# Tests: fungsi-fungsi pembantu (unit test murni, tanpa DB)
# ---------------------------------------------------------------------------

class TestFungsiPembantu:
    """Test fungsi pembantu di worksheet_service yang tidak butuh DB."""

    def test_hitung_saldo_kolom_debit_positif(self):
        """Akun debit dengan saldo positif → kolom debit, kredit 0."""
        d, k = _hitung_saldo_kolom(1000, 300, "Debit")
        assert d == 700
        assert k == 0

    def test_hitung_saldo_kolom_debit_negatif(self):
        """Akun debit dengan saldo tidak normal (lebih banyak kredit) → kolom kredit."""
        d, k = _hitung_saldo_kolom(300, 1000, "Debit")
        assert d == 0
        assert k == 700

    def test_hitung_saldo_kolom_kredit_positif(self):
        """Akun kredit dengan saldo positif → kolom kredit, debit 0."""
        d, k = _hitung_saldo_kolom(300, 1000, "Kredit")
        assert d == 0
        assert k == 700

    def test_hitung_saldo_kolom_kredit_negatif(self):
        """Akun kredit dengan saldo tidak normal → kolom debit."""
        d, k = _hitung_saldo_kolom(1000, 300, "Kredit")
        assert d == 700
        assert k == 0

    def test_pisahkan_lr_pendapatan(self):
        """Akun Pendapatan → masuk kolom L/R."""
        lr_d, lr_k, n_d, n_k = _pisahkan_lr_neraca("Pendapatan", 0, 5000)
        assert lr_d == 0
        assert lr_k == 5000
        assert n_d == 0
        assert n_k == 0

    def test_pisahkan_lr_beban_produksi(self):
        """Akun Beban Produksi → masuk kolom L/R."""
        lr_d, lr_k, n_d, n_k = _pisahkan_lr_neraca("Beban Produksi", 3000, 0)
        assert lr_d == 3000
        assert lr_k == 0
        assert n_d == 0
        assert n_k == 0

    def test_pisahkan_lr_beban_operasional(self):
        """Akun Beban Operasional → masuk kolom L/R."""
        lr_d, lr_k, n_d, n_k = _pisahkan_lr_neraca("Beban Operasional", 2000, 0)
        assert lr_d == 2000
        assert lr_k == 0

    def test_pisahkan_neraca_aset(self):
        """Akun Aset → masuk kolom Neraca."""
        lr_d, lr_k, n_d, n_k = _pisahkan_lr_neraca("Aset", 10000, 0)
        assert lr_d == 0
        assert lr_k == 0
        assert n_d == 10000
        assert n_k == 0

    def test_pisahkan_neraca_liabilitas(self):
        """Akun Liabilitas → masuk kolom Neraca."""
        lr_d, lr_k, n_d, n_k = _pisahkan_lr_neraca("Liabilitas", 0, 8000)
        assert n_d == 0
        assert n_k == 8000


# ---------------------------------------------------------------------------
# Tests: Neraca Lajur (worksheet_service)
# ---------------------------------------------------------------------------

class TestNeracaLajur:
    """Test fungsi buat_neraca_lajur() dan turunannya."""

    def test_buat_neraca_lajur_menghasilkan_dataframe(self, mock_db):
        """Neraca lajur harus menghasilkan DataFrame tidak kosong."""
        df = buat_neraca_lajur(1)
        assert not df.empty

    def test_kolom_neraca_lajur_lengkap(self, mock_db):
        """Kolom neraca lajur harus sesuai spesifikasi 10 kolom + info akun."""
        df = buat_neraca_lajur(1)
        kolom_wajib = [
            "kode_akun", "nama_akun", "kategori",
            "ns_debit", "ns_kredit",
            "peny_debit", "peny_kredit",
            "nsd_debit", "nsd_kredit",
            "lr_debit", "lr_kredit",
            "neraca_debit", "neraca_kredit",
        ]
        for kol in kolom_wajib:
            assert kol in df.columns, f"Kolom '{kol}' tidak ada di DataFrame"

    def test_ns_sebelum_penyesuaian_tidak_termasuk_pa(self, mock_db):
        """Kolom NS (sebelum penyesuaian) tidak boleh mencakup jurnal PA-."""
        df = buat_neraca_lajur(1)
        # Beban Penyusutan hanya ada di jurnal PA-, jadi ns_debit-nya harus 0
        baris_beban_penyusutan = df[df["kode_akun"] == "5106"]
        assert not baris_beban_penyusutan.empty, "Beban Penyusutan harus muncul di lajur"
        # Saldo awal ns_debit untuk 5106 = 0 (tidak ada di NS sebelum penyesuaian)
        assert baris_beban_penyusutan.iloc[0]["ns_debit"] == 0

    def test_penyesuaian_hanya_jurnal_pa(self, mock_db):
        """Kolom penyesuaian hanya berisi mutasi jurnal PA-."""
        df = buat_neraca_lajur(1)
        # Beban Penyusutan di penyesuaian harus 1jt (dari PA-PENYUSUTAN-3-1)
        baris = df[df["kode_akun"] == "5106"]
        assert not baris.empty
        assert baris.iloc[0]["peny_debit"] == 1000000

    def test_nsd_adalah_ns_ditambah_penyesuaian(self, mock_db):
        """NSD = NS + Penyesuaian per akun."""
        df = buat_neraca_lajur(1)
        # Kas: NS debit = 500jt + 10jt = 510jt; Penyesuaian = 0; NSD = 510jt
        baris_kas = df[df["kode_akun"] == "1101"]
        assert not baris_kas.empty
        kas = baris_kas.iloc[0]
        assert kas["nsd_debit"] == kas["ns_debit"] + kas["peny_debit"] - kas["ns_kredit"] - kas["peny_kredit"] or \
               kas["nsd_debit"] == kas["ns_debit"]  # sederhana: tidak ada penyesuaian kas

    def test_pendapatan_masuk_kolom_lr(self, mock_db):
        """Akun Pendapatan harus masuk kolom lr_kredit."""
        df = buat_neraca_lajur(1)
        baris = df[df["kode_akun"] == "4101"]
        assert not baris.empty
        # Penjualan 10jt → lr_kredit = 10jt
        assert baris.iloc[0]["lr_kredit"] == 10000000
        assert baris.iloc[0]["neraca_kredit"] == 0

    def test_beban_masuk_kolom_lr(self, mock_db):
        """Akun Beban harus masuk kolom lr_debit."""
        df = buat_neraca_lajur(1)
        baris = df[df["kode_akun"] == "5106"]
        assert not baris.empty
        # Beban Penyusutan 1jt → lr_debit = 1jt
        assert baris.iloc[0]["lr_debit"] == 1000000
        assert baris.iloc[0]["neraca_debit"] == 0

    def test_aset_masuk_kolom_neraca(self, mock_db):
        """Akun Aset harus masuk kolom neraca_debit."""
        df = buat_neraca_lajur(1)
        baris_kas = df[df["kode_akun"] == "1101"]
        assert not baris_kas.empty
        assert baris_kas.iloc[0]["neraca_debit"] > 0
        assert baris_kas.iloc[0]["lr_debit"] == 0

    def test_ekuitas_masuk_kolom_neraca(self, mock_db):
        """Akun Ekuitas harus masuk kolom neraca_kredit."""
        df = buat_neraca_lajur(1)
        baris = df[df["kode_akun"] == "3101"]
        assert not baris.empty
        assert baris.iloc[0]["neraca_kredit"] > 0
        assert baris.iloc[0]["lr_kredit"] == 0

    def test_hitung_laba_rugi_positif(self, mock_db):
        """Laba bersih = total kredit L/R - total debit L/R."""
        df = buat_neraca_lajur(1)
        laba = hitung_laba_rugi_dari_lajur(df)
        # Pendapatan 10jt - Beban Penyusutan 1jt = Laba 9jt
        assert laba == 9000000

    def test_validasi_neraca_lajur(self, mock_db):
        """Validasi keseimbangan harus mengembalikan dict yang benar."""
        df = buat_neraca_lajur(1)
        validasi = validasi_neraca_lajur(df)
        assert "ns_seimbang" in validasi
        assert "nsd_seimbang" in validasi
        assert "laba_bersih" in validasi
        assert validasi["laba_bersih"] == 9000000

    def test_laba_rugi_df_kosong(self):
        """DataFrame kosong → laba 0."""
        import pandas as pd
        df_kosong = pd.DataFrame()
        laba = hitung_laba_rugi_dari_lajur(df_kosong)
        assert laba == 0


# ---------------------------------------------------------------------------
# Tests: Laporan Keuangan (statements_service)
# ---------------------------------------------------------------------------

class TestLaporanKeuangan:
    """Test fungsi susun_laporan_laba_rugi(), perubahan ekuitas, neraca."""

    def test_laba_rugi_mengembalikan_struktur_benar(self, mock_db):
        """susun_laporan_laba_rugi() harus mengembalikan dict dengan key yang benar."""
        data = susun_laporan_laba_rugi(1)
        key_wajib = [
            "pendapatan", "beban_produksi", "beban_operasional",
            "total_pendapatan", "total_beban", "laba_bersih"
        ]
        for k in key_wajib:
            assert k in data, f"Key '{k}' tidak ada di hasil laba rugi"

    def test_laba_rugi_total_pendapatan(self, mock_db):
        """Total pendapatan harus sesuai dengan transaksi yang diinput."""
        data = susun_laporan_laba_rugi(1)
        # Penjualan 10jt
        assert data["total_pendapatan"] == 10000000

    def test_laba_rugi_total_beban(self, mock_db):
        """Total beban harus sesuai dengan jurnal penyesuaian."""
        data = susun_laporan_laba_rugi(1)
        # Hanya ada Beban Penyusutan 1jt dari PA-
        assert data["total_beban"] == 1000000

    def test_laba_bersih_benar(self, mock_db):
        """Laba Bersih = Pendapatan - Beban."""
        data = susun_laporan_laba_rugi(1)
        # 10jt - 1jt = 9jt
        assert data["laba_bersih"] == 9000000

    def test_laba_rugi_periode_kosong(self, mock_db):
        """Periode yang tidak ada datanya harus mengembalikan laba 0."""
        # period_id=999 tidak ada
        data = susun_laporan_laba_rugi(999)
        assert data["laba_bersih"] == 0

    def test_perubahan_ekuitas_modal_awal(self, mock_db):
        """Modal awal harus diambil dari opening_balances."""
        data = susun_laporan_perubahan_ekuitas(1, laba_bersih=9000000)
        # Modal Disetor 500jt dari opening_balances
        assert data["modal_disetor_awal"] == 500000000

    def test_perubahan_ekuitas_modal_akhir(self, mock_db):
        """Modal akhir = Modal Awal + Laba Bersih."""
        laba = 9000000
        data = susun_laporan_perubahan_ekuitas(1, laba_bersih=laba)
        # Modal awal 500jt + laba 9jt = 509jt
        assert data["modal_akhir"] == 500000000 + laba

    def test_neraca_menghasilkan_dict_lengkap(self, mock_db):
        """susun_neraca() harus mengembalikan dict dengan semua key."""
        modal_akhir = 509000000
        data = susun_neraca(1, modal_akhir)
        key_wajib = [
            "aset_lancar", "aset_tetap", "total_aset",
            "liabilitas_lancar", "total_liabilitas",
            "ekuitas", "total_ekuitas", "seimbang"
        ]
        for k in key_wajib:
            assert k in data, f"Key '{k}' tidak ada di neraca"

    def test_neraca_total_ekuitas_sama_dengan_modal_akhir(self, mock_db):
        """Total Ekuitas harus sama dengan modal_akhir yang diberikan."""
        modal_akhir = 509000000
        data = susun_neraca(1, modal_akhir)
        assert data["total_ekuitas"] == modal_akhir

    def test_neraca_aset_lancar_terisi(self, mock_db):
        """Aset lancar harus berisi Kas."""
        modal_akhir = 509000000
        data = susun_neraca(1, modal_akhir)
        kode_aset_lancar = [item["kode"] for item in data["aset_lancar"]]
        assert "1101" in kode_aset_lancar, "Kas harus muncul di aset lancar"


# ---------------------------------------------------------------------------
# Tests: Jurnal Penutup (closing_service)
# ---------------------------------------------------------------------------

class TestJurnalPenutup:
    """Test fungsi jurnal penutup dan penutupan periode."""

    def test_preview_jurnal_penutup_menghasilkan_list(self, mock_db):
        """preview_jurnal_penutup() harus menghasilkan list of dict."""
        rencana = preview_jurnal_penutup(1, "2026-10-31")
        assert isinstance(rencana, list)
        assert len(rencana) > 0

    def test_preview_terdiri_dari_3_jurnal(self, mock_db):
        """Harus ada 3 jurnal penutup: tutup pendapatan, tutup beban, pindah laba."""
        rencana = preview_jurnal_penutup(1, "2026-10-31")
        assert len(rencana) == 3, f"Harus 3 jurnal, dapat {len(rencana)}"

    def test_preview_jurnal_1_tutup_pendapatan(self, mock_db):
        """Jurnal pertama: Dr Pendapatan | Cr Ikhtisar L/R."""
        rencana = preview_jurnal_penutup(1, "2026-10-31")
        j1 = rencana[0]
        assert "JP-1-1" in j1["no_bukti"]
        # Cek ada debit di akun pendapatan dan kredit di Ikhtisar L/R
        lines = j1["lines"]
        kode_debit = [l["akun"] for l in lines if l["debit"] > 0]
        kode_kredit = [l["akun"] for l in lines if l["kredit"] > 0]
        assert "4101" in kode_debit  # Penjualan di-debit
        assert "3301" in kode_kredit  # Ikhtisar L/R di-kredit

    def test_preview_jurnal_2_tutup_beban(self, mock_db):
        """Jurnal kedua: Dr Ikhtisar L/R | Cr Beban."""
        rencana = preview_jurnal_penutup(1, "2026-10-31")
        j2 = rencana[1]
        assert "JP-1-2" in j2["no_bukti"]
        lines = j2["lines"]
        kode_debit = [l["akun"] for l in lines if l["debit"] > 0]
        kode_kredit = [l["akun"] for l in lines if l["kredit"] > 0]
        assert "3301" in kode_debit  # Ikhtisar L/R di-debit
        assert "5106" in kode_kredit  # Beban Penyusutan di-kredit

    def test_preview_jurnal_3_pindah_laba(self, mock_db):
        """Jurnal ketiga: Dr Ikhtisar L/R | Cr Laba Ditahan (saat laba)."""
        rencana = preview_jurnal_penutup(1, "2026-10-31")
        j3 = rencana[2]
        assert "JP-1-3" in j3["no_bukti"]
        lines = j3["lines"]
        kode_debit = [l["akun"] for l in lines if l["debit"] > 0]
        kode_kredit = [l["akun"] for l in lines if l["kredit"] > 0]
        assert "3301" in kode_debit  # Ikhtisar L/R di-debit (tutup)
        assert "3201" in kode_kredit  # Laba Ditahan di-kredit

    def test_jurnal_penutup_seimbang(self, mock_db):
        """Setiap jurnal penutup harus seimbang (debit == kredit)."""
        rencana = preview_jurnal_penutup(1, "2026-10-31")
        for jurnal in rencana:
            total_d = sum(l["debit"] for l in jurnal["lines"])
            total_k = sum(l["kredit"] for l in jurnal["lines"])
            assert total_d == total_k, (
                f"Jurnal {jurnal['no_bukti']} tidak seimbang: "
                f"D={total_d}, K={total_k}"
            )

    def test_buat_jurnal_penutup_menyimpan_ke_db(self, mock_db):
        """buat_jurnal_penutup() harus menyimpan 3 jurnal ke database."""
        id_list = buat_jurnal_penutup(1, "2026-10-31")
        assert len(id_list) == 3
        assert all(isinstance(i, int) for i in id_list)

    def test_jurnal_penutup_tercatat_di_db(self, mock_db, db_path):
        """Jurnal JP- harus ada di tabel journal_entries setelah disimpan."""
        buat_jurnal_penutup(1, "2026-10-31")
        koneksi = sqlite3.connect(str(db_path))
        koneksi.row_factory = sqlite3.Row
        rows = koneksi.execute(
            "SELECT no_bukti FROM journal_entries WHERE no_bukti LIKE 'JP-%'"
        ).fetchall()
        koneksi.close()
        assert len(rows) == 3

    def test_cek_jurnal_penutup_sudah_ada(self, mock_db):
        """cek_jurnal_penutup_sudah_ada() mengembalikan True setelah disimpan."""
        assert not cek_jurnal_penutup_sudah_ada(1)
        buat_jurnal_penutup(1, "2026-10-31")
        assert cek_jurnal_penutup_sudah_ada(1)

    def test_buat_jurnal_penutup_duplikat_error(self, mock_db):
        """Membuat jurnal penutup dua kali harus memunculkan ValueError."""
        buat_jurnal_penutup(1, "2026-10-31")
        with pytest.raises(ValueError, match="sudah pernah dibuat"):
            buat_jurnal_penutup(1, "2026-10-31")

    def test_ns_setelah_penutup_hanya_akun_permanen(self, mock_db):
        """NS setelah penutup hanya boleh berisi akun permanen (Aset, Liab, Ekuitas)."""
        buat_jurnal_penutup(1, "2026-10-31")
        df = hitung_neraca_saldo_setelah_penutup(1)
        kategori_muncul = set(df["kategori"].unique())
        kategori_sementara = {"Pendapatan", "Beban Produksi", "Beban Operasional"}
        # Tidak boleh ada kategori sementara yang bersaldo non-nol
        overlap = kategori_muncul & kategori_sementara
        assert len(overlap) == 0, f"Kategori sementara muncul: {overlap}"

    def test_tutup_periode_mengubah_status(self, mock_db, db_path):
        """tutup_periode() harus mengubah status menjadi 'tutup'."""
        buat_jurnal_penutup(1, "2026-10-31")
        tutup_periode(1)
        koneksi = sqlite3.connect(str(db_path))
        koneksi.row_factory = sqlite3.Row
        row = koneksi.execute("SELECT status FROM periods WHERE id = 1").fetchone()
        koneksi.close()
        assert row["status"] == "tutup"

    def test_tutup_periode_tanpa_jurnal_penutup_error(self, mock_db):
        """tutup_periode() harus gagal jika jurnal penutup belum dibuat."""
        with pytest.raises(ValueError, match="belum dibuat"):
            tutup_periode(1)

    def test_buat_jurnal_penutup_periode_tutup_error(self, mock_db, db_path):
        """Membuat jurnal penutup di periode yang sudah tutup harus error."""
        # Tutup periode langsung via SQL
        koneksi = sqlite3.connect(str(db_path))
        koneksi.execute("UPDATE periods SET status = 'tutup' WHERE id = 1")
        koneksi.commit()
        koneksi.close()

        with pytest.raises(ValueError, match="sudah ditutup"):
            buat_jurnal_penutup(1, "2026-10-31")
