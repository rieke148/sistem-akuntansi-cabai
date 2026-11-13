"""
views/12_laporan_keuangan.py
------------------------------
Tujuan  : Menampilkan 4 Laporan Keuangan:
          1. Laporan Laba Rugi
          2. Laporan Perubahan Ekuitas
          3. Neraca (Balance Sheet)
          4. Laporan Arus Kas (opsional)
Input   : Pilih periode.
Output  : Tabel per laporan di dalam 4 tab.
Dipanggil oleh : app.py (st.navigation)
"""

import streamlit as st
import pandas as pd
from database.connection import get_connection
from services.statements_service import (
    susun_laporan_laba_rugi,
    susun_laporan_perubahan_ekuitas,
    susun_neraca,
    susun_arus_kas,
)
from utils.formatting import format_rupiah
from utils.export import (
    export_dataframe_ke_excel,
    export_dataframe_ke_pdf,
    export_laporan_keuangan_ke_excel,
)
from utils.ui_components import selector_periode
import services.period_service as ps
import streamlit_antd_components as sac


# ---------------------------------------------------------------------------
# Fungsi pembantu (private)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def _ambil_semua_periode() -> list[dict]:
    """Mengambil semua periode."""
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            "SELECT id, tahun, bulan, nama_bulan AS label, status FROM periods ORDER BY tahun, bulan"
        ).fetchall()
    finally:
        koneksi.close()
    return [dict(r) for r in rows]


def _baris_rupiah(label: str, jumlah: int, indent: int = 0, bold: bool = False) -> None:
    """Menampilkan satu baris laporan dengan label dan jumlah rupiah (100% Python murni)."""
    prefix = "&emsp;" * indent if indent > 0 else ""
    jml_str = format_rupiah(jumlah)
    kol1, kol2 = st.columns([3, 1])
    with kol1:
        if bold:
            st.markdown(f"**{prefix}{label}**")
        else:
            st.markdown(f"{prefix}{label}")
    with kol2:
        if bold:
            st.markdown(f"**{jml_str}**")
        else:
            st.markdown(f"{jml_str}")


def _garis_tipis() -> None:
    """Menampilkan garis tipis pemisah antar baris menggunakan divider native."""
    st.divider()


def _tab_laba_rugi(period_id: int) -> None:
    """Menampilkan Laporan Laba Rugi."""
    with st.spinner("Menghitung Laba Rugi..."):
        data = susun_laporan_laba_rugi(period_id)

    st.subheader("PT Sari Subur Langgeng Jaya Hidroponik Farm")
    st.markdown("**Laporan Laba Rugi**")
    st.caption("Untuk periode yang berakhir pada akhir bulan terpilih")
    st.divider()

    # Pendapatan
    sac.divider(label="Pendapatan", align="left")
    for item in data["pendapatan"]:
        _baris_rupiah(item["nama_akun"], item["jumlah"], indent=1)
    _garis_tipis()
    _baris_rupiah("Total Pendapatan", data["total_pendapatan"])

    st.markdown("")

    # Beban Produksi
    sac.divider(label="Beban Produksi", align="left")
    for item in data["beban_produksi"]:
        _baris_rupiah(item["nama_akun"], item["jumlah"], indent=1)
    _garis_tipis()
    _baris_rupiah("Sub-total Beban Produksi", data["total_beban_produksi"])

    st.markdown("")

    # Beban Operasional
    sac.divider(label="Beban Operasional", align="left")
    for item in data["beban_operasional"]:
        _baris_rupiah(item["nama_akun"], item["jumlah"], indent=1)
    _garis_tipis()
    _baris_rupiah("Sub-total Beban Operasional", data["total_beban_operasional"])

    st.markdown("")
    _garis_tipis()
    _baris_rupiah("Total Beban", data["total_beban"])

    st.markdown("")
    st.markdown("---")

    # Laba / Rugi Bersih
    laba = data["laba_bersih"]
    label_laba = "LABA BERSIH" if laba >= 0 else "RUGI BERSIH"
    if laba >= 0:
        sac.alert(
            label=f"{label_laba}: {format_rupiah(laba)}",
            description="Pendapatan melebihi total beban.",
            color="success",
            icon=True,
        )
    else:
        sac.alert(
            label=f"{label_laba}: {format_rupiah(abs(laba))}",
            description="Beban melebihi pendapatan. Usahakan efisiensi biaya.",
            color="error",
            icon=True,
        )

    # Simpan ke session_state agar bisa dipakai tab lain
    st.session_state["laba_bersih_f6"] = laba
    return laba


