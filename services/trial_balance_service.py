"""
services/trial_balance_service.py
-----------------------------------
Tujuan  : Menghitung Neraca Saldo (Trial Balance) sebelum dan sesudah penyesuaian.
Input   : period_id, flag termasuk_penyesuaian.
Output  : DataFrame Neraca Saldo dengan kolom debit dan kredit per akun.
Dipanggil oleh : views/09_neraca_saldo.py, services/worksheet_service.py

CARA KERJA NERACA SALDO:
  1. Ambil saldo awal dari tabel opening_balances untuk periode ini.
  2. Tambahkan semua gerakan dari journal_lines untuk periode ini.
     - Jika termasuk_penyesuaian=False: hanya ambil jurnal bukan penyesuaian.
     - Jika termasuk_penyesuaian=True : ambil semua jurnal (termasuk penyesuaian).
  3. Hitung saldo akhir per akun sesuai saldo normal:
     - Akun DEBIT normal: saldo = saldo_awal + total_debit - total_kredit
     - Akun KREDIT normal: saldo = saldo_awal + total_kredit - total_debit
  4. Tampilkan saldo di kolom 'debit' (akun debit normal) atau 'kredit' (akun kredit normal).
  5. Validasi: total kolom debit == total kolom kredit.

CATATAN:
  Akun kontra (mis. Akumulasi Penyusutan, is_kontra=1) memiliki saldo normal Kredit
  meskipun berada dalam kelompok Aset. Ini sudah ditangani oleh kolom saldo_normal.
"""

import pandas as pd
from database.connection import get_connection


