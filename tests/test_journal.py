"""
tests/test_journal.py
---------------------
Tujuan  : Tes pytest untuk memastikan logika jurnal benar.
          Tes utama: jurnal wajib seimbang (Debit == Kredit).
Jalankan: pytest tests/ -v
"""

import pytest
from services.journal_service import validasi_jurnal_seimbang


class TestJurnalSeimbang:
    """Tes validasi jurnal seimbang."""

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
            {"debit": 0, "kredit": 500_000},  # kurang Rp500.000
        ]
        with pytest.raises(ValueError, match="tidak seimbang"):
            validasi_jurnal_seimbang(baris)

    def test_jurnal_tiga_baris_seimbang(self):
        """Jurnal dengan lebih dari 2 baris — total harus tetap sama."""
        baris = [
            {"debit": 5_000_000, "kredit": 0},   # Kas
            {"debit": 0, "kredit": 3_000_000},   # Penjualan Cabai
            {"debit": 0, "kredit": 2_000_000},   # Penjualan Selada
        ]
        total_d, total_k = validasi_jurnal_seimbang(baris)
        assert total_d == total_k == 5_000_000

    def test_jurnal_kosong_seimbang(self):
        """Jurnal kosong (tidak ada baris) dianggap seimbang (0 == 0)."""
        total_d, total_k = validasi_jurnal_seimbang([])
        assert total_d == total_k == 0
