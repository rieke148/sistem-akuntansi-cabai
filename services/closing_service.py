"""
services/closing_service.py
-----------------------------
Tujuan  : Membuat jurnal penutup dan menghitung neraca saldo setelah penutup.
Input   : period_id (int), tanggal (str).
Output  : Jurnal penutup disimpan ke DB; neraca saldo setelah penutup sebagai DataFrame.
Dipanggil oleh : views/13_jurnal_penutup.py

JURNAL PENUTUP (urutan harus benar):
  1. Tutup semua akun Pendapatan → Ikhtisar Laba Rugi
       Dr  Pendapatan (masing-masing)
       Cr  Ikhtisar Laba Rugi  (3130)
  2. Tutup semua akun Beban → Ikhtisar Laba Rugi
       Dr  Ikhtisar Laba Rugi  (3130)
       Cr  Beban-beban (masing-masing)
  3. Pindahkan Ikhtisar Laba Rugi → Laba (3120)
       Jika Laba  → Dr Ikhtisar L/R  |  Cr Laba
       Jika Rugi  → Dr Laba Ditahan  |  Cr Ikhtisar L/R
  4. Ubah status periode → 'tutup'

CATATAN:
  - Karena ini PT, tidak ada akun Prive. Modal Disetor tetap.
  - No. bukti format: JP-{period_id}-{no urut} (mis. JP-1-1, JP-1-2, JP-1-3)
  - Semua jurnal penutup diawali 'JP-' — bisa dideteksi saat buat neraca setelah penutup.
"""

import pandas as pd
from database.connection import get_connection
from services.trial_balance_service import hitung_neraca_saldo
from services.journal_service import simpan_jurnal


# Kode akun khusus yang diperlukan jurnal penutup
KODE_IKHTISAR_LR = "3130"   # Ikhtisar Laba Rugi
KODE_LABA_DITAHAN = "3120"  # Laba Ditahan


# ---------------------------------------------------------------------------
# Fungsi utama
# ---------------------------------------------------------------------------

def preview_jurnal_penutup(period_id: int, tanggal: str) -> list[dict]:
    """
    Menghitung jurnal penutup TANPA menyimpan ke database (untuk pratinjau).

    Args:
        period_id : ID periode.
        tanggal   : Tanggal jurnal penutup (format 'YYYY-MM-DD').

    Returns:
        List of dict, tiap dict mewakili satu journal_entry:
        [
          {
            'no_bukti': str,
            'keterangan': str,
            'lines': [{'akun': str, 'nama': str, 'debit': int, 'kredit': int}, ...]
          },
          ...
        ]

    Raises:
        ValueError: Jika periode sudah ditutup.
        ValueError: Jika akun Ikhtisar L/R atau Laba Ditahan tidak ditemukan.
    """
    _validasi_periode_masih_buka(period_id)
    return _hitung_jurnal_penutup(period_id, tanggal)


def buat_jurnal_penutup(period_id: int, tanggal: str) -> list[int]:
    """
    Membuat dan menyimpan semua jurnal penutup untuk akhir periode.
    Periode TIDAK otomatis ditutup — user harus klik tutup_periode() secara terpisah.

    Args:
        period_id : ID periode.
        tanggal   : Tanggal jurnal penutup (format 'YYYY-MM-DD').

    Returns:
        List ID journal_entry yang dibuat (biasanya 3 entri).

    Raises:
        ValueError: Jika periode sudah ditutup.
        ValueError: Jika jurnal penutup sudah pernah dibuat sebelumnya.
        ValueError: Jika akun Ikhtisar L/R atau Laba Ditahan tidak ditemukan.
    """
    _validasi_periode_masih_buka(period_id)
    _validasi_belum_ada_jurnal_penutup(period_id)

    # Hitung jurnal penutup
    rencana_jurnal = _hitung_jurnal_penutup(period_id, tanggal)

    # Simpan ke database
    id_list = []
    for jurnal in rencana_jurnal:
        baris_jurnal = [
            {"account_id": item["account_id"], "debit": item["debit"], "kredit": item["kredit"]}
            for item in jurnal["lines_raw"]
        ]
        journal_id = simpan_jurnal(
            period_id=period_id,
            tanggal=tanggal,
            no_bukti=jurnal["no_bukti"],
            journal_type="umum",
            keterangan=jurnal["keterangan"],
            baris=baris_jurnal,
        )
        id_list.append(journal_id)

    return id_list


