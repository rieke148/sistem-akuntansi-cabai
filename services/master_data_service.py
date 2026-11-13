"""
services/master_data_service.py
--------------------------------
Tujuan  : Semua fungsi CRUD (Create, Read, Update, Delete) untuk
          entitas Master Data. Tidak ada kode Streamlit di sini —
          hanya logika database.
Input   : Data dari views/01_master_data.py (dict/parameter).
Output  : Data berhasil disimpan/diubah, atau pesan error.
Dipanggil oleh : views/01_master_data.py

ENTITAS YANG DIKELOLA:
  accounts, customers, suppliers, items, employees,
  fixed_assets, blok_lahan, opening_balances, periods, parameters
"""

import sqlite3
import pandas as pd
from database.connection import get_connection
from utils.formatting import nama_bulan_tahun


# ================================================================
# HELPER UMUM
# ================================================================
def _ambil_semua(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Jalankan SELECT dan kembalikan DataFrame."""
    koneksi = get_connection()
    df = pd.read_sql_query(sql, koneksi, params=params)
    koneksi.close()
    return df


def _eksekusi(sql: str, params: tuple = ()) -> int:
    """
    Jalankan INSERT/UPDATE/DELETE.
    Mengembalikan lastrowid (berguna untuk INSERT).
    Raise exception jika gagal — ditangkap di views/.
    """
    koneksi = get_connection()
    cursor = koneksi.execute(sql, params)
    koneksi.commit()
    rowid = cursor.lastrowid
    koneksi.close()
    return rowid


# ================================================================
# BAGAN AKUN (Chart of Accounts)
# ================================================================
KATEGORI_AKUN = ["Aset", "Liabilitas", "Ekuitas",
                 "Pendapatan", "Beban Produksi", "Beban Operasional"]
SALDO_NORMAL = ["Debit", "Kredit"]


def ambil_semua_akun(kategori: str | None = None) -> pd.DataFrame:
    """Ambil semua akun, opsional filter per kategori."""
    sql = """
        SELECT id, kode_akun, nama_akun, kategori, saldo_normal,
               is_kontra, aktif
        FROM accounts
        {}
        ORDER BY kode_akun
    """.format("WHERE kategori = ?" if kategori else "")
    params = (kategori,) if kategori else ()
    return _ambil_semua(sql, params)


def tambah_akun(
    kode_akun: str,
    nama_akun: str,
    kategori: str,
    saldo_normal: str,
    is_kontra: bool = False,
) -> None:
    """
    Menambah akun baru ke COA.

    Validasi:
      - kode_akun harus unik
      - kategori harus valid
      - saldo_normal harus Debit atau Kredit
    """
    if not kode_akun.strip():
        raise ValueError("Kode akun tidak boleh kosong.")
    if not nama_akun.strip():
        raise ValueError("Nama akun tidak boleh kosong.")
    if kategori not in KATEGORI_AKUN:
        raise ValueError(f"Kategori tidak valid: {kategori}")
    if saldo_normal not in SALDO_NORMAL:
        raise ValueError("Saldo normal harus 'Debit' atau 'Kredit'.")

    _eksekusi(
        "INSERT INTO accounts (kode_akun, nama_akun, kategori, saldo_normal, is_kontra) "
        "VALUES (?, ?, ?, ?, ?)",
        (kode_akun.strip(), nama_akun.strip(), kategori, saldo_normal, int(is_kontra)),
    )


def ubah_akun(
    account_id: int,
    nama_akun: str,
    kategori: str,
    saldo_normal: str,
    is_kontra: bool,
    aktif: bool,
) -> None:
    """Mengubah data akun yang sudah ada (kode_akun tidak bisa diubah)."""
    if not nama_akun.strip():
        raise ValueError("Nama akun tidak boleh kosong.")
    _eksekusi(
        "UPDATE accounts SET nama_akun=?, kategori=?, saldo_normal=?, is_kontra=?, aktif=? "
        "WHERE id=?",
        (nama_akun.strip(), kategori, saldo_normal, int(is_kontra), int(aktif), account_id),
    )


def nonaktifkan_akun(account_id: int) -> None:
    """Menonaktifkan akun (tidak dihapus agar histori tetap ada)."""
    # Cek apakah akun sudah dipakai di journal_lines
    koneksi = get_connection()
    pemakaian = koneksi.execute(
        "SELECT COUNT(*) FROM journal_lines WHERE account_id = ?", (account_id,)
    ).fetchone()[0]
    koneksi.close()
    if pemakaian > 0:
        raise ValueError(
            f"Akun tidak bisa dinonaktifkan — sudah dipakai di {pemakaian} baris jurnal."
        )
    _eksekusi("UPDATE accounts SET aktif=0 WHERE id=?", (account_id,))


# ================================================================
# PELANGGAN
# ================================================================
TIPE_PELANGGAN = ["restoran", "supermarket", "umkm", "umum"]


def ambil_semua_pelanggan() -> pd.DataFrame:
    return _ambil_semua(
        "SELECT id, nama, tipe, telepon, alamat, aktif FROM customers ORDER BY nama"
    )


def tambah_pelanggan(nama: str, tipe: str, telepon: str, alamat: str) -> None:
    """Menambah pelanggan baru."""
    if not nama.strip():
        raise ValueError("Nama pelanggan tidak boleh kosong.")
    _eksekusi(
        "INSERT INTO customers (nama, tipe, telepon, alamat) VALUES (?, ?, ?, ?)",
        (nama.strip(), tipe, telepon.strip(), alamat.strip()),
    )


def ubah_pelanggan(
    customer_id: int, nama: str, tipe: str, telepon: str, alamat: str, aktif: bool
) -> None:
    """Mengubah data pelanggan."""
    if not nama.strip():
        raise ValueError("Nama pelanggan tidak boleh kosong.")
    _eksekusi(
        "UPDATE customers SET nama=?, tipe=?, telepon=?, alamat=?, aktif=? WHERE id=?",
        (nama.strip(), tipe, telepon.strip(), alamat.strip(), int(aktif), customer_id),
    )


# ================================================================
# SUPPLIER
# ================================================================
def ambil_semua_supplier() -> pd.DataFrame:
    return _ambil_semua(
        "SELECT id, nama, telepon, alamat, aktif FROM suppliers ORDER BY nama"
    )


def tambah_supplier(nama: str, telepon: str, alamat: str) -> None:
    if not nama.strip():
        raise ValueError("Nama supplier tidak boleh kosong.")
    _eksekusi(
        "INSERT INTO suppliers (nama, telepon, alamat) VALUES (?, ?, ?)",
        (nama.strip(), telepon.strip(), alamat.strip()),
    )


def ubah_supplier(
    supplier_id: int, nama: str, telepon: str, alamat: str, aktif: bool
) -> None:
    if not nama.strip():
        raise ValueError("Nama supplier tidak boleh kosong.")
    _eksekusi(
        "UPDATE suppliers SET nama=?, telepon=?, alamat=?, aktif=? WHERE id=?",
        (nama.strip(), telepon.strip(), alamat.strip(), int(aktif), supplier_id),
    )


# ================================================================
# ITEM PERSEDIAAN
# ================================================================
TIPE_ITEM = ["bahan", "hasil_panen"]
KOMODITAS_ITEM = ["cabai", "selada", "melon"]


def ambil_semua_item() -> pd.DataFrame:
    return _ambil_semua("""
        SELECT i.id, i.kode_item, i.nama_item, i.satuan, i.tipe, i.komoditas,
               i.account_id, a.kode_akun as akun_persediaan, i.aktif
        FROM items i
        LEFT JOIN accounts a ON i.account_id = a.id
        ORDER BY i.tipe, i.kode_item
    """)


def tambah_item(
    kode_item: str,
    nama_item: str,
    satuan: str,
    tipe: str,
    komoditas: str,
    account_id: int | None,
) -> None:
    if not kode_item.strip():
        raise ValueError("Kode item tidak boleh kosong.")
    if not nama_item.strip():
        raise ValueError("Nama item tidak boleh kosong.")
    _eksekusi(
        "INSERT INTO items (kode_item, nama_item, satuan, tipe, komoditas, account_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (kode_item.strip(), nama_item.strip(), satuan.strip(), tipe, komoditas, account_id),
    )


def ubah_item(
    item_id: int,
    nama_item: str,
    satuan: str,
    tipe: str,
    komoditas: str,
    account_id: int | None,
    aktif: bool,
) -> None:
    _eksekusi(
        "UPDATE items SET nama_item=?, satuan=?, tipe=?, komoditas=?, account_id=?, aktif=? "
        "WHERE id=?",
        (nama_item.strip(), satuan.strip(), tipe, komoditas, account_id, int(aktif), item_id),
    )


def hapus_item(item_id: int) -> None:
    """
    Menghapus item persediaan secara permanen jika belum memiliki riwayat stok.

    Item yang sudah memiliki pergerakan persediaan tidak boleh dihapus karena
    riwayat tersebut menjadi dasar audit kartu stok. Nonaktifkan item tersebut
    melalui form Edit Item agar histori tetap tersimpan.

    Args:
        item_id: ID item yang akan dihapus.

    Raises:
        ValueError: Jika item tidak ditemukan atau sudah memiliki riwayat stok.
    """
    if item_id <= 0:
        raise ValueError("Item yang dipilih tidak valid.")

    koneksi = get_connection()
    try:
        item = koneksi.execute(
            "SELECT kode_item, nama_item FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()

        if item is None:
            raise ValueError("Item yang ingin dihapus tidak ditemukan.")

        jumlah_riwayat = koneksi.execute(
            "SELECT COUNT(*) FROM inventory_movements WHERE item_id = ?",
            (item_id,),
        ).fetchone()[0]

        if jumlah_riwayat > 0:
            raise ValueError(
                f"Item '{item['kode_item']} - {item['nama_item']}' memiliki "
                f"{jumlah_riwayat} riwayat pergerakan stok sehingga tidak dapat "
                "dihapus permanen. Gunakan Edit Item lalu hilangkan centang "
                "'Aktif?' agar item tidak digunakan lagi tanpa menghapus histori."
            )

        cursor = koneksi.execute(
            "DELETE FROM items WHERE id = ?",
            (item_id,),
        )
        if cursor.rowcount != 1:
            raise ValueError("Item gagal dihapus karena data sudah berubah.")

        koneksi.commit()

    except sqlite3.IntegrityError as error:
        koneksi.rollback()
        raise ValueError(
            "Item tidak dapat dihapus karena masih terhubung dengan data lain. "
            "Nonaktifkan item agar riwayat tetap aman."
        ) from error
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()


# ================================================================
# PEKERJA
# ================================================================
TIPE_PEKERJA = ["tetap", "tambahan"]


def ambil_semua_pekerja() -> pd.DataFrame:
    return _ambil_semua(
        "SELECT id, nama, tipe_pekerja, upah_harian, komoditas, aktif "
        "FROM employees ORDER BY nama"
    )


def tambah_pekerja(
    nama: str, tipe_pekerja: str, upah_harian: int, komoditas: str
) -> None:
    if not nama.strip():
        raise ValueError("Nama pekerja tidak boleh kosong.")
    if upah_harian <= 0:
        raise ValueError("Upah harian harus lebih dari 0.")
    _eksekusi(
        "INSERT INTO employees (nama, tipe_pekerja, upah_harian, komoditas) "
        "VALUES (?, ?, ?, ?)",
        (nama.strip(), tipe_pekerja, upah_harian, komoditas),
    )


def ubah_pekerja(
    employee_id: int,
    nama: str,
    tipe_pekerja: str,
    upah_harian: int,
    komoditas: str,
    aktif: bool,
) -> None:
    if not nama.strip():
        raise ValueError("Nama pekerja tidak boleh kosong.")
    if upah_harian <= 0:
        raise ValueError("Upah harian harus lebih dari 0.")
    _eksekusi(
        "UPDATE employees SET nama=?, tipe_pekerja=?, upah_harian=?, komoditas=?, aktif=? "
        "WHERE id=?",
        (nama.strip(), tipe_pekerja, upah_harian, komoditas, int(aktif), employee_id),
    )


# ================================================================
# ASET TETAP
# ================================================================
KATEGORI_ASET = ["Tanah", "Bangunan", "Kendaraan", "Komputer", "Peralatan", "Perlengkapan"]


def ambil_semua_aset_tetap() -> pd.DataFrame:
    return _ambil_semua("""
        SELECT fa.id, fa.kode_aset, fa.nama_aset, fa.kategori_aset,
               fa.tanggal_perolehan, fa.harga_perolehan, fa.nilai_residu,
               fa.umur_ekonomis_tahun, fa.jumlah_unit, fa.is_disusutkan,
               a1.kode_akun as akun_aset, a2.kode_akun as akun_akumulasi,
               fa.aktif, fa.keterangan
        FROM fixed_assets fa
        LEFT JOIN accounts a1 ON fa.account_id = a1.id
        LEFT JOIN accounts a2 ON fa.account_akum_id = a2.id
        ORDER BY fa.kategori_aset, fa.kode_aset
    """)


def tambah_aset_tetap(
    kode_aset: str,
    nama_aset: str,
    kategori_aset: str,
    tanggal_perolehan: str,
    harga_perolehan: int,
    nilai_residu: int,
    umur_ekonomis_tahun: int,
    jumlah_unit: int,
    account_id: int | None,
    account_akum_id: int | None,
    keterangan: str = "",
) -> None:
    """
    Menambah aset tetap baru.
    - Tanah: is_disusutkan otomatis False, umur & residu = 0.
    - Aset lain: is_disusutkan = True.
    """
    if not kode_aset.strip():
        raise ValueError("Kode aset tidak boleh kosong.")
    if harga_perolehan <= 0:
        raise ValueError("Harga perolehan harus lebih dari 0.")
    if nilai_residu < 0:
        raise ValueError("Nilai residu tidak boleh negatif.")
    if nilai_residu >= harga_perolehan:
        raise ValueError("Nilai residu harus lebih kecil dari harga perolehan.")

    # Tanah tidak disusutkan
    is_disusutkan = 0 if kategori_aset == "Tanah" else 1

    _eksekusi(
        """INSERT INTO fixed_assets
           (kode_aset, nama_aset, kategori_aset, tanggal_perolehan,
            harga_perolehan, nilai_residu, umur_ekonomis_tahun, jumlah_unit,
            is_disusutkan, account_id, account_akum_id, keterangan)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (kode_aset.strip(), nama_aset.strip(), kategori_aset, tanggal_perolehan,
         harga_perolehan, nilai_residu, umur_ekonomis_tahun, jumlah_unit,
         is_disusutkan, account_id, account_akum_id, keterangan),
    )


