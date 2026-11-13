"""
views/05_jurnal_khusus.py
--------------------------
Tujuan  : Menampilkan 4 Jurnal Khusus berformat kolom tradisional akuntansi.
          Setiap jurnal punya kolom khusus yang merangkum kelompok akun tertentu,
          bukan menampilkan setiap akun satu per satu seperti Jurnal Umum.
Input   : Pilihan periode dari user (selectbox filter).
Output  : Tabel kolom tradisional per jenis jurnal + total kolom di bawah.
Dipanggil oleh : app.py (st.navigation)

4 JURNAL KHUSUS (sesuai PROJECT_BRIEF):
  1. Sales Journal       : Penjualan tempo → Piutang (D) | Penjualan (K)
  2. Purchase Journal    : Pembelian kredit → Persediaan (D) | Utang Usaha (K)
  3. Cash Receipt Journal: Penerimaan kas → Kas (D) | Piutang (K) | Penjualan (K) | Lain-lain (K)
  4. Cash Payment Journal: Pengeluaran kas → Kas (K) | Persediaan (D) | Upah (D) | Beban Ops (D) | Lain-lain (D)

CATATAN AKUNTANSI:
  Jurnal Khusus hanyalah TAMPILAN FORMAT KOLOM dari journal_entries.
  Data aslinya tetap satu tabel (journal_entries + journal_lines).
  Ref "✓" berarti sudah otomatis diposting ke buku besar oleh sistem.
"""

import streamlit as st
import pandas as pd
import streamlit_antd_components as sac
from database.connection import get_connection
from services.special_journal_service import (
    ambil_jurnal_penjualan,
    ambil_jurnal_pembelian,
    ambil_jurnal_penerimaan_kas,
    ambil_jurnal_pengeluaran_kas,
    hitung_total_kolom,
)
from utils.formatting import format_rupiah, format_tanggal
from utils.ui_components import divider_dengan_judul, selector_periode
from theme import WARNA_PRIMER


# ================================================================
# HELPER: Ambil periode
# ================================================================

@st.cache_data(ttl=60)
def _ambil_periode():
    """Ambil semua periode dari database untuk filter dropdown."""
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, nama_bulan AS label, status FROM periods ORDER BY tahun DESC, bulan DESC"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


# ================================================================
# HELPER: Format tabel + total
# ================================================================

def _format_rupiah_kolom(df: pd.DataFrame, kolom_angka: list[str]) -> pd.DataFrame:
    """
    Format kolom angka menjadi string Rupiah untuk tampilan.
    Nilai 0 ditampilkan sebagai '-' agar tabel lebih mudah dibaca.

    PENTING: Hitung total SEBELUM memanggil fungsi ini.
    """
    df = df.copy()
    for col in kolom_angka:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: format_rupiah(int(x)) if int(x) > 0 else "-"
            )
    return df


def _tampilkan_total_kolom(
    total: dict,
    label_map: dict[str, str],
    warna: str = WARNA_PRIMER,
) -> None:
    """
    Menampilkan baris total kolom dalam bentuk metrik horizontal.

    Args:
        total     : Dict {nama_kolom_internal: nilai_integer}.
        label_map : Dict {nama_kolom_internal: label_tampilan}.
    """
    sac.divider(label="Total Kolom", icon="sigma", align="center", color=warna)
    cols = st.columns(len(total))
    for i, (col_key, nilai) in enumerate(total.items()):
        label = label_map.get(col_key, col_key)
        with cols[i]:
            st.metric(label=label, value=format_rupiah(nilai))


def _tampilkan_pesan_kosong(jenis: str) -> None:
    """Tampilkan pesan informatif jika tidak ada data untuk jurnal ini."""
    st.info(
        f"Tidak ada transaksi **{jenis}** pada periode yang dipilih.\n\n"
        "Gunakan menu **Input Transaksi** untuk mencatat transaksi baru."
    )


# ================================================================
# TAB 1: SALES JOURNAL (JURNAL PENJUALAN TEMPO)
# ================================================================

