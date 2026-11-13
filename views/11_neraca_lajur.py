"""
views/11_neraca_lajur.py
--------------------------
Tujuan  : Menampilkan Neraca Lajur (Worksheet) 10 kolom.
Input   : Pilih periode dari selectbox.
Output  : Tabel neraca lajur lengkap + ringkasan validasi.
Dipanggil oleh : app.py (st.navigation)
"""

import streamlit as st
import pandas as pd
from database.connection import get_connection
from services.worksheet_service import buat_neraca_lajur, hitung_laba_rugi_dari_lajur, validasi_neraca_lajur
from utils.formatting import format_rupiah
from utils.ui_components import selector_periode
import streamlit_antd_components as sac


# ---------------------------------------------------------------------------
# Fungsi pembantu (private)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def _ambil_periode_buka_dan_tutup() -> list[dict]:
    """Mengambil semua periode (buka dan tutup) untuk dipilih di neraca lajur."""
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            "SELECT id, tahun, bulan, nama_bulan AS label, status FROM periods ORDER BY tahun, bulan"
        ).fetchall()
    finally:
        koneksi.close()
    return [dict(r) for r in rows]


def _format_tabel_lajur(df: pd.DataFrame) -> pd.DataFrame:
    """
    Memformat kolom-kolom angka dalam DataFrame neraca lajur
    untuk tampilan yang lebih rapi.
    """
    kolom_angka = [
        "ns_debit", "ns_kredit",
        "peny_debit", "peny_kredit",
        "nsd_debit", "nsd_kredit",
        "lr_debit", "lr_kredit",
        "neraca_debit", "neraca_kredit",
    ]
    df_tampil = df.copy()
    for kol in kolom_angka:
        df_tampil[kol] = df_tampil[kol].apply(
            lambda x: format_rupiah(int(x)) if int(x) != 0 else "-"
        )
    return df_tampil


def _tampilkan_ringkasan_validasi(validasi: dict) -> None:
    """Menampilkan hasil validasi keseimbangan neraca lajur."""
    sac.divider(label="Validasi Keseimbangan", icon="check-circle", align="center")

    col1, col2, col3 = st.columns(3)

    with col1:
        if validasi["ns_seimbang"]:
            sac.alert(
                label="Neraca Saldo Seimbang ✓",
                description=f"D = K = {format_rupiah(validasi['ns_total_debit'])}",
                color="success",
                icon=True,
            )
        else:
            sac.alert(
                label="Neraca Saldo Tidak Seimbang!",
                description=(
                    f"Debit: {format_rupiah(validasi['ns_total_debit'])}\n"
                    f"Kredit: {format_rupiah(validasi['ns_total_kredit'])}"
                ),
                color="error",
                icon=True,
            )

    with col2:
        if validasi["nsd_seimbang"]:
            sac.alert(
                label="NS Disesuaikan Seimbang ✓",
                description=f"D = K = {format_rupiah(validasi['nsd_total_debit'])}",
                color="success",
                icon=True,
            )
        else:
            sac.alert(
                label="NS Disesuaikan Tidak Seimbang!",
                description=(
                    f"Debit: {format_rupiah(validasi['nsd_total_debit'])}\n"
                    f"Kredit: {format_rupiah(validasi['nsd_total_kredit'])}"
                ),
                color="error",
                icon=True,
            )

    with col3:
        laba = validasi["laba_bersih"]
        if laba >= 0:
            sac.alert(
                label=f"Laba Bersih: {format_rupiah(laba)}",
                description="Neraca seimbang dengan laba ditambahkan ke ekuitas.",
                color="success",
                icon=True,
            )
        else:
            sac.alert(
                label=f"Rugi Bersih: {format_rupiah(abs(laba))}",
                description="Neraca seimbang dengan rugi mengurangi ekuitas.",
                color="warning",
                icon=True,
            )


def _tampilkan_subtotal(df: pd.DataFrame, judul: str, kol_d: str, kol_k: str) -> None:
    """Menampilkan sub-total satu pasang kolom di bawah tabel."""
    total_d = int(df[kol_d].sum())
    total_k = int(df[kol_k].sum())
    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        st.markdown(f"**Sub-total {judul}**")
    with col2:
        st.markdown(f"**{format_rupiah(total_d)}**")
    with col3:
        st.markdown(f"**{format_rupiah(total_k)}**")


# ---------------------------------------------------------------------------
# Fungsi utama tampilan
# ---------------------------------------------------------------------------

