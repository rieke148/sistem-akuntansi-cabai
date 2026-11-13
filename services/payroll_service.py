"""
services/payroll_service.py
----------------------------
Tujuan  : Menghitung upah pekerja berdasarkan hari kerja per periode 2 mingguan,
          menyimpan absensi ke tabel attendance, dan mencatat jurnal pembayaran
          atau akrual upah ke journal_entries.
Input   : period_id, daftar hari kerja per pekerja, tanggal bayar, sudah_dibayar.
Output  : ID jurnal yang dibuat, rekap absensi sebagai DataFrame.
Dipanggil oleh : views/03_penggajian.py

ATURAN UPAH (dari observasi lapangan):
  - Pekerja tetap     : Rp90.000/hari (diambil dari kolom upah_harian di tabel employees)
  - Tenaga tambahan   : Rp120.000/hari (idem)
  - Total upah = hari_kerja × upah_harian
  - Dibayar tiap 2 minggu:
      minggu1 = tgl 1-14 → dibayar sekitar tgl 15
      minggu2 = tgl 15-akhir → dibayar awal bulan berikutnya
  - Jika belum dibayar (sudah_dibayar=False) → dicatat sebagai Utang Gaji
      Dr Beban Upah Langsung (5105) | Cr Utang Gaji (2201)
  - Jika dibayar tunai (sudah_dibayar=True) → langsung kas keluar
      Dr Beban Upah Langsung (5105) | Cr Kas (1101)

NOMOR BUKTI KONVENSI:
  Format: 'GAJI-{PERIODE_BAYAR}-{PERIOD_ID}-{timestamp}'
  Contoh: 'GAJI-M1-1-20261015'
"""

import pandas as pd
from datetime import datetime
from database.connection import get_connection
from services.journal_service import simpan_jurnal


def hitung_upah_pekerja(
    employee_id: int,
    hari_kerja: int,
) -> dict:
    """
    Menghitung upah satu pekerja berdasarkan hari kerja.

    Args:
        employee_id : ID pekerja dari tabel employees.
        hari_kerja  : Jumlah hari hadir dalam satu periode pembayaran.

    Returns:
        Dict berisi: nama, tipe_pekerja, upah_harian, hari_kerja, total_upah.

    Rumus:
        total_upah = hari_kerja × upah_harian
    """
    koneksi = get_connection()
    row = koneksi.execute(
        "SELECT nama, tipe_pekerja, upah_harian FROM employees WHERE id = ?",
        (employee_id,)
    ).fetchone()
    koneksi.close()

    if not row:
        raise ValueError(f"Pekerja ID {employee_id} tidak ditemukan.")

    # Total upah = hari kerja x upah harian (integer Rupiah)
    total_upah = hari_kerja * int(row["upah_harian"])

    return {
        "nama": row["nama"],
        "tipe_pekerja": row["tipe_pekerja"],
        "upah_harian": int(row["upah_harian"]),
        "hari_kerja": hari_kerja,
        "total_upah": total_upah,
    }