def _tampilkan_jurnal_penjualan(period_id: int | None) -> None:
    """
    Menampilkan Sales Journal (Jurnal Penjualan Tempo) dalam format kolom tradisional.

    Format: Tanggal | No Faktur | Pelanggan | Jatuh Tempo | Ref | Piutang (D) | Penjualan (K)

    Setiap baris = 1 transaksi penjualan tempo.
    Total kolom ditampilkan di bawah tabel.
    """
    st.subheader("📋 Sales Journal — Jurnal Penjualan Tempo")
    st.caption(
        "Mencatat penjualan tempo dan pencatatan perpetualnya: Piutang (D) / Penjualan (K), "
        "serta HPP Penjualan (D) / Persediaan Cabai (K)."
    )

    df = ambil_jurnal_penjualan(period_id)

    if df.empty:
        _tampilkan_pesan_kosong("Penjualan Tempo")
        return

    # Kolom angka untuk dihitung totalnya
    kolom_angka = ["piutang_d", "penjualan_k", "hpp_d", "persediaan_k"]
    total = hitung_total_kolom(df, kolom_angka)

    # Tambah kolom Ref (sudah diposting otomatis)
    df["ref"] = "✓"

    # Format tanggal
    df["tanggal"] = df["tanggal"].apply(format_tanggal)
    df["jatuh_tempo"] = df["jatuh_tempo"].apply(
        lambda x: format_tanggal(x) if x != "-" else "-"
    )

    # Format angka sebagai Rupiah (setelah hitung total)
    df = _format_rupiah_kolom(df, kolom_angka)

    # Rename kolom untuk tampilan
    df_tampil = df.rename(columns={
        "tanggal": "Tanggal",
        "no_faktur": "No. Faktur",
        "pelanggan": "Pelanggan",
        "jatuh_tempo": "Jatuh Tempo",
        "ref": "Ref",
        "piutang_d": "Piutang Usaha (D)",
        "penjualan_k": "Penjualan (K)",
        "hpp_d": "HPP Penjualan (D)",
        "persediaan_k": "Persediaan Cabai (K)",
    })

    kolom_tampil = [
        "Tanggal", "No. Faktur", "Pelanggan", "Jatuh Tempo",
        "Ref", "Piutang Usaha (D)", "Penjualan (K)",
        "HPP Penjualan (D)", "Persediaan Cabai (K)",
    ]

    st.dataframe(
        df_tampil[kolom_tampil],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pelanggan": st.column_config.TextColumn(width="medium"),
            "Keterangan": st.column_config.TextColumn(width="large"),
            "Piutang Usaha (D)": st.column_config.TextColumn(width="medium"),
            "Penjualan (K)": st.column_config.TextColumn(width="medium"),
            "Ref": st.column_config.TextColumn(width="small"),
        },
    )

    st.caption(f"Total {len(df)} transaksi penjualan tempo.")

    # Tampilkan total kolom
    _tampilkan_total_kolom(
        total=total,
        label_map={
            "piutang_d": "Total Piutang (D)",
            "penjualan_k": "Total Penjualan (K)",
            "hpp_d": "Total HPP Penjualan (D)",
            "persediaan_k": "Total Persediaan Cabai (K)",
        },
    )

    # Validasi kedua pasangan: Piutang = Penjualan dan HPP = Persediaan.
    pasangan_penjualan_seimbang = total["piutang_d"] == total["penjualan_k"]
    pasangan_hpp_seimbang = total["hpp_d"] == total["persediaan_k"]
    if pasangan_penjualan_seimbang and pasangan_hpp_seimbang:
        sac.alert(
            label="Jurnal Seimbang ✅",
            description=(
                f"Piutang = Penjualan = {format_rupiah(total['piutang_d'])}; "
                f"HPP = Persediaan = {format_rupiah(total['hpp_d'])}"
            ),
            color="success", icon=True,
        )
    else:
        sac.alert(
            label="Peringatan: Kolom Tidak Seimbang",
            description=(
                f"Piutang (D): {format_rupiah(total['piutang_d'])} | "
                f"Penjualan (K): {format_rupiah(total['penjualan_k'])} | "
                f"HPP (D): {format_rupiah(total['hpp_d'])} | "
                f"Persediaan (K): {format_rupiah(total['persediaan_k'])}"
            ),
            color="warning", icon=True,
        )


