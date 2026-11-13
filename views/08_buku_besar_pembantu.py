"""
views/08_buku_besar_pembantu.py
--------------------------------
Tujuan  : BB Pembantu: Piutang per pelanggan, Persediaan per item,
          Aset Tetap, dan Utang Usaha.
Input   : Tab yang dipilih user, filter per pelanggan / item.
Output  : 4 tab tampilan BB Pembantu sesuai jenis.
Dipanggil oleh : app.py (st.navigation)

KONSEP BB PEMBANTU:
  Buku Besar Pembantu (sub-ledger) adalah rincian dari akun kontrol di Buku Besar.
  - Tab Piutang → rincian akun 1201 (Piutang Usaha) per pelanggan
  - Tab Persediaan → rincian akun 1301-1307 per item (dari kartu persediaan)
  - Tab Aset Tetap → rincian akun 1401+ per unit aset (nilai buku saat ini)
  - Tab Utang Usaha → ringkasan dari akun 2101 per supplier/transaksi
"""

import streamlit as st
import pandas as pd
from datetime import date
from database.connection import get_connection
from services.subsidiary_service import (
    ambil_bb_piutang,
    ambil_ringkasan_piutang_per_pelanggan,
    ambil_bb_persediaan,
    ambil_bb_aset_tetap,
    ambil_bb_utang,
)
from utils.formatting import format_rupiah, format_tanggal, format_qty


@st.cache_data(ttl=30)
def _ambil_daftar_pelanggan() -> list[dict]:
    """Ambil semua pelanggan aktif dari database."""
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, nama FROM customers WHERE aktif = 1 ORDER BY nama"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=30)
def _ambil_daftar_items() -> list[dict]:
    """Ambil semua item persediaan dari database."""
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, kode_item, nama_item, satuan, tipe FROM items ORDER BY tipe, kode_item"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


# =============================================================================
# TAB 1 — BB PIUTANG
# =============================================================================