def hitung_neraca_saldo(
    period_id: int,
    termasuk_penyesuaian: bool = False,
) -> pd.DataFrame:
    """
    Menghitung Neraca Saldo untuk satu periode.

    Args:
        period_id             : ID periode yang ingin dihitung.
        termasuk_penyesuaian  : False = NS sebelum penyesuaian (hanya jurnal biasa).
                                True  = NS setelah penyesuaian (semua jurnal).

    Returns:
        DataFrame dengan kolom:
        kode_akun | nama_akun | kategori | saldo_normal | debit | kredit

        Keterangan:
        - Akun dengan saldo normal DEBIT: saldo tampil di kolom 'debit', kredit=0.
        - Akun dengan saldo normal KREDIT: saldo tampil di kolom 'kredit', debit=0.
        - Akun dengan saldo=0 tetap ditampilkan (agar terlihat lengkap).
        - Akun dengan saldo NEGATIF (tidak normal) tetap ditampilkan apa adanya.
    """
    koneksi = get_connection()
    try:
        # -------------------------------------------------------------------
        # LANGKAH 1: Ambil semua akun aktif (sumber daftar akun)
        # -------------------------------------------------------------------
        semua_akun = koneksi.execute(
            """
            SELECT id, kode_akun, nama_akun, kategori, saldo_normal
            FROM accounts
            WHERE aktif = 1
            ORDER BY kode_akun
            """
        ).fetchall()

        # -------------------------------------------------------------------
        # LANGKAH 2: Ambil saldo awal per akun dari opening_balances
        # -------------------------------------------------------------------
        saldo_awal_rows = koneksi.execute(
            """
            SELECT account_id, saldo_debit, saldo_kredit
            FROM opening_balances
            WHERE period_id = ?
            """,
            (period_id,)
        ).fetchall()

        # Simpan dalam dict {account_id: (saldo_debit, saldo_kredit)}
        dict_saldo_awal = {
            r["account_id"]: (int(r["saldo_debit"]), int(r["saldo_kredit"]))
            for r in saldo_awal_rows
        }

        # -------------------------------------------------------------------
        # LANGKAH 3: Hitung total debit & kredit dari journal_lines
        # -------------------------------------------------------------------
        # Filter jurnal: jika termasuk_penyesuaian=False, kecualikan
        # jurnal yang bertipe 'umum' dengan keterangan penyesuaian.
        # Namun karena tidak ada flag penyesuaian di journal_entries,
        # kita pakai konvensi no_bukti yang diawali 'PA-' (Penyesuaian).
        # Lihat adjusting_service.py untuk konvensi no_bukti.
        if termasuk_penyesuaian:
            # Semua jurnal periode ini
            mutasi_rows = koneksi.execute(
                """
                SELECT jl.account_id,
                       COALESCE(SUM(jl.debit), 0)  AS total_debit,
                       COALESCE(SUM(jl.kredit), 0) AS total_kredit
                FROM journal_lines jl
                JOIN journal_entries je ON jl.journal_entry_id = je.id
                WHERE je.period_id = ?
                GROUP BY jl.account_id
                """,
                (period_id,)
            ).fetchall()
        else:
            # Kecualikan jurnal penyesuaian (no_bukti diawali 'PA-')
            mutasi_rows = koneksi.execute(
                """
                SELECT jl.account_id,
                       COALESCE(SUM(jl.debit), 0)  AS total_debit,
                       COALESCE(SUM(jl.kredit), 0) AS total_kredit
                FROM journal_lines jl
                JOIN journal_entries je ON jl.journal_entry_id = je.id
                WHERE je.period_id = ?
                  AND je.no_bukti NOT LIKE 'PA-%'
                GROUP BY jl.account_id
                """,
                (period_id,)
            ).fetchall()

    finally:
        koneksi.close()

    # Simpan mutasi dalam dict {account_id: (total_debit, total_kredit)}
    dict_mutasi = {
        r["account_id"]: (int(r["total_debit"]), int(r["total_kredit"]))
        for r in mutasi_rows
    }

    # -------------------------------------------------------------------
    # LANGKAH 4: Hitung saldo akhir per akun dan susun DataFrame
    # -------------------------------------------------------------------
    baris_data = []
    for akun in semua_akun:
        aid = akun["id"]
        saldo_normal = akun["saldo_normal"]  # 'Debit' atau 'Kredit'

        # Ambil saldo awal (default 0 jika tidak ada)
        ob_debit, ob_kredit = dict_saldo_awal.get(aid, (0, 0))

        # Ambil mutasi periode ini (default 0 jika tidak ada)
        mut_debit, mut_kredit = dict_mutasi.get(aid, (0, 0))

        # Total debit dan kredit (saldo awal + mutasi)
        total_debit_akun = ob_debit + mut_debit
        total_kredit_akun = ob_kredit + mut_kredit

        # Hitung saldo akhir sesuai saldo normal
        if saldo_normal == "Debit":
            # Akun debit: saldo bertambah dari debit, berkurang dari kredit
            saldo_akhir = total_debit_akun - total_kredit_akun
            # Tampilkan di kolom debit (saldo normal)
            if saldo_akhir >= 0:
                debit_ns = saldo_akhir
                kredit_ns = 0
            else:
                # Saldo tidak normal (misalnya kas overdraft) — tetap tampilkan
                debit_ns = 0
                kredit_ns = abs(saldo_akhir)
        else:
            # Akun kredit: saldo bertambah dari kredit, berkurang dari debit
            saldo_akhir = total_kredit_akun - total_debit_akun
            # Tampilkan di kolom kredit (saldo normal)
            if saldo_akhir >= 0:
                debit_ns = 0
                kredit_ns = saldo_akhir
            else:
                # Saldo tidak normal — tetap tampilkan
                debit_ns = abs(saldo_akhir)
                kredit_ns = 0

        # Hanya tampilkan akun yang punya saldo atau mutasi (sembunyikan yang 0 total)
        if total_debit_akun == 0 and total_kredit_akun == 0:
            continue  # lewati akun yang belum pernah dipakai

        baris_data.append({
            "kode_akun": akun["kode_akun"],
            "nama_akun": akun["nama_akun"],
            "kategori": akun["kategori"],
            "saldo_normal": saldo_normal,
            "debit": debit_ns,
            "kredit": kredit_ns,
        })

    return pd.DataFrame(baris_data, columns=[
        "kode_akun", "nama_akun", "kategori", "saldo_normal", "debit", "kredit"
    ])


def validasi_neraca_saldo_seimbang(df_neraca: pd.DataFrame) -> tuple[bool, int, int]:
    """
    Memvalidasi apakah neraca saldo seimbang (total debit == total kredit).

    Args:
        df_neraca : DataFrame hasil hitung_neraca_saldo().

    Returns:
        Tuple (seimbang: bool, total_debit: int, total_kredit: int).

    Catatan:
        Neraca saldo WAJIB seimbang. Jika tidak seimbang, ada kesalahan
        di input jurnal atau di saldo awal.
    """
    if df_neraca.empty:
        return True, 0, 0

    total_debit = int(df_neraca["debit"].sum())
    total_kredit = int(df_neraca["kredit"].sum())
    seimbang = total_debit == total_kredit
    return seimbang, total_debit, total_kredit
