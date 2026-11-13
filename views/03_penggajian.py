"""
views/03_penggajian.py
-----------------------
Tujuan  : Halaman input hari kerja pekerja, hitung upah, dan buat jurnal pembayaran
          atau akrual upah (tiap 2 minggu sekali).
Input   : Pilihan periode, periode bayar (minggu1/minggu2), hari kerja per pekerja.
Output  : Jurnal pengeluaran kas atau jurnal akrual upah + slip rekap.
Dipanggil oleh : app.py (st.navigation)

ALUR PENGGAJIAN:
  1. User pilih periode & periode pembayaran (minggu ke-1 atau ke-2).
  2. Sistem tampilkan daftar pekerja aktif beserta upah harian.
  3. User input hari kerja masing-masing pekerja.
  4. Sistem preview total upah.
  5. User pilih: bayar tunai (Dr Beban Upah | Cr Kas) atau akrual (Dr Beban Upah | Cr Utang Gaji).
  6. Klik Simpan → jurnal tersimpan + data absensi tercatat.
"""

import streamlit as st
import pandas as pd
from database.connection import get_connection
from services.payroll_service import (
    hitung_upah_pekerja,
    simpan_dan_bayar_upah,
    ambil_rekap_absensi,
    ambil_absensi_per_minggu,
)
from utils.formatting import format_rupiah, format_tanggal
from utils.ui_components import selector_periode
import services.period_service as ps


@st.cache_data(ttl=30)
def _ambil_daftar_periode() -> list[dict]:
    """Ambil semua periode dari database."""
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, tahun, bulan, nama_bulan, status FROM periods ORDER BY tahun DESC, bulan DESC"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=30)
def _ambil_pekerja_aktif() -> list[dict]:
    """Ambil semua pekerja aktif."""
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, nama, tipe_pekerja, upah_harian, komoditas FROM employees WHERE aktif = 1 ORDER BY nama"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=30)
def _ambil_akun_upah_dan_kas() -> dict:
    """Ambil ID akun Beban Upah Langsung (5105) dan Kas (1101)."""
    koneksi = get_connection()
    akun_upah = koneksi.execute(
        "SELECT id FROM accounts WHERE kode_akun = '5105'"
    ).fetchone()
    akun_kas = koneksi.execute(
        "SELECT id FROM accounts WHERE kode_akun = '1101'"
    ).fetchone()
    koneksi.close()
    return {
        "akun_beban_upah_id": akun_upah["id"] if akun_upah else None,
        "akun_kas_id": akun_kas["id"] if akun_kas else None,
    }


def _tampilkan_rekap_absensi(period_id: int) -> None:
    """Tampilkan rekap absensi dan upah bulan ini."""
    df = ambil_rekap_absensi(period_id)

    if df.empty or df["total_hari"].sum() == 0:
        st.info("Belum ada data absensi untuk periode ini.")
        return

    st.subheader("📋 Rekap Absensi & Upah Bulan Ini")

    # Tampilkan tabel rekap
    df_tampil = df[[
        "nama", "tipe_pekerja",
        "hari_minggu1", "hari_minggu2", "total_hari",
        "upah_harian", "total_upah",
        "sudah_dibayar_m1", "sudah_dibayar_m2"
    ]].copy()

    df_tampil["upah_harian"] = df_tampil["upah_harian"].apply(format_rupiah)
    df_tampil["total_upah"] = df_tampil["total_upah"].apply(format_rupiah)
    df_tampil["sudah_dibayar_m1"] = df_tampil["sudah_dibayar_m1"].map(
        {True: "✅ Lunas", False: "⏳ Belum"}
    )
    df_tampil["sudah_dibayar_m2"] = df_tampil["sudah_dibayar_m2"].map(
        {True: "✅ Lunas", False: "⏳ Belum"}
    )
    df_tampil = df_tampil.rename(columns={
        "nama": "Pekerja",
        "tipe_pekerja": "Tipe",
        "hari_minggu1": "Hari M1",
        "hari_minggu2": "Hari M2",
        "total_hari": "Total Hari",
        "upah_harian": "Upah/Hari",
        "total_upah": "Total Upah",
        "sudah_dibayar_m1": "M1",
        "sudah_dibayar_m2": "M2",
    })

    st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    # Total upah bulan ini
    total_upah_bulan = int(df["total_upah"].sum())
    st.metric("💰 Total Upah Bulan Ini", format_rupiah(total_upah_bulan))


