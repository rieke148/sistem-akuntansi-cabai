"""
services/transaction_service.py
---------------------------------
Tujuan  : Mengubah input form transaksi menjadi jurnal otomatis.
          Setiap jenis transaksi (penjualan tunai, beli bahan, dll)
          punya fungsi tersendiri yang menghasilkan baris debit/kredit.
Input   : Data transaksi dari views/02_input_transaksi.py (dict).
Output  : Memanggil journal_service.simpan_jurnal() untuk menyimpan.
Dipanggil oleh : views/02_input_transaksi.py

LOGIKA INTI:
  Setiap fungsi di file ini:
  1. Menerima data input (jumlah, akun, tanggal, dll)
  2. Menyusun baris jurnal sesuai pemetaan (lihat PROJECT_BRIEF tabel 1.5)
  3. Memanggil journal_service.simpan_jurnal() untuk menyimpan

PEMETAAN TRANSAKSI → JURNAL:
  Penjualan tunai     : Dr Kas          / Kr Penjualan
  Penjualan tempo     : Dr Piutang      / Kr Penjualan
  Terima piutang      : Dr Kas          / Kr Piutang Usaha
  Setoran modal       : Dr Kas          / Kr Modal Disetor
  Beli tunai          : Dr Persediaan   / Kr Kas
  Beli kredit         : Dr Persediaan   / Kr Utang Usaha
  Bayar upah          : Dr Beban Upah   / Kr Kas
  Biaya operasional   : Dr Beban terkait/ Kr Kas
  Beli aset           : Dr Aset Tetap   / Kr Kas
  Pakai bahan         : Dr Beban Produksi/ Kr Persediaan
  Panen               : Dr Persediaan Hasil / Kr Beban Produksi (HPP panen)
"""

import datetime
import pandas as pd
from database.connection import get_connection
from services.journal_service import simpan_jurnal, generate_nomor_bukti
from services.inventory_service import catat_gerakan_masuk, catat_gerakan_keluar


# ================================================================
# HELPER INTERNAL
# ================================================================

def _label_periode(period_id: int) -> str:
    """Helper: ambil label periode singkat (mis. 'OKT26') dari database."""
    koneksi = get_connection()
    row = koneksi.execute(
        "SELECT tahun, bulan FROM periods WHERE id = ?", (period_id,)
    ).fetchone()
    koneksi.close()
    if not row:
        return "UNKNOWN"
    # Nama bulan singkat (3 huruf kapital)
    nama_bulan_singkat = {
        1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MEI", 6: "JUN",
        7: "JUL", 8: "AGU", 9: "SEP", 10: "OKT", 11: "NOV", 12: "DES",
    }
    kode_bulan = nama_bulan_singkat.get(row["bulan"], str(row["bulan"]))
    kode_tahun = str(row["tahun"])[2:]  # 2026 → "26"
    return f"{kode_bulan}{kode_tahun}"


def _ambil_parameter(nama: str) -> str | None:
    """Helper: ambil nilai parameter dari tabel parameters."""
    koneksi = get_connection()
    row = koneksi.execute(
        "SELECT nilai FROM parameters WHERE kunci = ?", (nama,)
    ).fetchone()
    koneksi.close()
    return row["nilai"] if row else None


def _tambah_hari(tanggal_str: str, hari: int) -> str:
    """Helper: tambah hari ke tanggal, kembalikan string 'YYYY-MM-DD'."""
    tanggal = datetime.datetime.strptime(tanggal_str, "%Y-%m-%d").date()
    return str(tanggal + datetime.timedelta(days=hari))


# ================================================================
# 1. PENJUALAN TUNAI
# ================================================================

