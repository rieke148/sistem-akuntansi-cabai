"""
views/06_kartu_persediaan.py
-----------------------------
Tujuan  : Menampilkan Kartu Persediaan per item (rata-rata bergerak).
          Menunjukkan riwayat gerakan masuk/keluar dan saldo persediaan.
Input   : Pilihan item dari dropdown, filter tipe item.
Output  : Tabel kartu persediaan + metrik ringkasan + grafik saldo.
Dipanggil oleh : app.py (st.navigation)

KONSEP KARTU PERSEDIAAN:
  Metode rata-rata bergerak: setiap kali bahan masuk, harga rata-rata dihitung ulang.
  Kartu ini menunjukkan setiap gerakan beserta saldo kumulatif.
"""

import streamlit as st
import pandas as pd
from database.connection import get_connection
from services.inventory_service import ambil_kartu_persediaan, ambil_saldo_persediaan
from utils.formatting import format_rupiah, format_tanggal, format_qty


@st.cache_data(ttl=30)
def _ambil_daftar_items() -> list[dict]:
    """Ambil semua item persediaan dari database."""
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, kode_item, nama_item, satuan, tipe FROM items ORDER BY tipe, kode_item"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


def _tampilkan_ringkasan_saldo(item_id: int, satuan: str) -> None:
    """Tampilkan metrik ringkasan saldo persediaan item yang dipilih."""
    saldo = ambil_saldo_persediaan(item_id)

    kol1, kol2, kol3 = st.columns(3)
    with kol1:
        st.metric(
            label="📦 Saldo Kuantitas",
            value=format_qty(saldo["saldo_qty"], satuan),
            help="Jumlah stok persediaan saat ini"
        )
    with kol2:
        st.metric(
            label="💰 Saldo Nilai",
            value=format_rupiah(saldo["saldo_nilai"]),
            help="Nilai total persediaan saat ini"
        )
    with kol3:
        st.metric(
            label="📊 Harga Rata-rata",
            value=format_rupiah(saldo["harga_rata2"]),
            help="Harga rata-rata bergerak per satuan saat ini"
        )


def _tampilkan_tabel_kartu(df: pd.DataFrame, satuan: str) -> None:
    """Tampilkan tabel kartu persediaan dengan format yang rapi."""
    if df.empty:
        st.info("Belum ada gerakan untuk item ini. Lakukan transaksi pembelian bahan atau panen terlebih dahulu.")
        return

    # Format tampilan tabel
    df_tampil = df.copy()

    # Format tanggal
    df_tampil["tanggal"] = df_tampil["tanggal"].apply(format_tanggal)

    # Format tipe gerakan
    df_tampil["tipe_gerakan"] = df_tampil["tipe_gerakan"].map({
        "saldo_awal": "⚖ Saldo Awal",
        "masuk": "⬆ Masuk",
        "keluar": "⬇ Keluar",
    }).fillna(df_tampil["tipe_gerakan"])

    # Format angka uang
    for kol in ["harga_satuan", "total_nilai", "saldo_nilai", "harga_rata2"]:
        if kol in df_tampil.columns:
            df_tampil[kol] = df_tampil[kol].apply(format_rupiah)

    # Format qty
    for kol in ["qty", "saldo_qty"]:
        if kol in df_tampil.columns:
            df_tampil[kol] = df_tampil[kol].apply(
                lambda q: format_qty(q, satuan) if pd.notna(q) else "-"
            )

    # Rename kolom untuk tampilan
    df_tampil = df_tampil.rename(columns={
        "tanggal": "Tanggal",
        "tipe_gerakan": "Tipe",
        "qty": "Qty",
        "harga_satuan": "Harga Satuan",
        "total_nilai": "Total Nilai",
        "saldo_qty": "Saldo Qty",
        "saldo_nilai": "Saldo Nilai",
        "harga_rata2": "Harga Rata-rata",
        "keterangan": "Keterangan",
    })

    st.dataframe(df_tampil, use_container_width=True, hide_index=True)


