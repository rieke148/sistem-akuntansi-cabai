"""
tests/test_export.py
--------------------
Pengujian untuk utilitas export Excel dan PDF serta fungsi backup.
"""

import pytest
import pandas as pd
from utils.export import (
    export_dataframe_ke_excel,
    export_dataframe_ke_pdf,
    _bersihkan_teks_pdf,
)


def test_bersihkan_teks_pdf():
    """Memastikan karakter unicode berbahaya diganti dengan representasi latin-1 yang aman."""
    teks = "Neraca Saldo — Oktober 2026 • “Laporan” ✓"
    bersih = _bersihkan_teks_pdf(teks)
    assert "—" not in bersih
    assert "-" in bersih
    assert "•" not in bersih
    assert "*" in bersih
    assert "“" not in bersih
    assert '"' in bersih
    # Harus bisa di-encode ke latin-1 tanpa error
    bersih.encode("latin-1")


def test_export_dataframe_ke_excel():
    """Memastikan export dataframe ke bytes Excel (.xlsx) berhasil dan valid."""
    df = pd.DataFrame({
        "Kode Akun": ["1101", "4101"],
        "Nama Akun": ["Kas Tunai", "Penjualan Cabai Rawit"],
        "Debit": [1000000, 0],
        "Kredit": [0, 1000000],
    })
    excel_bytes = export_dataframe_ke_excel(
        df,
        nama_sheet="Neraca Saldo",
        judul="Neraca Saldo — Oktober 2026",
        kolom_rupiah=["Debit", "Kredit"],
    )
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0
    # Cek signature zip/xlsx (PK\x03\x04)
    assert excel_bytes[:2] == b"PK"


def test_export_dataframe_ke_pdf_dengan_unicode():
    """Memastikan export PDF tidak crash saat judul atau isi mengandung em-dash dan unicode."""
    df = pd.DataFrame({
        "Kode Akun": ["1101", "4101"],
        "Nama Akun": ["Kas — Tunai", "Penjualan Cabai “Super”"],
        "Debit": ["Rp1.000.000", "Rp0"],
        "Kredit": ["Rp0", "Rp1.000.000"],
    })
    pdf_bytes = export_dataframe_ke_pdf(
        df,
        judul_laporan="Neraca Saldo — Oktober 2026",
        kolom_rupiah=["Debit", "Kredit"],
        lebar_kolom=[30, 80, 40, 40],
    )
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    # Cek signature PDF (%PDF-)
    assert pdf_bytes[:5] == b"%PDF-"


def test_export_dataframe_ke_pdf_kosong():
    """Memastikan export PDF dataframe kosong tetap menghasilkan file PDF yang valid."""
    df = pd.DataFrame(columns=["Kode", "Nama", "Debit", "Kredit"])
    pdf_bytes = export_dataframe_ke_pdf(
        df,
        judul_laporan="Laporan Kosong",
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:5] == b"%PDF-"
