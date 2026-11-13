"""
utils/export.py
---------------
Tujuan  : Fungsi untuk mengekspor data ke format Excel (openpyxl) dan PDF (fpdf2).
Input   : DataFrame pandas atau dict data laporan.
Output  : Bytes yang bisa diunduh lewat st.download_button.
Dipanggil oleh : views/14_backup_export.py, views/12_laporan_keuangan.py

CATATAN: Semua fungsi mengembalikan bytes (bukan menyimpan file).
         Ini agar bisa langsung dipakai st.download_button tanpa simpan ke disk.
"""

import io
from datetime import datetime
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from fpdf import FPDF

from theme import NAMA_PERUSAHAAN, NAMA_APLIKASI
from utils.formatting import format_rupiah, format_tanggal


# ---------------------------------------------------------------
# WARNA EXCEL (dalam format ARGB hex, tanpa #)
# ---------------------------------------------------------------
WARNA_HEADER_EXCEL = "FF2E7D32"   # hijau tua
WARNA_SUBHEADER_EXCEL = "FFE8F5E9"  # hijau muda
WARNA_TEKS_PUTIH = "FFFFFFFF"


# ---------------------------------------------------------------
# EXPORT KE EXCEL
# ---------------------------------------------------------------
def export_dataframe_ke_excel(
    df: pd.DataFrame,
    nama_sheet: str = "Data",
    judul: str = "",
    kolom_rupiah: list[str] | None = None,
) -> bytes:
    """
    Mengekspor satu DataFrame ke file Excel dengan styling.

    Args:
        df           : DataFrame yang akan diekspor.
        nama_sheet   : Nama sheet Excel.
        judul        : Judul yang ditampilkan di baris pertama.
        kolom_rupiah : Daftar nama kolom yang berisi angka Rupiah
                       (akan diformat sebagai Rp).

    Returns:
        Bytes file Excel siap unduh.

    Contoh di views/:
        excel_bytes = export_dataframe_ke_excel(df_neraca, "Neraca Saldo", "Neraca Saldo Oktober 2026")
        st.download_button("Unduh Excel", excel_bytes, "neraca_saldo.xlsx")
    """
    wb = Workbook()
    ws = wb.active
    ws.title = nama_sheet

    baris_mulai = 1

    # --- Judul ---
    if judul:
        ws.merge_cells(f"A1:{get_column_letter(len(df.columns))}1")
        sel_judul = ws["A1"]
        sel_judul.value = judul
        sel_judul.font = Font(bold=True, size=14, color=WARNA_TEKS_PUTIH)
        sel_judul.fill = PatternFill("solid", fgColor=WARNA_HEADER_EXCEL)
        sel_judul.alignment = Alignment(horizontal="center")

        # Baris ke-2: nama perusahaan
        ws.merge_cells(f"A2:{get_column_letter(len(df.columns))}2")
        ws["A2"].value = NAMA_PERUSAHAAN
        ws["A2"].alignment = Alignment(horizontal="center")
        ws["A2"].font = Font(italic=True, size=10)

        # Baris ke-3: tanggal cetak
        ws.merge_cells(f"A3:{get_column_letter(len(df.columns))}3")
        ws["A3"].value = f"Dicetak: {format_tanggal(datetime.now().date())}"
        ws["A3"].alignment = Alignment(horizontal="center")
        ws["A3"].font = Font(italic=True, size=9, color="FF666666")

        baris_mulai = 5  # header kolom dimulai baris 5

    # --- Header kolom ---
    for idx_kol, nama_kol in enumerate(df.columns, start=1):
        sel = ws.cell(row=baris_mulai, column=idx_kol)
        sel.value = nama_kol
        sel.font = Font(bold=True, color=WARNA_TEKS_PUTIH)
        sel.fill = PatternFill("solid", fgColor=WARNA_HEADER_EXCEL)
        sel.alignment = Alignment(horizontal="center")

    # --- Data ---
    for idx_baris, (_, baris) in enumerate(df.iterrows(), start=baris_mulai + 1):
        # Warna bergantian untuk keterbacaan
        warna_baris = "FFF9FBF9" if idx_baris % 2 == 0 else "FFE8F5E9"
        for idx_kol, (nama_kol, nilai) in enumerate(baris.items(), start=1):
            sel = ws.cell(row=idx_baris, column=idx_kol)
            sel.value = nilai
            sel.fill = PatternFill("solid", fgColor=warna_baris)
            # Format kolom Rupiah rata kanan
            if kolom_rupiah and nama_kol in kolom_rupiah:
                sel.alignment = Alignment(horizontal="right")
                # Format number Excel dengan pemisah ribuan
                sel.number_format = '#,##0'

    # --- Auto-width kolom ---
    for idx_kol, nama_kol in enumerate(df.columns, start=1):
        # Ambil panjang terpanjang di kolom ini
        panjang_maks = len(str(nama_kol))
        for baris_data in df[nama_kol].astype(str):
            panjang_maks = max(panjang_maks, len(baris_data))
        ws.column_dimensions[get_column_letter(idx_kol)].width = min(panjang_maks + 4, 50)

    # Simpan ke bytes
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def export_laporan_keuangan_ke_excel(
    data_laporan: dict[str, pd.DataFrame],
    nama_file: str = "laporan_keuangan.xlsx",
) -> bytes:
    """
    Mengekspor beberapa laporan keuangan ke satu file Excel multi-sheet.

    Args:
        data_laporan : Dict {nama_sheet: DataFrame} untuk setiap laporan.

    Returns:
        Bytes file Excel multi-sheet.
    """
    wb = Workbook()
    # Hapus sheet default
    wb.remove(wb.active)

    for nama_sheet, df in data_laporan.items():
        ws = wb.create_sheet(title=nama_sheet[:31])  # max 31 karakter

        # Header perusahaan
        ws.merge_cells(f"A1:{get_column_letter(max(len(df.columns), 2))}1")
        ws["A1"].value = NAMA_PERUSAHAAN
        ws["A1"].font = Font(bold=True, size=12)
        ws["A1"].alignment = Alignment(horizontal="center")

        ws.merge_cells(f"A2:{get_column_letter(max(len(df.columns), 2))}2")
        ws["A2"].value = nama_sheet
        ws["A2"].font = Font(bold=True, size=11, color=WARNA_TEKS_PUTIH)
        ws["A2"].fill = PatternFill("solid", fgColor=WARNA_HEADER_EXCEL)
        ws["A2"].alignment = Alignment(horizontal="center")

        # Data
        for idx_kol, nama_kol in enumerate(df.columns, start=1):
            sel = ws.cell(row=4, column=idx_kol)
            sel.value = nama_kol
            sel.font = Font(bold=True)
            sel.fill = PatternFill("solid", fgColor=WARNA_SUBHEADER_EXCEL)

        for idx_baris, (_, baris) in enumerate(df.iterrows(), start=5):
            for idx_kol, nilai in enumerate(baris, start=1):
                ws.cell(row=idx_baris, column=idx_kol).value = nilai

        for idx_kol, nama_kol in enumerate(df.columns, start=1):
            panjang = max(len(str(nama_kol)), max((len(str(v or "")) for v in df[nama_kol]), default=0))
            ws.column_dimensions[get_column_letter(idx_kol)].width = min(max(panjang + 4, 12), 50)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# ---------------------------------------------------------------