def catat_penjualan_tunai(
    period_id: int,
    tanggal: str,
    pelanggan: str,
    jumlah_kg: float,
    harga_per_kg: int,
    akun_kas_id: int,
    akun_penjualan_id: int,
    komoditas: str = "cabai",
    keterangan_tambahan: str = "",
) -> int:
    """
    Mencatat transaksi penjualan tunai.

    Jurnal yang dibuat:
      Debit : Kas
      Kredit: Penjualan

    Args:
        jumlah_kg    : Kuantitas yang dijual (kg).
        harga_per_kg : Harga jual per kg (Rupiah, integer).
        pelanggan    : Nama pelanggan (teks bebas).

    Returns:
        ID journal_entry yang dibuat.
    """
    # Hitung total penjualan (integer Rupiah)
    total = int(jumlah_kg * harga_per_kg)

    keterangan = (
        f"Penjualan {komoditas} tunai ke {pelanggan} "
        f"{jumlah_kg} kg @ Rp{harga_per_kg:,}".replace(",", ".")
    )
    if keterangan_tambahan:
        keterangan += f" - {keterangan_tambahan}"

    # Generate nomor bukti otomatis: KM-OKT26-001
    no_bukti = generate_nomor_bukti("KM", _label_periode(period_id))

    # Susun baris jurnal: Kas (D) | Penjualan (K)
    baris = [
        {"account_id": akun_kas_id, "debit": total, "kredit": 0},
        {"account_id": akun_penjualan_id, "debit": 0, "kredit": total},
    ]

    return simpan_jurnal(
        period_id=period_id,
        tanggal=tanggal,
        no_bukti=no_bukti,
        journal_type="penerimaan_kas",
        keterangan=keterangan,
        baris=baris,
        komoditas=komoditas,
        pihak_terkait=pelanggan,
    )


# ================================================================
# 2. PENJUALAN TEMPO (KREDIT)
# ================================================================

def catat_penjualan_tempo(
    period_id: int,
    tanggal: str,
    customer_id: int,
    pelanggan_nama: str,
    jumlah_kg: float,
    harga_per_kg: int,
    akun_piutang_id: int,
    akun_penjualan_id: int,
    komoditas: str = "cabai",
) -> tuple[int, str]:
    """
    Mencatat penjualan tempo (kredit, jatuh tempo sesuai parameter).

    Jurnal yang dibuat:
      Debit : Piutang Usaha
      Kredit: Penjualan

    Efek samping:
      INSERT ke tabel receivables (piutang baru menunggu pelunasan).

    Returns:
        Tuple (entry_id, no_faktur).
    """
    total = int(jumlah_kg * harga_per_kg)

    # Nomor faktur / bukti penjualan tempo
    no_bukti = generate_nomor_bukti("JL", _label_periode(period_id))

    keterangan = (
        f"Penjualan {komoditas} tempo ke {pelanggan_nama} "
        f"{jumlah_kg} kg @ Rp{harga_per_kg:,}".replace(",", ".")
    )

    baris = [
        {"account_id": akun_piutang_id, "debit": total, "kredit": 0},
        {"account_id": akun_penjualan_id, "debit": 0, "kredit": total},
    ]

    entry_id = simpan_jurnal(
        period_id=period_id, tanggal=tanggal, no_bukti=no_bukti,
        journal_type="penjualan", keterangan=keterangan, baris=baris,
        komoditas=komoditas, pihak_terkait=pelanggan_nama,
    )

    # Hitung jatuh tempo dari parameter (default 7 hari)
    jatuh_tempo_hari = int(_ambil_parameter("jatuh_tempo_piutang_hari") or 7)
    tanggal_jatuh_tempo = _tambah_hari(tanggal, jatuh_tempo_hari)

    # Simpan ke tabel receivables agar bisa dilacak dan dilunasi
    koneksi = get_connection()
    koneksi.execute("""
        INSERT INTO receivables
            (journal_entry_id, customer_id, no_faktur, tanggal_faktur,
             tanggal_jatuh_tempo, jumlah, jumlah_terbayar, status)
        VALUES (?, ?, ?, ?, ?, ?, 0, 'belum_lunas')
    """, (entry_id, customer_id, no_bukti, tanggal, tanggal_jatuh_tempo, total))
    koneksi.commit()
    koneksi.close()

    return entry_id, no_bukti


# ================================================================
# 3. TERIMA PELUNASAN PIUTANG
# ================================================================

