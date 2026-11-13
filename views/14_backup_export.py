"""
views/14_backup_export.py
--------------------------
Tujuan  : Backup (unduh file .db / .xlsx) dan Restore (unggah file backup).
          Export semua laporan keuangan ke Excel dan PDF.
          Juga ada tombol "Reset ke Data Contoh" untuk Streamlit Cloud
          yang filesystemnya tidak permanen.
Input   : File backup yang diunggah user (untuk restore).
          Pilihan periode untuk export laporan.
Output  : File .db, .xlsx, atau .pdf yang bisa diunduh.
Dipanggil oleh : app.py (st.navigation)

CATATAN HOSTING:
  Streamlit Community Cloud filesystem TIDAK permanen.
  Setiap restart, data hilang. Gunakan fitur ini untuk menyimpan
  dan memulihkan data secara manual.
"""

import streamlit as st
import streamlit_antd_components as sac
import pandas as pd
from pathlib import Path

from database.connection import get_connection, PATH_DATABASE
from utils.ui_components import divider_dengan_judul, selector_periode
from utils.formatting import format_rupiah
from utils.export import (
    export_dataframe_ke_excel,
    export_dataframe_ke_pdf,
    export_laporan_keuangan_ke_excel,
)
import services.dashboard_service as ds


# ---------------------------------------------------------------
# HELPER: Ambil semua periode
# ---------------------------------------------------------------
@st.cache_data(ttl=60)
def _ambil_semua_periode() -> list[dict]:
    """Mengambil semua periode dari database."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, tahun, bulan, nama_bulan, status FROM periods ORDER BY tahun, bulan"
    ).fetchall()
    return [dict(r) for r in rows]


def _pilih_periode(key: str | None = None) -> int | None:
    """Widget untuk memilih periode. Mengembalikan period_id atau None."""
    return selector_periode(
        label="📅 Pilih Periode",
        key=key or "backup_export_periode",
        hanya_buka=False,
        tampilkan_kalender=True,
    )


# ---------------------------------------------------------------
# EXPORT TABEL DATABASE KE EXCEL (semua tabel penting)
# ---------------------------------------------------------------
def _export_semua_tabel_excel(period_id: int) -> bytes:
    """
    Mengambil semua tabel penting dan mengekspor ke Excel multi-sheet.
    Returns bytes file Excel.
    """
    conn = get_connection()
    tabel_tabel = {
        "Bagan Akun": "SELECT kode_akun, nama_akun, kategori, saldo_normal FROM accounts WHERE aktif=1 ORDER BY kode_akun",
        "Pelanggan": "SELECT nama, tipe, telepon, alamat FROM customers WHERE aktif=1",
        "Supplier": "SELECT nama, telepon, alamat FROM suppliers WHERE aktif=1",
        "Pekerja": "SELECT nama, tipe_pekerja, upah_harian, komoditas FROM employees WHERE aktif=1",
        "Items Persediaan": "SELECT kode_item, nama_item, satuan, tipe, komoditas FROM items WHERE aktif=1",
        "Blok Lahan": "SELECT kode_blok, komoditas, jumlah_pohon, luas_m2 FROM blok_lahan WHERE aktif=1",
        "Aset Tetap": "SELECT kode_aset, nama_aset, kategori_aset, harga_perolehan, umur_ekonomis_tahun FROM fixed_assets WHERE aktif=1",
        "Jurnal Entries": f"SELECT tanggal, no_bukti, journal_type, keterangan, pihak_terkait, komoditas FROM journal_entries WHERE period_id={period_id} ORDER BY tanggal, id",
        "Piutang": "SELECT no_faktur, tanggal_faktur, tanggal_jatuh_tempo, jumlah, jumlah_terbayar, status FROM receivables ORDER BY tanggal_faktur",
    }

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    import io
    from datetime import datetime
    from theme import NAMA_PERUSAHAAN

    wb = Workbook()
    wb.remove(wb.active)

    WARNA_HEADER = "FF2E7D32"
    WARNA_PUTIH = "FFFFFFFF"

    for nama_sheet, sql in tabel_tabel.items():
        try:
            rows = conn.execute(sql).fetchall()
        except Exception:
            continue

        if not rows:
            continue

        ws = wb.create_sheet(title=nama_sheet[:31])
        kolom = list(rows[0].keys())

        # Header
        ws.merge_cells(f"A1:{get_column_letter(len(kolom))}1")
        ws["A1"].value = f"{NAMA_PERUSAHAAN} — {nama_sheet}"
        ws["A1"].font = Font(bold=True, size=12, color=WARNA_PUTIH)
        ws["A1"].fill = PatternFill("solid", fgColor=WARNA_HEADER)
        ws["A1"].alignment = Alignment(horizontal="center")

        ws.merge_cells(f"A2:{get_column_letter(len(kolom))}2")
        ws["A2"].value = f"Dicetak: {datetime.now().strftime('%d %B %Y %H:%M')}"
        ws["A2"].alignment = Alignment(horizontal="center")
        ws["A2"].font = Font(italic=True, size=9)

        for idx_kol, nama_kol in enumerate(kolom, start=1):
            sel = ws.cell(row=4, column=idx_kol)
            sel.value = nama_kol.replace("_", " ").title()
            sel.font = Font(bold=True, color=WARNA_PUTIH)
            sel.fill = PatternFill("solid", fgColor=WARNA_HEADER)
            sel.alignment = Alignment(horizontal="center")

        for idx_baris, row in enumerate(rows, start=5):
            for idx_kol, nama_kol in enumerate(kolom, start=1):
                ws.cell(row=idx_baris, column=idx_kol).value = row[nama_kol]

        for idx_kol, nama_kol in enumerate(kolom, start=1):
            panjang = max(len(str(nama_kol)), max((len(str(r[nama_kol] or "")) for r in rows), default=0))
            ws.column_dimensions[get_column_letter(idx_kol)].width = min(panjang + 4, 50)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------
# EXPORT LAPORAN KEUANGAN
# ---------------------------------------------------------------
def _export_laporan_keuangan(period_id: int) -> tuple[bytes, bytes]:
    """
    Mengekspor laporan keuangan (neraca saldo) ke Excel dan PDF.
    Returns (excel_bytes, pdf_bytes)
    """
    # Ambil neraca saldo sebagai DataFrame
    from database.connection import get_connection

    conn = get_connection()
    sql = """
        SELECT a.kode_akun AS "Kode Akun",
               a.nama_akun AS "Nama Akun",
               a.kategori AS "Kategori",
               COALESCE(ob.saldo_debit, 0) + SUM(CASE WHEN jl.debit > 0 THEN jl.debit ELSE 0 END) AS "Debit",
               COALESCE(ob.saldo_kredit, 0) + SUM(CASE WHEN jl.kredit > 0 THEN jl.kredit ELSE 0 END) AS "Kredit"
        FROM accounts a
        LEFT JOIN opening_balances ob ON a.id = ob.account_id AND ob.period_id = ?
        LEFT JOIN journal_lines jl ON a.id = jl.account_id
        LEFT JOIN journal_entries je ON jl.journal_entry_id = je.id AND je.period_id = ?
        WHERE a.aktif = 1
        GROUP BY a.id, a.kode_akun, a.nama_akun, a.kategori, ob.saldo_debit, ob.saldo_kredit
        HAVING COALESCE(ob.saldo_debit,0) + COALESCE(ob.saldo_kredit,0) + SUM(COALESCE(jl.debit,0)) + SUM(COALESCE(jl.kredit,0)) > 0
        ORDER BY a.kode_akun
    """
    rows = conn.execute(sql, (period_id, period_id)).fetchall()
    df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()

    if df.empty:
        return b"", b""

    info = ds.ambil_info_periode(period_id)
    judul = f"Neraca Saldo — {info['nama_bulan']} {info['tahun']}"

    excel_bytes = export_dataframe_ke_excel(
        df, nama_sheet="Neraca Saldo", judul=judul,
        kolom_rupiah=["Debit", "Kredit"],
    )
    pdf_bytes = export_dataframe_ke_pdf(
        df, judul_laporan=judul,
        kolom_rupiah=["Debit", "Kredit"],
        lebar_kolom=[20, 70, 30, 35, 35],
    )
    return excel_bytes, pdf_bytes


# ---------------------------------------------------------------
# SECTION: BACKUP
# ---------------------------------------------------------------
def _section_backup_database() -> None:
    """Menampilkan seksi backup database dan export Excel."""
    divider_dengan_judul("Backup Database", "download")

    kol1, kol2 = st.columns(2)

    with kol1:
        st.markdown("**📦 Unduh File Database (.db)**")
        st.caption("File mentah SQLite. Bisa di-restore kembali ke sistem.")
        if PATH_DATABASE.exists():
            with open(PATH_DATABASE, "rb") as f:
                data_db = f.read()
            st.download_button(
                label="⬇️ Download Database (.db)",
                data=data_db,
                file_name="akuntansi_cabai_backup.db",
                mime="application/octet-stream",
                use_container_width=True,
                type="primary",
                key="dl_db_backup",
            )
            ukuran_kb = PATH_DATABASE.stat().st_size / 1024
            st.caption(f"📁 Ukuran file: {ukuran_kb:.1f} KB")
        else:
            st.error("File database tidak ditemukan!")

    with kol2:
        st.markdown("**📊 Export Semua Tabel ke Excel**")
        st.caption("Semua tabel penting dalam satu file .xlsx multi-sheet.")
        period_id_export = _pilih_periode(key="periode_export_semua_tabel")
        if period_id_export:
            try:
                excel_bytes = _export_semua_tabel_excel(period_id_export)
                st.download_button(
                    label="⬇️ Download Semua Tabel (.xlsx)",
                    data=excel_bytes,
                    file_name="akuntansi_cabai_semua_tabel.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_semua_tabel_xlsx",
                )
            except Exception as e:
                st.error(f"Gagal menyiapkan Excel: {e}")


# ---------------------------------------------------------------
# SECTION: EXPORT LAPORAN
# ---------------------------------------------------------------
def _section_export_laporan() -> None:
    """Menampilkan seksi export laporan keuangan ke Excel/PDF."""
    divider_dengan_judul("Export Laporan Keuangan", "file-earmark-arrow-down")

    st.markdown(
        "Export **Neraca Saldo** ke Excel atau PDF. "
        "Untuk Laporan Laba Rugi, Neraca, dan Arus Kas — buka menu **Laporan Keuangan**."
    )

    period_id = _pilih_periode(key="periode_export_laporan")
    if not period_id:
        return

    info = ds.ambil_info_periode(period_id)
    label = f"{info['nama_bulan']} {info['tahun']}" if info else f"Periode {period_id}"

    kol1, kol2 = st.columns(2)

    with kol1:
        try:
            excel_bytes, _ = _export_laporan_keuangan(period_id)
            if excel_bytes:
                st.download_button(
                    label=f"📊 Download Neraca Saldo — {label} (.xlsx)",
                    data=excel_bytes,
                    file_name=f"neraca_saldo_{label.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_neraca_saldo_xlsx",
                )
            else:
                st.info("Tidak ada data untuk diekspor.")
        except Exception as e:
            st.error(f"Gagal export Excel: {e}")

    with kol2:
        try:
            _, pdf_bytes = _export_laporan_keuangan(period_id)
            if pdf_bytes:
                st.download_button(
                    label=f"📄 Download Neraca Saldo — {label} (.pdf)",
                    data=pdf_bytes,
                    file_name=f"neraca_saldo_{label.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_neraca_saldo_pdf",
                )
            else:
                st.info("Tidak ada data untuk diekspor.")
        except Exception as e:
            st.error(f"Gagal export PDF: {e}")


# ---------------------------------------------------------------
# SECTION: RESTORE
# ---------------------------------------------------------------
def _section_restore_database() -> None:
    """Menampilkan seksi restore database dari file backup."""
    divider_dengan_judul("Restore Database", "upload")

    st.markdown("**📂 Upload File Backup (.db)**")
    st.caption("Upload file .db yang sebelumnya diunduh untuk memulihkan data.")

    file_upload = st.file_uploader(
        "Pilih file backup (.db)",
        type=["db"],
        help="Hanya file .db yang sebelumnya diunduh dari sistem ini.",
    )

    if file_upload is not None:
        st.warning(
            f"⚠️ Ini akan **mengganti seluruh database** dengan file '{file_upload.name}'. "
            "Semua data saat ini akan hilang!"
        )
        if st.button("🔄 Restore Database", type="primary", use_container_width=True):
            try:
                with open(PATH_DATABASE, "wb") as f:
                    f.write(file_upload.getbuffer())
                st.success("✅ Database berhasil di-restore! Muat ulang halaman.")
                st.balloons()
                st.cache_resource.clear()
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Gagal restore: {e}")


# ---------------------------------------------------------------
# SECTION: RESET
# ---------------------------------------------------------------
def _section_reset_database() -> None:
    """Menampilkan seksi reset database ke data contoh."""
    divider_dengan_judul("Reset ke Data Contoh", "arrow-counterclockwise")

    sac.alert(
        label="⚠️ Tindakan Berbahaya!",
        description=(
            "Reset akan menghapus SEMUA data dan mengisi ulang dengan data contoh Oktober 2026. "
            "Lakukan backup terlebih dahulu sebelum reset."
        ),
        color="error",
        icon=True,
    )

    if st.button("⚠️ Reset ke Data Contoh", use_container_width=True):
        st.session_state["konfirmasi_reset"] = True

    if st.session_state.get("konfirmasi_reset"):
        konfirmasi = st.checkbox(
            "✅ Saya mengerti bahwa SEMUA DATA akan dihapus dan diganti data contoh."
        )
        if konfirmasi:
            if st.button("🗑️ KONFIRMASI RESET", type="primary", use_container_width=True):
                try:
                    if PATH_DATABASE.exists():
                        PATH_DATABASE.unlink()

                    from database.schema import buat_semua_tabel
                    from database.seed import jalankan_seed
                    buat_semua_tabel()
                    jalankan_seed()

                    st.cache_resource.clear()
                    st.cache_data.clear()
                    st.session_state["konfirmasi_reset"] = False

                    st.success("✅ Database berhasil di-reset ke data contoh!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Gagal reset: {e}")


# ---------------------------------------------------------------
# FUNGSI UTAMA
# ---------------------------------------------------------------
def tampilkan() -> None:
    """Fungsi utama halaman Backup & Export. Dipanggil oleh app.py."""
    st.title("💾 Backup & Export")
    st.caption("Simpan, pulihkan, dan ekspor data sistem akuntansi.")

    sac.alert(
        label="📢 Penting untuk Pengguna Streamlit Cloud",
        description=(
            "Streamlit Community Cloud tidak menyimpan data secara permanen. "
            "Selalu download backup sebelum menutup aplikasi!"
        ),
        color="warning",
        icon=True,
    )

    _section_backup_database()
    st.divider()
    _section_export_laporan()
    st.divider()
    _section_restore_database()
    st.divider()
    _section_reset_database()


tampilkan()