# HELPER UNTUK SANITASI TEKS PDF
# ---------------------------------------------------------------
def _bersihkan_teks_pdf(teks: str) -> str:
    """
    Mengubah karakter unicode non-latin1 menjadi representasi latin-1 yang aman
    untuk font bawaan FPDF (Helvetica). Menghindari FPDFUnicodeEncodingException.
    """
    if not isinstance(teks, str):
        teks = str(teks)
    replacements = {
        "—": "-",   # em-dash
        "–": "-",   # en-dash
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "•": "*",
        "…": "...",
        "✓": "[OK]",
        "✔": "[OK]",
        "✗": "[X]",
    }
    for k, v in replacements.items():
        teks = teks.replace(k, v)
    return teks.encode("latin-1", "replace").decode("latin-1")


# ---------------------------------------------------------------
# EXPORT KE PDF
# ---------------------------------------------------------------
class PDFLaporan(FPDF):
    """
    Kelas PDF kustom untuk laporan keuangan.
    Mewarisi FPDF dan menambahkan header/footer standar perusahaan.
    """

    def __init__(self, judul_laporan: str = ""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.judul_laporan = _bersihkan_teks_pdf(judul_laporan)
        self.set_auto_page_break(auto=True, margin=15)
        self.add_page()

    def header(self) -> None:
        """Header yang otomatis muncul di setiap halaman."""
        # Nama perusahaan
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 7, _bersihkan_teks_pdf(NAMA_PERUSAHAAN), new_x="LMARGIN", new_y="NEXT", align="C")

        # Judul laporan
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(46, 125, 50)  # hijau tua
        self.cell(0, 6, self.judul_laporan, new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_text_color(0, 0, 0)

        # Tanggal cetak
        self.set_font("Helvetica", "", 8)
        self.cell(0, 5, f"Dicetak: {format_tanggal(datetime.now().date())}", new_x="LMARGIN", new_y="NEXT", align="C")

        # Garis pemisah
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self) -> None:
        """Footer dengan nomor halaman."""
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Halaman {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)


