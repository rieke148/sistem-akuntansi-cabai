"""
views/10_ayat_penyesuaian.py
-----------------------------
Tujuan  : Membuat dan menampilkan ayat jurnal penyesuaian akhir periode.
          Jenis: penyusutan aset tetap dan akrual upah.
Input   : Pilihan periode, parameter penyesuaian.
Output  : Jurnal penyesuaian dibuat dan disimpan; daftar semua penyesuaian ditampilkan.
Dipanggil oleh : app.py (st.navigation)

JENIS PENYESUAIAN YANG DIDUKUNG:
  1. Penyusutan Aset Tetap: garis lurus, dihitung per bulan per aset.
  2. Akrual Upah: upah yang belum dibayar di akhir periode.
"""

import streamlit as st
import pandas as pd
from database.connection import get_connection
from services.adjusting_service import (
    buat_penyesuaian_penyusutan,
    buat_penyesuaian_akrual_upah,
    ambil_ringkasan_penyesuaian,
    hapus_penyesuaian,
    cek_penyesuaian_sudah_ada,
)
from services.depreciation_service import hitung_semua_penyusutan
from utils.formatting import format_rupiah, format_tanggal
from utils.ui_components import selector_periode, render_page_header
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
def _ambil_akun_penyesuaian() -> dict:
    """Ambil ID akun-akun yang dibutuhkan untuk penyesuaian."""
    koneksi = get_connection()

    def cari(kode):
        row = koneksi.execute(
            "SELECT id, nama_akun FROM accounts WHERE kode_akun = ?", (kode,)
        ).fetchone()
        return dict(row) if row else {"id": None, "nama_akun": f"[{kode} tidak ditemukan]"}

    hasil = {
        "beban_upah": cari("6110"),               # Beban Gaji (COA baru)
        "utang_gaji": cari("2210"),               # Utang Gaji (COA baru)
    }
    koneksi.close()
    return hasil


def _tampilkan_daftar_penyesuaian(period_id: int) -> None:
    """Tampilkan semua jurnal penyesuaian yang sudah dibuat untuk periode ini."""
    df = ambil_ringkasan_penyesuaian(period_id)

    if df.empty:
        st.info("Belum ada jurnal penyesuaian untuk periode ini.")
        return

    st.subheader("📋 Daftar Penyesuaian yang Sudah Dibuat")

    total_penyesuaian = int(df["total_debit"].sum())
    kol_m1, kol_m2 = st.columns(2)
    with kol_m1:
        st.metric("📝 Jumlah Ayat Penyesuaian", f"{len(df)} jurnal")
    with kol_m2:
        st.metric("💰 Total Penyesuaian", format_rupiah(total_penyesuaian))

    # Tampilkan tabel
    df_tampil = df.copy()
    df_tampil["tanggal"] = df_tampil["tanggal"].apply(format_tanggal)
    df_tampil["total_debit"] = df_tampil["total_debit"].apply(format_rupiah)
    df_tampil["total_kredit"] = df_tampil["total_kredit"].apply(format_rupiah)
    df_tampil = df_tampil.rename(columns={
        "no_bukti": "No. Bukti",
        "tanggal": "Tanggal",
        "keterangan": "Keterangan",
        "total_debit": "Debit",
        "total_kredit": "Kredit",
    })
    st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    # Tombol hapus (per no_bukti)
    with st.expander("🗑️ Hapus Penyesuaian"):
        st.caption("Pilih no. bukti yang ingin dihapus. Hati-hati — tidak bisa dibatalkan!")
        opsi_hapus = df["no_bukti"].tolist()
        no_bukti_hapus = st.selectbox("Pilih No. Bukti", opsi_hapus, key="hapus_penyesuaian")

        if st.button("🗑️ Hapus Penyesuaian Ini", type="secondary"):
            try:
                berhasil = hapus_penyesuaian(no_bukti_hapus)
                if berhasil:
                    st.success(f"✅ Jurnal penyesuaian {no_bukti_hapus} berhasil dihapus.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Jurnal tidak ditemukan.")
            except ValueError as e:
                st.error(f"❌ {e}")


