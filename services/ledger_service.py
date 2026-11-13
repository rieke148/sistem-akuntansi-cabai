"""
services/ledger_service.py
--------------------------
Tujuan  : Fungsi untuk "posting" (memindahkan dari jurnal ke buku besar)
          dan menampilkan Buku Besar per akun.
Input   : account_id, period_id (filter opsional).
Output  : DataFrame Buku Besar dengan saldo berjalan.
Dipanggil oleh : views/07_buku_besar.py, services/trial_balance_service.py

KONSEP POSTING:
  Di sistem ini, "posting" = membaca journal_lines dan mengelompokkan
  per akun. Tidak ada tabel terpisah untuk Buku Besar — semua dihitung
  langsung dari journal_lines (prinsip "satu sumber kebenaran").

RUMUS SALDO BERJALAN:
  Saldo bergerak sesuai saldo normal akun:
  - Akun DEBIT normal (Aset, Beban): saldo += debit - kredit
  - Akun KREDIT normal (Liab, Ekuitas, Pendapatan): saldo += kredit - debit
"""

import pandas as pd
from database.connection import get_connection


def ambil_buku_besar(
    account_id: int,
    period_id: int | None = None,
    sertakan_saldo_awal: bool = True,
) -> pd.DataFrame:
    """
    Mengambil Buku Besar untuk satu akun dengan saldo berjalan.

    Args:
        account_id           : ID akun yang ingin dilihat.
        period_id            : Filter periode (None = semua periode).
        sertakan_saldo_awal  : Jika True, tampilkan baris saldo awal dari
                               opening_balances di atas transaksi.

    Returns:
        DataFrame dengan kolom:
        tanggal | no_bukti | keterangan | debit | kredit | saldo

    Logika saldo berjalan:
        Saldo bergerak sesuai saldo normal akun:
        - Akun DEBIT normal: saldo += debit - kredit
        - Akun KREDIT normal: saldo += kredit - debit
    """
    koneksi = get_connection()
    try:
        # Ambil informasi akun (nama + saldo normal)
        akun = koneksi.execute(
            "SELECT nama_akun, saldo_normal FROM accounts WHERE id = ?",
            (account_id,)
        ).fetchone()

        if not akun:
            return pd.DataFrame(columns=[
                "tanggal", "no_bukti", "keterangan", "debit", "kredit", "saldo"
            ])

        saldo_normal = akun["saldo_normal"]  # 'Debit' atau 'Kredit'

        # -------------------------------------------------------------------
        # LANGKAH 1: Ambil saldo awal dari opening_balances
        # -------------------------------------------------------------------
        saldo_awal = 0
        tanggal_saldo_awal = None

        if sertakan_saldo_awal:
            if period_id is not None:
                # Ambil saldo awal untuk periode yang dipilih
                ob = koneksi.execute(
                    """
                    SELECT ob.saldo_debit, ob.saldo_kredit, p.tahun, p.bulan
                    FROM opening_balances ob
                    JOIN periods p ON ob.period_id = p.id
                    WHERE ob.account_id = ? AND ob.period_id = ?
                    """,
                    (account_id, period_id)
                ).fetchone()
            else:
                # Ambil saldo awal dari periode paling awal
                ob = koneksi.execute(
                    """
                    SELECT ob.saldo_debit, ob.saldo_kredit, p.tahun, p.bulan
                    FROM opening_balances ob
                    JOIN periods p ON ob.period_id = p.id
                    WHERE ob.account_id = ?
                    ORDER BY p.tahun ASC, p.bulan ASC
                    LIMIT 1
                    """,
                    (account_id,)
                ).fetchone()

            if ob:
                # Hitung saldo awal sesuai saldo normal
                if saldo_normal == "Debit":
                    saldo_awal = int(ob["saldo_debit"]) - int(ob["saldo_kredit"])
                else:
                    saldo_awal = int(ob["saldo_kredit"]) - int(ob["saldo_debit"])

                # Tanggal saldo awal = 1 bulan sebelum periode
                bulan = ob["bulan"]
                tahun = ob["tahun"]
                tanggal_saldo_awal = f"{tahun}-{bulan:02d}-01"

        # -------------------------------------------------------------------
        # LANGKAH 2: Ambil semua baris jurnal untuk akun ini
        # -------------------------------------------------------------------
        if period_id is not None:
            baris = koneksi.execute(
                """
                SELECT
                    je.tanggal,
                    je.no_bukti,
                    je.keterangan,
                    COALESCE(jl.debit, 0)  AS debit,
                    COALESCE(jl.kredit, 0) AS kredit
                FROM journal_lines jl
                JOIN journal_entries je ON jl.journal_entry_id = je.id
                WHERE jl.account_id = ?
                  AND je.period_id = ?
                ORDER BY je.tanggal ASC, je.id ASC, jl.id ASC
                """,
                (account_id, period_id)
            ).fetchall()
        else:
            baris = koneksi.execute(
                """
                SELECT
                    je.tanggal,
                    je.no_bukti,
                    je.keterangan,
                    COALESCE(jl.debit, 0)  AS debit,
                    COALESCE(jl.kredit, 0) AS kredit
                FROM journal_lines jl
                JOIN journal_entries je ON jl.journal_entry_id = je.id
                WHERE jl.account_id = ?
                ORDER BY je.tanggal ASC, je.id ASC, jl.id ASC
                """,
                (account_id,)
            ).fetchall()

    finally:
        koneksi.close()

    # -------------------------------------------------------------------
    # LANGKAH 3: Susun DataFrame dengan saldo berjalan
    # -------------------------------------------------------------------
    baris_data = []

    # Baris saldo awal (baris pertama Buku Besar)
    if sertakan_saldo_awal:
        baris_data.append({
            "tanggal": tanggal_saldo_awal or "-",
            "no_bukti": "-",
            "keterangan": "Saldo Awal",
            "debit": saldo_awal if saldo_normal == "Debit" and saldo_awal > 0 else 0,
            "kredit": saldo_awal if saldo_normal == "Kredit" and saldo_awal > 0 else 0,
            "saldo": saldo_awal,
        })

    saldo_berjalan = saldo_awal

    for row in baris:
        debit = int(row["debit"])
        kredit = int(row["kredit"])

        # Hitung perubahan saldo sesuai saldo normal akun
        if saldo_normal == "Debit":
            saldo_berjalan += debit - kredit
        else:
            saldo_berjalan += kredit - debit

        baris_data.append({
            "tanggal": row["tanggal"],
            "no_bukti": row["no_bukti"],
            "keterangan": row["keterangan"],
            "debit": debit,
            "kredit": kredit,
            "saldo": saldo_berjalan,
        })

    return pd.DataFrame(baris_data, columns=[
        "tanggal", "no_bukti", "keterangan", "debit", "kredit", "saldo"
    ])