def _tab_perubahan_ekuitas(period_id: int, laba_bersih: int) -> int:
    """Menampilkan Laporan Perubahan Ekuitas."""
    with st.spinner("Menghitung Perubahan Ekuitas..."):
        data = susun_laporan_perubahan_ekuitas(period_id, laba_bersih)

    st.subheader("PT Sari Subur Langgeng Jaya Hidroponik Farm")
    st.markdown("**Laporan Perubahan Ekuitas**")
    st.caption("Untuk periode yang berakhir pada akhir bulan terpilih")
    st.divider()

    for item in data["detail"]:
        is_total = item.get("is_total", False)
        is_subtotal = item.get("is_subtotal", False)
        jumlah = item["jumlah"]
        label = item["keterangan"]

        if is_total:
            st.markdown("---")
            _baris_rupiah(label, jumlah)
            sac.alert(
                label=f"Modal Akhir: {format_rupiah(jumlah)}",
                description="Modal akhir ini akan muncul di Neraca sisi ekuitas.",
                color="success" if jumlah >= 0 else "error",
                icon=True,
            )
        elif is_subtotal:
            _garis_tipis()
            _baris_rupiah(label, jumlah)
            st.markdown("")
        else:
            indent = 0 if "awal" in label.lower() or "total" in label.lower() else 1
            _baris_rupiah(label, jumlah, indent=indent)

    st.session_state["modal_akhir_f6"] = data["modal_akhir"]
    return data["modal_akhir"]


def _tab_neraca(period_id: int, modal_akhir: int) -> None:
    """Menampilkan Neraca (Balance Sheet)."""
    with st.spinner("Menghitung Neraca..."):
        data = susun_neraca(period_id, modal_akhir)

    st.subheader("PT Sari Subur Langgeng Jaya Hidroponik Farm")
    st.markdown("**Neraca**")
    st.caption("Per akhir bulan terpilih")
    st.divider()

    col_kiri, col_kanan = st.columns(2)

    # ---- Kolom Kiri: ASET ----
    with col_kiri:
        sac.divider(label="ASET", align="left")

        # Aset Lancar
        st.markdown("**Aset Lancar**")
        for item in data["aset_lancar"]:
            is_kontra = item.get("is_kontra", False)
            label = f"({item['nama_akun']})" if is_kontra else item["nama_akun"]
            jumlah = -item["jumlah"] if is_kontra else item["jumlah"]
            _baris_rupiah(label, jumlah, indent=1)
        _garis_tipis()
        _baris_rupiah("Total Aset Lancar", data["total_aset_lancar"])

        st.markdown("")

        # Aset Tetap
        st.markdown("**Aset Tetap**")
        for item in data["aset_tetap"]:
            is_kontra = item.get("is_kontra", False)
            label = f"  ({item['nama_akun']})" if is_kontra else item["nama_akun"]
            jumlah = -item["jumlah"] if is_kontra else item["jumlah"]
            _baris_rupiah(label, jumlah, indent=1)
        _garis_tipis()
        _baris_rupiah("Total Aset Tetap", data["total_aset_tetap"])

        st.markdown("---")
        _baris_rupiah("TOTAL ASET", data["total_aset"])

    # ---- Kolom Kanan: LIABILITAS + EKUITAS ----
    with col_kanan:
        sac.divider(label="LIABILITAS & EKUITAS", align="left")

        # Liabilitas Lancar
        st.markdown("**Liabilitas Lancar**")
        for item in data["liabilitas_lancar"]:
            _baris_rupiah(item["nama_akun"], item["jumlah"], indent=1)
        if data["liabilitas_lancar"]:
            _garis_tipis()
            total_lancar = sum(i["jumlah"] for i in data["liabilitas_lancar"])
            _baris_rupiah("Total Liabilitas Lancar", total_lancar)

        st.markdown("")

        # Liabilitas Jangka Panjang
        st.markdown("**Liabilitas Jangka Panjang**")
        for item in data["liabilitas_jangka_panjang"]:
            _baris_rupiah(item["nama_akun"], item["jumlah"], indent=1)
        if data["liabilitas_jangka_panjang"]:
            _garis_tipis()
            total_panjang = sum(i["jumlah"] for i in data["liabilitas_jangka_panjang"])
            _baris_rupiah("Total Liabilitas Jangka Panjang", total_panjang)

        _garis_tipis()
        _baris_rupiah("Total Liabilitas", data["total_liabilitas"])

        st.markdown("")

        # Ekuitas
        st.markdown("**Ekuitas**")
        for item in data["ekuitas"]:
            _baris_rupiah(item["nama_akun"], item["jumlah"], indent=1)
        _garis_tipis()
        _baris_rupiah("Total Ekuitas", data["total_ekuitas"])

        st.markdown("---")
        _baris_rupiah("TOTAL LIABILITAS + EKUITAS", data["total_liabilitas_ekuitas"])

    # Validasi
    st.divider()
    if data["seimbang"]:
        sac.alert(
            label=f"✓ Neraca Seimbang",
            description=(
                f"Total Aset = Total Liabilitas + Ekuitas = "
                f"{format_rupiah(data['total_aset'])}"
            ),
            color="success",
            icon=True,
        )
    else:
        sac.alert(
            label="⚠ Neraca Tidak Seimbang!",
            description=(
                f"Aset: {format_rupiah(data['total_aset'])} | "
                f"Liab+Ekuitas: {format_rupiah(data['total_liabilitas_ekuitas'])}\n"
                f"Selisih: {format_rupiah(abs(data['total_aset'] - data['total_liabilitas_ekuitas']))}"
            ),
            color="error",
            icon=True,
        )


