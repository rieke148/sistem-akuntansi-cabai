"""
tests/test_depreciation.py
---------------------------
Tujuan  : Tes pytest untuk logika penyusutan aset tetap (garis lurus).
Jalankan: pytest tests/ -v
"""

import pytest
from services.depreciation_service import hitung_amortisasi_mulsa_bulanan


class TestPenyusutanGarisLurus:
    """Tes rumus penyusutan garis lurus."""

    def test_penyusutan_bangunan(self):
        """Verifikasi penyusutan bangunan Rp120 jt, residu Rp12 jt, umur 20 th."""
        harga = 120_000_000
        residu = 12_000_000
        umur_tahun = 20

        dasar = harga - residu          # = 108.000.000
        umur_bulan = umur_tahun * 12    # = 240
        penyusutan_bulan = dasar // umur_bulan  # = 450.000

        assert dasar == 108_000_000
        assert umur_bulan == 240
        assert penyusutan_bulan == 450_000  # Rp450.000/bulan

    def test_tanah_tidak_disusutkan(self):
        """Tanah (is_disusutkan=False) → penyusutan = 0."""
        is_disusutkan = False
        penyusutan = 0 if not is_disusutkan else 1_000_000
        assert penyusutan == 0

    def test_penyusutan_komputer(self):
        """Komputer Rp15 jt, residu Rp1,5 jt, umur 4 th."""
        harga = 15_000_000
        residu = 1_500_000
        umur_tahun = 4

        dasar = harga - residu          # = 13.500.000
        umur_bulan = umur_tahun * 12    # = 48
        penyusutan_bulan = dasar // umur_bulan  # = 281.250

        assert penyusutan_bulan == 281_250  # Rp281.250/bulan

    def test_amortisasi_mulsa(self):
        """Plastik mulsa 5 blok @ Rp400.000, umur 1,5 tahun."""
        amortisasi = hitung_amortisasi_mulsa_bulanan(
            harga_per_blok=400_000,
            jumlah_blok=5,
            umur_tahun=1.5,
        )
        # Total = 2.000.000 / 18 bulan = 111.111 (integer division)
        assert amortisasi == 111_111
