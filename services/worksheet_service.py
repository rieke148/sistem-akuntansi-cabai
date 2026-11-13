"""
services/worksheet_service.py
-------------------------------
Tujuan  : Menyusun Neraca Lajur (Worksheet) 10 kolom.
Input   : period_id (int).
Output  : DataFrame 10 kolom (5 pasang debit-kredit) + ringkasan laba/rugi.
Dipanggil oleh : views/11_neraca_lajur.py, services/statements_service.py

STRUKTUR NERACA LAJUR 10 KOLOM:
  Kolom 1-2 : Neraca Saldo sebelum penyesuaian (ns_debit | ns_kredit)
  Kolom 3-4 : Penyesuaian saja (peny_debit | peny_kredit)
  Kolom 5-6 : Neraca Saldo Disesuaikan = kolom 1-2 ditambah kolom 3-4 (nsd_debit | nsd_kredit)
  Kolom 7-8 : Laba Rugi — akun Pendapatan & Beban (lr_debit | lr_kredit)
  Kolom 9-10: Neraca    — akun Aset, Liabilitas, Ekuitas (neraca_debit | neraca_kredit)

LOGIKA PEMISAHAN KOLOM 7-8 vs 9-10:
  - Kategori 'Pendapatan', 'Beban Produksi', 'Beban Operasional' → masuk L/R
  - Kategori 'Aset', 'Liabilitas', 'Ekuitas'                   → masuk Neraca
  - Kolom L/R dan Neraca adalah cerminan kolom NSD (tidak bertambah/berkurang)

LABA BERSIH:
  Laba = total_kredit_LR - total_debit_LR  (positif = laba, negatif = rugi)
  Laba bersih ditambahkan ke Neraca sisi Kredit (ekuitas bertambah saat laba).
"""

import pandas as pd
from database.connection import get_connection
from services.trial_balance_service import hitung_neraca_saldo


# ---------------------------------------------------------------------------
# Fungsi utama
# ---------------------------------------------------------------------------

def buat_neraca_lajur(period_id: int) -> pd.DataFrame:
    """
    Membuat Neraca Lajur 10 kolom untuk satu periode.

    Args:
        period_id : ID periode yang ingin disusun neraca lajurnya.

    Returns:
        DataFrame dengan kolom:
        kode_akun | nama_akun | kategori |
        ns_debit | ns_kredit |
        peny_debit | peny_kredit |
        nsd_debit | nsd_kredit |
        lr_debit | lr_kredit |
        neraca_debit | neraca_kredit
    """
    # -------------------------------------------------------------------
    # LANGKAH 1: Ambil Neraca Saldo SEBELUM penyesuaian (kolom 1-2)
    # -------------------------------------------------------------------
    df_ns = hitung_neraca_saldo(period_id, termasuk_penyesuaian=False)

    # Jadikan dict: kode_akun → {debit, kredit, kategori, nama_akun}
    # Karena trial_balance hanya menampilkan akun yang punya saldo/mutasi,
    # kita gunakan DataFrame ini sebagai basis.
    dict_ns = {}
    for _, baris in df_ns.iterrows():
        dict_ns[baris["kode_akun"]] = {
            "nama_akun": baris["nama_akun"],
            "kategori": baris["kategori"],
            "saldo_normal": baris["saldo_normal"],
            "debit": int(baris["debit"]),
            "kredit": int(baris["kredit"]),
        }

    # -------------------------------------------------------------------
    # LANGKAH 2: Ambil mutasi penyesuaian saja (jurnal PA-) untuk kolom 3-4
    # -------------------------------------------------------------------
    dict_penyesuaian = _ambil_mutasi_penyesuaian(period_id)

    # -------------------------------------------------------------------
    # LANGKAH 3: Gabungkan semua kode_akun yang muncul di NS atau Penyesuaian
    # -------------------------------------------------------------------
    # Kita juga perlu info akun yang hanya muncul di penyesuaian (mis. akun baru)
    semua_kode = set(dict_ns.keys()) | set(dict_penyesuaian.keys())

    # Jika ada kode akun di penyesuaian tapi tidak di NS, ambil info akunnya
    dict_info_akun = _ambil_info_akun_dari_penyesuaian(period_id, semua_kode, dict_ns)

    # -------------------------------------------------------------------
    # LANGKAH 4: Susun baris-baris neraca lajur
    # -------------------------------------------------------------------
    baris_lajur = []

    # Urutan akun: ikuti urutan kode_akun
    for kode in sorted(semua_kode):
        # Info dasar akun
        if kode in dict_ns:
            info = dict_ns[kode]
        else:
            info = dict_info_akun.get(kode, {
                "nama_akun": kode,
                "kategori": "Lain-lain",
                "saldo_normal": "Debit",
                "debit": 0,
                "kredit": 0,
            })

        # Kolom 1-2: Neraca Saldo sebelum penyesuaian
        ns_debit = info["debit"]
        ns_kredit = info["kredit"]

        # Kolom 3-4: Penyesuaian (mutasi jurnal PA-)
        peny_data = dict_penyesuaian.get(kode, {"debit": 0, "kredit": 0})
        peny_debit = peny_data["debit"]
        peny_kredit = peny_data["kredit"]

        # Kolom 5-6: NS Disesuaikan = NS + Penyesuaian
        # Cara hitung: jumlahkan sisi debit dan kredit lalu hitung saldo akhir
        total_debit_akun = ns_debit + peny_debit
        total_kredit_akun = ns_kredit + peny_kredit

        saldo_normal = info["saldo_normal"]
        nsd_debit, nsd_kredit = _hitung_saldo_kolom(
            total_debit_akun, total_kredit_akun, saldo_normal
        )

        # Kolom 7-8 dan 9-10: pisahkan berdasarkan kategori
        kategori = info["kategori"]
        lr_debit, lr_kredit, neraca_debit, neraca_kredit = _pisahkan_lr_neraca(
            kategori, nsd_debit, nsd_kredit
        )

        baris_lajur.append({
            "kode_akun": kode,
            "nama_akun": info["nama_akun"],
            "kategori": kategori,
            "ns_debit": ns_debit,
            "ns_kredit": ns_kredit,
            "peny_debit": peny_debit,
            "peny_kredit": peny_kredit,
            "nsd_debit": nsd_debit,
            "nsd_kredit": nsd_kredit,
            "lr_debit": lr_debit,
            "lr_kredit": lr_kredit,
            "neraca_debit": neraca_debit,
            "neraca_kredit": neraca_kredit,
        })

    df_lajur = pd.DataFrame(baris_lajur, columns=[
        "kode_akun", "nama_akun", "kategori",
        "ns_debit", "ns_kredit",
        "peny_debit", "peny_kredit",
        "nsd_debit", "nsd_kredit",
        "lr_debit", "lr_kredit",
        "neraca_debit", "neraca_kredit",
    ])

    return df_lajur