def _tampilkan_tab_piutang() -> None:
    """Tab BB Pembantu Piutang: ringkasan per pelanggan + detail per faktur."""
    st.subheader("🧾 Buku Besar Pembantu Piutang")
    st.caption("Rincian saldo piutang usaha per pelanggan (aging analysis).")

    # Ringkasan per pelanggan
    df_ringkasan = ambil_ringkasan_piutang_per_pelanggan()

    if df_ringkasan.empty:
        st.info("✅ Tidak ada piutang yang belum lunas.")
        return

    # Tampilkan total keseluruhan
    total_semua = int(df_ringkasan["total_piutang"].sum())
    total_faktur_jatuh_tempo = int(df_ringkasan["faktur_jatuh_tempo"].sum())

    kol_m1, kol_m2, kol_m3 = st.columns(3)
    with kol_m1:
        st.metric("💰 Total Piutang Beredar", format_rupiah(total_semua))
    with kol_m2:
        st.metric("👥 Jumlah Pelanggan", len(df_ringkasan))
    with kol_m3:
        st.metric(
            "⚠️ Faktur Jatuh Tempo",
            str(total_faktur_jatuh_tempo),
            delta=f"-{total_faktur_jatuh_tempo} perlu ditagih" if total_faktur_jatuh_tempo > 0 else None,
            delta_color="inverse"
        )

    st.divider()

    # Peringatan jika ada yang jatuh tempo
    if total_faktur_jatuh_tempo > 0:
        st.warning(
            f"⚠️ Terdapat **{total_faktur_jatuh_tempo} faktur** yang sudah melewati jatuh tempo! "
            "Segera lakukan penagihan."
        )

    # Tampilkan ringkasan per pelanggan dengan detail expandable
    st.markdown("#### Ringkasan per Pelanggan")

    for _, baris_ringkasan in df_ringkasan.iterrows():
        pelanggan_nama = baris_ringkasan["pelanggan"]
        total_piutang = int(baris_ringkasan["total_piutang"])
        jumlah_faktur = int(baris_ringkasan["jumlah_faktur"])
        jatuh_tempo_count = int(baris_ringkasan["faktur_jatuh_tempo"])

        # Label expander dengan status
        label_jt = f" ⚠️ {jatuh_tempo_count} jatuh tempo" if jatuh_tempo_count > 0 else ""
        label_expander = (
            f"**{pelanggan_nama}** — {format_rupiah(total_piutang)} "
            f"({jumlah_faktur} faktur aktif){label_jt}"
        )

        with st.expander(label_expander, expanded=(jatuh_tempo_count > 0)):
            # Detail per faktur untuk pelanggan ini
            customer_id = int(baris_ringkasan["customer_id"])
            df_detail = ambil_bb_piutang(customer_id=customer_id)

            if df_detail.empty:
                st.info("Tidak ada faktur aktif.")
                continue

            for _, faktur in df_detail.iterrows():
                sisa = int(faktur["sisa_piutang"])
                tgl_jt = faktur["tanggal_jatuh_tempo"]
                sudah_jatuh_tempo = (
                    tgl_jt is not None
                    and str(tgl_jt) < str(date.today())
                    and faktur["status"] != "lunas"
                )

                # Tampilkan setiap faktur
                kol_f1, kol_f2, kol_f3, kol_f4 = st.columns([2, 1, 1, 1])
                with kol_f1:
                    ikon_status = "🔴" if sudah_jatuh_tempo else "🟡"
                    st.markdown(f"{ikon_status} **{faktur['no_faktur']}**")
                    st.caption(f"Terbit: {format_tanggal(faktur['tanggal_faktur'])}")
                with kol_f2:
                    st.markdown(f"**Tagihan:** {format_rupiah(faktur['jumlah'])}")
                    st.caption(f"Dibayar: {format_rupiah(faktur['jumlah_terbayar'])}")
                with kol_f3:
                    st.markdown(f"**Sisa:** {format_rupiah(sisa)}")
                    umur = int(faktur.get("umur_hari", 0))
                    st.caption(f"Umur: {umur} hari")
                with kol_f4:
                    st.markdown(f"**Jatuh Tempo:**")
                    tgl_jt_fmt = format_tanggal(tgl_jt)
                    if sudah_jatuh_tempo:
                        st.caption(f"🔴 {tgl_jt_fmt} *(terlambat)*")
                    else:
                        st.caption(f"🟢 {tgl_jt_fmt}")

                st.markdown("---")


# =============================================================================
# TAB 2 — BB PERSEDIAAN
# =============================================================================

