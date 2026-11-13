"""
views/00_dashboard.py
---------------------
Tujuan  : Halaman beranda. Menampilkan ringkasan keuangan, indikator
          tahapan siklus akuntansi, grafik, dan peringatan penting.
Input   : Data dari database melalui services/dashboard_service.py.
Output  : Tampilan dashboard dengan metrik, grafik, alert, dan tabel.
Dipanggil oleh : app.py (st.navigation)
"""

import streamlit as st
import streamlit_antd_components as sac
import pandas as pd

from theme import NAMA_PERUSAHAAN, WARNA_PRIMER
from utils.ui_components import render_steps_siklus, divider_dengan_judul, selector_periode
from utils.formatting import format_rupiah
import services.dashboard_service as ds


# ---------------------------------------------------------------
# HELPER INTERNAL
# ---------------------------------------------------------------
def _warna_saldo(nilai: int) -> str:
    """Mengembalikan warna teks berdasarkan nilai positif/negatif."""
    return "normal" if nilai >= 0 else "inverse"


def _tampilkan_metrik_utama(period_id: int) -> None:
    """Menampilkan 4 metrik utama: Kas, Piutang Overdue, Penjualan, Beban."""
    kas_bank = ds.ambil_saldo_kas_bank(period_id)
    overdue = ds.ambil_piutang_overdue()
    jual_beban = ds.ambil_ringkasan_penjualan_beban(period_id)

    kol1, kol2, kol3, kol4 = st.columns(4)
    with kol1:
        st.metric(
            label="💵 Total Kas & Bank",
            value=format_rupiah(kas_bank["total"]),
            delta=f"Kas {format_rupiah(kas_bank['kas'])} | Bank {format_rupiah(kas_bank['bank'])}",
            delta_color="off",
            help="Saldo Kas Tunai (1101) + Bank BRI (1102) periode ini",
        )
    with kol2:
        jml_overdue = len(overdue)
        total_overdue = sum(r["sisa_piutang"] for r in overdue)
        st.metric(
            label="⚠️ Piutang Jatuh Tempo",
            value=f"{jml_overdue} faktur",
            delta=format_rupiah(total_overdue) if jml_overdue else "Semua lancar ✓",
            delta_color="inverse" if jml_overdue else "off",
            help="Faktur yang sudah melewati tanggal jatuh tempo",
        )
    with kol3:
        st.metric(
            label="📈 Penjualan Periode Ini",
            value=format_rupiah(jual_beban["penjualan"]),
            help="Total kredit ke akun pendapatan (4xxx)",
        )
    with kol4:
        st.metric(
            label="📉 Beban Periode Ini",
            value=format_rupiah(jual_beban["beban"]),
            delta=format_rupiah(jual_beban["laba_kotor"]),
            delta_color=_warna_saldo(jual_beban["laba_kotor"]),
            help="Total debit ke akun beban (5xxx). Delta = Laba Kotor",
        )


def _tampilkan_grafik_penjualan(period_id: int) -> None:
    """Menampilkan grafik bar penjualan per komoditas."""
    df = ds.ambil_penjualan_per_komoditas(period_id)
    if df.empty:
        st.info("📊 Belum ada data penjualan untuk grafik.")
        return

    # Mapping nama display
    peta_nama = {
        "cabai": "🌶️ Cabai",
        "selada": "🥬 Selada",
        "melon": "🍈 Melon",
        "umum": "📦 Umum",
    }
    df["komoditas_label"] = df["komoditas"].map(lambda x: peta_nama.get(x, x))

    st.bar_chart(
        data=df.set_index("komoditas_label")["penjualan"],
        color=WARNA_PRIMER,
        use_container_width=True,
    )


def _tampilkan_grafik_penjualan_vs_beban(period_id: int) -> None:
    """Menampilkan grafik bar perbandingan total penjualan vs beban."""
    jual_beban = ds.ambil_ringkasan_penjualan_beban(period_id)
    if jual_beban["penjualan"] == 0 and jual_beban["beban"] == 0:
        st.info("📊 Belum ada data transaksi keuangan untuk grafik.")
        return

    df_pv = pd.DataFrame([
        {"Kategori": "Penjualan", "Nominal": jual_beban["penjualan"]},
        {"Kategori": "Total Beban", "Nominal": jual_beban["beban"]},
    ])

    st.bar_chart(
        data=df_pv.set_index("Kategori")["Nominal"],
        color=WARNA_PRIMER,
        use_container_width=True,
    )