def _tab_arus_kas(period_id: int) -> None:
    """Menampilkan Laporan Arus Kas (metode langsung)."""
    with st.spinner("Menghitung Arus Kas..."):
        data = susun_arus_kas(period_id)

    st.subheader("PT Sari Subur Langgeng Jaya Hidroponik Farm")
    st.markdown("**Laporan Arus Kas (Metode Langsung)**")
    st.caption("Untuk periode yang berakhir pada akhir bulan terpilih")
    st.divider()

    # Saldo awal
    _baris_rupiah("Saldo Kas Awal Periode", data["saldo_kas_awal"])
    st.markdown("")

    # Arus dari Aktivitas Operasi
    sac.divider(label="Aktivitas Operasi", align="left")
    for item in data["operasi"]["penerimaan"]:
        _baris_rupiah(f"Penerimaan: {item['keterangan']}", item["jumlah"], indent=1)
    for item in data["operasi"]["pengeluaran"]:
        _baris_rupiah(f"Pengeluaran: {item['keterangan']}", -item["jumlah"], indent=1)
    _garis_tipis()
    _baris_rupiah("Arus Kas Bersih dari Operasi", data["operasi"]["neto"])

    st.markdown("")

    # Arus dari Aktivitas Investasi
    sac.divider(label="Aktivitas Investasi", align="left")
    for item in data["investasi"]["penerimaan"]:
        _baris_rupiah(f"Penerimaan: {item['keterangan']}", item["jumlah"], indent=1)
    for item in data["investasi"]["pengeluaran"]:
        _baris_rupiah(f"Pengeluaran: {item['keterangan']}", -item["jumlah"], indent=1)
    if not data["investasi"]["penerimaan"] and not data["investasi"]["pengeluaran"]:
        st.caption("   Tidak ada aktivitas investasi periode ini.")
    _garis_tipis()
    _baris_rupiah("Arus Kas Bersih dari Investasi", data["investasi"]["neto"])

    st.markdown("")

    # Arus dari Aktivitas Pendanaan
    sac.divider(label="Aktivitas Pendanaan", align="left")
    for item in data["pendanaan"]["penerimaan"]:
        _baris_rupiah(f"Penerimaan: {item['keterangan']}", item["jumlah"], indent=1)
    for item in data["pendanaan"]["pengeluaran"]:
        _baris_rupiah(f"Pengeluaran: {item['keterangan']}", -item["jumlah"], indent=1)
    if not data["pendanaan"]["penerimaan"] and not data["pendanaan"]["pengeluaran"]:
        st.caption("   Tidak ada aktivitas pendanaan periode ini.")
    _garis_tipis()
    _baris_rupiah("Arus Kas Bersih dari Pendanaan", data["pendanaan"]["neto"])

    st.markdown("---")
    _baris_rupiah("Kenaikan/(Penurunan) Kas Bersih", data["kenaikan_penurunan_kas"])
    _baris_rupiah("Saldo Kas Akhir Periode", data["saldo_kas_akhir"])

    if data["saldo_kas_akhir"] >= 0:
        sac.alert(
            label=f"Saldo Kas Akhir: {format_rupiah(data['saldo_kas_akhir'])}",
            color="success", icon=True,
        )
    else:
        sac.alert(
            label=f"Saldo Kas Negatif: {format_rupiah(data['saldo_kas_akhir'])}",
            description="Periksa kembali data transaksi kas.",
            color="error", icon=True,
        )


