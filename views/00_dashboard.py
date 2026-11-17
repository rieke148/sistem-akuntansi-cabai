"""
views/00_dashboard.py
---------------------
Tujuan  : Dashboard eksekutif untuk memantau keuangan, penjualan,
          piutang, persediaan, aktivitas jurnal, dan tahapan akuntansi.
Input   : Data aktual dari services/dashboard_service.py.
Output  : Kartu KPI, grafik, tabel peringatan, dan progres siklus.
Dipanggil oleh : app.py melalui st.navigation.

Catatan:
  Dashboard tidak membuat angka contoh. Semua nilai dibaca dari service
  dan database aplikasi yang sudah berjalan.
"""

import pandas as pd
import streamlit as st

import services.dashboard_service as ds
from services.permission_service import wajib_punya_izin
from theme import WARNA_PRIMER, NAMA_PERUSAHAAN
from utils.formatting import format_rupiah, format_qty
from utils.ui_components import (
    divider_dengan_judul,
    render_alert,
    render_metric_card,
    render_page_header,
    render_steps_siklus,
    selector_periode,
)


def _tampilkan_kpi(period_id: int) -> None:
    """Menampilkan enam indikator utama berdasarkan periode terpilih."""
    kas = ds.ambil_saldo_kas_bank(period_id)
    piutang_terlambat = ds.ambil_piutang_overdue()
    ringkasan = ds.ambil_ringkasan_penjualan_beban(period_id)
    daftar_stok = ds.ambil_stok_persediaan()

    total_piutang = sum(int(item.get("sisa_piutang", 0) or 0) for item in piutang_terlambat)
    nilai_persediaan = sum(int(item.get("saldo_nilai", 0) or 0) for item in daftar_stok)
    qty_persediaan = sum(float(item.get("saldo_qty", 0) or 0) for item in daftar_stok)

    indikator = [
        (
            "Kas",
            format_rupiah(kas["total"]),
            "Saldo akun kas pada periode terpilih",
            None,
        ),
        (
            "Piutang lewat jatuh tempo",
            f"{len(piutang_terlambat)} faktur",
            format_rupiah(total_piutang),
            "inverse" if piutang_terlambat else "off",
        ),
        (
            "Penjualan cabai",
            format_rupiah(ringkasan["penjualan"]),
            "Kredit akun penjualan cabai pada periode ini",
            None,
        ),
        (
            "Laba kotor",
            format_rupiah(ringkasan["laba_kotor"]),
            "Penjualan dikurangi harga pokok penjualan",
            None,
        ),
        (
            "Nilai persediaan",
            format_rupiah(nilai_persediaan),
            "Nilai saldo terakhir kartu persediaan",
            None,
        ),
        (
            "Stok cabai",
            format_qty(qty_persediaan, "kg"),
            "Total kuantitas item hasil panen yang aktif",
            None,
        ),
    ]

    for awal in (0, 3):
        kolom = st.columns(3)
        for indeks, item in enumerate(indikator[awal:awal + 3]):
            label, nilai, keterangan, delta_color = item
            with kolom[indeks]:
                render_metric_card(
                    label,
                    nilai,
                    delta=keterangan,
                    delta_color=delta_color or "off",
                )


def _tampilkan_grafik_penjualan(period_id: int) -> None:
    """Menampilkan tren penjualan cabai per tanggal dari jurnal aktual."""
    df = ds.ambil_tren_penjualan_cabai(period_id)
    if df.empty:
        st.info("Belum ada penjualan cabai pada periode ini.")
        return

    data_grafik = df.copy()
    data_grafik["tanggal"] = pd.to_datetime(data_grafik["tanggal"])
    data_grafik = data_grafik.set_index("tanggal")["penjualan"]
    with st.container(border=True):
        st.area_chart(
            data_grafik,
            color=WARNA_PRIMER,
            use_container_width=True,
        )
    st.caption("Penjualan tunai dan tempo berdasarkan tanggal jurnal akun penjualan cabai.")


