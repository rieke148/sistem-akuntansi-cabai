"""
tests/test_e2e_accounting_cycle.py
-----------------------------------
Tujuan  : Uji End-to-End (E2E) siklus akuntansi penuh untuk Fase 8.
          Memvalidasi seluruh alur akuntansi dari inisialisasi schema,
          transaksi, mutasi stok, buku besar, neraca saldo, ayat penyesuaian,
          neraca lajur, laporan keuangan (Laba Rugi, Perubahan Ekuitas, Neraca seimbang),
          jurnal penutup, hingga ekspor dokumen (Excel & PDF).
Input   : Database sementara (tmp_path) terisolasi.
Output  : Pengujian siklus akuntansi 100% lulus.
Dipanggil oleh : pytest tests/ -v
"""

import sqlite3
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch

from database.schema import buat_semua_tabel
from database.seed import jalankan_seed
from services.trial_balance_service import hitung_neraca_saldo, validasi_neraca_saldo_seimbang
from services.adjusting_service import ambil_ringkasan_penyesuaian
from services.worksheet_service import buat_neraca_lajur, validasi_neraca_lajur
from services.statements_service import (
    susun_laporan_laba_rugi,
    susun_laporan_perubahan_ekuitas,
    susun_neraca,
    susun_arus_kas,
)
from services.closing_service import (
    preview_jurnal_penutup,
    buat_jurnal_penutup,
    hitung_neraca_saldo_setelah_penutup,
    tutup_periode,
)
from services.inventory_service import ambil_kartu_persediaan, ambil_saldo_persediaan
from services.ledger_service import ambil_buku_besar
from services.subsidiary_service import ambil_bb_piutang
from utils.export import export_dataframe_ke_excel, export_dataframe_ke_pdf


@pytest.fixture
def e2e_db(tmp_path):
    """Fixture membuat database bersih dengan schema dan data seed Oktober 2026."""
    db_file = tmp_path / "test_e2e_akuntansi.db"

    def get_conn():
        c = sqlite3.connect(str(db_file))
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON;")
        return c

    with patch("database.connection.get_connection", side_effect=get_conn), \
         patch("database.schema.get_connection", side_effect=get_conn), \
         patch("database.seed.get_connection", side_effect=get_conn), \
         patch("services.trial_balance_service.get_connection", side_effect=get_conn), \
         patch("services.adjusting_service.get_connection", side_effect=get_conn), \
         patch("services.worksheet_service.get_connection", side_effect=get_conn), \
         patch("services.statements_service.get_connection", side_effect=get_conn), \
         patch("services.closing_service.get_connection", side_effect=get_conn), \
         patch("services.inventory_service.get_connection", side_effect=get_conn), \
         patch("services.ledger_service.get_connection", side_effect=get_conn), \
         patch("services.subsidiary_service.get_connection", side_effect=get_conn), \
         patch("services.journal_service.get_connection", side_effect=get_conn), \
         patch("services.master_data_service.get_connection", side_effect=get_conn):

        # Inisialisasi tabel dan seed data
        buat_semua_tabel()
        jalankan_seed()
        yield get_conn


def test_e2e_persediaan_dan_buku_besar(e2e_db):
    """Verifikasi bahwa kartu persediaan dan buku besar terisi dengan data seed."""
    conn_func = e2e_db
    with patch("services.inventory_service.get_connection", side_effect=conn_func), \
         patch("services.ledger_service.get_connection", side_effect=conn_func):
        
        conn = conn_func()
        # Cari item yang memiliki pergerakan di tabel inventory_movements
        row = conn.execute("SELECT item_id FROM inventory_movements LIMIT 1").fetchone()
        assert row is not None, "Seed data harus memiliki inventory movements"
        item_id = row["item_id"]

        kartu = ambil_kartu_persediaan(item_id)
        assert len(kartu) > 0, "Kartu persediaan harus memiliki riwayat gerakan"
        
        saldo = ambil_saldo_persediaan(item_id)
        assert "saldo_qty" in saldo and "saldo_nilai" in saldo

        # Cek buku besar kas (kode 1101)
        akun_kas = conn.execute("SELECT id FROM accounts WHERE kode_akun = '1101'").fetchone()
        assert akun_kas is not None
        bb_kas = ambil_buku_besar(akun_kas["id"], period_id=1)
        assert len(bb_kas) > 0, "Buku besar Kas harus memiliki mutasi"