def hitung_laba_rugi_dari_lajur(df_lajur: pd.DataFrame) -> int:
    """
    Menghitung laba atau rugi dari neraca lajur.

    Rumus:
        Laba Bersih = Total Kredit L/R - Total Debit L/R
        - Positif = laba (pendapatan > beban)
        - Negatif = rugi (beban > pendapatan)

    Args:
        df_lajur : DataFrame hasil buat_neraca_lajur().

    Returns:
        int : laba bersih dalam Rupiah (negatif jika rugi).
    """
    if df_lajur.empty:
        return 0

    total_kredit_lr = int(df_lajur["lr_kredit"].sum())
    total_debit_lr = int(df_lajur["lr_debit"].sum())

    # Laba = Pendapatan (sisi kredit L/R) - Beban (sisi debit L/R)
    laba_bersih = total_kredit_lr - total_debit_lr
    return laba_bersih


def validasi_neraca_lajur(df_lajur: pd.DataFrame) -> dict:
    """
    Memvalidasi keseimbangan tiap pasang kolom dalam neraca lajur.

    Returns:
        Dict berisi hasil validasi tiap pasang kolom:
        {
          'ns_seimbang': bool,
          'ns_total_debit': int,
          'ns_total_kredit': int,
          'nsd_seimbang': bool,
          'nsd_total_debit': int,
          'nsd_total_kredit': int,
          'laba_bersih': int,
          'neraca_seimbang_setelah_laba': bool,
        }
    """
    if df_lajur.empty:
        return {
            "ns_seimbang": True, "ns_total_debit": 0, "ns_total_kredit": 0,
            "nsd_seimbang": True, "nsd_total_debit": 0, "nsd_total_kredit": 0,
            "laba_bersih": 0, "neraca_seimbang_setelah_laba": True,
        }

    ns_d = int(df_lajur["ns_debit"].sum())
    ns_k = int(df_lajur["ns_kredit"].sum())
    nsd_d = int(df_lajur["nsd_debit"].sum())
    nsd_k = int(df_lajur["nsd_kredit"].sum())
    lr_d = int(df_lajur["lr_debit"].sum())
    lr_k = int(df_lajur["lr_kredit"].sum())
    neraca_d = int(df_lajur["neraca_debit"].sum())
    neraca_k = int(df_lajur["neraca_kredit"].sum())

    laba_bersih = lr_k - lr_d  # positif = laba

    # Neraca seimbang jika: neraca_debit == neraca_kredit + laba_bersih
    # (laba menambah ekuitas di sisi kredit)
    if laba_bersih >= 0:
        # Laba → ditambahkan ke sisi kredit neraca (ekuitas bertambah)
        neraca_seimbang = neraca_d == (neraca_k + laba_bersih)
    else:
        # Rugi → ditambahkan ke sisi debit neraca (ekuitas berkurang)
        neraca_seimbang = (neraca_d + abs(laba_bersih)) == neraca_k

    return {
        "ns_seimbang": ns_d == ns_k,
        "ns_total_debit": ns_d,
        "ns_total_kredit": ns_k,
        "nsd_seimbang": nsd_d == nsd_k,
        "nsd_total_debit": nsd_d,
        "nsd_total_kredit": nsd_k,
        "laba_bersih": laba_bersih,
        "neraca_seimbang_setelah_laba": neraca_seimbang,
    }