def ubah_aset_tetap(
    asset_id: int,
    nama_aset: str,
    tanggal_perolehan: str,
    harga_perolehan: int,
    nilai_residu: int,
    umur_ekonomis_tahun: int,
    jumlah_unit: int,
    account_id: int | None,
    account_akum_id: int | None,
    aktif: bool,
    keterangan: str = "",
) -> None:
    """Mengubah data aset tetap — kode_aset dan kategori tidak bisa diubah."""
    if harga_perolehan <= 0:
        raise ValueError("Harga perolehan harus lebih dari 0.")
    if nilai_residu < 0:
        raise ValueError("Nilai residu tidak boleh negatif.")
    _eksekusi(
        """UPDATE fixed_assets SET
           nama_aset=?, tanggal_perolehan=?, harga_perolehan=?, nilai_residu=?,
           umur_ekonomis_tahun=?, jumlah_unit=?, account_id=?, account_akum_id=?,
           aktif=?, keterangan=?
           WHERE id=?""",
        (nama_aset.strip(), tanggal_perolehan, harga_perolehan, nilai_residu,
         umur_ekonomis_tahun, jumlah_unit, account_id, account_akum_id,
         int(aktif), keterangan, asset_id),
    )


def hitung_penyusutan_preview(
    harga: int, residu: int, umur_tahun: int, jumlah_unit: int
) -> dict:
    """
    Menghitung preview penyusutan untuk ditampilkan saat user isi form aset.
    Memudahkan user verifikasi angka sebelum simpan.

    Returns:
        Dict dengan kunci: dasar, penyusutan_per_bulan, penyusutan_per_tahun.
    """
    dasar = (harga - residu) * jumlah_unit
    umur_bulan = umur_tahun * 12
    per_bulan = dasar // umur_bulan if umur_bulan > 0 else 0
    per_tahun = per_bulan * 12
    return {
        "dasar_penyusutan": dasar,
        "penyusutan_per_bulan": per_bulan,
        "penyusutan_per_tahun": per_tahun,
    }


