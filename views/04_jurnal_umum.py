"""
views/04_jurnal_umum.py
------------------------
Tujuan  : Menampilkan Jurnal Umum dalam format tabel standar akuntansi.
          Format: tanggal | no_bukti | keterangan | kode_akun | nama_akun | debit | kredit
          Filter berdasarkan periode, jenis jurnal, dan komoditas.
Input   : Pilihan filter dari user (periode, jenis, komoditas).
Output  : Tabel jurnal, total debit/kredit, dan opsi hapus jurnal.
Dipanggil oleh : app.py (st.navigation)
"""

import streamlit as st
import pandas as pd
import streamlit_antd_components as sac
from database.connection import get_connection
from services.journal_service import ambil_semua_jurnal, hapus_jurnal
from utils.formatting import format_rupiah, format_tanggal
from utils.ui_components import divider_dengan_judul, selector_periode
from theme import WARNA_PRIMER


# ================================================================
# HELPER
# ================================================================

@st.cache_data(ttl=30)
def _ambil_periode():
    """Ambil semua periode untuk filter dropdown."""
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, nama_bulan AS label, status FROM periods ORDER BY tahun DESC, bulan DESC"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


def _hitung_penjualan_tanpa_hpp(
    period_id: int | None = None,
    komoditas: str | None = None,
) -> int:
    """Hitung entri penjualan yang belum memiliki debit akun HPP 5108."""
    kondisi = []
    params = []
    if period_id is not None:
        kondisi.append("je.period_id = ?")
        params.append(period_id)
    if komoditas is not None:
        kondisi.append("je.komoditas = ?")
        params.append(komoditas)

    tambahan = (" AND " + " AND ".join(kondisi)) if kondisi else ""
    sql = f"""
        SELECT COUNT(*) AS jumlah
        FROM journal_entries je
        WHERE je.journal_type IN ('penjualan', 'penerimaan_kas')
        AND EXISTS (
            SELECT 1
            FROM journal_lines jl
            JOIN accounts a ON jl.account_id = a.id
            WHERE jl.journal_entry_id = je.id
              AND a.kode_akun = '4101'
              AND jl.kredit > 0
        )
        AND NOT EXISTS (
            SELECT 1
            FROM journal_lines jl
            JOIN accounts a ON jl.account_id = a.id
            WHERE jl.journal_entry_id = je.id
              AND a.kode_akun = '5108'
              AND jl.debit > 0
        )
        {tambahan}
    """
    koneksi = get_connection()
    try:
        row = koneksi.execute(sql, params).fetchone()
        return int(row["jumlah"] or 0)
    finally:
        koneksi.close()


# ================================================================
# HALAMAN UTAMA
# ================================================================