def _tampilkan_perbandingan_penjualan_beban(period_id: int) -> None:
    """Membandingkan penjualan, HPP, dan beban produksi lain."""
    ringkasan = ds.ambil_ringkasan_penjualan_beban(period_id)
    nilai = [
        int(ringkasan["penjualan"]),
        int(ringkasan["hpp_penjualan"]),
        int(ringkasan["beban_produksi_lain"]),
    ]
    if not any(nilai):
        st.info("Belum ada data penjualan atau beban untuk periode ini.")
        return

    df = pd.DataFrame(
        {
            "Kategori": ["Penjualan", "HPP Penjualan", "Beban Produksi Lain"],
            "Nominal": nilai,
        }
    ).set_index("Kategori")
    with st.container(border=True):
        st.bar_chart(df, color=WARNA_PRIMER, use_container_width=True)
    st.caption("Beban produksi lain disajikan terpisah dari HPP penjualan.")


def _tampilkan_ringkasan_jurnal(period_id: int) -> None:
    """Menampilkan jumlah transaksi untuk setiap jenis jurnal."""
    ringkasan = ds.ambil_ringkasan_jurnal(period_id)
    daftar = [
        ("Penjualan", ringkasan["penjualan"]),
        ("Pembelian", ringkasan["pembelian"]),
        ("Penerimaan kas", ringkasan["penerimaan_kas"]),
        ("Pengeluaran kas", ringkasan["pengeluaran_kas"]),
        ("Jurnal umum", ringkasan["umum"]),
    ]
    kolom = st.columns(5)
    for kol, (label, jumlah) in zip(kolom, daftar):
        with kol:
            render_metric_card(label, str(jumlah))
    st.caption(f"Total {ringkasan['total_transaksi']} transaksi, tidak termasuk penyesuaian dan penutup.")


def _tampilkan_piutang_jatuh_tempo() -> None:
    """Menampilkan faktur piutang yang melewati tanggal jatuh tempo."""
    daftar = ds.ambil_piutang_overdue()
    divider_dengan_judul("Piutang Jatuh Tempo")
    if not daftar:
        render_alert(
            "Tidak Ada Piutang Jatuh Tempo",
            "Semua faktur yang belum lunas masih berada dalam batas waktu pembayaran.",
            "success",
        )
        return

    render_alert(
        f"{len(daftar)} Faktur Memerlukan Penagihan",
        "Periksa daftar piutang berikut dan tindak lanjuti pelanggan yang terlambat.",
        "warning",
    )
    df = pd.DataFrame(daftar).rename(
        columns={
            "no_faktur": "No. Faktur",
            "pelanggan": "Pelanggan",
            "sisa_piutang": "Sisa Piutang",
            "tanggal_jatuh_tempo": "Jatuh Tempo",
            "hari_telat": "Telat (Hari)",
        }
    )
    if "Sisa Piutang" in df.columns:
        df["Sisa Piutang"] = df["Sisa Piutang"].apply(format_rupiah)
    kolom = [c for c in ["No. Faktur", "Pelanggan", "Sisa Piutang", "Jatuh Tempo", "Telat (Hari)"] if c in df.columns]
    with st.container(border=True):
        st.dataframe(df[kolom], use_container_width=True, hide_index=True)


def _tampilkan_stok_persediaan() -> None:
    """Menampilkan saldo terakhir tiap item hasil panen yang aktif."""
    daftar = ds.ambil_stok_persediaan()
    divider_dengan_judul("Stok Persediaan Terkini")
    if not daftar:
        st.info("Belum ada mutasi persediaan. Catat saldo awal atau hasil panen terlebih dahulu.")
        return

    df = pd.DataFrame(daftar).rename(
        columns={
            "kode_item": "Kode Item",
            "nama_item": "Nama Item",
            "satuan": "Satuan",
            "saldo_qty": "Saldo Kuantitas",
            "saldo_nilai": "Nilai Persediaan",
        }
    )
    if "Nilai Persediaan" in df.columns:
        df["Nilai Persediaan"] = df["Nilai Persediaan"].apply(
            lambda nilai: format_rupiah(int(nilai or 0))
        )
    with st.container(border=True):
        st.dataframe(df, use_container_width=True, hide_index=True)


