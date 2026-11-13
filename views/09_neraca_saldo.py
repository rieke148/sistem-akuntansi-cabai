"""
views/09_neraca_saldo.py
-------------------------
Tujuan  : Menampilkan Neraca Saldo (Trial Balance) sebelum dan setelah penyesuaian.
Input   : Pilihan periode, toggle sebelum/sesudah penyesuaian.
Output  : Tabel neraca saldo per akun + metrik validasi seimbang.
Dipanggil oleh : app.py (st.navigation)

KONSEP NERACA SALDO:
  Neraca Saldo merangkum saldo semua akun aktif per periode.
  Jika total kolom Debit == total kolom Kredit → neraca saldo seimbang.
  Ini membuktikan bahwa seluruh jurnal sudah dicatat dengan benar (double entry).
"""

import streamlit as st
import pandas as pd
from database.connection import get_connection
from services.trial_balance_service import hitung_neraca_saldo, validasi_neraca_saldo_seimbang
from utils.formatting import format_rupiah
from utils.ui_components import selector_periode


@st.cache_data(ttl=30)
def _ambil_daftar_periode() -> list[dict]:
    """Ambil semua periode dari database."""
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, tahun, bulan, nama_bulan, status FROM periods ORDER BY tahun, bulan"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


def _tampilkan_tabel_neraca(df: pd.DataFrame) -> None:
    """Tampilkan tabel neraca saldo dengan format yang rapi."""
    if df.empty:
        st.info("Tidak ada data akun untuk periode ini.")
        return

    df_tampil = df.copy()

    # Format angka uang
    df_tampil["debit"] = df_tampil["debit"].apply(
        lambda x: format_rupiah(x) if x > 0 else "-"
    )
    df_tampil["kredit"] = df_tampil["kredit"].apply(
        lambda x: format_rupiah(x) if x > 0 else "-"
    )

    df_tampil = df_tampil.rename(columns={
        "kode_akun": "Kode",
        "nama_akun": "Nama Akun",
        "kategori": "Kategori",
        "saldo_normal": "Saldo Normal",
        "debit": "Debit",
        "kredit": "Kredit",
    })

    # Sembunyikan kolom saldo_normal dari tampilan
    df_tampil = df_tampil.drop(columns=["Saldo Normal"], errors="ignore")

    st.dataframe(df_tampil, use_container_width=True, hide_index=True)


def _tampilkan_total_baris(df: pd.DataFrame) -> None:
    """Tampilkan baris total debit dan kredit di bawah tabel."""
    if df.empty:
        return

    total_debit = int(df["debit"].sum())
    total_kredit = int(df["kredit"].sum())

    kol1, kol2, kol3 = st.columns([3, 1, 1])
    with kol1:
        st.markdown("**TOTAL**")
    with kol2:
        st.markdown(f"**{format_rupiah(total_debit)}**")
    with kol3:
        st.markdown(f"**{format_rupiah(total_kredit)}**")