def _form_input_absensi(
    period_id: int,
    periode_bayar: str,
    semua_pekerja: list[dict],
    akun_ids: dict,
) -> None:
    """Form input hari kerja per pekerja untuk satu periode pembayaran."""

    label_minggu = "Minggu 1 (Tgl 1–14)" if periode_bayar == "minggu1" else "Minggu 2 (Tgl 15–akhir)"

    # Ambil data absensi yang sudah ada
    df_existing = ambil_absensi_per_minggu(period_id, periode_bayar)
    sudah_dibayar_existing = (
        df_existing["sudah_dibayar"].any() if not df_existing.empty else False
    )

    if sudah_dibayar_existing:
        st.success(
            f"✅ **{label_minggu}** sudah dibayar. "
            "Lihat jurnal di halaman Jurnal Umum untuk detail."
        )
        # Tampilkan data absensi yang sudah ada (readonly)
        df_view = df_existing[["nama", "tipe_pekerja", "upah_harian", "hari_kerja", "total_upah"]].copy()
        df_view["upah_harian"] = df_view["upah_harian"].apply(format_rupiah)
        df_view["total_upah"] = df_view["total_upah"].apply(format_rupiah)
        df_view = df_view.rename(columns={
            "nama": "Pekerja", "tipe_pekerja": "Tipe",
            "upah_harian": "Upah/Hari", "hari_kerja": "Hari Kerja", "total_upah": "Total Upah"
        })
        st.dataframe(df_view, use_container_width=True, hide_index=True)
        return

    st.subheader(f"📝 Input Hari Kerja — {label_minggu}")

    with st.form(key=f"form_absensi_{periode_bayar}"):
        tanggal_bayar = st.date_input(
            "Tanggal Pembayaran",
            help="Tanggal saat upah dibayarkan atau dicatat sebagai utang"
        )

        st.markdown("**Hari Kerja per Pekerja:**")

        # Buat input hari kerja per pekerja
        # Ambil default dari data existing (jika ada)
        dict_existing_hari = {}
        if not df_existing.empty:
            for _, row in df_existing.iterrows():
                dict_existing_hari[row["employee_id"]] = row["hari_kerja"]

        input_hari = {}
        for pekerja in semua_pekerja:
            default_hari = dict_existing_hari.get(pekerja["id"], 0)
            tipe_label = "tetap (Rp90.000/hari)" if pekerja["tipe_pekerja"] == "tetap" else "tambahan (Rp120.000/hari)"
            kol_nama, kol_input, kol_upah = st.columns([3, 1, 2])
            with kol_nama:
                st.markdown(f"**{pekerja['nama']}** _{tipe_label}_")
            with kol_input:
                hari = st.number_input(
                    "Hari",
                    min_value=0,
                    max_value=14,
                    value=default_hari,
                    key=f"hari_{periode_bayar}_{pekerja['id']}",
                    label_visibility="collapsed",
                )
                input_hari[pekerja["id"]] = hari
            with kol_upah:
                upah_preview = hari * pekerja["upah_harian"]
                st.markdown(f"= **{format_rupiah(upah_preview)}**")

        # Hitung preview total
        total_preview = sum(
            input_hari.get(p["id"], 0) * p["upah_harian"]
            for p in semua_pekerja
        )
        st.divider()
        st.metric("💰 Preview Total Upah", format_rupiah(total_preview))

        metode_bayar = st.radio(
            "Metode Pembayaran",
            ["Bayar Tunai (Debit Kas)", "Catat sebagai Utang Gaji (Akrual)"],
            help=(
                "Tunai: Dr Beban Upah | Cr Kas\n"
                "Akrual: Dr Beban Upah | Cr Utang Gaji (bayar nanti)"
            )
        )

        tombol = st.form_submit_button("💾 Simpan & Buat Jurnal", type="primary")

        if tombol:
            if total_preview == 0:
                st.error("❌ Total upah tidak boleh nol. Isi minimal satu hari kerja.")
                return

            if not akun_ids.get("akun_beban_upah_id") or not akun_ids.get("akun_kas_id"):
                st.error("❌ Akun Beban Upah (5105) atau Kas (1101) tidak ditemukan. Periksa Bagan Akun.")
                return

            data_absensi = [
                {"employee_id": pid, "hari_kerja": hari}
                for pid, hari in input_hari.items()
            ]

            sudah_dibayar = (metode_bayar == "Bayar Tunai (Debit Kas)")

            try:
                journal_id = simpan_dan_bayar_upah(
                    period_id=period_id,
                    tanggal_bayar=str(tanggal_bayar),
                    periode_bayar=periode_bayar,
                    data_absensi=data_absensi,
                    akun_beban_upah_id=akun_ids["akun_beban_upah_id"],
                    akun_kas_id=akun_ids["akun_kas_id"],
                    sudah_dibayar=sudah_dibayar,
                )

                if journal_id:
                    metode_label = "tunai" if sudah_dibayar else "akrual (Utang Gaji)"
                    st.success(
                        f"✅ Upah {label_minggu} berhasil dicatat! "
                        f"Total: **{format_rupiah(total_preview)}** ({metode_label}). "
                        f"No. Jurnal: **{'GAJI-M1' if periode_bayar == 'minggu1' else 'GAJI-M2'}**"
                    )
                    # Hapus cache agar data terbaru muncul
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("Tidak ada upah yang perlu dicatat (semua pekerja 0 hari).")

            except ValueError as e:
                st.error(f"❌ Gagal menyimpan: {e}")
            except Exception as e:
                st.error(f"❌ Terjadi kesalahan: {e}")