def _tampilkan_progress_siklus(period_id: int) -> None:
    """Menampilkan tahapan siklus akuntansi berdasarkan data jurnal dan periode."""
    progress = ds.cek_progress_siklus(period_id)

    if progress["periode_tutup"]:
        tahap = 5
    elif progress["ada_penutup"]:
        tahap = 5
    elif progress["ada_penyesuaian"]:
        tahap = 4
    elif progress["ada_transaksi"]:
        tahap = 2
    else:
        tahap = 0

    divider_dengan_judul("Progress Siklus Akuntansi")
    render_steps_siklus(tahap_aktif=tahap)

    status = [
        ("Transaksi", progress["ada_transaksi"]),
        ("Penyesuaian", progress["ada_penyesuaian"]),
        ("Jurnal penutup", progress["ada_penutup"]),
        ("Periode ditutup", progress["periode_tutup"]),
    ]
    kolom = st.columns(4)
    for kol, (label, selesai) in zip(kolom, status):
        with kol:
            if selesai:
                st.success(f"{label}\nSelesai")
            else:
                st.info(f"{label}\nBelum dilakukan")


def tampilkan() -> None:
    """Fungsi utama dashboard. Hanya membaca data melalui service."""
    render_page_header(
        "Dashboard Usaha & Finansial",
        "Pantau posisi kas, penjualan cabai, laba kotor, piutang, dan persediaan dalam satu ruang kerja.",
        eyebrow="EXECUTIVE FINANCE OVERVIEW",
    )

    with st.container(border=True):
        period_id = selector_periode(
            label="Periode Laporan",
            key="dashboard_periode",
            hanya_buka=False,
            tampilkan_kalender=True,
            help="Pilih periode akuntansi untuk memperbarui seluruh ringkasan dashboard.",
        )

    if period_id is None:
        st.warning("Tidak ada periode tersedia. Tambahkan periode melalui menu Master Data.")
        return

    info_periode = ds.ambil_info_periode(period_id)
    if info_periode:
        nama_periode = f"{info_periode['nama_bulan']} {info_periode['tahun']}"
        st.caption(f"Periode aktif: **{nama_periode}** · Status: **{info_periode['status'].title()}**")

    divider_dengan_judul("Ringkasan Keuangan")
    try:
        _tampilkan_kpi(period_id)
    except Exception as error:
        st.error(f"Gagal memuat ringkasan keuangan: {error}")

    kolom_grafik, kolom_komposisi = st.columns([1.6, 1])
    with kolom_grafik:
        with st.container(border=True):
            st.subheader("Tren Penjualan Cabai")
            try:
                _tampilkan_grafik_penjualan(period_id)
            except Exception as error:
                st.error(f"Gagal memuat grafik penjualan: {error}")

    with kolom_komposisi:
        with st.container(border=True):
            st.subheader("Penjualan dan Beban")
            try:
                _tampilkan_perbandingan_penjualan_beban(period_id)
            except Exception as error:
                st.error(f"Gagal memuat perbandingan penjualan dan beban: {error}")

    divider_dengan_judul("Aktivitas Transaksi")
    try:
        _tampilkan_ringkasan_jurnal(period_id)
    except Exception as error:
        st.error(f"Gagal memuat aktivitas transaksi: {error}")

    _tampilkan_piutang_jatuh_tempo()
    _tampilkan_stok_persediaan()

    try:
        _tampilkan_progress_siklus(period_id)
    except Exception as error:
        st.error(f"Gagal memuat progress siklus akuntansi: {error}")


wajib_punya_izin("dashboard.view")
tampilkan()