def ambil_saldo_akun(
    account_id: int,
    period_id: int | None = None,
    sampai_tanggal: str | None = None,
) -> int:
    """
    Menghitung saldo akhir satu akun (dalam Rupiah).

    Saldo = Saldo Awal (opening_balances) + Total gerakan dari journal_lines.
    Hasilnya selalu positif jika sesuai saldo normal akun.

    Args:
        account_id    : ID akun.
        period_id     : Filter periode. Jika None, hitung semua periode.
        sampai_tanggal: Hitung saldo sampai tanggal ini ('YYYY-MM-DD').

    Returns:
        Saldo akun (integer Rupiah). Positif = sesuai saldo normal.
        Contoh: Kas Rp500.000.000 → 500000000
    """
    koneksi = get_connection()
    try:
        # Ambil saldo normal akun
        akun = koneksi.execute(
            "SELECT saldo_normal FROM accounts WHERE id = ?",
            (account_id,)
        ).fetchone()

        if not akun:
            return 0

        saldo_normal = akun["saldo_normal"]

        # Ambil saldo awal dari opening_balances
        if period_id is not None:
            ob = koneksi.execute(
                """
                SELECT saldo_debit, saldo_kredit
                FROM opening_balances
                WHERE account_id = ? AND period_id = ?
                """,
                (account_id, period_id)
            ).fetchone()
        else:
            # Ambil dari periode paling awal
            ob = koneksi.execute(
                """
                SELECT ob.saldo_debit, ob.saldo_kredit
                FROM opening_balances ob
                JOIN periods p ON ob.period_id = p.id
                WHERE ob.account_id = ?
                ORDER BY p.tahun ASC, p.bulan ASC
                LIMIT 1
                """,
                (account_id,)
            ).fetchone()

        if ob:
            if saldo_normal == "Debit":
                saldo_awal = int(ob["saldo_debit"]) - int(ob["saldo_kredit"])
            else:
                saldo_awal = int(ob["saldo_kredit"]) - int(ob["saldo_debit"])
        else:
            saldo_awal = 0

        # Hitung total debit & kredit dari journal_lines
        kondisi_ekstra = ""
        params: list = [account_id]

        if period_id is not None:
            kondisi_ekstra += " AND je.period_id = ?"
            params.append(period_id)

        if sampai_tanggal is not None:
            kondisi_ekstra += " AND je.tanggal <= ?"
            params.append(sampai_tanggal)

        totals = koneksi.execute(
            f"""
            SELECT
                COALESCE(SUM(jl.debit), 0)  AS total_debit,
                COALESCE(SUM(jl.kredit), 0) AS total_kredit
            FROM journal_lines jl
            JOIN journal_entries je ON jl.journal_entry_id = je.id
            WHERE jl.account_id = ?
            {kondisi_ekstra}
            """,
            tuple(params)
        ).fetchone()

        total_debit = int(totals["total_debit"])
        total_kredit = int(totals["total_kredit"])

        # Hitung saldo akhir sesuai saldo normal
        if saldo_normal == "Debit":
            saldo_akhir = saldo_awal + total_debit - total_kredit
        else:
            saldo_akhir = saldo_awal + total_kredit - total_debit

        return saldo_akhir

    finally:
        koneksi.close()


def ambil_semua_saldo_akun(period_id: int) -> dict[int, int]:
    """
    Menghitung saldo semua akun untuk satu periode.
    Dipakai oleh trial_balance_service untuk neraca saldo.

    Proses:
    1. Ambil semua akun aktif.
    2. Untuk masing-masing akun, panggil ambil_saldo_akun().

    Returns:
        Dict {account_id: saldo} dalam Rupiah.
        Contoh: {1: 500000000, 2: 10000000, ...}
    """
    koneksi = get_connection()
    try:
        semua_akun = koneksi.execute(
            "SELECT id FROM accounts ORDER BY kode_akun"
        ).fetchall()
    finally:
        koneksi.close()

    hasil = {}
    for akun in semua_akun:
        aid = akun["id"]
        hasil[aid] = ambil_saldo_akun(aid, period_id=period_id)

    return hasil
