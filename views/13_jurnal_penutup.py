"""
views/13_jurnal_penutup.py
----------------------------
Tujuan  : Membuat jurnal penutup, menutup periode, dan menampilkan
          neraca saldo setelah penutup.
Input   : Pilih periode, tombol aksi.
Output  : Jurnal penutup disimpan ke DB, periode ditutup.
Dipanggil oleh : app.py (st.navigation)
"""

import streamlit as st
from database.connection import get_connection
from services.closing_service import (
    preview_jurnal_penutup,
    buat_jurnal_penutup,
    tutup_periode,
    cek_jurnal_penutup_sudah_ada,
    hitung_neraca_saldo_setelah_penutup,
    hapus_jurnal_penutup,
)
from utils.formatting import format_rupiah
from utils.ui_components import selector_periode
import services.period_service as ps
import streamlit_antd_components as sac


# ---------------------------------------------------------------------------
# Fungsi pembantu (private)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def _ambil_periode_buka() -> list[dict]:
    """Mengambil periode yang masih berstatus buka."""
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            "SELECT id, tahun, bulan, nama_bulan AS label, status FROM periods ORDER BY tahun, bulan"
        ).fetchall()
    finally:
        koneksi.close()
    return [dict(r) for r in rows]


def _tampilkan_preview_jurnal(rencana: list[dict]) -> None:
    """Menampilkan pratinjau jurnal penutup sebelum disimpan."""
    sac.divider(label="Pratinjau Jurnal Penutup", icon="eye", align="center")

    if not rencana:
        sac.alert(
            label="Tidak ada jurnal penutup yang perlu dibuat.",
            description="Pastikan ada transaksi pendapatan dan beban di periode ini.",
            color="info",
            icon=True,
        )
        return

    for jurnal in rencana:
        with st.expander(f"📋 {jurnal['no_bukti']} — {jurnal['keterangan']}", expanded=True):
            # Buat tabel tampilan
            baris_tabel = []
            for line in jurnal["lines"]:
                baris_tabel.append({
                    "Kode Akun": line["akun"],
                    "Nama Akun": line["nama"],
                    "Debit": format_rupiah(line["debit"]) if line["debit"] > 0 else "-",
                    "Kredit": format_rupiah(line["kredit"]) if line["kredit"] > 0 else "-",
                })
            st.table(baris_tabel)

            # Total baris
            total_d = sum(l["debit"] for l in jurnal["lines"])
            total_k = sum(l["kredit"] for l in jurnal["lines"])
            col1, col2, col3 = st.columns([3, 1, 1])
            col1.markdown("**Total**")
            col2.markdown(f"**{format_rupiah(total_d)}**")
            col3.markdown(f"**{format_rupiah(total_k)}**")

            if total_d == total_k:
                st.success(f"✓ Jurnal seimbang")
            else:
                st.error("✗ Jurnal tidak seimbang — ada kesalahan!")


def _tampilkan_ns_setelah_penutup(period_id: int) -> None:
    """Menampilkan Neraca Saldo Setelah Penutup."""
    sac.divider(label="Neraca Saldo Setelah Penutup", icon="table", align="center")

    df = hitung_neraca_saldo_setelah_penutup(period_id)

    if df.empty:
        st.info("Belum ada data neraca saldo setelah penutup.")
        return

    # Format tampilan
    df_tampil = df[["kode_akun", "nama_akun", "kategori", "debit", "kredit"]].copy()
    df_tampil["debit"] = df_tampil["debit"].apply(
        lambda x: format_rupiah(int(x)) if int(x) > 0 else "-"
    )
    df_tampil["kredit"] = df_tampil["kredit"].apply(
        lambda x: format_rupiah(int(x)) if int(x) > 0 else "-"
    )
    df_tampil.columns = ["Kode", "Nama Akun", "Kategori", "Debit", "Kredit"]

    st.dataframe(df_tampil, use_container_width=True, height=400)

    # Total
    total_d = int(df["debit"].sum())
    total_k = int(df["kredit"].sum())
    col1, col2, col3 = st.columns([3, 2, 2])
    col1.markdown("**TOTAL**")
    col2.markdown(f"**{format_rupiah(total_d)}**")
    col3.markdown(f"**{format_rupiah(total_k)}**")

    if total_d == total_k:
        sac.alert(
            label="Neraca Saldo Setelah Penutup Seimbang ✓",
            description=(
                f"Total Debit = Total Kredit = {format_rupiah(total_d)}\n"
                "Hanya akun permanen (Aset, Liabilitas, Ekuitas) yang muncul."
            ),
            color="success",
            icon=True,
        )
    else:
        sac.alert(
            label="Neraca Saldo Tidak Seimbang!",
            description=f"Debit: {format_rupiah(total_d)} | Kredit: {format_rupiah(total_k)}",
            color="error",
            icon=True,
        )


# ---------------------------------------------------------------------------
# Fungsi utama tampilan
# ---------------------------------------------------------------------------