# ---------------------------------------------------------------------------
# Fungsi export
# ---------------------------------------------------------------------------

def _ambil_neraca_saldo_df(period_id: int) -> pd.DataFrame:
    """Mengambil neraca saldo sebagai DataFrame untuk export."""
    conn = get_connection()
    sql = """
        SELECT a.kode_akun AS "Kode Akun",
               a.nama_akun AS "Nama Akun",
               a.kategori AS "Kategori",
               COALESCE(ob.saldo_debit, 0) + COALESCE(SUM(CASE WHEN jl.debit > 0 THEN jl.debit ELSE 0 END), 0) AS "Debit",
               COALESCE(ob.saldo_kredit, 0) + COALESCE(SUM(CASE WHEN jl.kredit > 0 THEN jl.kredit ELSE 0 END), 0) AS "Kredit"
        FROM accounts a
        LEFT JOIN opening_balances ob ON a.id = ob.account_id AND ob.period_id = ?
        LEFT JOIN journal_lines jl ON a.id = jl.account_id
        LEFT JOIN journal_entries je ON jl.journal_entry_id = je.id AND je.period_id = ?
        WHERE a.aktif = 1
        GROUP BY a.id, a.kode_akun, a.nama_akun, a.kategori, ob.saldo_debit, ob.saldo_kredit
        HAVING COALESCE(ob.saldo_debit, 0) + COALESCE(ob.saldo_kredit, 0)
             + COALESCE(SUM(COALESCE(jl.debit, 0)), 0) + COALESCE(SUM(COALESCE(jl.kredit, 0)), 0) > 0
        ORDER BY a.kode_akun
    """
    rows = conn.execute(sql, (period_id, period_id)).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["Debit"] = df["Debit"].astype(int)
    df["Kredit"] = df["Kredit"].astype(int)
    return df