# ================================================================
# TAB 2: PURCHASE JOURNAL (JURNAL PEMBELIAN KREDIT)
# ================================================================

def _tampilkan_jurnal_pembelian(period_id: int | None) -> None:
    """
    Menampilkan Purchase Journal (Jurnal Pembelian Kredit) dalam format kolom tradisional.

    Format: Tanggal | No Faktur | Supplier | Ref | Persediaan (D) | Utang Usaha (K)

    CATATAN: Dari observasi lapangan PT Sari Subur Langgeng Jaya Hidroponik Farm,
    semua pembelian dilakukan TUNAI. Jurnal ini berisi data simulasi saja.
    """
    st.subheader("📋 Purchase Journal — Jurnal Pembelian Kredit")
    st.caption(
        "Mencatat pembelian bahan dengan pembayaran ditangguhkan (utang dagang). "
        "Debit ke Persediaan, Kredit ke Utang Usaha."
    )

    # Catatan khusus tentang kondisi riil usaha
    sac.alert(
        label="Catatan Observasi Lapangan",
        description=(
            "Berdasarkan wawancara dengan Bapak Hanif Margan Asparingga (Agronomist Utama), "
            "seluruh pembelian PT Sari Subur dilakukan TUNAI di Toko Sido Panen Bandungan. "
            "Jurnal Pembelian ini berisi data simulasi untuk keperluan kelengkapan sistem."
        ),
        color="info", icon=True,
    )

    df = ambil_jurnal_pembelian(period_id)

    if df.empty:
        _tampilkan_pesan_kosong("Pembelian Kredit")
        return

    kolom_angka = ["persediaan_d", "utang_k"]
    total = hitung_total_kolom(df, kolom_angka)

    df["ref"] = "✓"
    df["tanggal"] = df["tanggal"].apply(format_tanggal)
    df = _format_rupiah_kolom(df, kolom_angka)

    df_tampil = df.rename(columns={
        "tanggal": "Tanggal",
        "no_faktur": "No. Faktur",
        "supplier": "Supplier",
        "ref": "Ref",
        "persediaan_d": "Persediaan (D)",
        "utang_k": "Utang Usaha (K)",
    })

    kolom_tampil = [
        "Tanggal", "No. Faktur", "Supplier",
        "Ref", "Persediaan (D)", "Utang Usaha (K)",
    ]

    st.dataframe(
        df_tampil[kolom_tampil],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Persediaan (D)": st.column_config.TextColumn(width="medium"),
            "Utang Usaha (K)": st.column_config.TextColumn(width="medium"),
            "Ref": st.column_config.TextColumn(width="small"),
        },
    )

    st.caption(f"Total {len(df)} transaksi pembelian kredit.")

    _tampilkan_total_kolom(
        total=total,
        label_map={
            "persediaan_d": "Total Persediaan (D)",
            "utang_k": "Total Utang Usaha (K)",
        },
    )

    if total["persediaan_d"] == total["utang_k"]:
        sac.alert(
            label="Jurnal Seimbang ✅",
            description=f"Total Persediaan = Total Utang = {format_rupiah(total['persediaan_d'])}",
            color="success", icon=True,
        )


# ================================================================
# TAB 3: CASH RECEIPT JOURNAL (JURNAL PENERIMAAN KAS)
# ================================================================

