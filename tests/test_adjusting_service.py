"""Regression tests for adjustment types supported by the application."""

from services import adjusting_service


def test_amortisasi_mulsa_tidak_lagi_didukung():
    """Mulsa tidak lagi memiliki workflow jurnal amortisasi."""
    assert not hasattr(adjusting_service, "buat_penyesuaian_amortisasi_mulsa")
    assert adjusting_service.cek_penyesuaian_sudah_ada(1, "mulsa") is False
