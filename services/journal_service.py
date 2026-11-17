"""
services/journal_service.py
----------------------------
Tujuan  : Membuat, memvalidasi, dan mengambil data jurnal.
          Ini adalah service inti — semua operasi jurnal lewat sini.
Input   : Data transaksi (dict) dari views/ atau transaction_service.
Output  : ID jurnal yang dibuat, atau DataFrame jurnal untuk ditampilkan.
Dipanggil oleh : services/transaction_service.py, views/04_jurnal_umum.py

ATURAN WAJIB:
  Setiap jurnal HARUS seimbang (total debit == total kredit).
  Jika tidak seimbang, fungsi membatalkan operasi dan raise ValueError.
"""

import sqlite3
import pandas as pd
from decimal import Decimal
from database.connection import get_connection


def validasi_jurnal_seimbang(baris: list[dict]) -> tuple[int, int]:
    """
    Memvalidasi bahwa total debit sama dengan total kredit.

    Args:
        baris : List baris jurnal, setiap dict berisi 'debit' dan 'kredit'.

    Returns:
        Tuple (total_debit, total_kredit).

    Raises:
        ValueError: Jika total debit != total kredit.
    """
    total_debit = sum(b.get("debit", 0) for b in baris)
    total_kredit = sum(b.get("kredit", 0) for b in baris)

    if total_debit != total_kredit:
        raise ValueError(
            f"Jurnal tidak seimbang! "
            f"Total Debit: Rp{total_debit:,} ≠ Total Kredit: Rp{total_kredit:,}".replace(",", ".")
        )
    return total_debit, total_kredit