def _tampilkan_grafik_saldo(df: pd.DataFrame, satuan: str) -> None:
    """Tampilkan grafik saldo kuantitas persediaan dari waktu ke waktu."""
    if df.empty or len(df) < 2:
        return

    # Siapkan data grafik
    df_grafik = df[["tanggal", "saldo_qty", "saldo_nilai"]].copy()
    df_grafik["tanggal"] = pd.to_datetime(df_grafik["tanggal"], errors="coerce")
    df_grafik = df_grafik.dropna(subset=["tanggal"])
    df_grafik = df_grafik.sort_values("tanggal")

    if df_grafik.empty:
        return

    st.subheader("📈 Grafik Saldo Kuantitas")
    st.area_chart(
        df_grafik.set_index("tanggal")[["saldo_qty"]],
        use_container_width=True,
    )

    st.subheader("💹 Grafik Saldo Nilai")
    st.line_chart(
        df_grafik.set_index("tanggal")[["saldo_nilai"]],
        use_container_width=True,
    )


def tampilkan() -> None:
    """Fungsi utama halaman Kartu Persediaan."""
    st.title("📦 Kartu Persediaan")
    st.caption(
        "Persediaan dicatat dengan sistem perpetual dan metode rata-rata bergerak. "
        "Setiap pembelian, pemakaian, panen, dan penjualan langsung memperbarui saldo stok."
    )

    # Ambil data semua item
    semua_items = _ambil_daftar_items()

    if not semua_items:
        st.warning("⚠️ Belum ada item persediaan. Tambahkan item di halaman Master Data → Persediaan.")
        return

    # Filter berdasarkan tipe item
    tipe_pilihan = st.radio(
        "Filter Tipe Item",
        ["Semua", "Bahan Produksi", "Hasil Panen"],
        horizontal=True,
        key="filter_tipe_kartu",
    )

    tipe_map = {
        "Semua": None,
        "Bahan Produksi": "bahan",
        "Hasil Panen": "hasil_panen",
    }
    tipe_filter = tipe_map[tipe_pilihan]

    # Filter items berdasarkan tipe
    if tipe_filter:
        items_tampil = [i for i in semua_items if i["tipe"] == tipe_filter]
    else:
        items_tampil = semua_items

    if not items_tampil:
        st.info(f"Tidak ada item dengan tipe '{tipe_pilihan}'.")
        return

    # Dropdown pilih item
    opsi_item = {
        f"[{i['tipe'].upper()[:1]}] {i['kode_item']} - {i['nama_item']} ({i['satuan']})": i
        for i in items_tampil
    }

    item_dipilih_key = st.selectbox(
        "Pilih Item Persediaan",
        list(opsi_item.keys()),
        help="Pilih item untuk melihat kartu persediaannya"
    )
    item_dipilih = opsi_item[item_dipilih_key]
    item_id = item_dipilih["id"]
    satuan = item_dipilih["satuan"]

    st.divider()

    # Tampilkan ringkasan saldo
    st.subheader(f"📊 Saldo Terkini — {item_dipilih['nama_item']}")
    _tampilkan_ringkasan_saldo(item_id, satuan)

    st.divider()

    # Ambil data kartu persediaan
    df = ambil_kartu_persediaan(item_id)

    # Tampilkan tabel kartu persediaan
    st.subheader("📋 Kartu Persediaan (Riwayat Gerakan)")
    if not df.empty:
        st.caption(
            f"Total **{len(df)} gerakan** tercatat untuk item ini. "
            f"Metode pencatatan: **Perpetual** | Penilaian: **Rata-Rata Bergerak (Moving Average)**."
        )
    _tampilkan_tabel_kartu(df, satuan)

    # Grafik stok
    if not df.empty:
        st.divider()
        try:
            _tampilkan_grafik_saldo(df, satuan)
        except Exception as e:
            st.warning(f"Grafik tidak dapat ditampilkan: {e}")


# Panggil fungsi utama
tampilkan()