def export_dataframe_ke_pdf(
    df: pd.DataFrame,
    judul_laporan: str = "Laporan",
    kolom_rupiah: list[str] | None = None,
    lebar_kolom: list[float] | None = None,
) -> bytes:
    """
    Mengekspor DataFrame ke PDF dengan format laporan standar.

    Args:
        df            : DataFrame yang diekspor.
        judul_laporan : Judul laporan (muncul di header PDF).
        kolom_rupiah  : Kolom yang berisi angka Rupiah (rata kanan).
        lebar_kolom   : Lebar setiap kolom dalam mm (opsional, otomatis jika None).

    Returns:
        Bytes file PDF siap unduh.
    """
    pdf = PDFLaporan(judul_laporan=judul_laporan)
    pdf.set_font("Helvetica", "", 9)

    n_kol = len(df.columns)
    lebar_total = 190  # lebar halaman A4 dikurangi margin

    # Hitung lebar kolom otomatis jika tidak disediakan
    if lebar_kolom is None:
        lebar_kolom = [lebar_total / n_kol] * n_kol

    tinggi_baris = 7

    # --- Header kolom ---
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(46, 125, 50)   # hijau tua
    pdf.set_text_color(255, 255, 255)  # putih
    for idx, (nama_kol, lebar) in enumerate(zip(df.columns, lebar_kolom)):
        pdf.cell(lebar, tinggi_baris, _bersihkan_teks_pdf(str(nama_kol)), border=1, align="C", fill=True)
    pdf.ln()

    # --- Data ---
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(0, 0, 0)
    for idx_baris, (_, baris) in enumerate(df.iterrows()):
        # Warna bergantian
        if idx_baris % 2 == 0:
            pdf.set_fill_color(232, 245, 233)  # hijau sangat muda
        else:
            pdf.set_fill_color(255, 255, 255)

        for nama_kol, (nilai, lebar) in zip(df.columns, zip(baris, lebar_kolom)):
            # Rata kanan untuk kolom Rupiah
            align = "R" if (kolom_rupiah and nama_kol in kolom_rupiah) else "L"
            teks = _bersihkan_teks_pdf(str(nilai)) if nilai is not None else "-"
            # Potong teks panjang agar tidak meluber
            maks_karakter = int(lebar / 2.2)
            if len(teks) > maks_karakter:
                teks = teks[:maks_karakter - 2] + ".."
            pdf.cell(lebar, tinggi_baris, teks, border=1, align=align, fill=True)
        pdf.ln()

    # Kembalikan sebagai bytes
    return bytes(pdf.output())