def _ambil_laporan_lengkap_dict(period_id: int) -> dict[str, pd.DataFrame]:
    """Menyusun seluruh laporan keuangan ke dalam dict DataFrame untuk export multi-sheet."""
    lr = susun_laporan_laba_rugi(period_id)
    baris_lr = [
        {"Komponen": "PENDAPATAN", "Akun": "", "Jumlah (Rp)": ""},
    ]
    for it in lr["pendapatan"]:
        baris_lr.append({"Komponen": "Pendapatan", "Akun": it["nama_akun"], "Jumlah (Rp)": it["jumlah"]})
    baris_lr.append({"Komponen": "Total Pendapatan", "Akun": "", "Jumlah (Rp)": lr["total_pendapatan"]})

    baris_lr.append({"Komponen": "BEBAN PRODUKSI", "Akun": "", "Jumlah (Rp)": ""})
    for it in lr["beban_produksi"]:
        baris_lr.append({"Komponen": "Beban Produksi", "Akun": it["nama_akun"], "Jumlah (Rp)": it["jumlah"]})
    baris_lr.append({"Komponen": "Total Beban Produksi", "Akun": "", "Jumlah (Rp)": lr["total_beban_produksi"]})

    baris_lr.append({"Komponen": "BEBAN OPERASIONAL", "Akun": "", "Jumlah (Rp)": ""})
    for it in lr["beban_operasional"]:
        baris_lr.append({"Komponen": "Beban Operasional", "Akun": it["nama_akun"], "Jumlah (Rp)": it["jumlah"]})
    baris_lr.append({"Komponen": "Total Beban Operasional", "Akun": "", "Jumlah (Rp)": lr["total_beban_operasional"]})

    baris_lr.append({"Komponen": "TOTAL BEBAN", "Akun": "", "Jumlah (Rp)": lr["total_beban"]})
    baris_lr.append({"Komponen": "LABA BERSIH", "Akun": "", "Jumlah (Rp)": lr["laba_bersih"]})
    df_lr = pd.DataFrame(baris_lr)

    pe = susun_laporan_perubahan_ekuitas(period_id, lr["laba_bersih"])
    baris_pe = [{"Keterangan": it["keterangan"], "Jumlah (Rp)": it["jumlah"]} for it in pe["detail"]]
    df_pe = pd.DataFrame(baris_pe)

    neraca = susun_neraca(period_id, pe["modal_akhir"])
    baris_neraca = [
        {"Kategori": "ASET LANCAR", "Akun": "", "Jumlah (Rp)": ""},
    ]
    for it in neraca["aset_lancar"]:
        baris_neraca.append({"Kategori": "Aset Lancar", "Akun": it["nama_akun"], "Jumlah (Rp)": it["jumlah"]})
    baris_neraca.append({"Kategori": "Total Aset Lancar", "Akun": "", "Jumlah (Rp)": neraca["total_aset_lancar"]})

    baris_neraca.append({"Kategori": "ASET TETAP", "Akun": "", "Jumlah (Rp)": ""})
    for it in neraca["aset_tetap"]:
        baris_neraca.append({"Kategori": "Aset Tetap", "Akun": it["nama_akun"], "Jumlah (Rp)": it["jumlah"]})
    baris_neraca.append({"Kategori": "Total Aset Tetap", "Akun": "", "Jumlah (Rp)": neraca["total_aset_tetap"]})
    baris_neraca.append({"Kategori": "TOTAL ASET", "Akun": "", "Jumlah (Rp)": neraca["total_aset"]})

    baris_neraca.append({"Kategori": "LIABILITAS", "Akun": "", "Jumlah (Rp)": ""})
    for it in neraca["liabilitas_lancar"]:
        baris_neraca.append({"Kategori": "Liabilitas Lancar", "Akun": it["nama_akun"], "Jumlah (Rp)": it["jumlah"]})
    for it in neraca["liabilitas_jangka_panjang"]:
        baris_neraca.append({"Kategori": "Liabilitas Jangka Panjang", "Akun": it["nama_akun"], "Jumlah (Rp)": it["jumlah"]})
    baris_neraca.append({"Kategori": "Total Liabilitas", "Akun": "", "Jumlah (Rp)": neraca["total_liabilitas"]})

    baris_neraca.append({"Kategori": "EKUITAS", "Akun": "", "Jumlah (Rp)": ""})
    for it in neraca["ekuitas"]:
        baris_neraca.append({"Kategori": "Ekuitas", "Akun": it["nama_akun"], "Jumlah (Rp)": it["jumlah"]})
    baris_neraca.append({"Kategori": "TOTAL LIABILITAS & EKUITAS", "Akun": "", "Jumlah (Rp)": neraca["total_liabilitas_ekuitas"]})
    df_neraca = pd.DataFrame(baris_neraca)

    ak = susun_arus_kas(period_id)
    baris_ak = [
        {"Aktivitas": "ARUS KAS OPERASI", "Keterangan": "", "Jumlah (Rp)": ""},
    ]
    for it in ak["operasi"]["penerimaan"]:
        baris_ak.append({"Aktivitas": "Operasi (Masuk)", "Keterangan": it["keterangan"], "Jumlah (Rp)": it["jumlah"]})
    for it in ak["operasi"]["pengeluaran"]:
        baris_ak.append({"Aktivitas": "Operasi (Keluar)", "Keterangan": it["keterangan"], "Jumlah (Rp)": -it["jumlah"]})
    baris_ak.append({"Aktivitas": "Arus Kas Bersih Operasi", "Keterangan": "", "Jumlah (Rp)": ak["operasi"]["neto"]})

    baris_ak.append({"Aktivitas": "ARUS KAS INVESTASI", "Keterangan": "", "Jumlah (Rp)": ""})
    for it in ak["investasi"]["pengeluaran"]:
        baris_ak.append({"Aktivitas": "Investasi (Keluar)", "Keterangan": it["keterangan"], "Jumlah (Rp)": -it["jumlah"]})
    baris_ak.append({"Aktivitas": "Arus Kas Bersih Investasi", "Keterangan": "", "Jumlah (Rp)": ak["investasi"]["neto"]})

    baris_ak.append({"Aktivitas": "ARUS KAS PENDANAAN", "Keterangan": "", "Jumlah (Rp)": ""})
    for it in ak["pendanaan"]["penerimaan"]:
        baris_ak.append({"Aktivitas": "Pendanaan (Masuk)", "Keterangan": it["keterangan"], "Jumlah (Rp)": it["jumlah"]})
    baris_ak.append({"Aktivitas": "Arus Kas Bersih Pendanaan", "Keterangan": "", "Jumlah (Rp)": ak["pendanaan"]["neto"]})

    baris_ak.append({"Aktivitas": "KENAIKAN KAS BERSIH", "Keterangan": "", "Jumlah (Rp)": ak["kenaikan_penurunan_kas"]})
    baris_ak.append({"Aktivitas": "SALDO KAS AWAL", "Keterangan": "", "Jumlah (Rp)": ak["saldo_kas_awal"]})
    baris_ak.append({"Aktivitas": "SALDO KAS AKHIR", "Keterangan": "", "Jumlah (Rp)": ak["saldo_kas_akhir"]})
    df_ak = pd.DataFrame(baris_ak)

    df_ns = _ambil_neraca_saldo_df(period_id)

    dict_laporan = {
        "Laba Rugi": df_lr,
        "Perubahan Ekuitas": df_pe,
        "Neraca": df_neraca,
        "Arus Kas": df_ak,
    }
    if not df_ns.empty:
        dict_laporan["Neraca Saldo"] = df_ns

    return dict_laporan