def catat_penerimaan_piutang(
    period_id: int,
    receivable_id: int,
    tanggal: str,
    jumlah: int,
    akun_kas_id: int,
    akun_piutang_id: int,
    keterangan_tambahan: str = "",
) -> int:
    """
    Mencatat penerimaan pembayaran piutang dari pelanggan.

    Jurnal yang dibuat:
      Debit : Kas
      Kredit: Piutang Usaha

    Efek samping:
      UPDATE receivables SET jumlah_terbayar, status = 'lunas' WHERE id = receivable_id.

    Args:
        receivable_id : ID baris di tabel receivables.
        jumlah        : Jumlah yang diterima (harus <= sisa piutang).

    Returns:
        ID journal_entry yang dibuat.
    """
    # Ambil info piutang yang akan dilunasi
    koneksi = get_connection()
    row = koneksi.execute("""
        SELECT r.jumlah, r.jumlah_terbayar, r.no_faktur,
               c.nama AS pelanggan_nama
        FROM receivables r
        LEFT JOIN customers c ON r.customer_id = c.id
        WHERE r.id = ?
    """, (receivable_id,)).fetchone()
    koneksi.close()

    if not row:
        raise ValueError(f"Piutang ID {receivable_id} tidak ditemukan.")

    sisa = int(row["jumlah"]) - int(row["jumlah_terbayar"])
    if jumlah > sisa:
        raise ValueError(
            f"Jumlah melebihi sisa piutang. Sisa: Rp{sisa:,}".replace(",", ".")
        )

    pelanggan_nama = row["pelanggan_nama"] or "Pelanggan"
    no_faktur = row["no_faktur"]

    no_bukti = generate_nomor_bukti("KM", _label_periode(period_id))
    keterangan = f"Pelunasan piutang {pelanggan_nama} No.{no_faktur}"
    if keterangan_tambahan:
        keterangan += f" - {keterangan_tambahan}"

    baris = [
        {"account_id": akun_kas_id, "debit": jumlah, "kredit": 0},
        {"account_id": akun_piutang_id, "debit": 0, "kredit": jumlah},
    ]

    entry_id = simpan_jurnal(
        period_id=period_id, tanggal=tanggal, no_bukti=no_bukti,
        journal_type="penerimaan_kas", keterangan=keterangan, baris=baris,
        pihak_terkait=pelanggan_nama,
    )

    # Update status piutang
    jumlah_terbayar_baru = int(row["jumlah_terbayar"]) + jumlah
    status_baru = "lunas" if jumlah_terbayar_baru >= int(row["jumlah"]) else "belum_lunas"

    koneksi = get_connection()
    koneksi.execute("""
        UPDATE receivables
        SET jumlah_terbayar = ?, status = ?
        WHERE id = ?
    """, (jumlah_terbayar_baru, status_baru, receivable_id))
    koneksi.commit()
    koneksi.close()

    return entry_id


# ================================================================
# 4. SETORAN MODAL
# ================================================================

def catat_setoran_modal(
    period_id: int,
    tanggal: str,
    jumlah: int,
    akun_kas_id: int,
    akun_modal_id: int,
    keterangan: str = "Setoran modal pemilik",
) -> int:
    """
    Mencatat setoran modal dari pemilik usaha.

    Jurnal yang dibuat:
      Debit : Kas
      Kredit: Modal Disetor

    Returns:
        ID journal_entry yang dibuat.
    """
    no_bukti = generate_nomor_bukti("KM", _label_periode(period_id))

    baris = [
        {"account_id": akun_kas_id, "debit": jumlah, "kredit": 0},
        {"account_id": akun_modal_id, "debit": 0, "kredit": jumlah},
    ]

    return simpan_jurnal(
        period_id=period_id, tanggal=tanggal, no_bukti=no_bukti,
        journal_type="penerimaan_kas", keterangan=keterangan, baris=baris,
    )


# ================================================================
# 5. PEMBELIAN BAHAN TUNAI
# ================================================================

def catat_pembelian_tunai(
    period_id: int,
    tanggal: str,
    supplier_nama: str,
    item_id: int,
    qty: float,
    harga_satuan: int,
    akun_persediaan_id: int,
    akun_kas_id: int,
    keterangan: str = "",
) -> int:
    """
    Mencatat pembelian bahan tunai dari supplier.

    Jurnal yang dibuat:
      Debit : Persediaan (bahan)
      Kredit: Kas

    Efek samping:
      INSERT ke inventory_movements (bahan masuk, hitung rata-rata bergerak).

    Args:
        item_id      : ID item dari tabel items (untuk kartu persediaan).
        qty          : Kuantitas yang dibeli.
        harga_satuan : Harga per unit (Rupiah, integer).

    Returns:
        ID journal_entry yang dibuat.
    """
    jumlah = int(qty * harga_satuan)
    no_bukti = generate_nomor_bukti("KK", _label_periode(period_id))
    ket = keterangan or f"Beli bahan tunai - {supplier_nama}"

    baris = [
        {"account_id": akun_persediaan_id, "debit": jumlah, "kredit": 0},
        {"account_id": akun_kas_id, "debit": 0, "kredit": jumlah},
    ]

    entry_id = simpan_jurnal(
        period_id=period_id, tanggal=tanggal, no_bukti=no_bukti,
        journal_type="pengeluaran_kas", keterangan=ket, baris=baris,
        pihak_terkait=supplier_nama,
    )

    # Catat gerakan persediaan masuk (rata-rata bergerak dihitung otomatis)
    catat_gerakan_masuk(
        item_id=item_id, tanggal=tanggal, qty=qty,
        harga_satuan=harga_satuan, keterangan=ket,
        journal_entry_id=entry_id,
    )

    return entry_id