def _tab_penyusutan(period_id: int, tanggal_penyesuaian: str) -> None:
    """Tab penyesuaian: penyusutan aset tetap."""
    st.subheader("🏭 Penyusutan Aset Tetap")
    st.caption(
        "Penyusutan dihitung dengan metode garis lurus: "
        "(Harga Perolehan - Nilai Residu) ÷ (Umur Ekonomis × 12 bulan)."
    )

    # Tampilkan preview penyusutan
    df_penyusutan = hitung_semua_penyusutan()

    if df_penyusutan.empty:
        st.warning("Belum ada aset tetap yang perlu disusutkan.")
        return

    # Filter hanya yang perlu disusutkan
    df_disusutkan = df_penyusutan[df_penyusutan["is_disusutkan"] == True].copy()

    if df_disusutkan.empty:
        st.info("Tidak ada aset yang perlu disusutkan.")
        return

    # Tampilkan tabel preview
    df_preview = df_disusutkan[["kode_aset", "nama_aset", "harga_perolehan",
                                 "nilai_residu", "umur_ekonomis_tahun",
                                 "penyusutan_per_bulan"]].copy()
    df_preview["harga_perolehan"] = df_preview["harga_perolehan"].apply(format_rupiah)
    df_preview["nilai_residu"] = df_preview["nilai_residu"].apply(format_rupiah)
    df_preview["penyusutan_per_bulan"] = df_preview["penyusutan_per_bulan"].apply(format_rupiah)
    df_preview = df_preview.rename(columns={
        "kode_aset": "Kode",
        "nama_aset": "Nama Aset",
        "harga_perolehan": "Harga Perolehan",
        "nilai_residu": "Nilai Residu",
        "umur_ekonomis_tahun": "Umur (Tahun)",
        "penyusutan_per_bulan": "Penyusutan/Bulan",
    })
    st.dataframe(df_preview, use_container_width=True, hide_index=True)

    total_penyusutan = int(df_disusutkan["penyusutan_per_bulan"].sum())
    st.metric("💰 Total Penyusutan Bulan Ini", format_rupiah(total_penyusutan))

    # Cek apakah sudah dibuat
    sudah_ada = cek_penyesuaian_sudah_ada(period_id, "penyusutan")
    if sudah_ada:
        st.success("✅ Jurnal penyesuaian penyusutan sudah dibuat untuk periode ini.")
        return

    if st.button("💾 Buat Jurnal Penyesuaian Penyusutan", type="primary", key="btn_penyusutan"):
        try:
            ids = buat_penyesuaian_penyusutan(period_id=period_id, tanggal=tanggal_penyesuaian)
            if ids:
                st.success(
                    f"✅ Berhasil membuat **{len(ids)} jurnal** penyesuaian penyusutan. "
                    f"Total: {format_rupiah(total_penyusutan)}"
                )
                st.cache_data.clear()
                st.rerun()
            else:
                st.info("Tidak ada penyesuaian yang dibuat.")
        except ValueError as e:
            st.error(f"❌ {e}")
        except Exception as e:
            st.error(f"❌ Terjadi kesalahan: {e}")