def _tampilkan_tab_persediaan() -> None:
    """Tab BB Pembantu Persediaan: kartu persediaan per item dengan format BB."""
    st.subheader("📦 Buku Besar Pembantu Persediaan")
    st.caption(
        "Rincian persediaan per item (sub-ledger dari akun 1301–1307). "
        "Metode penilaian: Rata-Rata Bergerak."
    )

    semua_items = _ambil_daftar_items()
    if not semua_items:
        st.warning("Belum ada item persediaan.")
        return

    # Dropdown pilih item
    opsi_item = {
        f"{i['kode_item']} - {i['nama_item']} ({i['satuan']})": i
        for i in semua_items
    }

    item_dipilih_key = st.selectbox(
        "Pilih Item Persediaan",
        list(opsi_item.keys()),
        key="bb_persediaan_item",
    )
    item_dipilih = opsi_item[item_dipilih_key]
    item_id = item_dipilih["id"]
    satuan = item_dipilih["satuan"]

    # Ambil data BB persediaan
    df = ambil_bb_persediaan(item_id=item_id)

    if df.empty:
        st.info("Belum ada gerakan untuk item ini.")
        return

    # Metrik ringkasan saldo akhir
    baris_akhir = df.iloc[-1]
    kol_m1, kol_m2, kol_m3 = st.columns(3)
    with kol_m1:
        st.metric("📦 Saldo Qty", format_qty(float(baris_akhir["saldo_qty"]), satuan))
    with kol_m2:
        st.metric("💰 Saldo Nilai", format_rupiah(int(baris_akhir["saldo_nilai"])))
    with kol_m3:
        st.metric("📊 Harga Rata-rata", format_rupiah(int(baris_akhir["harga_rata2"])))

    st.divider()

    # Tampilkan tabel BB Pembantu format masuk/keluar
    df_tampil = df.copy()
    df_tampil["tanggal"] = df_tampil["tanggal"].apply(format_tanggal)

    # Format kolom qty
    for kol in ["masuk_qty", "keluar_qty", "saldo_qty"]:
        df_tampil[kol] = df_tampil[kol].apply(
            lambda q: format_qty(float(q), satuan) if q != 0 else "-"
        )

    # Format kolom nilai
    for kol in ["masuk_nilai", "keluar_nilai", "saldo_nilai", "harga_rata2"]:
        df_tampil[kol] = df_tampil[kol].apply(
            lambda x: format_rupiah(int(x)) if x != 0 else "-"
        )

    df_tampil = df_tampil.rename(columns={
        "tanggal": "Tanggal",
        "keterangan": "Keterangan",
        "masuk_qty": "Masuk Qty",
        "masuk_nilai": "Masuk Nilai",
        "keluar_qty": "Keluar Qty",
        "keluar_nilai": "Keluar Nilai",
        "saldo_qty": "Saldo Qty",
        "saldo_nilai": "Saldo Nilai",
        "harga_rata2": "Harga Rata-rata",
    })

    st.markdown(f"**Kartu Persediaan: {item_dipilih['nama_item']}**")
    st.dataframe(df_tampil, use_container_width=True, hide_index=True)


# =============================================================================
# TAB 3 — BB ASET TETAP
# =============================================================================

def _tampilkan_tab_aset_tetap() -> None:
    """Tab BB Pembantu Aset Tetap: daftar aset + akumulasi penyusutan + nilai buku."""
    st.subheader("🏭 Buku Besar Pembantu Aset Tetap")
    st.caption(
        "Daftar aset tetap dengan nilai buku saat ini. "
        "Penyusutan metode garis lurus sejak tanggal perolehan."
    )

    df = ambil_bb_aset_tetap()

    if df.empty:
        st.warning("Belum ada data aset tetap.")
        return

    # Metrik ringkasan
    total_harga = int(df["harga_perolehan"].sum())
    total_akum = int(df["akumulasi_penyusutan"].sum())
    total_nilai_buku = int(df["nilai_buku"].sum())

    kol_m1, kol_m2, kol_m3 = st.columns(3)
    with kol_m1:
        st.metric("🏭 Total Harga Perolehan", format_rupiah(total_harga))
    with kol_m2:
        st.metric("📉 Total Akumulasi Penyusutan", format_rupiah(total_akum))
    with kol_m3:
        st.metric("💎 Total Nilai Buku", format_rupiah(total_nilai_buku))

    st.divider()

    # Tampilkan tabel
    df_tampil = df.copy()

    df_tampil["tanggal_perolehan"] = df_tampil["tanggal_perolehan"].apply(format_tanggal)
    df_tampil["harga_perolehan"] = df_tampil["harga_perolehan"].apply(format_rupiah)
    df_tampil["nilai_residu"] = df_tampil["nilai_residu"].apply(format_rupiah)

    # Kolom akumulasi penyusutan & nilai buku
    df_tampil["akumulasi_penyusutan"] = df_tampil.apply(
        lambda baris: "Tidak Disusutkan"
        if not baris["is_disusutkan"]
        else format_rupiah(int(baris["akumulasi_penyusutan"])),
        axis=1
    )
    df_tampil["nilai_buku"] = df_tampil["nilai_buku"].apply(format_rupiah)

    # Kolom umur ekonomis
    df_tampil["umur_ekonomis_tahun"] = df_tampil.apply(
        lambda baris: "Tidak Disusutkan"
        if not baris["is_disusutkan"]
        else f"{int(baris['umur_ekonomis_tahun'])} tahun",
        axis=1
    )

    # Hapus kolom is_disusutkan (hanya untuk logika internal)
    df_tampil = df_tampil.drop(columns=["is_disusutkan"])

    df_tampil = df_tampil.rename(columns={
        "kode_aset": "Kode",
        "nama_aset": "Nama Aset",
        "kategori_aset": "Kategori",
        "tanggal_perolehan": "Tgl. Perolehan",
        "harga_perolehan": "Harga Perolehan",
        "akumulasi_penyusutan": "Akum. Penyusutan",
        "nilai_buku": "Nilai Buku",
        "umur_ekonomis_tahun": "Umur Ekonomis",
        "nilai_residu": "Nilai Residu",
    })

    st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    st.info(
        "📌 **Catatan:** Tanah (AT-001) tidak disusutkan sesuai standar akuntansi. "
        "Akumulasi penyusutan dihitung sejak tanggal perolehan sampai hari ini."
    )