def simpan_jurnal(
    period_id: int,
    tanggal: str,
    no_bukti: str,
    journal_type: str,
    keterangan: str,
    baris: list[dict],
    komoditas: str = "cabai",
    pihak_terkait: str | None = None,
) -> int:
    """
    Menyimpan satu transaksi jurnal ke database.

    Args:
        period_id     : ID periode akuntansi.
        tanggal       : Tanggal transaksi 'YYYY-MM-DD'.
        no_bukti      : Nomor bukti (harus unik).
        journal_type  : Jenis jurnal (penjualan/penerimaan_kas/dll).
        keterangan    : Deskripsi transaksi.
        baris         : List dict baris jurnal [{"account_id": X, "debit": Y, "kredit": Z}].
        komoditas     : Komoditas terkait (default: cabai).
        pihak_terkait : Nama pelanggan/supplier (opsional).

    Returns:
        ID journal_entry yang baru dibuat.

    Raises:
        ValueError: Jika jurnal tidak seimbang.
        sqlite3.IntegrityError: Jika no_bukti sudah ada.
    """
    # Validasi dulu sebelum menyimpan
    validasi_jurnal_seimbang(baris)

    koneksi = get_connection()
    try:
        cursor = koneksi.cursor()

        # Insert header jurnal
        cursor.execute("""
            INSERT INTO journal_entries
                (period_id, tanggal, no_bukti, journal_type, keterangan, komoditas, pihak_terkait)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (period_id, tanggal, no_bukti, journal_type, keterangan, komoditas, pihak_terkait))
        entry_id = cursor.lastrowid

        # Insert baris-baris jurnal
        for b in baris:
            cursor.execute("""
                INSERT INTO journal_lines
                    (journal_entry_id, account_id, debit, kredit, keterangan)
                VALUES (?, ?, ?, ?, ?)
            """, (entry_id, b["account_id"], b["debit"], b["kredit"], b.get("keterangan")))

        koneksi.commit()
        return entry_id
    except Exception as e:
        koneksi.rollback()
        raise e
    finally:
        koneksi.close()


def generate_nomor_bukti(prefix: str, periode_label: str) -> str:
    """
    Membuat nomor bukti otomatis berurutan dan unik.
    Format: "KK-OKT26-001"

    Menggunakan MAX nomor urut yang sudah ada (bukan COUNT) agar tidak
    bentrok ketika ada penghapusan atau nomor yang tidak urut.

    Args:
        prefix        : Kode jenis transaksi (KK=Kas Keluar, KM=Kas Masuk, dll).
        periode_label : Label periode singkat (mis. 'OKT26').

    Returns:
        Nomor bukti unik, mis. "KK-OKT26-042".
    """
    koneksi = get_connection()
    pola = f"{prefix}-{periode_label}-%"
    # Ambil semua nomor bukti yang cocok lalu cari nomor urut tertinggi
    rows = koneksi.execute(
        "SELECT no_bukti FROM journal_entries WHERE no_bukti LIKE ?",
        (pola,)
    ).fetchall()
    koneksi.close()

    maks = 0
    for row in rows:
        try:
            # Format: PREFIX-PERIODE-NNN, ambil bagian NNN
            bagian = row[0].rsplit("-", 1)[-1]
            angka = int(bagian)
            if angka > maks:
                maks = angka
        except (ValueError, IndexError):
            pass

    return f"{prefix}-{periode_label}-{maks + 1:03d}"


def ambil_semua_jurnal(
    period_id: int | None = None,
    journal_type: str | None = None,
    komoditas: str | None = None,
) -> pd.DataFrame:
    """
    Mengambil semua jurnal dengan filter opsional.
    Menggabungkan journal_entries dengan journal_lines dan accounts.

    Args:
        period_id    : Filter per periode (None = semua periode).
        journal_type : Filter jenis jurnal (None = semua jenis).
        komoditas    : Filter komoditas (None = semua komoditas).

    Returns:
        DataFrame dengan kolom: entry_id, tanggal, no_bukti, keterangan,
        kode_akun, nama_akun, debit, kredit, journal_type, komoditas, pihak_terkait.
    """
    koneksi = get_connection()

    # Bangun kondisi WHERE secara dinamis berdasarkan filter yang diberikan
    kondisi = []
    params: list = []

    if period_id is not None:
        kondisi.append("je.period_id = ?")
        params.append(period_id)

    if journal_type is not None:
        kondisi.append("je.journal_type = ?")
        params.append(journal_type)

    if komoditas is not None:
        kondisi.append("je.komoditas = ?")
        params.append(komoditas)

    klausa_where = ("WHERE " + " AND ".join(kondisi)) if kondisi else ""

    sql = f"""
        SELECT
            je.id           AS entry_id,
            je.tanggal,
            je.no_bukti,
            je.keterangan,
            je.journal_type,
            je.komoditas,
            je.pihak_terkait,
            a.kode_akun,
            a.nama_akun,
            jl.debit,
            jl.kredit
        FROM journal_entries je
        JOIN journal_lines jl ON je.id = jl.journal_entry_id
        JOIN accounts a ON jl.account_id = a.id
        {klausa_where}
        ORDER BY je.tanggal, je.id, jl.id
    """

    df = pd.read_sql_query(sql, koneksi, params=params)
    koneksi.close()
    return df


def ambil_jurnal_dengan_baris(entry_id: int) -> dict:
    """
    Mengambil satu jurnal lengkap dengan semua barisnya.

    Args:
        entry_id : ID journal_entry yang ingin ditampilkan.

    Returns:
        Dict berisi:
          'header' : {id, tanggal, no_bukti, journal_type, keterangan, komoditas, pihak_terkait}
          'baris'  : list of {account_id, kode_akun, nama_akun, debit, kredit}
        Kembalikan {'header': {}, 'baris': []} jika entry tidak ditemukan.
    """
    koneksi = get_connection()

    # Ambil header jurnal
    header_row = koneksi.execute("""
        SELECT id, tanggal, no_bukti, journal_type, keterangan, komoditas, pihak_terkait
        FROM journal_entries
        WHERE id = ?
    """, (entry_id,)).fetchone()

    if not header_row:
        koneksi.close()
        return {"header": {}, "baris": []}

    header = dict(header_row)

    # Ambil semua baris jurnal berikut nama akun
    baris_rows = koneksi.execute("""
        SELECT jl.account_id, a.kode_akun, a.nama_akun, jl.debit, jl.kredit
        FROM journal_lines jl
        JOIN accounts a ON jl.account_id = a.id
        WHERE jl.journal_entry_id = ?
        ORDER BY jl.id
    """, (entry_id,)).fetchall()

    koneksi.close()

    baris = [dict(r) for r in baris_rows]
    return {"header": header, "baris": baris}


def _tabel_ada(koneksi: sqlite3.Connection, nama_tabel: str) -> bool:
    """Mengecek apakah suatu tabel ada di database."""
    row = koneksi.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (nama_tabel,)
    ).fetchone()
    return bool(row)


def _rekalkulasi_kartu_persediaan(koneksi: sqlite3.Connection, item_id: int) -> None:
    """Menghitung ulang running balance saldo_qty, saldo_nilai, dan harga_rata2 kartu stok."""
    if not _tabel_ada(koneksi, "inventory_movements"):
        return
    rows = koneksi.execute("""
        SELECT id, tanggal, tipe_gerakan, qty, harga_satuan, total_nilai
        FROM inventory_movements
        WHERE item_id = ?
        ORDER BY tanggal ASC, COALESCE(journal_entry_id, id) ASC, id ASC
    """, (item_id,)).fetchall()

    saldo_qty = 0.0
    saldo_nilai = 0
    harga_rata2 = 0

    for r in rows:
        m_id = r["id"]
        tipe = r["tipe_gerakan"]
        qty = float(r["qty"])
        harga_satuan = int(r["harga_satuan"])

        if tipe in ("saldo_awal", "masuk"):
            total_nilai = int(qty * harga_satuan) if tipe == "masuk" else int(r["total_nilai"])
            saldo_qty += qty
            saldo_nilai += total_nilai
            harga_rata2 = int(saldo_nilai / saldo_qty) if saldo_qty > 0 else 0
            koneksi.execute("""
                UPDATE inventory_movements
                SET total_nilai = ?, saldo_qty = ?, saldo_nilai = ?, harga_rata2 = ?
                WHERE id = ?
            """, (total_nilai, saldo_qty, saldo_nilai, harga_rata2, m_id))
        elif tipe == "keluar":
            if abs(saldo_qty - qty) < 1e-9 or qty >= saldo_qty:
                total_nilai = saldo_nilai
                saldo_qty = 0.0
                saldo_nilai = 0
                harga_rata2 = 0
            else:
                total_nilai = int(qty * harga_rata2)
                saldo_qty = max(0.0, saldo_qty - qty)
                saldo_nilai = max(0, saldo_nilai - total_nilai)
            koneksi.execute("""
                UPDATE inventory_movements
                SET harga_satuan = ?, total_nilai = ?, saldo_qty = ?, saldo_nilai = ?, harga_rata2 = ?
                WHERE id = ?
            """, (harga_rata2, total_nilai, saldo_qty, saldo_nilai, harga_rata2, m_id))


def hapus_jurnal(entry_id: int) -> None:
    """
    Menghapus jurnal dan semua relasi terkait (lines, inventory, receivables, attendance).
    Hanya bisa dilakukan jika periode masih 'buka'.

    Args:
        entry_id : ID journal_entry yang ingin dihapus.

    Raises:
        PermissionError : Jika periode sudah ditutup (status = 'tutup').
        ValueError      : Jika entry_id tidak ditemukan atau sudah ada pelunasan piutang.
    """
    koneksi = get_connection()
    try:
        # Cek status periode dari jurnal ini
        row = koneksi.execute("""
            SELECT p.status, je.no_bukti
            FROM journal_entries je
            JOIN periods p ON je.period_id = p.id
            WHERE je.id = ?
        """, (entry_id,)).fetchone()

        if not row:
            raise ValueError(f"Jurnal dengan ID {entry_id} tidak ditemukan.")

        if row["status"] == "tutup":
            raise PermissionError(
                f"Tidak bisa menghapus jurnal '{row['no_bukti']}'. "
                "Periode sudah ditutup."
            )

        items_terdampak = []
        # 1. Cek apakah ada pergerakan persediaan terkait
        if _tabel_ada(koneksi, "inventory_movements"):
            rows_inv = koneksi.execute(
                "SELECT DISTINCT item_id FROM inventory_movements WHERE journal_entry_id = ?",
                (entry_id,)
            ).fetchall()
            items_terdampak = [r["item_id"] for r in rows_inv]
            koneksi.execute("DELETE FROM inventory_movements WHERE journal_entry_id = ?", (entry_id,))

        # 2. Cek piutang terkait
        if _tabel_ada(koneksi, "receivables"):
            row_rec = koneksi.execute(
                "SELECT id, status, jumlah_terbayar FROM receivables WHERE journal_entry_id = ?",
                (entry_id,)
            ).fetchone()
            if row_rec:
                if row_rec["jumlah_terbayar"] > 0:
                    raise ValueError("Tidak bisa menghapus jurnal penjualan tempo yang sudah memiliki pembayaran piutang.")
                koneksi.execute("DELETE FROM receivables WHERE journal_entry_id = ?", (entry_id,))

        # 3. Lepaskan relasi absensi penggajian
        if _tabel_ada(koneksi, "attendance"):
            koneksi.execute(
                "UPDATE attendance SET journal_entry_id = NULL, sudah_dibayar = 0 WHERE journal_entry_id = ?",
                (entry_id,)
            )

        # 4. Hapus header — journal_lines terhapus otomatis via ON DELETE CASCADE
        koneksi.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))

        # 5. Rekalkulasi kartu stok item yang terdampak
        for it_id in items_terdampak:
            _rekalkulasi_kartu_persediaan(koneksi, it_id)

        koneksi.commit()
    except Exception as e:
        koneksi.rollback()
        raise e
    finally:
        koneksi.close()


def buat_pratinjau_jurnal(baris: list[dict], nama_akun_map: dict) -> list[dict]:
    """
    Membuat daftar pratinjau jurnal tanpa menyimpan ke database.
    Digunakan oleh views/02_input_transaksi.py untuk menampilkan preview
    sebelum pengguna menekan tombol Simpan.

    Args:
        baris        : List dict [{account_id, debit, kredit}, ...].
        nama_akun_map: Dict {account_id: {'kode_akun': ..., 'nama_akun': ...}}.

    Returns:
        List dict siap ditampilkan sebagai tabel pratinjau.
    """
    pratinjau = []
    for b in baris:
        akun_info = nama_akun_map.get(b["account_id"], {})
        pratinjau.append({
            "Akun": f"{akun_info.get('kode_akun', '?')} - {akun_info.get('nama_akun', '?')}",
            "Debit": b["debit"],
            "Kredit": b["kredit"],
        })
    return pratinjau