def _tab_akrual_upah(period_id: int, tanggal_penyesuaian: str, akun_ids: dict) -> None:
    """Tab penyesuaian: akrual upah yang belum dibayar."""
    st.subheader("👷 Akrual Upah Belum Dibayar")
    st.caption(
        "Jika ada upah pekerja yang belum dibayar di akhir bulan, catat sebagai Utang Gaji. "
        "Dr Beban Upah | Cr Utang Gaji"
    )

    st.info(
        "💡 **Kapan dipakai?** Upah minggu ke-2 (tgl 15–akhir) biasanya dibayarkan "
        "di awal bulan berikutnya. Jika belum dibayar saat tutup buku, catat di sini."
    )

    # Input jumlah akrual
    jumlah_akrual = st.number_input(
        "Jumlah Upah Belum Dibayar (Rp)",
        min_value=0,
        max_value=100_000_000,
        value=0,
        step=90_000,
        help="Total upah yang belum dibayar sampai akhir periode",
    )

    if jumlah_akrual > 0:
        st.info(
            f"Preview jurnal:\n"
            f"- **Debit** Beban Upah Langsung: **{format_rupiah(jumlah_akrual)}**\n"
            f"- **Kredit** Utang Gaji: **{format_rupiah(jumlah_akrual)}**"
        )

    # Validasi akun
    akun_upah = akun_ids["beban_upah"]
    akun_utang = akun_ids["utang_gaji"]

    if not akun_upah["id"] or not akun_utang["id"]:
        st.error("❌ Akun Beban Gaji (6110) atau Utang Gaji (2210) tidak ditemukan.")
        return

    # Cek sudah ada?
    sudah_ada = cek_penyesuaian_sudah_ada(period_id, "akrual_upah")
    if sudah_ada:
        st.success("✅ Jurnal akrual upah sudah dibuat untuk periode ini.")
        return

    if st.button("💾 Buat Jurnal Akrual Upah", type="primary", key="btn_akrual",
                 disabled=(jumlah_akrual == 0)):
        try:
            journal_id = buat_penyesuaian_akrual_upah(
                period_id=period_id,
                tanggal=tanggal_penyesuaian,
                akun_beban_upah_id=akun_upah["id"],
                akun_utang_gaji_id=akun_utang["id"],
                jumlah_akrual=int(jumlah_akrual),
            )
            if journal_id:
                st.success(
                    f"✅ Jurnal akrual upah berhasil dibuat! "
                    f"Utang gaji dicatat: {format_rupiah(jumlah_akrual)}"
                )
                st.cache_data.clear()
                st.rerun()
        except Exception as e:
            st.error(f"❌ {e}")


def tampilkan() -> None:
    """Fungsi utama halaman Ayat Penyesuaian."""
    render_page_header("Ayat Penyesuaian", "Susun penyusutan aset dan akrual upah pada akhir periode.", eyebrow="laporan")
    st.caption(
        "Penyesuaian akhir periode: penyusutan aset tetap dan akrual upah. "
        "Setiap penyesuaian membuat jurnal otomatis yang bisa dilihat di Jurnal Umum."
    )

    semua_periode = _ambil_daftar_periode()
    if not semua_periode:
        st.warning("⚠️ Belum ada periode.")
        return

    akun_ids = _ambil_akun_penyesuaian()

    # Pilih periode
    kol_periode, kol_tgl = st.columns([2, 2])
    with kol_periode:
        period_id = selector_periode(
            label="📅 Pilih Periode Penyesuaian",
            key="penyesuaian_periode",
            hanya_buka=False,
            tampilkan_kalender=True,
        )

    if not period_id:
        return

    import datetime
    periode_obj = ps.ambil_info_periode(period_id) or {"tahun": 2026, "bulan": 10, "status": "buka"}
    bln = periode_obj["bulan"]
    thn = periode_obj["tahun"]
    hari_terakhir = 28 if bln == 2 else (30 if bln in [4, 6, 9, 11] else 31)

    with kol_tgl:
        tgl_penyesuaian = st.date_input(
            "Tanggal Penyesuaian",
            value=datetime.date(thn, bln, hari_terakhir),
            help="Biasanya tanggal terakhir periode",
            key=f"tgl_peny_{period_id}",
        )

    tanggal_str = str(tgl_penyesuaian)

    if periode_obj.get("status") == "tutup":
        st.warning("⚠️ Periode ini sudah ditutup. Tidak bisa menambah penyesuaian.")

    st.divider()

    # Tampilkan daftar penyesuaian yang sudah ada
    _tampilkan_daftar_penyesuaian(period_id)

    st.divider()

    if periode_obj["status"] == "buka":
        st.subheader("➕ Buat Penyesuaian Baru")

        # 2 Tabs penyesuaian
        tab_penyusutan, tab_upah = st.tabs([
            "🏭 Penyusutan Aset Tetap",
            "👷 Akrual Upah",
        ])

        with tab_penyusutan:
            _tab_penyusutan(period_id, tanggal_str)

        with tab_upah:
            _tab_akrual_upah(period_id, tanggal_str, akun_ids)


from services.permission_service import wajib_punya_izin
wajib_punya_izin("reports.manage")
tampilkan()