# =============================================================================
# TAB 4 — BB UTANG USAHA
# =============================================================================

def _tampilkan_tab_utang() -> None:
    """Tab BB Pembantu Utang Usaha: ringkasan dari jurnal pembelian kredit."""
    st.subheader("📋 Buku Besar Pembantu Utang Usaha")
    st.caption(
        "Ringkasan utang usaha dari jurnal pembelian kredit (akun 2101). "
        "Utang timbul saat pembelian tidak langsung dibayar tunai."
    )

    df = ambil_bb_utang()

    if df.empty:
        st.info(
            "✅ Tidak ada data utang usaha yang tercatat dari transaksi kredit.\n\n"
            "**Catatan:** Berdasarkan observasi operasional PT Sari Subur Langgeng Jaya, "
            "sebagian besar pembelian dilakukan secara **tunai** (cash), sehingga tidak "
            "menimbulkan utang usaha. Data akan muncul jika ada transaksi pembelian kredit."
        )
        return

    # Metrik ringkasan
    total_utang = int(df["total_utang"].sum())
    kol_m1, kol_m2 = st.columns(2)
    with kol_m1:
        st.metric("💳 Total Utang Usaha", format_rupiah(total_utang))
    with kol_m2:
        st.metric("🏭 Jumlah Supplier", len(df))

    st.divider()

    # Tampilkan tabel
    df_tampil = df.copy()
    df_tampil["total_utang"] = df_tampil["total_utang"].apply(format_rupiah)

    df_tampil = df_tampil.rename(columns={
        "supplier": "Supplier / Pihak",
        "total_utang": "Total Utang",
        "jumlah_transaksi": "Jumlah Transaksi",
    })

    st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    st.info(
        "⚠️ **Catatan:** Data ini menampilkan total kredit ke akun Utang Usaha (2101) "
        "dari seluruh jurnal. Belum memperhitungkan pembayaran utang yang sudah dilakukan. "
        "Implementasi penuh pada Fase 5 (Neraca Saldo)."
    )


# =============================================================================
# FUNGSI UTAMA
# =============================================================================

def tampilkan() -> None:
    """Fungsi utama halaman Buku Besar Pembantu."""
    st.title("🔖 Buku Besar Pembantu")
    st.caption(
        "Sub-ledger yang merinci saldo akun kontrol di Buku Besar. "
        "Terdiri dari 4 jenis: Piutang, Persediaan, Aset Tetap, dan Utang Usaha."
    )

    # 4 Tab BB Pembantu
    tab_piutang, tab_persediaan, tab_aset, tab_utang = st.tabs([
        "🧾 Piutang Usaha",
        "📦 Persediaan",
        "🏭 Aset Tetap",
        "📋 Utang Usaha",
    ])

    with tab_piutang:
        _tampilkan_tab_piutang()

    with tab_persediaan:
        _tampilkan_tab_persediaan()

    with tab_aset:
        _tampilkan_tab_aset_tetap()

    with tab_utang:
        _tampilkan_tab_utang()


# Panggil fungsi utama
tampilkan()