# ---------------------------------------------------------------------------
# Fungsi-fungsi pembantu (private)
# ---------------------------------------------------------------------------

def _ambil_mutasi_penyesuaian(period_id: int) -> dict:
    """
    Mengambil total debit dan kredit dari jurnal penyesuaian (no_bukti LIKE 'PA-%')
    per akun untuk periode tertentu.

    Returns:
        dict {kode_akun: {'debit': int, 'kredit': int}}
    """
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            """
            SELECT a.kode_akun,
                   COALESCE(SUM(jl.debit), 0)  AS total_debit,
                   COALESCE(SUM(jl.kredit), 0) AS total_kredit
            FROM journal_lines jl
            JOIN journal_entries je ON jl.journal_entry_id = je.id
            JOIN accounts a         ON jl.account_id = a.id
            WHERE je.period_id = ?
              AND je.no_bukti LIKE 'PA-%'
            GROUP BY a.kode_akun
            """,
            (period_id,)
        ).fetchall()
    finally:
        koneksi.close()

    return {
        r["kode_akun"]: {
            "debit": int(r["total_debit"]),
            "kredit": int(r["total_kredit"]),
        }
        for r in rows
    }


def _ambil_info_akun_dari_penyesuaian(
    period_id: int,
    semua_kode: set,
    dict_ns: dict,
) -> dict:
    """
    Mengambil info (nama_akun, kategori, saldo_normal) untuk kode akun
    yang ada di penyesuaian tapi tidak ada di NS (saldo awal nol).

    Returns:
        dict {kode_akun: {nama_akun, kategori, saldo_normal, debit: 0, kredit: 0}}
    """
    # Kode akun yang perlu dicari di database
    kode_perlu_dicari = [k for k in semua_kode if k not in dict_ns]
    if not kode_perlu_dicari:
        return {}

    koneksi = get_connection()
    try:
        # Buat placeholder dinamis sesuai jumlah kode
        placeholder = ",".join("?" for _ in kode_perlu_dicari)
        rows = koneksi.execute(
            f"""
            SELECT kode_akun, nama_akun, kategori, saldo_normal
            FROM accounts
            WHERE kode_akun IN ({placeholder})
            """,
            kode_perlu_dicari
        ).fetchall()
    finally:
        koneksi.close()

    return {
        r["kode_akun"]: {
            "nama_akun": r["nama_akun"],
            "kategori": r["kategori"],
            "saldo_normal": r["saldo_normal"],
            "debit": 0,
            "kredit": 0,
        }
        for r in rows
    }


def _hitung_saldo_kolom(
    total_debit: int,
    total_kredit: int,
    saldo_normal: str,
) -> tuple[int, int]:
    """
    Menghitung saldo akhir dan menempatkannya di kolom yang tepat.

    Args:
        total_debit  : total sisi debit (saldo awal D + mutasi D + penyesuaian D)
        total_kredit : total sisi kredit
        saldo_normal : 'Debit' atau 'Kredit'

    Returns:
        (kolom_debit, kolom_kredit) — salah satu pasti 0.
    """
    if saldo_normal == "Debit":
        # Akun debit: saldo = debit - kredit
        saldo = total_debit - total_kredit
        if saldo >= 0:
            return saldo, 0
        else:
            # Saldo tidak normal (mis. kas overdraft)
            return 0, abs(saldo)
    else:
        # Akun kredit: saldo = kredit - debit
        saldo = total_kredit - total_debit
        if saldo >= 0:
            return 0, saldo
        else:
            # Saldo tidak normal
            return abs(saldo), 0


def _pisahkan_lr_neraca(
    kategori: str,
    nsd_debit: int,
    nsd_kredit: int,
) -> tuple[int, int, int, int]:
    """
    Memisahkan saldo NS Disesuaikan ke kolom Laba Rugi atau Neraca.

    Aturan:
    - Pendapatan, Beban Produksi, Beban Operasional → masuk L/R
    - Aset, Liabilitas, Ekuitas                     → masuk Neraca

    Returns:
        (lr_debit, lr_kredit, neraca_debit, neraca_kredit)
    """
    kategori_lr = {"Pendapatan", "Beban Produksi", "Beban Operasional"}

    if kategori in kategori_lr:
        # Masuk kolom Laba Rugi
        return nsd_debit, nsd_kredit, 0, 0
    else:
        # Masuk kolom Neraca (Aset, Liabilitas, Ekuitas, dan lain-lain)
        return 0, 0, nsd_debit, nsd_kredit