def tampilkan() -> None:
    """Fungsi utama halaman Neraca Saldo."""
    st.title("⚖️ Neraca Saldo")
    st.caption(
        "Trial Balance: ringkasan saldo semua akun aktif. "
        "Total Debit harus sama dengan total Kredit."
    )

    # Ambil daftar periode
    semua_periode = _ambil_daftar_periode()
    if not semua_periode:
        st.warning("⚠️ Belum ada periode. Tambahkan di Master Data → Periode.")
        return

    # Pilih periode
    kol_periode, kol_jenis = st.columns([2, 2])

    with kol_periode:
        period_id = selector_periode(
            label="📅 Pilih Periode Neraca Saldo",
            key="neraca_saldo_periode",
            hanya_buka=False,
            tampilkan_kalender=True,
        )

    if not period_id:
        return

    with kol_jenis:
        jenis_ns = st.radio(
            "Jenis Neraca Saldo",
            ["Sebelum Penyesuaian", "Setelah Penyesuaian"],
            horizontal=True,
            help=(
                "Sebelum Penyesuaian: hanya jurnal biasa (kecuali PA-).\n"
                "Setelah Penyesuaian: semua jurnal termasuk penyesuaian."
            )
        )

    termasuk_penyesuaian = (jenis_ns == "Setelah Penyesuaian")

    # Hitung neraca saldo
    df = hitung_neraca_saldo(period_id=period_id, termasuk_penyesuaian=termasuk_penyesuaian)

    # Validasi keseimbangan
    seimbang, total_debit, total_kredit = validasi_neraca_saldo_seimbang(df)

    st.divider()

    # Tampilkan status validasi
    if df.empty:
        st.info("Belum ada transaksi pada periode ini.")
        return

    if seimbang:
        st.success(
            f"✅ **Neraca Saldo Seimbang!**  "
            f"Total Debit = Total Kredit = **{format_rupiah(total_debit)}**"
        )
    else:
        selisih = abs(total_debit - total_kredit)
        st.error(
            f"❌ **Neraca Saldo TIDAK Seimbang!**  "
            f"Debit: {format_rupiah(total_debit)} | "
            f"Kredit: {format_rupiah(total_kredit)} | "
            f"Selisih: {format_rupiah(selisih)}\n\n"
            "Periksa jurnal yang ada — kemungkinan ada entri yang salah."
        )

    # Metrik ringkasan
    kol_m1, kol_m2, kol_m3 = st.columns(3)
    with kol_m1:
        st.metric("📊 Total Debit", format_rupiah(total_debit))
    with kol_m2:
        st.metric("📊 Total Kredit", format_rupiah(total_kredit))
    with kol_m3:
        st.metric("📋 Jumlah Akun", f"{len(df)} akun")

    st.divider()

    # Filter per kategori (opsional)
    semua_kategori = sorted(df["kategori"].unique().tolist())
    kategori_pilihan = st.multiselect(
        "Filter Kategori Akun",
        semua_kategori,
        default=semua_kategori,
        help="Pilih kategori akun yang ingin ditampilkan"
    )

    df_tampil = df[df["kategori"].isin(kategori_pilihan)] if kategori_pilihan else df

    # Tampilkan per kategori (dengan sub-judul)
    import services.period_service as ps
    info_p = ps.ambil_info_periode(period_id)
    periode_label = info_p["nama_bulan"] if info_p else f"Periode {period_id}"
    jenis_label = "Sebelum Penyesuaian" if not termasuk_penyesuaian else "Setelah Penyesuaian"
    st.subheader(f"📋 Neraca Saldo — {periode_label} ({jenis_label})")

    for kategori in semua_kategori:
        if kategori not in kategori_pilihan:
            continue

        df_kat = df_tampil[df_tampil["kategori"] == kategori]
        if df_kat.empty:
            continue

        # Sub-total per kategori
        sub_debit = int(df_kat["debit"].sum())
        sub_kredit = int(df_kat["kredit"].sum())

        with st.expander(
            f"**{kategori}** — Debit: {format_rupiah(sub_debit)} | Kredit: {format_rupiah(sub_kredit)}",
            expanded=True
        ):
            _tampilkan_tabel_neraca(df_kat)

    # Baris total keseluruhan
    st.divider()
    kol_label, kol_d, kol_k = st.columns([3, 1, 1])
    with kol_label:
        st.markdown("### 📊 TOTAL KESELURUHAN")
    with kol_d:
        st.markdown(f"### {format_rupiah(total_debit)}")
    with kol_k:
        st.markdown(f"### {format_rupiah(total_kredit)}")

    if seimbang:
        st.caption("✅ Neraca saldo seimbang — semua jurnal tercatat dengan benar (double entry).")
    else:
        st.caption(
            "❌ Neraca saldo tidak seimbang. "
            "Periksa apakah ada jurnal yang belum lengkap atau salah akun."
        )


# Panggil fungsi utama
tampilkan()
