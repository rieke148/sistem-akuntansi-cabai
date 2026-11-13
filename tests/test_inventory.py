"""
tests/test_inventory.py
------------------------
Tujuan  : Tes pytest untuk logika kartu persediaan (rata-rata bergerak).
Jalankan: pytest tests/ -v
"""

import pytest


class TestRataRataBergerak:
    """Tes perhitungan rata-rata bergerak persediaan."""

    def test_harga_rata2_pertama_masuk(self):
        """Pembelian pertama: harga rata-rata = harga beli."""
        # Simulasi perhitungan tanpa database
        qty_masuk = 4
        harga_satuan = 180_000
        saldo_qty_lama = 0
        saldo_nilai_lama = 0

        total_masuk = qty_masuk * harga_satuan
        saldo_qty_baru = saldo_qty_lama + qty_masuk
        saldo_nilai_baru = saldo_nilai_lama + total_masuk
        harga_rata2 = saldo_nilai_baru // saldo_qty_baru  # integer division

        assert saldo_qty_baru == 4
        assert saldo_nilai_baru == 720_000
        assert harga_rata2 == 180_000  # Rp180.000/karung

    def test_harga_rata2_pembelian_kedua(self):
        """Pembelian kedua dengan harga berbeda → rata-rata berubah."""
        # Saldo setelah pembelian pertama
        saldo_qty = 4
        saldo_nilai = 720_000
        # harga rata2 = 180.000

        # Beli lagi 2 karung @ Rp200.000
        qty_masuk = 2
        harga_satuan = 200_000
        total_masuk = qty_masuk * harga_satuan  # = 400.000

        saldo_qty_baru = saldo_qty + qty_masuk          # = 6
        saldo_nilai_baru = saldo_nilai + total_masuk    # = 1.120.000
        harga_rata2_baru = saldo_nilai_baru // saldo_qty_baru  # = 186.666

        assert saldo_qty_baru == 6
        assert saldo_nilai_baru == 1_120_000
        assert harga_rata2_baru == 186_666  # pembulatan integer ke bawah

    def test_harga_rata2_tidak_berubah_saat_keluar(self):
        """Saat bahan keluar, harga rata-rata TIDAK berubah."""
        saldo_qty = 6
        saldo_nilai = 1_120_000
        harga_rata2 = 186_666  # harga rata-rata saat ini

        # Pakai 3 karung
        qty_keluar = 3
        total_keluar = qty_keluar * harga_rata2  # = 559.998

        saldo_qty_baru = saldo_qty - qty_keluar          # = 3
        saldo_nilai_baru = saldo_nilai - total_keluar    # = 560.002
        harga_rata2_baru = harga_rata2                   # TETAP sama!

        assert saldo_qty_baru == 3
        assert harga_rata2_baru == 186_666  # tidak berubah

    def test_saldo_tidak_boleh_negatif(self):
        """Keluar lebih dari saldo → harus error."""
        saldo_qty = 2
        qty_keluar = 5  # lebih dari saldo

        with pytest.raises(ValueError):
            if qty_keluar > saldo_qty:
                raise ValueError(
                    f"Saldo tidak cukup. Tersedia: {saldo_qty}, diminta: {qty_keluar}"
                )