def tutup_periode(period_id: int) -> None:
    """
    Mengubah status periode menjadi 'tutup'.
    Setelah ditutup, tidak ada transaksi yang bisa ditambah atau diedit.

    Args:
        period_id : ID periode yang akan ditutup.

    Raises:
        ValueError: Jika jurnal penutup belum dibuat.
        ValueError: Jika periode sudah tutup sebelumnya.
    """
    _validasi_periode_masih_buka(period_id)
    _validasi_sudah_ada_jurnal_penutup(period_id)

    koneksi = get_connection()
    try:
        koneksi.execute(
            "UPDATE periods SET status = 'tutup' WHERE id = ?",
            (period_id,)
        )
        koneksi.commit()
    finally:
        koneksi.close()


def cek_jurnal_penutup_sudah_ada(period_id: int) -> bool:
    """
    Mengecek apakah jurnal penutup sudah pernah dibuat untuk periode ini.

    Returns:
        True jika sudah ada jurnal JP-, False jika belum.
    """
    koneksi = get_connection()
    try:
        row = koneksi.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM journal_entries
            WHERE period_id = ?
              AND no_bukti LIKE 'JP-%'
            """,
            (period_id,)
        ).fetchone()
    finally:
        koneksi.close()

    return int(row["cnt"]) > 0


def hitung_neraca_saldo_setelah_penutup(period_id: int) -> pd.DataFrame:
    """
    Menghitung Neraca Saldo Setelah Penutup.
    Hanya menampilkan akun permanen (Aset, Liabilitas, Ekuitas).
    Akun sementara (Pendapatan, Beban, Ikhtisar L/R) seharusnya bersaldo nol.

    Args:
        period_id : ID periode.

    Returns:
        DataFrame: kode_akun | nama_akun | kategori | debit | kredit
    """
    # NS sesudah penyesuaian sudah mencakup jurnal penyesuaian (PA-)
    # Kita perlu menambahkan jurnal penutup (JP-) juga
    df_ns = _hitung_ns_termasuk_penutup(period_id)

    # Filter: hanya tampilkan akun permanen dan yang bersaldo tidak nol
    kategori_permanen = {"Aset", "Liabilitas", "Ekuitas"}
    df_permanen = df_ns[
        df_ns["kategori"].isin(kategori_permanen) &
        ((df_ns["debit"] > 0) | (df_ns["kredit"] > 0))
    ].copy()

    return df_permanen.reset_index(drop=True)


def hapus_jurnal_penutup(period_id: int) -> bool:
    """
    Menghapus jurnal penutup (JP-) jika periode belum ditutup.
    Berguna jika user ingin mengubah data lalu buat jurnal penutup ulang.

    Returns:
        True jika berhasil dihapus, False jika tidak ada yang dihapus.
    """
    _validasi_periode_masih_buka(period_id)

    koneksi = get_connection()
    try:
        # Ambil ID journal_entries yang akan dihapus
        rows = koneksi.execute(
            """
            SELECT id FROM journal_entries
            WHERE period_id = ? AND no_bukti LIKE 'JP-%'
            """,
            (period_id,)
        ).fetchall()

        if not rows:
            return False

        id_list = [r["id"] for r in rows]
        placeholder = ",".join("?" for _ in id_list)

        # Hapus journal_lines dulu (ada FK constraint)
        koneksi.execute(
            f"DELETE FROM journal_lines WHERE journal_entry_id IN ({placeholder})",
            id_list
        )
        # Hapus journal_entries
        koneksi.execute(
            f"DELETE FROM journal_entries WHERE id IN ({placeholder})",
            id_list
        )
        koneksi.commit()
        return True
    finally:
        koneksi.close()


# ---------------------------------------------------------------------------
# Fungsi pembantu (private)
# ---------------------------------------------------------------------------

def _validasi_periode_masih_buka(period_id: int) -> None:
    """Melempar ValueError jika periode sudah tutup."""
    koneksi = get_connection()
    try:
        row = koneksi.execute(
            "SELECT status FROM periods WHERE id = ?",
            (period_id,)
        ).fetchone()
    finally:
        koneksi.close()

    if row is None:
        raise ValueError(f"Periode ID {period_id} tidak ditemukan.")
    if row["status"] == "tutup":
        raise ValueError(f"Periode ID {period_id} sudah ditutup dan tidak bisa diubah.")


def _validasi_belum_ada_jurnal_penutup(period_id: int) -> None:
    """Melempar ValueError jika jurnal penutup sudah ada."""
    if cek_jurnal_penutup_sudah_ada(period_id):
        raise ValueError(
            f"Jurnal penutup untuk periode {period_id} sudah pernah dibuat. "
            "Hapus dulu sebelum membuat ulang."
        )


def _validasi_sudah_ada_jurnal_penutup(period_id: int) -> None:
    """Melempar ValueError jika jurnal penutup belum ada (syarat untuk tutup periode)."""
    if not cek_jurnal_penutup_sudah_ada(period_id):
        raise ValueError(
            f"Jurnal penutup belum dibuat. Buat jurnal penutup dahulu sebelum menutup periode."
        )


def _ambil_id_akun(kode_akun: str) -> int:
    """Mengambil ID akun berdasarkan kode akun. Raise ValueError jika tidak ditemukan."""
    koneksi = get_connection()
    try:
        row = koneksi.execute(
            "SELECT id, nama_akun FROM accounts WHERE kode_akun = ?",
            (kode_akun,)
        ).fetchone()
    finally:
        koneksi.close()

    if row is None:
        raise ValueError(
            f"Akun dengan kode '{kode_akun}' tidak ditemukan. "
            "Pastikan akun Ikhtisar Laba Rugi (3130) dan Laba (3120) sudah ada."
        )
    return int(row["id"])


def _hitung_jurnal_penutup(period_id: int, tanggal: str) -> list[dict]:
    """
    Menghitung jurnal penutup dari saldo bersih akun pendapatan dan beban.

    Saldo bersih diperlukan karena akun 5110 juga menerima kredit ketika
    biaya produksi dipindahkan menjadi persediaan hasil panen.
    """
    df_ns = hitung_neraca_saldo(period_id, termasuk_penyesuaian=True)
    if df_ns.empty:
        return []

    id_ikhtisar = _ambil_id_akun(KODE_IKHTISAR_LR)
    id_laba_ditahan = _ambil_id_akun(KODE_LABA_DITAHAN)
    dict_akun_id = _ambil_semua_akun_id()

    akun_pendapatan = df_ns[df_ns["kategori"] == "Pendapatan"].copy()
    akun_beban = df_ns[
        df_ns["kategori"].isin(["Beban Produksi", "Beban Operasional"])
    ].copy()

    hasil: list[dict] = []

    # Saldo pendapatan bersih normalnya kredit. Akun yang bersaldo debit
    # tetap ditutup dengan arah kebalikan agar saldonya menjadi nol.
    baris_pendapatan: list[dict] = []
    raw_pendapatan: list[dict] = []
    total_pendapatan_bersih = 0
    for _, baris in akun_pendapatan.iterrows():
        nilai_bersih = int(baris["kredit"]) - int(baris["debit"])
        total_pendapatan_bersih += nilai_bersih
        if nilai_bersih == 0:
            continue

        jumlah = abs(nilai_bersih)
        debit = jumlah if nilai_bersih > 0 else 0
        kredit = jumlah if nilai_bersih < 0 else 0
        baris_pendapatan.append({
            "akun": baris["kode_akun"],
            "nama": baris["nama_akun"],
            "debit": debit,
            "kredit": kredit,
        })
        aid = dict_akun_id.get(baris["kode_akun"])
        hasil_baris_akun = {
            "account_id": aid,
            "debit": debit,
            "kredit": kredit,
        }
        # Simpan raw lines untuk jurnal penutup.
        raw_pendapatan.append(hasil_baris_akun)

    if total_pendapatan_bersih != 0:
        jumlah = abs(total_pendapatan_bersih)
        # Pendapatan bersaldo kredit ditutup dengan kredit ke ikhtisar.
        # Bila saldo pendapatan bersih debit, arah kredit/debit dibalik.
        baris_pendapatan.append({
            "akun": KODE_IKHTISAR_LR,
            "nama": "Ikhtisar Laba Rugi",
            "debit": 0 if total_pendapatan_bersih > 0 else jumlah,
            "kredit": jumlah if total_pendapatan_bersih > 0 else 0,
        })
        raw_pendapatan.append({
            "account_id": id_ikhtisar,
            "debit": 0 if total_pendapatan_bersih > 0 else jumlah,
            "kredit": jumlah if total_pendapatan_bersih > 0 else 0,
        })
        hasil.append({
            "no_bukti": f"JP-{period_id}-1",
            "keterangan": "Jurnal Penutup 1: Tutup akun Pendapatan",
            "lines": baris_pendapatan,
            "lines_raw": raw_pendapatan,
        })

    # Saldo beban bersih normalnya debit. Kredit pada 5110 bisa berasal
    # dari kapitalisasi hasil panen dan harus mengurangi saldo bebannya.
    baris_beban: list[dict] = []
    raw_beban: list[dict] = []
    total_beban_bersih = 0
    for _, baris in akun_beban.iterrows():
        nilai_bersih = int(baris["debit"]) - int(baris["kredit"])
        total_beban_bersih += nilai_bersih
        if nilai_bersih == 0:
            continue

        jumlah = abs(nilai_bersih)
        debit = 0 if nilai_bersih > 0 else jumlah
        kredit = jumlah if nilai_bersih > 0 else 0
        baris_beban.append({
            "akun": baris["kode_akun"],
            "nama": baris["nama_akun"],
            "debit": debit,
            "kredit": kredit,
        })
        raw_beban.append({
            "account_id": dict_akun_id.get(baris["kode_akun"]),
            "debit": debit,
            "kredit": kredit,
        })

    if total_beban_bersih != 0:
        jumlah = abs(total_beban_bersih)
        # Beban bersaldo debit ditutup dengan debit ke ikhtisar.
        # Jika saldo bersih beban justru kredit, arah penutup dibalik.
        baris_beban.insert(0, {
            "akun": KODE_IKHTISAR_LR,
            "nama": "Ikhtisar Laba Rugi",
            "debit": jumlah if total_beban_bersih > 0 else 0,
            "kredit": 0 if total_beban_bersih > 0 else jumlah,
        })
        raw_beban.insert(0, {
            "account_id": id_ikhtisar,
            "debit": jumlah if total_beban_bersih > 0 else 0,
            "kredit": 0 if total_beban_bersih > 0 else jumlah,
        })
        hasil.append({
            "no_bukti": f"JP-{period_id}-2",
            "keterangan": "Jurnal Penutup 2: Tutup akun Beban",
            "lines": baris_beban,
            "lines_raw": raw_beban,
        })

    # Laba/rugi adalah pendapatan bersih dikurangi beban bersih.
    laba_bersih = total_pendapatan_bersih - total_beban_bersih
    if laba_bersih != 0:
        jumlah = abs(laba_bersih)
        if laba_bersih > 0:
            lines = [
                {"akun": KODE_IKHTISAR_LR, "nama": "Ikhtisar Laba Rugi",
                 "debit": jumlah, "kredit": 0},
                {"akun": KODE_LABA_DITAHAN, "nama": "Laba",
                 "debit": 0, "kredit": jumlah},
            ]
            lines_raw = [
                {"account_id": id_ikhtisar, "debit": jumlah, "kredit": 0},
                {"account_id": id_laba_ditahan, "debit": 0, "kredit": jumlah},
            ]
            keterangan = "Jurnal Penutup 3: Pindah Laba Bersih ke Laba"
        else:
            lines = [
                {"akun": KODE_LABA_DITAHAN, "nama": "Laba",
                 "debit": jumlah, "kredit": 0},
                {"akun": KODE_IKHTISAR_LR, "nama": "Ikhtisar Laba Rugi",
                 "debit": 0, "kredit": jumlah},
            ]
            lines_raw = [
                {"account_id": id_laba_ditahan, "debit": jumlah, "kredit": 0},
                {"account_id": id_ikhtisar, "debit": 0, "kredit": jumlah},
            ]
            keterangan = "Jurnal Penutup 3: Pindah Rugi Bersih ke Laba"

        hasil.append({
            "no_bukti": f"JP-{period_id}-3",
            "keterangan": keterangan,
            "lines": lines,
            "lines_raw": lines_raw,
        })

    return hasil
def _hitung_ns_termasuk_penutup(period_id: int) -> pd.DataFrame:
    """
    Menghitung NS yang mencakup semua jurnal (termasuk PA- dan JP-).
    Digunakan untuk Neraca Saldo Setelah Penutup.

    Returns:
        DataFrame: kode_akun | nama_akun | kategori | saldo_normal | debit | kredit
    """
    from services.trial_balance_service import hitung_neraca_saldo

    # hitung_neraca_saldo dengan termasuk_penyesuaian=True sudah mencakup semua jurnal
    # kecuali jurnal penutup. Kita perlu menambahkan mutasi dari jurnal JP- secara manual.
    df_ns = hitung_neraca_saldo(period_id, termasuk_penyesuaian=True)

    # Ambil mutasi dari jurnal penutup
    koneksi = get_connection()
    try:
        mutasi_jp = koneksi.execute(
            """
            SELECT a.kode_akun, a.nama_akun, a.kategori, a.saldo_normal,
                   COALESCE(SUM(jl.debit), 0)  AS total_debit,
                   COALESCE(SUM(jl.kredit), 0) AS total_kredit
            FROM journal_lines jl
            JOIN journal_entries je ON jl.journal_entry_id = je.id
            JOIN accounts a ON jl.account_id = a.id
            WHERE je.period_id = ?
              AND je.no_bukti LIKE 'JP-%'
            GROUP BY a.kode_akun
            """,
            (period_id,)
        ).fetchall()
    finally:
        koneksi.close()

    if not mutasi_jp:
        return df_ns

    # Konversi df_ns ke dict untuk update mudah
    dict_ns = {row["kode_akun"]: row.to_dict() for _, row in df_ns.iterrows()}

    for r in mutasi_jp:
        kode = r["kode_akun"]
        d = int(r["total_debit"])
        k = int(r["total_kredit"])

        if kode in dict_ns:
            # Update saldo yang ada
            baris = dict_ns[kode]
            # Hitung ulang saldo berdasarkan saldo_normal
            existing_d = baris["debit"]
            existing_k = baris["kredit"]

            if baris["saldo_normal"] == "Debit":
                saldo_lama = existing_d - existing_k
                saldo_baru = saldo_lama + d - k
                dict_ns[kode]["debit"] = max(saldo_baru, 0)
                dict_ns[kode]["kredit"] = max(-saldo_baru, 0)
            else:
                saldo_lama = existing_k - existing_d
                saldo_baru = saldo_lama + k - d
                dict_ns[kode]["kredit"] = max(saldo_baru, 0)
                dict_ns[kode]["debit"] = max(-saldo_baru, 0)
        else:
            # Akun baru (Ikhtisar L/R mungkin belum ada di NS sebelum penutup)
            saldo_normal = r["saldo_normal"]
            if saldo_normal == "Debit":
                saldo = d - k
                dict_ns[kode] = {
                    "kode_akun": kode,
                    "nama_akun": r["nama_akun"],
                    "kategori": r["kategori"],
                    "saldo_normal": saldo_normal,
                    "debit": max(saldo, 0),
                    "kredit": max(-saldo, 0),
                }
            else:
                saldo = k - d
                dict_ns[kode] = {
                    "kode_akun": kode,
                    "nama_akun": r["nama_akun"],
                    "kategori": r["kategori"],
                    "saldo_normal": saldo_normal,
                    "debit": max(-saldo, 0),
                    "kredit": max(saldo, 0),
                }

    baris_list = sorted(dict_ns.values(), key=lambda x: x["kode_akun"])
    return pd.DataFrame(baris_list, columns=[
        "kode_akun", "nama_akun", "kategori", "saldo_normal", "debit", "kredit"
    ])


def _ambil_semua_akun_id() -> dict:
    """
    Mengambil mapping kode_akun → account_id untuk semua akun aktif.

    Returns:
        dict {kode_akun: id}
    """
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            "SELECT id, kode_akun FROM accounts WHERE aktif = 1"
        ).fetchall()
    finally:
        koneksi.close()

    return {r["kode_akun"]: r["id"] for r in rows}