def _unduh_neraca_saldo_excel(period_id: int, label_periode: str) -> None:
    """Menyiapkan dan menampilkan tombol download neraca saldo Excel."""
    with st.spinner("Menyiapkan Excel..."):
        df = _ambil_neraca_saldo_df(period_id)
        if df.empty:
            st.warning("Tidak ada data neraca saldo.")
            return
        excel_bytes = export_dataframe_ke_excel(
            df,
            nama_sheet="Neraca Saldo",
            judul=f"Neraca Saldo — {label_periode}",
            kolom_rupiah=["Debit", "Kredit"],
        )
    st.download_button(
        label="📥 Download Excel",
        data=excel_bytes,
        file_name=f"neraca_saldo_{label_periode.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _unduh_neraca_saldo_pdf(period_id: int, label_periode: str) -> None:
    """Menyiapkan dan menampilkan tombol download neraca saldo PDF."""
    with st.spinner("Menyiapkan PDF..."):
        df = _ambil_neraca_saldo_df(period_id)
        if df.empty:
            st.warning("Tidak ada data neraca saldo.")
            return
        pdf_bytes = export_dataframe_ke_pdf(
            df,
            judul_laporan=f"Neraca Saldo — {label_periode}",
            kolom_rupiah=["Debit", "Kredit"],
            lebar_kolom=[20, 70, 30, 35, 35],
        )
    st.download_button(
        label="📥 Download PDF",
        data=pdf_bytes,
        file_name=f"neraca_saldo_{label_periode.replace(' ', '_')}.pdf",
        mime="application/pdf",
    )


# ---------------------------------------------------------------------------
# Fungsi utama tampilan
# ---------------------------------------------------------------------------

def tampilkan() -> None:
    """Halaman utama Laporan Keuangan."""
    st.title("📄 Laporan Keuangan")
    st.caption(
        "Laporan keuangan disusun secara berurutan: "
        "Laba Rugi → Perubahan Ekuitas → Neraca → Arus Kas. "
        "Laba Bersih dari L/R masuk ke Perubahan Ekuitas, "
        "dan Modal Akhir masuk ke Neraca."
    )

    # -------------------------------------------------------------------
    # Pilih periode
    # -------------------------------------------------------------------
    kol_p, _ = st.columns([2, 2])
    with kol_p:
        period_id = selector_periode(
            label="📅 Pilih Periode Laporan Keuangan",
            key="laporan_keuangan_periode",
            hanya_buka=False,
            tampilkan_kalender=True,
        )

    if not period_id:
        return

    info_p = ps.ambil_info_periode(period_id)
    pilihan = f"{info_p['nama_bulan']} ({info_p['status'].title()})" if info_p else f"Periode {period_id}"

    # Tombol export laporan keuangan periode ini
    with st.expander("⬇️ Export Laporan Keuangan ke Excel / PDF", expanded=False):
        st.markdown("**📦 Paket Lengkap Laporan Keuangan (Multi-Sheet Excel)**")
        st.caption("Berisi: Laba Rugi, Perubahan Ekuitas, Neraca, Arus Kas, dan Neraca Saldo.")
        try:
            dict_laporan = _ambil_laporan_lengkap_dict(period_id)
            excel_semua = export_laporan_keuangan_ke_excel(dict_laporan)
            st.download_button(
                label=f"📥 Download Semua Laporan Keuangan — {pilihan} (.xlsx)",
                data=excel_semua,
                file_name=f"laporan_keuangan_lengkap_{pilihan.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary",
            )
        except Exception as e:
            st.error(f"Gagal menyiapkan paket Excel: {e}")

        st.markdown("---")
        st.markdown("**📄 Export Neraca Saldo**")
        kol_e1, kol_e2 = st.columns(2)
        with kol_e1:
            try:
                df_ns = _ambil_neraca_saldo_df(period_id)
                if not df_ns.empty:
                    excel_bytes = export_dataframe_ke_excel(
                        df_ns,
                        nama_sheet="Neraca Saldo",
                        judul=f"Neraca Saldo — {pilihan}",
                        kolom_rupiah=["Debit", "Kredit"],
                    )
                    st.download_button(
                        label="📊 Download Neraca Saldo (Excel)",
                        data=excel_bytes,
                        file_name=f"neraca_saldo_{pilihan.replace(' ', '_')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                else:
                    st.info("Tidak ada data neraca saldo.")
            except Exception as e:
                st.error(f"Gagal export Excel: {e}")

        with kol_e2:
            try:
                df_ns = _ambil_neraca_saldo_df(period_id)
                if not df_ns.empty:
                    pdf_bytes = export_dataframe_ke_pdf(
                        df_ns,
                        judul_laporan=f"Neraca Saldo — {pilihan}",
                        kolom_rupiah=["Debit", "Kredit"],
                        lebar_kolom=[20, 70, 30, 35, 35],
                    )
                    st.download_button(
                        label="📄 Download Neraca Saldo (PDF)",
                        data=pdf_bytes,
                        file_name=f"neraca_saldo_{pilihan.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                else:
                    st.info("Tidak ada data neraca saldo.")
            except Exception as e:
                st.error(f"Gagal export PDF: {e}")

    st.divider()

    # -------------------------------------------------------------------
    # 4 Tabs laporan keuangan
    # -------------------------------------------------------------------
    tab_lk = sac.tabs(
        [
            sac.TabsItem(label="Laba Rugi", icon="bar-chart"),
            sac.TabsItem(label="Perubahan Ekuitas", icon="arrow-up-circle"),
            sac.TabsItem(label="Neraca", icon="balance-scale" if False else "grid"),
            sac.TabsItem(label="Arus Kas", icon="cash-stack"),
        ],
        align="center",
        variant="outline",
    )

    if tab_lk == "Laba Rugi":
        _tab_laba_rugi(period_id)

    elif tab_lk == "Perubahan Ekuitas":
        # Hitung laba dulu (bisa dari session_state kalau sudah ada)
        laba = st.session_state.get("laba_bersih_f6")
        if laba is None:
            with st.spinner("Menghitung laba bersih..."):
                data_lr = susun_laporan_laba_rugi(period_id)
                laba = data_lr["laba_bersih"]
                st.session_state["laba_bersih_f6"] = laba
        _tab_perubahan_ekuitas(period_id, laba)

    elif tab_lk == "Neraca":
        laba = st.session_state.get("laba_bersih_f6")
        if laba is None:
            with st.spinner("Menghitung laba bersih..."):
                data_lr = susun_laporan_laba_rugi(period_id)
                laba = data_lr["laba_bersih"]
                st.session_state["laba_bersih_f6"] = laba

        modal_akhir = st.session_state.get("modal_akhir_f6")
        if modal_akhir is None:
            with st.spinner("Menghitung modal akhir..."):
                data_pe = susun_laporan_perubahan_ekuitas(period_id, laba)
                modal_akhir = data_pe["modal_akhir"]
                st.session_state["modal_akhir_f6"] = modal_akhir

        _tab_neraca(period_id, modal_akhir)

    elif tab_lk == "Arus Kas":
        _tab_arus_kas(period_id)


tampilkan()