def tampilkan() -> None:
    """Fungsi utama halaman Jurnal Umum."""
    st.title("📔 Jurnal Umum")
    st.caption("Semua transaksi dalam format jurnal akuntansi standar (Debit - Kredit).")

    # ---- Panel filter ----
    with st.expander("🔍 Filter Jurnal", expanded=True):
        kol1, kol2, kol3 = st.columns(3)

        with kol1:
            period_id_filter = selector_periode(
                label="Periode Jurnal",
                key="jurnal_umum_periode",
                hanya_buka=False,
                izinkan_semua=True,
                tampilkan_kalender=True,
            )

        with kol2:
            JENIS_JURNAL = {
                "Semua Jenis": None,
                "Penerimaan Kas (KM)": "penerimaan_kas",
                "Pengeluaran Kas (KK)": "pengeluaran_kas",
                "Penjualan (JL)": "penjualan",
                "Pembelian (PB)": "pembelian",
                "Jurnal Umum (JU)": "umum",
            }
            jenis_pilih = st.selectbox(
                "Jenis Jurnal",
                list(JENIS_JURNAL.keys()),
                help=(
                    "HPP penjualan tunai berada pada Penerimaan Kas, sedangkan HPP penjualan tempo "
                    "berada pada Penjualan. Pilih Semua Jenis untuk melihat keduanya."
                ),
            )
            journal_type_filter = JENIS_JURNAL[jenis_pilih]

        with kol3:
            komoditas_pilih = sac.segmented(
                items=[
                    sac.SegmentedItem(label="Semua"),
                    sac.SegmentedItem(label="Cabai"),
                ],
                label="Komoditas",
                color=WARNA_PRIMER,
                return_index=False,
                key="filter_komoditas_jurnal",
            )
            komoditas_filter = None if komoditas_pilih == "Semua" else komoditas_pilih.lower()

    # ---- Ambil data jurnal ----
    df = ambil_semua_jurnal(
        period_id=period_id_filter,
        journal_type=journal_type_filter,
        komoditas=komoditas_filter,
    )

    if journal_type_filter == "umum":
        st.info(
            "HPP penjualan tidak dicatat sebagai jenis Jurnal Umum (JU). "
            "HPP melekat pada transaksi penjualan tunai (Penerimaan Kas) atau "
            "penjualan tempo (Penjualan). Pilih **Semua Jenis** untuk melihat seluruhnya."
        )

    jumlah_penjualan_tanpa_hpp = _hitung_penjualan_tanpa_hpp(
        period_id=period_id_filter,
        komoditas=komoditas_filter,
    )
    if jumlah_penjualan_tanpa_hpp:
        st.warning(
            f"Ditemukan **{jumlah_penjualan_tanpa_hpp} transaksi penjualan** yang belum memiliki "
            "baris debit akun **5108 - HPP Penjualan Cabai**. Transaksi lama sebelum metode "
            "perpetual diaktifkan tidak dihitung HPP-nya secara otomatis karena biaya perolehan "
            "historis harus dapat diverifikasi. Pastikan saldo awal dan biaya persediaan benar "
            "untuk transaksi baru."
        )

    if df.empty:
        st.info("Tidak ada data jurnal dengan filter yang dipilih.")
        return

    # ---- Hitung total ----
    total_debit = int(df["debit"].sum())
    total_kredit = int(df["kredit"].sum())
    seimbang = total_debit == total_kredit

    # ---- Metrik ringkasan ----
    sac.divider(label="Ringkasan", icon="bar-chart", align="center", color=WARNA_PRIMER)
    kol_m1, kol_m2, kol_m3, kol_m4 = st.columns(4)
    with kol_m1:
        jumlah_entry = df["entry_id"].nunique()
        st.metric("Total Entri Jurnal", f"{jumlah_entry:,}".replace(",", "."))
    with kol_m2:
        st.metric("Total Debit", format_rupiah(total_debit))
    with kol_m3:
        st.metric("Total Kredit", format_rupiah(total_kredit))
    with kol_m4:
        st.metric("Status", "✅ Seimbang" if seimbang else "❌ Tidak Seimbang")

    # Tampilkan peringatan jika tidak seimbang
    if not seimbang:
        sac.alert(
            label="Peringatan: Jurnal Tidak Seimbang!",
            description=f"Selisih: {format_rupiah(abs(total_debit - total_kredit))}. Mohon periksa data.",
            color="warning", icon=True,
        )

    # ---- Tabel jurnal ----
    sac.divider(label="Detail Jurnal", icon="journal-text", align="center", color=WARNA_PRIMER)

    # Format untuk tampilan
    df_tampil = df.copy()
    df_tampil["tanggal"] = df_tampil["tanggal"].apply(format_tanggal)
    df_tampil["debit"] = df_tampil["debit"].apply(lambda x: format_rupiah(x) if x > 0 else "-")
    df_tampil["kredit"] = df_tampil["kredit"].apply(lambda x: format_rupiah(x) if x > 0 else "-")

    # Rename kolom untuk tampilan yang lebih rapi
    df_tampil = df_tampil.rename(columns={
        "tanggal": "Tanggal",
        "no_bukti": "No. Bukti",
        "keterangan": "Keterangan",
        "kode_akun": "Kode",
        "nama_akun": "Nama Akun",
        "debit": "Debit",
        "kredit": "Kredit",
        "journal_type": "Jenis",
        "pihak_terkait": "Pihak Terkait",
    })

    kolom_tampil = ["Tanggal", "No. Bukti", "Keterangan", "Kode", "Nama Akun", "Debit", "Kredit"]

    st.dataframe(
        df_tampil[kolom_tampil],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Debit": st.column_config.TextColumn(width="medium"),
            "Kredit": st.column_config.TextColumn(width="medium"),
            "Keterangan": st.column_config.TextColumn(width="large"),
        },
    )

    st.caption(
        f"Menampilkan **{len(df)}** baris dari **{jumlah_entry}** entri jurnal. "
        f"Total Debit = Total Kredit = **{format_rupiah(total_debit)}**"
    )

    # ---- Hapus Jurnal ----
    sac.divider(label="Hapus Jurnal", icon="trash", align="center", color=WARNA_PRIMER)
    st.caption("⚠️ Hapus jurnal hanya bisa dilakukan jika periode masih **buka**.")

    with st.expander("🗑️ Hapus Jurnal", expanded=False):
        # Buat dropdown daftar entri jurnal (unik per no_bukti)
        df_entri = df[["entry_id", "no_bukti", "keterangan", "tanggal"]].drop_duplicates("entry_id")
        opsi_hapus = [
            f"{row['no_bukti']} | {row['keterangan'][:40]}"
            for _, row in df_entri.iterrows()
        ]

        if opsi_hapus:
            hapus_idx = st.selectbox("Pilih Jurnal yang Akan Dihapus", range(len(opsi_hapus)),
                                     format_func=lambda i: opsi_hapus[i])
            entry_id_hapus = int(df_entri.iloc[hapus_idx]["entry_id"])

            if st.button("🗑️ Hapus Jurnal Ini", type="secondary"):
                try:
                    hapus_jurnal(entry_id_hapus)
                    st.success("✅ Jurnal berhasil dihapus.")
                    st.cache_data.clear()
                    st.rerun()
                except PermissionError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Gagal menghapus jurnal: {e}")


# Panggil fungsi utama
tampilkan()
