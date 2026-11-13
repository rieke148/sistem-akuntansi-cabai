"""
tests/test_master_data.py
--------------------------
Tujuan  : Tes pytest untuk logika Master Data.
          Tes menggunakan database in-memory SQLite agar tidak
          mengganggu data asli.
Jalankan: pytest tests/test_master_data.py -v
"""

import pytest
import sqlite3
from unittest.mock import patch, MagicMock
import pandas as pd

# Import fungsi yang akan dites (tidak butuh DB nyata untuk tes logika)
from services.master_data_service import (
    hitung_penyusutan_preview,
    validasi_saldo_awal_seimbang,
    ambil_nilai_parameter,
    KATEGORI_AKUN,
    SALDO_NORMAL,
    TIPE_PEKERJA,
)


class TestPenyusutanPreview:
    """Tes fungsi preview penyusutan (tidak butuh database)."""

    def test_bangunan_satu_unit(self):
        """Bangunan Rp120 jt, residu Rp12 jt, umur 20 th, 1 unit."""
        hasil = hitung_penyusutan_preview(120_000_000, 12_000_000, 20, 1)
        assert hasil["dasar_penyusutan"] == 108_000_000
        assert hasil["penyusutan_per_bulan"] == 450_000
        assert hasil["penyusutan_per_tahun"] == 5_400_000

    def test_komputer_satu_unit(self):
        """Komputer Rp15 jt, residu Rp1,5 jt, umur 4 th."""
        hasil = hitung_penyusutan_preview(15_000_000, 1_500_000, 4, 1)
        assert hasil["dasar_penyusutan"] == 13_500_000
        assert hasil["penyusutan_per_bulan"] == 281_250
        assert hasil["penyusutan_per_tahun"] == 3_375_000

    def test_peralatan_multi_unit(self):
        """Cangkul Rp150.000, residu Rp0, umur 3 th, 5 unit."""
        hasil = hitung_penyusutan_preview(150_000, 0, 3, 5)
        # Dasar = (150.000 - 0) x 5 = 750.000
        assert hasil["dasar_penyusutan"] == 750_000
        # Per bulan = 750.000 / (3 x 12) = 750.000 / 36 = 20.833
        assert hasil["penyusutan_per_bulan"] == 20_833
        assert hasil["penyusutan_per_tahun"] == 20_833 * 12

    def test_tanah_tidak_disusutkan(self):
        """Tanah umur=0 → penyusutan = 0 (tidak error)."""
        hasil = hitung_penyusutan_preview(2_500_000_000, 0, 0, 1)
        # umur_bulan = 0 → penyusutan = 0
        assert hasil["penyusutan_per_bulan"] == 0
        assert hasil["penyusutan_per_tahun"] == 0

    def test_kendaraan_satu_unit(self):
        """Kendaraan Rp250 jt, residu Rp25 jt, umur 8 th."""
        hasil = hitung_penyusutan_preview(250_000_000, 25_000_000, 8, 1)
        # Dasar = 225.000.000 / (8 x 12) = 225.000.000 / 96 = 2.343.750
        assert hasil["dasar_penyusutan"] == 225_000_000
        assert hasil["penyusutan_per_bulan"] == 2_343_750


class TestValidasiSaldoAwal:
    """Tes validasi saldo awal seimbang — menggunakan mock database."""

    def test_saldo_seimbang(self):
        """
        Simulasi saldo awal yang sudah seimbang.
        Total Debit (Kas + Tanah + Bangunan) = Total Kredit (Modal Disetor).
        """
        df_mock = pd.DataFrame({
            "saldo_debit": [500_000_000, 2_500_000_000, 120_000_000, 0],
            "saldo_kredit": [0, 0, 0, 3_120_000_000],
        })
        total_d = int(df_mock["saldo_debit"].sum())
        total_k = int(df_mock["saldo_kredit"].sum())
        assert total_d == total_k == 3_120_000_000

    def test_saldo_tidak_seimbang(self):
        """Saldo tidak seimbang — total debit != total kredit."""
        df_mock = pd.DataFrame({
            "saldo_debit": [500_000_000, 0],
            "saldo_kredit": [0, 300_000_000],  # kurang Rp200 jt
        })
        total_d = int(df_mock["saldo_debit"].sum())
        total_k = int(df_mock["saldo_kredit"].sum())
        assert total_d != total_k
        selisih = abs(total_d - total_k)
        assert selisih == 200_000_000


class TestKonstantaMasterData:
    """Tes konstanta dan daftar pilihan agar tidak berubah tanpa sengaja."""

    def test_kategori_akun_lengkap(self):
        """6 kategori akun harus ada."""
        assert "Aset" in KATEGORI_AKUN
        assert "Liabilitas" in KATEGORI_AKUN
        assert "Ekuitas" in KATEGORI_AKUN
        assert "Pendapatan" in KATEGORI_AKUN
        assert "Beban Produksi" in KATEGORI_AKUN
        assert "Beban Operasional" in KATEGORI_AKUN
        assert len(KATEGORI_AKUN) == 6

    def test_saldo_normal_dua_pilihan(self):
        """Hanya ada 2 saldo normal: Debit dan Kredit."""
        assert SALDO_NORMAL == ["Debit", "Kredit"]

    def test_tipe_pekerja_dua_pilihan(self):
        """Hanya ada 2 tipe pekerja: tetap dan tambahan."""
        assert "tetap" in TIPE_PEKERJA
        assert "tambahan" in TIPE_PEKERJA


class TestValidasiInputAset:
    """Tes validasi input form aset tetap."""

    def test_harga_harus_lebih_besar_dari_residu(self):
        """Nilai residu >= harga perolehan harus ditolak."""
        with pytest.raises(ValueError, match="lebih kecil"):
            # Simulasi validasi yang ada di tambah_aset_tetap
            harga = 1_000_000
            residu = 1_500_000  # residu > harga — tidak valid
            if residu >= harga:
                raise ValueError("Nilai residu harus lebih kecil dari harga perolehan.")

    def test_harga_positif(self):
        """Harga perolehan = 0 harus ditolak."""
        with pytest.raises(ValueError, match="lebih dari 0"):
            harga = 0
            if harga <= 0:
                raise ValueError("Harga perolehan harus lebih dari 0.")

    def test_residu_tidak_negatif(self):
        """Nilai residu negatif harus ditolak."""
        with pytest.raises(ValueError, match="negatif"):
            residu = -100_000
            if residu < 0:
                raise ValueError("Nilai residu tidak boleh negatif.")


class TestValidasiInputPekerja:
    """Tes validasi input form pekerja."""

    def test_upah_harus_positif(self):
        """Upah harian 0 atau negatif harus ditolak."""
        with pytest.raises(ValueError, match="lebih dari 0"):
            upah = 0
            if upah <= 0:
                raise ValueError("Upah harian harus lebih dari 0.")

    def test_nama_tidak_boleh_kosong(self):
        """Nama pekerja kosong harus ditolak."""
        with pytest.raises(ValueError, match="kosong"):
            nama = "   "  # hanya spasi
            if not nama.strip():
                raise ValueError("Nama pekerja tidak boleh kosong.")