def _tampilkan_ringkasan_jurnal(period_id: int) -> None:
    """Menampilkan ringkasan jumlah transaksi per jenis."""
    ring = ds.ambil_ringkasan_jurnal(period_id)
    kol1, kol2, kol3, kol4, kol5 = st.columns(5)
    with kol1:
        st.metric("🛒 Penjualan", ring["penjualan"])
    with kol2:
        st.metric("🛍️ Pembelian", ring["pembelian"])
    with kol3:
        st.metric("💰 Penerimaan Kas", ring["penerimaan_kas"])
    with kol4:
        st.metric("💸 Pengeluaran Kas", ring["pengeluaran_kas"])
    with kol5:
        st.metric("📝 Jurnal Umum", ring["umum"])
    st.caption(f"**Total {ring['total_transaksi']} transaksi** (diluar penyesuaian & penutup)")


def _tampilkan_piutang_overdue() -> None:
    """Menampilkan tabel piutang jatuh tempo."""
    overdue = ds.ambil_piutang_overdue()
    if not overdue:
        sac.alert(
            label="✅ Tidak Ada Piutang Jatuh Tempo",
            description="Semua piutang masih dalam batas jatuh tempo.",
            color="success",
            icon=True,
        )
        return

    sac.alert(
        label=f"⚠️ {len(overdue)} Faktur Piutang Jatuh Tempo!",
        description="Segera lakukan penagihan untuk faktur di bawah ini.",
        color="warning",
        icon=True,
    )

    df = pd.DataFrame(overdue)
    df = df.rename(columns={
        "no_faktur": "No. Faktur",
        "pelanggan": "Pelanggan",
        "sisa_piutang": "Sisa Piutang",
        "tanggal_jatuh_tempo": "Jatuh Tempo",
        "hari_telat": "Telat (Hari)",
    })
    df["Sisa Piutang"] = df["Sisa Piutang"].apply(format_rupiah)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _tampilkan_stok_persediaan() -> None:
    """Menampilkan tabel stok persediaan terkini."""
    stok = ds.ambil_stok_persediaan()
    if not stok:
        st.info("📦 Belum ada data pergerakan persediaan.")
        return

    df = pd.DataFrame(stok)
    df = df.rename(columns={
        "kode_item": "Kode",
        "nama_item": "Item",
        "satuan": "Satuan",
        "saldo_qty": "Stok (Qty)",
        "saldo_nilai": "Nilai (Rp)",
    })
    df["Nilai (Rp)"] = df["Nilai (Rp)"].apply(lambda x: format_rupiah(int(x or 0)))

    # Tandai stok kosong
    def _style_stok(val):
        return "color: red; font-weight: bold;" if val <= 0 else ""

    fn_map = getattr(df.style, "map", getattr(df.style, "applymap", None))
    styled_df = fn_map(_style_stok, subset=["Stok (Qty)"]) if fn_map else df
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
    )


def _tampilkan_steps_siklus(period_id: int) -> None:
    """Menampilkan indikator progress siklus akuntansi."""
    progress = ds.cek_progress_siklus(period_id)

    # Tentukan tahap aktif berdasarkan progress
    if progress["periode_tutup"]:
        tahap = 5  # Penutupan (selesai semua)
    elif progress["ada_penutup"]:
        tahap = 5
    elif progress["ada_penyesuaian"]:
        tahap = 4  # Laporan Keuangan
    elif progress["ada_transaksi"]:
        tahap = 2  # Neraca Saldo
    else:
        tahap = 0  # Belum ada transaksi

    render_steps_siklus(tahap_aktif=tahap)

    # Tampilkan status masing-masing tahap
    kol1, kol2, kol3, kol4 = st.columns(4)
    with kol1:
        if progress["ada_transaksi"]:
            st.success("✅ Transaksi diinput")
        else:
            st.warning("⏳ Belum ada transaksi")
    with kol2:
        if progress["ada_penyesuaian"]:
            st.success("✅ Ayat penyesuaian dibuat")
        else:
            st.warning("⏳ Belum ada penyesuaian")
    with kol3:
        if progress["ada_penutup"]:
            st.success("✅ Jurnal penutup dibuat")
        else:
            st.warning("⏳ Belum ditutup")
    with kol4:
        if progress["periode_tutup"]:
            st.success("✅ Periode ditutup")
        else:
            st.warning("⏳ Periode masih buka")