# ================================================================
# 6. PEMBELIAN KREDIT (HUTANG DAGANG)
# ================================================================

def catat_pembelian_kredit(
    period_id: int,
    tanggal: str,
    supplier_nama: str,
    item_id: int,
    qty: float,
    harga_satuan: int,
    akun_persediaan_id: int,
    akun_utang_id: int,
    keterangan: str = "",
) -> int:
    """
    Mencatat pembelian bahan secara kredit (menambah hutang usaha).

    Jurnal yang dibuat:
      Debit : Persediaan
      Kredit: Utang Usaha

    Efek samping:
      INSERT ke inventory_movements (bahan masuk).

    Returns:
        ID journal_entry yang dibuat.
    """
    jumlah = int(qty * harga_satuan)
    no_bukti = generate_nomor_bukti("PB", _label_periode(period_id))
    ket = keterangan or f"Beli kredit dari {supplier_nama}"

    baris = [
        {"account_id": akun_persediaan_id, "debit": jumlah, "kredit": 0},
        {"account_id": akun_utang_id, "debit": 0, "kredit": jumlah},
    ]

    entry_id = simpan_jurnal(
        period_id=period_id, tanggal=tanggal, no_bukti=no_bukti,
        journal_type="pembelian", keterangan=ket, baris=baris,
        pihak_terkait=supplier_nama,
    )

    # Catat gerakan persediaan masuk
    catat_gerakan_masuk(
        item_id=item_id, tanggal=tanggal, qty=qty,
        harga_satuan=harga_satuan, keterangan=ket,
        journal_entry_id=entry_id,
    )

    return entry_id


# ================================================================
# 7. PEMAKAIAN BAHAN KE BLOK LAHAN
# ================================================================

def catat_pemakaian_bahan(
    period_id: int,
    tanggal: str,
    item_id: int,
    qty: float,
    akun_beban_id: int,
    akun_persediaan_id: int,
    blok_nama: str = "",
    keterangan: str = "",
    komoditas: str = "cabai",
) -> int:
    """
    Mencatat pemakaian bahan produksi ke blok lahan (Jurnal Umum).

    Jurnal yang dibuat:
      Debit : Beban Bahan Produksi
      Kredit: Persediaan

    Efek samping:
      INSERT ke inventory_movements (bahan keluar, dihitung dengan harga rata-rata bergerak).

    Args:
        item_id  : ID item bahan yang dipakai.
        qty      : Kuantitas yang dipakai.
        blok_nama: Nama blok lahan (untuk keterangan).

    Returns:
        ID journal_entry yang dibuat.
    """
    no_bukti = generate_nomor_bukti("JU", _label_periode(period_id))

    # Hitung nilai keluar berdasarkan saldo persediaan (rata-rata bergerak)
    # catat_gerakan_keluar akan raise ValueError jika saldo tidak cukup
    hasil_keluar = catat_gerakan_keluar(
        item_id=item_id, tanggal=tanggal, qty=qty,
        keterangan=keterangan or f"Pemakaian bahan ke blok {blok_nama}",
    )
    total_nilai = hasil_keluar["total_keluar"]

    ket = keterangan or f"Pemakaian bahan produksi ke blok {blok_nama}"
    if blok_nama and not keterangan:
        ket = f"Pemakaian bahan ke blok {blok_nama}"

    baris = [
        {"account_id": akun_beban_id, "debit": total_nilai, "kredit": 0},
        {"account_id": akun_persediaan_id, "debit": 0, "kredit": total_nilai},
    ]

    entry_id = simpan_jurnal(
        period_id=period_id, tanggal=tanggal, no_bukti=no_bukti,
        journal_type="umum", keterangan=ket, baris=baris, komoditas=komoditas,
    )

    # Update journal_entry_id di gerakan keluar yang baru dibuat
    # SQLite tidak mendukung UPDATE ... ORDER BY ... LIMIT, gunakan subquery
    koneksi = get_connection()
    koneksi.execute("""
        UPDATE inventory_movements
        SET journal_entry_id = ?
        WHERE id = (
            SELECT id FROM inventory_movements
            WHERE item_id = ? AND tipe_gerakan = 'keluar'
            ORDER BY id DESC LIMIT 1
        )
    """, (entry_id, item_id))
    koneksi.commit()
    koneksi.close()

    return entry_id