def _tampilkan_jurnal_penerimaan_kas(period_id: int | None) -> None:
    """
    Menampilkan Cash Receipt Journal (Jurnal Penerimaan Kas) dalam format kolom tradisional.

    Format: Tanggal | No Bukti | Keterangan | Ref | Kas (D) | Piutang (K) | Penjualan (K) | Lain-lain (K)

    Kolom Kas (D) = total uang masuk per transaksi.
    Kolom kredit menjelaskan DARI MANA uang itu berasal.
    Validasi: Kas (D) harus = Piutang (K) + Penjualan (K) + Lain-lain (K)
    """
    st.subheader("📋 Cash Receipt Journal — Jurnal Penerimaan Kas")
    st.caption(
        "Mencatat semua penerimaan uang kas. "
        "Kolom kredit menunjukkan asal kas: dari penjualan tunai, pelunasan piutang, atau lain-lain."
    )

    df = ambil_jurnal_penerimaan_kas(period_id)

    if df.empty:
        _tampilkan_pesan_kosong("Penerimaan Kas")
        return

    kolom_angka = ["kas_d", "piutang_k", "penjualan_k", "lain_lain_k", "hpp_d", "persediaan_k"]
    total = hitung_total_kolom(df, kolom_angka)

    df["ref"] = "✓"
    df["tanggal"] = df["tanggal"].apply(format_tanggal)
    df = _format_rupiah_kolom(df, kolom_angka)

    df_tampil = df.rename(columns={
        "tanggal": "Tanggal",
        "no_bukti": "No. Bukti",
        "keterangan": "Keterangan",
        "pihak_terkait": "Pihak Terkait",
        "ref": "Ref",
        "kas_d": "Kas (D)",
        "piutang_k": "Piutang (K)",
        "penjualan_k": "Penjualan (K)",
        "lain_lain_k": "Lain-lain (K)",
        "hpp_d": "HPP Penjualan (D)",
        "persediaan_k": "Persediaan Cabai (K)",
    })

    kolom_tampil = [
        "Tanggal", "No. Bukti", "Keterangan", "Pihak Terkait",
        "Ref", "Kas (D)", "Piutang (K)", "Penjualan (K)", "Lain-lain (K)",
        "HPP Penjualan (D)", "Persediaan Cabai (K)",
    ]

    st.dataframe(
        df_tampil[kolom_tampil],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Keterangan": st.column_config.TextColumn(width="large"),
            "Kas (D)": st.column_config.TextColumn(width="medium"),
            "Piutang (K)": st.column_config.TextColumn(width="medium"),
            "Penjualan (K)": st.column_config.TextColumn(width="medium"),
            "Lain-lain (K)": st.column_config.TextColumn(width="medium"),
            "Ref": st.column_config.TextColumn(width="small"),
        },
    )

    st.caption(f"Total {len(df)} transaksi penerimaan kas.")

    _tampilkan_total_kolom(
        total=total,
        label_map={
            "kas_d": "Total Kas (D)",
            "piutang_k": "Piutang (K)",
            "penjualan_k": "Penjualan (K)",
            "lain_lain_k": "Lain-lain (K)",
            "hpp_d": "HPP Penjualan (D)",
            "persediaan_k": "Persediaan Cabai (K)",
        },
    )

    # HPP dan pengurangan persediaan merupakan jurnal perpetual pendamping,
    # bukan komponen yang membentuk penerimaan kas.
    # Validasi penerimaan kas tetap: kas_d == piutang_k + penjualan_k + lain_lain_k
    total_kredit = total["piutang_k"] + total["penjualan_k"] + total["lain_lain_k"]
    if total["kas_d"] == total_kredit:
        sac.alert(
            label="Jurnal Seimbang ✅",
            description=(
                f"Total Kas (D) = Total Kredit = {format_rupiah(total['kas_d'])}\n"
                f"[Piutang: {format_rupiah(total['piutang_k'])} + "
                f"Penjualan: {format_rupiah(total['penjualan_k'])} + "
                f"Lain-lain: {format_rupiah(total['lain_lain_k'])}]"
            ),
            color="success", icon=True,
        )
    else:
        sac.alert(
            label="Peringatan: Total Tidak Seimbang",
            description=(
                f"Kas (D): {format_rupiah(total['kas_d'])} ≠ "
                f"Total Kredit: {format_rupiah(total_kredit)}"
            ),
            color="warning", icon=True,
        )