# ---------------------------------------------------------------
# FUNGSI UTAMA
# ---------------------------------------------------------------
def tampilkan() -> None:
    """Fungsi utama halaman Dashboard. Dipanggil oleh app.py."""
    kol_head, kol_periode = st.columns([3, 2])
    with kol_head:
        st.title("🏠 Dashboard")
        st.caption(NAMA_PERUSAHAAN)
    with kol_periode:
        period_id = selector_periode(
            label="📅 Filter Periode Dashboard",
            key="dashboard_periode",
            hanya_buka=False,
            tampilkan_kalender=True,
            help="Pilih periode untuk melihat metrik dan grafik keuangan",
        )

    if period_id is None:
        st.warning(
            "⚠️ Tidak ada periode yang dipilih. "
            "Pilih periode di atas atau tambahkan di menu **Master Data → Periode**."
        )
        return

    info_periode = ds.ambil_info_periode(period_id)
    if info_periode:
        label_periode = f"{info_periode['nama_bulan']} {info_periode['tahun']}"
        st.info(f"📅 Menampilkan data **{label_periode}** (Status: {info_periode['status'].title()})")

    # ================================================================
    # BAGIAN 1: METRIK UTAMA
    # ================================================================
    divider_dengan_judul("Ringkasan Keuangan", "bar-chart")
    try:
        _tampilkan_metrik_utama(period_id)
    except Exception as e:
        st.error(f"Gagal memuat metrik: {e}")

    # ================================================================
    # BAGIAN 2: GRAFIK & RINGKASAN TRANSAKSI
    # ================================================================
    st.divider()
    kol_grafik, kol_jurnal = st.columns([3, 2])

    with kol_grafik:
        divider_dengan_judul("Grafik Keuangan", "bar-chart-line")
        tab_komoditas, tab_pv = st.tabs(["🌾 Per Komoditas", "⚖️ Penjualan vs Beban"])
        with tab_komoditas:
            try:
                _tampilkan_grafik_penjualan(period_id)
            except Exception as e:
                st.error(f"Gagal memuat grafik: {e}")
        with tab_pv:
            try:
                _tampilkan_grafik_penjualan_vs_beban(period_id)
            except Exception as e:
                st.error(f"Gagal memuat grafik: {e}")

    with kol_jurnal:
        divider_dengan_judul("Aktivitas Transaksi", "journal-text")
        try:
            _tampilkan_ringkasan_jurnal(period_id)
        except Exception as e:
            st.error(f"Gagal memuat ringkasan jurnal: {e}")

    # ================================================================
    # BAGIAN 3: PERINGATAN PIUTANG JATUH TEMPO
    # ================================================================
    st.divider()
    divider_dengan_judul("Piutang Jatuh Tempo", "exclamation-triangle")
    try:
        _tampilkan_piutang_overdue()
    except Exception as e:
        st.error(f"Gagal memuat piutang: {e}")

    # ================================================================
    # BAGIAN 4: STOK PERSEDIAAN
    # ================================================================
    st.divider()
    divider_dengan_judul("Stok Persediaan Terkini", "box-seam")
    try:
        _tampilkan_stok_persediaan()
    except Exception as e:
        st.error(f"Gagal memuat stok: {e}")

    # ================================================================
    # BAGIAN 5: INDIKATOR SIKLUS AKUNTANSI
    # ================================================================
    st.divider()
    divider_dengan_judul("Progress Siklus Akuntansi", "arrow-right-circle")
    try:
        _tampilkan_steps_siklus(period_id)
    except Exception as e:
        st.error(f"Gagal memuat progress siklus: {e}")

    # ================================================================
    # BAGIAN 6: INFO PROGRESS PEMBANGUNAN
    # ================================================================
    st.divider()
    divider_dengan_judul("Progress Pembangunan Sistem", "tools")
    fase_list = [
        ("✅", "F0", "Fondasi (Struktur, Database, COA, Tema)"),
        ("✅", "F1", "Master Data (COA, Pelanggan, Supplier, Pekerja, Aset, Parameter)"),
        ("✅", "F2", "Input Transaksi + Mesin Jurnal (10 jenis transaksi + pratinjau jurnal)"),
        ("✅", "F3", "Jurnal Umum & 4 Jurnal Khusus"),
        ("✅", "F4", "Buku Besar + BB Pembantu + Kartu Persediaan"),
        ("✅", "F5", "Neraca Saldo + Penggajian + Penyesuaian"),
        ("✅", "F6", "Neraca Lajur + Laporan Keuangan + Jurnal Penutup"),
        ("✅", "F7", "Dashboard (data nyata) + Export Excel/PDF + Backup/Restore"),
        ("⏳", "F8", "Tes Akhir, Rapikan, Deploy"),
    ]
    for ikon, kode, nama in fase_list:
        st.markdown(f"{ikon} **{kode}** — {nama}")


# Panggil fungsi utama
tampilkan()
