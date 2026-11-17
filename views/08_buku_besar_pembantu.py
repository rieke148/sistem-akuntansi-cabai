"""
views/08_buku_besar_pembantu.py
--------------------------------
Tujuan  : BB Pembantu: Piutang Usaha per pelanggan dan Utang Usaha per supplier.
Input   : Tab yang dipilih user.
Output  : 2 tab Buku Besar Pembantu: Piutang Usaha dan Utang Usaha.
Dipanggil oleh : app.py (st.navigation)

KONSEP BB PEMBANTU:
  Buku Besar Pembantu (sub-ledger) adalah rincian dari akun kontrol di Buku Besar.
  - Tab Piutang → rincian akun 1120 (Piutang Usaha) per pelanggan
  - Tab Utang Usaha → rincian akun 2110 (Utang Usaha) per supplier/transaksi
"""

import streamlit as st
from datetime import date
from services.subsidiary_service import (
    ambil_bb_piutang,
    ambil_ringkasan_piutang_per_pelanggan,
    ambil_bb_utang,
)
from utils.formatting import format_rupiah, format_tanggal


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
# TAB 2 — BB UTANG USAHA
# =============================================================================


def _tampilkan_tab_utang() -> None:
    """Tab BB Pembantu Utang Usaha: ringkasan dari jurnal pembelian kredit."""
    st.subheader("📋 Buku Besar Pembantu Utang Usaha")
    st.caption(
        "Ringkasan utang usaha dari jurnal pembelian kredit (akun 2110). "
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
        "⚠️ **Catatan:** Data ini menampilkan total kredit ke akun Utang Usaha (2110) "
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
        "Terdiri dari Piutang Usaha per pelanggan dan Utang Usaha per supplier."
    )

    # 2 Tab BB Pembantu
    tab_piutang, tab_utang = st.tabs([
        "🧾 Piutang Usaha",
        "📋 Utang Usaha",
    ])

    with tab_piutang:
        _tampilkan_tab_piutang()

    with tab_utang:
        _tampilkan_tab_utang()


from services.permission_service import wajib_punya_izin
wajib_punya_izin("ledger.view")
tampilkan()