def test_e2e_neraca_saldo_sebelum_penyesuaian(e2e_db):
    """Verifikasi Neraca Saldo sebelum penyesuaian seimbang (Debit == Kredit)."""
    conn_func = e2e_db
    with patch("services.trial_balance_service.get_connection", side_effect=conn_func):
        df_ns = hitung_neraca_saldo(period_id=1, termasuk_penyesuaian=False)
        seimbang, debit, kredit = validasi_neraca_saldo_seimbang(df_ns)
        assert seimbang is True, f"Neraca saldo sebelum penyesuaian harus seimbang! Debit={debit:,} vs Kredit={kredit:,}"
        assert debit == kredit
        assert debit > 0


def test_e2e_neraca_lajur_dan_laporan_keuangan(e2e_db):
    """Verifikasi Neraca Lajur 10 Kolom dan seluruh laporan keuangan utama."""
    conn_func = e2e_db
    with patch("services.worksheet_service.get_connection", side_effect=conn_func), \
         patch("services.statements_service.get_connection", side_effect=conn_func), \
         patch("services.trial_balance_service.get_connection", side_effect=conn_func):

        # 1. Neraca Lajur
        lajur = buat_neraca_lajur(period_id=1)
        validasi = validasi_neraca_lajur(lajur)
        assert validasi["ns_seimbang"] is True, "Neraca saldo di lajur harus seimbang!"
        assert validasi["nsd_seimbang"] is True, "Neraca saldo disesuaikan di lajur harus seimbang!"
        assert validasi["neraca_seimbang_setelah_laba"] is True, "Neraca lajur harus seimbang setelah laba!"

        # 2. Laporan Laba Rugi
        lr = susun_laporan_laba_rugi(period_id=1)
        assert "laba_bersih" in lr
        assert lr["total_pendapatan"] >= 0

        # 3. Laporan Perubahan Ekuitas
        pe = susun_laporan_perubahan_ekuitas(period_id=1, laba_bersih=lr["laba_bersih"])
        assert pe["modal_akhir"] == pe["modal_awal"] + pe["tambahan_setoran"] + pe["laba_bersih"]

        # 4. Neraca (Aset = Liabilitas + Ekuitas)
        neraca = susun_neraca(period_id=1, modal_akhir=pe["modal_akhir"])
        assert neraca["seimbang"] is True, (
            f"Neraca tidak seimbang! Aset: {neraca['total_aset']:,} vs "
            f"Liab+Ekuitas: {neraca['total_liabilitas_ekuitas']:,} "
            f"(Selisih: {neraca['selisih']:,})"
        )

        # 5. Laporan Arus Kas
        arus_kas = susun_arus_kas(period_id=1)
        assert "saldo_kas_akhir" in arus_kas


def test_e2e_penutupan_periode_dan_neraca_saldo_penutup(e2e_db):
    """Verifikasi proses penutupan periode (Fase 6 & Fase 8)."""
    conn_func = e2e_db
    with patch("services.closing_service.get_connection", side_effect=conn_func), \
         patch("services.statements_service.get_connection", side_effect=conn_func), \
         patch("services.worksheet_service.get_connection", side_effect=conn_func), \
         patch("services.trial_balance_service.get_connection", side_effect=conn_func):

        # Preview jurnal penutup
        preview = preview_jurnal_penutup(period_id=1, tanggal="2026-10-31")
        assert len(preview) > 0, "Harus ada entri penutup"

        # Buat jurnal penutup
        id_list = buat_jurnal_penutup(period_id=1, tanggal="2026-10-31")
        assert len(id_list) > 0

        # Tutup periode
        tutup_periode(period_id=1)

        # Neraca Saldo Setelah Penutup: akun nominal tidak ada di akun permanen
        df_ns_tutup = hitung_neraca_saldo_setelah_penutup(period_id=1)
        assert not df_ns_tutup.empty
        for _, baris in df_ns_tutup.iterrows():
            kode = str(baris["kode_akun"])
            assert not kode.startswith(("4", "5", "6")), (
                f"Akun nominal {kode} tidak boleh muncul di neraca saldo setelah penutupan!"
            )


def test_e2e_export_excel_dan_pdf(e2e_db):
    """Verifikasi export dokumen Excel dan PDF berfungsi tanpa error."""
    conn_func = e2e_db
    with patch("services.trial_balance_service.get_connection", side_effect=conn_func), \
         patch("services.master_data_service.get_connection", side_effect=conn_func):

        df_ns = hitung_neraca_saldo(period_id=1)

        # Export Excel
        excel_bytes = export_dataframe_ke_excel(df_ns, nama_sheet="Neraca Saldo", judul="Neraca Saldo Okt 2026")
        assert isinstance(excel_bytes, bytes)
        assert len(excel_bytes) > 500
        assert excel_bytes[:2] == b"PK"

        # Export PDF
        pdf_bytes = export_dataframe_ke_pdf(df_ns, judul_laporan="Neraca Saldo Okt 2026")
        assert isinstance(pdf_bytes, (bytes, bytearray))
        assert len(pdf_bytes) > 500