# ================================================================
# 8. PENCATATAN HASIL PANEN
# ================================================================

def catat_panen(
    period_id: int,
    tanggal: str,
    item_panen_id: int,
    jumlah_kg: float,
    harga_estimasi_per_kg: int,
    akun_persediaan_panen_id: int,
    akun_hpp_panen_id: int,
    blok_nama: str = "",
    komoditas: str = "cabai",
    keterangan: str = "",
) -> int:
    """
    Mencatat hasil panen masuk ke persediaan (Jurnal Umum).

    Panen adalah perpindahan "nilai produksi" menjadi "persediaan hasil".
    Jurnal yang dibuat:
      Debit : Persediaan Cabai Rawit (1304 / 1305)
      Kredit: Beban Pokok Produksi / HPP Panen (akun lawan)

    Efek samping:
      INSERT ke inventory_movements (panen masuk sebagai item hasil panen).

    Args:
        item_panen_id         : ID item hasil panen (mis. Cabai Rawit Merah).
        jumlah_kg             : Hasil panen dalam kg.
        harga_estimasi_per_kg : Estimasi harga pokok per kg (untuk nilai persediaan).
        blok_nama             : Blok lahan asal panen.

    Returns:
        ID journal_entry yang dibuat.
    """
    total_nilai = int(jumlah_kg * harga_estimasi_per_kg)
    no_bukti = generate_nomor_bukti("JU", _label_periode(period_id))
    ket = keterangan or f"Panen cabai {jumlah_kg} kg dari blok {blok_nama}"

    baris = [
        {"account_id": akun_persediaan_panen_id, "debit": total_nilai, "kredit": 0},
        {"account_id": akun_hpp_panen_id, "debit": 0, "kredit": total_nilai},
    ]

    entry_id = simpan_jurnal(
        period_id=period_id, tanggal=tanggal, no_bukti=no_bukti,
        journal_type="umum", keterangan=ket, baris=baris, komoditas=komoditas,
    )

    # Catat gerakan persediaan panen masuk
    catat_gerakan_masuk(
        item_id=item_panen_id, tanggal=tanggal, qty=jumlah_kg,
        harga_satuan=harga_estimasi_per_kg, keterangan=ket,
        journal_entry_id=entry_id,
    )

    return entry_id


# ================================================================
# 9. BIAYA OPERASIONAL (LISTRIK, BBM, SEWA TRAKTOR)
# ================================================================

def catat_biaya_operasional(
    period_id: int,
    tanggal: str,
    jenis_biaya: str,
    jumlah: int,
    akun_beban_id: int,
    akun_kas_id: int,
    keterangan: str = "",
) -> int:
    """
    Mencatat biaya operasional (listrik, BBM, sewa traktor, dll).

    Jurnal yang dibuat:
      Debit : Beban [jenis_biaya]
      Kredit: Kas

    Args:
        jenis_biaya : Deskripsi singkat (mis. 'listrik', 'BBM pengiriman').
        jumlah      : Total biaya (Rupiah, integer).

    Returns:
        ID journal_entry yang dibuat.
    """
    no_bukti = generate_nomor_bukti("KK", _label_periode(period_id))
    ket = keterangan or f"Biaya {jenis_biaya}"

    baris = [
        {"account_id": akun_beban_id, "debit": jumlah, "kredit": 0},
        {"account_id": akun_kas_id, "debit": 0, "kredit": jumlah},
    ]

    return simpan_jurnal(
        period_id=period_id, tanggal=tanggal, no_bukti=no_bukti,
        journal_type="pengeluaran_kas", keterangan=ket, baris=baris,
    )