def tampilkan() -> None:
    """Fungsi utama halaman Penggajian."""
    st.title("💰 Penggajian")
    st.caption(
        "Input hari kerja pekerja per periode 2 mingguan. "
        "Sistem akan menghitung upah dan membuat jurnal otomatis."
    )

    semua_periode = _ambil_daftar_periode()
    if not semua_periode:
        st.warning("⚠️ Belum ada periode. Tambahkan di Master Data → Periode.")
        return

    semua_pekerja = _ambil_pekerja_aktif()
    if not semua_pekerja:
        st.warning("⚠️ Belum ada pekerja aktif. Tambahkan di Master Data → Pekerja.")
        return

    akun_ids = _ambil_akun_upah_dan_kas()

    # Pilih periode
    kol_p, _ = st.columns([2, 2])
    with kol_p:
        period_id = selector_periode(
            label="📅 Pilih Periode Penggajian",
            key="penggajian_periode",
            hanya_buka=False,
            tampilkan_kalender=True,
            help="Pilih bulan periode penggajian",
        )

    if not period_id:
        return

    periode_obj = ps.ambil_info_periode(period_id) or {"status": "buka"}

    if periode_obj.get("status") == "tutup":
        st.warning("⚠️ Periode ini sudah ditutup. Tidak bisa menambah atau mengubah data.")
        _tampilkan_rekap_absensi(period_id)
        return

    # Tampilkan rekap absensi bulan ini
    _tampilkan_rekap_absensi(period_id)

    st.divider()

    # Tabs untuk 2 periode pembayaran
    tab_m1, tab_m2 = st.tabs(["📅 Minggu 1 (Tgl 1–14)", "📅 Minggu 2 (Tgl 15–akhir)"])

    with tab_m1:
        _form_input_absensi(
            period_id=period_id,
            periode_bayar="minggu1",
            semua_pekerja=semua_pekerja,
            akun_ids=akun_ids,
        )

    with tab_m2:
        _form_input_absensi(
            period_id=period_id,
            periode_bayar="minggu2",
            semua_pekerja=semua_pekerja,
            akun_ids=akun_ids,
        )


# Panggil fungsi utama
tampilkan()