# ================================================================
# TAB 4: CASH PAYMENT JOURNAL (JURNAL PENGELUARAN KAS)
# ================================================================

def _tampilkan_jurnal_pengeluaran_kas(period_id: int | None) -> None:
    """
    Menampilkan Cash Payment Journal (Jurnal Pengeluaran Kas) dalam format kolom tradisional.

    Format:
      Tanggal | No Bukti | Keterangan | Ref |
      Kas (K) | Persediaan (D) | Beban Upah (D) | Beban Produksi (D) | Beban Ops (D) | Lain-lain (D)

    Kolom Kas (K) = total uang keluar per transaksi.
    Kolom debit menjelaskan UNTUK APA uang dikeluarkan.
    Validasi: Kas (K) == sum semua kolom debit.
    """
    st.subheader("📋 Cash Payment Journal — Jurnal Pengeluaran Kas")
    st.caption(
        "Mencatat semua pengeluaran kas. "
        "Kolom debit menunjukkan tujuan pengeluaran: bahan, upah, beban operasional, dll."
    )

    df = ambil_jurnal_pengeluaran_kas(period_id)

    if df.empty:
        _tampilkan_pesan_kosong("Pengeluaran Kas")
        return

    kolom_angka = ["kas_k", "persediaan_d", "beban_upah_d", "beban_produksi_d", "beban_ops_d", "lain_lain_d"]
    total = hitung_total_kolom(df, kolom_angka)

    df["ref"] = "✓"
    df["tanggal"] = df["tanggal"].apply(format_tanggal)
    df = _format_rupiah_kolom(df, kolom_angka)

    df_tampil = df.rename(columns={
        "tanggal": "Tanggal",
        "no_bukti": "No. Bukti",
        "keterangan": "Keterangan",
        "pihak_terkait": "Pihak Terkait",
        "ref": "Ref",
        "kas_k": "Kas (K)",
        "persediaan_d": "Persediaan (D)",
        "beban_upah_d": "Beban Upah (D)",
        "beban_produksi_d": "Beban Prod. (D)",
        "beban_ops_d": "Beban Ops (D)",
        "lain_lain_d": "Lain-lain (D)",
    })

    kolom_tampil = [
        "Tanggal", "No. Bukti", "Keterangan", "Pihak Terkait", "Ref",
        "Kas (K)", "Persediaan (D)", "Beban Upah (D)",
        "Beban Prod. (D)", "Beban Ops (D)", "Lain-lain (D)",
    ]

    st.dataframe(
        df_tampil[kolom_tampil],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Keterangan": st.column_config.TextColumn(width="large"),
            "Kas (K)": st.column_config.TextColumn(width="medium"),
            "Persediaan (D)": st.column_config.TextColumn(width="medium"),
            "Beban Upah (D)": st.column_config.TextColumn(width="medium"),
            "Beban Prod. (D)": st.column_config.TextColumn(width="medium"),
            "Beban Ops (D)": st.column_config.TextColumn(width="medium"),
            "Lain-lain (D)": st.column_config.TextColumn(width="medium"),
            "Ref": st.column_config.TextColumn(width="small"),
        },
    )

    st.caption(f"Total {len(df)} transaksi pengeluaran kas.")

    _tampilkan_total_kolom(
        total=total,
        label_map={
            "kas_k": "Total Kas (K)",
            "persediaan_d": "Persediaan (D)",
            "beban_upah_d": "Beban Upah (D)",
            "beban_produksi_d": "Beban Prod. (D)",
            "beban_ops_d": "Beban Ops (D)",
            "lain_lain_d": "Lain-lain (D)",
        },
    )

    # Validasi: Kas (K) == sum semua debit
    total_debit = (
        total["persediaan_d"]
        + total["beban_upah_d"]
        + total["beban_produksi_d"]
        + total["beban_ops_d"]
        + total["lain_lain_d"]
    )
    if total["kas_k"] == total_debit:
        sac.alert(
            label="Jurnal Seimbang ✅",
            description=(
                f"Total Kas (K) = Total Debit = {format_rupiah(total['kas_k'])}\n"
                f"[Persediaan: {format_rupiah(total['persediaan_d'])} + "
                f"Upah: {format_rupiah(total['beban_upah_d'])} + "
                f"Prod: {format_rupiah(total['beban_produksi_d'])} + "
                f"Ops: {format_rupiah(total['beban_ops_d'])} + "
                f"Lain: {format_rupiah(total['lain_lain_d'])}]"
            ),
            color="success", icon=True,
        )
    else:
        sac.alert(
            label="Peringatan: Total Tidak Seimbang",
            description=(
                f"Kas (K): {format_rupiah(total['kas_k'])} ≠ "
                f"Total Debit: {format_rupiah(total_debit)}"
            ),
            color="warning", icon=True,
        )