def tampilkan() -> None:
    """Halaman utama Neraca Lajur."""
    st.title("📊 Neraca Lajur (Worksheet 10 Kolom)")
    st.caption(
        "Neraca Lajur adalah alat bantu untuk menyusun laporan keuangan. "
        "Terdiri dari 5 pasang kolom: NS sebelum penyesuaian, Penyesuaian, "
        "NS Disesuaikan, Laba Rugi, dan Neraca."
    )

    # -------------------------------------------------------------------
    # Pilih periode
    # -------------------------------------------------------------------
    kol_p, _ = st.columns([2, 2])
    with kol_p:
        period_id = selector_periode(
            label="📅 Pilih Periode Neraca Lajur",
            key="neraca_lajur_periode",
            hanya_buka=False,
            tampilkan_kalender=True,
        )

    if not period_id:
        return

    # -------------------------------------------------------------------
    # Hitung neraca lajur
    # -------------------------------------------------------------------
    with st.spinner("Menghitung neraca lajur..."):
        df_lajur = buat_neraca_lajur(period_id)

    if df_lajur.empty:
        sac.alert(
            label="Belum ada data transaksi untuk periode ini.",
            description="Input transaksi terlebih dahulu, kemudian buat ayat penyesuaian.",
            color="info",
            icon=True,
        )
        return

    # -------------------------------------------------------------------
    # Ringkasan validasi keseimbangan
    # -------------------------------------------------------------------
    validasi = validasi_neraca_lajur(df_lajur)
    _tampilkan_ringkasan_validasi(validasi)

    st.divider()

    # -------------------------------------------------------------------
    # Tampilkan tabel neraca lajur lengkap
    # -------------------------------------------------------------------
    sac.divider(label="Tabel Neraca Lajur", icon="table", align="center")

    # Format tampilan
    df_tampil = df_lajur.copy()

    # Kolom yang akan ditampilkan dan label header
    rename_map = {
        "kode_akun": "Kode",
        "nama_akun": "Nama Akun",
        "ns_debit": "NS Debit",
        "ns_kredit": "NS Kredit",
        "peny_debit": "Peny. Debit",
        "peny_kredit": "Peny. Kredit",
        "nsd_debit": "NSD Debit",
        "nsd_kredit": "NSD Kredit",
        "lr_debit": "L/R Debit",
        "lr_kredit": "L/R Kredit",
        "neraca_debit": "Neraca Debit",
        "neraca_kredit": "Neraca Kredit",
    }

    df_tampil = df_tampil.drop(columns=["kategori"]).rename(columns=rename_map)

    # Format angka
    for kol in df_tampil.columns:
        if kol not in ("Kode", "Nama Akun"):
            df_tampil[kol] = df_tampil[kol].apply(
                lambda x: format_rupiah(int(x)) if int(x) != 0 else "-"
            )

    # Tampilkan dengan height yang proporsional
    st.dataframe(
        df_tampil,
        use_container_width=True,
        height=min(800, 50 + len(df_tampil) * 35),
        column_config={
            "Kode": st.column_config.TextColumn("Kode", width="small"),
            "Nama Akun": st.column_config.TextColumn("Nama Akun", width="medium"),
        }
    )

    # -------------------------------------------------------------------
    # Baris total (footer)
    # -------------------------------------------------------------------
    st.divider()
    sac.divider(label="Total Kolom", icon="sigma", align="center")

    col_labels = st.columns([2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
    headers = ["", "NS Debit", "NS Kredit", "Peny D", "Peny K",
               "NSD Debit", "NSD Kredit", "L/R Debit", "L/R Kredit",
               "Neraca D", "Neraca K"]
    for i, h in enumerate(headers):
        col_labels[i].markdown(f"**{h}**")

    col_vals = st.columns([2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
    total_map = [
        ("", "TOTAL"),
        ("ns_debit", ""),
        ("ns_kredit", ""),
        ("peny_debit", ""),
        ("peny_kredit", ""),
        ("nsd_debit", ""),
        ("nsd_kredit", ""),
        ("lr_debit", ""),
        ("lr_kredit", ""),
        ("neraca_debit", ""),
        ("neraca_kredit", ""),
    ]
    total_vals = ["TOTAL"] + [
        format_rupiah(int(df_lajur[kol].sum())) if kol else ""
        for kol, _ in total_map[1:]
    ]
    for i, v in enumerate(total_vals):
        col_vals[i].markdown(f"**{v}**")

    # -------------------------------------------------------------------
    # Baris Laba / Rugi di kolom Neraca
    # -------------------------------------------------------------------
    laba_bersih = validasi["laba_bersih"]
    if laba_bersih != 0:
        st.divider()
        col_lr = st.columns([2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
        label_lr = "Laba Bersih" if laba_bersih >= 0 else "Rugi Bersih"
        nilai_lr = format_rupiah(abs(laba_bersih))

        col_lr[0].markdown(f"**{label_lr}**")
        # Laba bersih: sisi debit L/R (beban < pendapatan) → masuk neraca kredit
        if laba_bersih >= 0:
            col_lr[7].markdown(f"**{nilai_lr}**")   # L/R Debit (penyeimbang)
            col_lr[10].markdown(f"**{nilai_lr}**")  # Neraca Kredit (ekuitas bertambah)
        else:
            col_lr[8].markdown(f"**{nilai_lr}**")   # L/R Kredit (penyeimbang)
            col_lr[9].markdown(f"**{nilai_lr}**")   # Neraca Debit (ekuitas berkurang)


tampilkan()