def simpan_dan_bayar_upah(
    period_id: int,
    tanggal_bayar: str,
    periode_bayar: str,
    data_absensi: list[dict],
    akun_beban_upah_id: int,
    akun_kas_id: int,
    sudah_dibayar: bool = True,
) -> int:
    """
    Menyimpan absensi ke tabel attendance dan mencatat jurnal pembayaran upah.

    Args:
        period_id         : ID periode akuntansi.
        tanggal_bayar     : Tanggal pembayaran 'YYYY-MM-DD'.
        periode_bayar     : 'minggu1' atau 'minggu2'.
        data_absensi      : List dict [{employee_id: int, hari_kerja: int}, ...]
        akun_beban_upah_id: ID akun Beban Upah Langsung (mis. id=38, kode 5105).
        akun_kas_id       : ID akun Kas (mis. id=1, kode 1101).
        sudah_dibayar     : True  → jurnal: Dr Beban Upah | Cr Kas
                            False → jurnal: Dr Beban Upah | Cr Utang Gaji

    Returns:
        ID journal_entry yang dibuat. 0 jika tidak ada upah > 0.

    Raises:
        ValueError: Jika data absensi kosong atau total upah = 0.
    """
    if not data_absensi:
        raise ValueError("Data absensi tidak boleh kosong.")

    # Hitung total upah semua pekerja
    total_upah_keseluruhan = 0
    rincian_per_pekerja = []

    for item in data_absensi:
        employee_id = item["employee_id"]
        hari_kerja = int(item.get("hari_kerja", 0))

        if hari_kerja <= 0:
            continue  # pekerja yang tidak masuk, lewati

        rincian = hitung_upah_pekerja(employee_id, hari_kerja)
        total_upah_keseluruhan += rincian["total_upah"]
        rincian_per_pekerja.append({
            "employee_id": employee_id,
            "hari_kerja": hari_kerja,
            "total_upah": rincian["total_upah"],
        })

    if total_upah_keseluruhan == 0:
        return 0

    # -------------------------------------------------------------------
    # Tentukan akun kredit: Kas (tunai) atau Utang Gaji (akrual)
    # -------------------------------------------------------------------
    koneksi = get_connection()
    try:
        if sudah_dibayar:
            # Bayar tunai → Kredit Kas
            akun_kredit_id = akun_kas_id
        else:
            # Akrual → Kredit Utang Gaji (cari dari tabel accounts)
            row_utang = koneksi.execute(
                "SELECT id FROM accounts WHERE kode_akun = '2201'"
            ).fetchone()
            if not row_utang:
                raise ValueError("Akun Utang Gaji (2201) tidak ditemukan di Bagan Akun.")
            akun_kredit_id = row_utang["id"]

        # -------------------------------------------------------------------
        # Buat nomor bukti unik
        # -------------------------------------------------------------------
        kode_minggu = "M1" if periode_bayar == "minggu1" else "M2"
        tgl_str = tanggal_bayar.replace("-", "")
        no_bukti = f"GAJI-{kode_minggu}-{period_id}-{tgl_str}"

        # Cek apakah no_bukti sudah ada (hindari duplikat)
        cek = koneksi.execute(
            "SELECT id FROM journal_entries WHERE no_bukti = ?",
            (no_bukti,)
        ).fetchone()
        if cek:
            raise ValueError(
                f"Upah {kode_minggu} periode ini sudah pernah dicatat "
                f"(no. bukti: {no_bukti}). Hapus dulu sebelum input ulang."
            )

        # -------------------------------------------------------------------
        # Susun keterangan
        # -------------------------------------------------------------------
        label_minggu = "Minggu 1 (1-14)" if periode_bayar == "minggu1" else "Minggu 2 (15-akhir)"
        status_bayar = "tunai" if sudah_dibayar else "akrual/utang"
        keterangan = f"Pembayaran upah pekerja {label_minggu} — {status_bayar}"

        # -------------------------------------------------------------------
        # Buat baris jurnal: 1 Debit (Beban Upah) + 1 Kredit (Kas/Utang)
        # -------------------------------------------------------------------
        baris_jurnal = [
            {
                "account_id": akun_beban_upah_id,
                "debit": total_upah_keseluruhan,
                "kredit": 0,
            },
            {
                "account_id": akun_kredit_id,
                "debit": 0,
                "kredit": total_upah_keseluruhan,
            },
        ]

        # Simpan jurnal ke database
        journal_entry_id = simpan_jurnal(
            period_id=period_id,
            tanggal=tanggal_bayar,
            no_bukti=no_bukti,
            journal_type="pengeluaran_kas" if sudah_dibayar else "umum",
            keterangan=keterangan,
            baris=baris_jurnal,
        )

        # -------------------------------------------------------------------
        # Simpan absensi ke tabel attendance
        # -------------------------------------------------------------------
        for item in rincian_per_pekerja:
            # Cek apakah sudah ada absensi untuk employee ini di periode & minggu ini
            cek_abs = koneksi.execute(
                """
                SELECT id FROM attendance
                WHERE employee_id = ? AND period_id = ? AND periode_bayar = ?
                """,
                (item["employee_id"], period_id, periode_bayar)
            ).fetchone()

            if cek_abs:
                # Update jika sudah ada
                koneksi.execute(
                    """
                    UPDATE attendance
                    SET hari_kerja = ?, total_upah = ?,
                        sudah_dibayar = ?, journal_entry_id = ?
                    WHERE id = ?
                    """,
                    (item["hari_kerja"], item["total_upah"],
                     1 if sudah_dibayar else 0, journal_entry_id, cek_abs["id"])
                )
            else:
                # Insert baru
                koneksi.execute(
                    """
                    INSERT INTO attendance
                        (employee_id, period_id, periode_bayar,
                         hari_kerja, total_upah, sudah_dibayar, journal_entry_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (item["employee_id"], period_id, periode_bayar,
                     item["hari_kerja"], item["total_upah"],
                     1 if sudah_dibayar else 0, journal_entry_id)
                )

        koneksi.commit()
        return journal_entry_id

    finally:
        koneksi.close()


def ambil_rekap_absensi(period_id: int) -> pd.DataFrame:
    """
    Mengambil rekap absensi dan upah semua pekerja untuk satu periode.
    Menggabungkan data attendance kedua minggu per pekerja.

    Args:
        period_id : ID periode akuntansi.

    Returns:
        DataFrame: nama | tipe_pekerja | hari_minggu1 | hari_minggu2 |
                   total_hari | upah_harian | total_upah | sudah_dibayar_m1 | sudah_dibayar_m2

    Keterangan:
        total_hari  = hari_minggu1 + hari_minggu2
        total_upah  = total_hari × upah_harian
    """
    koneksi = get_connection()
    try:
        # Ambil semua absensi periode ini + data pekerja
        rows = koneksi.execute(
            """
            SELECT
                e.id AS employee_id,
                e.nama,
                e.tipe_pekerja,
                e.upah_harian,
                COALESCE(SUM(CASE WHEN a.periode_bayar = 'minggu1' THEN a.hari_kerja END), 0)
                    AS hari_minggu1,
                COALESCE(SUM(CASE WHEN a.periode_bayar = 'minggu2' THEN a.hari_kerja END), 0)
                    AS hari_minggu2,
                COALESCE(MAX(CASE WHEN a.periode_bayar = 'minggu1' THEN a.sudah_dibayar END), 0)
                    AS sudah_dibayar_m1,
                COALESCE(MAX(CASE WHEN a.periode_bayar = 'minggu2' THEN a.sudah_dibayar END), 0)
                    AS sudah_dibayar_m2
            FROM employees e
            LEFT JOIN attendance a
                ON a.employee_id = e.id AND a.period_id = ?
            WHERE e.aktif = 1
            GROUP BY e.id, e.nama, e.tipe_pekerja, e.upah_harian
            ORDER BY e.nama
            """,
            (period_id,)
        ).fetchall()
    finally:
        koneksi.close()

    if not rows:
        return pd.DataFrame(columns=[
            "nama", "tipe_pekerja", "hari_minggu1", "hari_minggu2",
            "total_hari", "upah_harian", "total_upah",
            "sudah_dibayar_m1", "sudah_dibayar_m2",
        ])

    baris_data = []
    for row in rows:
        hari_m1 = int(row["hari_minggu1"])
        hari_m2 = int(row["hari_minggu2"])
        total_hari = hari_m1 + hari_m2
        upah_harian = int(row["upah_harian"])
        total_upah = total_hari * upah_harian

        baris_data.append({
            "employee_id": row["employee_id"],
            "nama": row["nama"],
            "tipe_pekerja": row["tipe_pekerja"],
            "hari_minggu1": hari_m1,
            "hari_minggu2": hari_m2,
            "total_hari": total_hari,
            "upah_harian": upah_harian,
            "total_upah": total_upah,
            "sudah_dibayar_m1": bool(row["sudah_dibayar_m1"]),
            "sudah_dibayar_m2": bool(row["sudah_dibayar_m2"]),
        })

    return pd.DataFrame(baris_data)


def ambil_absensi_per_minggu(
    period_id: int,
    periode_bayar: str,
) -> pd.DataFrame:
    """
    Mengambil data absensi untuk satu periode pembayaran (minggu1 atau minggu2).

    Args:
        period_id    : ID periode akuntansi.
        periode_bayar: 'minggu1' atau 'minggu2'.

    Returns:
        DataFrame: employee_id | nama | tipe_pekerja | upah_harian |
                   hari_kerja | total_upah | sudah_dibayar
    """
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            """
            SELECT
                e.id AS employee_id,
                e.nama,
                e.tipe_pekerja,
                e.upah_harian,
                COALESCE(a.hari_kerja, 0) AS hari_kerja,
                COALESCE(a.total_upah, 0) AS total_upah,
                COALESCE(a.sudah_dibayar, 0) AS sudah_dibayar
            FROM employees e
            LEFT JOIN attendance a
                ON a.employee_id = e.id
                AND a.period_id = ?
                AND a.periode_bayar = ?
            WHERE e.aktif = 1
            ORDER BY e.nama
            """,
            (period_id, periode_bayar)
        ).fetchall()
    finally:
        koneksi.close()

    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame(
        columns=["employee_id", "nama", "tipe_pekerja", "upah_harian",
                 "hari_kerja", "total_upah", "sudah_dibayar"]
    )
