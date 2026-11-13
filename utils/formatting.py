"""
utils/formatting.py
-------------------
Tujuan  : Fungsi-fungsi pembantu untuk memformat angka dan tanggal
          agar tampilannya konsisten di seluruh aplikasi.
Input   : Angka integer (Rupiah) atau objek date/string tanggal.
Output  : String yang sudah diformat (siap tampil di UI).
Dipanggil oleh : Semua file views/ dan utils/export.py

Contoh penggunaan:
  format_rupiah(1500000)   → "Rp1.500.000"
  format_tanggal("2026-10-05") → "05 Oktober 2026"
"""

from datetime import date, datetime
from decimal import Decimal


# ---------------------------------------------------------------
# NAMA BULAN BAHASA INDONESIA
# ---------------------------------------------------------------
NAMA_BULAN_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def format_rupiah(angka: int | float | Decimal | None, tanda_minus: bool = True) -> str:
    """
    Memformat angka menjadi format Rupiah Indonesia.

    Args:
        angka       : Angka yang akan diformat (dalam Rupiah).
        tanda_minus : Jika True, angka negatif ditampilkan dengan tanda minus.

    Returns:
        String format "Rp1.234.567" atau "Rp0" jika None.

    Contoh:
        format_rupiah(1500000)   → "Rp1.500.000"
        format_rupiah(-500000)   → "-Rp500.000"
        format_rupiah(0)         → "Rp0"
    """
    if angka is None:
        return "Rp0"

    # Konversi ke integer (bulatkan ke bawah)
    angka_int = int(angka)
    negatif = angka_int < 0

    # Ambil nilai absolut untuk pemformatan
    abs_angka = abs(angka_int)

    # Format dengan pemisah ribuan menggunakan titik (bukan koma)
    # Python default pakai koma: 1,234,567 → kita ganti ke 1.234.567
    angka_format = f"{abs_angka:,}".replace(",", ".")

    if negatif and tanda_minus:
        return f"-Rp{angka_format}"
    return f"Rp{angka_format}"


def format_rupiah_tabel(angka: int | float | Decimal | None) -> str:
    """
    Format Rupiah khusus untuk tabel — menampilkan angka negatif dalam kurung.
    Contoh: format_rupiah_tabel(-500000) → "(Rp500.000)"
    """
    if angka is None:
        return "Rp0"
    angka_int = int(angka)
    if angka_int < 0:
        abs_format = f"{abs(angka_int):,}".replace(",", ".")
        return f"(Rp{abs_format})"
    angka_format = f"{angka_int:,}".replace(",", ".")
    return f"Rp{angka_format}"


def format_tanggal(tanggal: str | date | datetime | None) -> str:
    """
    Memformat tanggal ke format "DD Bulan YYYY" Bahasa Indonesia.

    Args:
        tanggal : String 'YYYY-MM-DD', objek date, atau datetime.

    Returns:
        String "05 Oktober 2026" atau "-" jika None.

    Contoh:
        format_tanggal("2026-10-05")  → "05 Oktober 2026"
        format_tanggal(date(2026, 10, 5))  → "05 Oktober 2026"
    """
    if tanggal is None:
        return "-"

    # Konversi string ke objek date
    if isinstance(tanggal, str):
        try:
            tanggal = datetime.strptime(tanggal, "%Y-%m-%d").date()
        except ValueError:
            return str(tanggal)  # kembalikan apa adanya kalau format salah

    if isinstance(tanggal, datetime):
        tanggal = tanggal.date()

    nama_bulan = NAMA_BULAN_ID.get(tanggal.month, str(tanggal.month))
    return f"{tanggal.day:02d} {nama_bulan} {tanggal.year}"


def format_tanggal_singkat(tanggal: str | date | None) -> str:
    """
    Format tanggal singkat: "05/10/2026".
    Berguna untuk tabel yang sempit.
    """
    if tanggal is None:
        return "-"
    if isinstance(tanggal, str):
        try:
            tanggal = datetime.strptime(tanggal, "%Y-%m-%d").date()
        except ValueError:
            return str(tanggal)
    return f"{tanggal.day:02d}/{tanggal.month:02d}/{tanggal.year}"


def format_qty(qty: float | None, satuan: str = "") -> str:
    """
    Memformat kuantitas persediaan.
    Jika qty bulat (mis. 5.0), tampilkan "5". Jika desimal, tampilkan "5.5".

    Contoh:
        format_qty(5.0, "karung")  → "5 karung"
        format_qty(5.5, "kg")      → "5.5 kg"
    """
    if qty is None:
        return f"0 {satuan}".strip()

    # Tampilkan tanpa desimal jika bulat
    if qty == int(qty):
        angka_str = str(int(qty))
    else:
        angka_str = str(qty)

    return f"{angka_str} {satuan}".strip()


def parse_rupiah(teks: str) -> int:
    """
    Mengubah string Rupiah kembali ke integer.
    Berguna saat user mengetik angka dengan format.

    Contoh:
        parse_rupiah("Rp1.500.000")  → 1500000
        parse_rupiah("1.500.000")    → 1500000
        parse_rupiah("1500000")      → 1500000
    """
    # Hapus "Rp", titik pemisah ribuan, dan spasi
    bersih = teks.replace("Rp", "").replace(".", "").replace(",", "").strip()
    try:
        return int(bersih)
    except ValueError:
        return 0


def nama_bulan_tahun(bulan: int, tahun: int) -> str:
    """
    Mengembalikan nama bulan dan tahun.
    Contoh: nama_bulan_tahun(10, 2026) → "Oktober 2026"
    """
    return f"{NAMA_BULAN_ID.get(bulan, str(bulan))} {tahun}"