def tampilkan() -> None:
    """Halaman utama Jurnal Penutup."""
    st.title("🔒 Jurnal Penutup")
    st.caption(
        "Jurnal penutup menutup akun sementara (Pendapatan dan Beban) dan "
        "memindahkan laba/rugi ke Laba Ditahan. Setelah periode ditutup, "
        "data tidak bisa diubah lagi."
    )

    # -------------------------------------------------------------------
    # Pilih periode
    # -------------------------------------------------------------------
    kol_p, _ = st.columns([2, 2])
    with kol_p:
        period_id = selector_periode(
            label="📅 Pilih Periode Jurnal Penutup",
            key="jurnal_penutup_periode",
            hanya_buka=False,
            tampilkan_kalender=True,
        )

    if not period_id:
        return

    periode_terpilih = ps.ambil_info_periode(period_id) or {"status": "buka", "tahun": 2026, "bulan": 10}
    status_periode = periode_terpilih.get("status", "buka")

    # -------------------------------------------------------------------
    # Status periode
    # -------------------------------------------------------------------
    if status_periode == "tutup":
        sac.alert(
            label=f"Periode ini sudah DITUTUP.",
            description="Tidak bisa membuat atau mengubah jurnal penutup.",
            color="warning",
            icon=True,
        )
        st.divider()
        _tampilkan_ns_setelah_penutup(period_id)
        return

    # -------------------------------------------------------------------
    # Cek apakah jurnal penutup sudah ada
    # -------------------------------------------------------------------
    sudah_ada_jp = cek_jurnal_penutup_sudah_ada(period_id)

    # -------------------------------------------------------------------
    # Pilih tanggal jurnal penutup
    # -------------------------------------------------------------------
    import datetime
    tanggal_penutup = st.date_input(
        "Tanggal Jurnal Penutup",
        value=datetime.date.today(),
        help="Biasanya tanggal akhir bulan periode."
    )
    tanggal_str = tanggal_penutup.strftime("%Y-%m-%d")

    st.divider()

    # -------------------------------------------------------------------
    # Pratinjau jurnal penutup
    # -------------------------------------------------------------------
    if not sudah_ada_jp:
        # Hitung dan tampilkan pratinjau
        try:
            with st.spinner("Menghitung jurnal penutup..."):
                rencana = preview_jurnal_penutup(period_id, tanggal_str)
        except ValueError as e:
            sac.alert(
                label="Gagal menghitung jurnal penutup.",
                description=str(e),
                color="error",
                icon=True,
            )
            return

        _tampilkan_preview_jurnal(rencana)

        st.divider()

        # Tombol simpan jurnal penutup
        sac.divider(label="Aksi", icon="gear", align="center")
        col1, col2 = st.columns(2)
        with col1:
            if rencana and st.button(
                "💾 Simpan Jurnal Penutup",
                type="primary",
                use_container_width=True,
                help="Simpan 3 jurnal penutup ke database."
            ):
                try:
                    id_list = buat_jurnal_penutup(period_id, tanggal_str)
                    st.cache_data.clear()
                    st.success(
                        f"✓ Berhasil menyimpan {len(id_list)} jurnal penutup "
                        f"(ID: {', '.join(map(str, id_list))})"
                    )
                    st.rerun()
                except ValueError as e:
                    st.error(f"Gagal: {e}")
                except Exception as e:
                    st.error(f"Error tidak terduga: {e}")
        with col2:
            st.info(
                "Setelah menyimpan jurnal penutup, Anda bisa menutup periode "
                "dengan tombol di bawah."
            )
    else:
        # Jurnal penutup sudah ada — tampilkan status dan opsi
        sac.alert(
            label="Jurnal Penutup sudah dibuat ✓",
            description="Lihat Neraca Saldo Setelah Penutup di bawah.",
            color="success",
            icon=True,
        )

        # Tampilkan NS setelah penutup
        _tampilkan_ns_setelah_penutup(period_id)

        st.divider()

        # Tombol aksi
        sac.divider(label="Aksi Lanjutan", icon="gear", align="center")
        col1, col2 = st.columns(2)

        with col1:
            # Tombol hapus jurnal penutup (jika periode belum tutup)
            if st.button(
                "🗑️ Hapus Jurnal Penutup",
                type="secondary",
                use_container_width=True,
                help="Hapus jurnal penutup jika ingin mengubah data dan buat ulang."
            ):
                if st.session_state.get("konfirmasi_hapus_jp"):
                    try:
                        berhasil = hapus_jurnal_penutup(period_id)
                        if berhasil:
                            st.cache_data.clear()
                            st.success("✓ Jurnal penutup berhasil dihapus.")
                            st.session_state["konfirmasi_hapus_jp"] = False
                            st.rerun()
                        else:
                            st.warning("Tidak ada jurnal penutup yang dihapus.")
                    except ValueError as e:
                        st.error(str(e))
                else:
                    st.session_state["konfirmasi_hapus_jp"] = True
                    st.warning(
                        "⚠ Klik sekali lagi tombol **Hapus Jurnal Penutup** untuk konfirmasi. "
                        "Data jurnal penutup akan dihapus permanen."
                    )

        with col2:
            # Tombol tutup periode
            st.markdown("#### 🔒 Tutup Periode")
            st.warning(
                "**Peringatan:** Setelah periode ditutup, **tidak ada yang bisa diubah**. "
                "Pastikan semua data sudah benar."
            )

            if st.checkbox("Saya sudah memeriksa semua data dan yakin ingin menutup periode."):
                if st.button(
                    "🔒 TUTUP PERIODE",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        tutup_periode(period_id)
                        st.cache_data.clear()
                        st.success(
                            f"✓ Periode berhasil ditutup! "
                            f"Periode ini tidak bisa diedit lagi."
                        )
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))


tampilkan()