# ================================================================
# 10. PEMBELIAN ASET TETAP TUNAI
# ================================================================

def catat_pembelian_aset(
    period_id: int,
    tanggal: str,
    nama_aset: str,
    jumlah: int,
    akun_aset_id: int,
    akun_kas_id: int,
    keterangan: str = "",
) -> int:
    """
    Mencatat pembelian aset tetap secara tunai.

    Jurnal yang dibuat:
      Debit : Aset Tetap (sesuai akun aset)
      Kredit: Kas

    Returns:
        ID journal_entry yang dibuat.
    """
    no_bukti = generate_nomor_bukti("KK", _label_periode(period_id))
    ket = keterangan or f"Pembelian aset - {nama_aset}"

    baris = [
        {"account_id": akun_aset_id, "debit": jumlah, "kredit": 0},
        {"account_id": akun_kas_id, "debit": 0, "kredit": jumlah},
    ]

    return simpan_jurnal(
        period_id=period_id, tanggal=tanggal, no_bukti=no_bukti,
        journal_type="pengeluaran_kas", keterangan=ket, baris=baris,
        pihak_terkait=nama_aset,
    )


# ================================================================
# FUNGSI BANTU: PRATINJAU JURNAL (TANPA SIMPAN)
# ================================================================

def buat_baris_pratinjau(
    baris: list[dict],
    account_ids: list[int],
) -> pd.DataFrame:
    """
    Membuat DataFrame pratinjau jurnal tanpa menyimpan ke database.
    Digunakan oleh views/02_input_transaksi.py untuk menampilkan
    pratinjau sebelum pengguna menekan tombol Simpan.

    Args:
        baris       : List dict [{account_id, debit, kredit}, ...].
        account_ids : List ID akun yang perlu dicari namanya di DB.

    Returns:
        DataFrame dengan kolom: Akun, Debit, Kredit.
        Baris terakhir berisi TOTAL Debit dan Kredit.
    """
    # Ambil nama akun dari database sekaligus
    if not account_ids:
        return pd.DataFrame(columns=["Akun", "Debit", "Kredit"])

    placeholders = ",".join(["?"] * len(account_ids))
    koneksi = get_connection()
    rows = koneksi.execute(
        f"SELECT id, kode_akun, nama_akun FROM accounts WHERE id IN ({placeholders})",
        account_ids,
    ).fetchall()
    koneksi.close()

    # Buat map id → info akun
    peta_akun = {r["id"]: {"kode": r["kode_akun"], "nama": r["nama_akun"]} for r in rows}

    pratinjau = []
    total_debit = 0
    total_kredit = 0

    for b in baris:
        akun_info = peta_akun.get(b["account_id"], {"kode": "?", "nama": "?"})
        debit = int(b.get("debit", 0))
        kredit = int(b.get("kredit", 0))
        total_debit += debit
        total_kredit += kredit
        pratinjau.append({
            "Akun": f"{akun_info['kode']} - {akun_info['nama']}",
            "Debit": debit,
            "Kredit": kredit,
        })

    # Tambah baris TOTAL di bawah
    pratinjau.append({
        "Akun": "**TOTAL**",
        "Debit": total_debit,
        "Kredit": total_kredit,
    })

    return pd.DataFrame(pratinjau)


def ambil_piutang_terbuka() -> pd.DataFrame:
    """
    Mengambil semua piutang yang belum lunas untuk form Terima Pelunasan Piutang.

    Returns:
        DataFrame: id, pelanggan, no_faktur, tanggal_faktur, jatuh_tempo,
                   jumlah_piutang, jumlah_terbayar, sisa_piutang.
    """
    koneksi = get_connection()
    df = pd.read_sql_query("""
        SELECT
            r.id,
            COALESCE(c.nama, 'Tidak diketahui') AS pelanggan,
            r.no_faktur,
            r.tanggal_faktur,
            r.tanggal_jatuh_tempo,
            r.jumlah,
            r.jumlah_terbayar,
            (r.jumlah - r.jumlah_terbayar) AS sisa_piutang
        FROM receivables r
        LEFT JOIN customers c ON r.customer_id = c.id
        WHERE r.status != 'lunas'
        ORDER BY r.tanggal_jatuh_tempo ASC
    """, koneksi)
    koneksi.close()
    return df