# ================================================================
# HALAMAN UTAMA
# ================================================================

def tampilkan() -> None:
    """
    Fungsi utama halaman Jurnal Khusus.
    Dipanggil oleh app.py.
    """
    st.title("📚 Jurnal Khusus")
    st.caption(
        "4 Jurnal Khusus berformat kolom tradisional. "
        "Data bersumber dari satu tabel `journal_entries` yang difilter dan dipivot."
    )

    # ---- Penjelasan singkat ----
    with st.expander("ℹ️ Apa itu Jurnal Khusus?", expanded=False):
        st.markdown("""
        **Jurnal Khusus** adalah cara menyajikan jurnal dalam format kolom tradisional
        yang dikelompokkan per jenis transaksi. Berbeda dengan **Jurnal Umum** yang
        menampilkan setiap akun satu baris, Jurnal Khusus merangkum dalam kolom:

        | Jurnal | Jenis Transaksi | Format Kolom |
        |--------|-----------------|--------------|
        | Sales Journal | Penjualan Tempo | Piutang (D) / Penjualan (K) |
        | Purchase Journal | Pembelian Kredit | Persediaan (D) / Utang (K) |
        | Cash Receipt | Penerimaan Kas | Kas (D) / Piutang (K) / Penjualan (K) / Lain (K) |
        | Cash Payment | Pengeluaran Kas | Kas (K) / Persediaan (D) / Upah (D) / Ops (D) / Lain (D) |

        **Ref "✓"** berarti entri sudah diposting otomatis ke Buku Besar oleh sistem.
        """)

    # ---- Filter periode ----
    st.divider()
    kol_filter, _ = st.columns([2, 2])
    with kol_filter:
        period_id_filter = selector_periode(
            label="Filter Periode Jurnal Khusus",
            key="jurnal_khusus_periode",
            hanya_buka=False,
            izinkan_semua=True,
            tampilkan_kalender=True,
        )

    st.divider()

    # ---- 4 Tab Jurnal Khusus ----
    tab_dipilih = sac.tabs(
        items=[
            sac.TabsItem(label="Jurnal Penjualan", icon="cart-check"),
            sac.TabsItem(label="Jurnal Pembelian", icon="cart-plus"),
            sac.TabsItem(label="Penerimaan Kas", icon="cash-coin"),
            sac.TabsItem(label="Pengeluaran Kas", icon="cash-stack"),
        ],
        color=WARNA_PRIMER,
        return_index=False,
        key="tab_jurnal_khusus",
    )

    st.divider()

    # ---- Konten per tab ----
    if tab_dipilih == "Jurnal Penjualan":
        _tampilkan_jurnal_penjualan(period_id_filter)

    elif tab_dipilih == "Jurnal Pembelian":
        _tampilkan_jurnal_pembelian(period_id_filter)

    elif tab_dipilih == "Penerimaan Kas":
        _tampilkan_jurnal_penerimaan_kas(period_id_filter)

    elif tab_dipilih == "Pengeluaran Kas":
        _tampilkan_jurnal_pengeluaran_kas(period_id_filter)


# Panggil fungsi utama
tampilkan()