# ================================================================
# BLOK LAHAN
# ================================================================
def ambil_semua_blok() -> pd.DataFrame:
    return _ambil_semua(
        "SELECT id, kode_blok, jumlah_pohon, tanggal_tanam, komoditas, "
        "luas_m2, jarak_tanam_cm, keterangan, aktif FROM blok_lahan ORDER BY kode_blok"
    )


def tambah_blok(
    kode_blok: str,
    jumlah_pohon: int,
    tanggal_tanam: str,
    komoditas: str,
    luas_m2: float,
    jarak_tanam_cm: float,
    keterangan: str = "",
) -> None:
    if not kode_blok.strip():
        raise ValueError("Kode blok tidak boleh kosong.")
    _eksekusi(
        """INSERT INTO blok_lahan
           (kode_blok, jumlah_pohon, tanggal_tanam, komoditas,
            luas_m2, jarak_tanam_cm, keterangan)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (kode_blok.strip().upper(), jumlah_pohon, tanggal_tanam,
         komoditas, luas_m2, jarak_tanam_cm, keterangan),
    )


def ubah_blok(
    blok_id: int,
    jumlah_pohon: int,
    tanggal_tanam: str,
    luas_m2: float,
    jarak_tanam_cm: float,
    keterangan: str,
    aktif: bool,
) -> None:
    _eksekusi(
        """UPDATE blok_lahan SET jumlah_pohon=?, tanggal_tanam=?,
           luas_m2=?, jarak_tanam_cm=?, keterangan=?, aktif=?
           WHERE id=?""",
        (jumlah_pohon, tanggal_tanam, luas_m2, jarak_tanam_cm, keterangan, int(aktif), blok_id),
    )


# ================================================================
# SALDO AWAL
# ================================================================
def ambil_saldo_awal(period_id: int) -> pd.DataFrame:
    return _ambil_semua("""
        SELECT ob.id, a.kode_akun, a.nama_akun, a.kategori, a.saldo_normal,
               ob.saldo_debit, ob.saldo_kredit, ob.catatan
        FROM opening_balances ob
        JOIN accounts a ON ob.account_id = a.id
        WHERE ob.period_id = ?
        ORDER BY a.kode_akun
    """, (period_id,))


def simpan_saldo_awal(
    period_id: int,
    account_id: int,
    saldo_debit: int,
    saldo_kredit: int,
    catatan: str = "",
) -> None:
    """
    Menyimpan atau mengupdate saldo awal satu akun.
    Pakai INSERT OR REPLACE agar idempotent (aman dipanggil ulang).
    """
    if saldo_debit < 0 or saldo_kredit < 0:
        raise ValueError("Saldo tidak boleh negatif.")
    if saldo_debit > 0 and saldo_kredit > 0:
        raise ValueError("Saldo debit dan kredit tidak boleh keduanya > 0 untuk satu akun.")

    # Cek apakah sudah ada
    koneksi = get_connection()
    ada = koneksi.execute(
        "SELECT id FROM opening_balances WHERE period_id=? AND account_id=?",
        (period_id, account_id)
    ).fetchone()
    koneksi.close()

    if ada:
        _eksekusi(
            "UPDATE opening_balances SET saldo_debit=?, saldo_kredit=?, catatan=? "
            "WHERE period_id=? AND account_id=?",
            (saldo_debit, saldo_kredit, catatan, period_id, account_id),
        )
    else:
        _eksekusi(
            "INSERT INTO opening_balances (period_id, account_id, saldo_debit, saldo_kredit, catatan) "
            "VALUES (?, ?, ?, ?, ?)",
            (period_id, account_id, saldo_debit, saldo_kredit, catatan),
        )


def hapus_saldo_awal(saldo_id: int) -> None:
    """Menghapus saldo awal satu akun."""
    _eksekusi("DELETE FROM opening_balances WHERE id=?", (saldo_id,))


def validasi_saldo_awal_seimbang(period_id: int) -> tuple[bool, int, int]:
    """
    Memvalidasi apakah total saldo awal seimbang (total debit == total kredit).
    Penting sebelum mulai input transaksi.

    Returns:
        (seimbang, total_debit, total_kredit)
    """
    df = ambil_saldo_awal(period_id)
    if df.empty:
        return True, 0, 0
    total_d = int(df["saldo_debit"].sum())
    total_k = int(df["saldo_kredit"].sum())
    return total_d == total_k, total_d, total_k


# ================================================================
# PERIODE
# ================================================================
def ambil_semua_periode() -> pd.DataFrame:
    return _ambil_semua("SELECT id, nama_bulan, tahun, bulan, status FROM periods ORDER BY tahun, bulan")


def tambah_periode(tahun: int, bulan: int) -> None:
    """Menambah periode baru. Hanya bisa jika periode tersebut belum ada."""
    nama = nama_bulan_tahun(bulan, tahun)
    _eksekusi(
        "INSERT INTO periods (tahun, bulan, nama_bulan) VALUES (?, ?, ?)",
        (tahun, bulan, nama),
    )


# ================================================================
# PARAMETER OPERASIONAL
# ================================================================
def ambil_semua_parameter() -> pd.DataFrame:
    return _ambil_semua("SELECT id, kunci, nilai, satuan, catatan FROM parameters ORDER BY kunci")


def ubah_parameter(param_id: int, nilai_baru: str) -> None:
    """Mengubah nilai satu parameter."""
    if not nilai_baru.strip():
        raise ValueError("Nilai parameter tidak boleh kosong.")
    _eksekusi(
        "UPDATE parameters SET nilai=? WHERE id=?",
        (nilai_baru.strip(), param_id),
    )


def ambil_nilai_parameter(kunci: str, default: str = "0") -> str:
    """
    Mengambil nilai satu parameter berdasarkan kunci.
    Dipakai oleh service lain yang butuh tarif upah, harga, dsb.

    Contoh: ambil_nilai_parameter("upah_tetap_harian") → "90000"
    """
    koneksi = get_connection()
    row = koneksi.execute(
        "SELECT nilai FROM parameters WHERE kunci=?", (kunci,)
    ).fetchone()
    koneksi.close()
    return row["nilai"] if row else default
